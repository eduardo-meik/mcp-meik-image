"""Media server publishing: path building, URL joins and failure diagnostics."""

from __future__ import annotations

from datetime import datetime

import paramiko
import pytest

from meik_image.config import MediaConfig, load_settings
from meik_image.media import MediaError, MediaPublisher, build_remote_path


def _cfg(**overrides) -> MediaConfig:
    base = dict(
        mode="sftp",
        host="sftp.example.com",
        port=22,
        user="meiklabs",
        password="secret",
        remote_dir="/home2/meiklabs/public_html/assets/blog/",
        base_url="https://meiklabs.com/assets/blog",
        subdir_by_date=True,
    )
    base.update(overrides)
    return MediaConfig(**base)


def test_remote_path_and_url_group_by_day() -> None:
    cfg = _cfg()
    remote, relative = build_remote_path(cfg, "hero-abc123.webp", when=datetime(2026, 11, 15, 10, 30))

    assert remote == "/home2/meiklabs/public_html/assets/blog/2026-11-15/hero-abc123.webp"
    assert relative == "2026-11-15/hero-abc123.webp"


def test_remote_path_without_day_folder() -> None:
    cfg = _cfg(subdir_by_date=False)
    remote, relative = build_remote_path(cfg, "hero.webp", when=datetime(2026, 11, 15))

    assert remote == "/home2/meiklabs/public_html/assets/blog/hero.webp"
    assert relative == "hero.webp"


def test_publish_builds_public_url(monkeypatch: pytest.MonkeyPatch) -> None:
    publisher = MediaPublisher(_cfg())
    uploaded: list[tuple[str, str, int]] = []

    def fake_put(self, folder: str, remote_path: str, data: bytes) -> None:
        uploaded.append((folder, remote_path, len(data)))

    monkeypatch.setattr(MediaPublisher, "_put_sftp", fake_put)
    published = publisher.publish(b"binary", "hero.webp", when=datetime(2026, 11, 15, 9, 0))

    assert published.url == "https://meiklabs.com/assets/blog/2026-11-15/hero.webp"
    assert published.remote_path == "/home2/meiklabs/public_html/assets/blog/2026-11-15/hero.webp"
    assert published.transport == "sftp"
    assert uploaded == [("/home2/meiklabs/public_html/assets/blog/2026-11-15", published.remote_path, 6)]


def test_publish_without_configuration_explains_what_is_missing() -> None:
    publisher = MediaPublisher(_cfg(host=None))

    assert publisher.configured is False
    with pytest.raises(MediaError, match="MEIK_MEDIA_HOST"):
        publisher.publish(b"binary", "x.webp")


def test_auth_failure_is_reported_with_a_fix_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    class RejectingTransport:
        def __init__(self, *args, **kwargs) -> None:
            self.banner_timeout = 0

        def connect(self, **kwargs):
            raise paramiko.AuthenticationException("Authentication failed.")

    monkeypatch.setattr(paramiko, "Transport", RejectingTransport)
    status = MediaPublisher(_cfg()).status()

    assert status.configured is True
    assert status.ok is False
    assert "rechazó el usuario/clave" in status.detail
    assert "SSH Access" in status.detail or "ftp" in status.detail


def test_unreachable_host_is_reported_without_raising(monkeypatch: pytest.MonkeyPatch) -> None:
    class UnreachableTransport:
        def __init__(self, *args, **kwargs) -> None:
            self.banner_timeout = 0

        def connect(self, **kwargs):
            raise OSError("timed out")

    monkeypatch.setattr(paramiko, "Transport", UnreachableTransport)
    status = MediaPublisher(_cfg()).status()

    assert status.ok is False
    assert "No se pudo abrir SFTP" in status.detail


def test_banner_drop_is_reported_with_a_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    class DroppingTransport:
        def __init__(self, *args, **kwargs) -> None:
            self.banner_timeout = 0

        def connect(self, **kwargs):
            raise paramiko.SSHException("Error reading SSH protocol banner")

    monkeypatch.setattr(paramiko, "Transport", DroppingTransport)
    status = MediaPublisher(_cfg()).status()

    assert status.ok is False
    assert "handshake SSH" in status.detail
    assert "cPHulk" in status.detail


def test_settings_read_legacy_sftp_variable_names(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in {
        "SFTP_HOST": "sftp.legacy.com",
        "SFTP_PORT": "2222",
        "SFTP_USER": "legacyuser",
        "SFTP_PASS": "legacypass",
        "REMOTE_DIR": "/home/legacy/public_html/assets",
        "BASE_URL": "https://legacy.com/assets",
    }.items():
        monkeypatch.setenv(name, value)
    for name in ("MEIK_MEDIA_MODE", "MEIK_MEDIA_HOST", "MEIK_MEDIA_USER", "MEIK_MEDIA_PASSWORD",
                 "MEIK_MEDIA_REMOTE_DIR", "MEIK_MEDIA_BASE_URL", "MEIK_MEDIA_PORT"):
        monkeypatch.delenv(name, raising=False)

    media = load_settings().media

    assert media.mode == "sftp"
    assert media.host == "sftp.legacy.com"
    assert media.port == 2222
    assert media.configured is True


def test_sftp_private_key_path_alias_is_recognised(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEIK_MEDIA_HOST", "sftp.legacy.com")
    monkeypatch.setenv("MEIK_MEDIA_USER", "meiklabs")
    monkeypatch.setenv("MEIK_MEDIA_REMOTE_DIR", "/home/meiklabs/public_html/assets")
    monkeypatch.setenv("MEIK_MEDIA_BASE_URL", "https://legacy.com/assets")
    monkeypatch.setenv("SFTP_PRIVATE_KEY_PATH", r"C:\keys\mcp_blog_key")
    monkeypatch.delenv("MEIK_MEDIA_KEY_PATH", raising=False)
    monkeypatch.delenv("SFTP_KEY_PATH", raising=False)
    monkeypatch.delenv("MEIK_MEDIA_PASSWORD", raising=False)
    monkeypatch.delenv("SFTP_PASS", raising=False)
    monkeypatch.delenv("SSH_PASSWORD", raising=False)

    media = load_settings().media

    assert media.key_path == r"C:\keys\mcp_blog_key"
    assert media.configured is True


def test_media_mode_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SFTP_HOST", "sftp.legacy.com")
    monkeypatch.setenv("MEIK_MEDIA_MODE", "off")
    assert load_settings().media.configured is False


def test_key_based_auth_is_used_when_a_private_key_is_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    class CapturingTransport:
        def __init__(self, *args, **kwargs) -> None:
            self.banner_timeout = 0

        def connect(self, **kwargs):
            captured.update(kwargs)

        def close(self) -> None:
            pass

    monkeypatch.setattr(paramiko, "Transport", CapturingTransport)
    monkeypatch.setattr(paramiko.PKey, "from_path", staticmethod(lambda path, passphrase=None: "PKEY"))
    publisher = MediaPublisher(_cfg(password=None, key_path="C:/keys/mcp_blog_key"))
    publisher._connect_sftp()

    assert captured["pkey"] == "PKEY"
    assert "password" not in captured


def test_key_only_configuration_counts_as_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MEIK_MEDIA_PASSWORD", raising=False)
    monkeypatch.delenv("SFTP_PASS", raising=False)
    monkeypatch.setenv("MEIK_MEDIA_HOST", "sftp.legacy.com")
    monkeypatch.setenv("MEIK_MEDIA_USER", "user")
    monkeypatch.setenv("MEIK_MEDIA_KEY_PATH", "C:/keys/id_ed25519")
    monkeypatch.setenv("MEIK_MEDIA_REMOTE_DIR", "/home/user/public_html/assets")
    monkeypatch.setenv("MEIK_MEDIA_BASE_URL", "https://legacy.com/assets")

    media = load_settings().media

    assert media.configured is True
    assert media.key_path == "C:/keys/id_ed25519"


def test_ftp_without_password_explains_the_limitation() -> None:
    publisher = MediaPublisher(_cfg(mode="ftp", password=None, key_path="C:/keys/id_ed25519"))

    with pytest.raises(MediaError, match="no admite autenticación por clave"):
        publisher.publish(b"binary", "x.jpg")


def test_cpanel_upload_posts_multipart_and_builds_url(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    captured: dict = {}

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {"status": 1, "data": {"uploaded": True}}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(httpx, "post", fake_post)
    publisher = MediaPublisher(
        _cfg(mode="cpanel", password=None, cpanel_token="TOKEN123", cpanel_url="https://cpanel.meiklabs.com:2083")
    )

    published = publisher.publish(b"binary", "hero.webp", when=datetime(2026, 11, 15, 8, 0))

    assert captured["url"] == "https://cpanel.meiklabs.com:2083/execute/Fileman/upload_files"
    assert captured["headers"]["Authorization"] == "cpanel meiklabs:TOKEN123"
    assert captured["data"] == {"dir": "/home2/meiklabs/public_html/assets/blog/2026-11-15"}
    assert captured["files"]["file-1"][0] == "hero.webp"
    assert published.url == "https://meiklabs.com/assets/blog/2026-11-15/hero.webp"
    assert published.transport == "cpanel"


def test_cpanel_rejected_token_is_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    class Rejected:
        status_code = 403
        text = "Forbidden"

        def json(self):
            return {}

    monkeypatch.setattr(httpx, "post", lambda url, **kw: Rejected())
    publisher = MediaPublisher(_cfg(mode="cpanel", password=None, cpanel_token="BAD"))

    with pytest.raises(MediaError, match="token"):
        publisher.publish(b"binary", "hero.webp")


def test_cpanel_mode_without_token_is_not_configured() -> None:
    assert MediaPublisher(_cfg(mode="cpanel", password=None, cpanel_token=None)).configured is False


def test_cpanel_token_alias_is_recognised(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEIK_MEDIA_MODE", "cpanel")
    monkeypatch.setenv("MEIK_MEDIA_HOST", "sftp.legacy.com")
    monkeypatch.setenv("MEIK_MEDIA_USER", "meiklabs")
    monkeypatch.setenv("MEIK_MEDIA_REMOTE_DIR", "/home/meiklabs/public_html/assets")
    monkeypatch.setenv("MEIK_MEDIA_BASE_URL", "https://meiklabs.com/assets")
    monkeypatch.setenv("CPANEL_API_TOKEN", "TOKEN-FROM-DOTENV")
    monkeypatch.delenv("MEIK_MEDIA_CPANEL_TOKEN", raising=False)
    monkeypatch.delenv("CPANEL_TOKEN", raising=False)

    media = load_settings().media

    assert media.cpanel_token == "TOKEN-FROM-DOTENV"
    assert media.configured is True


def test_cpanel_mode_derives_the_host_from_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Horizon deployments may only carry the cPanel token, not the SFTP host."""
    for name in ("MEIK_MEDIA_HOST", "SFTP_HOST", "MEIK_MEDIA_KEY_PATH", "SFTP_KEY_PATH",
                 "SFTP_PRIVATE_KEY_PATH", "MEIK_MEDIA_PASSWORD", "SFTP_PASS", "SSH_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("MEIK_MEDIA_MODE", "cpanel")
    monkeypatch.setenv("MEIK_MEDIA_USER", "meiklabs")
    monkeypatch.setenv("MEIK_MEDIA_CPANEL_TOKEN", "TOKEN")
    monkeypatch.setenv("MEIK_MEDIA_REMOTE_DIR", "/home2/meiklabs/public_html/website_x/img/blog/")
    monkeypatch.setenv("MEIK_MEDIA_BASE_URL", "https://static.meiklabs.com/img/blog")

    media = load_settings().media

    assert media.cpanel_host == "static.meiklabs.com"
    assert media.missing == []
    assert media.configured is True


def test_missing_lists_only_what_the_active_mode_needs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEIK_MEDIA_MODE", "cpanel")
    monkeypatch.setenv("MEIK_MEDIA_CPANEL_TOKEN", "TOKEN")
    monkeypatch.setenv("MEIK_MEDIA_REMOTE_DIR", "/home/meiklabs/public_html/img/blog/")
    monkeypatch.setenv("MEIK_MEDIA_BASE_URL", "https://static.meiklabs.com/img/blog")
    for name in ("MEIK_MEDIA_USER", "SFTP_USER", "MEIK_MEDIA_HOST", "SFTP_HOST"):
        monkeypatch.delenv(name, raising=False)

    media = load_settings().media

    assert media.missing == ["MEIK_MEDIA_USER"]
    assert media.configured is False


def test_publish_error_names_the_missing_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEIK_MEDIA_MODE", "cpanel")
    monkeypatch.delenv("MEIK_MEDIA_CPANEL_TOKEN", raising=False)
    monkeypatch.delenv("CPANEL_API_TOKEN", raising=False)
    monkeypatch.delenv("CPANEL_TOKEN", raising=False)

    publisher = MediaPublisher(load_settings().media)

    with pytest.raises(MediaError) as excinfo:
        publisher.publish(b"binary", "x.webp")
    assert "MEIK_MEDIA_CPANEL_TOKEN" in str(excinfo.value)
    assert "modo actual: cpanel" in str(excinfo.value)
