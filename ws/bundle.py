"""Bundle engine templates, CSS, JS and episodes into self-contained dist/*.html."""
from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path
from typing import Dict, List

from ws import schema

CSS_FILES = ("tokens.css", "screens.css")
JS_COMMON = ("nav.js", "render.js", "animate.js")
SLOT_RE = re.compile(r"<!--(CSS|JS|EPISODES|LIST)-->")
# output name -> (template, last script, series kept or None for all)
TARGETS = (
    ("serie-cursor.html", "stage.html", "stage.js", "cursor"),
    ("serie-claude-code.html", "stage.html", "stage.js", "claude-code"),
    ("control.html", "control.html", "control.js", None),
)
SERIES_TITLES = (("cursor", "Serie Cursor"), ("claude-code", "Serie Claude Code"))


class BundleError(Exception):
    """The sources cannot be bundled safely."""


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").replace("\r\n", "\n")
    except OSError as exc:
        raise BundleError("%s: cannot read (%s)" % (path, exc))


def _inline(path: Path, closer: str) -> str:
    text = _read(path)
    if closer in text.lower():
        raise BundleError("%s: contains %s, which would end the inline block" % (path.name, closer))
    return text


def episodes_json(episodes: List[dict]) -> str:
    """JSON array with < > & escaped, so no </script> or <!-- can appear inside it."""
    raw = json.dumps(episodes, ensure_ascii=False, separators=(",", ":"))
    return raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _fill(template: str, slots: Dict[str, str], name: str) -> str:
    found = SLOT_RE.findall(template)
    for slot in slots:
        if found.count(slot) != 1:
            raise BundleError("engine/%s: expected exactly one <!--%s--> slot, found %d"
                              % (name, slot, found.count(slot)))
    # one pass: inlined content is never re-scanned for slots
    return SLOT_RE.sub(lambda m: slots[m.group(1)], template)


def _page(step: dict, root: Path) -> dict:
    """A page step with its HTML inlined in place of its path (the stage cannot read files)."""
    if step.get("type") != "page":
        return step
    out = {k: v for k, v in step.items() if k != "src"}
    out["html"] = _read(Path(root) / "episodes" / step["src"])
    return out


def for_stage(episode: dict, root=None) -> dict:
    """The episode as the stage and the control see it: `capture_only` steps removed
    (they only advance the demo state during capture) and page steps carrying their HTML.
    The source JSON keeps both as they are."""
    out = dict(episode)
    out["chapters"] = []
    for ch in episode.get("chapters", []):
        ch = dict(ch)
        ch["steps"] = [_page(s, root) for s in ch.get("steps", []) if not s.get("capture_only")]
        out["chapters"].append(ch)
    return out


def _chapters_label(n: int) -> str:
    return "1 capítulo" if n == 1 else "%d capítulos" % n


def episode_list(episodes: List[dict]) -> str:
    """The landing page's per-series episode list. Every episode text is HTML-escaped."""
    parts = []
    for series, heading in SERIES_TITLES:
        parts.append("<h2>%s</h2>" % escape(heading))
        mine = [e for e in episodes if e.get("series") == series]
        if not mine:
            parts.append('<p class="empty">Todavía no hay episodios.</p>')
            continue
        parts.append('<ul class="eps">')
        for e in mine:
            href = "serie-%s.html#%s/1" % (series, e["id"])
            parts.append('<li><a href="%s">%s</a><p>%s</p><small>%s</small></li>' % (
                escape(href, quote=True), escape(e["title"]), escape(e["pitch"]["does"]),
                _chapters_label(len(e["chapters"]))))
        parts.append("</ul>")
    return "\n  ".join(parts)


def render(root) -> Dict[str, str]:
    """Build every dist file in memory: {file name: html}. Writes nothing."""
    root = Path(root)
    engine = root / "engine"
    episodes = [for_stage(e, root) for e in schema.load_all(root)]
    css = "<style>\n" + "\n".join(_inline(engine / f, "</style") for f in CSS_FILES) + "\n</style>"
    out: Dict[str, str] = {}
    for name, template, last, series in TARGETS:
        scripts = "\n".join("<script>\n%s\n</script>" % _inline(engine / f, "</script")
                            for f in JS_COMMON + (last,))
        chosen = [e for e in episodes if series is None or e.get("series") == series]
        data = '<script type="application/json" id="episodes">%s</script>' % episodes_json(chosen)
        html = _fill(_read(engine / template), {"CSS": css, "JS": scripts, "EPISODES": data}, template)
        out[name] = html
    tokens = "<style>\n%s\n</style>" % _inline(engine / CSS_FILES[0], "</style")
    out["index.html"] = _fill(_read(engine / "index.html"),
                              {"CSS": tokens, "LIST": episode_list(episodes)}, "index.html")
    return out


def write(root, rendered: Dict[str, str]) -> List[Path]:
    dist = Path(root) / "dist"
    dist.mkdir(exist_ok=True)
    paths = []
    for name in rendered:
        p = dist / name
        p.write_bytes(rendered[name].encode("utf-8"))
        paths.append(p)
    return paths


def build(root) -> List[Path]:
    """Write dist/serie-*.html, control.html and the landing page index.html."""
    return write(root, render(root))
