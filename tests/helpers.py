"""Shared test helpers: an episode factory and a temp episodes tree."""
from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def minimal_episode(**over):
    """A valid episode with one chapter holding one step of every type."""
    ep = {
        "id": "demo",
        "series": "cursor",
        "order": 1,
        "title": "demo",
        "pitch": {"ask": "Pedido de ejemplo", "does": "Hace algo."},
        "skill": {"repo": "demo-skill", "commit": "abc1234", "date": "2026-10-19"},
        "workspace": {"repo": "mi-servicio"},
        "chapters": [
            {
                "id": "instalar",
                "title": "Instalar",
                "screen": "terminal",
                "steps": [
                    {"type": "term", "cmd": "ls", "out": ["a"], "source": "real", "cwd": "~"},
                    {"type": "ask", "text": "Hola", "source": "inferido"},
                    {"type": "tool", "label": "Ran · x", "source": "inferido"},
                    {"type": "say", "md": "**ok**", "source": "inferido"},
                    {"type": "approve", "title": "T", "lines": ["l"], "button": "Apruebo 1",
                     "source": "inferido"},
                    {"type": "worked", "seconds": 3, "source": "inferido"},
                ],
            }
        ],
    }
    ep = copy.deepcopy(ep)
    ep.update(over)
    return ep


class TempTree:
    """A temporary repo root with an episodes/ folder; use as a context manager."""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "episodes").mkdir()

    def write(self, series_dir, name, episode):
        d = self.root / "episodes" / series_dir
        d.mkdir(parents=True, exist_ok=True)
        p = d / name
        p.write_text(json.dumps(episode), encoding="utf-8")
        return p

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._tmp.cleanup()
