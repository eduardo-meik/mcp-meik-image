# Tamaños por destino

Fuente de verdad: `meik_image/presets.py` y la herramienta `size_presets`. Pasa el id en
`output.size`; ahí se resuelven píxeles, `fit`, `max_kb` y la proporción que recibe el modelo.

| id | Píxeles | Proporción | Ratio modelo | Peso | Estilo por defecto | Interpola |
| --- | --- | --- | --- | --- | --- | --- |
| `linkedin-post` | 1200×627 | 1.91:1 | 16:9 | ≤200 KB | blog-satire | no |
| `linkedin-link` | 1200×627 | 1.91:1 | 16:9 | ≤200 KB | blog-satire | no |
| `linkedin-square` | 1024×1024 | 1:1 | 1:1 | ≤220 KB | — | no |
| `linkedin-portrait` | 896×1120 | 4:5 | 3:4 | ≤220 KB | — | no |
| `linkedin-company-cover` | 1344×336 | 4:1 | 16:9 | ≤150 KB | — | no |
| `linkedin-personal-banner` | 1344×336 | 4:1 | 16:9 | ≤150 KB | — | no |
| `blog-hero` | 1344×768 | 16:9 | 16:9 | ≤250 KB | blog-satire | no |
| `blog-inline` | 1216×896 | 4:3 | 4:3 | ≤220 KB | blog-satire | no |
| `blog-diagram` | 1216×860 | √2 | 4:3 | ≤350 KB | blog-diagram | no |
| `blog-wide` | 1344×672 | 2:1 | 16:9 | ≤300 KB | blog-satire | no |
| `og-image` | 1200×630 | 1.91:1 | 16:9 | ≤200 KB | — | no |
| `email-header` | 1200×400 | 3:1 | 16:9 | ≤150 KB | — | no |
| `x-post` | 1344×768 | 16:9 | 16:9 | ≤250 KB | — | no |
| `x-card` | 1200×675 | 16:9 | 16:9 | ≤200 KB | — | no |
| `instagram-square` | 1024×1024 | 1:1 | 1:1 | ≤220 KB | — | no |
| `instagram-story` | 768×1344 | 9:16 | 9:16 | ≤250 KB | — | no |
| `youtube-thumb` | 1280×720 | 16:9 | 16:9 | ≤180 KB | — | no |
| `slide` | 1920×1080 | 16:9 | 16:9 | ≤400 KB | quiet-surface | **sí** |
| `pptx` | 1344×756 | 16:9 | 16:9 | ≤400 KB | — | no |
| `slide-4k` | 3840×2160 | 16:9 | 16:9 | ≤900 KB | — | **sí** |
| `square` | 1200×1200 | 1:1 | 1:1 | ≤220 KB | — | **sí** |
| `wide` | 1920×1080 | 16:9 | 16:9 | ≤300 KB | — | **sí** |

## Salida nativa del modelo

| Ratio | Nativo |
| --- | --- |
| 16:9 | 1344×768 |
| 4:3 | 1216×896 |
| 1:1 | 1024×1024 |
| 3:4 | 896×1216 |
| 9:16 | 768×1344 |
| auto | 1344×768 |

Recraft V4.1 Flash V2 **no** acepta píxeles ni `21:9`; el tamaño exacto lo produce el servidor con
Pillow después del render. Pedir más píxeles que el nativo no añade detalle: interpola, y el
manifiesto lo expone en `needs_upscale`, `optimization` y `source_dimensions`.

## Qué elegir

- **Hero de blog / OG**: `blog-hero`. Si el mismo artículo se comparte en LinkedIn, `linkedin-post`
  (1200×627) para la tarjeta y `blog-hero` para el artículo.
- **Figura interior**: `blog-inline`. Si es un concepto que se explica, `blog-diagram`.
- **Diagrama**: `blog-diagram` (1216×860) siempre con `allow_text: true`.
- **Portadas 4:1**: `linkedin-company-cover`. Se recorta mucho: deja el motivo al centro.
- **Deck**: `slide` para FHD, `pptx` si la plantilla es estándar. `slide-4k` solo si el deck se
  proyecta en 4K de verdad.
- **Recorte a medida** (banner de web, pie de email): combina `width`/`height` + `fit: "cover"` y
  `max_kb`.

## Formato y peso

| Formato | Peso típico de un hero 1200×630 | Nota |
| --- | --- | --- |
| WebP q82 | ~7 KB | el más liviano, ideal para blog |
| JPEG q85 | ~24 KB | compatibilidad con herramientas viejas |
| PNG | ~50 KB | zonas planas o necesidad de lossless |
| AVIF q60 | parecido a WebP | comprime algo más, codifica más lento |

`max_kb` es un presupuesto: el optimizador baja calidad (hasta q40) y después escala hasta
cumplirlo. Se aplica a `webp`, `jpeg` y `avif`; en `png` se ignora, porque conserva la calidad.

El preset rellena `width`, `height` y `max_kb` solo si no los pasas, y fija siempre `fit: "cover"`.
