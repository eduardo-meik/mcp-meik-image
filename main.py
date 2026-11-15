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

Flujo recomendado:
1. Llama `brand_kit` para ver estilos, paletas, formatos y arquetipos de slide.
2. Blog: `generate_blog_hero` (16:9, reserva espacio para el titular) y `generate_blog_figure` (4:3).
3. Pitch deck: `generate_pitch_slide_visual` para cada slide y `generate_deck_background` (theme dark).
4. Para todo lo demás usa `generate_image` con style/palette explícitos.

Reglas de uso:
- Nunca pidas palabras o letras dentro de la imagen: el copy se compone en HTML o en la slide.
- Usa siempre las paletas brand-dark o brand-light salvo que se pida otra cosa.
- Cada herramienta devuelve las imágenes inline (para verlas) y un JSON con prompt, coste,
  dimensiones y ruta del archivo original cuando el servidor corre en local.
- El texto alternativo se entrega como `alt_text_hint`: refínalo antes de publicarlo.
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
