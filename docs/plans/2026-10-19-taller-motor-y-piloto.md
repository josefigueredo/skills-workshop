# Skills Workshop — Engine, Episode 0 and Pilot Episode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the workshop engine (two stage pages and one presenter control, self-contained HTML built from episode scripts), episode 0 «Antes de empezar», and one complete pilot episode (inherited-audit) the person can review before the rest of the episodes are scripted.

**Architecture:** Episode scripts are JSON files validated and inlined by a Python stdlib build script into `dist/` (`serie-cursor.html`, `serie-claude-code.html`, `control.html`). The stage renders any step index as a pure function of (episode, index), then animates only a forward single step. The control opens the stage window with a click and drives it with `postMessage`. Terminal steps marked `real` are refreshed by running their commands against demo projects in a fake HOME.

**Tech Stack:** Python 3.9+ stdlib (build, capture, tests), vanilla JS (ES2017, no modules, no dependencies), CSS custom properties, headless Google Chrome for JS tests.

**Spec:** `docs/specs/2026-10-19-taller-skills-design.md` (binding). Approved mockups: `docs/maquetas/{pantallas,marco,control}.html` (fragments; visual reference, not code to copy verbatim). Real screen references (git-ignored, may be absent): `docs/maquetas/referencias/*.png`.

**Out of this plan (Plan 2, after the person reviews the pilot):** scripts for jira-team-kit, product-brain-mcp, confluence-team-kit, auditing-repos, local-board-skill, install-unified-ci, arq-review (blocked on its harness-docs cleanup), WayOfWork and run-in-cursor.

## Global Constraints

- Python 3.9 stdlib only; `python3 -m unittest discover -s tests` green on `python3` and `/usr/bin/python3`, output pristine.
- JS: plain scripts, no build tooling, no npm, no CDN, no network. Everything in `dist/` works opened from `file://` in Chrome on macOS, offline.
- `dist/*.html` are self-contained: no `<script src>`, no `<link href>` to anything, no `url(http…)`. `dist/` is committed (so a presenter only needs the files).
- Chrome binary: `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`, overridable with env `CHROME`; JS tests skip with a message when it is missing.
- Code, identifiers, CLI messages in English; on-screen workshop text, notes and human docs in Rioplatense Spanish.
- On screen the model is «Sonnet 5.5» and the user is «Persona del equipo». No real names, mails, `/Users/…` paths, tokens or keys anywhere in `episodes/`, `dist/` or `demo/`.
- Conventional commits; no AI attribution lines.
- Never write to Jira, Confluence or GitHub; never push.

## Review Focus

1. Jumping backwards or across chapters (`⇧←`, chapter selector) shows the exact finished state of that step, never a half-typed or duplicated line.
2. The stage window was closed or reloaded while the control is open: the control notices, offers to reopen it, and resumes at the same step.
3. Chrome blocks `window.open` when not triggered by a click: opening happens only from a button handler; a test asserts no `window.open` outside it.
4. An episode script with a typo (unknown step type, missing field, unknown screen) fails the build with file, chapter and step index — never a blank stage.
5. Personal data slipping into a `real` capture (home path, user name from `whoami`, git author): capture output is normalised and the privacy check runs on `dist/` too.

---

## File Structure

```
build.py                       # CLI: validate | capture | build | check  (thin, calls ws/)
ws/__init__.py
ws/schema.py                   # episode schema + validate(episode) -> list[str]
ws/privacy.py                  # generic rules + WS_LEAK_TERMS file; scan(paths) -> list[str]
ws/capture.py                  # run `real` term steps in a fake HOME; normalise output
ws/bundle.py                   # inline css/js/episodes into dist/*.html
engine/tokens.css              # all colours/fonts/sizes as custom properties (light Cursor, dark terminal, cards)
engine/screens.css             # cursor-full, cursor-agent, terminal, approval, claude-code, card
engine/nav.js                  # pure navigation: index math, chapter jumps (no DOM)
engine/render.js               # renderStep(container, episode, index) -> pure DOM of the finished state
engine/animate.js              # animate the last step forward (typing, streaming), speed factor
engine/stage.js                # stage page: receives messages, holds state, uses render/animate
engine/control.js              # control page: opens stage, keys, list, mini preview, notes, faq, timer, blackout
engine/stage.html              # template with <!--CSS--> <!--JS--> <!--EPISODES--> slots
engine/control.html            # template, same slots
episodes/cursor/00-antes-de-empezar.json
episodes/cursor/01-inherited-audit.json
episodes/claude-code/.keep
demo/mi-servicio/              # small mock system (see Task 7)
tools/requisitos.sh            # episode 0 checker the attendees run
docs/presentar.md              # how to present, record, Q&A (Spanish)
docs/guion.md                  # how to write an episode script (Spanish)
tests/…                        # one test file per ws module + test_engine.py (headless Chrome)
tests/js/harness.html          # loads engine js + tests/js/*.test.js, prints "JS PASS n FAIL m"
dist/serie-cursor.html  dist/serie-claude-code.html  dist/control.html
```

## Episode Script Format (Interfaces for every task)

```json
{
  "id": "inherited-audit", "series": "cursor", "order": 1,
  "title": "inherited-audit",
  "pitch": {"ask": "Auditá este sistema heredado…", "does": "Fija la base, busca bugs y races, prueba cada uno con un test rojo y entrega dos reportes."},
  "skill": {"repo": "inherited-audit", "commit": "51311c7", "date": "2026-10-19"},
  "workspace": {"repo": "mi-servicio", "files": ["api", "web", "docs", "README.md"], "chats": [{"title": "Agregar endpoint de pagos", "age": "2d"}]},
  "chapters": [
    {"id": "instalar", "title": "Instalar", "subtitle": "Una vez por máquina", "screen": "terminal",
     "faq": [{"q": "¿Y si no tengo Docker?", "a": "…"}],
     "steps": [
       {"type": "term", "cmd": "git clone …", "out": ["…"], "source": "real", "cwd": "~", "notes": "…"},
       {"type": "ask", "text": "…", "source": "inferido", "notes": "…"}
     ]}
  ]
}
```

- `skill.commit` and `skill.date` record which version of the skill the `real` and `inferido` steps were written against (spec: «De dónde salen las salidas»).
- `series`: `cursor | claude-code`. `screen`: `terminal | cursor-full | cursor-agent | claude-code`. Every chapter renders as **its card first** (implicit step 0 of the chapter, not listed in `steps`), then its steps.
- Step types and required fields: `term {cmd, out[]}`, `ask {text}`, `tool {label}` (e.g. `Ran · ia.py baseline`), `say {md}` (tiny markdown: `**b**`, `` `code` ``, `- ` lists, `#### ` heading), `approve {title, lines[], button}` (macOS approval window overlay), `worked {seconds}`. Every step: `source: real|inferido` (required), optional `notes`, optional `pause` (bool, autoplay stops after it).
- `real` term steps also need `cwd` relative to `demo/` or `~` (the fake HOME).
- Global index: the flattened list of (chapter card + its steps) across the episode; `nav.js` owns the mapping.
- Messages control → stage: `{type: "show", episode: id, index: n, animate: bool, speed: number}`, `{type: "blackout", on: bool}`, `{type: "ping"}`; stage → control: `{type: "ready"}`, `{type: "shown", episode, index}`, `{type: "done-animating", index}`, `{type: "pong"}`. Always `postMessage(msg, "*")` (file:// origins are opaque); receivers check `event.source` is the window they opened / their opener.

---

### Task 1: Scaffold, schema and `build.py validate`

**Files:** Create `build.py`, `ws/__init__.py`, `ws/schema.py`, `tests/test_schema.py`, `tests/helpers.py`, `episodes/cursor/`, `episodes/claude-code/.keep`, `README.md` (stub: one paragraph + «en construcción»).

**Interfaces:** Produces `ws.schema.load(path) -> dict`, `ws.schema.validate(episode: dict, where: str) -> list[str]` (messages `"<file> chapter <i> (<id>) step <j>: <problem>"`), `ws.schema.load_all(root: Path) -> list[dict]` sorted by (series, order). `build.py validate` exit 0 / 1 (prints every problem) / 2 usage.

- [ ] **Step 1: Write failing tests** in `tests/test_schema.py`: `test_minimal_episode_is_valid`; `test_unknown_step_type_names_file_chapter_and_step` (asserts message contains `chapter 0 (instalar) step 1` and `unknown step type 'foo'`); `test_missing_required_field_per_type` (subTest over each type with one field dropped); `test_source_required_and_closed_set`; `test_real_term_needs_cwd`; `test_unknown_screen`; `test_series_matches_folder` (an episode under `episodes/cursor/` with `series: claude-code` fails); `test_duplicate_ids_across_files`; `test_chapter_ids_unique_within_episode`; `test_validate_cli_exit_codes` (0 clean tree, 1 with one bad file, 2 bad args).
- [ ] **Step 2:** Run `python3 -m unittest tests.test_schema -v` → FAIL (module missing).
- [ ] **Step 3:** Implement schema as a dict of type → required fields; no third-party validator.
- [ ] **Step 4:** Run both suites → PASS.
- [ ] **Step 5:** Commit `feat: episode script schema and validate command`.

### Task 2: Privacy check

**Files:** Create `ws/privacy.py`, `tests/test_privacy.py`; modify `build.py` (`check` subcommand).

**Interfaces:** `ws.privacy.rules() -> dict[str, re.Pattern]` = generic rules (`/Users/[^/\s]+`, `/home/[^/\s]+`, e-mail addresses except `@example.com`, `ghp_|github_pat_|xox[bp]-|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY`) plus one regex per non-comment line of the file named by env `WS_LEAK_TERMS` (absent → generic only). `scan(paths: list[Path]) -> list[str]` (`"<path>:<line>: <label>: <excerpt>"`, excerpt masked to 20 chars). `build.py check` scans `episodes/`, `demo/`, `dist/`, exit 1 on hits.

- [ ] **Step 1: Failing tests:** each generic rule hits on a crafted line and not on its near-miss (`demo@example.com` passes, `/Users/` alone passes); `test_external_terms_file_adds_patterns`; `test_without_env_only_generic`; `test_check_cli_exit_1_on_hit`; `test_excerpt_never_prints_full_secret`.
- [ ] **Step 2–4:** Run → FAIL; implement; both suites PASS.
- [ ] **Step 5:** Commit `feat: privacy check over episodes, demo and dist`.

### Task 3: Navigation core (`nav.js`) and the JS test harness

**Files:** Create `engine/nav.js`, `tests/js/harness.html`, `tests/js/nav.test.js`, `tests/test_engine.py`.

**Interfaces:** `Nav.flatten(episode) -> [{chapter: i, step: j|-1, kind: "card"|type}]` (`step: -1` = chapter card); `Nav.clamp(ep, i)`; `Nav.nextChapter(ep, i)` → index of the next card (or last index); `Nav.prevChapter(ep, i)` → current chapter's card if `i` is past it, else previous chapter's card; `Nav.position(ep, i) -> {chapter, step, total, chapterTitle}`. Harness: a page that loads the listed scripts, runs `test(name, fn)` blocks, and writes `JS PASS n FAIL m` plus failure names into `<pre id=result>`. `test_engine.py` runs Chrome `--headless=new --dump-dom file://…/harness.html?suite=nav`, asserts `FAIL 0` and `PASS ≥ 1`, skips without Chrome.

- [ ] **Step 1:** Write `nav.test.js` cases: flatten counts card+steps; `prevChapter` from mid-chapter goes to that chapter's card, from a card goes to previous card, from first card stays; `nextChapter` from last chapter stays at last index; `clamp` bounds. Write `test_engine.py::test_nav_suite` and `test_harness_reports_failures` (a deliberately failing fixture suite reports `FAIL 1`).
- [ ] **Step 2–4:** FAIL → implement → PASS (both Pythons).
- [ ] **Step 5:** Commit `feat: pure navigation core and headless JS test harness`.

### Task 4: Screens and static render (`render.js`, CSS)

**Files:** Create `engine/tokens.css`, `engine/screens.css`, `engine/render.js`, `tests/js/render.test.js`; modify `tests/test_engine.py`.

**Interfaces:** `Render.step(container, episode, index)` replaces `container`'s content with the **finished** state of `index`: for a card, the chapter card (gradient, «<skill> · <n> de <total>», title, subtitle); otherwise the chapter's screen with every step of that chapter up to `index` applied. Screens follow the approved mockups and the spec's «Pantallas»: `cursor-full` (sidebar with New Chat/Search/Automations/Customize and `workspace.repo` + chats, the current chat titled after the chapter; conversation; «Send follow-up» + `Sonnet 5.5 ⌄`; footer `main ⌄` / `This Mac ⌄`; right panel tabs README.md/Changes/Browser/Canvas, file tree from `workspace.files`, integrated `zsh` showing `term` steps), `cursor-agent` (same without right panel, with the «Open Tabs» column), `terminal` (dark, no tabs, segmented prompt: apple, folder, branch, dotted fill, `system`, time), `claude-code` (terminal theme, Claude Code transcript layout: `> ` user lines, `⏺` tool and answer lines), `approve` (centered macOS dialog overlay with title, lines, **Cancelar** and the step's `button`). Every colour, font and size in `tokens.css` custom properties (spec: easy to change when Cursor changes). Prompt time is a fixed `11:30` (deterministic captures). User label «Persona del equipo», model «Sonnet 5.5».

- [ ] **Step 1: Failing tests** (`render.test.js`, run through `test_engine.py`): rendering index of a card shows the title and «n de total»; a `cursor-full` chapter at its 3rd step shows exactly 3 step nodes in order; going back (render i then i-2) leaves exactly i-2 steps (no residue); a `term` step on `cursor-full` appears in the integrated zsh, on `terminal` in the main area; `approve` renders an overlay with both buttons; `say` markdown renders `<strong>`, `<code>`, `<li>`; text is inserted as text (a step containing `<script>` renders literally — `textContent`, never `innerHTML` for script data); no element contains a real name (assert the user label).
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** Open `tests/js/render-preview.html` (a page rendering each screen of a fixture episode side by side) in Chrome and compare against `docs/maquetas/pantallas.html` and the references if present; adjust tokens. Record in the commit body what was checked.
- [ ] **Step 6:** Commit `feat: stage screens rendered as a pure function of the step index`.

### Task 5: Animation and playback

**Files:** Create `engine/animate.js`, `tests/js/animate.test.js`; modify `tests/test_engine.py`.

**Interfaces:** `Animate.run(container, episode, index, {speed, now, schedule}) -> {cancel(), done: Promise}` animates only the step at `index` on top of `Render.step(container, episode, index - 1)`; `term.cmd` and `ask.text` type character by character (base 28 ms/char ÷ speed), `term.out` lines and `say` blocks appear line by line (base 120 ms/line ÷ speed), `tool` and `worked` appear at once after 250 ms, `approve` fades in. `schedule` and `now` are injectable so tests run without real time. `cancel()` leaves the container exactly in `Render.step(…, index)` state. Autoplay delay between steps: 900 ms ÷ speed; it stops at the end of a chapter's last step and after any step with `pause: true`.

- [ ] **Step 1: Failing tests:** with a fake scheduler, after all ticks the DOM equals `Render.step(index)` (compare `innerHTML`); `cancel()` midway yields the same final DOM; speed 2 halves the number of scheduled ms; autoplay stops at chapter end and at `pause`.
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** Commit `feat: step animation with injectable clock and cancel-to-final-state`.

### Task 6: Stage page, control page and the message protocol

**Files:** Create `engine/stage.html`, `engine/stage.js`, `engine/control.html`, `engine/control.js`, `tests/js/protocol.test.js`; modify `tests/test_engine.py`.

**Interfaces:** Stage: listens for the messages in «Episode Script Format»; on `show` cancels any running animation, then animates (if `animate` and index = current+1) or renders the finished state; replies `shown`, then `done-animating`; `blackout` toggles a full black layer; answers `ping`; sends `ready` to `window.opener` on load. Control (layout of `docs/maquetas/control.html`): episode and chapter selectors, chapter list with times (elapsed per chapter while playing), steps of the current chapter with `▶`, a mini preview rendered locally with `Render.step` scaled down (no screenshot), «Lo que viene» (next card title or next step label), buttons and keys `⇧←` `←` `space` `→` `⇧→`, speed select (0.5×/1×/1.5×/2×), episode clock, `B` blackout, notes of the current step and FAQ of the current chapter. «Abrir escenario» button is the only caller of `window.open` (target name `ws-stage`, the series' stage file chosen by the episode's `series`). Every 2 s the control pings; no `pong` in 5 s → banner «El escenario se cerró» with «Reabrir», which reopens and resends the current `show`.

- [ ] **Step 1: Failing tests:** protocol logic is in pure functions tested in the harness (`Control.reduce(state, key|message) -> {state, outbox}`): `→` from a card emits `show animate:true`; `←` emits `show animate:false`; `space` toggles play and, when playing, `done-animating` schedules the next `show`; `⇧→/⇧←` use `Nav`; missing pong after 5 s sets `stageLost`; switching episode across series changes the stage file; `test_engine.py::test_window_open_only_in_click_handler` greps `engine/control.js` and asserts exactly one `window.open(` inside the function bound to the «Abrir escenario» button. The notes panel shows each step's `source` (`real` / `inferido`) and the episode's `skill.commit`; the stage never does.
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5: Manual check:** open the built files (Task 8) in Chrome, run an episode end to end with keys, close the stage mid-way and reopen. Record the result in the task report.
- [ ] **Step 6:** Commit `feat: stage and presenter control driven over postMessage`.

### Task 7: Demo project and `real` capture

**Files:** Create `demo/mi-servicio/` (built by `demo/setup.sh <dir>` like inherited-audit's `docs/img/src/demo/setup.sh`: a small Python API with 2–3 seeded bugs, one race-prone counter, a passing unit test suite, fixed git author `Demo <demo@example.com>` and dates), `ws/capture.py`, `tests/test_capture.py`; modify `build.py` (`capture [--episode ID]`).

**Interfaces:** `capture.run(episode, demo_root: Path, home: Path) -> episode'` re-runs every `term` step with `source: real` (bash, `cwd` resolved under the fake HOME or the built demo, env `HOME`, `NO_COLOR=1`, `LANG=C.UTF-8`, `GIT_*` demo identity), replaces `out` with stdout+stderr lines, normalises the fake HOME to `~` and the temp root to `~`, strips ANSI, and writes the episode back keeping key order. Steps not `real` are untouched. Non-zero exit is kept as an extra line `# exit N` (as in hdoc captures).

- [ ] **Step 1: Failing tests:** a fixture episode with one `real` step (`echo $HOME/x`) captures `~/x`; ANSI stripped; `inferido` untouched; exit code line; `whoami`-style leak is caught by `privacy.scan` on the result (test runs capture then scan and asserts the fixture's fake user name is normalised); `setup.sh` builds a repo whose test suite passes (`python3 -m unittest` inside it, exit 0).
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** Commit `feat: demo system and capture of real terminal steps`.

### Task 8: Bundle into `dist/`

**Files:** Create `ws/bundle.py`, `tests/test_bundle.py`, `dist/`; modify `build.py` (`build` = validate + bundle + check).

**Interfaces:** `bundle.build(root: Path) -> list[Path]` writes `dist/serie-cursor.html`, `dist/serie-claude-code.html` (each with only its series' episodes) and `dist/control.html` (all episodes, notes and FAQ), filling the `<!--CSS-->`, `<!--JS-->`, `<!--EPISODES-->` slots; episodes embedded as `<script type="application/json" id="episodes">` with `</` escaped. Output is deterministic (same input → byte-identical).

- [ ] **Step 1: Failing tests:** no `src=`, `href=` (except `#…`), `url(http` in any dist file; stage file contains only its series; control contains both; `</script>` inside a step text does not break the page (JSON parses back equal); two builds are byte-identical; `build.py build` exits 1 when validate or check fails and writes nothing.
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** Commit `feat: self-contained dist bundles for both series and the control`.

### Task 9: Episode 0 «Antes de empezar» and the requirements checker

**Files:** Create `tools/requisitos.sh`, `tests/test_requisitos.py`, `episodes/cursor/00-antes-de-empezar.json`.

**Interfaces:** `tools/requisitos.sh` (bash, macOS) checks, in order, `brew`, `git`, `python3 ≥ 3.9`, `uv`, `tmux`, `jq`, Cursor (`/Applications/Cursor.app` or `cursor` on PATH), an SSH key that GitHub accepts (`ssh -T git@github.com` greeting), and read access to one org repo given by `--repo OWNER/NAME` (`git ls-remote`); prints one `✓`/`✗` line per item with a one-line Spanish fix for each `✗`; exit 0 all ok, 1 something missing. `--offline` skips the two network checks. Episode 0 chapters: «Qué necesitás» (card + `say` list), «Verificarlo» (terminal: download/run the checker, real capture with everything ✓ in the demo HOME using `--offline`), «Si falta algo» (inferido: one ✗ example and its fix), «Cierre»; plus FAQ. The invitation text for attendees lives in the episode notes of the last chapter.

- [ ] **Step 1: Failing tests:** with a fake PATH of stub binaries the checker prints all ✓ and exits 0; removing `uv` prints one ✗ with its fix and exits 1; `--offline` never calls `ssh` or `git ls-remote` (stubs record calls); episode 0 validates.
- [ ] **Step 2–4:** FAIL → implement → PASS; `build.py capture --episode antes-de-empezar` then `build.py build`.
- [ ] **Step 5:** Commit `feat: episode 0 and the requirements checker`.

### Task 10: Pilot episode — inherited-audit

**Files:** Create `episodes/cursor/01-inherited-audit.json`; extend `demo/setup.sh` only if the pilot needs it.

Source: `Harness/inherited-audit` at the commit the episode records (`git -C … rev-parse --short HEAD` on `publish`): `README.md` («Le decís al agente…» table → `pitch`), `docs/instalacion.md` (install chapter, prompts), `docs/showcase.md` (main case + every other case, in order), `docs/instalacion.md` «Si algo falla». Chapters per the spec's «Estructura fija». Terminal steps that the skill's CLI can run on the demo (`init`, `detect`, `baseline`, `status`, `cite-check`, `filter`, `render`) are `real` and captured; agent conversation steps are `inferido` from SKILL.md and the pass prompts, written as Sonnet 5.5 would answer in Cursor, short. Notes per step say what to stress and why; FAQ per chapter 2–4 entries.

- [ ] **Step 1:** Write the script; `build.py validate` exit 0.
- [ ] **Step 2:** `build.py capture --episode inherited-audit`, then `build.py build` (includes privacy check) exit 0.
- [ ] **Step 3:** Play it end to end in Chrome with the control at 1×; record total time per chapter in the task report (target 6–12 min total) and adjust step text if it overshoots.
- [ ] **Step 4:** Commit `feat: pilot episode inherited-audit`.

### Task 11: Presenter and author docs

**Files:** Create `docs/presentar.md`, `docs/guion.md`; replace `README.md`.

- `docs/presentar.md` (Spanish): abrir `dist/control.html`, «Abrir escenario», compartir solo la ventana del escenario en Meet, grabar con OBS o con la grabación de macOS (elegir la ventana), teclas, `B` durante preguntas, qué hacer si el escenario se cierra.
- `docs/guion.md` (Spanish): el formato de guion con un ejemplo mínimo, `real` vs `inferido`, cómo correr `capture`, `build`, `check` con `WS_LEAK_TERMS`, y cómo sacar un episodio del showcase de una skill.
- `README.md`: qué es, cómo se presenta (link), cómo se agrega un episodio (link), desarrollo (los dos `unittest`, Chrome para los tests JS), y la lista de episodios con su estado.
- [ ] **Step 1:** Write; check every relative link resolves (`tests/test_docs.py::test_relative_links_resolve`, written first, failing on a broken fixture link).
- [ ] **Step 2:** Both suites PASS; commit `docs: presenting and authoring guides`.
- [ ] **Step 3:** Propose to the person the one-line entry for `Harness/skills-workshop/` in `SPECKIT/AGENTS.md` («código propio que se desarrolla»); show the diff, do not commit it there without their yes.

---

## Gate after this plan

Stop and hand the pilot to the person: `dist/control.html` + the episode-0 and inherited-audit episodes. Their review of tone, length, notes and screen fidelity decides Plan 2 (the remaining episodes), which reuses Task 10 as its template.
