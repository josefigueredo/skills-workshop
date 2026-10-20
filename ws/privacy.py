"""Privacy check: generic leak rules plus an optional external terms file.

The external terms file ($WS_LEAK_TERMS) is a list of real-system names from elsewhere;
some of them are also names of skills this workshop teaches. privacy-allow.txt (repo
root, one name per line, # comments) lists those names: a leak-term hit that lies wholly
inside an allowed name on the same line is dropped. Generic rules are never allowed."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, List

GENERIC = {
    "user-path-mac": r"/Users/[^/\s]+",
    "user-path-linux": r"/home/[^/\s]+",
    # Any address except @example.com and GitHub's SSH transport user (git@github.com,
    # which every clone line carries). The match starts at the whole local part, so
    # the git@github.com exception cannot be dodged by matching from inside a longer name.
    "email": r"(?<![A-Za-z0-9._%+-])(?!git@github\.com(?![A-Za-z0-9-]|\.[A-Za-z0-9]))"
             r"[A-Za-z0-9._%+-]+@(?!example\.com(?![A-Za-z0-9-]|\.[A-Za-z0-9]))"
             r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}",
    "secret": r"ghp_|github_pat_|xox[bp]-|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY",
}

EXCERPT_MAX = 20
ALLOW_FILE = Path(__file__).resolve().parent.parent / "privacy-allow.txt"


def rules() -> Dict[str, "re.Pattern"]:
    """Generic rules plus one `leak-term` regex per line of $WS_LEAK_TERMS."""
    out = {k: re.compile(v) for k, v in GENERIC.items()}
    path = os.environ.get("WS_LEAK_TERMS")
    if not path:
        return out
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError("%s: cannot read leak terms file (%s)" % (path, exc))
    count = 0
    for n, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            rx = re.compile(line, re.IGNORECASE)
        except re.error as exc:
            raise ValueError("%s:%d: invalid regex (%s)" % (path, n, exc))
        # One pattern per line (never joined: inline flags, named groups and
        # backreferences must keep their per-line meaning). Keys after the first
        # carry a `#n` suffix; the reported label is the part before it.
        out["leak-term" if count == 0 else "leak-term#%d" % (count + 1)] = rx
        count += 1
    return out


def allowed() -> List[str]:
    """Names in ALLOW_FILE (missing file: none)."""
    try:
        text = ALLOW_FILE.read_text(encoding="utf-8")
    except OSError:
        return []
    return [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]


def _is_word(c: str) -> bool:
    return c.isalnum() or c == "_"


def _allowed_spans(line: str, names: List[str]) -> List[tuple]:
    low = line.lower()
    spans = []
    for name in names:
        n = name.lower()
        i = low.find(n)
        while i >= 0:
            j = i + len(n)
            # whole identifiers only: `myproduct-brainy` must not be exempt
            if not (i > 0 and _is_word(low[i - 1])) and not (j < len(low) and _is_word(low[j])):
                spans.append((i, j))
            i = low.find(n, i + 1)
    return spans


def _excerpt(line: str, m: "re.Match") -> str:
    """At most EXCERPT_MAX chars of context; the match is masked, never whole."""
    # Some rules match only a prefix (e.g. `ghp_`): widen the masked span to the
    # whole token so its tail never shows up as "context".
    start, end = m.start(), m.end()
    while end < len(line) and line[end] not in " \t\"'`,;)]}>":
        end += 1
    text = line[start:end]
    keep = min(4, max(len(text) - 1, 0))
    masked = text[:keep] + "…"
    room = EXCERPT_MAX - len(masked)
    before = line[max(0, start - room // 2):start]
    after = line[end:end + room - len(before)]
    return (before + masked + after).replace("\t", " ")[:EXCERPT_MAX]


def _files(paths: List[Path]):
    for p in paths:
        p = Path(p)
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file():
                    yield f
        elif p.is_file():
            yield p


def scan_text(text: str, where: str) -> List[str]:
    """Hits in one text as `<where>:<line>: <label>: <excerpt>` (excerpt masked)."""
    rs = rules()
    names = allowed()
    hits: List[str] = []
    for n, line in enumerate(text.splitlines(), 1):
        spans = _allowed_spans(line, names) if names else []
        for label, rx in rs.items():
            for m in rx.finditer(line):
                if label.startswith("leak-term") and any(a <= m.start() and m.end() <= b for a, b in spans):
                    continue
                hits.append("%s:%d: %s: %s" % (where, n, label.split("#")[0], _excerpt(line, m)))
    return hits


def scan(paths: List[Path]) -> List[str]:
    """Return `<path>:<line>: <label>: <excerpt>` for every hit in text files."""
    rules()  # fail fast on an unreadable/invalid leak-terms file, even with nothing to scan
    hits: List[str] = []
    for f in _files(paths):
        try:
            text = f.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        hits.extend(scan_text(text, str(f)))
    return hits
