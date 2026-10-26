"""Episode script schema: plain-dict validation, no third-party validator."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

SERIES = ("cursor", "claude-code")
SCREENS = ("terminal", "cursor-full", "cursor-agent", "claude-code")
SOURCES = ("real", "inferido")

# step type -> {required field: expected python type(s)}
STEP_FIELDS = {
    "term": {"cmd": str, "out": list},
    "ask": {"text": str},
    "tool": {"label": str},
    "say": {"md": str},
    "approve": {"title": str, "button": str},  # plus `lines`, or `src` with the tool's real window page
    "worked": {"seconds": (int, float)},
    "page": {"title": str, "src": str},
    "click": {"target": str},
}
# A click step is the person pressing a button of the Cursor screen; `target` names the button (render.js draws it).
CLICK_TARGETS = ("ide",)
CLICK_SCREENS = ("cursor-full", "cursor-agent")
# A page step shows a real HTML page (episodes/pages/<name>.html) in a browser window; the bundle inlines it.
PAGE_SRC_RE = re.compile(r"^pages/[a-z0-9][a-z0-9-]*\.html$")


# Keys allowed besides the required ones, so a misspelt key fails instead of being ignored.
# `in`, `capture_only`, `real_clock` and `color` are accepted on any step so their own, clearer message reports a misplacement.
STEP_COMMON = ("type", "source", "notes", "pause", "in", "capture_only", "real_clock", "callouts", "color")
STEP_EXTRA = {"term": ("cwd",), "approve": ("lines", "src", "window", "width", "height"), "page": ("capture",)}
TOP_KEYS = ("id", "series", "order", "title", "pitch", "skill", "workspace", "minutes", "chapters")
CHAPTER_KEYS = ("id", "title", "subtitle", "screen", "faq", "steps")
PITCH_KEYS = ("ask", "does")
SKILL_KEYS = ("repo", "commit", "date")
WORKSPACE_KEYS = ("repo", "files", "chats", "model")
FAQ_KEYS = ("q", "a")


def load(path) -> dict:
    """Read one episode script from a JSON file."""
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def episode_files(root: Path):
    base = Path(root) / "episodes"
    if not base.is_dir():
        return []
    return sorted(p for d in sorted(base.iterdir()) if d.is_dir() for p in sorted(d.glob("*.json")))


def load_all(root) -> list:
    """Load every episodes/<series>/*.json under root, sorted by (series, order)."""
    eps = [load(p) for p in episode_files(Path(root))]
    return sorted(eps, key=lambda e: (str(e.get("series")), e.get("order", 0)))


def _check_type(value, expected, label, out):
    ok = isinstance(value, expected) and not isinstance(value, bool)
    if not ok:
        out.append("%s must be %s" % (label, _type_name(expected)))
    return ok


def _type_name(t):
    if t is list:
        return "a list"
    if t is str:
        return "a string"
    if t is dict:
        return "an object"
    return "a number"


def _require(obj, fields, prefix, out):
    """Report missing/mis-typed required fields; return True when all are fine."""
    clean = True
    for name, expected in fields.items():
        if name not in obj:
            out.append("%s: missing '%s'" % (prefix, name))
            clean = False
        elif not _check_type(obj[name], expected, "%s: '%s'" % (prefix, name), out):
            clean = False
    return clean


def _unknown_keys(obj, allowed, prefix, out):
    for key in obj:
        if key not in allowed:
            out.append("%s: unknown key %r" % (prefix, key))


def _home_relative(cwd) -> bool:
    """'~' or '~/<path>' with no '..' segment and no backslash."""
    if not isinstance(cwd, str) or "\\" in cwd:
        return False
    if cwd != "~" and not cwd.startswith("~/"):
        return False
    return ".." not in cwd.split("/")


def _validate_step(step, prefix, out, screen=None):
    if not isinstance(step, dict):
        out.append("%s: step must be an object" % prefix)
        return
    stype = step.get("type")
    if stype not in STEP_FIELDS:
        out.append("%s: unknown step type %r" % (prefix, stype))
        return
    _require(step, STEP_FIELDS[stype], prefix, out)
    _unknown_keys(step, STEP_COMMON + tuple(STEP_FIELDS[stype]) + STEP_EXTRA.get(stype, ()), prefix, out)
    source = step.get("source")
    if "source" not in step:
        out.append("%s: missing 'source'" % prefix)
    elif source not in SOURCES:
        out.append("%s: source must be 'real' or 'inferido'" % prefix)
    if "notes" in step and not isinstance(step["notes"], str):
        out.append("%s: 'notes' must be a string" % prefix)
    if "pause" in step and not isinstance(step["pause"], bool):
        out.append("%s: 'pause' must be true or false" % prefix)
    # `in: "zsh"` marks a term step as a command the person types: in cursor-full it goes to the
    # integrated terminal, in claude-code it is a `!` bash-mode line. Without it the step renders
    # as the agent's command.
    if "in" in step:
        if stype != "term":
            out.append("%s: 'in' is only valid on a term step" % prefix)
        elif step["in"] != "zsh":
            out.append("%s: 'in' must be \"zsh\"" % prefix)
        elif screen not in ("cursor-full", "claude-code"):
            out.append("%s: 'in' \"zsh\" is only valid in a cursor-full or claude-code chapter" % prefix)
    # `capture_only: true` steps only advance the demo state during capture; the bundle
    # drops them, so the stage and the control never see them.
    if "capture_only" in step:
        if step["capture_only"] is not True:
            out.append("%s: 'capture_only' must be true when present" % prefix)
        elif stype != "term" or source != "real":
            out.append("%s: 'capture_only' is only valid on a real term step" % prefix)
    # `real_clock: true` real steps run on the real clock: what compares now with file times needs it.
    if "real_clock" in step:
        if step["real_clock"] is not True:
            out.append("%s: 'real_clock' must be true when present" % prefix)
        elif stype != "term" or source != "real":
            out.append("%s: 'real_clock' is only valid on a real term step" % prefix)
    # `color: true` term steps are captured in a truecolor terminal and keep their SGR colour codes.
    if "color" in step:
        if not isinstance(step["color"], bool):
            out.append("%s: 'color' must be true or false" % prefix)
        elif stype != "term":
            out.append("%s: 'color' is only valid on a term step" % prefix)
    if stype == "approve":
        _validate_approve(step, prefix, out)
    if stype == "click":
        if screen not in CLICK_SCREENS:
            out.append("%s: a click step is only valid in a cursor-full or cursor-agent chapter" % prefix)
        elif isinstance(step.get("target"), str) and step["target"] not in CLICK_TARGETS:
            out.append("%s: 'target' must be one of %s" % (prefix, ", ".join(CLICK_TARGETS)))
    if "callouts" in step:
        _validate_callouts(step, prefix, out)
    if stype in ("page", "approve") and isinstance(step.get("src"), str) and not PAGE_SRC_RE.match(step["src"]):
        out.append("%s: 'src' must be 'pages/<name>.html' (lowercase, under episodes/)" % prefix)
    # `capture: "~/<path>"` on a real page step: capture copies that file, written by the episode's real steps in the
    # fake HOME, to episodes/<src> (normalised and privacy-checked like the steps' output).
    if "capture" in step:
        if source != "real":
            out.append("%s: 'capture' is only valid on a real page step" % prefix)
        elif step["capture"] == "~" or not _home_relative(step["capture"]):
            out.append("%s: 'capture' must be '~/<path>' without '..' (a file in the fake HOME)" % prefix)
    if stype == "term" and source == "real":
        cwd = step.get("cwd")
        if cwd is None:
            out.append("%s: real term step needs 'cwd'" % prefix)
        elif not _home_relative(cwd):
            out.append("%s: 'cwd' must be '~' or '~/<path>' without '..' (relative to the fake HOME)" % prefix)


CALLOUT_KINDS = ("note", "box", "underline")
CALLOUT_KEYS = ("kind", "text", "match")
_INLINE_RE = re.compile(r"(\*\*[^*]+?\*\*|`[^`]+`)")
_SGR_RE = re.compile(r"\x1b\[[0-9;]*m")


def _text_runs(step) -> list:
    """The text runs the stage renders for a step, each one text node: `match` must fall inside one of them."""
    stype = step.get("type")
    if stype == "term":
        cmd = str(step.get("cmd", ""))
        runs = [r for o in step.get("out") or [] for r in _SGR_RE.split(str(o)) if r]
        return [cmd] + runs + ["▸ Ran · " + cmd]
    if stype == "ask":
        return [str(step.get("text", ""))]
    if stype == "tool":
        return [str(step.get("label", "")), "▸ " + str(step.get("label", ""))]
    if stype == "worked":
        return ["Worked for %ss" % step.get("seconds", 0)]
    if stype == "say":
        runs = []
        for line in str(step.get("md", "")).split("\n"):
            line = re.sub(r"^(- |#{2,4} )", "", line.strip())
            for part in _INLINE_RE.split(line):
                if part.startswith("**") and part.endswith("**") and len(part) > 4:
                    part = part[2:-2]
                elif part.startswith("`") and part.endswith("`") and len(part) > 2:
                    part = part[1:-1]
                if part:
                    runs.append(part)
        return runs
    return []


def _validate_callouts(step, prefix, out):
    """`callouts`: visual cues the stage shows while the step is current (render.js applyCallouts)."""
    cos = step["callouts"]
    if not isinstance(cos, list):
        out.append("%s: 'callouts' must be a list" % prefix)
        return
    overlay = step.get("type") in ("page", "approve", "click")
    for i, co in enumerate(cos):
        where = "%s callout %d" % (prefix, i)
        if not isinstance(co, dict):
            out.append("%s: must be an object" % where)
            continue
        bad = sorted(k for k in co if k not in CALLOUT_KEYS)
        kind = co.get("kind")
        if bad:
            out.append("%s: unknown key(s) %s" % (where, ", ".join(bad)))
        elif kind not in CALLOUT_KINDS:
            out.append("%s: kind must be one of %s" % (where, ", ".join(CALLOUT_KINDS)))
        elif overlay and kind != "note":
            out.append("%s: a %s step takes only 'note' callouts (its content is a frame or a button)"
                       % (where, step["type"]))
        elif kind == "note" and not (isinstance(co.get("text"), str) and co["text"].strip()):
            out.append("%s: a note needs 'text'" % where)
        elif kind != "note" and not (isinstance(co.get("match"), str) and co["match"]):
            out.append("%s: a %s needs 'match'" % (where, kind))
        elif "text" in co and not isinstance(co["text"], str):
            out.append("%s: 'text' must be a string" % where)
        elif kind != "note" and not any(co["match"] in r for r in _text_runs(step)):
            out.append("%s: match %r is not in the step's text (it must sit inside one line or one run of "
                       "plain, bold or code text)" % (where, co["match"]))


def _validate_approve(step, prefix, out):
    """An approve step lists `lines`, or shows the tool's real window: `src` (its page, rendered by the tool's own
    code), `window` (the title bar), `width` and `height` (points, as the tool sizes it)."""
    if "lines" in step:
        _check_type(step["lines"], list, "%s: 'lines'" % prefix, out)
    elif "src" not in step:
        out.append("%s: missing 'lines' (or 'src' with the tool's window page)" % prefix)
    if "src" in step:
        _check_type(step["src"], str, "%s: 'src'" % prefix, out)
    if "window" in step:
        _check_type(step["window"], str, "%s: 'window'" % prefix, out)
    for key in ("width", "height"):
        if key in step and _check_type(step[key], int, "%s: '%s'" % (prefix, key), out) \
                and not 100 <= step[key] <= 1200:
            out.append("%s: '%s' must be from 100 to 1200 points" % (prefix, key))


def _validate_chapter(chapter, i, out, where, seen_ids):
    cid = chapter.get("id", "?") if isinstance(chapter, dict) else "?"
    prefix = "%s chapter %d (%s)" % (where, i, cid)
    if not isinstance(chapter, dict):
        out.append("%s: chapter must be an object" % prefix)
        return
    _require(chapter, {"id": str, "title": str, "screen": str, "steps": list}, prefix, out)
    _unknown_keys(chapter, CHAPTER_KEYS, prefix, out)
    if isinstance(chapter.get("id"), str):
        if chapter["id"] in seen_ids:
            out.append("%s: duplicate chapter id %r" % (prefix, chapter["id"]))
        seen_ids.add(chapter["id"])
    if isinstance(chapter.get("screen"), str) and chapter["screen"] not in SCREENS:
        out.append("%s: unknown screen %r" % (prefix, chapter["screen"]))
    # A card names its case: "Otro caso" says nothing on the card nor in an index.
    if isinstance(chapter.get("title"), str) and chapter["title"].strip().lower().startswith("otro caso"):
        out.append("%s: title %r starts with 'Otro caso': name the case (the subtitle usually says it)"
                   % (prefix, chapter["title"]))
    if "subtitle" in chapter and not isinstance(chapter["subtitle"], str):
        out.append("%s: 'subtitle' must be a string" % prefix)
    for k, item in enumerate(chapter.get("faq", []) if isinstance(chapter.get("faq", []), list) else []):
        if not isinstance(item, dict):
            out.append("%s faq %d: must be an object" % (prefix, k))
            continue
        _require(item, {"q": str, "a": str}, "%s faq %d" % (prefix, k), out)
        _unknown_keys(item, FAQ_KEYS, "%s faq %d" % (prefix, k), out)
    if "faq" in chapter and not isinstance(chapter["faq"], list):
        out.append("%s: 'faq' must be a list" % prefix)
    if isinstance(chapter.get("steps"), list):
        for j, step in enumerate(chapter["steps"]):
            _validate_step(step, "%s step %d" % (prefix, j), out, chapter.get("screen"))


def minutes_problem(value) -> str:
    """'' when value is a valid [min, max] in whole minutes (0 < min <= max), else what is wrong."""
    if not (isinstance(value, list) and len(value) == 2
            and all(isinstance(v, int) and not isinstance(v, bool) for v in value)):
        return "must be [min, max] in whole minutes"
    if not 0 < value[0] <= value[1]:
        return "must have 0 < min <= max (got %d-%d)" % tuple(value)
    return ""


def validate(episode: dict, where: str) -> list:
    """Return a list of problems ('<file> chapter <i> (<id>) step <j>: <problem>')."""
    out: list = []
    if not isinstance(episode, dict):
        return ["%s: episode must be an object" % where]
    _require(episode, {"id": str, "series": str, "order": int, "title": str,
                       "pitch": dict, "skill": dict, "workspace": dict, "chapters": list},
             where, out)
    _unknown_keys(episode, TOP_KEYS, where, out)
    if isinstance(episode.get("series"), str) and episode["series"] not in SERIES:
        out.append("%s: unknown series %r (expected one of %s)" % (where, episode["series"], ", ".join(SERIES)))
    if isinstance(episode.get("pitch"), dict):
        _require(episode["pitch"], {"ask": str, "does": str}, "%s: pitch" % where, out)
        _unknown_keys(episode["pitch"], PITCH_KEYS, "%s: pitch" % where, out)
    if isinstance(episode.get("skill"), dict):
        _require(episode["skill"], {"repo": str, "commit": str, "date": str}, "%s: skill" % where, out)
        _unknown_keys(episode["skill"], SKILL_KEYS, "%s: skill" % where, out)
    if isinstance(episode.get("workspace"), dict):
        _require(episode["workspace"], {"repo": str}, "%s: workspace" % where, out)
        _unknown_keys(episode["workspace"], WORKSPACE_KEYS, "%s: workspace" % where, out)
        if "model" in episode["workspace"]:
            _check_type(episode["workspace"]["model"], str, "%s: workspace: 'model'" % where, out)
    if "minutes" in episode and minutes_problem(episode["minutes"]):
        out.append("%s: 'minutes' %s" % (where, minutes_problem(episode["minutes"])))
    chapters = episode.get("chapters")
    if isinstance(chapters, list):
        if not chapters:
            out.append("%s: 'chapters' must not be empty" % where)
        seen: set = set()
        for i, chapter in enumerate(chapters):
            _validate_chapter(chapter, i, out, where, seen)
    return out


def page_steps(episode):
    """Every step that shows a page (a page step, an approve with its window page) with a usable src, in order."""
    for ch in episode.get("chapters") or []:
        for st in (ch.get("steps") or []) if isinstance(ch, dict) else []:
            if isinstance(st, dict) and st.get("type") in ("page", "approve") \
                    and PAGE_SRC_RE.match(str(st.get("src", ""))):
                yield st


def _missing_pages(episode, root: Path, where: str, capturing: bool = False) -> list:
    if not isinstance(episode, dict):
        return []
    return ["%s: episodes/%s does not exist" % (where, st["src"])
            for st in page_steps(episode)
            if not (capturing and "capture" in st) and not (root / "episodes" / st["src"]).is_file()]


INDEX_SRC_RE = re.compile(r"^pages/[a-z0-9-]+-indice\.html$")
_INDEX_TITLE_RE = re.compile(r'class="t">([^<]*)<')


def _index_mismatches(episode, root: Path, where: str) -> list:
    """An index page (pages/<x>-indice.html) lists the chapters after the one that shows it, each title in an
    element of class "t", as their cards say them."""
    out = []
    chapters = [c for c in episode.get("chapters") or [] if isinstance(c, dict)] if isinstance(episode, dict) else []
    for i, chapter in enumerate(chapters):
        for st in chapter.get("steps") or []:
            src = str(st.get("src", "")) if isinstance(st, dict) else ""
            page = root / "episodes" / src
            if st.get("type") != "page" or not INDEX_SRC_RE.match(src) or not page.is_file():
                continue
            listed = [html.unescape(t).strip() for t in _INDEX_TITLE_RE.findall(page.read_text(encoding="utf-8"))]
            cards = [str(c.get("title", "")) for c in chapters[i + 1:]]
            if listed != cards:
                out.append("%s: episodes/%s lists %s, but the cards after it say %s"
                           % (where, src, listed, cards))
    return out


def check_tree(root, capturing: bool = False) -> list:
    """Validate every episode under root/episodes plus cross-file rules.

    capturing: a page that capture is about to write (a page step with `capture`) may not exist yet."""
    out: list = []
    seen: dict = {}
    for path in episode_files(Path(root)):
        where = "%s/%s" % (path.parent.name, path.name)
        try:
            ep = load(path)
        except ValueError as exc:
            out.append("%s: invalid JSON (%s)" % (where, exc))
            continue
        out.extend(validate(ep, where))
        from ws import scaffold  # late: scaffold imports schema

        out.extend(scaffold.pending(ep, where))
        out.extend(_missing_pages(ep, Path(root), where, capturing))
        out.extend(_index_mismatches(ep, Path(root), where))
        if not isinstance(ep, dict):
            continue
        if ep.get("series") != path.parent.name:
            out.append("%s: file is in folder %r but series %r" % (where, path.parent.name, ep.get("series")))
        key = (ep.get("series"), ep.get("id"))
        if key in seen:
            out.append("%s: duplicate episode id %r (also in %s)" % (where, ep.get("id"), seen[key]))
        else:
            seen[key] = where
    return out
