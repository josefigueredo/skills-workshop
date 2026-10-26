# Cómo presentar un episodio

Para quien presenta o graba. No hace falta saber programar: alcanza con Chrome y los archivos de la carpeta `dist` del repo (la que trae los HTML ya armados).

## Antes de empezar

1. Abrí `dist/control.html` **en Chrome**: clic derecho, «Abrir con», Google Chrome; o arrastrá el archivo a una ventana de Chrome. Un doble clic lo abre con el navegador predeterminado, que puede no ser Chrome. El control y el escenario necesitan Chrome. Funciona sin internet.
2. Elegí el episodio en el selector de arriba. Cada episodio sabe de qué serie es, y el control abre el escenario de esa serie (`serie-cursor.html` o `serie-claude-code.html`).
3. Hacé clic en **«Abrir escenario»**. Tiene que ser un clic tuyo: si el escenario se abriera solo, Chrome lo bloquearía como una ventana que se abre sin que la pidas.
4. Se abre una segunda ventana, el **escenario**: es lo único que ve la audiencia. Arrastrala adonde la vas a compartir o grabar.

El control (la ventana donde hiciste clic) es tu tablero: tiene las notas, las preguntas frecuentes, el reloj y la lista de pasos. **Nunca** lo compartas.

## Qué compartir o grabar

Solo la **ventana del escenario**, nunca la pantalla entera ni la ventana del control.

- **Meet:** Presentar ahora, **Una ventana**, y elegí la del escenario.
- **OBS:** fuente **Captura de ventana** apuntando a la ventana del escenario.
- **Grabación de macOS** (Cmd + Shift + 5): elegí **«Grabar la parte seleccionada»** y arrastrá el recuadro justo sobre la ventana del escenario. Ojo: en video macOS solo ofrece pantalla entera o un recuadro (elegir una ventana es solo para capturas de pantalla), así que no pongas nada encima de esa ventana mientras grabás.
- Para una captura limpia de la ventana sola, recomendamos **OBS con «Captura de ventana»**.

Una precaución: mantené la ventana del escenario visible mientras grabás, sin minimizarla ni taparla del todo con otra. Chrome pausa el dibujado de las ventanas ocultas y la grabación podría salir congelada (es una precaución, no algo que hayamos medido). Taparla un poco solo es tolerable con Meet (una ventana) y con la captura de ventana de OBS, que toman la ventana aunque haya algo encima. Con la grabación de macOS, que graba un recuadro de la pantalla, no: no tapes nada. En todos los casos, el control puede quedar al lado.

## Las teclas

Funcionan en el control **y también cuando estás haciendo clic o escribiendo en la ventana del escenario** (así podés grabar con el escenario en primer plano).

| Tecla | Qué hace |
|---|---|
| `→` o `AvPág` | Adelante un paso (se anima: tipeo, respuesta que va saliendo). Si el paso todavía se está animando, lo termina ahí (salida completa y sus notas) y el próximo `→` avanza |
| `←` o `RePág` | Atrás un paso (muestra el paso anterior ya terminado, sin animar; frena el play) |
| `espacio` | Play / pausa: avanza solo; frena en los pasos marcados con pausa |
| `↓` o `⇧ →` | Salta al principio del capítulo siguiente |
| `↑` o `⇧ ←` | Salta al principio del capítulo (o al anterior si ya estás ahí) |
| `B` | Pantalla en negro; otra vez `B` la devuelve. Usala durante las preguntas |

También podés usar los botones del control: es lo mismo. `AvPág` y `RePág` están porque los presentadores inalámbricos (los clickers) mandan esas teclas.

### Un episodio abierto desde su link, sin el control

Si abrís la serie desde la portada (o con un link como `serie-cursor.html#antes-de-empezar/1`), la página anda sola: `→`/`AvPág`/`espacio` avanzan animando (si el paso todavía se anima, primero lo terminan), `←`/`RePág` retroceden, `⇧ →`/`⇧ ←` saltan de capítulo y `B` pone negro. La dirección se actualiza con el paso, así que si recargás seguís donde estabas. La placa del primer capítulo muestra al pie las teclas `←` y `→`, para quien abre el link sin saber cómo moverse. No hay notas, reloj ni play automático: para presentar en serio, usá el control.

## Durante la presentación

- **Velocidad:** el selector «Velocidad del tipeo» (0,5×, 1×, 1,5×, 2×) cambia qué tan rápido se anima el tipeo. No cambia los pasos.
- **Reloj:** arranca con tu primer movimiento (`→`, espacio, un salto o elegir un capítulo) y sigue corriendo aunque pauses: la narración también cuenta. Al lado de cada capítulo ves el estimado y lo que llevás gastado. Arriba figura el estimado total a la velocidad elegida.
- **Notas y preguntas frecuentes:** están en el control. Las **notas** son de cada paso (cambian al avanzar); las **preguntas frecuentes** son de cada capítulo. **No se muestran nunca en el escenario**, ni en grabación ni en pantalla compartida. Las notas dicen qué remarcar y por qué; las preguntas son las que suelen hacer.
- **Preguntas del público:** `B` para negro, respondés tranquilo, `B` de nuevo para volver al mismo paso.
- **Cambiar de capítulo:** el selector de capítulo del control (o `↓` / `↑`). El escenario sigue abierto.
- **Cambiar de episodio:** el selector de episodio. Si el nuevo es de la **otra serie**, el control te pide abrir su escenario: otro clic en «Abrir escenario» (es otra página). El reloj vuelve a cero.

## Si aparece «El escenario se cerró»

El control avisa con ese cartel cuando la ventana del escenario se cerró (o dejó de contestar). Hacé clic en **«Reabrir»**: el escenario vuelve a abrir y retoma **en el mismo paso** donde estabas. Si estás grabando, cortá ahí y seguí en otra toma. Si la ventana sigue abierta pero el cartel no se va, cerrala y usá «Reabrir».

## Ensayar un solo paso (opcional, para quien arma episodios)

Para mirar un paso suelto sin el control, abrí el escenario con la posición en la URL: `#<id-del-episodio>/<número de paso>`. Por ejemplo, el paso 6 del piloto:

```
dist/serie-cursor.html#inherited-audit/6
```

El número es la posición del paso en todo el episodio, contando desde 1, igual que el «paso N de M» del control (no dentro del capítulo): la placa de cada capítulo cuenta como un paso, antes de los pasos del capítulo. Muestra el paso ya terminado, sin animación y sin teclas. Sirve para revisar cómo se ve una pantalla; para ensayar el ritmo usá el control.

## Checklist rápido

- [ ] Chrome actualizado, notificaciones silenciadas, otras ventanas cerradas.
- [ ] `dist/control.html` abierto y escenario abierto con «Abrir escenario».
- [ ] Compartís o grabás solo la ventana del escenario.
- [ ] La ventana del escenario queda visible.
- [ ] Probaste `→`, `espacio` y `B` antes de empezar.

Para escribir un episodio nuevo: [guion.md](guion.md).
