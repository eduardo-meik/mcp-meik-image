"""Size presets (LinkedIn, blog, decks) and the captured blog style."""

from __future__ import annotations

import pytest

from meik_image import prompts
from meik_image.brand import BLOG_TONE, resolve_palette, resolve_style
from meik_image.presets import SIZES, catalog, resolve_size
from meik_image.styleguide import blog_style_guide


def test_linkedin_post_matches_the_documented_size() -> None:
    preset = resolve_size("linkedin-post")

    assert preset is not None
    assert (preset.width, preset.height) == (1200, 627)
    assert round(preset.ratio, 3) == 1.914
    assert preset.model_ratio == "16:9"
    assert preset.max_kb == 200
    assert preset.default_style == "blog-satire"


def test_every_preset_uses_a_supported_model_ratio() -> None:
    supported = {"1:1", "4:3", "3:4", "16:9", "9:16", "auto"}

    for preset in SIZES.values():
        assert preset.model_ratio in supported, preset.id
        assert preset.fit in {"cover", "contain", "stretch"}, preset.id
        assert preset.width >= 64 and preset.height >= 64, preset.id


def test_unknown_size_is_rejected_with_the_valid_list() -> None:
    with pytest.raises(ValueError, match="Tamaño desconocido"):
        resolve_size("tiktok-vertical")


def test_size_aliases_return_none_for_free_form() -> None:
    assert resolve_size("auto") is None
    assert resolve_size(None) is None


def test_catalog_is_serialisable_and_covers_linkedin_and_decks() -> None:
    data = catalog()

    assert "linkedin-post" in data
    assert "linkedin-company-cover" in data
    assert "slide" in data
    assert data["linkedin-post"]["ratio"] == 1.914


def test_native_sizes_match_the_model_floor() -> None:
    from meik_image.presets import NATIVE_SIZE

    assert NATIVE_SIZE["16:9"] == (1344, 768)
    assert resolve_size("blog-hero").needs_upscale is False  # type: ignore[union-attr]
    assert resolve_size("slide").needs_upscale is True  # type: ignore[union-attr]
    assert catalog()["blog-hero"]["needs_upscale"] is False


def test_blog_style_prompt_carries_the_meik_tone() -> None:
    prompt = prompts.compose_blog_hero(
        title="La IA no reemplaza, multiplica el papeleo",
        angle="por qué la automatización mal aplicada crea más trabajo",
        keywords=["papeleo", "robots"],
        style=resolve_style("blog-satire"),
        palette=resolve_palette("brand-dark"),
        text_space="right",
    )

    assert BLOG_TONE in prompt
    assert "deadpan" in prompt
    assert "ironic" in prompt or "ironía" in prompt


def test_abstract_styles_do_not_get_the_blog_tone() -> None:
    prompt = prompts.compose_freeform(
        "shapes",
        style=resolve_style("abstract-geometric"),
        palette=resolve_palette("brand-dark"),
    )

    assert BLOG_TONE not in prompt


def test_blog_satire_allows_people_instead_of_forbidding_faces() -> None:
    prompt = prompts.compose_freeform(
        "robots de oficina repartiendo papel a un analista",
        style=resolve_style("blog-satire"),
        palette=resolve_palette("brand-dark"),
    )

    assert "no photorealistic faces" not in prompt
    assert "deadpan expressions" in prompt


def test_blog_diagram_can_keep_its_labels() -> None:
    with_text = prompts.compose_freeform(
        "diagrama de dos curvas",
        style=resolve_style("blog-diagram"),
        palette=resolve_palette("brand-dark"),
        allow_text=True,
    )
    without_text = prompts.compose_freeform(
        "diagrama de dos curvas",
        style=resolve_style("blog-diagram"),
        palette=resolve_palette("brand-dark"),
    )

    assert "no text" not in with_text
    assert "no text" in without_text


def test_style_guide_documents_registers_rules_and_references() -> None:
    guide = blog_style_guide()

    assert set(guide["registros"]) == {"blog-satire", "blog-diagram", "blog-mascot"}
    assert len(guide["reglas"]) >= 6
    assert len(guide["referencias_reales"]) >= 5
    assert "texto_en_imagen" in guide
    assert "absurd" in guide["tono"] or "irónic" in guide["tono"]


def test_natural_palette_applies_no_provider_colour_controls() -> None:
    """A colour control on the provider is what tinted the photos magenta."""
    natural = resolve_palette("natural")

    assert natural.colors == ()
    assert "no magenta or violet tint" in natural.prompt
    assert "no colour cast" in natural.prompt


def test_editorial_natural_is_an_alias_of_natural() -> None:
    assert resolve_palette("editorial-natural") is resolve_palette("natural")


def test_blog_style_prompt_forbids_the_brand_colour_wash() -> None:
    prompt = prompts.compose_blog_hero(
        title="CapLite explica la banca del futuro",
        angle="por qué una cuenta digital no necesita sucursal",
        keywords=None,
        style=resolve_style("blog-satire"),
        palette=resolve_palette("natural"),
    )

    assert "no colour cast" in prompt
    assert "brand violet and magenta only as small accents" not in prompt
    assert "no gradient overlay or vignette" in prompt


def test_blog_tools_default_to_the_natural_palette() -> None:
    import asyncio

    from main import mcp

    tools = {tool.name: tool for tool in asyncio.run(mcp.list_tools())}
    for name in ("generate_blog_hero", "generate_blog_figure"):
        schema = tools[name].parameters
        palette = schema["properties"]["palette"]
        assert palette.get("default") == "natural", name
