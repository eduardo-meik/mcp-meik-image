"""MCP tools exposed to Claude / any MCP client."""

from __future__ import annotations

import json
import logging
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.utilities.types import Image
from mcp.types import ToolAnnotations
from pydantic import Field

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
from .imaging import extension_for, fit_inline
from .openrouter import GeneratedImage, GenerationResult, ImageGenerationError, OpenRouterImageClient
from .storage import AssetStore

logger = logging.getLogger("meik_image.tools")

PaletteName = Literal[tuple(sorted(PALETTES))]  # type: ignore[valid-type]
StyleName = Literal[tuple(sorted(STYLES))]  # type: ignore[valid-type]
FormatName = Literal[tuple(sorted(FORMATS))]  # type: ignore[valid-type]
SlideTypeName = Literal[tuple(sorted(SLIDE_TYPES))]  # type: ignore[valid-type]
TextSpace = Literal[tuple(sorted(TEXT_SPACES))]  # type: ignore[valid-type]

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
GENERATES = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)


def _store() -> AssetStore:
    return AssetStore(load_settings().image_dir)


def _generate(prompt: str, *, aspect_ratio: str, n: int, palette: Palette) -> GenerationResult:
    settings = load_settings()
    client = OpenRouterImageClient(settings)
    colors = palette.colors if palette.id != "none" else None
    return client.generate(prompt, aspect_ratio=aspect_ratio, n=n, palette_colors=colors)


def _deliver(
    result: GenerationResult,
    *,
    prompt: str,
    slug: str,
    meta: dict[str, Any],
) -> list[Any]:
    """Save full-resolution renders, then return inline images plus a JSON manifest."""
    settings = load_settings()
    store = _store()
    content: list[Any] = []
    images_meta: list[dict[str, Any]] = []

    for index, generated in enumerate(result.images, start=1):
        entry: dict[str, Any] = {"index": index}
        asset = store.save(
            generated.data,
            generated.media_type,
            slug=slug,
            metadata={
                "prompt": prompt,
                "model": result.model,
                "aspect_ratio": result.aspect_ratio,
                **meta,
            },
        )
        if asset is not None:
            entry["asset_id"] = asset.asset_id
            entry["saved_to"] = str(asset.path)
            entry["bytes"] = asset.bytes_written

        payload = fit_inline(generated.data, generated.media_type, settings.inline_max_chars)
        entry["inline"] = {
            "media_type": payload.media_type,
            "width": payload.width,
            "height": payload.height,
            "base64_chars": payload.base64_chars,
            "downscaled_for_client": payload.downscaled,
        }
        images_meta.append(entry)
        content.append(Image(data=payload.data, format=extension_for(payload.media_type)))

    manifest = {
        "status": "ok",
        "model": result.model,
        "aspect_ratio": result.aspect_ratio,
        "count": len(result.images),
        "cost_usd": result.cost_usd,
        "duration_seconds": result.duration_seconds,
        "prompt": prompt,
        **meta,
        "images": images_meta,
        "storage": {
            "enabled": store.enabled,
            "root": str(store.root) if store.root else None,
        },
    }
    if not store.enabled:
        manifest["note"] = (
            "Almacenamiento local deshabilitado (entorno remoto): usa la imagen inline de esta "
            "respuesta, no hay archivo persistente en el servidor."
        )
    elif any(entry["inline"]["downscaled_for_client"] for entry in images_meta):
        manifest["note"] = (
            "La imagen inline se redujo para caber en el límite del cliente; "
            "el archivo a resolución completa está en saved_to."
        )

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
    ) -> list[Any]:
        try:
            resolved_style = resolve_style(style)
            resolved_palette = resolve_palette(palette)
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
                aspect_ratio=aspect_ratio,
                n=n,
                palette=resolved_palette,
            )
        except (ValueError, ImageGenerationError) as exc:
            raise _fail(exc) from exc

        file_slug = slug or prompts.compose_filename_slug(prompt)
        return _deliver(
            result,
            prompt=final_prompt,
            slug=file_slug,
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
        palette: Annotated[PaletteName, Field(description="Paleta de marca.")] = DEFAULT_PALETTE,
        text_space: Annotated[
            TextSpace,
            Field(description="Lado donde se reserva el espacio para el titular."),
        ] = "left",
        n: Annotated[int, Field(ge=1, le=6, description="Cantidad de variantes.")] = 1,
        mood: Annotated[str | None, Field(description="Tono emocional de la marca.")] = None,
        strict_palette: Annotated[bool, Field(description="Forzar colores de marca en el proveedor.")] = True,
        allow_text: Annotated[bool, Field(description="Permitir texto dentro de la imagen.")] = False,
    ) -> list[Any]:
        try:
            resolved_style = resolve_style(style)
            resolved_palette = resolve_palette(palette)
            media_format = resolve_format("blog-hero")
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
                aspect_ratio=media_format.aspect_ratio,
                n=n,
                palette=resolved_palette,
            )
        except (ValueError, ImageGenerationError) as exc:
            raise _fail(exc) from exc

        return _deliver(
            result,
            prompt=final_prompt,
            slug=f"blog-hero-{title}",
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
        palette: Annotated[PaletteName, Field(description="Paleta de marca.")] = "brand-light",
        n: Annotated[int, Field(ge=1, le=6, description="Cantidad de variantes.")] = 1,
        mood: Annotated[str | None, Field(description="Tono emocional.")] = None,
        strict_palette: Annotated[bool, Field(description="Forzar colores de marca.")] = True,
        allow_text: Annotated[bool, Field(description="Permitir texto dentro de la imagen.")] = False,
    ) -> list[Any]:
        try:
            resolved_style = resolve_style(style)
            resolved_palette = resolve_palette(palette)
            media_format = resolve_format("blog-inline")
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
                aspect_ratio=media_format.aspect_ratio,
                n=n,
                palette=resolved_palette,
            )
        except (ValueError, ImageGenerationError) as exc:
            raise _fail(exc) from exc

        return _deliver(
            result,
            prompt=final_prompt,
            slug=f"blog-figura-{concept}",
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
    ) -> list[Any]:
        try:
            resolved_slide = resolve_slide_type(slide_type)
            resolved_style = resolve_style(style)
            resolved_palette = resolve_palette(palette)
            media_format = resolve_format("slide")
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
                aspect_ratio=media_format.aspect_ratio,
                n=n,
                palette=resolved_palette,
            )
        except (ValueError, ImageGenerationError) as exc:
            raise _fail(exc) from exc

        reserved = text_space or resolved_slide.default_text_space
        return _deliver(
            result,
            prompt=final_prompt,
            slug=f"slide-{resolved_slide.id}-{title}",
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
    ) -> list[Any]:
        try:
            resolved_style = resolve_style(style)
            resolved_palette = resolve_palette(palette)
            media_format = resolve_format("slide")
            final_prompt = prompts.compose_background(
                theme=theme,
                style=resolved_style,
                palette=resolved_palette,
                intensity=intensity,
                strict_palette=strict_palette,
            )
            result = _generate(
                final_prompt,
                aspect_ratio=media_format.aspect_ratio,
                n=n,
                palette=resolved_palette,
            )
        except (ValueError, ImageGenerationError) as exc:
            raise _fail(exc) from exc

        return _deliver(
            result,
            prompt=final_prompt,
            slug=f"deck-fondo-{theme}",
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


__all__ = ["register_tools", "GeneratedImage", "GenerationResult"]
