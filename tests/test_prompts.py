"""Prompt composition: brand guardrails, palette strictness and text-space reservation."""

from __future__ import annotations

import pytest

from meik_image import prompts
from meik_image.brand import (
    DEFAULT_PALETTE,
    DEFAULT_STYLE,
    resolve_format,
    resolve_palette,
    resolve_style,
    resolve_slide_type,
)


def test_freeform_prompt_carries_no_text_guardrail_and_text_space() -> None:
    prompt = prompts.compose_freeform(
        "abstract layered planes",
        style=resolve_style(DEFAULT_STYLE),
        palette=resolve_palette(DEFAULT_PALETTE),
        text_space="right",
    )

    assert "abstract layered planes" in prompt
    assert "no text" in prompt
    assert "no logos" in prompt
    assert "the right third" in prompt
    assert prompt.endswith(".")


def test_allow_text_removes_the_lettering_guardrail() -> None:
    prompt = prompts.compose_freeform(
        "minimal wordmark lockup",
        style=resolve_style("line-art"),
        palette=resolve_palette(DEFAULT_PALETTE),
        allow_text=True,
    )

    assert "no text" not in prompt
    assert "no captions" not in prompt
    assert "no photorealistic faces" in prompt


def test_strict_palette_uses_locked_wording() -> None:
    palette = resolve_palette("brand-dark")
    style = resolve_style("gradient-mesh")

    strict = prompts.compose_freeform("x", style=style, palette=palette, strict_palette=True)
    soft = prompts.compose_freeform("x", style=style, palette=palette, strict_palette=False)

    assert "strictly limited to" in strict
    assert "strictly limited to" not in soft
    assert "leaning toward" in soft


def test_blog_hero_reserves_space_for_the_headline() -> None:
    prompt = prompts.compose_blog_hero(
        title="Automatización con criterio",
        angle="cómo priorizar procesos antes de comprar IA",
        keywords=["procesos", "datos", "priorización", "procesos"],
        style=resolve_style("abstract-geometric"),
        palette=resolve_palette("brand-light"),
        text_space="left",
    )

    assert "Automatización con criterio" in prompt
    assert "visual cues evoking procesos, datos, priorización" in prompt
    assert "the left third" in prompt
    assert "Meik Labs" in prompt


def test_slide_visual_uses_archetype_default_text_space() -> None:
    slide = resolve_slide_type("title")
    prompt = prompts.compose_slide_visual(
        slide=slide,
        title="Meik Labs · Serie A",
        key_message="categoría nueva de automatización",
        style=resolve_style("abstract-geometric"),
        palette=resolve_palette("brand-dark"),
    )

    assert "pitch-deck slide" in prompt
    assert "the right third" in prompt
    assert "categoría nueva de automatización" in prompt


def test_background_prompt_avoids_focal_subject() -> None:
    prompt = prompts.compose_background(
        theme="light",
        style=resolve_style("gradient-mesh"),
        palette=resolve_palette("brand-light"),
        intensity="subtle",
    )

    assert "#F5F5F5" in prompt
    assert "no focal subject" in prompt
    assert "extremely low contrast" in prompt
    assert "dark text remains readable" in prompt


def test_dark_background_keeps_the_frame_dark_for_white_text() -> None:
    prompt = prompts.compose_background(
        theme="dark",
        style=resolve_style("gradient-mesh"),
        palette=resolve_palette("brand-dark"),
    )

    assert "near-black #1C1C1C" in prompt
    assert "white text remains readable" in prompt
    assert "under 20% of the frame" in prompt


def test_unknown_style_palette_or_slide_type_raise() -> None:
    with pytest.raises(ValueError, match="Estilo desconocido"):
        resolve_style("vaporwave")
    with pytest.raises(ValueError, match="Paleta desconocida"):
        resolve_palette("neon")
    with pytest.raises(ValueError, match="Tipo de slide desconocido"):
        resolve_slide_type("dank-memes")
    with pytest.raises(ValueError, match="Formato desconocido"):
        resolve_format("billboard")


def test_empty_prompt_is_rejected() -> None:
    with pytest.raises(ValueError, match="vacío"):
        prompts.compose_freeform("   ", style=resolve_style(DEFAULT_STYLE), palette=resolve_palette(DEFAULT_PALETTE))


def test_filename_slug_is_ascii_and_bounded() -> None:
    assert prompts.compose_filename_slug("Récord de 95% en pagos automáticos") == "record-de-95-en-pagos-automaticos"
    assert prompts.compose_filename_slug("!!!") == "meik-image"
