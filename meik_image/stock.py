"""Unsplash como fuente de fotografía real.

Evaluación (resumen, ver README para el detalle):

- Aporta fotografía auténtica y bien producida, imposible de igualar con un modelo
  text-to-image de 3 segundos.
- No sirve para el registro satírico del blog: no puede inventar la escena absurda
  (robots repartiendo papel, concilio prusiano con logos). Para eso sigue Recraft.
- La licencia de Unsplash permite uso comercial gratuito, pero **no** permite
  recompilar las fotos para crear un servicio competidor, y las guías de la API
  piden atribución y disparar el endpoint de descarga cuando se usa una foto.

Por eso queda como fuente opcional (`UNSPLASH_ACCESS_KEY`) para contextos donde una
foto real es mejor que una ilustración: oficinas, industria, equipo, producto.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger("meik_image.stock")

API_BASE = "https://api.unsplash.com"
USER_AGENT = "MeikLabsImageMCP/1.0"


class StockError(RuntimeError):
    """Unsplash failure with a message meant for the calling model."""


@dataclass(frozen=True)
class StockPhoto:
    id: str
    description: str | None
    width: int
    height: int
    photographer: str
    photographer_url: str
    page_url: str
    color: str | None
    download_location: str | None
    urls: dict[str, str]

    @property
    def attribution(self) -> dict[str, str]:
        return {
            "photo_by": self.photographer,
            "photographer_url": self.photographer_url,
            "photo_page": self.page_url,
            "license": "Unsplash License (uso comercial permitido, no recompilar)",
            "credit_text": f"Foto: {self.photographer} / Unsplash",
        }


class UnsplashClient:
    def __init__(self, access_key: str | None) -> None:
        self._key = access_key

    @property
    def configured(self) -> bool:
        return bool(self._key)

    def _headers(self) -> dict[str, str]:
        if not self._key:
            raise StockError(
                "Falta UNSPLASH_ACCESS_KEY. Créala en https://unsplash.com/oauth/applications "
                "(Access Key) y añádela al entorno del servidor."
            )
        return {"Authorization": f"Client-ID {self._key}", "Accept-Version": "v1", "User-Agent": USER_AGENT}

    def search(
        self,
        query: str,
        *,
        orientation: str | None = None,
        count: int = 6,
        color: str | None = None,
    ) -> list[StockPhoto]:
        params: dict[str, Any] = {
            "query": query,
            "per_page": max(1, min(count, 30)),
            "content_filter": "high",
        }
        if orientation in {"landscape", "portrait", "squarish"}:
            params["orientation"] = orientation
        if color:
            params["color"] = color
        try:
            with httpx.Client(timeout=30, headers=self._headers()) as client:
                response = client.get(f"{API_BASE}/search/photos", params=params)
        except httpx.HTTPError as exc:
            raise StockError(f"No se pudo consultar Unsplash: {exc}") from exc

        if response.status_code == 401:
            raise StockError("Unsplash rechazó la ACCESS KEY (401). Revisa UNSPLASH_ACCESS_KEY.")
        if response.status_code == 403:
            raise StockError("Unsplash respondió 403: límite de peticiones alcanzado o app deshabilitada.")
        if response.status_code >= 400:
            raise StockError(f"Unsplash respondió {response.status_code}: {response.text[:200]}")

        results = (response.json() or {}).get("results") or []
        photos: list[StockPhoto] = []
        for item in results:
            try:
                photos.append(
                    StockPhoto(
                        id=item["id"],
                        description=item.get("description") or item.get("alt_description"),
                        width=int(item.get("width") or 0),
                        height=int(item.get("height") or 0),
                        photographer=(item.get("user") or {}).get("name") or "Unsplash",
                        photographer_url=(item.get("user") or {}).get("links", {}).get("html") or "",
                        page_url=(item.get("links") or {}).get("html") or "",
                        color=item.get("color"),
                        download_location=(item.get("links") or {}).get("download_location"),
                        urls=item.get("urls") or {},
                    )
                )
            except (KeyError, TypeError):
                continue
        return photos

    def get_photo(self, photo_id: str) -> StockPhoto:
        try:
            with httpx.Client(timeout=30, headers=self._headers()) as client:
                response = client.get(f"{API_BASE}/photos/{photo_id}")
        except httpx.HTTPError as exc:
            raise StockError(f"No se pudo consultar Unsplash: {exc}") from exc
        if response.status_code == 404:
            raise StockError(f"Unsplash no conoce la foto {photo_id!r}.")
        if response.status_code >= 400:
            raise StockError(f"Unsplash respondió {response.status_code}: {response.text[:200]}")
        item = response.json() or {}
        return StockPhoto(
            id=item.get("id") or photo_id,
            description=item.get("description") or item.get("alt_description"),
            width=int(item.get("width") or 0),
            height=int(item.get("height") or 0),
            photographer=(item.get("user") or {}).get("name") or "Unsplash",
            photographer_url=(item.get("user") or {}).get("links", {}).get("html") or "",
            page_url=(item.get("links") or {}).get("html") or "",
            color=item.get("color"),
            download_location=(item.get("links") or {}).get("download_location"),
            urls=item.get("urls") or {},
        )

    def fetch(self, photo: StockPhoto, *, size: str = "regular") -> bytes:
        url = photo.urls.get(size) or photo.urls.get("regular") or photo.urls.get("full")
        if not url:
            raise StockError(f"La foto {photo.id} no trae URL de imagen.")
        try:
            with httpx.Client(timeout=60, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
                response = client.get(url)
                response.raise_for_status()
                data = response.content
                self._track_download(client, photo)
        except httpx.HTTPError as exc:
            raise StockError(f"No se pudo descargar la foto {photo.id}: {exc}") from exc
        if not data:
            raise StockError(f"La descarga de {photo.id} llegó vacía.")
        return data

    def _track_download(self, client: httpx.Client, photo: StockPhoto) -> None:
        """Unsplash asks API consumers to ping download_location when a photo is used."""
        if not photo.download_location:
            return
        try:
            client.get(photo.download_location, headers=self._headers())
        except Exception as exc:  # noqa: BLE001 - tracking must never break publishing
            logger.debug("No se pudo registrar la descarga en Unsplash: %s", exc)


def client_from_settings() -> UnsplashClient:
    from .config import load_settings

    return UnsplashClient(load_settings().unsplash_access_key)
