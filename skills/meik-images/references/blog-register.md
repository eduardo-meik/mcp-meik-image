# Registro editorial del blog

El blog de Meik Labs no usa arte abstracto de marca: usa **escenas concretas, deadpan y absurdas**,
con tono relajado e irónico. Vive en los estilos `blog-*` y en la herramienta `blog_style_guide`.

## Reglas

1. Una sola premisa ridícula por imagen, actuada completamente en serio.
2. Escena concreta y reconocible: oficina, sala de reuniones, campamento, biblioteca, mesa de
   directorio. Nunca un fondo abstracto.
3. Lo absurdo está en la situación y los objetos, no en el acabado: ejecución realista, sobria y
   bien iluminada.
4. La IA y los robots conviven como colegas aburridos, con expresión deadpan; nunca amenazantes ni
   futuristas.
5. Texto en español (Chile) solo cuando aporta el chiste: pancartas, pizarras, pantallas. 2-6
   palabras por superficie.
6. Referencias locales reconocibles cuando el artículo lo permita.
7. Composición ancha, luz natural o de ventana, grado de color neutro; violeta y magenta de marca
   solo como acento en un prop, nunca baño de color del encuadre.
8. Prohibido el cliché: manos estrechándose, hologramas azules, cerebros brillantes, gente
   señalando gráficos.

## Los tres registros

| Registro | Estilo | Cuándo | Texto | Tamaño | Paleta |
| --- | --- | --- | --- | --- | --- |
| Foto deadpan | `blog-satire` | opinión, análisis, noticias (por defecto) | opcional, rótulos cortos | `blog-hero` o `linkedin-post` | `editorial-natural` (o `neutral`) |
| Diagrama a mano | `blog-diagram` | explicar un concepto o una brecha | **sí**: es el contenido | `blog-diagram` | de marca |
| Mascota 3D | `blog-mascot` | cultura, producto, comunidad | no | `blog-inline` o `linkedin-post` | `editorial-natural` |

## Recetas

**blog-satire**

```
{premisa absurda en una frase}. {escena concreta con objetos reconocibles}.
{quién hace qué, con expresión neutra}. {detalle pequeño que cierra el chiste}.
```

> Un equipo de robots de oficina reparte montañas de papel a un analista humano que ya no tiene
> dónde dejarlas; uno de los robots muestra en su pecho una pantalla que dice PENDING. Luz de
> ventana, oficina real, nadie sonríe.

**blog-diagram**

```
Diagrama dibujado a mano que explica {concepto}: {dos o tres elementos con flechas},
anotaciones cortas en español, {conclusión rotulada}.
```

> Diagrama manuscrito con dos curvas: la IA subiendo en violeta y la adopción real subiendo apenas
> en verde; la brecha entre ambas rotulada «LA BRECHA DE LA IA».

**blog-mascot**

```
Render 3D de {personaje mascota} haciendo {acción absurda y específica} entre {objetos reales},
mirada deadpan, luz cálida de interior.
```

> Render 3D de un cangrejo robot con lentes y lupa leyendo un libro enorme en una biblioteca de
> libros apilados, mirada concentrada y absurda.

## Política de texto en imagen

- Por defecto **sin texto**: el titular y el copy van en el HTML.
- Con texto, solo en diagramas (`allow_text: true`) y en chistes que dependen de un cartel o
  pantalla.
- Límite: 2-6 palabras por superficie, en mayúsculas, sin frases largas.
- Recraft garabatea el español. Si la imagen depende de que las palabras se lean, repite con
  `model: "google/gemini-3.1-flash-image"` y el mismo prompt.

## Flujo

1. Elige el registro: `blog-satire` por defecto, `blog-diagram` si hay un concepto que explicar.
2. Escribe la premisa absurda en castellano, en una frase, antes de escribir el prompt visual.
3. Compón con la receta + escena concreta + detalle que cierra el chiste.
4. Elige `output.size` según destino.
5. Revisa el render: si el chiste no se entiende en 2 segundos, cambia la premisa, no el estilo.

## Referencias reales

| Archivo en `static.meiklabs.com/img/blog` | Qué muestra |
| --- | --- |
| `mas-ai-mas-trabajo.webp` | oficinista sepultado en papel, robots cargando más papel, pantalla PENDING |
| `manual-resistencia-ingenieros-ia-saboteando-algoritmos.webp` | protesta dentro de la oficina, pancartas en español, robots enfrente |
| `prusia-ai.webp` | concilio de guerra histórico con logos de IA como caras y mapa rotulado |
| `brecha-ia-supervision-humana-inercia-organizacional.webp` | diagrama manuscrito con dos curvas y anotaciones |
| `openclaw-rl-aprendizaje-continuo-agentes.webp` | mascota 3D leyendo en una biblioteca cálida |
