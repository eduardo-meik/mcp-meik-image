"""Publish generated images to the Meik Labs media server (cPanel / shared hosting).

SFTP is the default transport; plain FTP and explicit FTPS are supported for hosts
where SSH is disabled. Files land in ``remote_dir[/YYYY-MM-DD]/name.ext`` and are
returned as public URLs built from ``base_url``.
"""

from __future__ import annotations

import io
import logging
import posixpath
import socket
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .config import MediaConfig

logger = logging.getLogger("meik_image.media")


class MediaError(RuntimeError):
    """Publishing failure with a message meant for the calling model."""


@dataclass(frozen=True)
class PublishedFile:
    url: str
    remote_path: str
    size_bytes: int
    transport: str


@dataclass(frozen=True)
class MediaStatus:
    configured: bool
    mode: str
    ok: bool
    detail: str
    host: str | None = None
    remote_dir: str | None = None
    base_url: str | None = None
    transport: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def _join_url(base_url: str, relative: str) -> str:
    return f"{base_url.rstrip('/')}/{relative.lstrip('/')}"


def build_remote_path(cfg: MediaConfig, filename: str, *, when: datetime | None = None) -> tuple[str, str]:
    """Return (absolute remote path, relative path under base_url)."""
    stamp = (when or datetime.now()).strftime("%Y-%m-%d")
    base = (cfg.remote_dir or "").rstrip("/")
    folder = f"{base}/{stamp}" if cfg.subdir_by_date else base
    return f"{folder}/{filename}", f"{stamp}/{filename}" if cfg.subdir_by_date else filename


class MediaPublisher:
    def __init__(self, cfg: MediaConfig) -> None:
        self._cfg = cfg

    @property
    def configured(self) -> bool:
        return self._cfg.configured

    # ------------------------------------------------------------------ public
    def publish(self, data: bytes, filename: str, *, when: datetime | None = None) -> PublishedFile:
        if not self.configured:
            raise MediaError(
                "El media server no está configurado. Define MEIK_MEDIA_HOST, MEIK_MEDIA_USER, "
                "MEIK_MEDIA_PASSWORD, MEIK_MEDIA_REMOTE_DIR y MEIK_MEDIA_BASE_URL "
                "(o las variables SFTP_HOST / SFTP_USER / SFTP_PASS / REMOTE_DIR / BASE_URL)."
            )
        remote_path, relative = build_remote_path(self._cfg, filename, when=when)
        folder = posixpath.dirname(remote_path)

        mode = self._cfg.mode
        if mode == "sftp":
            self._put_sftp(folder, remote_path, data)
        elif mode == "cpanel":
            self._put_cpanel(folder, remote_path, data)
        elif mode in {"ftp", "ftps"}:
            if self._cfg.key_path and not self._cfg.password:
                raise MediaError(
                    f"{mode.upper()} no admite autenticación por clave: define MEIK_MEDIA_PASSWORD "
                    "o usa MEIK_MEDIA_MODE=sftp."
                )
            self._put_ftp(folder, remote_path, data)
        else:
            raise MediaError(f"Modo de publicación no soportado: {mode!r}. Usa sftp, cpanel, ftp o ftps.")

        return PublishedFile(
            url=_join_url(self._cfg.base_url or "", relative),
            remote_path=remote_path,
            size_bytes=len(data),
            transport=mode,
        )

    def status(self) -> MediaStatus:
        if not self.configured:
            return MediaStatus(
                configured=False,
                mode=self._cfg.mode,
                ok=False,
                detail=(
                    "Publicación deshabilitada: faltan datos de conexión. "
                    "Revisa MEIK_MEDIA_HOST/USER/PASSWORD/REMOTE_DIR/BASE_URL."
                ),
                host=self._cfg.host,
                remote_dir=self._cfg.remote_dir,
                base_url=self._cfg.base_url,
            )
        try:
            if self._cfg.mode == "cpanel":
                return self._cpanel_status()
            if self._cfg.mode == "sftp":
                transport = self._connect_sftp()
                sftp = transport.open_sftp_client()
                try:
                    cwd = sftp.normalize(".")
                    exists = True
                    try:
                        sftp.stat(self._cfg.remote_dir)
                    except IOError:
                        exists = False
                finally:
                    sftp.close()
                    transport.close()
                return MediaStatus(
                    configured=True,
                    mode=self._cfg.mode,
                    ok=True,
                    detail=(
                        f"SFTP OK como {self._cfg.user}. Home={cwd}. "
                        f"REMOTE_DIR {'existe' if exists else 'no existe (se creará al publicar)'}."
                    ),
                    host=self._cfg.host,
                    remote_dir=self._cfg.remote_dir,
                    base_url=self._cfg.base_url,
                    transport="sftp",
                    extra={"home": cwd, "remote_dir_exists": exists},
                )
            conn = self._connect_ftp()
            try:
                cwd = conn.pwd()
                listing = []
                try:
                    listing = conn.nlst(self._cfg.remote_dir)[:5]
                except Exception:  # noqa: BLE001 - directory may not exist yet
                    listing = []
            finally:
                try:
                    conn.quit()
                except Exception:  # noqa: BLE001
                    conn.close()
            return MediaStatus(
                configured=True,
                mode=self._cfg.mode,
                ok=True,
                detail=f"FTP OK como {self._cfg.user}. Home={cwd}.",
                host=self._cfg.host,
                remote_dir=self._cfg.remote_dir,
                base_url=self._cfg.base_url,
                transport=self._cfg.mode,
                extra={"home": cwd, "sample_entries": listing},
            )
        except MediaError as exc:
            return MediaStatus(
                configured=True,
                mode=self._cfg.mode,
                ok=False,
                detail=str(exc),
                host=self._cfg.host,
                remote_dir=self._cfg.remote_dir,
                base_url=self._cfg.base_url,
            )
        except Exception as exc:  # noqa: BLE001 - status must never raise
            return MediaStatus(
                configured=True,
                mode=self._cfg.mode,
                ok=False,
                detail=f"{type(exc).__name__}: {exc}",
                host=self._cfg.host,
                remote_dir=self._cfg.remote_dir,
                base_url=self._cfg.base_url,
            )

    # ------------------------------------------------------------------ sftp
    def _load_pkey(self):
        import paramiko

        path = self._cfg.key_path
        if not path:
            return None
        try:
            return paramiko.PKey.from_path(path, passphrase=self._cfg.key_passphrase)
        except AttributeError:  # paramiko < 3.2
            for key_class in (paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey):
                try:
                    return key_class.from_private_key_file(path, password=self._cfg.key_passphrase)
                except Exception:  # noqa: BLE001, PERF203 - try the next key type
                    continue
            raise MediaError(f"No se pudo leer la clave privada en {path}.")
        except Exception as exc:  # noqa: BLE001
            raise MediaError(f"No se pudo leer la clave privada en {path}: {exc}") from exc

    # ----------------------------------------------------------------- cpanel
    def _cpanel_base(self) -> str:
        base = self._cfg.cpanel_url or f"https://{self._cfg.host}:2083"
        return base.rstrip("/")

    def _cpanel_headers(self) -> dict[str, str]:
        return {"Authorization": f"cpanel {self._cfg.user}:{self._cfg.cpanel_token}"}

    def _put_cpanel(self, folder: str, remote_path: str, data: bytes) -> None:
        import httpx

        if not self._cfg.cpanel_token:
            raise MediaError(
                "Falta MEIK_MEDIA_CPANEL_TOKEN (cPanel → Security → Manage API Tokens)."
            )
        url = f"{self._cpanel_base()}/execute/Fileman/upload_files"
        try:
            response = httpx.post(
                url,
                headers=self._cpanel_headers(),
                data={"dir": folder},
                files={"file-1": (posixpath.basename(remote_path), data, "application/octet-stream")},
                timeout=60,
                verify=self._cfg.cpanel_verify_tls,
            )
        except httpx.HTTPError as exc:
            raise MediaError(f"No se pudo llamar a la API de cPanel en {url}: {exc}") from exc

        if response.status_code in {401, 403}:
            raise MediaError(
                "cPanel rechazó el token (401/403). Revisa MEIK_MEDIA_CPANEL_TOKEN y que el token "
                "tenga permisos de Fileman."
            )
        if response.status_code >= 400:
            raise MediaError(f"cPanel respondió {response.status_code}: {response.text[:200]}")
        try:
            body = response.json()
        except ValueError:
            return
        if isinstance(body, dict) and body.get("status") == 0:
            errors = body.get("errors") or body.get("messages") or body.get("data")
            raise MediaError(f"cPanel rechazó la subida: {errors}")

    def _cpanel_status(self) -> MediaStatus:
        import httpx

        url = f"{self._cpanel_base()}/execute/Fileman/list_files"
        try:
            response = httpx.get(
                url,
                headers=self._cpanel_headers(),
                params={"dir": self._cfg.remote_dir, "types": "file|dir"},
                timeout=30,
                verify=self._cfg.cpanel_verify_tls,
            )
        except httpx.HTTPError as exc:
            return MediaStatus(
                configured=True,
                mode="cpanel",
                ok=False,
                detail=f"No se pudo contactar la API de cPanel en {url}: {exc}",
                host=self._cfg.host,
                remote_dir=self._cfg.remote_dir,
                base_url=self._cfg.base_url,
            )
        if response.status_code in {401, 403}:
            return MediaStatus(
                configured=True,
                mode="cpanel",
                ok=False,
                detail="Token de cPanel rechazado (401/403). Revisa MEIK_MEDIA_CPANEL_TOKEN.",
                host=self._cfg.host,
                remote_dir=self._cfg.remote_dir,
                base_url=self._cfg.base_url,
            )
        ok = response.status_code == 200
        entries: list[str] = []
        try:
            body = response.json()
            for item in (body.get("data") or [])[:5]:
                if isinstance(item, dict):
                    entries.append(item.get("file") or item.get("path") or "?")
        except ValueError:
            pass
        return MediaStatus(
            configured=True,
            mode="cpanel",
            ok=ok,
            detail=(
                f"API de cPanel respondió {response.status_code} para {self._cfg.remote_dir}."
                if ok
                else f"API de cPanel respondió {response.status_code}."
            ),
            host=self._cfg.host,
            remote_dir=self._cfg.remote_dir,
            base_url=self._cfg.base_url,
            transport="cpanel",
            extra={"sample_entries": entries},
        )

    def _connect_sftp(self):
        import paramiko

        try:
            transport = paramiko.Transport((self._cfg.host, self._cfg.port or 22))
            transport.banner_timeout = 30
            pkey = self._load_pkey()
            if pkey is not None:
                transport.connect(username=self._cfg.user, pkey=pkey)
            else:
                transport.connect(username=self._cfg.user, password=self._cfg.password)
            return transport
        except paramiko.AuthenticationException as exc:
            raise MediaError(
                "El servidor rechazó el usuario/clave SFTP. Verifica MEIK_MEDIA_USER y "
                "MEIK_MEDIA_PASSWORD, o configura MEIK_MEDIA_KEY_PATH con tu clave privada "
                "(en cPanel: 'SSH Access' debe estar habilitado; si no lo está, "
                "usa MEIK_MEDIA_MODE=ftp o ftps)."
            ) from exc
        except paramiko.SSHException as exc:
            raise MediaError(
                f"El servidor cortó el handshake SSH ({str(exc)[:80]}). Causas típicas: acceso SSH "
                "deshabilitado para la cuenta, host/puerto incorrecto, o bloqueo anti-fuerza-bruta "
                "(cPanel → cPHulk Brute Force Protection: borra el registro de tu IP). "
                "También puedes usar MEIK_MEDIA_MODE=ftp/ftps."
            ) from exc
        except (socket.timeout, OSError) as exc:
            raise MediaError(
                f"No se pudo abrir SFTP contra {self._cfg.host}:{self._cfg.port or 22}: {exc}"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise MediaError(f"Error SFTP ({type(exc).__name__}): {exc}") from exc

    def _put_sftp(self, folder: str, remote_path: str, data: bytes) -> None:
        transport = self._connect_sftp()
        try:
            sftp = transport.open_sftp_client()
            try:
                self._sftp_makedirs(sftp, folder)
                sftp.putfo(io.BytesIO(data), remote_path)
            finally:
                sftp.close()
        except MediaError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise MediaError(f"No se pudo subir por SFTP a {remote_path}: {exc}") from exc
        finally:
            transport.close()

    @staticmethod
    def _sftp_makedirs(sftp, path: str) -> None:
        current = ""
        for part in path.strip("/").split("/"):
            current = f"{current}/{part}"
            try:
                sftp.stat(current)
            except IOError:
                try:
                    sftp.mkdir(current)
                except IOError:
                    pass

    # ------------------------------------------------------------------- ftp
    def _connect_ftp(self):
        from ftplib import FTP, FTP_TLS, error_perm

        timeout = 30
        try:
            if self._cfg.mode == "ftps":
                conn = FTP_TLS(timeout=timeout)
                conn.connect(self._cfg.host, self._cfg.port or 21)
                conn.auth()
                conn.prot_p()
            else:
                conn = FTP(timeout=timeout)
                conn.connect(self._cfg.host, self._cfg.port or 21)
            conn.login(self._cfg.user, self._cfg.password)
            return conn
        except error_perm as exc:
            raise MediaError(
                f"El servidor rechazó el usuario/clave FTP ({exc}). Revisa MEIK_MEDIA_USER y "
                "MEIK_MEDIA_PASSWORD."
            ) from exc
        except (socket.timeout, OSError) as exc:
            raise MediaError(
                f"No se pudo abrir FTP contra {self._cfg.host}:{self._cfg.port or 21}: {exc}"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise MediaError(f"Error FTP ({type(exc).__name__}): {exc}") from exc

    def _put_ftp(self, folder: str, remote_path: str, data: bytes) -> None:
        conn = self._connect_ftp()
        try:
            for part in folder.strip("/").split("/"):
                if not part:
                    continue
                try:
                    conn.mkd(part)
                except Exception:  # noqa: BLE001 - already exists, or cwd-relative
                    pass
                try:
                    conn.cwd(part)
                except Exception:  # noqa: BLE001
                    break
            conn.storbinary("STOR " + posixpath.basename(remote_path), io.BytesIO(data))
        except MediaError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise MediaError(f"No se pudo subir por FTP a {remote_path}: {exc}") from exc
        finally:
            try:
                conn.quit()
            except Exception:  # noqa: BLE001
                conn.close()


def publisher_from_settings() -> MediaPublisher:
    from .config import load_settings

    return MediaPublisher(load_settings().media)
