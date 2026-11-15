"""Meik Labs image generation MCP server.

Entrypoint for Prefect Horizon / FastMCP Gateway: ``main.py:mcp``
Local stdio (Claude Desktop / Claude Code): ``python main.py``
Local HTTP: ``python main.py --http``
Health check: ``python main.py --check``
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Launchers (Claude Desktop, fastmcp run, Horizon) may start this file from any cwd.
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastmcp import FastMCP  # noqa: E402

from meik_image import __version__  # noqa: E402
from meik_image.config import configure_logging, load_settings  # noqa: E402
from meik_image.storage import AssetStore  # noqa: E402
from meik_image.tools import register_tools  # noqa: E402

INSTRUCTIONS = """\
Servidor de generación de imágenes de Meik Labs (Recraft V4.1 Flash V2 vía OpenRouter).

Marca: violeta #4F00C4, magenta #FF5CF3, tinta #1C1C1C, papel #F5F5F5.
Tipografías: Space Grotesk (títulos), Inter (cuerpo), JetBrains Mono (código).

Registro editorial del blog: NO es arte abstracto de marca. Es escena concreta, deadpan
y absurda, con tono relajado e irónico (robots como colegas, oficinas, concilios
históricos, diagramas dibujados a mano). Usa `blog_style_guide` antes de escribir un
prompt de blog.

Flujo recomendado:
1. `brand_kit` para paletas/estilos y `blog_style_guide` para el registro del blog.
2. Blog: `generate_blog_hero` con style=blog-satire (foto deadpan) o blog-diagram
   (explicativo, allow_text=true). `generate_blog_figure` para figuras intermedias.
3. Redes: `generate_image` con style=blog-satire y output.size=linkedin-post.
4. Pitch deck: `generate_pitch_slide_visual` (estilos glass-ui/isometric-tech/quiet-surface).
5. Foto real en vez de ilustración: `search_stock_photos` y `publish_stock_photo`
   (Unsplash, requiere UNSPLASH_ACCESS_KEY; devuelve atribución obligatoria).

Tamaños: usa `output.size` en vez de inventar píxeles. Presets disponibles con
`size_presets`: linkedin-post 1200x627, linkedin-square 1024x1024, linkedin-portrait,
linkedin-company-cover 1344x336, blog-hero 1344x768, blog-inline 1216x896,
blog-diagram 1216x860, blog-wide 1344x672, og-image 1200x630, x-post, x-card,
instagram-square, instagram-story, youtube-thumb, slide 1920x1080, pptx, slide-4k.
El modelo genera como máximo 1344 px de lado largo: por sobre eso se interpola y el
manifiesto lo marca en `optimization` y `source_dimensions`.

Formato y peso: `output.format` (webp por defecto, o jpeg/png/avif), `quality` y
`max_kb` (webp pesa ~3x menos que jpeg para el mismo arte).

Publicación: con el media server configurado, cada imagen se sube y el manifiesto trae
`public_url`. `media_server_status` diagnostica y `publish_asset` reintenta.

Reglas de uso:
- Nunca pidas texto si no es un diagrama o un chiste que dependa de un cartel: el copy
  va en HTML. Con texto, usa 2-6 palabras por superficie y mayúsculas.
- Si las palabras tienen que leerse sí o sí, pasa `model="google/gemini-3.1-flash-image"`.
- Paletas: brand-dark o brand-light; el registro blog tolera la paleta de marca como acento.
- Cada herramienta devuelve las imágenes inline más un JSON con prompt, coste, tamaño,
  formato, peso, ruta local, URL pública y `alt_text_hint` para refinar.
"""

mcp = FastMCP(
    name="Meik Labs · Imágenes",
    instructions=INSTRUCTIONS,
    version=__version__,
)

register_tools(mcp)


def _health() -> dict:
    import asyncio

    settings = load_settings()
    store = AssetStore(settings.image_dir)
    try:
        tools = sorted(tool.name for tool in asyncio.run(mcp.list_tools()))
    except Exception:  # noqa: BLE001 - health check must never crash
        tools = []
    return {
        "status": "ok" if settings.has_api_key else "missing_api_key",
        "version": __version__,
        "model": settings.model,
        "api_key_configured": settings.has_api_key,
        "image_dir": str(store.root) if store.enabled and store.root else None,
        "inline_max_chars": settings.inline_max_chars,
        "tools": sorted(tools),
    }


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    settings = load_settings()
    configure_logging(settings)

    if "--check" in args:
        print(json.dumps(_health(), ensure_ascii=False, indent=2))
        raise SystemExit(0 if settings.has_api_key else 1)

    if "--http" in args:
        port = 8000
        for index, arg in enumerate(args):
            if arg == "--port" and index + 1 < len(args):
                port = int(args[index + 1])
        mcp.run(transport="http", host="0.0.0.0", port=port)
        return

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
