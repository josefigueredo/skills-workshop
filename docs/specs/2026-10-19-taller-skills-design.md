# Taller de skills de team: diseño

Fecha: 2026-10-19. Estado: aprobado en conversación; revisado por un lector externo, con sus dudas resueltas.

## Para qué

Que el equipo **adopte las skills como su forma estándar de trabajar**, no que aprenda un catálogo. El taller muestra,
skill por skill, cómo se instala, el caso principal con su resultado feliz y después cada uno de los otros casos. Hay
personas no técnicas en la audiencia: la instalación tiene que poder seguirse sin saber de terminal más allá de pegar
un comando.

Se usa de dos maneras, con el mismo material:

1. **Grabado:** la persona que presenta maneja la reproducción con control fino y graba la ventana del escenario.
2. **En vivo:** se reproduce en una Meet, que también se graba, con preguntas y respuestas en el medio (saltar atrás,
   pausar, poner la pantalla en negro).

## Objetivos

- Una **serie de episodios cortos, uno por skill**, con la misma estructura y el mismo aspecto en todos.
- Pantallas que se lean como las reales: Cursor (ventana Agents, tema claro, Sonnet 5.5) y la terminal de la persona.
- Un **control del presentador** en una ventana aparte que maneja al escenario.
- El contenido sale de la documentación que ya existe en cada skill (`docs/showcase.md`, `docs/instalacion.md`): el
  taller la pone en escena, no la reinventa.
- Fácil de mantener: si cambia una skill se edita su guion, no se regraba a mano; si cambia la interfaz de Cursor se
  cambian variables de CSS.

## No objetivos

- No es un curso de terminal, de git ni de brew: los requisitos básicos vienen instalados (ver «Episodio 0»).
- No graba ni edita video: produce lo que se graba (con OBS o la grabación de macOS).
- No ejecuta las skills de verdad durante el taller: todo es puesta en escena.
- No cubre las GitHub Actions de `agentic-doc/` (agentic-docs-check, api-contract-check): no son skills que se le
  piden a un agente. Pueden ir a un anexo más adelante.

## Anti-objetivos (fracaso aunque funcione)

- Que un episodio prometa una instalación que en la realidad falla para una persona no técnica.
- Que las pantallas se vean falsas o distintas entre episodios (lo que ya pasa hoy con las maquetas de cada repo).
- Que mantenerlo dependa de una sola persona o de herramientas que no están en el repo.
- Que muestre datos de una persona, credenciales o rutas personales.

## Audiencia y requisitos previos

Personas del equipo, técnicas y no técnicas, que usan Cursor a diario. Antes del curso, quien organiza pide que
estén instalados brew y las herramientas básicas. El **episodio 0** lo hace explícito: la lista de requisitos (brew,
git, Python 3, `uv`, tmux, jq, Cursor, clave SSH cargada en GitHub y acceso a la org de los repos), un comando que
verifica todo y dice qué falta, y un texto listo para mandar a quienes se anoten. *Decisión del diseño, no pedida
explícitamente.*

## Las dos series

Decisión de la persona: las skills que corren en Claude Code van en **otro HTML de escenario**, para la misma
audiencia. Mismo motor, mismo control, mismo formato de guion.

**Serie Cursor**

| # | Episodio | Fuente |
|---|---|---|
| 0 | Antes de empezar | Se escribe para el taller |
| 1… | inherited-audit, jira-team-kit (4 skills), product-brain-mcp, confluence-team-kit, auditing-repos, local-board-skill, install-unified-ci, arq-review | `showcase.md` e `instalacion.md` de cada una |

El orden dentro de la serie queda para el plan.

**Serie Claude Code:** WayOfWork (7 skills `wow-*`) y run-in-cursor.

run-in-session y harness-docs **quedan afuera por ahora**: no tienen remoto git, así que nadie las puede instalar
desde un clon. Decisión de la persona: van a tener remoto cuando sean compatibles con Cursor, y en ese momento se suman
a la serie Cursor como cualquier otra.

## Estructura fija de un episodio

Placas de capítulo entre escenas (opción C de `docs/maquetas/marco.html`, elegida por la persona); la narración va
por la voz de quien presenta.

1. **Placa de entrada:** nombre de la skill y la frase «Le decís al agente… / Y la skill…» del README.
2. **Instalar:** placa y después la terminal, paso a paso.
3. **Caso principal:** placa y después Cursor completo, de punta a punta, hasta el resultado.
4. **Otros casos:** una placa por caso y después la vista de solo el agente.
5. **Si algo falla:** los dos o tres errores típicos, de la sección del mismo nombre de `instalacion.md`.
6. **Cierre:** qué te llevás y cuál es el próximo episodio.

Duración objetivo: entre 6 y 12 minutos por episodio, ajustable con la velocidad del tipeo. *Decisión del diseño.*

## De dónde salen las salidas que se ven

Decisión de la persona: la salida de cada paso se **infiere conociendo la skill** o se **obtiene corriéndola contra un
proyecto de prueba**. El repo del taller trae uno o más proyectos de prueba (sistemas chicos, sin datos reales, como
el repo `tienda` de inherited-audit), pensados para que cada skill tenga algo sobre qué trabajar.

- Lo que se puede correr sin efectos afuera (CLI locales, lectura de repos, reportes) se corre contra el proyecto de
  prueba y el guion copia la salida real.
- Lo que escribe afuera (Jira, Confluence, ventanas de aprobación) o necesita credenciales se infiere a partir del
  código y la documentación de la skill.
- Cada paso del guion dice cuál de las dos es (`real` o `inferido`), con la fecha y el commit de la skill. Las notas
  del presentador lo muestran; el escenario no. *Decisión del diseño.*

## Pantallas

Aprobadas sobre capturas reales del Cursor de la persona (`docs/maquetas/pantallas.html`):

1. **Cursor completo:** barra izquierda (New Chat, Search, Automations, Customize, repos con sus chats), conversación
   al centro (pedido arriba, «Worked for…», herramientas, respuesta, «Send follow-up», rama y «This Mac»), panel
   derecho (pestañas README, Changes, Browser, Canvas; árbol de archivos; terminal `zsh` integrada).
2. **Solo el agente:** sin panel derecho, con la columna «Open Tabs». Para los otros casos.
3. **Terminal de la persona:** oscura, sin pestañas, con prompt de segmentos (manzana, carpeta, rama, línea de puntos,
   «system», hora). Para la instalación.
4. **Ventana de aprobación de macOS** (jira-team-kit, product-brain-mcp, confluence-team-kit): sale de las maquetas
   que esas skills ya tienen.
5. **Serie Claude Code:** la pestaña de Claude Code en la terminal, con el tema de la terminal de la persona (pantalla
   3). Las maquetas `cc-*` de run-in-session y harness-docs sirven de referencia de forma.

En pantalla el modelo dice **Sonnet 5.5** y la persona es «Persona del equipo», nunca un nombre real. *Decisiones del
diseño.*

## Control del presentador

Ventana aparte que no se comparte ni se graba (`docs/maquetas/control.html`, aprobada):

- Capítulos del episodio con tiempos, pasos del capítulo en curso y selectores para saltar de episodio o capítulo.
- Miniatura del escenario en vivo con el número de paso, y aviso de lo que viene.
- Controles: capítulo atrás (`⇧←`), atrás 1 (`←`), play/pausa (`espacio`), adelante 1 (`→`), capítulo adelante (`⇧→`).
- Velocidad del tipeo, reloj del episodio y `B` para poner el escenario en negro.
- Notas para decir (qué remarcar y por qué) y preguntas frecuentes con su respuesta corta. No se ven en el escenario.

Pedido de la persona: control fino para grabar y para presentar en vivo con Q&A. Los agregados (velocidad, reloj, `B`,
notas, preguntas) son *decisión del diseño* y la persona los aprobó.

## Cómo se construye (decidido)

- **Guiones como datos:** un archivo por episodio con capítulos, pasos y notas. Tipos de paso: placa, línea de
  terminal (comando y salida), pedido al agente, herramienta que corre, respuesta del agente, ventana de aprobación.
  Los genera un agente desde el showcase y la instalación de cada skill; la persona los revisa.
- **Un motor, dos escenarios, un control.** HTML autocontenido que se abre con doble clic, sin servidor, para poder
  pasarlo a otra persona que dé el taller. El control abre el escenario como ventana propia y le manda órdenes.
- **Estilo en variables de CSS**, partiendo de las maquetas aprobadas.
- **Repo:** `Harness/skills-workshop`. Documentación para personas en castellano rioplatense.

## Trabajo previo, fuera del taller

- **arq-review se ordena con el estándar de harness-docs** (README índice, showcase, instalación, capturas) antes de
  armar su episodio, para que salga de su showcase como los demás. Decisión de la persona.
- Los requisitos del episodio 0 los pide quien organiza antes del curso.

## Decisiones del diseño tomadas después de la revisión

Cada una es *decisión del diseño*; la persona puede revertirla.

- **Fidelidad visual:** fiel en espíritu, no al píxel. Fuentes del sistema, íconos con caracteres o SVG simples, el
  cromo de Cursor reproducido con CSS. Referencia: las capturas reales en `docs/maquetas/referencias/` (ignoradas por
  git porque muestran nombre y repos de una persona).
- **Navegador y equipo:** Chrome en macOS, sin conexión. Dos ventanas: el control abre el escenario con un clic (gesto
  de la persona, así el navegador no lo bloquea). Para grabar o compartir en Meet se elige solo la ventana del
  escenario.
- **Guiones dentro del HTML:** un script de armado en Python (biblioteca estándar, dentro del repo) toma los guiones y
  escribe un HTML autocontenido por serie, más el control. Así se abre con doble clic sin chocar con las restricciones
  de `file://`.
- **«Atrás 1» reconstruye el estado:** lo que se ve es función del número de paso. Retroceder muestra el paso anterior
  ya terminado, sin repetir la animación; avanzar anima solo el paso nuevo.
- **Datos personales:** una lista de expresiones a rechazar que vive fuera del repo (como en inherited-audit, con una
  variable de entorno), más reglas genéricas en el repo: rutas `/Users/`, mails, claves con forma conocida.
- **Notas y preguntas frecuentes:** las redacta el agente junto con el guion y las revisa quien presenta. Solo en
  castellano; sin subtítulos en inglés.

## Lo que queda para quien construye

- El formato exacto del guion y el motor de animación (tipeo, aparición de respuestas, tiempos).
- Cómo se comunican control y escenario sin servidor (por ejemplo, la referencia de la ventana abierta).
- El orden de los episodios dentro de cada serie.
- Cómo se verifica que un guion siga coincidiendo con el showcase de su skill cuando la skill cambia.
- Tests del motor y del formato de guion, y cómo se valida que los HTML no tengan datos personales.

## Riesgos conocidos

- Las maquetas actuales de cada repo son oscuras e inconsistentes (algunas dicen «Cursor», otras «Claude Code» con la
  misma forma); el taller no las reusa visualmente, solo su contenido.
- Varias instalaciones hoy no son para no técnicos (`uv`, `mcp.json`, tmux, `ln -s` a mano, SSH). El episodio 0 cubre
  los requisitos; lo demás tiene que quedar explicado en cada episodio o resolverse en la skill.
- Un paso `inferido` puede quedar viejo cuando cambia la skill: por eso lleva el commit de la skill con el que se
  escribió.
