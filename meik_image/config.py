"""Runtime configuration resolved from environment variables / .env."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = "recraft/recraft-v4.1-flash-v2:free"
DEFAULT_INLINE_MAX_CHARS = 120_000

load_dotenv(BASE_DIR / ".env", override=False)


def _env_str(name: str, default: str | None = None) -> str | None:
    raw = os.environ.get(name)
    if raw is None:
        return default
    value = raw.strip().strip('"').strip("'")
    return value or default


def _env_int(name: str, default: int) -> int:
    raw = _env_str(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        logging.getLogger("meik_image").warning("Invalid integer for %s: %r; using %s", name, raw, default)
        return default


def _env_float(name: str, default: float) -> float:
    raw = _env_str(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        logging.getLogger("meik_image").warning("Invalid number for %s: %r; using %s", name, raw, default)
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = _env_str(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on", "si", "sí"}


@dataclass(frozen=True)
class Settings:
    api_key: str | None
    model: str
    image_dir: Path | None
    inline_max_chars: int
    timeout_seconds: float
    max_retries: int
    app_url: str
    app_name: str
    log_level: str

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)


def load_settings() -> Settings:
    """Read settings fresh from the environment (cheap, safe to call per request)."""

    raw_dir = _env_str("MEIK_IMAGE_DIR", "output")
    image_dir: Path | None
    if raw_dir is None or raw_dir.lower() in {"off", "none", "false", "disabled"}:
        image_dir = None
    else:
        candidate = Path(raw_dir).expanduser()
        image_dir = candidate if candidate.is_absolute() else (BASE_DIR / candidate)

    return Settings(
        api_key=_env_str("OPENROUTER_API_KEY"),
        model=_env_str("MEIK_IMAGE_MODEL", DEFAULT_MODEL) or DEFAULT_MODEL,
        image_dir=image_dir,
        inline_max_chars=_env_int("MEIK_INLINE_MAX_CHARS", DEFAULT_INLINE_MAX_CHARS),
        timeout_seconds=_env_float("MEIK_IMAGE_TIMEOUT_SECONDS", 180.0),
        max_retries=_env_int("MEIK_IMAGE_MAX_RETRIES", 2),
        app_url=_env_str("MEIK_APP_URL", "https://meiklabs.com") or "https://meiklabs.com",
        app_name=_env_str("MEIK_APP_NAME", "Meik Labs Image MCP") or "Meik Labs Image MCP",
        log_level=(_env_str("LOG_LEVEL", "INFO") or "INFO").upper(),
    )


def configure_logging(settings: Settings | None = None) -> None:
    settings = settings or load_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
