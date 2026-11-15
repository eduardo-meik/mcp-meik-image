"""MCP tools exposed to Claude / any MCP client."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import uuid4

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.utilities.types import Image
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from . import prompts
from .brand import (
    DEFAULT_PALETTE,
    DEFAULT_SLIDE_TYPE,
    DEFAULT_STYLE,
    FORMATS,
    PALETTES,
    SLIDE_TYPES,
    STYLES,
    TEXT_SPACES,
    Palette,
    get_brand_kit,
    resolve_format,
    resolve_palette,
    resolve_slide_type,
    resolve_style,
)
from .config import load_settings
from .imaging import dimensions, extension_for, fit_inline
from .media import MediaError, MediaPublisher, publisher_from_settings
from .openrouter import GeneratedImage, GenerationResult, ImageGenerationError, OpenRouterImageClient
from .optimize import extension_of, normalize_format, optimize_image
from .presets import SIZES, catalog as size_catalog, resolve_size
from .stock import StockError, UnsplashClient, client_from_settings
from .storage import AssetStore, slugify
from .styleguide import blog_style_guide as build_blog_style_guide

logger = logging.getLogger("meik_image.tools")

PaletteName = Literal[tuple(sorted(PALETTES))]  # type: ignore[valid-type]
StyleName = Literal[tuple(sorted(STYLES))]  # type: ignore[valid-type]
FormatName = Literal[tuple(sorted(FORMATS))]  # type: ignore[valid-type]
SlideTypeName = Literal[tuple(sorted(SLIDE_TYPES))]  # type: ignore[valid-type]
TextSpace = Literal[tuple(sorted(TEXT_SPACES))]  # type: ignore[valid-type]
SizeName = Literal[tuple(sorted(SIZES))]  # type: ignore[valid-type]

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
GENERATES = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)


class OutputSpec(BaseModel):
    """Tamaño, formato y publicación de la imagen entregada."""

    size: SizeName | None = Field(
        None,
        description=(
            "Preset de tamaño por destino: linkedin-post (1200x627), linkedin-square, "
            "linkedin-company-cover (1584x396), blog-hero (1600x900), blog-diagram (1600x1131), "
            "blog-wide (2400x1200), og-image (1200x630), instagram-story, youtube-thumb, slide "
            "(1920x1080), etc. Si lo indicas, sobrescribe width/height/fit y elige la proporción "
            "correcta para el modelo."
        ),
    )
    format: Literal["webp", "jpeg", "png", "avif", "auto"] = Field(
        "auto",
        description=(
            "Formato de salida. 'auto' usa el del servidor (webp por defecto). "
            "webp/jpeg son los más livianos para blog; png no pierde calidad; avif comprime más pero "
            "tarda más en codificar."
        ),
    )
    quality: int | None = Field(
        None, ge=40, le=100, description="Calidad 40-100. Si falta se usa 82 (webp), 85 (jpeg), 60 (avif)."
    )
    width: int | None = Field(
        None, ge=64, le=4096, description="Ancho exacto en píxeles. Recraft sólo entrega proporciones, así que el recorte/escala se hace aquí."
    )
    height: int | None = Field(None, ge=64, le=4096, description="Alto exacto en píxeles.")
    fit: Literal["cover", "contain", "stretch"] = Field(
        "cover",
        description=(
            "Cómo encajar el tamaño exacto: 'cover' recorta para llenar (recomendado), "
            "'contain' agrega relleno, 'stretch' deforma."
        ),
    )
    max_kb: int | None = Field(
        None, ge=10, le=5000, description="Peso máximo del archivo en KB; baja calidad/escala hasta cumplirlo."
    )
    publish: bool = Field(
        True,
        description=(
            "Subir la imagen al media server (cPanel) y devolver la URL pública. "
            "Si el servidor no está configurado se ignora sin fallar."
        ),
    )
    filename: str | None = Field(
        None,
        description=(
            "Nombre exacto del archivo, sin extensión (p. ej. el slug del post). Úsalo cuando la "
            "URL deba ser predecible: /img/blog/<slug>.webp. Si falta, se usa el slug del título "
            "más un sufijo único."
        ),
    )


def _store() -> AssetStore:
    return AssetStore(load_settings().image_dir)


def _generate(
    prompt: str,
    *,
    aspect_ratio: str,
    n: int,
    palette: Palette,
    model: str | None = None,
) -> GenerationResult:
    settings = load_settings()
    client = OpenRouterImageClient(settings)
    colors = palette.colors if palette.id != "none" else None
    return client.generate(prompt, aspect_ratio=aspect_ratio, n=n, model=model, palette_colors=colors)


def _resolve_output(
    output: OutputSpec | None,
    *,
    default_aspect: str,
) -> tuple[OutputSpec, str]:
    """Expand a size preset into pixels and pick the closest aspect ratio for the model."""
    spec = output or OutputSpec()
    preset = resolve_size(spec.size)
    if preset is None:
        return spec, default_aspect
    resolved = spec.model_copy(
        update={
            "width": spec.width or preset.width,
            "height": spec.height or preset.height,
            "fit": preset.fit,
            "max_kb": spec.max_kb or preset.max_kb,
        }
    )
    return resolved, preset.model_ratio


def _deliver(
    result: GenerationResult,
    *,
    prompt: str,
    slug: str,
    meta: dict[str, Any],
    output: OutputSpec | None = None,
) -> list[Any]:
    """Optimize each render, save it locally, publish it, then return it inline."""
    settings = load_settings()
    store = _store()
    publisher = MediaPublisher(settings.media)
    spec = output or OutputSpec()
    try:
        fmt = normalize_format(spec.format, settings.output_format)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc

    content: list[Any] = []
    images_meta: list[dict[str, Any]] = []
    publish_errors: list[str] = []
    stamp = datetime.now().strftime("%H%M%S")

    for index, generated in enumerate(result.images, start=1):
        source_w, source_h = dimensions(generated.data)
        processed = optimize_image(
            generated.data,
            generated.media_type,
            output_format=fmt,
            quality=spec.quality,
            width=spec.width,
            height=spec.height,
            fit=spec.fit,
            max_kb=spec.max_kb,
        )
        filename_stem = (spec.filename or "").strip()
        if filename_stem:
            filename = f"{slugify(filename_stem, max_words=12)}.{extension_of(processed)}"
        elif settings.media.naming == "slug":
            filename = f"{slugify(slug)}.{extension_of(processed)}"
        else:
            filename = f"{slugify(slug)}-{stamp}-{uuid4().hex[:6]}.{extension_of(processed)}"
        entry: dict[str, Any] = {
            "index": index,
            "format": processed.fmt,
            "bytes": processed.size_bytes,
            "width": processed.width,
            "height": processed.height,
            "source_dimensions": f"{source_w}x{source_h}" if source_w else None,
            "optimization": list(processed.steps),
        }

        asset = store.save(
            processed.data,
            processed.media_type,
            slug=slug,
            filename=filename,
            metadata={
                "prompt": prompt,
                "model": result.model,
                "aspect_ratio": result.aspect_ratio,
                "format": processed.fmt,
                "optimization": list(processed.steps),
                **meta,
            },
        )
        if asset is not None:
            entry["asset_id"] = asset.asset_id
            entry["saved_to"] = str(asset.path)

        if spec.publish and publisher.configured:
            try:
                published = publisher.publish(processed.data, filename)
                entry["public_url"] = published.url
                entry["remote_path"] = published.remote_path
                entry["published_via"] = published.transport
            except MediaError as exc:
                entry["publish_error"] = str(exc)
                publish_errors.append(f"{filename}: {exc}")

        payload = fit_inline(processed.data, processed.media_type, settings.inline_max_chars)
        entry["inline"] = {
            "media_type": payload.media_type,
            "width": payload.width,
            "height": payload.height,
            "base64_chars": payload.base64_chars,
            "downscaled_for_client": payload.downscaled,
        }
        images_meta.append(entry)
        content.append(Image(data=payload.data, format=extension_for(payload.media_type)))

    manifest: dict[str, Any] = {
        "status": "ok",
        "model": result.model,
        "aspect_ratio": result.aspect_ratio,
        "count": len(result.images),
        "cost_usd": result.cost_usd,
        "duration_seconds": result.duration_seconds,
        "prompt": prompt,
        **meta,
        "output": {
            "format": fmt,
            "requested": spec.model_dump(exclude_none=True),
            "media_server_configured": publisher.configured,
        },
        "images": images_meta,
        "storage": {
            "enabled": store.enabled,
            "root": str(store.root) if store.root else None,
        },
    }

    notes: list[str] = []
    if not store.enabled:
        notes.append(
            "Almacenamiento local deshabilitado (entorno remoto): no hay archivo persistente en el servidor."
        )
    if spec.publish and not publisher.configured:
        notes.append(
            "Publicación omitida: el media server no está configurado "
            "(MEIK_MEDIA_HOST/USER/PASSWORD/REMOTE_DIR/BASE_URL)."
        )
    if publish_errors:
        notes.append("Falló la publicación en el media server: " + " | ".join(publish_errors))
    if any(entry["inline"]["downscaled_for_client"] for entry in images_meta) and not publish_errors:
        notes.append(
            "La copia inline se recomprimió para caber en el límite del cliente; "
            "usa public_url o saved_to para la versión definitiva."
        )
    if notes:
        manifest["notes"] = notes

    content.append(json.dumps(manifest, ensure_ascii=False, indent=2))
    return content


def _fail(exc: Exception) -> ToolError:
    logger.warning("Tool error: %s", exc)
    return ToolError(str(exc))


def register_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        name="brand_kit",
        description=(
            "Devuelve el kit de marca de Meik Labs: colores oficiales (violeta #4F00C4, magenta "
            "#FF5CF3, tinta #1C1C1C, papel #F5F5F5), tipografías, paletas, estilos visuales, "
            "formatos y arquetipos de slide disponibles. Úsalo antes de generar para elegir "
            "style/palette correctos."
        ),
        annotations=READ_ONLY,
        output_schema=None,
    )
    def brand_kit() -> str:
        kit = get_brand_kit()
        payload = {
            "brand": kit.name,
            "tagline": kit.tagline,
            "fonts": list(kit.fonts),
            "colors": {
                "primary": kit.primary_hex,
                "secondary": kit.secondary_hex,
                "ink": kit.ink_hex,
                "paper": kit.paper_hex,
            },
            "palettes": {
                key: {"name": p.name, "description": p.description} for key, p in kit.palettes.items()
            },
            "styles": {
                key: {
                    "name": s.name,
                    "description": s.description,
                    "best_for": list(s.best_for),
                }
                for key, s in kit.styles.items()
            },
            "formats": {
                key: {"name": f.name, "aspect_ratio": f.aspect_ratio, "purpose": f.purpose}
                for key, f in kit.formats.items()
            },
            "slide_types": {
                key: {"name": s.name, "description": s.description} for key, s in kit.slide_types.items()
            },
            "sizes": size_catalog(),
            "blog_register": {
                "estilos": ["blog-satire", "blog-diagram", "blog-mascot"],
                "tono": "relajado, irónico y absurdo; consulta la herramienta blog_style_guide",
            },
            "defaults": {
                "style": DEFAULT_STYLE,
                "palette": DEFAULT_PALETTE,
                "slide_type": DEFAULT_SLIDE_TYPE,
                "text_space": "left",
            },
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    @mcp.tool(
        name="generate_image",
        description=(
            "Genera una o varias imágenes desde texto (Recraft V4.1 Flash V2) con estilos y paletas "
            "de Meik Labs. Úsalo para cualquier imagen suelta: ilustraciones de blog, visuales de "
            "slides, portadas, fondos o assets sociales. Devuelve las imágenes inline y guarda el "
            "original a resolución completa cuando hay disco disponible."
        ),
        annotations=GENERATES,
        output_schema=None,
    )
    def generate_image(
        prompt: Annotated[
            str,
            Field(
                description=(
                    "Qué se quiere ver, en lenguaje visual concreto (sujeto, materiales, luz, "
                    "composición). No pidas texto en la imagen: el modelo lo renderiza mal."
                )
            ),
        ],
        style: Annotated[
            StyleName,
            Field(description="Preset visual de la marca. Default: abstract-geometric."),
        ] = DEFAULT_STYLE,
        palette: Annotated[
            PaletteName,
            Field(description="Paleta de color. Default: brand-dark."),
        ] = DEFAULT_PALETTE,
        aspect_ratio: Annotated[
            Literal["16:9", "4:3", "3:4", "1:1", "9:16", "auto"],
            Field(description="Proporción soportada por el modelo. Default: 16:9."),
        ] = "16:9",
        n: Annotated[int, Field(ge=1, le=6, description="Cantidad de variantes (1-6).")] = 1,
        text_space: Annotated[
            TextSpace | None,
            Field(description="Zona reservada para texto superpuesto (left/right/top/bottom/center/none)."),
        ] = None,
        mood: Annotated[str | None, Field(description="Tono emocional: sobrio, energético, cálido…")] = None,
        must_include: Annotated[str | None, Field(description="Elementos obligatorios en la escena.")] = None,
        must_avoid: Annotated[str | None, Field(description="Elementos a excluir explícitamente.")] = None,
        strict_palette: Annotated[
            bool, Field(description="Fijar los colores de marca vía controles del proveedor.")
        ] = True,
        allow_text: Annotated[
            bool,
            Field(
                description=(
                    "Permitir texto en la imagen (por ejemplo un wordmark). Default false: "
                    "las imágenes salen sin letras para que el copy se componga en HTML/slides."
                )
            ),
        ] = False,
        slug: Annotated[str | None, Field(description="Nombre de archivo base. Si falta, se deriva del prompt.")] = None,
        output: Annotated[
            OutputSpec | None,
            Field(description="Tamaño exacto (px), formato de salida y publicación en el media server."),
        ] = None,
        model: Annotated[

            str | None,

            Field(description="Modelo de OpenRouter para esta llamada. Usa google/gemini-3.1-flash-image cuando la imagen deba llevar texto legible en español. Default: el configurado en el servidor."),

        ] = None,

    ) -> list[Any]:
        try:
            resolved_style = resolve_style(style)
            resolved_palette = resolve_palette(palette)
            output_spec, aspect = _resolve_output(output, default_aspect=aspect_ratio)
            final_prompt = prompts.compose_freeform(
                prompt,
                style=resolved_style,
                palette=resolved_palette,
                text_space=text_space,
                strict_palette=strict_palette,
                allow_text=allow_text,
                mood=mood,
                must_include=must_include,
                must_avoid=must_avoid,
            )
            result = _generate(
                final_prompt,
                aspect_ratio=aspect,
                n=n,
                model=model,
                palette=resolved_palette,
            )
        except (ValueError, ImageGenerationError) as exc:
            raise _fail(exc) from exc

        file_slug = slug or prompts.compose_filename_slug(prompt)
        return _deliver(
            result,
            prompt=final_prompt,
            slug=file_slug,
            output=output_spec,
            meta={
                "kind": "freeform",
                "style": resolved_style.id,
                "palette": resolved_palette.id,
                "text_space": text_space or "none",
                "alt_text_hint": prompts.suggest_alt_text(
                    subject=prompt.strip(),
                    style=resolved_style,
                    palette=resolved_palette,
                    purpose="imagen de contenido",
                ),
            },
        )

    @mcp.tool(
        name="generate_blog_hero",
        description=(
            "Genera la imagen de cabecera (hero/OG) de un artículo de blog de Meik Labs en 16:9, "
            "con espacio negativo reservado para el titular. Pasa el título y, si existe, el ángulo "
            "del artículo."
        ),
        annotations=GENERATES,
        output_schema=None,
    )
    def generate_blog_hero(
        title: Annotated[str, Field(description="Titular del artículo.")],
        angle: Annotated[str | None, Field(description="De qué trata realmente el artículo (1-2 frases).")] = None,
        keywords: Annotated[
            list[str] | None,
            Field(description="3-6 conceptos clave que la imagen debe evocar visualmente."),
        ] = None,
        style: Annotated[StyleName, Field(description="Preset visual.")] = DEFAULT_STYLE,
        palette: Annotated[
            PaletteName,
            Field(description="Paleta de color. Default natural: foto neutra sin filtro."),
        ] = "natural",
        text_space: Annotated[
            TextSpace,
            Field(description="Lado donde se reserva el espacio para el titular."),
        ] = "left",
        n: Annotated[int, Field(ge=1, le=6, description="Cantidad de variantes.")] = 1,
        mood: Annotated[str | None, Field(description="Tono emocional de la marca.")] = None,
        strict_palette: Annotated[bool, Field(description="Forzar colores de marca en el proveedor.")] = True,
        allow_text: Annotated[bool, Field(description="Permitir texto dentro de la imagen.")] = False,
        output: Annotated[
            OutputSpec | None,
            Field(description="Tamaño exacto (px), formato de salida y publicación en el media server."),
        ] = None,
        model: Annotated[

            str | None,

            Field(description="Modelo de OpenRouter para esta llamada. Usa google/gemini-3.1-flash-image cuando la imagen deba llevar texto legible en español. Default: el configurado en el servidor."),

        ] = None,

    ) -> list[Any]:
        try:
            resolved_style = resolve_style(style)
            resolved_palette = resolve_palette(palette)
            media_format = resolve_format("blog-hero")
            output_spec, aspect = _resolve_output(output, default_aspect=media_format.aspect_ratio)
            final_prompt = prompts.compose_blog_hero(
                title=title,
                angle=angle,
                keywords=keywords,
                style=resolved_style,
                palette=resolved_palette,
                text_space=text_space,
                strict_palette=strict_palette,
                allow_text=allow_text,
                mood=mood,
            )
            result = _generate(
                final_prompt,
                aspect_ratio=aspect,
                n=n,
                model=model,
                palette=resolved_palette,
            )
        except (ValueError, ImageGenerationError) as exc:
            raise _fail(exc) from exc

        return _deliver(
            result,
            prompt=final_prompt,
            slug=f"blog-hero-{title}",
            output=output_spec,
            meta={
                "kind": "blog-hero",
                "title": title,
                "format": media_format.id,
                "style": resolved_style.id,
                "palette": resolved_palette.id,
                "text_space": text_space,
                "alt_text_hint": prompts.suggest_alt_text(
                    subject=angle or title,
                    style=resolved_style,
                    palette=resolved_palette,
                    purpose=f"el artículo «{title}»",
                ),
            },
        )

    @mcp.tool(
        name="generate_blog_figure",
        description=(
            "Genera una figura interior para un artículo de blog (4:3, composición centrada, sin "
            "espacio para texto). Úsala para secciones que necesitan una imagen de apoyo."
        ),
        annotations=GENERATES,
        output_schema=None,
    )
    def generate_blog_figure(
        concept: Annotated[str, Field(description="Concepto o sección que la figura debe ilustrar.")],
        style: Annotated[StyleName, Field(description="Preset visual.")] = "flat-vector",
        palette: Annotated[
            PaletteName,
            Field(description="Paleta de color. Default natural: foto neutra sin filtro."),
        ] = "natural",
        n: Annotated[int, Field(ge=1, le=6, description="Cantidad de variantes.")] = 1,
        mood: Annotated[str | None, Field(description="Tono emocional.")] = None,
        strict_palette: Annotated[bool, Field(description="Forzar colores de marca.")] = True,
        allow_text: Annotated[bool, Field(description="Permitir texto dentro de la imagen.")] = False,
        output: Annotated[
            OutputSpec | None,
            Field(description="Tamaño exacto (px), formato de salida y publicación en el media server."),
        ] = None,
        model: Annotated[

            str | None,

            Field(description="Modelo de OpenRouter para esta llamada. Usa google/gemini-3.1-flash-image cuando la imagen deba llevar texto legible en español. Default: el configurado en el servidor."),

        ] = None,

    ) -> list[Any]:
        try:
            resolved_style = resolve_style(style)
            resolved_palette = resolve_palette(palette)
            media_format = resolve_format("blog-inline")
            output_spec, aspect = _resolve_output(output, default_aspect=media_format.aspect_ratio)
            final_prompt = prompts.compose_blog_figure(
                concept=concept,
                style=resolved_style,
                palette=resolved_palette,
                strict_palette=strict_palette,
                allow_text=allow_text,
                mood=mood,
            )
            result = _generate(
                final_prompt,
                aspect_ratio=aspect,
                n=n,
                model=model,
                palette=resolved_palette,
            )
        except (ValueError, ImageGenerationError) as exc:
            raise _fail(exc) from exc

        return _deliver(
            result,
            prompt=final_prompt,
            slug=f"blog-figura-{concept}",
            output=output_spec,
            meta={
                "kind": "blog-figure",
                "concept": concept,
                "format": media_format.id,
                "style": resolved_style.id,
                "palette": resolved_palette.id,
                "alt_text_hint": prompts.suggest_alt_text(
                    subject=concept,
                    style=resolved_style,
                    palette=resolved_palette,
                    purpose="una figura del artículo",
                ),
            },
        )

    @mcp.tool(
        name="generate_pitch_slide_visual",
        description=(
            "Genera el visual de una slide de pitch deck (16:9) según el arquetipo de la slide "
            "(title, problem, solution, product, market, traction, competition, team, roadmap, "
            "business-model, ask, quote). Respeta el espacio reservado para el texto de la slide."
        ),
        annotations=GENERATES,
        output_schema=None,
    )
    def generate_pitch_slide_visual(
        title: Annotated[str, Field(description="Título de la slide.")],
        slide_type: Annotated[SlideTypeName, Field(description="Arquetipo narrativo de la slide.")] = DEFAULT_SLIDE_TYPE,
        key_message: Annotated[
            str | None,
            Field(description="La idea que la slide debe comunicar; se convierte en metáfora visual."),
        ] = None,
        style: Annotated[StyleName, Field(description="Preset visual.")] = "glass-ui",
        palette: Annotated[PaletteName, Field(description="Paleta de marca.")] = DEFAULT_PALETTE,
        text_space: Annotated[
            TextSpace | None,
            Field(description="Zona reservada para el texto; si falta se usa la del arquetipo."),
        ] = None,
        n: Annotated[int, Field(ge=1, le=6, description="Cantidad de variantes.")] = 1,
        strict_palette: Annotated[bool, Field(description="Forzar colores de marca.")] = True,
        allow_text: Annotated[bool, Field(description="Permitir texto dentro de la imagen.")] = False,
        output: Annotated[
            OutputSpec | None,
            Field(description="Tamaño exacto (px), formato de salida y publicación en el media server."),
        ] = None,
        model: Annotated[

            str | None,

            Field(description="Modelo de OpenRouter para esta llamada. Usa google/gemini-3.1-flash-image cuando la imagen deba llevar texto legible en español. Default: el configurado en el servidor."),

        ] = None,

    ) -> list[Any]:
        try:
            resolved_slide = resolve_slide_type(slide_type)
            resolved_style = resolve_style(style)
            resolved_palette = resolve_palette(palette)
            media_format = resolve_format("slide")
            output_spec, aspect = _resolve_output(output, default_aspect=media_format.aspect_ratio)
            final_prompt = prompts.compose_slide_visual(
                slide=resolved_slide,
                title=title,
                key_message=key_message,
                style=resolved_style,
                palette=resolved_palette,
                text_space=text_space,
                strict_palette=strict_palette,
                allow_text=allow_text,
            )
            result = _generate(
                final_prompt,
                aspect_ratio=aspect,
                n=n,
                model=model,
                palette=resolved_palette,
            )
        except (ValueError, ImageGenerationError) as exc:
            raise _fail(exc) from exc

        reserved = text_space or resolved_slide.default_text_space
        return _deliver(
            result,
            prompt=final_prompt,
            slug=f"slide-{resolved_slide.id}-{title}",
            output=output_spec,
            meta={
                "kind": "pitch-slide",
                "slide_type": resolved_slide.id,
                "title": title,
                "format": media_format.id,
                "style": resolved_style.id,
                "palette": resolved_palette.id,
                "text_space": reserved,
                "layout_advice": (
                    f"Coloca el texto en la zona '{reserved}' de la slide; "
                    "usa Space Grotesk en títulos y Inter en el cuerpo."
                ),
                "alt_text_hint": prompts.suggest_alt_text(
                    subject=key_message or title,
                    style=resolved_style,
                    palette=resolved_palette,
                    purpose=f"la slide «{title}»",
                ),
            },
        )

    @mcp.tool(
        name="generate_deck_background",
        description=(
            "Genera un fondo abstracto de baja intensidad para slides (16:9), pensado para llevar "
            "texto encima. Theme dark usa #1C1C1C, theme light usa #F5F5F5."
        ),
        annotations=GENERATES,
        output_schema=None,
    )
    def generate_deck_background(
        theme: Annotated[Literal["dark", "light"], Field(description="Fondo oscuro o claro.")] = "dark",
        intensity: Annotated[
            Literal["subtle", "medium", "bold"],
            Field(description="Cuánto protagonismo tiene el fondo. Default subtle."),
        ] = "subtle",
        style: Annotated[StyleName, Field(description="Preset visual.")] = "quiet-surface",
        palette: Annotated[PaletteName, Field(description="Paleta de marca.")] = "brand-dark",
        n: Annotated[int, Field(ge=1, le=6, description="Cantidad de variantes.")] = 1,
        strict_palette: Annotated[bool, Field(description="Forzar colores de marca.")] = True,
        output: Annotated[
            OutputSpec | None,
            Field(description="Tamaño exacto (px), formato de salida y publicación en el media server."),
        ] = None,
        model: Annotated[

            str | None,

            Field(description="Modelo de OpenRouter para esta llamada. Usa google/gemini-3.1-flash-image cuando la imagen deba llevar texto legible en español. Default: el configurado en el servidor."),

        ] = None,

    ) -> list[Any]:
        try:
            resolved_style = resolve_style(style)
            resolved_palette = resolve_palette(palette)
            media_format = resolve_format("slide")
            output_spec, aspect = _resolve_output(output, default_aspect=media_format.aspect_ratio)
            final_prompt = prompts.compose_background(
                theme=theme,
                style=resolved_style,
                palette=resolved_palette,
                intensity=intensity,
                strict_palette=strict_palette,
            )
            result = _generate(
                final_prompt,
                aspect_ratio=aspect,
                n=n,
                model=model,
                palette=resolved_palette,
            )
        except (ValueError, ImageGenerationError) as exc:
            raise _fail(exc) from exc

        return _deliver(
            result,
            prompt=final_prompt,
            slug=f"deck-fondo-{theme}",
            output=output_spec,
            meta={
                "kind": "deck-background",
                "theme": theme,
                "intensity": intensity,
                "format": media_format.id,
                "style": resolved_style.id,
                "palette": resolved_palette.id,
                "alt_text_hint": f"Fondo abstracto {theme} para slides de Meik Labs.",
            },
        )

    @mcp.tool(
        name="list_generated_images",
        description=(
            "Lista las imágenes generadas previamente cuando el servidor corre en local con "
            "almacenamiento habilitado (asset_id, archivo, prompt, estilo, fecha)."
        ),
        annotations=READ_ONLY,
        output_schema=None,
    )
    def list_generated_images(
        limit: Annotated[int, Field(ge=1, le=100, description="Cantidad máxima de resultados.")] = 20,
        query: Annotated[str | None, Field(description="Filtro por texto en nombre o metadatos.")] = None,
    ) -> str:
        store = _store()
        payload = {
            "storage_enabled": store.enabled,
            "root": str(store.root) if store.root else None,
            "assets": store.list_assets(limit=limit, query=query),
        }
        if not store.enabled:
            payload["note"] = "El almacenamiento local está deshabilitado en este entorno."
        return json.dumps(payload, ensure_ascii=False, indent=2)

    @mcp.tool(
        name="show_saved_image",
        description=(
            "Devuelve inline una imagen ya generada, por asset_id o nombre de archivo. Disponible "
            "sólo cuando el servidor corre en local con almacenamiento habilitado."
        ),
        annotations=READ_ONLY,
        output_schema=None,
    )
    def show_saved_image(
        asset_id: Annotated[str, Field(description="asset_id (stem del archivo) o nombre de archivo.")],
    ) -> list[Any]:
        store = _store()
        loaded = store.load(asset_id)
        if loaded is None:
            raise ToolError(
                f"No encontré el asset '{asset_id}' en el almacenamiento local"
                f" ({store.root or 'deshabilitado'})."
            )
        data, media, sidecar = loaded
        payload = fit_inline(data, media, load_settings().inline_max_chars)
        manifest = {
            "status": "ok",
            "asset_id": sidecar.get("asset_id", asset_id),
            "media_type": payload.media_type,
            "width": payload.width,
            "height": payload.height,
            "downscaled_for_client": payload.downscaled,
            "prompt": sidecar.get("prompt"),
            "style": sidecar.get("style"),
            "palette": sidecar.get("palette"),
            "created_at": sidecar.get("created_at"),
        }
        return [
            Image(data=payload.data, format=extension_for(payload.media_type)),
            json.dumps(manifest, ensure_ascii=False, indent=2),
        ]

    @mcp.tool(
        name="size_presets",
        description=(
            "Lista los tamaños paramétricos por destino (LinkedIn 1200x627, portada de empresa "
            "1584x396, blog-hero 1600x900, blog-diagram 1600x1131, OG 1200x630, story 1080x1920, "
            "slide 1920x1080, etc.) con su proporción, propósito y peso recomendado. "
            "Úsalo para elegir el valor de output.size."
        ),
        annotations=READ_ONLY,
        output_schema=None,
    )
    def size_presets() -> str:
        return json.dumps(
            {
                "sizes": size_catalog(),
                "uso": "Pasa el id en output.size; puedes sobrescribir width/height/fit/max_kb.",
            },
            ensure_ascii=False,
            indent=2,
        )

    @mcp.tool(
        name="blog_style_guide",
        description=(
            "Devuelve el estilo editorial del blog de Meik Labs capturado como sistema de prompts: "
            "tono relajado, irónico y absurdo, los tres registros (foto deadpan, diagrama dibujado a "
            "mano, mascota 3D), reglas, recetas de prompt y política de texto en imagen. "
            "Consúltalo antes de escribir un prompt de blog."
        ),
        annotations=READ_ONLY,
        output_schema=None,
    )
    def blog_style_guide() -> str:
        return json.dumps(build_blog_style_guide(), ensure_ascii=False, indent=2)

    @mcp.tool(
        name="search_stock_photos",
        description=(
            "Busca fotografías reales en Unsplash (oficinas, industria, equipo, producto) cuando una "
            "foto auténtica comunica mejor que una ilustración. Devuelve ids, descripción, autor y "
            "atribución lista para usar. Requiere UNSPLASH_ACCESS_KEY. No sirve para el registro "
            "satírico del blog: eso se genera con los estilos blog-*."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True),
        output_schema=None,
    )
    def search_stock_photos(
        query: Annotated[str, Field(description="Qué buscar, en inglés suele dar mejores resultados.")],
        orientation: Annotated[
            Literal["landscape", "portrait", "squarish"] | None,
            Field(description="Orientación preferida de la foto."),
        ] = "landscape",
        count: Annotated[int, Field(ge=1, le=30, description="Cuántos resultados.")] = 6,
        color: Annotated[
            Literal["black_and_white", "black", "white", "yellow", "orange", "red", "purple", "magenta", "green", "teal", "blue"] | None,
            Field(description="Filtro de color dominante."),
        ] = None,
    ) -> str:
        client = client_from_settings()
        if not client.configured:
            raise ToolError(
                "Unsplash no está configurado. Añade UNSPLASH_ACCESS_KEY al entorno "
                "(https://unsplash.com/oauth/applications → Access Key)."
            )
        try:
            photos = client.search(query, orientation=orientation, count=count, color=color)
        except StockError as exc:
            raise ToolError(str(exc)) from exc
        return json.dumps(
            {
                "query": query,
                "count": len(photos),
                "photos": [
                    {
                        "id": photo.id,
                        "description": photo.description,
                        "dimensions": f"{photo.width}x{photo.height}",
                        "color": photo.color,
                        "attribution": photo.attribution,
                        "preview_url": photo.urls.get("small"),
                    }
                    for photo in photos
                ],
                "siguiente_paso": "Elige un id y llama publish_stock_photo con el tamaño destino.",
            },
            ensure_ascii=False,
            indent=2,
        )

    @mcp.tool(
        name="publish_stock_photo",
        description=(
            "Descarga una foto de Unsplash por id, la recorta al tamaño pedido, la optimiza, la "
            "publica en el media server y devuelve la URL pública junto con la atribución "
            "obligatoria (autor + enlace)."
        ),
        annotations=GENERATES,
        output_schema=None,
    )
    def publish_stock_photo(
        photo_id: Annotated[str, Field(description="Id de Unsplash obtenido con search_stock_photos.")],
        output: Annotated[
            OutputSpec | None,
            Field(description="Tamaño destino (size), formato, peso y publicación."),
        ] = None,
    ) -> list[Any]:
        client = client_from_settings()
        if not client.configured:
            raise ToolError(
                "Unsplash no está configurado. Añade UNSPLASH_ACCESS_KEY al entorno."
            )
        try:
            photo = client.get_photo(photo_id)
            data = client.fetch(photo, size="full" if photo.urls.get("full") else "regular")
        except StockError as exc:
            raise ToolError(str(exc)) from exc

        spec, _ = _resolve_output(output, default_aspect="16:9")
        result = GenerationResult(
            images=(GeneratedImage(data=data, media_type="image/jpeg"),),
            model="unsplash",
            aspect_ratio="auto",
            cost_usd=0.0,
            duration_seconds=0.0,
        )
        meta: dict[str, Any] = {
            "kind": "stock-photo",
            "source": "unsplash",
            "photo_id": photo.id,
            "description": photo.description,
            "attribution": photo.attribution,
            "style": "editorial-photo",
            "palette": "none",
            "alt_text_hint": f"Foto: {photo.description or 'imagen de archivo'} ({photo.photographer} / Unsplash).",
        }
        return _deliver(
            result,
            prompt=f"Unsplash photo {photo.id}: {photo.description or ''}".strip(),
            slug=f"stock-{photo.id}",
            output=spec,
            meta=meta,
        )

    @mcp.tool(
        name="publish_asset",
        description=(
            "Optimiza y publica en el media server (cPanel) una imagen ya generada, por asset_id. "
            "Útil para reintentar una subida fallida o publicar en otro tamaño/formato."
        ),
        annotations=GENERATES,
        output_schema=None,
    )
    def publish_asset(
        asset_id: Annotated[str, Field(description="asset_id de list_generated_images.")],
        output: Annotated[
            OutputSpec | None,
            Field(description="Tamaño y formato antes de subir. La publicación se fuerza aunque publish=false."),
        ] = None,
    ) -> list[Any]:
        store = _store()
        loaded = store.load(asset_id)
        if loaded is None:
            raise ToolError(f"No encontré el asset '{asset_id}' en el almacenamiento local.")

        data, media, sidecar = loaded
        spec, _ = _resolve_output(output, default_aspect="1:1")
        settings = load_settings()
        try:
            processed = optimize_image(
                data,
                media,
                output_format=normalize_format(spec.format, settings.output_format),
                quality=spec.quality,
                width=spec.width,
                height=spec.height,
                fit=spec.fit,
                max_kb=spec.max_kb,
            )
        except ValueError as exc:
            raise ToolError(str(exc)) from exc

        publisher = publisher_from_settings()
        filename = (
            f"{slugify(spec.filename, max_words=12)}.{extension_of(processed)}"
            if spec.filename
            else f"{sidecar.get('asset_id', asset_id)}-{processed.width}x{processed.height}.{extension_of(processed)}"
        )
        published = publisher.publish(processed.data, filename)

        payload = fit_inline(processed.data, processed.media_type, settings.inline_max_chars)
        manifest = {
            "status": "ok",
            "asset_id": sidecar.get("asset_id", asset_id),
            "public_url": published.url,
            "remote_path": published.remote_path,
            "published_via": published.transport,
            "format": processed.fmt,
            "bytes": processed.size_bytes,
            "width": processed.width,
            "height": processed.height,
            "optimization": list(processed.steps),
            "prompt": sidecar.get("prompt"),
        }
        return [
            Image(data=payload.data, format=extension_for(payload.media_type)),
            json.dumps(manifest, ensure_ascii=False, indent=2),
        ]

    @mcp.tool(
        name="media_server_status",
        description=(
            "Diagnostica la conexión al media server (SFTP/FTP) y muestra el modo, host, carpeta "
            "remota y URL base configurados. Úsalo cuando una publicación falle."
        ),
        annotations=READ_ONLY,
        output_schema=None,
    )
    def media_server_status() -> str:
        settings = load_settings()
        publisher = MediaPublisher(settings.media)
        status = publisher.status()
        payload: dict[str, Any] = {
            "configured": status.configured,
            "ok": status.ok,
            "mode": status.mode,
            "detail": status.detail,
            "host": status.host or settings.media.cpanel_host,
            "remote_dir": status.remote_dir,
            "base_url": status.base_url,
            "transport": status.transport,
            "subdir_by_date": settings.media.subdir_by_date,
            "naming": settings.media.naming,
            "public_url_pattern": (
                f"{settings.media.base_url.rstrip('/')}/"
                + ("<YYYY-MM-DD>/" if settings.media.subdir_by_date else "")
                + "<nombre>.<ext>"
                if settings.media.base_url
                else None
            ),
            "output_default_format": settings.output_format,
        }
        if status.extra:
            payload["extra"] = status.extra
        if not status.configured:
            payload["missing"] = settings.media.missing
            payload["how_to_configure"] = (
                "Faltan variables de entorno: "
                + ", ".join(settings.media.missing)
                + ". En local van en .env; en Horizon/remoto, en los secretos del servidor."
            )
        return json.dumps(payload, ensure_ascii=False, indent=2)


__all__ = ["register_tools", "GeneratedImage", "GenerationResult"]
