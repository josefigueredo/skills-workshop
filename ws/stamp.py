"""dist/source.sha256: the digest of the episodes a dist/ was built from.

A skill's Pages workflow recomputes it with plain Python (templates/skill-pages.yml) and refuses to publish a dist/
that is older than its episodes. Keep both computations identical: tests/test_skill_root.py runs the template's."""
from __future__ import annotations

import hashlib
from pathlib import Path

FILE = "source.sha256"


def digest(root) -> str:
    """sha256 over every non-hidden file under root/episodes, by relative POSIX path: path, NUL, bytes, NUL."""
    root = Path(root)
    h = hashlib.sha256()
    files = [p for p in (root / "episodes").rglob("*")
             if p.is_file() and not any(part.startswith(".") for part in p.relative_to(root).parts)]
    for p in sorted(files, key=lambda q: q.relative_to(root).as_posix()):
        h.update(p.relative_to(root).as_posix().encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()
