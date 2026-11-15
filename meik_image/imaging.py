"""Image decoding, format sniffing and inline-payload sizing.

Claude's MCP connectors cap a single tool result (roughly 150k characters), and a
base64 image costs ~1.33 chars per byte. Full-resolution files are therefore written
to disk when storage is enabled, while the inline copy is downscaled just enough to
fit the client budget.
"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass

RASTER_EXTENSIONS = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/svg+xml": "svg",
}

# (max_dimension, quality) tried in order until the payload fits the budget.
COMPRESSION_LADDER: tuple[tuple[int, int], ...] = (
    (1600, 90),
    (1400, 86),
    (1280, 82),
    (1152, 78),
    (1024, 74),
    (896, 70),
    (768, 66),
    (640, 60),
    (512, 55),
    (448, 50),
    (384, 45),
    (320, 40),
)


@dataclass(frozen=True)
class InlinePayload:
    data: bytes
    media_type: str
    base64_chars: int
    downscaled: bool
    width: int | None
    height: int | None


def sniff_media_type(data: bytes, fallback: str | None = None) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    head = data[:512].lstrip().lower()
    if head.startswith(b"<?xml") or head.startswith(b"<svg"):
        return "image/svg+xml"
    return (fallback or "image/png").lower()


def extension_for(media_type: str) -> str:
    return RASTER_EXTENSIONS.get(media_type.lower(), "webp")


def dimensions(data: bytes) -> tuple[int | None, int | None]:
    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as image:
            return image.size
    except Exception:  # noqa: BLE001 - SVG or unknown formats
        return None, None


def _encode_webp(data: bytes, max_dim: int, quality: int) -> bytes | None:
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover - pillow is a hard dependency
        return None

    try:
        with Image.open(io.BytesIO(data)) as source:
            image = source.copy()
    except Exception:  # noqa: BLE001 - SVG and other non-raster payloads
        return None

    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
    if max(image.size) > max_dim:
        image.thumbnail((max_dim, max_dim), Image.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, format="WEBP", quality=quality, method=6)
    return buffer.getvalue() or None


def fit_inline(data: bytes, media_type: str, max_chars: int) -> InlinePayload:
    """Return a payload whose base64 representation fits ``max_chars``."""
    media = sniff_media_type(data, media_type)
    encoded_chars = len(base64.b64encode(data))
    width, height = dimensions(data)

    if encoded_chars <= max_chars:
        return InlinePayload(data, media, encoded_chars, False, width, height)

    if media == "image/svg+xml":
        # Vectors cannot be recompressed here; report honestly instead of mangling them.
        return InlinePayload(data, media, encoded_chars, False, None, None)

    for max_dim, quality in COMPRESSION_LADDER:
        candidate = _encode_webp(data, max_dim, quality)
        if candidate is None:
            break
        candidate_chars = len(base64.b64encode(candidate))
        if candidate_chars <= max_chars:
            width, height = dimensions(candidate)
            return InlinePayload(candidate, "image/webp", candidate_chars, True, width, height)

    # Nothing fit the budget; ship the smallest attempt we produced.
    smallest = _encode_webp(data, COMPRESSION_LADDER[-1][0], COMPRESSION_LADDER[-1][1])
    if smallest is None:
        return InlinePayload(data, media, encoded_chars, False, width, height)
    width, height = dimensions(smallest)
    return InlinePayload(smallest, "image/webp", len(base64.b64encode(smallest)), True, width, height)
