"""Exact sizing, format conversion and byte budgets."""

from __future__ import annotations

import io
import os

import pytest
from PIL import Image

from meik_image.optimize import extension_of, normalize_format, optimize_image


def _graphic_bytes(size=(1344, 768)) -> bytes:
    """A brand-like flat graphic: compresses the way real Recraft output does."""
    buffer = io.BytesIO()
    Image.new("RGB", size, (79, 0, 196)).save(buffer, format="PNG")
    return buffer.getvalue()


def _gradient_bytes(size=(1200, 630)) -> bytes:
    """Gradients are what Recraft actually returns; they are the honest size benchmark."""
    ramp = Image.radial_gradient("L").resize(size)
    image = Image.merge("RGB", (ramp, ramp.point(lambda v: 255 - v), ramp))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _noise_bytes(size=(1344, 768)) -> bytes:
    buffer = io.BytesIO()
    Image.frombytes("RGB", size, os.urandom(size[0] * size[1] * 3)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_format_aliases_and_validation() -> None:
    assert normalize_format("jpg") == "jpeg"
    assert normalize_format("WEBP") == "webp"
    assert normalize_format("auto", "jpeg") == "jpeg"
    with pytest.raises(ValueError, match="Formato de salida desconocido"):
        normalize_format("tiff")


def test_exact_size_with_cover_crops_to_requested_dimensions() -> None:
    processed = optimize_image(_graphic_bytes(), "image/png", output_format="webp", width=1200, height=630)

    assert (processed.width, processed.height) == (1200, 630)
    assert processed.fmt == "webp"
    assert processed.media_type == "image/webp"
    assert any("cover crop" in step for step in processed.steps)
    assert extension_of(processed) == "webp"


def test_width_only_keeps_aspect_ratio() -> None:
    processed = optimize_image(_graphic_bytes(), "image/png", output_format="jpeg", width=800)

    assert processed.width == 800
    assert processed.height == round(768 * (800 / 1344))


def test_contain_pads_instead_of_cropping() -> None:
    processed = optimize_image(
        _graphic_bytes((400, 400)), "image/png", output_format="png", width=600, height=300, fit="contain"
    )

    assert (processed.width, processed.height) == (600, 300)
    assert any("contain pad" in step for step in processed.steps)


def test_webp_is_the_lightest_and_jpeg_beats_png_for_gradient_art() -> None:
    source = _gradient_bytes()

    as_png = optimize_image(source, "image/png", output_format="png")
    as_jpeg = optimize_image(source, "image/png", output_format="jpeg")
    as_webp = optimize_image(source, "image/png", output_format="webp")

    assert as_webp.size_bytes < as_jpeg.size_bytes < as_png.size_bytes
    assert as_jpeg.media_type == "image/jpeg"
    assert as_webp.media_type == "image/webp"


def test_max_kb_budget_is_respected() -> None:
    processed = optimize_image(_noise_bytes(), "image/png", output_format="jpeg", max_kb=200)

    assert processed.size_bytes <= 200 * 1024
    assert any("fitted under" in step for step in processed.steps)


def test_quality_floor_and_scale_down_when_quality_alone_is_not_enough() -> None:
    processed = optimize_image(
        _noise_bytes(), "image/png", output_format="webp", quality=95, max_kb=60
    )

    assert processed.size_bytes <= 60 * 1024
    assert any("scaled down" in step for step in processed.steps)


def test_upscaling_is_reported() -> None:
    processed = optimize_image(_graphic_bytes((400, 225)), "image/png", output_format="webp", width=1600)

    assert processed.width == 1600
    assert any("upscaled" in step for step in processed.steps)


def test_svg_is_passed_through_untouched() -> None:
    svg = b"<svg xmlns='http://www.w3.org/2000/svg' width='10' height='10'/>"
    processed = optimize_image(svg, "image/svg+xml", output_format="webp", width=100)

    assert processed.data == svg
    assert processed.fmt == "svg"
