# Publicación y diagnóstico

Con el media server configurado, **cada generación se sube sola** (`output.publish` viene en
`true`) y el manifiesto devuelve `public_url`, `remote_path` y `published_via`. Los archivos van a
`REMOTE_DIR[/YYYY-MM-DD]/slug-hora-id.ext`.

```ini
MEIK_MEDIA_MODE=sftp            # sftp | cpanel | ftp | ftps | off
MEIK_MEDIA_HOST=sftp.meiklabs.com
MEIK_MEDIA_PORT=22
MEIK_MEDIA_USER=usuario_cpanel
MEIK_MEDIA_PASSWORD=clave       # o MEIK_MEDIA_KEY_PATH (+ MEIK_MEDIA_KEY_PASSPHRASE)
MEIK_MEDIA_REMOTE_DIR=/home2/usuario/public_html/assets/blog/
MEIK_MEDIA_BASE_URL=https://static.meiklabs.com/assets/blog
MEIK_MEDIA_SUBDIR_BY_DATE=true
```

También se aceptan los alias `SFTP_HOST`, `SFTP_PORT`, `SFTP_USER`, `SFTP_PASS`, `SSH_PASSWORD`,
`REMOTE_DIR`, `BASE_URL`, `CPANEL_URL` y `CPANEL_API_TOKEN`.

## Transportes

| Modo | Requiere | Cuándo |
| --- | --- | --- |
| `sftp` | SSH habilitado + clave autorizada o contraseña | el más rápido y estable |
| `cpanel` | `MEIK_MEDIA_CPANEL_TOKEN` (cPanel → Security → Manage API Tokens) | SSH/FTP bloqueados |
| `ftp` / `ftps` | contraseña (no aceptan clave) | último recurso; `ftps` añade TLS explícito |

```ini
MEIK_MEDIA_MODE=cpanel
MEIK_MEDIA_CPANEL_TOKEN=tu-token
MEIK_MEDIA_CPANEL_URL=https://cpanel.meiklabs.com:2083   # opcional
MEIK_MEDIA_CPANEL_VERIFY_TLS=false                       # muchos cPanel usan certificado propio
```

El token necesita al menos `Fileman::upload_files` y `Fileman::list_files`; borrar archivos exige
`delete_files`.

## La URL debe estar servida por el mismo hosting

Subir el archivo no basta: la URL pública funciona solo si el docroot del hostname es la carpeta de
destino. Caso real de Meik Labs:

- `meiklabs.com` resuelve a Firebase Hosting → `/assets/blog/...` devuelve el HTML del SPA.
- `static.meiklabs.com` resuelve a Bluehost con docroot `public_html/website_71e15d19` → **sí**
  sirve los archivos.

Configuración verificada: `MEIK_MEDIA_REMOTE_DIR=/home2/meiklabs/public_html/website_71e15d19/assets/blog/`
y `MEIK_MEDIA_BASE_URL=https://static.meiklabs.com/assets/blog`.

## Flujo de trabajo

1. Antes de generar, `media_server_status` si hay dudas de credenciales: devuelve modo, host,
   carpeta remota, URL base y la causa exacta del fallo.
2. Genera normal. Si la subida falla, la imagen se entrega igual y el manifiesto trae
   `publish_error`: no hace falta regenerar (y volver a pagar).
3. Reintenta con `publish_asset(asset_id, output=…)`, que fuerza la publicación aunque
   `publish=false` y permite otro tamaño o formato.
4. `publish_asset` y `show_saved_image` requieren `asset_id`, así que solo funcionan si el servidor
   corre en local con `MEIK_IMAGE_DIR` distinto de `off`.

## Síntomas y causa

| Síntoma | Causa / solución |
| --- | --- |
| `OPENROUTER_API_KEY inválida o revocada (401)` | key mal copiada, truncada o revocada |
| `La cuenta de OpenRouter no tiene saldo suficiente (402)` | usa la variante `:free` o agrega créditos |
| `Límite de peticiones alcanzado (429)` | el servidor reintenta con backoff: baja `n` o espacia llamadas |
| Letras o logos basura | no uses `allow_text`; el guardrail se desactiva con ese flag |
| El cliente dice que la respuesta es demasiado grande | baja `MEIK_INLINE_MAX_CHARS` (p. ej. 80000) |
| `No encontré el asset …` | almacenamiento local en `off` o el asset vive en otro despliegue |
| `El servidor rechazó el usuario/clave SFTP` | clave incorrecta o SSH deshabilitado → `MEIK_MEDIA_MODE=ftp` |
| `El servidor cortó el handshake SSH` | SSH bloqueado, puerto equivocado o bloqueo por intentos |
| Bloqueo tras varios intentos | cPanel → cPHulk Brute Force Protection → borra tu IP, o usa `MEIK_MEDIA_MODE=cpanel` |
| `publish_error` pero la imagen llega | comportamiento normal: reintenta con `publish_asset` |
| Unsplash responde 401/403 | falta `UNSPLASH_ACCESS_KEY` o la cuota horaria se agotó |

## Unsplash

`search_stock_photos` y `publish_stock_photo` requieren `UNSPLASH_ACCESS_KEY`. La segunda descarga,
recorta al tamaño pedido, optimiza, publica y devuelve `attribution` con `credit_text`
(`Foto: Autor / Unsplash`) más los enlaces: **cítala** en el pie o en el `alt`. Licencia: uso
comercial gratis sin atribución legal obligatoria, pero prohibido recompilar las fotos como servicio
o venderlas sin modificar.
