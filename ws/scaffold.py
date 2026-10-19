"""`build.py new`: a valid episode skeleton, and the COMPLETAR gate that keeps it out of dist."""
from __future__ import annotations

import datetime
import json
import re
import subprocess
from pathlib import Path
from typing import List, Optional

from ws import capture, schema

MARK = "COMPLETAR"
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


class ScaffoldError(Exception):
    """The skeleton cannot be written (bad name, clash with an existing episode)."""


def _faq(topic: str) -> list:
    return [{"q": "%s: pregunta frecuente %d sobre %s" % (MARK, n, topic), "a": "%s: respuesta corta" % MARK}
            for n in (1, 2)]


def _step(kind: str, what: str) -> dict:
    text = "%s: %s" % (MARK, what)
    base = {"source": "inferido", "notes": MARK}
    if kind == "term":
        return dict({"type": "term", "cmd": text, "out": ["%s: salida del comando" % MARK]}, **base)
    if kind == "ask":
        return dict({"type": "ask", "text": text}, **base)
    return dict({"type": "say", "md": text}, **base)


def _chapter(cid: str, title: str, screen: str, steps: list) -> dict:
    return {"id": cid, "title": title, "subtitle": "%s: una línea que ubique el capítulo" % MARK,
            "screen": screen, "faq": _faq(title.lower()), "steps": steps}


def skeleton(repo: str, series: str, order: int, commit: str, date: str, id: Optional[str] = None) -> dict:
    """The fixed episode structure of the design spec, every text a COMPLETAR placeholder."""
    return {
        "id": id or repo, "series": series, "order": order, "title": id or repo,
        "pitch": {"ask": "%s: lo que le decís al agente (README de la skill)" % MARK,
                  "does": "%s: lo que hace la skill (README de la skill)" % MARK},
        "skill": {"repo": repo, "commit": commit, "date": date},
        "workspace": {"repo": "mi-servicio"},
        "chapters": [
            _chapter("instalar", "Instalar", "terminal",
                     [_step("term", "comando de instalación (instalacion.md de la skill)")]),
            _chapter("caso-principal", "Caso principal", "cursor-full",
                     [_step("ask", "lo que la persona le pide al agente"),
                      _step("say", "la respuesta del agente, de punta a punta, hasta el resultado")]),
            _chapter("otro-caso", "Otro caso", "cursor-agent",
                     [_step("ask", "otro pedido típico"), _step("say", "la respuesta del agente")]),
            _chapter("si-algo-falla", "Si algo falla", "terminal",
                     [_step("term", "comando que falla o lo diagnostica (sección «Si algo falla» de instalacion.md)")]),
            _chapter("cierre", "Cierre", "cursor-agent",
                     [_step("say", "qué te llevás y cuál es el próximo episodio")]),
        ],
    }


def _walk(value, label: str, out: List[str]) -> None:
    """Collect the label of every string under value that carries the mark."""
    if isinstance(value, str):
        if MARK in value:
            out.append(label)
    elif isinstance(value, dict):
        for k, v in value.items():
            _walk(v, ("%s.%s" % (label, k)) if label else k, out)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _walk(v, ("%s %d" % (label, i)) if label else str(i), out)


def _labels(value, label: str = "") -> List[str]:
    out: List[str] = []
    _walk(value, label, out)
    return out


def pending(episode, where: str) -> List[str]:
    """One problem per field still holding COMPLETAR: '<file> chapter <i> (<id>) step <j>: ...'."""
    if not isinstance(episode, dict):
        return []
    out = []
    head = {k: v for k, v in episode.items() if k != "chapters"}
    for lab in _labels(head):
        out.append("%s: %s still in '%s'" % (where, MARK, lab))
    chapters = episode.get("chapters")
    for i, ch in enumerate(chapters if isinstance(chapters, list) else []):
        if not isinstance(ch, dict):
            continue
        prefix = "%s chapter %d (%s)" % (where, i, ch.get("id", "?"))
        for lab in _labels({k: v for k, v in ch.items() if k != "steps"}):
            out.append("%s: %s still in '%s'" % (prefix, MARK, lab))
        steps = ch.get("steps")
        for j, st in enumerate(steps if isinstance(steps, list) else []):
            for lab in _labels(st):
                out.append("%s step %d: %s still in '%s'" % (prefix, j, MARK, lab))
    return out


def skill_commit(root, repo: str) -> str:
    """Short HEAD of the skill repo (see capture.skill_source), else COMPLETAR."""
    path = capture.skill_source(Path(root), repo)
    try:
        proc = subprocess.run(["git", "-C", str(path), "rev-parse", "--short", "HEAD"],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              universal_newlines=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return MARK
    sha = proc.stdout.strip()
    return sha if proc.returncode == 0 and re.fullmatch(r"[0-9a-f]{4,40}", sha) else MARK


def create(root, repo: str, series: str = "cursor", order: Optional[int] = None,
           today: Optional[datetime.date] = None, id: Optional[str] = None) -> Path:
    """Write episodes/<series>/<NN>-<id>.json (id defaults to repo; a monorepo hosts several ids).
    Never overwrites; raises ScaffoldError."""
    id = id or repo
    root = Path(root)
    if series not in schema.SERIES:
        raise ScaffoldError("unknown series %r" % series)
    if not NAME_RE.match(repo):
        raise ScaffoldError("%r is not a valid skill repo name (lowercase letters, digits, . _ -)" % repo)
    if not NAME_RE.match(id):
        raise ScaffoldError("%r is not a valid episode id (lowercase letters, digits, . _ -)" % id)
    if order is not None and order < 0:
        raise ScaffoldError("--order must be 0 or more")
    existing = []
    for p in schema.episode_files(root):
        if p.parent.name != series:
            continue
        try:
            ep = schema.load(p)
        except ValueError:
            continue
        if isinstance(ep, dict):
            existing.append((p, ep))
    for p, ep in existing:
        if ep.get("id") == id:
            raise ScaffoldError("episode %r already exists (%s)" % (id, p.name))
        if order is not None and ep.get("order") == order:
            raise ScaffoldError("order %d is taken by %s" % (order, p.name))
    if order is None:
        orders = [ep["order"] for _, ep in existing if isinstance(ep.get("order"), int)]
        order = max(orders) + 1 if orders else 1
    target = root / "episodes" / series / ("%02d-%s.json" % (order, id))
    if target.exists():
        raise ScaffoldError("%s already exists" % target.name)
    date = (today or datetime.date.today()).isoformat()
    ep = skeleton(repo, series, order, skill_commit(root, repo), date, id)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(str(target), "x", encoding="utf-8") as fh:  # "x": fails instead of overwriting
        fh.write(json.dumps(ep, ensure_ascii=False, indent=2) + "\n")
    return target
