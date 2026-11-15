"""Prompt composition for Meik Labs blog and pitch-deck imagery.

Image models render text badly, so every composition carries an explicit guardrail
against lettering unless the caller deliberately allows it.
"""

from __future__ import annotations

from .brand import (
    BLOG_TONE,
    DEFAULT_TEXT_SPACE,
    TEXT_SPACES,
    Palette,
    SlideArchetype,
    StylePreset,
)

NO_TEXT_GUARDRAIL = (
    "absolutely no text, no lettering, no words, no numbers, no captions, no logos, "
    "no watermarks, no readable UI labels"
)
NO_FACES_GUARDRAIL = "no photorealistic faces, no close-up portraits"


def _clean(value: str | None) -> str:
    return (value or "").strip().strip(". ")


def _join(parts: list[str | None]) -> str:
    seen: set[str] = set()
    ordered: list[str] = []
    for part in parts:
        if not part:
            continue
        cleaned = part.strip().strip(",").strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(cleaned)
    return ", ".join(ordered) + "."


def _text_space_clause(text_space: str | None) -> str:
    key = (text_space or DEFAULT_TEXT_SPACE).strip().lower()
    return TEXT_SPACES.get(key, TEXT_SPACES[DEFAULT_TEXT_SPACE])


def _palette_clause(palette: Palette, strict: bool) -> str | None:
    if not palette.prompt:
        return None
    if strict:
        return palette.prompt
    return palette.prompt.replace("strictly limited to", "leaning toward")


def _guardrails(allow_text: bool) -> str | None:
    pieces = [NO_FACES_GUARDRAIL]
    if not allow_text:
        pieces.insert(0, NO_TEXT_GUARDRAIL)
    return ", ".join(pieces)


def _tone_clause(style: StylePreset, tone: str | None = None) -> str | None:
    """Blog styles carry the editorial voice of Meik Labs automatically."""
    if tone:
        return tone
    if style.id.startswith("blog-"):
        return BLOG_TONE
    return None


def _faces_clause(style: StylePreset, allow_text: bool) -> str | None:
    """Editorial photo registers need real people, so the no-faces rule must relax."""
    if style.id in {"blog-satire", "blog-mascot"}:
        pieces = [] if allow_text else [NO_TEXT_GUARDRAIL]
        pieces.append(
            "ordinary believable people allowed, neutral deadpan expressions, "
            "no glamour retouching, no stock-photo smiling"
        )
        return ", ".join(pieces)
    return _guardrails(allow_text)


def compose_freeform(
    prompt: str,
    *,
    style: StylePreset,
    palette: Palette,
    text_space: str | None = None,
    strict_palette: bool = True,
    allow_text: bool = False,
    mood: str | None = None,
    must_include: str | None = None,
    must_avoid: str | None = None,
) -> str:
    subject = _clean(prompt)
    if not subject:
        raise ValueError("El prompt no puede estar vacío.")
    return _join(
        [
            subject,
            style.prompt,
            mood,
            must_include,
            _palette_clause(palette, strict_palette),
            _tone_clause(style),
            _text_space_clause(text_space) if text_space else None,
            f"avoid: {must_avoid}" if _clean(must_avoid) else None,
            _faces_clause(style, allow_text),
        ]
    )


def compose_blog_hero(
    *,
    title: str,
    angle: str | None,
    keywords: list[str] | None,
    style: StylePreset,
    palette: Palette,
    text_space: str | None = DEFAULT_TEXT_SPACE,
    strict_palette: bool = True,
    allow_text: bool = False,
    mood: str | None = None,
) -> str:
    topic = _clean(angle) or _clean(title)
    keyword_clause = None
    if keywords:
        cleaned = [k.strip() for k in keywords if k and k.strip()]
        if cleaned:
            keyword_clause = "visual cues evoking " + ", ".join(cleaned)
    return _join(
        [
            f"hero illustration for a Meik Labs blog article titled \"{_clean(title)}\" about {topic}",
            style.prompt,
            keyword_clause,
            mood,
            _palette_clause(palette, strict_palette),
            _tone_clause(style),
            "wide cinematic composition, subject weighted to one side, confident negative space",
            _text_space_clause(text_space),
            _faces_clause(style, allow_text),
        ]
    )


def compose_blog_figure(
    *,
    concept: str,
    style: StylePreset,
    palette: Palette,
    text_space: str | None = "none",
    strict_palette: bool = True,
    allow_text: bool = False,
    mood: str | None = None,
) -> str:
    return _join(
        [
            f"editorial figure illustrating {_clean(concept)} for a Meik Labs article",
            style.prompt,
            mood,
            _palette_clause(palette, strict_palette),
            _tone_clause(style),
            "self-contained central composition that reads well at small size",
            _text_space_clause(text_space),
            _faces_clause(style, allow_text),
        ]
    )


def compose_slide_visual(
    *,
    slide: SlideArchetype,
    title: str,
    key_message: str | None,
    style: StylePreset,
    palette: Palette,
    text_space: str | None = None,
    strict_palette: bool = True,
    allow_text: bool = False,
) -> str:
    message = _clean(key_message)
    message_clause = f"metaphor for {message}" if message else None
    return _join(
        [
            f"visual for a Meik Labs pitch-deck slide titled \"{_clean(title)}\" ({slide.name})",
            slide.prompt,
            message_clause,
            style.prompt,
            _palette_clause(palette, strict_palette),
            "presentation-ready composition, readable from across a room at 16:9",
            _text_space_clause(text_space or slide.default_text_space),
            _faces_clause(style, allow_text),
        ]
    )


def compose_background(
    *,
    theme: str,
    style: StylePreset,
    palette: Palette,
    intensity: str = "subtle",
    strict_palette: bool = True,
    allow_text: bool = False,
) -> str:
    theme_key = (theme or "dark").strip().lower()
    if theme_key in {"dark", "oscuro"}:
        surface = "deep near-black #1C1C1C presentation background"
        readability = (
            "overall value stays dark across the whole frame so white text remains readable everywhere"
        )
        colour_budget = "colour restricted to a soft glow under 20% of the frame"
    elif theme_key in {"light", "claro"}:
        surface = "clean off-white #F5F5F5 presentation background"
        readability = (
            "overall value stays bright and even across the whole frame so dark text remains readable everywhere"
        )
        colour_budget = "colour reduced to a pale tint under 20% of the frame"
    else:
        surface = f"{theme_key} presentation background"
        readability = "even value across the frame so overlaid text remains readable"
        colour_budget = "colour restricted to a small area under 20% of the frame"

    intensity_key = (intensity or "subtle").strip().lower()
    intensity_clause = {
        "subtle": (
            "extremely low contrast, calm and quiet, barely-there detail, "
            "no bright highlights, tonal range compressed around the base colour"
        ),
        "medium": "moderate detail away from the centre, calm regions for text",
        "bold": "expressive shapes outside the text safe area",
    }.get(intensity_key, "extremely low contrast, calm and quiet, barely-there detail")

    return _join(
        [
            f"abstract presentation background, {surface}",
            style.prompt,
            _palette_clause(palette, strict_palette),
            intensity_clause,
            colour_budget,
            readability,
            "no bright blooms, no large saturated areas, no focal subject, no horizon",
            _text_space_clause("center"),
            _guardrails(allow_text),
        ]
    )


def suggest_alt_text(
    *,
    subject: str,
    style: StylePreset,
    palette: Palette,
    purpose: str,
) -> str:
    """Deterministic first draft; the calling model is expected to polish it."""
    palette_note = {
        "brand-dark": "en violeta y magenta sobre negro",
        "brand-light": "en violeta y magenta sobre blanco",
        "brand-mono": "en violeta monocromático",
        "neutral": "en grises neutros con acento violeta",
        "warm": "en tonos cálidos con base violeta",
        "cool": "en azules fríos con acento violeta",
        "none": "",
    }.get(palette.id, "")
    pieces = [style.alt_hint or "Imagen abstracta", palette_note, f"para {purpose}: {subject.strip()}"]
    return " ".join(p.strip() for p in pieces if p and p.strip()).strip(" :") + "."


def compose_filename_slug(subject: str, *, max_words: int = 6) -> str:
    """Turn a human subject into a stable, filesystem-safe slug."""
    import re
    import unicodedata

    normalized = unicodedata.normalize("NFKD", subject or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    words = re.findall(r"[a-z0-9]+", ascii_text)[:max_words]
    return "-".join(words) or "meik-image"
