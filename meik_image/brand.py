"""Meik Labs brand kit: palettes, visual styles, formats and slide archetypes.

Values mirror the production website tokens (meiklabs_website/src/styles/brand-tokens.css):
primary #4F00C4, secondary #FF5CF3, neutral-dark #1C1C1C, neutral-light #F5F5F5,
display font Space Grotesk, body font Inter.
"""

from __future__ import annotations

from dataclasses import dataclass, field

BRAND_NAME = "Meik Labs"
BRAND_TAGLINE = "AI, datos y automatización para empresas que quieren escalar"
BRAND_FONTS = ("Space Grotesk (display)", "Inter (body)", "JetBrains Mono (code/UI)")

RGB = tuple[int, int, int]

BRAND_VIOLET: RGB = (79, 0, 196)
BRAND_MAGENTA: RGB = (255, 92, 243)
BRAND_INK: RGB = (28, 28, 28)
BRAND_PAPER: RGB = (245, 245, 245)


@dataclass(frozen=True)
class Palette:
    id: str
    name: str
    description: str
    prompt: str
    colors: tuple[RGB, ...] = ()
    for_light_background: bool = False


PALETTES: dict[str, Palette] = {
    "brand-dark": Palette(
        id="brand-dark",
        name="Meik brand dark",
        description="Violeta #4F00C4 → magenta #FF5CF3 sobre fondo casi negro. El look por defecto de la marca.",
        prompt=(
            "palette strictly limited to deep violet #4F00C4, vivid magenta #FF5CF3, "
            "pale lilac highlights and near-black #1C1C1C background, rich dark contrast, glowing gradients"
        ),
        colors=(BRAND_VIOLET, BRAND_MAGENTA, BRAND_INK),
    ),
    "brand-light": Palette(
        id="brand-light",
        name="Meik brand light",
        description="Violeta y magenta sobre off-white #F5F5F5, para blogs con fondo claro y decks corporativos.",
        prompt=(
            "palette strictly limited to deep violet #4F00C4, vivid magenta #FF5CF3 and soft lilac tints "
            "on a clean off-white #F5F5F5 background, airy light editorial mood, crisp edges"
        ),
        colors=(BRAND_VIOLET, BRAND_MAGENTA, BRAND_PAPER),
        for_light_background=True,
    ),
    "brand-mono": Palette(
        id="brand-mono",
        name="Brand monochrome",
        description="Violeta sobre negro con acentos mínimos; máxima sobriedad para slides densos.",
        prompt=(
            "monochrome violet #4F00C4 palette with a single magenta #FF5CF3 accent, "
            "near-black #1C1C1C background, high contrast, minimal, sophisticated"
        ),
        colors=(BRAND_VIOLET, BRAND_MAGENTA, BRAND_INK),
    ),
    "neutral": Palette(
        id="neutral",
        name="Neutral editorial",
        description="Grises, blanco y un acento violeta; cuando la imagen no debe competir con la marca.",
        prompt=(
            "restrained neutral palette of graphite greys, off-white and bone, with one small violet #4F00C4 accent, "
            "editorial and calm"
        ),
        colors=(BRAND_VIOLET, BRAND_INK, BRAND_PAPER),
        for_light_background=True,
    ),
    "natural": Palette(
        id="natural",
        name="Natural (foto real)",
        description=(
            "Grado fotográfico neutro: luz de día, blancos reales, piel real. Sin filtro de color ni "
            "acentos de marca. Es la paleta por defecto del blog."
        ),
        prompt=(
            "natural photographic colour, balanced daylight white balance, honest whites and true skin tones, "
            "no colour cast, no coloured gels or lighting, no magenta or violet tint, no gradient overlay, "
            "no vignette"
        ),
        colors=(),
        for_light_background=True,
    ),
    "warm": Palette(
        id="warm",
        name="Warm accent",
        description="Ámbar y coral con base oscura; para casos de éxito, personas y storytelling.",
        prompt=(
            "warm palette of amber, coral and soft sand tones anchored by a deep violet #4F00C4 shadow, "
            "cinematic warmth, dark base"
        ),
        colors=(BRAND_VIOLET, (255, 138, 76), BRAND_INK),
    ),
    "cool": Palette(
        id="cool",
        name="Cool data",
        description="Azules y violetas fríos, tipo dato/infraestructura.",
        prompt=(
            "cool palette of electric blues, cyan and violet #4F00C4 on a near-black #1C1C1C base, "
            "technical and precise, subtle magenta #FF5CF3 spark"
        ),
        colors=(BRAND_VIOLET, (56, 132, 255), BRAND_INK),
    ),
    "none": Palette(
        id="none",
        name="Free palette",
        description="Sin restricción de paleta: el modelo elige los colores según el tema.",
        prompt="",
    ),
}

DEFAULT_PALETTE = "brand-dark"

# Alias heredado: antes esta paleta inyectaba violeta por controls.colors y teñía
# las fotos. Ahora apunta a la paleta natural, sin filtro de color.
PALETTES["editorial-natural"] = PALETTES["natural"]


@dataclass(frozen=True)
class StylePreset:
    id: str
    name: str
    description: str
    prompt: str
    best_for: tuple[str, ...] = ()
    alt_hint: str = ""


STYLES: dict[str, StylePreset] = {
    "abstract-geometric": StylePreset(
        id="abstract-geometric",
        name="Abstract geometric 3D",
        description="Formas 3D suaves, gradientes y volúmenes limpios. El estilo insignia para hero de blog.",
        prompt=(
            "abstract 3D geometric composition with smooth rounded volumes, matte and glossy surfaces, "
            "soft studio lighting, subtle grain, generous negative space, premium tech editorial aesthetic"
        ),
        best_for=("blog hero", "slide cover"),
        alt_hint="Composición geométrica abstracta en 3D",
    ),
    "quiet-surface": StylePreset(
        id="quiet-surface",
        name="Quiet surface",
        description="Superficie casi plana con un solo resplandor suave; el fondo correcto para slides con texto.",
        prompt=(
            "flat matte surface, one very soft radial glow confined to a single corner, no visible objects, "
            "no bloom, no flare, no texture noise, near-uniform tonal field, quiet and cinematic"
        ),
        best_for=("backgrounds", "slides con mucho texto"),
        alt_hint="Fondo de superficie abstracta",
    ),
    "gradient-mesh": StylePreset(
        id="gradient-mesh",
        name="Gradient mesh",
        description="Mallas de gradiente ligeras y difusas; fondo elegante y no distractorio.",
        prompt=(
            "soft gradient mesh abstraction, flowing diffused colour fields, gentle bloom, "
            "smooth blurred transitions, no hard edges, minimalist contemporary"
        ),
        best_for=("backgrounds", "blog hero"),
        alt_hint="Degradado abstracto difuso",
    ),
    "isometric-tech": StylePreset(
        id="isometric-tech",
        name="Isometric tech",
        description="Isométrico limpio de sistemas, servidores, flujos y pipelines.",
        prompt=(
            "clean isometric 3D illustration of abstract technical systems, stacked layers, data flows, "
            "precise geometry, soft shadows, crisp vector-like finish, no characters"
        ),
        best_for=("explicar arquitectura", "procesos", "integración"),
        alt_hint="Ilustración isométrica de sistemas técnicos",
    ),
    "flat-vector": StylePreset(
        id="flat-vector",
        name="Flat vector editorial",
        description="Ilustración plana editorial, formas simples, ideal para conceptos de negocio.",
        prompt=(
            "flat vector editorial illustration, simplified geometric shapes, confident silhouettes, "
            "subtle texture overlay, plenty of breathing room, magazine-quality composition"
        ),
        best_for=("conceptos de negocio", "blog inline"),
        alt_hint="Ilustración vectorial plana",
    ),
    "line-art": StylePreset(
        id="line-art",
        name="Minimal line art",
        description="Líneas finas sobre fondo liso; máxima elegancia, mínimo ruido.",
        prompt=(
            "minimal single-weight line art on a flat background, elegant thin strokes, "
            "technical blueprint precision, restrained detail, large empty areas"
        ),
        best_for=("secciones de texto", "quotes", "agenda"),
        alt_hint="Ilustración de líneas minimalista",
    ),
    "editorial-photo": StylePreset(
        id="editorial-photo",
        name="Editorial photography",
        description="Fotografía editorial de producto/entorno, luz natural y profundidad de campo.",
        prompt=(
            "editorial photography, natural directional light, shallow depth of field, "
            "premium materials, muted colour grade, architectural minimalism, no people in frame"
        ),
        best_for=("casos de uso", "industria", "office"),
        alt_hint="Fotografía editorial",
    ),
    "data-viz": StylePreset(
        id="data-viz",
        name="Abstract data visual",
        description="Gráficos y dashboards abstractos como metáfora de datos y métricas.",
        prompt=(
            "abstract data visualisation artwork, floating translucent charts, bar and line glyphs, "
            "grid overlays, glow accents, no readable labels or numbers, elegant information aesthetic"
        ),
        best_for=("traction", "métricas", "IA"),
        alt_hint="Visualización de datos abstracta",
    ),
    "glass-ui": StylePreset(
        id="glass-ui",
        name="Glassmorphism UI",
        description="Paneles de vidrio, capas translúcidas; moderno para producto/SaaS.",
        prompt=(
            "abstract glassmorphism composition, frosted translucent panels, layered depth, "
            "soft specular highlights, floating cards without readable content, premium SaaS aesthetic"
        ),
        best_for=("producto", "SaaS", "demo"),
        alt_hint="Composición de paneles translúcidos",
    ),
    "topographic": StylePreset(
        id="topographic",
        name="Topographic flow lines",
        description="Curvas de nivel y flujos; transmite sistema, escala y precisión.",
        prompt=(
            "elegant topographic contour lines and flowing ridgelines forming abstract landscapes, "
            "finely graded strokes, depth through line density, technical yet organic"
        ),
        best_for=("escala", "roadmap", "estrategia"),
        alt_hint="Líneas topográficas abstractas",
    ),
    "collage": StylePreset(
        id="collage",
        name="Editorial collage",
        description="Collage de papel y texturas; más humano y expresivo.",
        prompt=(
            "editorial paper collage, torn edges, layered cut-paper texture, subtle print grain, "
            "bold shapes, art-directed magazine cover energy"
        ),
        best_for=("cultura", "talento", "marca"),
        alt_hint="Collage editorial de papel",
    ),
    "blueprint": StylePreset(
        id="blueprint",
        name="Technical blueprint",
        description="Planos técnicos, retículas y anotaciones; para arquitectura y seguridad.",
        prompt=(
            "technical blueprint drawing, fine white grid, precise schematic shapes, "
            "measurement ticks and registration marks, drafting table aesthetic, no readable annotations"
        ),
        best_for=("seguridad", "arquitectura", "compliance"),
        alt_hint="Plano técnico esquemático",
    ),
    # ------------------------------------------------------------------ blog
    "blog-satire": StylePreset(
        id="blog-satire",
        name="Blog · foto deadpan absurda",
        description=(
            "Foto editorial realista con una premisa ridícula actuada en serio: robots como colegas, "
            "oficinas, concilios históricos. El caballo de batalla del blog."
        ),
        prompt=(
            "photorealistic editorial photograph, a single ridiculous premise staged completely straight, "
            "believable real-world environment (office, institution, boardroom, historical reenactment), "
            "mundane props carrying the joke, robots and humans treated as equally ordinary colleagues, "
            "deadpan expressions and body language, natural available light with bright even exposure, "
            "clean neutral photographic colour, honest whites and real skin tones, "
            "no colour cast, no coloured lighting, no magenta or violet tint, no gradient overlay or vignette, "
            "shallow depth of field, wide cinematic framing, sharp realistic detail, "
            "no illustration, no cartoon stylisation, no neon glow"
        ),
        best_for=("hero de artículo", "LinkedIn", "portada de newsletter"),
        alt_hint="Fotografía editorial irónica",
    ),
    "blog-diagram": StylePreset(
        id="blog-diagram",
        name="Blog · diagrama dibujado a mano",
        description=(
            "Diagrama tipo pizarra explicado por alguien: flechas gruesas con gradiente violeta-magenta, "
            "iconos con sombra, títulos manuscritos. Pide allow_text=true para las anotaciones."
        ),
        prompt=(
            "hand-drawn marker explainer diagram on a clean off-white board, wobbly hand-drawn arrows with "
            "gradient fills going from violet #4F00C4 to magenta #FF5CF3, one contrasting mint-green accent "
            "curve, simple sketched icons with soft drop shadows, thick handwritten headings, minimal axes "
            "with arrowheads, generous empty space, the charming imprecision of a smart colleague drawing "
            "while explaining, flat two-dimensional, not a photo, not 3D"
        ),
        best_for=("explicar un concepto", "figura interior", "carrusel educativo"),
        alt_hint="Diagrama explicativo dibujado a mano",
    ),
    "blog-mascot": StylePreset(
        id="blog-mascot",
        name="Blog · mascota 3D",
        description=(
            "Render 3D de un personaje adorable con mirada deadpan entre objetos reales; "
            "sirve para posts de producto o de cultura."
        ),
        prompt=(
            "3D character render, glossy stylised mascot with friendly deadpan eyes, sitting among believable "
            "real-world props, soft warm interior light, subtle subsurface glow, restrained Pixar-adjacent "
            "look, high-detail materials, shallow depth of field, cinematic composition, "
            "no text on the character itself"
        ),
        best_for=("cultura", "producto", "posts de comunidad"),
        alt_hint="Render 3D de mascota",
    ),
}

DEFAULT_STYLE = "abstract-geometric"

# El blog de Meik Labs no usa arte abstracto de marca: usa escenas concretas,
# deadpan y absurdas, con un tono relajado e irónico. Este bloque se añade solo
# a los estilos que empiezan con "blog-".
BLOG_TONE = (
    "tone: relaxed, self-aware and dryly ironic; the absurdity is played completely straight "
    "and the joke is obvious without being explained; one single clear idea per image; "
    "natural photographic colour with no colour cast and no brand-colour filter; "
    "no corporate stock-photo clichés such as handshakes, generic blue holograms or glowing brains; "
    "Spanish (Chile) wording when any text appears"
)

BLOG_STYLES: tuple[str, ...] = ("blog-satire", "blog-diagram", "blog-mascot")



@dataclass(frozen=True)
class Format:
    id: str
    name: str
    aspect_ratio: str
    purpose: str


FORMATS: dict[str, Format] = {
    "blog-hero": Format("blog-hero", "Blog hero / cover", "16:9", "Cabecera de artículo, OG image"),
    "blog-inline": Format("blog-inline", "Blog figure", "4:3", "Figura dentro del artículo"),
    "slide": Format("slide", "Slide 16:9", "16:9", "Visual de slide y fondo de deck"),
    "square": Format("square", "Square 1:1", "1:1", "Social, thumbnails, avatares de sección"),
    "portrait": Format("portrait", "Portrait 3:4", "3:4", "Cards verticales, blog mobile"),
    "story": Format("story", "Story 9:16", "9:16", "Stories, reels, banners verticales"),
}

TEXT_SPACES: dict[str, str] = {
    "none": "a balanced composition with no area reserved for text",
    "left": "the left third kept quiet and visually empty for a headline overlay",
    "right": "the right third kept quiet and visually empty for a headline overlay",
    "top": "the top third kept quiet and visually empty for a headline overlay",
    "bottom": "the bottom third kept quiet and visually empty for a headline overlay",
    "center": "the central band kept quiet and visually empty for a headline overlay",
}

DEFAULT_TEXT_SPACE = "left"


@dataclass(frozen=True)
class SlideArchetype:
    id: str
    name: str
    description: str
    prompt: str
    default_text_space: str = DEFAULT_TEXT_SPACE


SLIDE_TYPES: dict[str, SlideArchetype] = {
    "title": SlideArchetype(
        "title", "Portada de deck",
        "La slide 1: debe verse ambiciosa, limpia y con espacio para el título grande.",
        "bold abstract hero composition for a pitch deck cover, single dominant form, "
        "dramatic gradient lighting, cinematic depth",
        "right",
    ),
    "problem": SlideArchetype(
        "problem", "Problema",
        "Tensión, fricción, caos contenido. Sin dramatismo literal.",
        "abstract visual of tension and friction: fractured planes, misaligned grids, "
        "compressed shapes, restrained chaos dissolving into order",
        "right",
    ),
    "solution": SlideArchetype(
        "solution", "Solución",
        "Claridad, orden emergente, piezas que encajan.",
        "abstract visual of clarity emerging from complexity: interlocking modular forms aligning, "
        "clean geometry snapping into place, luminous seams",
        "left",
    ),
    "product": SlideArchetype(
        "product", "Producto / demo",
        "Capas de interfaz sin texto legible; sugiere producto digital.",
        "abstract layered interface composition, floating panels and depth, soft glow, "
        "no readable text or icons, product storytelling",
        "left",
    ),
    "market": SlideArchetype(
        "market", "Mercado / TAM",
        "Escala, expansión, magnitud.",
        "abstract visual of scale and expansion: nested fields radiating outward, orbital rings, "
        "gradient density increasing toward the edges",
        "right",
    ),
    "traction": SlideArchetype(
        "traction", "Tracción / métricas",
        "Crecimiento medible, sin números legibles.",
        "abstract growth visual: ascending translucent bars and ribbons, upward momentum, "
        "clean data-space aesthetic, no readable figures",
        "right",
    ),
    "competition": SlideArchetype(
        "competition", "Competencia",
        "Mapa de posicionamiento, diferenciación.",
        "abstract positioning diagram: sparse markers on a subtle grid, one highlighted node standing apart, "
        "clear hierarchy, no text",
        "right",
    ),
    "team": SlideArchetype(
        "team", "Equipo",
        "Unidad, red, personas (sin rostros).",
        "abstract network of connected nodes forming a cohesive constellation, warm human tone, "
        "no faces or portraits",
        "bottom",
    ),
    "roadmap": SlideArchetype(
        "roadmap", "Roadmap",
        "Progresión y fases.",
        "abstract sequential composition: clean stepped progression across the frame, "
        "pathway of glowing waypoints, forward motion",
        "top",
    ),
    "business-model": SlideArchetype(
        "business-model", "Modelo de negocio",
        "Ciclos, flujos, economía circular.",
        "abstract cyclical flow diagram, closed loop of interconnected vessels, "
        "smooth continuous motion, balanced composition, no labels",
        "left",
    ),
    "ask": SlideArchetype(
        "ask", "El ask",
        "Confianza y dirección; cierre de deck.",
        "confident abstract closing composition, converging lines toward a bright horizon, "
        "sense of direction and inevitability",
        "left",
    ),
    "quote": SlideArchetype(
        "quote", "Cita / testimonio",
        "Casi vacío, textura muy sutil para sostener una cita.",
        "extremely subtle abstract texture, near-monochrome, very low contrast, "
        "quiet atmospheric surface",
        "none",
    ),
}

DEFAULT_SLIDE_TYPE = "product"


@dataclass(frozen=True)
class BrandKit:
    name: str
    tagline: str
    fonts: tuple[str, ...]
    primary_hex: str
    secondary_hex: str
    ink_hex: str
    paper_hex: str
    palettes: dict[str, Palette] = field(default_factory=lambda: dict(PALETTES))
    styles: dict[str, StylePreset] = field(default_factory=lambda: dict(STYLES))
    formats: dict[str, Format] = field(default_factory=lambda: dict(FORMATS))
    slide_types: dict[str, SlideArchetype] = field(default_factory=lambda: dict(SLIDE_TYPES))


def get_brand_kit() -> BrandKit:
    return BrandKit(
        name=BRAND_NAME,
        tagline=BRAND_TAGLINE,
        fonts=BRAND_FONTS,
        primary_hex="#4F00C4",
        secondary_hex="#FF5CF3",
        ink_hex="#1C1C1C",
        paper_hex="#F5F5F5",
    )


def resolve_palette(palette: str | None) -> Palette:
    key = (palette or DEFAULT_PALETTE).strip().lower()
    if key in PALETTES:
        return PALETTES[key]
    valid = ", ".join(sorted(PALETTES))
    raise ValueError(f"Paleta desconocida: {palette!r}. Usa una de: {valid}.")


def resolve_style(style: str | None) -> StylePreset:
    key = (style or DEFAULT_STYLE).strip().lower()
    if key in STYLES:
        return STYLES[key]
    valid = ", ".join(sorted(STYLES))
    raise ValueError(f"Estilo desconocido: {style!r}. Usa uno de: {valid}.")


def resolve_format(media_format: str | None) -> Format:
    key = (media_format or "blog-hero").strip().lower()
    if key in FORMATS:
        return FORMATS[key]
    valid = ", ".join(sorted(FORMATS))
    raise ValueError(f"Formato desconocido: {media_format!r}. Usa uno de: {valid}.")


def resolve_slide_type(slide_type: str | None) -> SlideArchetype:
    key = (slide_type or DEFAULT_SLIDE_TYPE).strip().lower()
    if key in SLIDE_TYPES:
        return SLIDE_TYPES[key]
    valid = ", ".join(sorted(SLIDE_TYPES))
    raise ValueError(f"Tipo de slide desconocido: {slide_type!r}. Usa uno de: {valid}.")
