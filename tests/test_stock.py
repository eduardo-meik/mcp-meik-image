"""Unsplash client: parsing, error mapping, download tracking and attribution."""

from __future__ import annotations

import httpx
import pytest

from meik_image.stock import StockError, UnsplashClient

SEARCH_PAYLOAD = {
    "results": [
        {
            "id": "abc123",
            "description": "Team working in a bright office",
            "alt_description": "people at desks",
            "width": 4000,
            "height": 2667,
            "color": "#3a3a3a",
            "user": {"name": "Jane Doe", "links": {"html": "https://unsplash.com/@jane"}},
            "links": {
                "html": "https://unsplash.com/photos/abc123",
                "download_location": "https://api.unsplash.com/photos/abc123/download",
            },
            "urls": {"regular": "https://images.unsplash.com/abc123.jpg", "small": "https://images.unsplash.com/abc123-s.jpg"},
        }
    ]
}


class FakeResponse:
    def __init__(self, status_code: int = 200, payload: dict | None = None, content: bytes = b"") -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.content = content
        self.text = ""

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)  # type: ignore[arg-type]


def _install_client(monkeypatch: pytest.MonkeyPatch, handler) -> list[str]:
    calls: list[str] = []

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            self._headers = kwargs.get("headers") or {}

        def __enter__(self):
            return self

        def __exit__(self, *args) -> bool:
            return False

        def get(self, url, **kwargs):
            calls.append(url)
            return handler(url, kwargs, self._headers)

    monkeypatch.setattr(httpx, "Client", FakeClient)
    return calls


def test_search_returns_photos_with_attribution(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_headers: list[dict] = []

    def handler(url, kwargs, headers):
        seen_headers.append(headers)
        return FakeResponse(200, SEARCH_PAYLOAD)

    _install_client(monkeypatch, handler)
    photos = UnsplashClient("KEY").search("office", count=3)

    assert len(photos) == 1
    photo = photos[0]
    assert photo.id == "abc123"
    assert photo.photographer == "Jane Doe"
    assert photo.attribution["credit_text"] == "Foto: Jane Doe / Unsplash"
    assert seen_headers[0]["Authorization"] == "Client-ID KEY"


def test_missing_key_is_explained() -> None:
    client = UnsplashClient(None)

    assert client.configured is False
    with pytest.raises(StockError, match="UNSPLASH_ACCESS_KEY"):
        client.search("office")


def test_rejected_key_is_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_client(monkeypatch, lambda url, kwargs, headers: FakeResponse(401))

    with pytest.raises(StockError, match="401"):
        UnsplashClient("BAD").search("office")


def test_fetch_downloads_and_pings_the_download_location(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(url, kwargs, headers):
        if "images.unsplash.com" in url:
            return FakeResponse(200, {}, b"JPEGDATA")
        if "search/photos" in url:
            return FakeResponse(200, SEARCH_PAYLOAD)
        return FakeResponse(200, {"ok": True})

    calls = _install_client(monkeypatch, handler)
    client = UnsplashClient("KEY")
    photo = client.search("office")[0]

    data = client.fetch(photo)

    assert data == b"JPEGDATA"
    assert any("images.unsplash.com" in call for call in calls)
    assert any("download" in call for call in calls)
