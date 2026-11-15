"""ASGI entrypoint for FastMCP Gateway / Horizon.

The platform builds the repo with uv and serves it with uvicorn, importing
``src.server:app`` (the default layout of its starter template). This module keeps
that contract while reusing the server defined in ``main.py``.

Exposed objects:
- ``mcp``: the FastMCP instance (for ``fastmcp run src/server.py:mcp``)
- ``app``: the Starlette/ASGI application (for ``uvicorn src.server:app``)
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import app, mcp  # noqa: E402

__all__ = ["app", "mcp"]