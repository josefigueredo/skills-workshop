# Cómo escribir un episodio

Un episodio es un archivo JSON en `episodes/<serie>/NN-nombre.json`. El motor lo valida y lo mete en `dist/`. Para presentarlo: [presentar.md](presentar.md).

## Formato mínimo

```json
{
  "id": "mi-skill", "series": "cursor", "order": 2, "title": "mi-skill",
  "pitch": {"ask": "Lo que le decís al agente…", "does": "Lo que hace la skill."},
  "skill": {"repo": "mi-skill", "commit": "51311c7", "date": "2026-10-19"},
  "workspace": {"repo": "mi-servicio"},
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
- `workspace.repo` es el nombre del repo que se ve en Cursor; `workspace` también acepta `files` (lista de nombres) y `chats` (`[{"title": "…", "age": "2d"}]`).
- `skill.commit` y `skill.date` dicen contra qué versión de la skill se escribió el episodio.
- Cada capítulo se muestra **primero como una placa** (sale sola, no se declara en `steps`) y después sus pasos. `screen` elige la pantalla: `terminal`, `cursor-full`, `cursor-agent` o `claude-code`.
- En el episodio de ejemplo más corto, [episodes/cursor/00-antes-de-empezar.json](../episodes/cursor/00-antes-de-empezar.json), se ve todo junto. El piloto completo es [01-inherited-audit.json](../episodes/cursor/01-inherited-audit.json).

## Tipos de paso

Todo paso lleva `type` y `source` (obligatorios).

| `type` | Campos obligatorios | Qué muestra |
|---|---|---|
| `term` | `cmd`, `out` (lista de líneas) | Un comando y su salida |
| `ask` | `text` | Lo que la persona le escribe al agente |
| `tool` | `label` | Una ficha de herramienta, por ejemplo `Ran · ia.py baseline` |
| `say` | `md` | La respuesta del agente, en markdown mínimo (ver abajo) |
| `approve` | `title`, `lines` (lista), `button` | La ventana de aprobación de macOS |
| `worked` | `seconds` | «Worked for Ns» |

Campos opcionales de cualquier paso:

- `notes`: texto para quien presenta, solo en el control.
- `pause: true`: el play automático frena después de este paso.

Opcionales solo de `term`:

- `in: "zsh"`: en `cursor-full`, el comando se muestra tipeado por la persona en la terminal integrada de Cursor. Sin `in`, el comando sale en el chat, como si lo corriera el agente (lo normal en Cursor). **Solo tiene efecto en `cursor-full`**: en las otras pantallas se ignora sin avisar, no esperes verlo.
- `cwd` (obligatorio si es `real`): carpeta desde donde corre, siempre `~` o `~/algo` (relativa al HOME falso, sin `..`).
- `capture_only: true` (solo en `term` `real`): el paso corre durante `capture` para avanzar el estado de la demo (por ejemplo crear un archivo que el siguiente paso necesita), pero el `build` lo saca: el escenario y el control nunca lo ven.

### El markdown mínimo de `say`

Soporta solo esto:

- `**negrita**` y `` `código` ``
- `- ` al principio de la línea para una lista
- `#### ` al principio para un subtítulo
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

`build.py capture` arma un HOME falso con la demo en `~/mi-servicio` (la construye `demo/setup.sh`) y la skill del episodio clonada en `~/skills/<skill.repo>` en `skill.commit`. La skill se lee de `$WS_SKILLS_ROOT/<skill.repo>`; si no definís la variable, de la carpeta de al lado del repo del taller.

Si tu episodio necesita estado extra (una rama, un reporte), ponelo en `demo/prep/<id-del-episodio>.sh`: capture lo corre después de armar el HOME y recibe la ruta del HOME como único argumento. Mirá `demo/prep/inherited-audit.sh`.

Dos cuidados:

- **Nunca captures `git log` ni `git show` sobre el clon de una skill**: muestran el autor real del commit y es un dato personal. Si necesitás mostrar historia, que sea de `~/mi-servicio` (autor «Demo»).
- Dentro de la captura el PATH tiene solo el `python3` del sistema o de Homebrew, nunca uno dentro de tu carpeta personal: los pasos usan `/usr/bin/python3`.

## Los comandos

Se corren desde la raíz del repo del taller.

```
python3 build.py validate                       # revisa el formato de los guiones
python3 build.py capture --episode mi-skill     # re-corre los pasos `real` y actualiza el JSON
python3 build.py build                          # valida, arma dist/ y revisa privacidad
python3 build.py check                          # revisa privacidad de episodes/, demo/ y dist/
```

`capture` sin `--episode` los corre todos. Escribe en los JSON solo si pasan las reglas de privacidad. `build` no escribe nada en `dist/` si algo falla.

### Privacidad: `check` y `WS_LEAK_TERMS`

`check` aplica reglas genéricas (mails que no sean `@example.com` (la única excepción es `git@github.com`, el usuario de las direcciones SSH de GitHub), rutas `/Users/…`, tokens y claves) y, además, los términos propios que le des con la variable `WS_LEAK_TERMS`: un archivo con **una expresión regular por línea** (nombres, usuarios, dominios internos). Guardalo **fuera del repo**, porque listaría justamente lo que no tiene que estar en él.

```
WS_LEAK_TERMS=~/privado/leak-terms.txt python3 build.py check
```

Corré `check` (o `build`, que lo incluye) con el archivo antes de cada commit. Si no definís la variable, solo corren las reglas genéricas.

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

## Cuánto dura

El control muestra el estimado: abrí `dist/control.html` y mirá «Estimado ~» (total, a la velocidad elegida) y el estimado por capítulo. Sale de `Animate.episodeDuration` (lo que tarda el tipeo y las animaciones). Eso es solo la pantalla: sumale la narración, a unas 150 palabras por minuto sobre el texto de las `notes`. La meta es de **6 a 12 minutos** por episodio. Si te pasás, partí el caso principal o sacá un caso del medio.

## Antes de entregar

```
python3 build.py build
WS_LEAK_TERMS=<tu archivo> python3 build.py check
python3 -m unittest discover -s tests
```

Recién ahí `dist/` está al día. `dist/` se commitea: quien presenta solo necesita esos archivos.
