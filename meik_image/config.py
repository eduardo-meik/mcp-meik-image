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
class MediaConfig:
    """Where generated images get published (cPanel / shared hosting)."""

    mode: str  # off | sftp | ftp | ftps
    host: str | None
    port: int | None
    user: str | None
    password: str | None
    remote_dir: str | None
    base_url: str | None
    subdir_by_date: bool

    @property
    def configured(self) -> bool:
        return bool(
            self.mode in {"sftp", "ftp", "ftps"}
            and self.host
            and self.user
            and self.password
            and self.remote_dir
            and self.base_url
        )


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
    output_format: str
    output_quality: int
    media: MediaConfig

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)


def _media_config() -> MediaConfig:
    host = _env_str("MEIK_MEDIA_HOST") or _env_str("SFTP_HOST")
    mode = (_env_str("MEIK_MEDIA_MODE") or ("sftp" if host else "off")).lower()
    port_raw = _env_str("MEIK_MEDIA_PORT") or _env_str("SFTP_PORT")
    default_port = {"sftp": 22, "ftp": 21, "ftps": 21}.get(mode)
    try:
        port = int(port_raw) if port_raw else default_port
    except ValueError:
        port = default_port
    return MediaConfig(
        mode=mode,
        host=host,
        port=port,
        user=_env_str("MEIK_MEDIA_USER") or _env_str("SFTP_USER"),
        password=_env_str("MEIK_MEDIA_PASSWORD") or _env_str("SFTP_PASS") or _env_str("SSH_PASSWORD"),
        remote_dir=_env_str("MEIK_MEDIA_REMOTE_DIR") or _env_str("REMOTE_DIR"),
        base_url=_env_str("MEIK_MEDIA_BASE_URL") or _env_str("BASE_URL"),
        subdir_by_date=_env_bool("MEIK_MEDIA_SUBDIR_BY_DATE", True),
    )


def load_settings() -> Settings:
    """Read settings fresh from the environment (cheap, safe to call per request)."""

    raw_dir = _env_str("MEIK_IMAGE_DIR", "output")
    image_dir: Path | None
    if raw_dir is None or raw_dir.lower() in {"off", "none", "false", "disabled"}:
        image_dir = None
    else:
        candidate = Path(raw_dir).expanduser()
        image_dir = candidate if candidate.is_absolute() else (BASE_DIR / candidate)

    output_format = (_env_str("MEIK_OUTPUT_FORMAT", "webp") or "webp").lower()

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
        output_format=output_format,
        output_quality=_env_int("MEIK_OUTPUT_QUALITY", 82),
        media=_media_config(),
    )


def configure_logging(settings: Settings | None = None) -> None:
    settings = settings or load_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
