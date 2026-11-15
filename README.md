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
| `media_server_status` | Diagnostica la conexión SFTP/FTP/cPanel y la carpeta remota | JSON |
| `size_presets` | Tamaños por destino (LinkedIn 1200×627, OG, blog, story, slide…) | JSON |
| `blog_style_guide` | El estilo editorial del blog capturado como sistema de prompts | JSON |
| `search_stock_photos` | Busca fotos reales en Unsplash | JSON |
| `publish_stock_photo` | Descarga, optimiza y publica una foto de Unsplash con atribución | Imagen + URL |
| `list_generated_images` | Lista los assets guardados en local (solo con disco) | JSON |
| `show_saved_image` | Vuelve a mostrar inline un asset guardado | Imagen |

Todas las herramientas de generación aceptan `output` para controlar tamaño, formato, peso y publicación
(ver [Tamaño, formato y peso](#tamaño-formato-y-peso)).

Estilos: `abstract-geometric`, `gradient-mesh`, `quiet-surface`, `isometric-tech`, `flat-vector`,
`line-art`, `editorial-photo`, `data-viz`, `glass-ui`, `topographic`, `collage`, `blueprint`.

Paletas: `brand-dark`, `brand-light`, `brand-mono`, `neutral`, `editorial-natural`, `warm`, `cool`,
`none`.

Registro de blog (tono relajado, irónico y absurdo): `blog-satire`, `blog-diagram`, `blog-mascot`.

Arquetipos de slide: `title`, `problem`, `solution`, `product`, `market`, `traction`, `competition`,
`team`, `roadmap`, `business-model`, `ask`, `quote`.

## Skill para agentes (Claude Code / Copilot / Codex)

`skills/meik-images/` empaqueta el uso del servidor como *skill*: cuándo llamar cada herramienta,
qué preset de tamaño toca, el registro editorial del blog, la atribución de Unsplash y cómo
reintentar una publicación.

```
skills/meik-images/SKILL.md               decisión de herramienta + reglas + ejemplos
skills/meik-images/references/sizes.md    los 22 presets, salida nativa y formatos
skills/meik-images/references/blog-register.md  reglas, recetas y ejemplos reales del blog
skills/meik-images/references/publishing.md     SFTP/cPanel, diagnóstico y Unsplash
```

Instalarla en el cliente (copia la carpeta al directorio de skills del agente):

```powershell
# Claude Code / Copilot (skills de usuario)
Copy-Item -Recurse skills\meik-images $env:USERPROFILE\.copilot\skills\
```

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

Horizon despliega desde un repositorio de GitHub y **sirve el servidor con uvicorn**, así que
el repo debe exponer una **app ASGI**, no solo la instancia de FastMCP.

Este repo ya trae las dos cosas y `fastmcp.json`:

| Entrypoint | Objeto | Cuándo |
| --- | --- | --- |
| `main.py:mcp` | instancia FastMCP | `fastmcp run`, Claude Desktop local |
| `main.py:app` | app ASGI (Starlette) | uvicorn / Horizon |
| `src/server.py:app` · `src/server.py:mcp` | igual que arriba | layout por defecto de la plantilla de Horizon |
| `src/main.py:app` · `src/main.py:mcp` | alias | si el entrypoint quedó como `src/main.py:...` |

Pasos:

1. Sube este repo a GitHub (ya está en `eduardo-meik/mcp-meik-image`).
2. Entra en <https://horizon.prefect.io> y autentica con GitHub.
3. **Connect GitHub** → elige el repo.
4. Configura el servidor:
   - **Name**: `meik-images` (define la URL pública)
   - **Entrypoint**: `main.py:mcp` — si el formulario insiste en un layout `src/`,
     usa `src/server.py:mcp`
   - **Authentication**: activada (recomendado: solo tu organización)
5. **Deploy Server**. El build clona el repo, resuelve `requirements.txt` con uv y publica en <60 s.
6. Añade los secretos (ver más abajo) y verifica con `https://<nombre>.fastmcp.app/health`.

> **Error `ModuleNotFoundError: No module named 'src'`**: el entrypoint configurado apunta a un
> layout `src/...` que el repo no tenía. Ya está cubierto con `src/server.py` y `src/main.py`;
> si vuelve a aparecer, revisa que el campo Entrypoint diga `main.py:mcp`.

> **`mcp` no es una app ASGI**: usa `main.py:app` (o `src/server.py:app`) cuando el host arranque
> con uvicorn.

El servidor expone además `GET /health` (estado, modelo, API key y media server configurados) y
`GET /` con la información del endpoint. Se sirve en modo **stateless** porque las plataformas con
scale-to-zero pierden la sesión entre peticiones y todas las herramientas son autocontenidas.

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
| `UNSPLASH_ACCESS_KEY` | — | Habilita `search_stock_photos` / `publish_stock_photo` |
| `MEIK_MEDIA_MODE` | `sftp` si hay host | `sftp` \| `ftp` \| `ftps` \| `off` |
| `MEIK_MEDIA_HOST` / `_PORT` / `_USER` / `_PASSWORD` | — | Credenciales del hosting |
| `MEIK_MEDIA_REMOTE_DIR` | — | Carpeta remota de destino |
| `MEIK_MEDIA_BASE_URL` | — | URL pública equivalente a esa carpeta |
| `MEIK_MEDIA_KEY_PATH` / `_KEY_PASSPHRASE` | — | Auth SFTP por clave privada (alternativa a la contraseña) |
| `MEIK_MEDIA_CPANEL_TOKEN` / `_CPANEL_URL` | — | Modo `cpanel`: subida vía API UAPI (Fileman) |
| `MEIK_MEDIA_SUBDIR_BY_DATE` | `true` | Subcarpetas `YYYY-MM-DD`. Para `/img/blog/` va en `false` |
| `MEIK_MEDIA_NAMING` | `unique` | `slug` → nombre estable `<slug>.ext`; `unique` → con hora y sufijo |

## Convención de rutas del blog

El blog publica en **`https://static.meiklabs.com/img/blog/<slug>.webp`** — plano, sin carpetas
por fecha y con el slug del post como nombre. Es lo que usa el skill `blog-creator` y lo que hay
hoy en el directorio (7 imágenes, todas `<slug>.webp`).

Configuración correspondiente:

```ini
MEIK_MEDIA_MODE=cpanel
MEIK_MEDIA_CPANEL_TOKEN=***
MEIK_MEDIA_USER=meiklabs
MEIK_MEDIA_REMOTE_DIR=/home2/meiklabs/public_html/website_71e15d19/img/blog/
MEIK_MEDIA_BASE_URL=https://static.meiklabs.com/img/blog
MEIK_MEDIA_SUBDIR_BY_DATE=false
MEIK_MEDIA_NAMING=slug
```

Para forzar el nombre exacto de un post, pasa `output.filename`:

```json
{"output": {"size": "blog-hero", "format": "webp", "filename": "como-automatizar-sin-morir"}}
```

→ `https://static.meiklabs.com/img/blog/como-automatizar-sin-morir.webp`

Repetir la llamada con el mismo `filename` **sobrescribe** el archivo: la URL queda estable y el
`Image URL` del post en Notion no cambia.

En modo `cpanel` no hace falta `MEIK_MEDIA_HOST`: se deriva del hostname de `MEIK_MEDIA_BASE_URL`
(cPanel escucha en `:2083` del mismo servidor). Sí necesitas `MEIK_MEDIA_USER` (el usuario cPanel,
porque la cabecera de la API es `cpanel usuario:token`).

## Estilo editorial del blog

Las imágenes del blog (`https://static.meiklabs.com/img/blog`) no son arte abstracto de marca:
son **escenas concretas, deadpan y absurdas**, con un tono relajado e irónico. Ese estilo está
capturado en tres estilos y en la herramienta `blog_style_guide`.

| Registro | Estilo | Cuándo | Ejemplo real |
| --- | --- | --- | --- |
| Foto deadpan | `blog-satire` | opinión, análisis, noticias | oficinista sepultado en papel con robots cargando más papel |
| Diagrama dibujado a mano | `blog-diagram` | explicar un concepto o una brecha | dos curvas violeta/verde rotuladas «LA BRECHA DE LA IA» |
| Mascota 3D | `blog-mascot` | cultura, producto, comunidad | cangrejo robot leyendo con lupa en una biblioteca |

Reglas que se aplican automáticamente en los estilos `blog-*`:

1. Una sola premisa ridícula, actuada completamente en serio.
2. Escena concreta y reconocible (oficina, sala de reuniones, campamento, biblioteca).
3. Lo absurdo está en la situación, no en el acabado: ejecución realista y sobria.
4. Robots y humanos como colegas aburridos, mirada deadpan; nunca amenazantes.
5. Texto en español sólo cuando aporta el chiste: 2-6 palabras por superficie.
6. Nada de clichés: manos estrechándose, hologramas azules, cerebros brillantes.

```json
{"prompt": "Una jefa aprueba IA «para reducir reuniones»; ahora hay tres reuniones semanales para planificar la IA que reduce reuniones. Sala real, calendario saturado, un robot sostiene una pizarra con una reunión más, todos con cara neutra.",
 "style": "blog-satire",
 "output": {"size": "linkedin-post"}}
```

Para diagramas usa `style: "blog-diagram"` con `allow_text: true` — es el único caso donde el
texto dentro de la imagen es el contenido. Recraft escribe bien rótulos cortos en español; si el
texto tiene que ser perfecto, pasa `model: "google/gemini-3.1-flash-image"`.

## Tamaños por destino

`output.size` resuelve el tamaño exacto, la proporción para el modelo y el peso recomendado.
Listado completo con `size_presets`.

| Preset | Píxeles | Proporción | Peso | Nota |
| --- | --- | --- | --- | --- |
| `linkedin-post` | 1200×627 | 1.91:1 | ≤200 KB | post y post con enlace |
| `linkedin-square` | 1024×1024 | 1:1 | ≤220 KB | feed y carrusel |
| `linkedin-portrait` | 896×1120 | 4:5 | ≤220 KB | carrusel vertical |
| `linkedin-company-cover` | 1344×336 | 4:1 | ≤150 KB | se recorta: motivo al centro |
| `blog-hero` | 1344×768 | 16:9 | ≤250 KB | cabecera y OG |
| `blog-inline` | 1216×896 | 4:3 | ≤220 KB | figura interior |
| `blog-diagram` | 1216×860 | √2 | ≤350 KB | diagramas con anotaciones |
| `blog-wide` | 1344×672 | 2:1 | ≤300 KB | editorial ancha |
| `og-image` | 1200×630 | 1.91:1 | ≤200 KB | preview al compartir |
| `instagram-story` | 768×1344 | 9:16 | ≤250 KB | story / reel |
| `slide` | 1920×1080 | 16:9 | ≤400 KB | deck FHD (se interpola) |

Recraft genera como máximo **1344 px de lado largo** (1344×768 en 16:9, 1216×896 en 4:3,
1024×1024 en 1:1). Los presets están alineados a esa salida para no interpolar; cuando pides más
(`slide`, `slide-4k`) el manifiesto lo marca en `optimization` y `source_dimensions`, y
`size_presets` expone `needs_upscale`.

## Unsplash: evaluación

Integrado como fuente **opcional** (`UNSPLASH_ACCESS_KEY`), con `search_stock_photos` y
`publish_stock_photo` (descarga, recorta, optimiza, publica y devuelve la atribución).

**Aporta**
- Fotografía real y bien producida: oficinas, industria, equipo, producto. Imposible de igualar
  con un text-to-image de 3 segundos y gratis.
- Cuando el artículo necesita credibilidad documental, no humor.

**No aporta**
- No puede inventar la escena absurda del blog (robots repartiendo papel, concilio prusiano con
  logos). Para eso siguen los estilos `blog-*`.
- Depende de un tercero: cuotas (50 req/h en modo demo, 5000 req/h tras aprobación) y
  disponibilidad.

**Licencia y obligaciones**
- Unsplash License: uso comercial gratis, sin atribución legal obligatoria, pero **prohibido**
  recompilar las fotos para ofrecer un servicio similar y prohibido venderlas sin modificar.
- Las guías de la API piden atribución visible y disparar el endpoint de descarga al usar una
  foto: el servidor lo hace y devuelve `attribution.credit_text` (`Foto: Autor / Unsplash`) más
  los enlaces. Úsalo en el pie o en el `alt`.

**Recomendación de uso**: `blog-satire` para todo lo que necesite el guiño del blog; Unsplash
para casos de estudio, páginas de servicio y decks donde una foto real vende mejor.

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

Resultado (con `MEIK_MEDIA_SUBDIR_BY_DATE=false` y `MEIK_MEDIA_NAMING=slug`):
`https://static.meiklabs.com/img/blog/<slug>.webp`

### La URL debe estar servida por el mismo hosting

Subir el archivo no basta: la URL pública solo funciona si el **docroot del hostname** es la carpeta donde se sube. Caso real de Meik Labs:

- `meiklabs.com` resuelve a **Firebase Hosting** (199.36.158.100), así que
  `https://meiklabs.com/assets/blog/...` devuelve el HTML del SPA, no la imagen.
- `static.meiklabs.com` resuelve a Bluehost (50.87.253.110) con docroot
  `public_html/website_71e15d19`, y **sí** sirve los archivos. El blog vive en
  `website_71e15d19/img/blog/`.

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
main.py                 FastMCP app + entrypoints (mcp, app) + CLI local
fastmcp.json            Config de proyecto FastMCP (source/env/deployment)
src/server.py           Entrypoint ASGI para Horizon/uvicorn (app, mcp)
src/main.py             Alias de src.server para el layout src/main.py:mcp
meik_image/config.py    Settings desde entorno/.env
meik_image/brand.py     Paletas, estilos (incluye registro blog), formatos, arquetipos de slide
meik_image/presets.py   Tamaños por destino (LinkedIn, blog, redes, decks) y salida nativa
meik_image/styleguide.py El estilo editorial del blog como sistema de prompts
meik_image/prompts.py   Composición de prompts, tono y guardrails
meik_image/openrouter.py Cliente de /api/v1/images con reintentos
meik_image/stock.py     Unsplash: búsqueda, descarga y atribución
meik_image/optimize.py  Tamaño exacto, formatos (webp/jpeg/png/avif) y presupuesto de peso
meik_image/media.py     Publicación SFTP/FTP al media server y diagnóstico
meik_image/imaging.py   Detección de formato y ajuste del payload inline
meik_image/storage.py   Guardado local + sidecar JSON, listado y carga segura
meik_image/tools.py     Herramientas MCP
skills/meik-images/     Skill para agentes (SKILL.md + references/)
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
