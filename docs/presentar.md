# Cómo presentar un episodio

Para quien presenta o graba. No hace falta saber programar: alcanza con Chrome y los archivos de `dist/`.

## Antes de empezar

1. Abrí `dist/control.html` en Chrome (doble clic, funciona sin internet).
2. Elegí el episodio en el selector de arriba. Cada episodio sabe de qué serie es, y el control abre el escenario de esa serie (`serie-cursor.html` o `serie-claude-code.html`).
3. Hacé clic en **«Abrir escenario»**. Tiene que ser un clic tuyo: si el escenario se abriera solo, Chrome lo bloquearía como ventana emergente.
4. Se abre una segunda ventana, el **escenario**: es lo único que ve la audiencia. Arrastrala adonde la vas a compartir o grabar.

El control (la ventana donde hiciste clic) es tu tablero: tiene las notas, las preguntas frecuentes, el reloj y la lista de pasos. **Nunca** lo compartas.

## Qué compartir o grabar

Solo la **ventana del escenario**, nunca la pantalla entera ni la ventana del control.

- **Meet:** Presentar ahora, **Una ventana**, y elegí la del escenario.
- **OBS:** fuente **Captura de ventana** apuntando a la ventana del escenario.
- **Grabación de macOS** (Cmd + Shift + 5): **Grabar parte de la pantalla o ventana seleccionada** y hacé clic sobre la ventana del escenario.

Una precaución: mantené la ventana del escenario visible mientras grabás, sin minimizarla ni taparla del todo con otra. Chrome pausa el dibujado de las ventanas ocultas y la grabación podría salir congelada (es una precaución, no algo que hayamos medido). Podés tapar una parte, o dejar el control al lado.

## Las teclas

Funcionan en el control **y también cuando el foco está en el escenario** (así podés grabar con el escenario en primer plano).

| Tecla | Qué hace |
|---|---|
| `→` | Adelante un paso (se anima: tipeo, respuesta que va saliendo) |
| `←` | Atrás un paso (muestra el paso anterior ya terminado, sin animar; frena el play) |
| `espacio` | Play / pausa: avanza solo; frena en los pasos marcados con pausa |
| `⇧ →` | Salta al principio del capítulo siguiente |
| `⇧ ←` | Salta al principio del capítulo (o al anterior si ya estás ahí) |
| `B` | Pantalla en negro; otra vez `B` la devuelve. Usala durante las preguntas |

También podés usar los botones del control: es lo mismo.

## Durante la presentación

- **Velocidad:** el selector «Velocidad del tipeo» (0,5×, 1×, 1,5×, 2×) cambia qué tan rápido se anima el tipeo. No cambia los pasos.
- **Reloj:** arranca con tu primer movimiento (`→`, espacio, un salto o elegir un capítulo) y sigue corriendo aunque pauses: la narración también cuenta. Al lado de cada capítulo ves el estimado y lo que llevás gastado. Arriba figura el estimado total a la velocidad elegida.
- **Notas y preguntas frecuentes:** están en el control, para el paso en el que estás. **No se muestran nunca en el escenario**, ni en grabación ni en pantalla compartida. Las notas dicen qué remarcar y por qué; las preguntas son las que suelen hacer.
- **Preguntas del público:** `B` para negro, respondés tranquilo, `B` de nuevo para volver al mismo paso.
- **Cambiar de capítulo:** el selector de capítulo del control (o `⇧ →` / `⇧ ←`). El escenario sigue abierto.
- **Cambiar de episodio:** el selector de episodio. Si el nuevo es de la **otra serie**, el control te pide abrir su escenario: otro clic en «Abrir escenario» (es otra página). El reloj vuelve a cero.

## Si aparece «El escenario se cerró»

El control avisa con ese cartel cuando la ventana del escenario se cerró (o dejó de contestar). Hacé clic en **«Reabrir»**: el escenario vuelve a abrir y retoma **en el mismo paso** donde estabas. Si estás grabando, cortá ahí y seguí en otra toma. Si la ventana sigue abierta pero el cartel no se va, cerrala y usá «Reabrir».

## Ensayar un solo paso

Para mirar un paso suelto sin el control, abrí el escenario con la posición en la URL: `#<id-del-episodio>/<número de paso>`. Por ejemplo, el paso 5 del piloto:

```
dist/serie-cursor.html#inherited-audit/5
```

El número es el índice global del episodio, desde 0: la placa de cada capítulo cuenta como un paso, antes de los pasos del capítulo. Muestra el paso ya terminado, sin animación y sin teclas. Sirve para revisar cómo se ve una pantalla; para ensayar el ritmo usá el control.

## Checklist rápido

- [ ] Chrome actualizado, notificaciones silenciadas, otras ventanas cerradas.
- [ ] `dist/control.html` abierto y escenario abierto con «Abrir escenario».
- [ ] Compartís o grabás solo la ventana del escenario.
- [ ] La ventana del escenario queda visible.
- [ ] Probaste `→`, `espacio` y `B` antes de empezar.

Para escribir un episodio nuevo: [guion.md](guion.md).
