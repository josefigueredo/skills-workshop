# Skills Workshop — Remaining Episodes Implementation Plan (Plan 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Script, capture and build the remaining nine episodes of both series. Before that, add the two small engine changes those episodes need: skill repos in more than one place, and several episodes from one monorepo.

**Architecture:** Each episode is one JSON file under `episodes/<series>/`. It is scaffolded with `build.py new`, filled in from the skill's own docs at a pinned commit on its default branch, captured with `build.py capture` (offline `real` steps only) and bundled into `dist/` by `build.py build`. The engine and the screens already exist (Plan 1). The Claude Code screen gets its first real episode here, so its fidelity fixes are in scope for that task.

**Tech Stack:** Python 3.9+ stdlib, vanilla JS, headless Chrome for JS tests (as in Plan 1).

**Spec:** `docs/specs/2026-10-19-taller-skills-design.md` (binding). Episode authoring guide: `docs/guion.md`. Reference episode: `episodes/cursor/01-inherited-audit.json` (approved by the person: tone, length, notes and faq are the bar).

## Global Constraints

- Everything in Plan 1's Global Constraints still holds (`docs/plans/2026-10-19-taller-motor-y-piloto.md`).
- **Fixed episode structure** (spec): pitch card · instalar · caso principal · otro caso · si algo falla · cierre (what you take away, and the next episode). Duration between 6 and 12 minutes: the on-screen estimate plus narration at about 150 words per minute over `notes`.
- **One episode per skill repo.** jira-team-kit (4 skills) and WayOfWork (7 skills) also fit in one each: the main case covers the core flow, and the other skills get one short chapter. Splitting into two episodes is allowed only if the core flow alone runs past 12 minutes; the implementer records it in the report.
- **Sources:**
  - Read the skill's `README.md`, `docs/showcase.md`, `docs/instalacion.md`, `docs/instalacion-detallada.md`, `docs/referencia.md` and `SKILL.md`(s) **at the pinned commit**, with `git -C <repo> show <commit>:<path>`. Never read the working tree: several checkouts are on other branches or dirty.
  - What the agent says on screen must agree with the `SKILL.md` at that commit.
- **`real` vs `inferido`:**
  - `real` only for commands that run offline in the capture's fake HOME.
  - Anything that writes to Jira, Confluence or GitHub, or opens a macOS approval window, is `inferido`, and the window is shown with an `approve` step. That covers `jtk … --apply`, `jtk apply`, `ctk apply`, `ctk grant`, `wow … --apply`, `arq … --apply` and any push.
  - Never put those commands in a `real` step, because capture runs `real` steps for real.
- **On screen:** the model is «Sonnet 5.5», the user is «Persona del equipo», the demo repo is `mi-servicio`, and the hostname is `mi-mac`. No real names, Jira keys of real projects, URLs of real tenants, tokens or `/Users/…` paths. Use invented keys like `PLAT-123`, `PRY-2026-0042`.
- **Privacy:**
  - `WS_LEAK_TERMS=<file> python3 build.py check` must pass before every commit that touches `episodes/` or `dist/`.
  - The leak file is never printed, quoted or copied. Only its path is passed.
- **Pins:** the pinned skill commits (table below) are on each repo's default branch, measured on 2026-10-19 with `git fetch` and `origin/HEAD`. Do not re-pin to a working-tree HEAD.
- **No publishing:**
  - Every episode commit goes on branch `feat/episodios`.
  - Never push, never merge.
  - The person reviews the batch before it reaches `main`, because pushing to main publishes the site.
- Conventional commits, no AI attribution lines. Human text in Rioplatense Spanish; code in English.

## Episodes, order and pins

The spec leaves the order to the plan. This is the ruling: the skills that use the macOS approval window go together, then the repo tools, then arq-review. Each «Cierre» names the next row. The last Cursor episode points to the Claude Code series, and the last Claude Code episode closes the workshop.

| Series | # | Episode id | `skill.repo` (local dir under a skills root) | Commit | Notes |
|---|---|---|---|---|---|
| cursor | 02 | `jira-team-kit` | `jira-kanban` (remote `jira-team-kit`; `~/.agents/skills/jira-team-kit` is a symlink to it) | `93a6126` | 4 skills, approval window |
| cursor | 03 | `confluence-team-kit` | `confluence-team-kit` | `f432c40` | MCP, approval window |
| cursor | 04 | `product-brain-mcp` | `product-brain-mcp` | `64d7721` | MCP, approval window |
| cursor | 05 | `auditing-repos` | `teamwayofwork` (skill in `skills/auditing-repos`) | `a0bc150` | monorepo |
| cursor | 06 | `local-board-skill` | `teamwayofwork` (`skills/local-board-skill`) | `a0bc150` | monorepo |
| cursor | 07 | `install-unified-ci` | `teamwayofwork` (`skills/install-unified-ci`) | `a0bc150` | monorepo |
| cursor | 08 | `arq-review` | `arq-review` | `acd5d98` | harness-docs cleanup already merged (PR #2) |
| claude-code | 01 | `wayofwork` | `WayOfWork` | `739b578` | 7 skills; first real Claude Code screen |
| claude-code | 02 | `run-in-cursor` | `run-in-cursor` | `c485a7b` | |

Skills roots: `Harness/` (the default, next to this repo) and `~/CurrentCode` (for the monorepo). Capture reaches both via `WS_SKILLS_ROOT="$HOME/CurrentCode/SPECKIT/Harness:$HOME/CurrentCode"` after Task 1.

## Review Focus

1. **An episode promises an install step that fails for a non-technical person.** Each install chapter follows the skill's `instalacion.md` at the pinned commit. Where that guide needs `uv`, `mcp.json`, tmux, symlinks or SSH, the episode explains it or points to episode 0. It never skips it.
2. **The agent on screen does something the skill forbids or doesn't do.** Example: it runs an `--apply` itself, when the user always runs it with `!`. The task reviewer checks each `ask`/`say`/`tool` against the `SKILL.md`.
3. **A `real` step that needs the network, credentials or a GUI.** Capture fails or, worse, captures an error. Every `real` step must capture cleanly with no network, in the fake HOME.
4. **The «Cierre» chain is broken or the order is inconsistent with the table.** The final task asserts it with a test.
5. **Real data in the monorepo episodes.** `teamwayofwork` belongs to another org (josefigueredo), and its docs may carry real squad, repo or tenant names. Keep them off screen and check with `check`.

---

### Task 1: Engine — several skills roots, `--id` for monorepo episodes, duration report

**Files:**
- Modify: `ws/capture.py` (`skills_root` → `skill_source`), `ws/scaffold.py`, `build.py`
- Create: `ws/duration.py` (or a function in `ws/bundle.py` if smaller)
- Test: `tests/test_capture.py`, `tests/test_scaffold.py`, `tests/test_build_cli.py` (whichever hold the current tests for those modules)
- Docs: `docs/guion.md` (sections «Sumar una skill nueva» and «Cuánto dura»)

**Interfaces:**
- Produces:
  - `capture.skill_source(root: Path, repo: str) -> Path`: the first `<dir>/<repo>` with a git dir across `WS_SKILLS_ROOT` split on `os.pathsep`, else the default `root.parent/<repo>`. `prepare_home` and `scaffold.skill_commit` use it, and the CaptureError message lists every root it tried.
  - `build.py new <repo> [--id ID] [--series S] [--order N]`: the id defaults to `<repo>`, and the file is `NN-<id>.json`. The duplicate check is on the id.
  - `build.py duration [--episode ID]`: one line per episode and per chapter, `screen m:ss · narración m:ss · total m:ss`. The screen time comes from the engine's own `Animate.episodeDuration` and per-chapter equivalent, run in headless Chrome (reuse the JS test runner's Chrome plumbing), so Python never re-implements timing. Narration is the word count of `notes` at 150 words per minute. Exit 1 when an episode's total falls outside 6–12 min, with that episode named. Skip with a clear message and exit 0 when Chrome is missing.

- [ ] **Step 1: Write failing tests.**
  - `skill_source`: two temp roots, repo only in the second, returns the second. The repo is in both, returns the first. `WS_SKILLS_ROOT` unset, returns the parent of root.
  - `create(..., id="auditing-repos")` with `repo="teamwayofwork"` writes `NN-auditing-repos.json` with `id` auditing-repos and `skill.repo` the monorepo. A second `create` with a new id from the same repo succeeds. A duplicate id raises ScaffoldError.
  - `duration` on the two existing episodes prints two episode lines, and exits 0 for both. If 01 measures outside the range, report it and do not change the threshold.
- [ ] **Step 2: Run the tests and see them fail.**
- [ ] **Step 3: Implement. Run both Pythons; every test is green.**
- [ ] **Step 4: Docs.** In `docs/guion.md`, cover `--id` for monorepos, a `WS_SKILLS_ROOT` with several folders, and `build.py duration`.
- [ ] **Step 5: Commit** `feat: skills from several roots, --id for monorepo episodes, duration report`.

### Episode task template (Tasks 2–10)

Every episode task follows these steps. Its own section only names the episode, the pins and what is particular to it.

- [ ] **Step 1: Read the sources at the pin.** See the Sources rule above. Note the install commands, the main flow from the showcase, one other case, and the failure modes from the detailed install guide or the reference.
- [ ] **Step 2: Scaffold.** `python3 build.py new <repo> --id <id> --series <series> --order <N>`. Then set `skill.commit` to the pin.
- [ ] **Step 3: Write the episode.**
  - Fill every COMPLETAR, following `docs/guion.md` and matching the reference episode's density: notes say what to stress and why, and 2–4 faq per chapter.
  - Pick the screens:
    - `terminal` for the install;
    - `cursor-full` for the main case in the Cursor series;
    - `cursor-agent` for the other cases;
    - `claude-code` for the Claude Code series.
  - Steps that need a hand-off from the user (`!` commands, approval windows) show the user doing it.
- [ ] **Step 4: Demo state.** If `real` steps need state beyond `mi-servicio`, add `demo/prep/<id>.sh`, modelled on `demo/prep/inherited-audit.sh`. Otherwise mark those steps `inferido`.
- [ ] **Step 5: Capture and build.**
  - Capture: `WS_SKILLS_ROOT=… python3 build.py capture --episode <id>`, then `python3 build.py validate`.
  - Build and check: `python3 build.py build`, then `WS_LEAK_TERMS=… python3 build.py check`.
  - Duration: run `python3 build.py duration --episode <id>` and confirm it falls within 6–12 min.
- [ ] **Step 6: Visual check.** Take headless Chrome screenshots (`--window-size=1600,900`) of `dist/serie-<series>.html#<id>/<N>` for the pitch card, one step per screen used, and the approval window if any. Save them to the scratchpad dir given in the dispatch, never into the repo, and look at them.
- [ ] **Step 7: Fix the «Cierre» of the previous episode** if it doesn't name this one, so the chain matches the table.
- [ ] **Step 8: Run both suites, then commit** `feat(episodes): <id>`, plus `dist/`.

### Task 2: cursor 02 · jira-team-kit
`jira-kanban` @ `93a6126`. Four skills.
- The main case is creating an epic and its tickets from the conversation, ending in the `jtk` approval window (**Cancelar** / **Apruebo <n>**) shown as an `approve` step.
- The other case is one of the remaining skills, and one short chapter lists what the others do.
- `jtk plan` only reads Jira: it can be shown, but it is `inferido` because capture has no Jira.
- The inherited-audit «Cierre» already names jira-team-kit, so leave it as it is.

### Task 3: cursor 03 · confluence-team-kit
`confluence-team-kit` @ `f432c40`.
- The install includes the MCP setup from its guide.
- The main case is `ctk plan` → `ctk diff` → `ctk apply` with the approval window.
- `ctk ci` is CI only: mention it, never simulate it.

### Task 4: cursor 04 · product-brain-mcp
`product-brain-mcp` @ `64d7721`.
- The install includes `uv` and the MCP config from its guide. Python 3.12 is required, so say so.
- Follow its showcase/tutorial for the main case.

### Task 5: cursor 05 · auditing-repos
`teamwayofwork` @ `a0bc150`, skill dir `skills/auditing-repos`, id `auditing-repos`.
- This is the first monorepo episode, so it exercises Task 1's `--id` and multi-root capture.

### Task 6: cursor 06 · local-board-skill
`teamwayofwork` @ `a0bc150`, `skills/local-board-skill`.

### Task 7: cursor 07 · install-unified-ci
`teamwayofwork` @ `a0bc150`, `skills/install-unified-ci`.
- Anything that pushes or opens PRs is `inferido`.

### Task 8: cursor 08 · arq-review
`arq-review` @ `acd5d98`. Two skills, `arq-manager` and `arq-architect`, used from a reviews repo.
- The demo needs a reviews-repo stand-in: a `demo/prep/arq-review.sh` that builds `~/arq-reviews` with one invented `PRY-2026-0042` request, if `real` steps need it.
- `arq … --apply` is the user's `!` command, so it is `inferido`.
- The «Cierre» points to the Claude Code series.

### Task 9: claude-code 01 · wayofwork
`WayOfWork` @ `739b578`. This is the first episode on the `claude-code` screen.
- **Screen fidelity first.**
  - Render one chapter, screenshot it, and compare it with the `cc-*` mockups named in the spec (run-in-session and harness-docs repos, `docs/img/src/cc-*.html` at their default branch). Fix `engine/render.js`/`screens.css`/`tokens.css` gaps under TDD (render tests; keep the pinned counts in `tests/test_engine.py` in sync).
  - Check that an `approve` step renders on the `claude-code` screen. If it does not, implement it only if this episode needs it.
- Content:
  - The main case is `wow-guide` → the core Product Brain + Spec-Kit + Jira flow.
  - One short chapter covers the other `wow-*` skills.
  - `wow … --apply` is always the user's `!`.

### Task 10: claude-code 02 · run-in-cursor
`run-in-cursor` @ `c485a7b`.
- The main case is handing a `/spec-kit.*` command to Cursor from Claude Code, with tmux under the hood. Its install needs tmux, so explain it.
- The «Cierre» closes the workshop.

### Task 11: Series wrap-up

**Files:** `README.md` (episode table with status), `tests/test_episodes.py` (or the existing episode test file), `dist/`.

- [ ] **Step 1: Write a failing test that the «Cierre» chain matches the series order.**
  - Each episode's last chapter's last `say` names the next episode in its series, by title or id.
  - The last Cursor episode names the Claude Code series.
  - The last Claude Code episode names no next episode.
- [ ] **Step 2: Make it pass, if anything is off.**
- [ ] **Step 3: Update the README episode table:** every episode with its series, order and status «en revisión».
- [ ] **Step 4: Final run.**
  - `python3 build.py build` and `check`.
  - `duration` with no `--episode`: every episode is in range.
  - Both suites green.
- [ ] **Step 5: Commit** `docs: episode table and Cierre chain test`.

Stop after the final review. Hand the batch to the person with the preview links and the list of unreviewed episodes. The push is theirs.
