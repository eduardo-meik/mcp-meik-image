"""Alias so ``src.main:app`` / ``src.main:mcp`` also resolve.

Some templates configure the entrypoint as ``src/main.py:mcp``; keeping this module
avoids a missing-module failure whichever path the platform is configured with.
"""

from __future__ import annotations

from src.server import app, mcp

__all__ = ["app", "mcp"]
