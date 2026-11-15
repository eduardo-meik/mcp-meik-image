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
    assert "SSH Access" in status.detail


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


def test_media_mode_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SFTP_HOST", "sftp.legacy.com")
    monkeypatch.setenv("MEIK_MEDIA_MODE", "off")

    assert load_settings().media.configured is False
