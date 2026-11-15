"""Shared test fixtures: keep generated artefacts out of the repo tree."""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture()
def png_bytes() -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (320, 180), (79, 0, 196)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture()
def webp_bytes() -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (1344, 768), (255, 92, 243)).save(buffer, format="WEBP", quality=95)
    return buffer.getvalue()


@pytest.fixture()
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test")
    monkeypatch.setenv("MEIK_IMAGE_DIR", str(tmp_path / "assets"))
    monkeypatch.delenv("MEIK_IMAGE_MODEL", raising=False)
    monkeypatch.delenv("MEIK_INLINE_MAX_CHARS", raising=False)
    return tmp_path
