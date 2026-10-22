# Taller de skills: motor de episodios

Motor para armar los episodios del taller en video. Cada episodio es un guion en JSON que se valida y se convierte en HTML autocontenido, sin internet y sin dependencias:

- `dist/serie-cursor.html` y `dist/serie-claude-code.html`: el **escenario**, lo que ve la audiencia (una por serie).
- `dist/control.html`: el **control** de quien presenta (teclas, notas, preguntas frecuentes, reloj).

El diseño completo está en [docs/specs/2026-10-19-taller-skills-design.md](docs/specs/2026-10-19-taller-skills-design.md).

## El sitio

`dist/index.html` es la portada: un botón para presentar y la lista de episodios con su vista previa. Se publica como sitio de GitHub Pages: la dirección está en el repo, en Settings → Pages (el sitio de GitHub Pages del repo). Cada push a `main` lo vuelve a publicar solo (`.github/workflows/pages.yml`: valida los guiones, comprueba que `dist/` esté al día y sube esa carpeta). Si `dist/` quedó desactualizado, el publicado falla en vez de mostrar algo viejo. La primera vez hay que elegir «GitHub Actions» como fuente en Settings → Pages.

## Cómo se presenta

Abrís `dist/control.html`, hacés clic en «Abrir escenario» y compartís solo esa ventana. Todo en [docs/presentar.md](docs/presentar.md).

## Cómo se agrega un episodio

El guion de cada episodio vive en el repo de su skill (`workshop/episodes/`), que lo mantiene y publica su propio sitio en GitHub Pages. Este repo tiene el motor y una copia de los guiones para armar las series completas: `python3 build.py sync` la trae de las skills. Se arranca con `python3 build.py --root <skill>/workshop new <skill>` (un esqueleto con `COMPLETAR` que `build` no deja pasar), se completa el guion JSON, se captura lo que corre de verdad, se arma `dist/` y se revisa la privacidad. Todo en [docs/guion.md](docs/guion.md).

```
python3 build.py [--root DIR] new SKILL [--series S] [--order N] [--id ID] | validate | capture [--episode ID] | build | check | duration [--episode ID] | sync [--repo R] [--check]
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

| # | Episodio | Estado | El guion vive en |
|---|---|---|---|
| 0 | Antes de empezar | listo | este repo |
| 1 | inherited-audit | listo | `inherited-audit` |
| 2 | jira-team-kit | listo | `jira-team-kit` |
| 3 | confluence-team-kit | listo | `confluence-skill-mcp` |
| 4 | product-brain-mcp | listo | `product-brain-skill-mcp` (en `/taller/` de su sitio) |
| 5 | auditing-repos | listo | `josefigueredo/teamwayofwork` |
| 6 | local-board-skill | listo | `josefigueredo/teamwayofwork` |
| 7 | install-unified-ci | listo | `josefigueredo/teamwayofwork` |
| 8 | arq-review | listo | `arch-review` |

Serie Claude Code:

| # | Episodio | Estado | El guion vive en |
|---|---|---|---|
| 1 | wayofwork (7 skills `wow-*`) | listo | `wow` |
| 2 | run-in-cursor | listo | `run-in-cursor` |

El «Cierre» de cada episodio nombra al siguiente; el último de Cursor nombra la serie de Claude Code y el último de Claude Code cierra el taller. Lo comprueba `CierreChainTests` en `tests/test_schema.py`.
