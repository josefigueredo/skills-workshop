"""`build.py duration`: screen time (the engine's own estimate, run in headless Chrome) plus narration."""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from html import unescape
from pathlib import Path
from typing import Callable, Dict, List, Optional

from ws import bundle, schema
from ws.chrome import chrome_available, chrome_path

ENGINE_SCRIPTS = ("nav.js", "render.js", "animate.js")
WORDS_PER_MINUTE = 150
MIN_MS, MAX_MS = 6 * 60000, 12 * 60000
SPEED = 1  # the engine's normal speed

_PAGE = """<!doctype html><html><head><meta charset="utf-8"></head><body>
<pre id="result">RUNNING</pre>
%(scripts)s
<script>
var EPISODES = JSON.parse(document.getElementById("episodes").textContent);
var out = {};
EPISODES.forEach(function (ep) {
  var d = Animate.episodeDuration(ep, %(speed)d);
  out[ep.id] = {total: d.total, chapters: d.chapters.map(function (c) { return {id: c.id, ms: c.ms}; })};
});
document.getElementById("result").textContent = JSON.stringify(out);
</script>
</body></html>
"""


def narration_words(episode: dict) -> int:
    """Words in every step's `notes`, and nothing else."""
    n = 0
    for ch in episode.get("chapters", []):
        for st in ch.get("steps", []):
            notes = st.get("notes")
            if isinstance(notes, str):
                n += len(notes.split())
    return n


def narration_ms(words: int) -> int:
    return int(round(words * 60000.0 / WORDS_PER_MINUTE))


def fmt(ms: float) -> str:
    secs = int(round(ms / 1000.0))
    return "%d:%02d" % (secs // 60, secs % 60)


def measure(root, episodes: List[dict]) -> Dict[str, dict]:
    """{episode id: {"total": ms, "chapters": [{"id", "ms"}]}} from Animate.episodeDuration in Chrome."""
    engine = Path(root) / "engine"
    scripts = "\n".join('<script src="%s"></script>' % (engine / f).as_uri() for f in ENGINE_SCRIPTS)
    data = '<script type="application/json" id="episodes">%s</script>' % bundle.episodes_json(episodes)
    page = _PAGE % {"scripts": scripts + "\n" + data, "speed": SPEED}
    with tempfile.TemporaryDirectory(prefix="ws-duration-") as tmp:
        html = Path(tmp) / "duration.html"
        html.write_text(page, encoding="utf-8")
        cmd = [chrome_path(), "--headless=new", "--disable-gpu", "--allow-file-access-from-files",
               "--user-data-dir=%s" % (Path(tmp) / "profile"),
               "--virtual-time-budget=5000", "--dump-dom", html.as_uri()]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True, timeout=120)
    m = re.search(r'<pre id="result">(.*?)</pre>', proc.stdout, re.S)
    text = unescape(m.group(1)).strip() if m else ""
    try:
        return json.loads(text)
    except ValueError:
        raise RuntimeError("Chrome did not report durations (got %r)" % text[:200])


def _line(label: str, screen_ms: float, words: int) -> str:
    narr = narration_ms(words)
    return "%s: screen %s · narración %s · total %s" % (label, fmt(screen_ms), fmt(narr), fmt(screen_ms + narr))


def report(root, episode_id: Optional[str] = None, emit: Callable = print,
           measure_fn: Optional[Callable] = None) -> int:
    """Print one line per episode and chapter. 0 ok, 1 an episode outside 6-12 min, 2 unknown id.

    Episodes with `order` 0 (the setup intro) are listed but never fail the range."""
    if not chrome_available():
        emit("duration: skipped, Chrome not found at %s (set CHROME)" % chrome_path())
        return 0
    try:
        episodes = [schema.load(p) for p in schema.episode_files(Path(root))]
        if episode_id is not None:
            episodes = [e for e in episodes if e.get("id") == episode_id]
            if not episodes:
                emit("duration: no episode with id %r" % episode_id)
                return 2
        episodes.sort(key=lambda e: (str(e.get("series")), e.get("order", 0)))
        # What the stage shows: capture_only steps out, pages inlined. Screen and narration use the same steps.
        episodes = [bundle.for_stage(e, root) for e in episodes]
        measured = (measure_fn or measure)(root, episodes)
        rows = []
        for ep in episodes:
            m = measured[ep["id"]]
            words = narration_words(ep)
            if len(m["chapters"]) != len(ep["chapters"]):
                raise RuntimeError("%s has %d chapters but Chrome measured %d"
                                   % (ep["id"], len(ep["chapters"]), len(m["chapters"])))
            chapters = []
            for ch, cm in zip(ep["chapters"], m["chapters"]):
                cw = sum(len(s["notes"].split()) for s in ch["steps"] if isinstance(s.get("notes"), str))
                chapters.append((ch["id"], cm["ms"], cw))
            rows.append((ep, m["total"], words, chapters))
    except (subprocess.SubprocessError, OSError, RuntimeError, ValueError, KeyError, TypeError,
            bundle.BundleError) as exc:
        emit("duration: %s: %s" % (type(exc).__name__, exc))
        return 2
    bad = []
    for ep, screen, words, chapters in rows:
        total = screen + narration_ms(words)
        intro = ep.get("order") == 0
        emit(_line(ep["id"], screen, words) + ("  (setup intro, not range-checked)" if intro else ""))
        for cid, cms, cw in chapters:
            emit("  " + _line(cid, cms, cw))
        if not intro and not (MIN_MS <= total <= MAX_MS):
            bad.append((ep["id"], total))
    for ep_id, total in bad:
        emit("duration: %s is outside 6-12 min (total %s)" % (ep_id, fmt(total)))
    return 1 if bad else 0
