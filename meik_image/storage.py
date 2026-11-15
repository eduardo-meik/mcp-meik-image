"""Local asset library: save full-resolution renders with JSON sidecars.

Storage is a local convenience. On a hosted deployment (Prefect Horizon / FastMCP
Gateway) the filesystem is ephemeral, so the inline image in the tool result stays
the source of truth.
"""

from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .imaging import extension_for, sniff_media_type

logger = logging.getLogger("meik_image.storage")


@dataclass(frozen=True)
class StoredAsset:
    asset_id: str
    path: Path
    media_type: str
    bytes_written: int
    created_at: str


def slugify(value: str, max_words: int = 6) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    words = re.findall(r"[a-z0-9]+", ascii_text)[:max_words]
    return "-".join(words) or "meik-image"

class AssetStore:
    """Writes renders under a root directory and reads them back safely."""

    def __init__(self, root: Path | None) -> None:
        self._root = root

    @property
    def enabled(self) -> bool:
        return self._root is not None

    @property
    def root(self) -> Path | None:
        return self._root

    def _ensure_root(self) -> Path:
        if self._root is None:
            raise RuntimeError("El almacenamiento local está deshabilitado (MEIK_IMAGE_DIR=off).")
        self._root.mkdir(parents=True, exist_ok=True)
        return self._root

    def save(
        self,
        data: bytes,
        media_type: str,
        *,
        slug: str,
        metadata: dict[str, Any],
        filename: str | None = None,
    ) -> StoredAsset | None:
        if self._root is None:
            return None
        try:
            root = self._ensure_root()
            today = datetime.now().strftime("%Y-%m-%d")
            folder = root / today
            folder.mkdir(parents=True, exist_ok=True)

            media = sniff_media_type(data, media_type)
            if filename:
                stem = Path(filename).stem
                asset_id = slugify(stem, max_words=12)
                path = folder / f"{asset_id}.{extension_for(media)}"
            else:
                asset_id = f"{slugify(slug)}-{datetime.now().strftime('%H%M%S')}-{uuid.uuid4().hex[:6]}"
                path = folder / f"{asset_id}.{extension_for(media)}"
            path.write_bytes(data)

            created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            sidecar = {
                "asset_id": asset_id,
                "file": path.name,
                "media_type": media,
                "bytes": len(data),
                "created_at": created_at,
                **metadata,
            }
            (folder / f"{asset_id}.json").write_text(
                json.dumps(sidecar, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return StoredAsset(asset_id, path, media, len(data), created_at)
        except OSError as exc:
            logger.warning("No se pudo guardar el asset en disco (%s); se devuelve sólo inline.", exc)
            return None

    def _iter_files(self) -> Iterator[Path]:
        if self._root is None or not self._root.exists():
            return iter(())
        return (
            p
            for p in sorted(self._root.rglob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
            if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".webp", ".gif", ".svg"}
        )

    def list_assets(self, *, limit: int = 20, query: str | None = None) -> list[dict[str, Any]]:
        if self._root is None:
            return []
        needle = (query or "").strip().lower()
        results: list[dict[str, Any]] = []
        for path in self._iter_files():
            meta = self._read_sidecar(path)
            if needle:
                haystack = " ".join(
                    part
                    for part in (
                        path.name,
                        json.dumps(meta, ensure_ascii=False) if meta else "",
                    )
                    if part
                ).lower()
                if needle not in haystack:
                    continue
            results.append(
                {
                    "asset_id": path.stem,
                    "file": str(path),
                    "media_type": (meta or {}).get("media_type"),
                    "prompt": (meta or {}).get("prompt"),
                    "style": (meta or {}).get("style"),
                    "palette": (meta or {}).get("palette"),
                    "aspect_ratio": (meta or {}).get("aspect_ratio"),
                    "created_at": (meta or {}).get("created_at"),
                }
            )
            if len(results) >= max(1, limit):
                break
        return results

    def load(self, asset_id: str) -> tuple[bytes, str, dict[str, Any]] | None:
        """Resolve an asset id (or file name) to bytes, media type and sidecar metadata."""
        if self._root is None:
            return None
        root = self._root.resolve()

        def inside(path: Path) -> bool:
            try:
                path.resolve().relative_to(root)
            except ValueError:
                return False
            return True

        candidate = root / asset_id
        if not inside(candidate):
            return None
        candidate = candidate.resolve()
        if not candidate.exists():
            matches = [p for p in self._iter_files() if p.stem == asset_id or p.name == asset_id]
            if not matches or not inside(matches[0]):
                return None
            candidate = matches[0].resolve()
        if not candidate.is_file():
            return None
        data = candidate.read_bytes()
        media = sniff_media_type(data, (self._read_sidecar(candidate) or {}).get("media_type"))
        return data, media, self._read_sidecar(candidate) or {}

    @staticmethod
    def _read_sidecar(path: Path) -> dict[str, Any] | None:
        sidecar = path.with_suffix(".json")
        try:
            if sidecar.exists():
                return json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return None


def default_store() -> AssetStore:
    from .config import load_settings

    return AssetStore(load_settings().image_dir)


def describe_root(store: AssetStore) -> str:
    return os.fspath(store.root) if store.root else "deshabilitado"
