"""OpenRouter parameter handling, error translation and inline payload sizing."""

from __future__ import annotations

import base64

import httpx
import pytest

from meik_image import imaging
from meik_image.openrouter import (
    ImageGenerationError,
    normalize_aspect_ratio,
    normalize_n,
)


def test_aspect_ratio_aliases_and_validation() -> None:
    assert normalize_aspect_ratio("landscape") == "16:9"
    assert normalize_aspect_ratio("Story") == "9:16"
    assert normalize_aspect_ratio(" 16:9 ") == "16:9"
    with pytest.raises(ImageGenerationError, match="no soportada"):
        normalize_aspect_ratio("21:9")


def test_n_is_clamped_and_capped() -> None:
    assert normalize_n(0) == 1
    assert normalize_n(None) == 1
    assert normalize_n(4) == 4
    with pytest.raises(ImageGenerationError, match="máximo es 6"):
        normalize_n(9)


def test_quota_and_auth_errors_are_actionable() -> None:
    unauthorized = httpx.Response(401, json={"error": {"message": "No auth credentials found"}})
    no_credit = httpx.Response(402, json={"error": {"message": "Insufficient credits"}})

    auth_message = str(_translate(unauthorized))
    assert "OPENROUTER_API_KEY inválida" in auth_message
    assert "No auth credentials found" in auth_message

    credit_message = str(_translate(no_credit))
    assert "saldo" in credit_message
    assert "Insufficient credits" in credit_message


def _translate(response: httpx.Response) -> ImageGenerationError:
    from meik_image.openrouter import OpenRouterImageClient

    return OpenRouterImageClient._translate_error(response)


def test_sniff_media_type_detects_webp_and_svg(webp_bytes: bytes) -> None:
    assert imaging.sniff_media_type(webp_bytes) == "image/webp"
    assert imaging.sniff_media_type(b'<?xml version="1.0"?><svg/>') == "image/svg+xml"
    assert imaging.extension_for("image/webp") == "webp"


def test_small_payload_is_returned_untouched(png_bytes: bytes) -> None:
    payload = imaging.fit_inline(png_bytes, "image/png", max_chars=10_000_000)

    assert payload.data == png_bytes
    assert payload.downscaled is False
    assert payload.width == 320
    assert payload.height == 180


def test_oversized_payload_is_downscaled_to_fit_budget() -> None:
    import io
    import os

    from PIL import Image

    # Random pixels compress badly, so the original payload cannot fit the budget.
    noise = Image.frombytes("RGB", (1200, 800), os.urandom(1200 * 800 * 3))
    buffer = io.BytesIO()
    noise.save(buffer, format="PNG")
    original = buffer.getvalue()
    budget = 120_000

    payload = imaging.fit_inline(original, "image/png", max_chars=budget)

    assert payload.downscaled is True
    assert payload.media_type == "image/webp"
    assert payload.base64_chars <= budget
    assert len(base64.b64encode(payload.data)) == payload.base64_chars
    assert payload.width is not None and payload.width <= 1200


def test_impossible_budget_returns_smallest_attempt_instead_of_raising() -> None:
    import io
    import os

    from PIL import Image

    noise = Image.frombytes("RGB", (800, 600), os.urandom(800 * 600 * 3))
    buffer = io.BytesIO()
    noise.save(buffer, format="PNG")

    payload = imaging.fit_inline(buffer.getvalue(), "image/png", max_chars=1_000)

    assert payload.downscaled is True
    assert payload.width is not None and payload.width <= 320


def test_svg_is_never_recompressed() -> None:
    svg = b"<svg xmlns='http://www.w3.org/2000/svg'>" + b"x" * 5_000 + b"</svg>"
    payload = imaging.fit_inline(svg, "image/svg+xml", max_chars=100)

    assert payload.data == svg
    assert payload.media_type == "image/svg+xml"
    assert payload.downscaled is False
