"""Asset storage, path safety and MCP tool registration."""

from __future__ import annotations

import asyncio
import json

import pytest

from meik_image.storage import AssetStore, slugify


def test_save_writes_file_and_sidecar(tmp_path, webp_bytes: bytes) -> None:
    store = AssetStore(tmp_path / "assets")

    asset = store.save(webp_bytes, "image/webp", slug="Hero de Blog", metadata={"prompt": "algo"})

    assert asset is not None
    assert asset.path.exists()
    assert asset.path.suffix == ".webp"
    assert asset.path.parent.name  # date folder
    sidecar = json.loads(asset.path.with_suffix(".json").read_text(encoding="utf-8"))
    assert sidecar["prompt"] == "algo"
    assert sidecar["media_type"] == "image/webp"


def test_disabled_store_returns_none(webp_bytes: bytes) -> None:
    store = AssetStore(None)

    assert store.enabled is False
    assert store.save(webp_bytes, "image/webp", slug="x", metadata={}) is None
    assert store.list_assets() == []


def test_load_roundtrip_and_traversal_is_blocked(tmp_path, webp_bytes: bytes) -> None:
    store = AssetStore(tmp_path / "assets")
    asset = store.save(webp_bytes, "image/webp", slug="slide portada", metadata={"prompt": "p"})
    assert asset is not None

    loaded = store.load(asset.asset_id)
    assert loaded is not None
    data, media, sidecar = loaded
    assert data == webp_bytes
    assert media == "image/webp"
    assert sidecar["asset_id"] == asset.asset_id

    assert store.load("../../etc/passwd") is None
    assert store.load("does-not-exist") is None


def test_sibling_directory_with_shared_prefix_is_not_reachable(tmp_path, png_bytes: bytes) -> None:
    assets = tmp_path / "assets"
    sibling = tmp_path / "assets-evil"
    sibling.mkdir()
    (sibling / "secret.png").write_bytes(png_bytes)
    store = AssetStore(assets)

    assert store.load("../assets-evil/secret.png") is None


def test_list_assets_filters_by_query(tmp_path, png_bytes: bytes) -> None:
    store = AssetStore(tmp_path / "assets")
    store.save(png_bytes, "image/png", slug="blog hero pagos", metadata={"prompt": "pagos automáticos"})
    store.save(png_bytes, "image/png", slug="slide equipo", metadata={"prompt": "red de nodos"})

    assert len(store.list_assets()) == 2
    hits = store.list_assets(query="pagos")
    assert len(hits) == 1
    assert "pagos" in hits[0]["asset_id"]


def test_slugify_strips_accents_and_symbols() -> None:
    assert slugify("Métricas 2026: +45%") == "metricas-2026-45"
    assert slugify("") == "meik-image"


def test_all_tools_are_registered(isolated_env) -> None:
    from main import mcp

    names = sorted(tool.name for tool in asyncio.run(mcp.list_tools()))
    assert names == [
        "blog_style_guide",
        "brand_kit",
        "generate_blog_figure",
        "generate_blog_hero",
        "generate_deck_background",
        "generate_image",
        "generate_pitch_slide_visual",
        "list_generated_images",
        "media_server_status",
        "publish_asset",
        "publish_stock_photo",
        "search_stock_photos",
        "show_saved_image",
        "size_presets",
    ]


def test_brand_kit_tool_returns_palette_and_slide_types() -> None:
    from main import mcp

    result = asyncio.run(mcp.call_tool("brand_kit", {}))
    text = "".join(getattr(item, "text", "") for item in result.content)
    payload = json.loads(text)

    assert payload["colors"]["primary"] == "#4F00C4"
    assert "brand-dark" in payload["palettes"]
    assert "traction" in payload["slide_types"]


def test_generation_tool_reports_a_missing_key_clearly(monkeypatch, tmp_path) -> None:
    from main import mcp

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("MEIK_IMAGE_DIR", str(tmp_path / "assets"))
    monkeypatch.setattr("meik_image.config.load_dotenv", lambda *a, **k: None)

    with pytest.raises(Exception) as excinfo:
        asyncio.run(mcp.call_tool("generate_blog_hero", {"title": "Prueba"}))

    assert "OPENROUTER_API_KEY" in str(excinfo.value)


def test_health_reports_tools_and_key_state(isolated_env) -> None:
    from main import _health

    health = _health()

    assert health["status"] == "ok"
    assert health["api_key_configured"] is True
    assert health["model"] == "recraft/recraft-v4.1-flash-v2:free"
    assert "generate_blog_hero" in health["tools"]


def test_asgi_app_is_exposed_for_uvicorn_hosts(isolated_env) -> None:
    """FastMCP Gateway/Horizon serves the repo with uvicorn, so an ASGI app must exist."""
    import main

    assert main.app is not None
    paths = [getattr(route, "path", None) for route in main.app.routes]
    assert "/mcp" in paths
    assert "/health" in paths


def test_served_package_reuses_the_same_app(isolated_env) -> None:
    """src/server.py and src/main.py exist because the platform's default entrypoint is src.*."""
    import main
    from src.main import app as from_src_main
    from src.server import app as from_src_server

    assert from_src_server is main.app
    assert from_src_main is main.app


def test_health_route_reports_configuration(isolated_env, monkeypatch) -> None:
    from starlette.testclient import TestClient

    import main

    monkeypatch.setenv("MEIK_MEDIA_MODE", "off")

    with TestClient(main.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["api_key_configured"] is True
    assert body["media_server_configured"] is False


def test_fastmcp_json_points_at_a_loadable_entrypoint(isolated_env) -> None:
    import json
    from pathlib import Path

    config = json.loads(Path("fastmcp.json").read_text(encoding="utf-8"))

    assert config["source"]["path"] == "main.py"
    assert config["source"]["entrypoint"] == "mcp"
    assert config["environment"]["requirements"] == "requirements.txt"
    assert config["deployment"]["transport"] == "http"


def test_naming_mode_slug_produces_a_stable_filename(isolated_env, monkeypatch) -> None:
    import json

    from PIL import Image

    from meik_image.openrouter import GeneratedImage, GenerationResult
    from meik_image.tools import OutputSpec, _deliver

    buffer = __import__("io").BytesIO()
    Image.new("RGB", (1344, 768), (79, 0, 196)).save(buffer, format="WEBP")
    result = GenerationResult(
        images=(GeneratedImage(data=buffer.getvalue(), media_type="image/webp"),),
        model="test",
        aspect_ratio="16:9",
        cost_usd=0.0,
        duration_seconds=0.0,
    )

    monkeypatch.setenv("MEIK_MEDIA_MODE", "off")
    monkeypatch.setenv("MEIK_MEDIA_NAMING", "slug")
    content = _deliver(result, prompt="p", slug="Mi Post Sobre IA", output=OutputSpec(size="blog-hero"), meta={})
    manifest = json.loads(content[-1])
    assert manifest["images"][0]["saved_to"].endswith("mi-post-sobre-ia.webp")

    monkeypatch.setenv("MEIK_MEDIA_NAMING", "unique")
    content = _deliver(result, prompt="p", slug="Mi Post Sobre IA", output=OutputSpec(size="blog-hero"), meta={})
    saved = json.loads(content[-1])["images"][0]["saved_to"]
    assert "mi-post-sobre-ia-" in saved and saved.endswith(".webp")


def test_output_filename_overrides_the_generated_name(isolated_env, monkeypatch) -> None:
    import io
    import json

    from PIL import Image

    from meik_image.openrouter import GeneratedImage, GenerationResult
    from meik_image.tools import OutputSpec, _deliver

    buffer = io.BytesIO()
    Image.new("RGB", (1344, 768), (255, 92, 243)).save(buffer, format="WEBP")
    result = GenerationResult(
        images=(GeneratedImage(data=buffer.getvalue(), media_type="image/webp"),),
        model="test",
        aspect_ratio="16:9",
        cost_usd=0.0,
        duration_seconds=0.0,
    )

    monkeypatch.setenv("MEIK_MEDIA_MODE", "off")
    content = _deliver(
        result,
        prompt="p",
        slug="Titulo Cualquiera",
        output=OutputSpec(size="blog-hero", filename="como-automatizar-sin-morir"),
        meta={},
    )

    saved = json.loads(content[-1])["images"][0]["saved_to"]
    assert saved.endswith("como-automatizar-sin-morir.webp")
