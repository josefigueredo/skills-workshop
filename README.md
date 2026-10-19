# Taller de skills: motor de episodios

Motor para armar los episodios del taller en video. Cada episodio es un guion en JSON que se valida y se convierte en HTML autocontenido, sin internet y sin dependencias:

- `dist/serie-cursor.html` y `dist/serie-claude-code.html`: el **escenario**, lo que ve la audiencia (una por serie).
- `dist/control.html`: el **control** de quien presenta (teclas, notas, preguntas frecuentes, reloj).

El diseño completo está en [docs/specs/2026-10-19-taller-skills-design.md](docs/specs/2026-10-19-taller-skills-design.md).

## Cómo se presenta

Abrís `dist/control.html`, hacés clic en «Abrir escenario» y compartís solo esa ventana. Todo en [docs/presentar.md](docs/presentar.md).

## Cómo se agrega un episodio

Se escribe un guion JSON, se captura lo que corre de verdad, se arma `dist/` y se revisa la privacidad. Todo en [docs/guion.md](docs/guion.md).

```
python3 build.py validate | capture [--episode ID] | build | check
```

## Desarrollo

Solo Python 3.9 o más (biblioteca estándar) y JavaScript plano. Los tests corren con las dos versiones de Python:

```
python3 -m unittest discover -s tests
/usr/bin/python3 -m unittest discover -s tests
```

Los tests de JavaScript corren en Chrome sin ventana (headless) y hace falta tenerlo instalado: se busca en `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`, o en la ruta de la variable `CHROME`. Sin Chrome esos tests se saltean con un aviso.

## Episodios

Serie Cursor:

| # | Episodio | Estado |
|---|---|---|
| 0 | Antes de empezar | listo |
| 1 | inherited-audit | piloto en revisión |
| 2… | jira-team-kit (4 skills) | pendiente |
| | product-brain-mcp | pendiente |
| | confluence-team-kit | pendiente |
| | auditing-repos | pendiente |
| | local-board-skill | pendiente |
| | install-unified-ci | pendiente |
| | arq-review | pendiente |

El orden de los pendientes se decide después de revisar el piloto.

Serie Claude Code:

| Episodio | Estado |
|---|---|
| WayOfWork (7 skills `wow-*`) | pendiente |
| run-in-cursor | pendiente |
