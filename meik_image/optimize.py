"""Post-processing: exact pixel sizes, web-friendly formats and byte budgets.

Recraft V4.1 Flash V2 only accepts an aspect ratio (1:1, 4:3, 3:4, 16:9, 9:16, auto),
so a concrete pixel size is produced here: resize + crop/pad, then re-encode.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

from .imaging import extension_for, sniff_media_type

SUPPORTED_FORMATS = ("webp", "jpeg", "png", "avif")
DEFAULT_QUALITY = {"webp": 82, "jpeg": 85, "avif": 60, "png": None}
MIME_BY_FORMAT = {
    "webp": "image/webp",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "avif": "image/avif",
}
FIT_MODES = ("cover", "contain", "stretch")
MIN_DIMENSION = 64


@dataclass(frozen=True)
class ProcessedImage:
    data: bytes
    media_type: str
    fmt: str
    width: int | None
    height: int | None
    steps: tuple[str, ...] = field(default_factory=tuple)

    @property
    def size_bytes(self) -> int:
        return len(self.data)


def normalize_format(value: str | None, fallback: str = "webp") -> str:
    raw = (value or "auto").strip().lower()
    if raw in {"auto", ""}:
        return normalize_format(fallback)
    if raw in {"jpg", "jpe"}:
        raw = "jpeg"
    if raw not in SUPPORTED_FORMATS:
        allowed = ", ".join(SUPPORTED_FORMATS)
        raise ValueError(f"Formato de salida desconocido: {value!r}. Usa uno de: {allowed}.")
    return raw


def _resolve_target(
    source: tuple[int, int],
    width: int | None,
    height: int | None,
) -> tuple[int, int] | None:
    sw, sh = source
    if width and height:
        return max(MIN_DIMENSION, int(width)), max(MIN_DIMENSION, int(height))
    if width:
        return max(MIN_DIMENSION, int(width)), max(MIN_DIMENSION, round(sh * (width / sw)))
    if height:
        return max(MIN_DIMENSION, round(sw * (height / sh))), max(MIN_DIMENSION, int(height))
    return None


def _apply_geometry(image, target: tuple[int, int], fit: str, background: tuple[int, int, int]):
    from PIL import Image

    tw, th = target
    sw, sh = image.size
    steps: list[str] = []
    mode = fit if fit in FIT_MODES else "cover"

    if mode == "stretch":
        out = image.resize((tw, th), Image.LANCZOS)
        steps.append(f"stretched to {tw}x{th}")
    elif mode == "cover":
        scale = max(tw / sw, th / sh)
        interim = (max(tw, round(sw * scale)), max(th, round(sh * scale)))
        resized = image.resize(interim, Image.LANCZOS)
        left = (interim[0] - tw) // 2
        top = (interim[1] - th) // 2
        out = resized.crop((left, top, left + tw, top + th))
        steps.append(f"cover crop to {tw}x{th}")
    else:  # contain
        scale = min(tw / sw, th / sh)
        interim = (max(1, round(sw * scale)), max(1, round(sh * scale)))
        resized = image.resize(interim, Image.LANCZOS)
        canvas = Image.new("RGBA", (tw, th), (*background, 255))
        canvas.paste(resized, ((tw - interim[0]) // 2, (th - interim[1]) // 2), resized if resized.mode == "RGBA" else None)
        out = canvas
        steps.append(f"contain pad to {tw}x{th}")

    if max(image.size) < max(tw, th):
        steps.append("upscaled beyond source resolution")
    return out, steps


def _encode(image, fmt: str, quality: int | None) -> bytes:
    buffer = io.BytesIO()
    kwargs: dict = {}
    if fmt == "png":
        image.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()
    if fmt == "webp":
        image.convert("RGBA" if image.mode == "RGBA" else "RGB").save(
            buffer, format="WEBP", quality=quality or DEFAULT_QUALITY["webp"], method=6
        )
        return buffer.getvalue()
    if fmt == "avif":
        image.convert("RGBA" if image.mode == "RGBA" else "RGB").save(
            buffer, format="AVIF", quality=quality or DEFAULT_QUALITY["avif"]
        )
        return buffer.getvalue()
    flat = image.convert("RGB") if image.mode != "RGB" else image
    flat.save(buffer, format="JPEG", quality=quality or DEFAULT_QUALITY["jpeg"], optimize=True, progressive=True)
    return buffer.getvalue()


def optimize_image(
    data: bytes,
    media_type: str,
    *,
    output_format: str | None = None,
    quality: int | None = None,
    width: int | None = None,
    height: int | None = None,
    fit: str = "cover",
    max_kb: int | None = None,
    background: tuple[int, int, int] = (28, 28, 28),
) -> ProcessedImage:
    """Resize/convert ``data``.

    ``max_kb`` keeps stepping quality (and then scale) down until the file fits,
    which is what you want for blog pages and pitch decks.
    """
    media = sniff_media_type(data, media_type)
    fmt = normalize_format(output_format)
    if media == "image/svg+xml":
        return ProcessedImage(data, media, "svg", None, None, ("svg passthrough (no raster transform)",))

    from PIL import Image

    with Image.open(io.BytesIO(data)) as opened:
        image = opened.copy()

    steps: list[str] = []
    if width or height:
        target = _resolve_target(image.size, width, height)
        if target:
            image, geometry_steps = _apply_geometry(image, target, fit, background)
            steps.extend(geometry_steps)

    if fmt == "jpeg" and image.mode in ("RGBA", "LA", "P"):
        flat = Image.new("RGB", image.size, background)
        rgba = image.convert("RGBA")
        flat.paste(rgba, mask=rgba.split()[-1])
        image = flat
        steps.append(f"alpha flattened onto rgb{background}")

    q = quality if quality else DEFAULT_QUALITY[fmt]
    encoded = _encode(image, fmt, q)
    steps.append(f"{fmt} q{q or 'lossless'}")

    if max_kb and fmt != "png":
        floor_quality = 40
        attempts = 0
        while len(encoded) > max_kb * 1024 and attempts < 12:
            attempts += 1
            if q and q > floor_quality:
                q = max(floor_quality, q - 8)
                steps.append(f"quality lowered to q{q}")
            else:
                scale = 0.85
                new_size = (
                    max(MIN_DIMENSION, int(image.size[0] * scale)),
                    max(MIN_DIMENSION, int(image.size[1] * scale)),
                )
                if new_size == image.size:
                    break
                image = image.resize(new_size, Image.LANCZOS)
                q = floor_quality if q else None
                steps.append(f"scaled down to {new_size[0]}x{new_size[1]}")
            encoded = _encode(image, fmt, q)
        steps.append(f"fitted under {max_kb} KB ({len(encoded) // 1024} KB)")

    return ProcessedImage(
        data=encoded,
        media_type=MIME_BY_FORMAT[fmt],
        fmt=fmt,
        width=image.size[0],
        height=image.size[1],
        steps=tuple(steps),
    )


def extension_of(processed: ProcessedImage) -> str:
    return "jpg" if processed.fmt == "jpeg" else extension_for(processed.media_type)
