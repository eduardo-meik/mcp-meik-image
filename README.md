# Meik Labs · Imágenes (MCP)

Servidor MCP para generar imágenes de **Meik Labs** —pensado para blogs y pitch decks— usando
`recraft/recraft-v4.1-flash-v2:free` a través de la API de imágenes de OpenRouter.
Cada herramienta devuelve las imágenes **inline** (para verlas en el chat) y guarda el original
a resolución completa cuando el servidor corre en local.

- Entrypoint Horizon / FastMCP Gateway: **`main.py:mcp`**
- Transporte local: **stdio** (`python main.py`) u **HTTP** (`python main.py --http`)
- Coste del modelo `:free` verificado: **$0.00 por imagen** (la variante sin `:free` cuesta $0.007/imagen)

## Herramientas

| Herramienta | Para qué | Salida por defecto |
| --- | --- | --- |
| `brand_kit` | Colores, tipografías, paletas, estilos, formatos y arquetipos disponibles | JSON |
| `generate_image` | Imagen libre desde texto con estilo/paleta de marca | 16:9 |
| `generate_blog_hero` | Cabecera de artículo con espacio reservado para el titular | 16:9 |
| `generate_blog_figure` | Figura interior del artículo, composición centrada | 4:3 |
| `generate_pitch_slide_visual` | Visual por arquetipo de slide (`problem`, `solution`, `traction`, …) | 16:9 |
| `generate_deck_background` | Fondo de slides de baja intensidad para poner texto encima | 16:9 |
| `publish_asset` | Optimiza y sube al media server una imagen ya generada | Imagen + URL |
| `media_server_status` | Diagnostica la conexión SFTP/FTP y la carpeta remota | JSON |
| `list_generated_images` | Lista los assets guardados en local (solo con disco) | JSON |
| `show_saved_image` | Vuelve a mostrar inline un asset guardado | Imagen |

Todas las herramientas de generación aceptan `output` para controlar tamaño, formato, peso y publicación
(ver [Tamaño, formato y peso](#tamaño-formato-y-peso)).

Estilos: `abstract-geometric`, `gradient-mesh`, `quiet-surface`, `isometric-tech`, `flat-vector`,
`line-art`, `editorial-photo`, `data-viz`, `glass-ui`, `topographic`, `collage`, `blueprint`.

Paletas: `brand-dark`, `brand-light`, `brand-mono`, `neutral`, `warm`, `cool`, `none`.

Arquetipos de slide: `title`, `problem`, `solution`, `product`, `market`, `traction`, `competition`,
`team`, `roadmap`, `business-model`, `ask`, `quote`.

## Instalación local

```powershell
cd C:\Meik_Apps\Tools\mcp_image
uv venv .venv --python 3.13
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
Copy-Item .env.example .env   # y pon tu OPENROUTER_API_KEY
.venv\Scripts\python.exe main.py --check
```

`--check` imprime el estado (clave configurada, modelo, carpeta de salida, herramientas cargadas)
y devuelve código 0 solo si hay `OPENROUTER_API_KEY`.

Ejecutar:

```powershell
.venv\Scripts\python.exe main.py            # stdio (Claude Desktop / Claude Code)
.venv\Scripts\python.exe main.py --http     # HTTP en 0.0.0.0:8000 (endpoint /mcp)
```

## Conectar a Claude Desktop (stdio, local)

```powershell
.venv\Scripts\fastmcp.exe install claude-desktop main.py:mcp --name meik-images --with-requirements requirements.txt
```

La API key **no** se escribe en el config: `main.py` carga `.env` del proyecto con `python-dotenv`.
Si prefieres hacerlo a mano, añade a `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "meik-images": {
      "command": "C:\\Meik_Apps\\Tools\\mcp_image\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Meik_Apps\\Tools\\mcp_image\\main.py"],
      "env": { "MEIK_IMAGE_DIR": "C:\\Meik_Apps\\Tools\\mcp_image\\output" }
    }
  }
}
```

## Conectar a Claude Cowork / claude.ai (remoto, vía Horizon)

Cowork y claude.ai no ejecutan servidores locales: necesitan una URL HTTPS pública. Ese es el
trabajo de Horizon.

1. Despliega el servidor (siguiente sección) y copia la URL, del estilo
   `https://<nombre>.fastmcp.app/mcp`.
2. En Claude: **Customize → Connectors → Add → Add custom connector**.
3. Nombre: `Meik Labs Imágenes`; URL: la del paso 1.
4. Deja la autenticación que Claude detecte (OAuth 2.1 con registro dinámico) y pulsa **Connect**.
   El redirect URI es `https://claude.ai/api/mcp/auth_callback`.
5. En cada chat, activa el conector con **+ → Connectors → Meik Labs Imágenes**.

En Claude Code, lo mismo por CLI:

```powershell
claude mcp add --transport http meik-images https://<nombre>.fastmcp.app/mcp
```

## Publicar en Prefect Horizon (ex FastMCP Gateway)

Horizon despliega desde un repositorio de GitHub; no hay comando de deploy en la CLI
(`fastmcp login` / `whoami` / `logout` son solo credenciales).

1. Sube este repo a GitHub (por ejemplo `eduardo-meik/mcp-meik-image`).
2. Entra en <https://horizon.prefect.io> y autentica con GitHub.
3. **Connect GitHub** → elige el repo.
4. Configura el servidor:
   - **Name**: `meik-images` (define la URL pública)
   - **Entrypoint**: `main.py:mcp`
   - **Authentication**: activada (recomendado: solo tu organización)
5. **Deploy Server**. El build clona el repo, instala `requirements.txt` y publica en <60 s.
   Los pushes a `main` redespliegan solos y cada PR genera un preview.
6. En la configuración del servidor, añade el secreto **`OPENROUTER_API_KEY`** y, si aplica,
   `MEIK_IMAGE_MODEL=recraft/recraft-v4.1-flash-v2:free`. En remoto conviene
   `MEIK_IMAGE_DIR=off` (el filesystem es efímero).

Plan Personal de Horizon: gratis, 200 servidores MCP, escala a cero cuando está inactivo.

## Variables de entorno

| Variable | Default | Descripción |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | — | Requerida. Clave `sk-or-v1-…` |
| `MEIK_IMAGE_MODEL` | `recraft/recraft-v4.1-flash-v2:free` | Modelo de imagen |
| `MEIK_OUTPUT_FORMAT` | `webp` | Formato por defecto si no se especifica en `output` |
| `MEIK_OUTPUT_QUALITY` | `82` | Calidad por defecto |
| `MEIK_IMAGE_DIR` | `output` | Carpeta de originales. `off` desactiva el guardado |
| `MEIK_INLINE_MAX_CHARS` | `120000` | Presupuesto de la imagen inline (límite de Claude ≈150k) |
| `MEIK_IMAGE_TIMEOUT_SECONDS` | `180` | Timeout por llamada a OpenRouter |
| `MEIK_IMAGE_MAX_RETRIES` | `2` | Reintentos ante 429/5xx/red |
| `MEIK_APP_URL` / `MEIK_APP_NAME` | meiklabs.com / Meik Labs Image MCP | Cabeceras de atribución de OpenRouter |
| `LOG_LEVEL` | `INFO` | Nivel de log |
| `MEIK_MEDIA_MODE` | `sftp` si hay host | `sftp` \| `ftp` \| `ftps` \| `off` |
| `MEIK_MEDIA_HOST` / `_PORT` / `_USER` / `_PASSWORD` | — | Credenciales del hosting |
| `MEIK_MEDIA_REMOTE_DIR` | — | Carpeta remota de destino |
| `MEIK_MEDIA_BASE_URL` | — | URL pública equivalente a esa carpeta |
| `MEIK_MEDIA_KEY_PATH` / `_KEY_PASSPHRASE` | — | Auth SFTP por clave privada (alternativa a la contraseña) |
| `MEIK_MEDIA_CPANEL_TOKEN` / `_CPANEL_URL` | — | Modo `cpanel`: subida vía API UAPI (Fileman) |
| `MEIK_MEDIA_SUBDIR_BY_DATE` | `true` | Organizar en subcarpetas `YYYY-MM-DD` |

## Tamaño, formato y peso

**¿Se puede pedir un tamaño exacto?** Recraft V4.1 Flash V2 sólo acepta proporción
(`1:1`, `4:3`, `3:4`, `16:9`, `9:16`, `auto`) — no píxeles. El servidor produce el tamaño exacto
después, con Pillow, así que igual obtienes lo que necesitas:

```json
{"width": 1200, "height": 630, "fit": "cover", "format": "webp", "quality": 82, "max_kb": 250}
```

| Campo | Efecto |
| --- | --- |
| `width` / `height` | Tamaño exacto en píxeles. Si omites uno, mantiene la proporción |
| `fit` | `cover` recorta para llenar (recomendado), `contain` agrega relleno, `stretch` deforma |
| `format` | `webp` (default), `jpeg`, `png`, `avif` |
| `quality` | 40–100; por defecto 82 webp / 85 jpeg / 60 avif |
| `max_kb` | Peso máximo; baja calidad y luego escala hasta cumplirlo |
| `publish` | Subir al media server y devolver `public_url` |

Medido sobre arte con gradientes (lo que devuelve Recraft a 1200×630):

| Formato | Peso | Nota |
| --- | --- | --- |
| WebP q82 | **7 KB** | el más liviano, soporte universal, ideal para blog |
| JPEG q85 | 24 KB | mejor compatibilidad con herramientas viejas |
| PNG | 50 KB | sólo para zonas planas o si necesitas transparencia/lossless |
| AVIF q60 | ~igual que WebP | comprime algo más, pero codifica más lento |

En la prueba real de un hero 16:9: **1200×630, JPEG q88, 57 KB** (antes de optimizar el render pesaba ~840 KB).

> Si pides más píxeles que el render original (p. ej. `width: 1920` sobre un 1344 px), el manifiesto
> lo marca como `upscaled` — no gana detalle, sólo interpola.

## Publicar en el media server (cPanel)

Cuando el media server está configurado, cada generación se sube automáticamente y el manifiesto
devuelve `public_url`, `remote_path` y el transporte usado. Los archivos van a
`REMOTE_DIR[/YYYY-MM-DD]/slug-hora-id.ext`.

```ini
MEIK_MEDIA_MODE=sftp            # sftp | cpanel | ftp | ftps | off
MEIK_MEDIA_HOST=sftp.meiklabs.com
MEIK_MEDIA_PORT=22
MEIK_MEDIA_USER=usuario_cpanel
MEIK_MEDIA_PASSWORD=clave       # o usa MEIK_MEDIA_KEY_PATH
MEIK_MEDIA_REMOTE_DIR=/home2/usuario/public_html/assets/blog/
MEIK_MEDIA_BASE_URL=https://meiklabs.com/assets/blog
MEIK_MEDIA_SUBDIR_BY_DATE=true
```

Tres transportes, según lo que permita el hosting:

| Modo | Requiere | Cuándo usarlo |
| --- | --- | --- |
| `sftp` | SSH habilitado + clave autorizada (o contraseña) | el más rápido y estable |
| `cpanel` | `MEIK_MEDIA_CPANEL_TOKEN` (cPanel → Security → Manage API Tokens) | si SSH/FTP están bloqueados o deshabilitados |
| `ftp` / `ftps` | contraseña | último recurso; `ftps` añade TLS explícito |

Para el modo API de cPanel:

```ini
MEIK_MEDIA_MODE=cpanel
MEIK_MEDIA_CPANEL_TOKEN=tu-token
MEIK_MEDIA_CPANEL_URL=https://cpanel.meiklabs.com:2083   # opcional
MEIK_MEDIA_CPANEL_VERIFY_TLS=false                       # muchos cPanel usan certificado propio
```

También se aceptan los nombres cortos `SFTP_HOST`, `SFTP_PORT`, `SFTP_USER`, `SFTP_PASS`,
`REMOTE_DIR` y `BASE_URL` (útiles si ya venían de Bluehost).

Resultado: `https://meiklabs.com/assets/blog/2026-11-15/blog-hero-titulo-103012-a1b2c3.webp`

### La URL debe estar servida por el mismo hosting

Subir el archivo no basta: la URL pública solo funciona si el **docroot del hostname** es la carpeta donde se sube. Caso real de Meik Labs:

- `meiklabs.com` resuelve a **Firebase Hosting** (199.36.158.100), así que
  `https://meiklabs.com/assets/blog/...` devuelve el HTML del SPA, no la imagen.
- `static.meiklabs.com` resuelve a Bluehost (50.87.253.110) con docroot
  `public_html/website_71e15d19`, y **sí** sirve los archivos.

Configuración verificada (HTTP 200 + `content-type` de imagen + bytes idénticos):

```ini
MEIK_MEDIA_MODE=cpanel
CPANEL_API_TOKEN=***
MEIK_MEDIA_REMOTE_DIR=/home2/meiklabs/public_html/website_71e15d19/assets/blog/
MEIK_MEDIA_BASE_URL=https://static.meiklabs.com/assets/blog
```

Si más adelante creas `media.meiklabs.com` (cPanel → Domains → Create A New Domain con
document root `/home2/meiklabs/public_html/assets`), basta cambiar esas dos variables: el
DNS de `meiklabs.com` lo administra Bluehost, así que el registro A se crea solo.

> El token de cPanel necesita al menos `Fileman::upload_files` y `Fileman::list_files`.
> Borrar archivos requiere permisos extra (`delete_files`), que un token mínimo no trae.

- **SFTP** necesita que el acceso SSH esté habilitado en cPanel (SSH Access → Manage SSH Keys/Enable).
- **Auth por clave SSH**: en vez de `MEIK_MEDIA_PASSWORD` puedes usar `MEIK_MEDIA_KEY_PATH` apuntando
  a la clave privada (y `MEIK_MEDIA_KEY_PASSPHRASE` si tiene passphrase). Es lo recomendado si
  generaste un par de claves en cPanel.
- Si SSH está deshabilitado, usa `MEIK_MEDIA_MODE=ftp` (o `ftps` para TLS explícito); esos modos
  requieren contraseña, no aceptan clave.
- Usa `media_server_status` para probar la conexión sin generar nada; devuelve la causa exacta
  (credenciales rechazadas, handshake cortado, host inalcanzable, carpeta inexistente).
- Si una subida falla, la generación **no** falla: la imagen se entrega igual y `publish_error`
  explica qué pasó. `publish_asset` reintenta con otro tamaño/formato.

## Cómo se comporta el modelo

- Proporciones soportadas: `1:1`, `4:3`, `3:4`, `16:9`, `9:16`, `auto`. **No** soporta `21:9`.
- Hasta **6** imágenes por llamada (`n`), sin soporte de imágenes de referencia.
- Salida típica en `image/webp`; el servidor detecta el formato real por *magic bytes*.
- La paleta de marca se refuerza con `provider.options.recraft.controls.colors` (violeta
  `#4F00C4`, magenta `#FF5CF3`, tinta `#1C1C1C`), además del texto del prompt.
- Las imágenes se piden **sin texto**: el copy se compone en el HTML del blog o en la slide.
  Usa `allow_text=true` solo si de verdad quieres letras dentro de la imagen.

### Imagen inline vs. archivo original

Un render de 1344×768 pesa ~600–900 KB; en base64 supera el límite de resultado de un conector
de Claude (~150k caracteres). Por eso el servidor:

1. guarda el original a resolución completa en `MEIK_IMAGE_DIR/AAAA-MM-DD/`;
2. devuelve una copia inline recomprimida (WebP) que cabe en `MEIK_INLINE_MAX_CHARS`,
   reduciendo tamaño/calidad solo lo necesario.

El JSON que acompaña a cada imagen indica `downscaled_for_client`, dimensiones, `saved_to`,
`asset_id`, `cost_usd`, `duration_seconds`, el prompt final y un `alt_text_hint`.

> El archivo guardado en `saved_to` es ya la versión **optimizada** (formato, tamaño y peso que
> pediste en `output`), es la misma que se publica en el media server. El render original del modelo
> no se conserva: es reproducible volviendo a llamar la herramienta.

## Estructura

```
main.py                 FastMCP app + entrypoint (mcp)
meik_image/config.py    Settings desde entorno/.env
meik_image/brand.py     Paletas, estilos, formatos, arquetipos de slide
meik_image/prompts.py   Composición de prompts y guardrails
meik_image/openrouter.py Cliente de /api/v1/images con reintentos
meik_image/optimize.py  Tamaño exacto, formatos (webp/jpeg/png/avif) y presupuesto de peso
meik_image/media.py     Publicación SFTP/FTP al media server y diagnóstico
meik_image/imaging.py   Detección de formato y ajuste del payload inline
meik_image/storage.py   Guardado local + sidecar JSON, listado y carga segura
meik_image/tools.py     Herramientas MCP
tests/                  pytest (sin red)
```

## Tests

```powershell
.venv\Scripts\python.exe -m pytest -q
```

## Problemas típicos

| Síntoma | Causa / solución |
| --- | --- |
| `OPENROUTER_API_KEY inválida o revocada (401)` | Key mal copiada, truncada o revocada. Revisa `.env` |
| `La cuenta de OpenRouter no tiene saldo suficiente (402)` | Usa la variante `:free` o agrega créditos |
| `Límite de peticiones alcanzado (429)` | El servidor ya reintenta con backoff; baja `n` o espacia llamadas |
| Aparecen letras o logos basura | No uses `allow_text`; el guardrail se desactiva con ese flag |
| El cliente dice que la respuesta es demasiado grande | Baja `MEIK_INLINE_MAX_CHARS` (p. ej. 80000) |
| `No encontré el asset …` | El almacenamiento local está en `off` o el asset vive en otro despliegue |
| `El servidor rechazó el usuario/clave SFTP` | Clave incorrecta o SSH deshabilitado en cPanel → `MEIK_MEDIA_MODE=ftp` |
| `El servidor cortó el handshake SSH` | SSH bloqueado/deshabilitado, puerto equivocado o bloqueo por intentos |
| Bloqueo tras varios intentos fallidos | cPanel → **cPHulk Brute Force Protection** → borra el registro de tu IP, o usa `MEIK_MEDIA_MODE=cpanel` |
| `publish_error` pero la imagen llega | La generación no falla por la subida; reintenta con `publish_asset` |

## Marca

| Token | Valor |
| --- | --- |
| primary | `#4F00C4` |
| secondary | `#FF5CF3` |
| ink | `#1C1C1C` |
| paper | `#F5F5F5` |
| display | Space Grotesk |
| body | Inter |
| mono | JetBrains Mono |
