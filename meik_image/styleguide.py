"""El estilo editorial del blog de Meik Labs, capturado como sistema de prompts.

Sale de las imágenes reales publicadas en https://static.meiklabs.com/img/blog:

- mas-ai-mas-trabajo: oficina fotorrealista, oficinista sepultado en papel y robots
  cargando más pilas de papel, uno con una pantalla "PENDING".
- manual-resistencia-ingenieros-ia-saboteando-algoritmos: protesta dentro de la
  oficina con pancartas en español ("HUMANOS AL MANDO: LA RESISTENCIA DE LA OFICINA")
  frente a robots.
- prusia-ai: concilio de guerra prusiano con logos de IA como caras y un mapa
  rotulado "PROVINCIAL CHILE / BATTLEFIELD".
- brecha-ia-supervision-humana-inercia-organizacional: diagrama manuscrito, curvas
  violeta y verde, anotaciones en español ("LA BRECHA DE LA IA (THE AI GAP)").
- openclaw-rl-aprendizaje-continuo-agentes: mascota 3D (cangrejo robot con lupa y
  lentes leyendo un libro) en una biblioteca cálida.
"""

from __future__ import annotations

from typing import Any

from .brand import BLOG_STYLES, BLOG_TONE, STYLES

RULES: list[str] = [
    "Una sola premisa ridícula por imagen, actuada completamente en serio.",
    "Escena concreta y reconocible: oficina, sala de reuniones, campamento, biblioteca,"
    " mesa de directorio. Nunca un fondo abstracto.",
    "Lo absurdo está en la situación y los objetos, no en el acabado: la ejecución es"
    " realista, sobria y bien iluminada.",
    "La IA y los robots conviven como colegas aburridos, con expresión deadpan; nunca"
    " son amenazantes ni futuristas.",
    "El texto en español se usa cuando aporta el chiste (pancartas, pizarras, rótulos)"
    " y debe ser corto: 2 a 6 palabras por superficie.",
    "Referencias locales reconocibles para el lector chileno (lugares, cargos,"
    " instituciones) cuando el artículo lo permita.",
    "Composición ancha tipo editorial, luz natural o de ventana, exposición pareja y"
    " grado de color neutro: el violeta/magenta de marca aparece como acento en un prop,"
    " nunca como baño de color de todo el encuadre.",
    "Prohibido el cliché: manos estrechándose, hologramas azules, cerebros brillantes,"
    " personas señalando gráficos.",
]

REGISTER_GUIDANCE: dict[str, dict[str, Any]] = {
    "blog-satire": {
        "cuando": "Posts de opinión, análisis y noticias. El registro por defecto del blog.",
        "receta": (
            "{premisa absurda en una frase}. {escena concreta con objetos reconocibles}. "
            "{quién hace qué, con expresión neutra}. {detalle pequeño que cierra el chiste}."
        ),
        "ejemplo": (
            "Un equipo de robots de oficina reparte montañas de papel a un analista humano que ya "
            "no tiene dónde dejarlas; uno de los robots muestra en su pecho una pantalla que dice "
            "PENDING. Luz de ventana, oficina real, nadie sonríe."
        ),
        "allow_text": "opcional (rótulos y pantallas cortos)",
        "size": "linkedin-post o blog-hero",
        "paleta": "editorial-natural (recomendada) o neutral; brand-dark tiñe toda la escena",
    },
    "blog-diagram": {
        "cuando": "Explicar un concepto, una brecha o un modelo mental. Reemplaza al típico gráfico de consultora.",
        "receta": (
            "Diagrama dibujado a mano que explica {concepto}: {dos o tres elementos con flechas}, "
            "anotaciones cortas en español, {conclusión rotulada}."
        ),
        "ejemplo": (
            "Diagrama manuscrito con dos curvas: la IA subiendo en violeta y la adopción real subiendo "
            "apenas en verde; la brecha entre ambas rotulada «LA BRECHA DE LA IA»."
        ),
        "allow_text": "sí (es un diagrama: sin etiquetas no comunica)",
        "size": "blog-diagram",
    },
    "blog-mascot": {
        "cuando": "Cultura, producto y comunidad; humaniza un tema técnico.",
        "receta": (
            "Render 3D de {personaje mascota} haciendo {acción absurda y específica} entre "
            "{objetos reales}, mirada deadpan, luz cálida de interior."
        ),
        "ejemplo": (
            "Render 3D de un cangrejo robot con lentes y lupa leyendo un libro enorme en una biblioteca "
            "de libros apilados, mirada concentrada y absurda."
        ),
        "allow_text": "no",
        "size": "blog-inline o linkedin-post",
    },
}

TEXT_POLICY: dict[str, Any] = {
    "default": "sin texto: el titular y el copy van en HTML",
    "cuando_si": "diagramas (allow_text=true) y chistes que dependen de un cartel o pantalla",
    "limite": "2-6 palabras por superficie; mayúsculas; sin frases largas",
    "riesgo": (
        "Recraft V4.1 Flash V2 garabatea texto en español: si la imagen depende de las palabras, "
        "usa el parámetro model con un modelo que escriba bien "
        "(p. ej. google/gemini-3.1-flash-image) manteniendo el mismo prompt."
    ),
}

WORKFLOW: list[str] = [
    "1. Elige el registro según el artículo (satire por defecto; diagram si hay un concepto que explicar).",
    "2. Escribe la premisa absurda en castellano, en una frase, antes de escribir el prompt visual.",
    "3. Compón con la receta del registro + escena concreta + detalle que cierra el chiste.",
    "4. Usa size=linkedin-post (1200x627) o blog-hero (1600x900) según destino.",
    "5. Revisa el render: si el chiste no se entiende en 2 segundos, cambia la premisa, no el estilo.",
]


def blog_style_guide() -> dict[str, Any]:
    return {
        "registro": "blog de Meik Labs",
        "tono": BLOG_TONE,
        "estilos": {key: STYLES[key].description for key in BLOG_STYLES if key in STYLES},
        "reglas": RULES,
        "registros": REGISTER_GUIDANCE,
        "texto_en_imagen": TEXT_POLICY,
        "flujo": WORKFLOW,
        "referencias_reales": [
            {
                "archivo": "mas-ai-mas-trabajo.webp",
                "que_muestra": "oficinista sepultado en papel, robots cargando más papel, pantalla PENDING",
            },
            {
                "archivo": "manual-resistencia-ingenieros-ia-saboteando-algoritmos.webp",
                "que_muestra": "protesta dentro de la oficina, pancartas en español, robots enfrente",
            },
            {
                "archivo": "prusia-ai.webp",
                "que_muestra": "concilio de guerra histórico con logos de IA como caras y mapa rotulado",
            },
            {
                "archivo": "brecha-ia-supervision-humana-inercia-organizacional.webp",
                "que_muestra": "diagrama manuscrito con dos curvas y anotaciones en español",
            },
            {
                "archivo": "openclaw-rl-aprendizaje-continuo-agentes.webp",
                "que_muestra": "mascota 3D leyendo en una biblioteca cálida",
            },
        ],
    }
