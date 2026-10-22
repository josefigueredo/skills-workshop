"""Where the engine and the demo live for a given --root.

The root is the content: episodes/<series>/*.json and episodes/pages/. In this workshop it also holds engine/ and
demo/; a skill keeps only its content (in <skill>/workshop/) and borrows them from here."""
from __future__ import annotations

from pathlib import Path

WORKSHOP = Path(__file__).resolve().parent.parent
# skill.repo of the episodes that belong to the workshop itself (antes-de-empezar): build.py sync leaves them alone.
WORKSHOP_REPO = "skills-workshop"


def _own_or_workshop(root, name: str) -> Path:
    own = Path(root) / name
    return own if own.is_dir() else WORKSHOP / name


def engine_dir(root) -> Path:
    return _own_or_workshop(root, "engine")


def demo_dir(root) -> Path:
    return _own_or_workshop(root, "demo")


def workshop_root(root) -> Path:
    """The workshop repo that serves this root: the root itself when it carries an engine, else this one."""
    return Path(root) if (Path(root) / "engine").is_dir() else WORKSHOP
