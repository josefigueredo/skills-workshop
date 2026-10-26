# Cómo escribir un episodio

Un episodio es un archivo JSON en `episodes/<serie>/NN-nombre.json`. El motor lo valida y lo mete en `dist/`. Para presentarlo: [presentar.md](presentar.md).

## Formato mínimo

```json
{
  "id": "mi-skill", "series": "cursor", "order": 2, "title": "mi-skill",
  "pitch": {"ask": "Lo que le decís al agente…", "does": "Lo que hace la skill."},
  "skill": {"repo": "mi-skill", "commit": "51311c7", "date": "2026-10-19"},
  "workspace": {"repo": "mi-servicio"},
  "minutes": [6, 12],
  "chapters": [
    {"id": "instalar", "title": "Instalar", "subtitle": "Una vez por máquina", "screen": "terminal",
     "faq": [{"q": "¿Y si no tengo Docker?", "a": "No hace falta."}],
     "steps": [
       {"type": "term", "cmd": "uv --version", "out": ["uv 0.5.0"], "source": "inferido",
        "notes": "Qué remarcar y por qué."}
     ]}
  ]
}
```

- `series`: `cursor` o `claude-code`. `order`: posición dentro de la serie (el 0 es «Antes de empezar»).
- `minutes`: cuánto tiene que durar el episodio, `[mínimo, máximo]` en minutos enteros. Lo pregunta `new` al crearlo; cada episodio tiene el suyo, porque una presentación de diapositivas y una demo de punta a punta no duran lo mismo. Sin `minutes`, el rango es de 6 a 12 (ver «Cuánto dura»).
- `workspace.repo` es el nombre del repo que se ve en Cursor; `workspace` también acepta `files` (lista de nombres) y `chats` (`[{"title": "…", "age": "2d"}]`) y `model`, el modelo que muestra el chat (por defecto, Sonnet 5.5): tiene que ser el que escribe en el episodio.
- `skill.commit` y `skill.date` dicen contra qué versión de la skill se escribió el episodio.
- Cada capítulo se muestra **primero como una placa** (sale sola, no se declara en `steps`) y después sus pasos. `screen` elige la pantalla: `terminal`, `cursor-full`, `cursor-agent` o `claude-code`.
- En el episodio de ejemplo más corto, [episodes/cursor/00-antes-de-empezar.json](../episodes/cursor/00-antes-de-empezar.json), se ve todo junto. El piloto completo es [01-inherited-audit.json](../episodes/cursor/01-inherited-audit.json).

## Tipos de paso

Todo paso lleva `type` y `source` (obligatorios).

| `type` | Campos obligatorios | Qué muestra |
|---|---|---|
| `term` | `cmd`, `out` (lista de líneas) | Un comando y su salida |
| `ask` | `text` | Lo que la persona le escribe al agente |
| `tool` | `label` | Una ficha de herramienta, por ejemplo `Ran · ia.py baseline`; en `claude-code`, un `label` que empieza con `Skill(` suma la línea «Successfully loaded skill» |
| `say` | `md` | La respuesta del agente, en markdown mínimo (ver abajo) |
| `approve` | `title`, `button`, y `lines` (lista) o `src` | La ventana de aprobación. Con `src` (`pages/<nombre>.html`) es la ventana real de la herramienta: la página que dibuja su código, con `window` (el título de la barra), `width` y `height` (los puntos que le da la herramienta) y los botones Cancelar y `button` abajo. Sin `src`, una caja genérica con `lines` |
| `worked` | `seconds` | «Worked for Ns» |
| `page` | `title`, `src` | Una página HTML real en una ventana de navegador sobre la pantalla, por ejemplo la vista previa de `jtk create --html`. `src` es `pages/<nombre>.html` dentro de `episodes/`; el `build` la mete en el bundle y el escenario la muestra en un iframe con `sandbox` (corre su propio JS, nunca toca el escenario). `title` va en la barra de direcciones. Con `capture` (`~/<ruta>`, solo en un paso `real`), `build.py capture` copia a `src` el archivo que escribieron los pasos reales en el HOME de prueba, por ejemplo los reportes de `ia.py render`: pasa por la misma normalización y el mismo control de privacidad que la salida de los comandos |
| `click` | `target` | La persona toca un botón de la pantalla de Cursor: mientras es el paso actual, el botón queda marcado y su nota sale debajo de la barra de arriba. Hoy el único `target` es `ide`, el botón **IDE ↗** de arriba de la conversación, que abre el editor. **Solo vale en `cursor-full` y `cursor-agent`**, y solo acepta callouts `note` |

Las páginas sin `capture` (la vista previa de jtk y las ventanas de aprobación de jtk, ctk y pbmcp) las genera `python3 tools/real_pages.py` con el código de cada herramienta en el commit que fija su episodio, en `workshop/episodes/pages/` del repo de cada skill, y escribe el ancho y el alto de cada ventana; después `build.py sync` las trae a la copia. Si cambia el episodio o el commit, se vuelve a correr.

Campos opcionales de cualquier paso:

- `notes`: texto para quien presenta, solo en el control.
- `pause: true`: el play automático frena después de este paso.
- `callouts`: marcas visuales que el escenario muestra **solo mientras ese paso es el actual**, para que el público vea dónde mirar; con el paso siguiente desaparecen. Es una lista; cada una tiene `kind` y, según el tipo:
  - `{"kind": "note", "text": "…"}`: una nube con texto (acepta `**negrita**` y `` `código` ``) al final del paso.
  - `{"kind": "box", "match": "…", "text": "…"}`: un recuadro sobre el texto exacto `match`; con `text`, una etiqueta al lado.
  - `{"kind": "underline", "match": "…"}`: un subrayado sobre `match` (también acepta `text`).

  `match` tiene que caer dentro de un solo tramo de texto del paso: el comando, una línea de salida o un tramo del markdown de `say` (la negrita y el `código` lo parten en tramos). Si no está, `validate` lo rechaza. En los pasos `page` y `approve` solo vale `note`, porque su contenido es una ventana aparte; en `click`, también, porque marca un botón y no un texto.

Opcionales solo de `term`:

- `in: "zsh"`: el comando lo tipea la persona, no el agente. En `cursor-full` sale en la terminal integrada de Cursor; en `claude-code` sale como `! comando` (el modo bash de Claude Code), que es como la persona corre lo que el agente le deja listo, por ejemplo un `--apply`. Sin `in`, el comando sale como si lo corriera el agente. **Solo vale en `cursor-full` y `claude-code`**: en las otras pantallas `validate` lo rechaza.
- `cwd` (obligatorio si es `real`): carpeta desde donde corre, siempre `~` o `~/algo` (relativa al HOME falso, sin `..`).
- `color: true`: la salida se ve con sus colores, como en una terminal de verdad. En un paso `real`, `capture` lo corre en una pseudo-terminal de 120 columnas con `TERM=xterm-256color`, `COLORTERM=truecolor` y sin `NO_COLOR`, y guarda en `out` los códigos de color (SGR) y nada más; el escenario los pinta (16 colores, 256 y truecolor, negrita, tenue, cursiva, subrayado). Sirve para herramientas que solo pintan cuando escriben en una terminal, sin agregarle al comando un `--color always` que el público no tipearía. El `match` de las notas se busca en el texto sin códigos, y un tramo de color corta el texto como la negrita en `say`.
- `capture_only: true` (solo en `term` `real`): el paso corre durante `capture` para avanzar el estado de la demo (por ejemplo crear un archivo que el siguiente paso necesita), pero el `build` lo saca: el escenario y el control nunca lo ven.

### El markdown mínimo de `say`

Soporta solo esto:

- `**negrita**` y `` `código` ``
- `- ` al principio de la línea para una lista
- `## `, `### ` o `#### ` al principio para un subtítulo (los tres se ven igual)
- una tabla con barras (`| a | b |`): la fila antes del separador `| --- | --- |` es el encabezado. Sirve para mostrar tal cual la salida de un CLI que ya imprime Markdown, como `jtk team`
- una línea en blanco separa párrafos

Límites que conviene conocer:

- Una línea en blanco **corta la lista**: si seguís con otro `- `, empieza una lista nueva.
- Una línea de continuación (por ejemplo `  más texto` indentado, debajo de un `- `) **no continúa el ítem**: se convierte en un párrafo aparte y corta la lista. Cada ítem va en una sola línea.
- No hay listas anidadas, listas numeradas, links ni tablas.
- Las líneas seguidas sin `- ` se juntan en un solo párrafo.

## `real` o `inferido`

Cada paso declara de dónde sale lo que muestra:

- **`real`**: salida capturada corriendo el comando de verdad contra la demo, en un HOME falso. Necesita `cwd`. Solo para pasos que no tienen efectos afuera.
- **`inferido`**: escrito a mano a partir del README, el showcase o la instalación de la skill. Todo lo que habla el agente es `inferido`.

Regla: si corre sin red y sin efectos externos, es `real`. Los pasos de red (`git clone` desde GitHub, `ssh`, `brew install`) son **siempre `inferido`**.

`skill.commit` y `skill.date` son lo que le dice al futuro que los `real` y los `inferido` valen para esa versión. Si la skill cambia, hay que revisar el episodio contra el commit nuevo.

### Preparar la demo para los pasos `real`

`build.py capture` arma un HOME falso con la demo en `~/mi-servicio` (la construye `demo/setup.sh`) y la skill del episodio clonada en `~/skills/<skill.repo>` en `skill.commit`. La skill se lee de `$WS_SKILLS_ROOT/<skill.repo>`; `WS_SKILLS_ROOT` puede tener varias carpetas separadas por `:` y se usa la primera que tenga el repo. Si no definís la variable, de la carpeta de al lado del repo del taller. Si ninguna tiene `<skill.repo>`, prueba el mismo nombre sin el prefijo `` (`cursor-budget` para `cursor-budget`), que es como se clonan varias skills.

Cada paso `real` corre con la hora de Buenos Aires (`TZ`) y, si es Python, con un reloj que arranca en `skill.date` a las 10:00 y avanza con el tiempo real (`ws/clock/`): `time.time`, `localtime`/`strftime` sin argumento y `datetime.now`/`today` dicen la fecha del episodio, no el día en que capturaste. Como cada paso arranca en el mismo instante, volver a capturar sin cambiar nada no cambia la salida; si cambia, cambió el comando o la skill. Las herramientas en otros lenguajes ven el reloj real.

Si tu episodio necesita estado extra (una rama, un reporte), ponelo en `demo/prep/<id-del-episodio>.sh`: capture lo corre después de armar el HOME y recibe la ruta del HOME como único argumento. Mirá `demo/prep/inherited-audit.sh`.

Dos cuidados:

- **Nunca captures `git log` ni `git show` sobre el clon de una skill**: muestran el autor real del commit y es un dato personal. Si necesitás mostrar historia, que sea de `~/mi-servicio` (autor «Demo»).
- Dentro de la captura el PATH tiene solo el `python3` del sistema o de Homebrew, nunca uno dentro de tu carpeta personal: los pasos usan `/usr/bin/python3`.

## Dónde vive cada episodio

El guion de cada skill vive **en el repo de la skill**, en `workshop/`: `workshop/episodes/<serie>/NN-<id>.json` y sus páginas en `workshop/episodes/pages/`. Ahí se mantiene, en el mismo PR que cambia la skill. El repo también commitea su sitio armado (`workshop/dist/`), y su GitHub Pages lo publica (`.github/workflows/workshop-pages.yml`, copiado de `templates/skill-pages.yml`; en product-brain-mcp va en `/taller/` de su sitio). El workflow no arma nada: compara `workshop/dist/source.sha256` con los guiones y, si `dist/` quedó viejo, falla. Así no hace falta que el CI de la skill lea este repo, que es privado.

El `episodes/` de este repo es **una copia** de los guiones de las skills: con ella se arman las series completas y la portada del taller. Solo `antes-de-empezar` es de acá. No edites la copia: editá la skill y traela con `sync`.

El motor, la demo (`demo/setup.sh`) y los scripts de preparación (`demo/prep/`) siguen acá: con `--root <skill>/workshop`, todos los comandos leen y escriben los guiones de la skill y usan el motor y la demo de este repo.

## Los comandos

Se corren desde la raíz del repo del taller. Con `--root <skill>/workshop` trabajan sobre los guiones de esa skill.

```
python3 build.py new mi-skill [--series cursor|claude-code] [--order N] [--minutes MIN-MAX]   # esqueleto de un episodio nuevo
python3 build.py validate                       # revisa el formato de los guiones
python3 build.py capture --episode mi-skill     # re-corre los pasos `real` y actualiza el JSON
python3 build.py build                          # valida, arma dist/ y revisa privacidad
python3 build.py check                          # revisa privacidad de episodes/, demo/ y dist/
python3 build.py sync [--repo R] [--check]      # trae los guiones de las skills a episodes/
```

`sync` busca cada skill como `capture` (`$WS_SKILLS_ROOT`, o al lado del taller) y lee su copia de trabajo, así que tiene que estar en una rama que tenga `workshop/`. Si no encuentra ningún clon, sale con 1 y dice que no pudo verificar el `dist/` de esa skill, con las carpetas que probó: agregá la que la tiene a `WS_SKILLS_ROOT` (por ejemplo, `~/CurrentCode` para un repo que vive fuera de `Harness/`). Sin `--repo`, recorre los repos de la copia. Copia los guiones y sus páginas, borra de la copia los episodios que la skill ya no tiene y vuelve a armar el `dist/` de la skill en memoria: si el commiteado quedó viejo (porque cambió el guion o el motor), lo dice y sale con 1. `--check` no escribe nada: lista lo que difiere y sale con 1 si hay algo.

`capture` sin `--episode` los corre todos. Escribe en los JSON solo si pasan las reglas de privacidad. `build` no escribe nada en `dist/` si algo falla.

### Privacidad: `check` y `WS_LEAK_TERMS`

`check` aplica reglas genéricas (mails que no sean `@example.com` (la única excepción es `git@github.com`, el usuario de las direcciones SSH de GitHub), rutas `/Users/…`, tokens y claves) y, además, los términos propios que le des con la variable `WS_LEAK_TERMS`: un archivo con **una expresión regular por línea** (nombres, usuarios, dominios internos). Guardalo **fuera del repo**, porque listaría justamente lo que no tiene que estar en él.

```
WS_LEAK_TERMS=~/privado/leak-terms.txt python3 build.py check
```

Corré `check` (o `build`, que lo incluye) con el archivo antes de cada commit. Si no definís la variable, solo corren las reglas genéricas.

Si tu lista marca el nombre de una skill que el taller enseña (por ejemplo, el episodio de esa skill o el «Cierre» que la anuncia), no la cambies: sumá el nombre exacto a `privacy-allow.txt`, en la raíz del repo. Un término de tu lista que cae entero dentro de un nombre permitido, en la misma línea, deja de contar; fuera de ese nombre sigue marcando. Las reglas genéricas (rutas, mails, claves) nunca tienen excepción. Sumá un nombre solo cuando un episodio lo necesita y la persona que organiza el taller está de acuerdo.

## Cómo sacar un episodio de una skill

1. **Leé la rama publicada**, no la de trabajo: `git -C ../<skill> show publish:README.md` (y `docs/showcase.md`, `docs/instalacion.md` o los nombres equivalentes). Anotá el commit: va en `skill.commit`.
2. **Armá la estructura fija:**
   1. **Placa de entrada:** el nombre y la frase «Le decís al agente… / Y la skill…» del README (es `pitch.ask` y `pitch.does`).
   2. **Instalar:** placa y terminal, paso a paso, de la instalación.
   3. **Caso principal:** placa y `cursor-full`, de punta a punta, hasta el resultado.
   4. **Otros casos:** una placa por caso, con `cursor-agent`.
   5. **Si algo falla:** los dos o tres errores típicos de la sección del mismo nombre de la instalación.
   6. **Cierre:** qué te llevás y cuál es el próximo episodio.
3. **Marcá `real` lo que corre sin red** y `inferido` el resto, y corré `capture`.
4. **Escribí las `notes` de cada paso importante:** qué remarcar y **por qué**, no un libreto para leer. La narración es la voz de quien presenta; las notas son el recordatorio. Pensá en un público no técnico.
5. **Cargá 2 a 4 preguntas frecuentes por capítulo** (`faq`): las que de verdad hace la gente, con respuestas cortas que se puedan decir en voz alta.
6. **Contrastá con la skill:** lo que dice el agente en pantalla tiene que ser coherente con su `SKILL.md`. Una respuesta que contradice la skill es el error más caro de encontrar tarde.

## Sumar una skill nueva

1. **Armá el esqueleto en la skill:** `python3 build.py --root <skill>/workshop new <repo-de-la-skill>` (con `--series claude-code` si va en esa serie, y `--order N` si no querés el siguiente número libre). En una terminal te pregunta cuánto tiene que durar (`--minutes MIN-MAX` para no preguntar; Enter deja 6-12) y lo escribe en `minutes`. Si varias skills viven en un mismo repo (un monorepo), usá `--id <skill>`: `python3 build.py new teamwayofwork --id auditing-repos` escribe `NN-auditing-repos.json` con `id` `auditing-repos` y `skill.repo` el monorepo. El id es lo que no se puede repetir, no el repo, así que de un mismo repo salen tantos episodios como ids distintos. Escribe `episodes/<serie>/NN-<id>.json` (el id es el repo si no pasás `--id`) con la estructura fija: instalar, caso principal, otro caso, si algo falla y cierre. Toma `skill.commit` de la primera carpeta de `$WS_SKILLS_ROOT` que tenga `<repo>` si lo encuentra, y la fecha de hoy. No pisa nada: si el episodio o el número ya existen, se niega.
   Ojo con el pin: `new` toma `skill.commit` del HEAD de tu copia local, y esa copia puede estar en otra rama o atrasada. Si no está en el commit de la rama por defecto del remoto, corregí `skill.commit` a mano ni bien termine `new` (y `skill.date` con `git -C <repo> log -1 --format=%cs <commit>`). La captura clona la copia local y hace checkout de `skill.commit`, así que lo que sale en pantalla es ese commit. Nunca hagas checkout ni fetch en la copia de la skill.
2. **Completá todo lo que dice `COMPLETAR`**, leyendo el README, el showcase y la instalación de la skill (ver «Cómo sacar un episodio de una skill»). Mientras quede un `COMPLETAR`, `validate` y `build` fallan y te dicen el archivo, el capítulo y el paso, así que un episodio a medias nunca llega a `dist/`.
3. **Capturá** lo que corre sin red: `python3 build.py --root <skill>/workshop capture --episode <id>`.
4. **Armá:** `python3 build.py --root <skill>/workshop build` y revisá la privacidad con `check`.
5. **Mirá la vista previa:** abrí `<skill>/workshop/dist/index.html`, entrá al episodio nuevo o andá directo a `serie-<serie>.html#<id>/1`.
6. **Publicalo desde la skill:** copiá `templates/skill-pages.yml` a `<skill>/.github/workflows/workshop-pages.yml` y `templates/skill-workshop-README.md` a `<skill>/workshop/README.md`, y commiteá `workshop/` en la skill. La primera vez, en Settings → Pages de la skill, elegí «GitHub Actions».
7. **Traelo al taller:** `python3 build.py sync --repo <repo-de-la-skill>` y `python3 build.py build`.
8. **Pasalo a revisión de la persona** antes de sumarlo a la tabla de episodios del README y de publicarlo.

## Cuánto dura

El control muestra el estimado: abrí `dist/control.html` y mirá «Estimado ~» (total, a la velocidad elegida) y el estimado por capítulo. Sale de `Animate.episodeDuration` (lo que tarda el tipeo y las animaciones). Eso es solo la pantalla: sumale la narración, a unas 150 palabras por minuto sobre el texto de las `notes`. La meta es la que declara el episodio en `minutes`: la elegís al crearlo, según para qué es (una demo, una presentación para un grupo técnico, una intro corta). Si no la declara, es de **6 a 12 minutos**. Si te pasás, primero preguntate si el rango sigue siendo el correcto; si lo es, partí el caso principal o sacá un caso del medio.

Para no sumar a mano: `python3 build.py duration` (o `--episode <id>`) imprime una línea por episodio y por capítulo, `screen m:ss · narración m:ss · total m:ss`. La pantalla sale de `Animate.episodeDuration` corrido en Chrome sin ventana (no se reimplementa en Python), y la narración es la cuenta de palabras de las `notes` a 150 por minuto. Cada línea de episodio dice su rango (`(rango 6-12 min)`). Termina con código 1 y nombra al episodio si su total queda fuera de su rango. El episodio de `order` 0 (`antes-de-empezar`, la intro de preparación, hoy 4:13) se lista pero no cuenta para el código de salida, salvo que declare `minutes`: no es un episodio de skill. Sin Chrome, avisa que se saltea y sale con 0 (`CHROME` apunta a otro binario).

## Antes de entregar

```
python3 build.py sync --check
python3 build.py build
WS_LEAK_TERMS=<tu archivo> python3 build.py check
python3 -m unittest discover -s tests
```

Recién ahí `dist/` está al día. `dist/` se commitea: quien presenta solo necesita esos archivos, y el sitio publicado sale de esa carpeta.
