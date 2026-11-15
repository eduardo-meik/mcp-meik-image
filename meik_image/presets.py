"""Parametric size presets: the sizes each channel actually needs.

Recraft only accepts aspect ratios, so every preset carries the closest ratio the
model supports plus the exact pixel target and fit mode used on delivery.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SizePreset:
    id: str
    name: str
    width: int
    height: int
    model_ratio: str
    fit: str
    purpose: str
    max_kb: int | None = None
    default_style: str | None = None

    @property
    def ratio(self) -> float:
        return self.width / self.height

    @property
    def label(self) -> str:
        return f"{self.width}x{self.height}"

    @property
    def needs_upscale(self) -> bool:
        """True when the preset asks for more pixels than the model can generate."""
        native_w = NATIVE_SIZE.get(self.model_ratio, (1344, 768))[0]
        return self.width > native_w


SIZES: dict[str, SizePreset] = {
    # --- LinkedIn -------------------------------------------------------
    "linkedin-post": SizePreset(
        "linkedin-post", "LinkedIn · post con imagen", 1200, 627, "16:9", "cover",
        "Imagen de post (1.91:1). El formato que más se muestra en el feed.",
        max_kb=200, default_style="blog-satire",
    ),
    "linkedin-link": SizePreset(
        "linkedin-link", "LinkedIn · post con enlace", 1200, 627, "16:9", "cover",
        "Tarjeta de enlace compartido (1.91:1).",
        max_kb=200, default_style="blog-satire",
    ),
    "linkedin-square": SizePreset(
        "linkedin-square", "LinkedIn · cuadrado", 1024, 1024, "1:1", "cover",
        "Post cuadrado, carrusel y documentos.",
        max_kb=220,
    ),
    "linkedin-portrait": SizePreset(
        "linkedin-portrait", "LinkedIn · vertical 4:5", 896, 1120, "3:4", "cover",
        "Carruseles verticales y posts que ocupan más alto en mobile.",
        max_kb=220,
    ),
    "linkedin-company-cover": SizePreset(
        "linkedin-company-cover", "LinkedIn · portada de empresa", 1344, 336, "16:9", "cover",
        "Banner de página (4:1). Se recorta bastante: deja el motivo al centro.",
        max_kb=150,
    ),
    "linkedin-personal-banner": SizePreset(
        "linkedin-personal-banner", "LinkedIn · banner personal", 1344, 336, "16:9", "cover",
        "Fondo de perfil (4:1).",
        max_kb=150,
    ),
    # --- Blog -----------------------------------------------------------
    "blog-hero": SizePreset(
        "blog-hero", "Blog · cabecera 16:9", 1344, 768, "16:9", "cover",
        "Hero de artículo y OG image.",
        max_kb=250, default_style="blog-satire",
    ),
    "blog-inline": SizePreset(
        "blog-inline", "Blog · figura 4:3", 1216, 896, "4:3", "cover",
        "Figura dentro del artículo.",
        max_kb=220, default_style="blog-satire",
    ),
    "blog-diagram": SizePreset(
        "blog-diagram", "Blog · diagrama A4 apaisado", 1216, 860, "4:3", "cover",
        "Diagrama explicativo con anotaciones (√2).",
        max_kb=350, default_style="blog-diagram",
    ),
    "blog-wide": SizePreset(
        "blog-wide", "Blog · panorámica 2:1", 1344, 672, "16:9", "cover",
        "Cabecera ancha tipo editorial (2:1).",
        max_kb=300, default_style="blog-satire",
    ),
    "og-image": SizePreset(
        "og-image", "Open Graph", 1200, 630, "16:9", "cover",
        "Preview al compartir en redes y apps de mensajería.",
        max_kb=200,
    ),
    "email-header": SizePreset(
        "email-header", "Email · cabecera", 1200, 400, "16:9", "cover",
        "Banda de cabecera para newsletters (3:1).",
        max_kb=150,
    ),
    # --- Otras redes ----------------------------------------------------
    "x-post": SizePreset(
        "x-post", "X / Twitter · imagen", 1344, 768, "16:9", "cover",
        "Imagen de post (16:9).", max_kb=250,
    ),
    "x-card": SizePreset(
        "x-card", "X / Twitter · summary card", 1200, 675, "16:9", "cover",
        "Tarjeta de enlace.", max_kb=200,
    ),
    "instagram-square": SizePreset(
        "instagram-square", "Instagram · cuadrado", 1024, 1024, "1:1", "cover",
        "Post de feed.", max_kb=220,
    ),
    "instagram-story": SizePreset(
        "instagram-story", "Instagram · story / reel", 768, 1344, "9:16", "cover",
        "Story o portada de reel.", max_kb=250,
    ),
    "youtube-thumb": SizePreset(
        "youtube-thumb", "YouTube · miniatura", 1280, 720, "16:9", "cover",
        "Miniatura de video.", max_kb=180,
    ),
    # --- Presentaciones --------------------------------------------------
    "slide": SizePreset(
        "slide", "Slide 16:9 (FHD)", 1920, 1080, "16:9", "cover",
        "Slide de deck en pantalla completa.", max_kb=400, default_style="quiet-surface",
    ),
    "pptx": SizePreset(
        "pptx", "PowerPoint / Keynote 16:9", 1344, 756, "16:9", "cover",
        "Proporción de plantilla estándar de PowerPoint.",
        max_kb=400,
    ),
    "slide-4k": SizePreset(
        "slide-4k", "Slide 16:9 (4K)", 3840, 2160, "16:9", "cover",
        "Deck 4K. Ojo: el modelo no genera a 4K, se interpola desde ~1344 px.",
        max_kb=900,
    ),
    # --- Genéricos -------------------------------------------------------
    "square": SizePreset(
        "square", "Cuadrado 1:1", 1200, 1200, "1:1", "cover", "Uso genérico.", max_kb=220,
    ),
    "wide": SizePreset(
        "wide", "Panorámica 16:9", 1920, 1080, "16:9", "cover", "Uso genérico.", max_kb=300,
    ),
}

# Salida nativa real de Recraft V4.1 Flash V2 por proporción (lado largo 1344 px).
NATIVE_SIZE: dict[str, tuple[int, int]] = {
    "16:9": (1344, 768),
    "4:3": (1216, 896),
    "1:1": (1024, 1024),
    "3:4": (896, 1216),
    "9:16": (768, 1344),
    "auto": (1344, 768),
}

DEFAULT_SIZE = "blog-hero"


def resolve_size(size: str | None) -> SizePreset | None:
    if not size:
        return None
    key = size.strip().lower()
    if key in {"none", "auto", "libre"}:
        return None
    if key in SIZES:
        return SIZES[key]
    valid = ", ".join(SIZES)
    raise ValueError(f"Tamaño desconocido: {size!r}. Usa uno de: {valid}.")


def catalog() -> dict[str, dict[str, object]]:
    """Compact description used by the tools that expose the preset list."""
    return {
        key: {
            "name": preset.name,
            "width": preset.width,
            "height": preset.height,
            "ratio": round(preset.ratio, 3),
            "model_ratio": preset.model_ratio,
            "purpose": preset.purpose,
            "max_kb": preset.max_kb,
            "default_style": preset.default_style,
            "needs_upscale": preset.needs_upscale,
        }
        for key, preset in SIZES.items()
    }
