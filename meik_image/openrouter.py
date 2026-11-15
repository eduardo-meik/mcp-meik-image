"""Thin, well-behaved client for OpenRouter's dedicated Image API."""

from __future__ import annotations

import base64
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Sequence

import httpx

from .config import Settings

logger = logging.getLogger("meik_image.openrouter")

IMAGE_API_URL = "https://openrouter.ai/api/v1/images"
SUPPORTED_ASPECT_RATIOS = ("1:1", "4:3", "3:4", "16:9", "9:16", "auto")
MAX_IMAGES_PER_CALL = 6

ASPECT_ALIASES = {
    "square": "1:1",
    "cuadrado": "1:1",
    "landscape": "16:9",
    "wide": "16:9",
    "horizontal": "16:9",
    "paisaje": "16:9",
    "portrait": "3:4",
    "vertical": "3:4",
    "retrato": "3:4",
    "story": "9:16",
    "stories": "9:16",
    "reel": "9:16",
    "classic": "4:3",
    "auto": "auto",
}

RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


class ImageGenerationError(RuntimeError):
    """Raised with a message that is safe and useful to surface to the calling model."""


def normalize_aspect_ratio(value: str | None) -> str:
    raw = (value or "16:9").strip().lower()
    raw = ASPECT_ALIASES.get(raw, raw).replace(" ", "")
    if raw not in SUPPORTED_ASPECT_RATIOS:
        allowed = ", ".join(SUPPORTED_ASPECT_RATIOS)
        raise ImageGenerationError(
            f"Proporción '{value}' no soportada por Recraft V4.1 Flash V2. Usa una de: {allowed}."
        )
    return raw


def normalize_n(value: int | None) -> int:
    try:
        count = int(value if value is not None else 1)
    except (TypeError, ValueError):
        count = 1
    if count < 1:
        count = 1
    if count > MAX_IMAGES_PER_CALL:
        raise ImageGenerationError(f"n máximo es {MAX_IMAGES_PER_CALL} imágenes por llamada.")
    return count


@dataclass(frozen=True)
class GeneratedImage:
    data: bytes
    media_type: str


@dataclass(frozen=True)
class GenerationResult:
    images: tuple[GeneratedImage, ...]
    model: str
    aspect_ratio: str
    cost_usd: float | None
    duration_seconds: float
    usage: dict[str, Any] = field(default_factory=dict)


class OpenRouterImageClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _headers(self) -> dict[str, str]:
        if not self._settings.api_key:
            raise ImageGenerationError(
                "Falta OPENROUTER_API_KEY. Configúrala en el entorno del servidor "
                "(variable de entorno o archivo .env) antes de generar imágenes."
            )
        return {
            "Authorization": f"Bearer {self._settings.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self._settings.app_url,
            "X-Title": self._settings.app_name,
        }

    def generate(
        self,
        prompt: str,
        *,
        aspect_ratio: str | None = "16:9",
        n: int | None = 1,
        model: str | None = None,
        palette_colors: Sequence[tuple[int, int, int]] | None = None,
    ) -> GenerationResult:
        ratio = normalize_aspect_ratio(aspect_ratio)
        count = normalize_n(n)
        model_id = (model or self._settings.model).strip()

        payload: dict[str, Any] = {
            "model": model_id,
            "prompt": prompt,
            "aspect_ratio": ratio,
            "n": count,
        }
        if palette_colors:
            # Recraft accepts provider-specific "controls"; passing RGB anchors keeps
            # generated artwork inside the Meik Labs palette.
            payload["provider"] = {
                "options": {
                    "recraft": {
                        "controls": {
                            "colors": [{"rgb": [int(c) for c in rgb[:3]]} for rgb in palette_colors]
                        }
                    }
                }
            }

        attempts = max(0, self._settings.max_retries) + 1
        last_error: Exception | None = None
        started = time.perf_counter()

        for attempt in range(1, attempts + 1):
            try:
                with httpx.Client(timeout=self._settings.timeout_seconds) as client:
                    response = client.post(IMAGE_API_URL, headers=self._headers(), json=payload)
                if response.status_code >= 400:
                    error = self._translate_error(response)
                    if response.status_code in RETRYABLE_STATUS and attempt < attempts:
                        delay = self._retry_delay(response, attempt)
                        logger.warning(
                            "OpenRouter %s on attempt %s/%s; retrying in %.1fs",
                            response.status_code,
                            attempt,
                            attempts,
                            delay,
                        )
                        time.sleep(delay)
                        last_error = error
                        continue
                    raise error
                result = self._parse(response, model_id, ratio, time.perf_counter() - started)
                logger.info(
                    "Generated %s image(s) with %s in %.1fs (cost=%s)",
                    len(result.images),
                    model_id,
                    result.duration_seconds,
                    result.cost_usd,
                )
                return result
            except ImageGenerationError:
                raise
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < attempts:
                    delay = min(2 ** (attempt - 1), 8)
                    logger.warning("Network error contacting OpenRouter (%s); retrying in %ss", exc, delay)
                    time.sleep(delay)
                    continue
                raise ImageGenerationError(
                    f"No se pudo contactar OpenRouter tras {attempts} intento(s): {exc}"
                ) from exc

        raise ImageGenerationError(str(last_error) if last_error else "Generación fallida.")

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        header = response.headers.get("retry-after")
        if header:
            try:
                return min(float(header), 20.0)
            except ValueError:
                pass
        return min(2 ** (attempt - 1), 8)

    @staticmethod
    def _translate_error(response: httpx.Response) -> ImageGenerationError:
        detail = ""
        try:
            body = response.json()
            if isinstance(body, dict):
                error = body.get("error")
                if isinstance(error, dict):
                    detail = str(error.get("message") or "")
                elif error:
                    detail = str(error)
                if not detail:
                    detail = str(body.get("message") or "")
        except Exception:  # noqa: BLE001 - best-effort error extraction
            detail = (response.text or "")[:300]

        detail = detail.strip()
        suffix = f" Detalle: {detail}" if detail else ""
        status = response.status_code
        if status == 401:
            return ImageGenerationError("OPENROUTER_API_KEY inválida o revocada (401)." + suffix)
        if status == 402:
            return ImageGenerationError(
                "La cuenta de OpenRouter no tiene saldo suficiente (402). "
                "Usa el modelo :free o agrega créditos." + suffix
            )
        if status == 429:
            return ImageGenerationError("Límite de peticiones alcanzado en OpenRouter (429)." + suffix)
        if status == 400:
            return ImageGenerationError(
                "OpenRouter rechazó la petición (400). Revisa el prompt o los parámetros." + suffix
            )
        return ImageGenerationError(f"OpenRouter respondió {status}.{suffix}")

    @staticmethod
    def _parse(response: httpx.Response, model_id: str, ratio: str, elapsed: float) -> GenerationResult:
        try:
            body = response.json()
        except ValueError as exc:
            raise ImageGenerationError("OpenRouter devolvió una respuesta no JSON.") from exc

        entries = body.get("data") or []
        images: list[GeneratedImage] = []
        for entry in entries:
            encoded = entry.get("b64_json") or entry.get("image") or entry.get("url")
            if not encoded:
                continue
            if isinstance(encoded, str) and encoded.startswith(("http://", "https://")):
                raise ImageGenerationError(
                    "OpenRouter devolvió una URL de imagen en lugar de datos binarios; "
                    "no se puede incrustar la imagen en esta respuesta."
                )
            try:
                raw = base64.b64decode(encoded, validate=False)
            except Exception as exc:  # noqa: BLE001
                raise ImageGenerationError("La imagen devuelta no es base64 válido.") from exc
            media_type = entry.get("media_type") or "image/png"
            images.append(GeneratedImage(data=raw, media_type=media_type))

        if not images:
            raise ImageGenerationError("OpenRouter no devolvió ninguna imagen.")

        usage = body.get("usage") or {}
        cost = usage.get("cost")
        try:
            cost_value = float(cost) if cost is not None else None
        except (TypeError, ValueError):
            cost_value = None

        return GenerationResult(
            images=tuple(images),
            model=model_id,
            aspect_ratio=ratio,
            cost_usd=cost_value,
            duration_seconds=round(elapsed, 2),
            usage=usage,
        )
