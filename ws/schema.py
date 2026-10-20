"""Episode script schema: plain-dict validation, no third-party validator."""
from __future__ import annotations

import json
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
    "approve": {"title": str, "lines": list, "button": str},
    "worked": {"seconds": (int, float)},
}


# Keys allowed besides the required ones, so a misspelt key fails instead of being ignored.
# `in` and `capture_only` are accepted on any step so their own, clearer message reports a misplacement.
STEP_COMMON = ("type", "source", "notes", "pause", "in", "capture_only")
STEP_EXTRA = {"term": ("cwd",)}
TOP_KEYS = ("id", "series", "order", "title", "pitch", "skill", "workspace", "chapters")
CHAPTER_KEYS = ("id", "title", "subtitle", "screen", "faq", "steps")
PITCH_KEYS = ("ask", "does")
SKILL_KEYS = ("repo", "commit", "date")
WORKSPACE_KEYS = ("repo", "files", "chats")
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
    if stype == "term" and source == "real":
        cwd = step.get("cwd")
        if cwd is None:
            out.append("%s: real term step needs 'cwd'" % prefix)
        elif not _home_relative(cwd):
            out.append("%s: 'cwd' must be '~' or '~/<path>' without '..' (relative to the fake HOME)" % prefix)


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
    chapters = episode.get("chapters")
    if isinstance(chapters, list):
        if not chapters:
            out.append("%s: 'chapters' must not be empty" % where)
        seen: set = set()
        for i, chapter in enumerate(chapters):
            _validate_chapter(chapter, i, out, where, seen)
    return out


def check_tree(root) -> list:
    """Validate every episode under root/episodes plus cross-file rules."""
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
