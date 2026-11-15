---
name: meik-images
description: "Genera, dimensiona y publica imágenes de Meik Labs con el MCP meik-images (Recraft V4.1 Flash V2 vía OpenRouter, Unsplash, media server cPanel): hero y figuras de blog, imágenes de LinkedIn y otras redes, visuales y fondos de pitch deck, y fotos reales. Úsala cuando haya que crear una imagen desde texto, elegir estilo/paleta de marca, fijar tamaño exacto y peso (LinkedIn 1200x627, OG 1200x630, blog-hero 1344x768), respetar el registro editorial satírico del blog, citar la atribución obligatoria de Unsplash o diagnosticar y reintentar una publicación."
---

# Meik Labs · Imágenes

Servidor MCP que genera imágenes para el blog y los decks de Meik Labs, las ajusta al píxel y
formato pedidos y las publica en el media server. Cada llamada devuelve la imagen inline más un
JSON de manifiesto (prompt final, coste, dimensiones, peso, ruta local, URL pública y
`alt_text_hint`).

El servidor **compone el prompt**: tú describes la escena, él añade estilo, paleta, espacio para
titular y el guardrail de «sin texto». No repitas descriptores de estilo en `prompt`.

## Elegir herramienta

| Lo que se pide | Herramienta |
| --- | --- |
| Cabecera de un artículo (hero/OG) | `generate_blog_hero` |
| Figura que acompaña una sección | `generate_blog_figure` |
| Imagen suelta: LinkedIn, redes, portada, fondo, ilustración | `generate_image` |
| Visual de una slide según el arquetipo | `generate_pitch_slide_visual` |
| Fondo de slide para poner texto encima | `generate_deck_background` |
| Foto real (caso de estudio, industria, equipo) | `search_stock_photos` → `publish_stock_photo` |
| Qué estilos, paletas, formatos y arquetipos existen | `brand_kit` |
| Qué ids de tamaño existen | `size_presets` |
| Cómo se escribe un prompt de blog | `blog_style_guide` |
| Reintentar o reencuadrar una subida | `publish_asset`, `media_server_status` |
| Ver o volver a mostrar algo ya generado | `list_generated_images`, `show_saved_image` |

## Reglas que no se rompen

1. **Tamaño por preset, no por píxeles inventados.** Usa `output.size`; `width`/`height` solo para
   un recorte exacto que no exista como preset. El preset rellena `width`, `height` y `max_kb`
   cuando no los indicas y siempre fija `fit: cover`; un `width`/`height` explícito manda sobre el
   preset.
2. **Sin texto salvo que el texto sea el contenido.** `allow_text` queda en `false`: el titular y el
   copy van en el HTML de la slide o del post. Solo se activa en diagramas y en chistes que dependen
   de un cartel, con 2-6 palabras por superficie.
3. **Si las letras tienen que leerse sí o sí**, repite la llamada con
   `model: "google/gemini-3.1-flash-image"` y el mismo prompt.
4. **Blog ≠ arte abstracto.** El registro del blog es escena concreta, deadpan y absurda. Para blog
   usa `style: "blog-satire"` (o `blog-diagram` / `blog-mascot`) y `palette: "editorial-natural"`;
   `brand-dark` tiñe toda la escena de violeta y mata la foto.
5. **La imagen inline es una copia.** Viene recomprimida para caber en el límite del cliente. La
   versión definitiva es `saved_to` o `public_url`; si `inline.downscaled_for_client` es `true`, no
   es la que se publica en el artículo.
6. **Publicar no es generar.** `output.publish` viene en `true`: si el media server falla, la imagen
   se entrega igual y el manifiesto trae `publish_error`. Se reintenta con `publish_asset`.
7. **Unsplash obliga a atribuir.** Devuelve `attribution.credit_text`; úsalo en el pie o en el `alt`.
8. **Itera la premisa, no el estilo.** Si el chiste no se entiende en dos segundos, cambia la escena.

## El objeto `output`

| Campo | Efecto |
| --- | --- |
| `size` | Preset destino (ver tabla abajo). Elige también la proporción del modelo |
| `format` | `webp` (por defecto del servidor), `jpeg`, `png`, `avif` o `auto` |
| `quality` | 40-100. Por defecto 82 webp / 85 jpeg / 60 avif |
| `width` / `height` | Píxeles exactos; si omites uno se mantiene la proporción |
| `fit` | `cover` recorta para llenar (recomendado), `contain` rellena, `stretch` deforma |
| `max_kb` | Peso máximo: baja calidad y luego escala hasta cumplirlo |
| `publish` | Subir al media server y devolver `public_url` |

Presets más usados: `linkedin-post` 1200×627, `linkedin-square` 1024×1024, `og-image` 1200×630,
`blog-hero` 1344×768, `blog-inline` 1216×896, `blog-diagram` 1216×860, `blog-wide` 1344×672,
`instagram-story` 768×1344, `slide` 1920×1080. Tabla completa, proporciones y aviso de
interpolación en [references/sizes.md](references/sizes.md).

El modelo solo acepta proporciones (`1:1`, `4:3`, `3:4`, `16:9`, `9:16`, `auto`) y genera como
máximo **1344 px de lado largo**; `slide`, `slide-4k`, `wide` y `square` se interpolan (el
manifiesto lo marca con `needs_upscale`, `optimization` y `source_dimensions`).

## Cómo escribir el prompt

- Describe **qué se ve**: sujeto, materiales, objetos, luz, composición, encuadre. Una idea por
  imagen.
- `text_space` (`left`, `right`, `top`, `bottom`, `center`, `none`) reserva la zona del titular.
  Para hero de blog: `left`.
- Afina con `mood`, `must_include` y `must_avoid` en vez de reescribir el prompt entero.
- `n` acepta 1-6: pide 2-3 variantes para comparar, no para «probar suerte».
- Nombra el archivo con `slug` cuando el post ya tiene uno; si falta se deriva del prompt.

## Blog: el registro satírico

Premisa absurda actuada en serio, escena real y reconocible, ejecución sobria, robots y humanos
como colegas aburridos. Sin clichés (manos estrechándose, hologramas azules, cerebros brillantes).

```json
{"title": "La IA que iba a reducir reuniones",
 "angle": "Ahora hay tres reuniones semanales para planificar la IA que reduce reuniones.",
 "style": "blog-satire", "palette": "editorial-natural", "output": {"size": "blog-hero"}}
```

`blog-diagram` **sí** lleva texto (`allow_text: true`, `output.size: "blog-diagram"`); ahí las
etiquetas son el contenido. Reglas, recetas y ejemplos reales en
[references/blog-register.md](references/blog-register.md).

## Ejemplos de llamada

LinkedIn post con el registro del blog:

```json
{"prompt": "Un analista humano sepultado en pilas de papel mientras dos robots de oficina apilan más; uno lleva una pantalla que dice PENDING. Oficina real, luz de ventana, nadie sonríe.",
 "style": "blog-satire", "palette": "editorial-natural", "output": {"size": "linkedin-post"}}
```

Visual de slide:

```json
{"title": "Tracción", "slide_type": "traction", "key_message": "el crecimiento se acelera",
 "style": "data-viz", "output": {"size": "slide"}}
```

Fondo para texto encima: `generate_deck_background` con `theme: "dark"`, `intensity: "subtle"`,
`style: "quiet-surface"`.

## Resultado y errores

- `asset_id` y `saved_to` solo existen si el servidor corre en local con disco; en remoto no hay
  archivo persistente y `publish_asset` / `show_saved_image` no aplican.
- `cost_usd` es 0 con el modelo `:free` y con Unsplash.
- Errores típicos: 401 key inválida, 402 sin saldo, 429 reintentado con backoff (baja `n`),
  `publish_error` por credenciales o SSH bloqueado. Diagnóstico y variables de entorno en
  [references/publishing.md](references/publishing.md).
