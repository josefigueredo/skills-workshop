"""Capture of `real` terminal steps: run them against the demo in a fake HOME."""
from __future__ import annotations

import copy
import getpass
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

from ws import schema

DEMO_NAME = "Demo"
DEMO_EMAIL = "demo@example.com"
STEP_TIMEOUT = 120
FAKE_USER = "persona"

_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[@-Z\\-_]")


class CaptureError(Exception):
    """A capture could not run (bad prepare, missing cwd, ...). Others keep going."""


def skills_root(root: Path) -> Path:
    """Where skill repos live: $WS_SKILLS_ROOT, else the workshop repo's parent."""
    env = os.environ.get("WS_SKILLS_ROOT")
    return Path(env) if env else Path(root).resolve().parent


def _git_env() -> dict:
    env = dict(os.environ)
    env.update({
        "GIT_AUTHOR_NAME": DEMO_NAME, "GIT_AUTHOR_EMAIL": DEMO_EMAIL,
        "GIT_COMMITTER_NAME": DEMO_NAME, "GIT_COMMITTER_EMAIL": DEMO_EMAIL,
        "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
    })
    return env


def _run_quiet(args: List[str], what: str, cwd: Optional[Path] = None) -> None:
    r = subprocess.run(args, cwd=str(cwd) if cwd else None, env=_git_env(),
                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, universal_newlines=True)
    if r.returncode != 0:
        raise CaptureError("%s failed (exit %d): %s" % (what, r.returncode, r.stdout.strip()))


def prepare_home(root: Path, episode: dict, home: Path) -> None:
    """Build the demo at home/mi-servicio and the episode's skill at home/skills/<repo>."""
    root, home = Path(root), Path(home)
    _run_quiet(["bash", str(root / "demo" / "setup.sh"), str(home)], "demo/setup.sh")
    skill = episode["skill"]
    repo, commit = skill["repo"], skill["commit"]
    src = skills_root(root) / repo
    if not (src / ".git").exists() and not (src / "HEAD").exists():
        raise CaptureError("skill repo %r not found at %s (commit %s); set WS_SKILLS_ROOT"
                           % (repo, src, commit))
    dest = home / "skills" / repo
    (home / "skills").mkdir(exist_ok=True)
    try:
        _run_quiet(["git", "clone", "-q", str(src), str(dest)], "clone of %r" % repo)
        _run_quiet(["git", "-c", "advice.detachedHead=false", "checkout", "-q", commit],
                   "checkout of commit %s" % commit, cwd=dest)
    except CaptureError as exc:
        raise CaptureError("skill %r at commit %s (source %s): %s" % (repo, commit, src, exc))


def _variants(path) -> List[str]:
    p = str(path)
    out = [p, os.path.realpath(p)]
    out += ["/private" + p] if sys.platform == "darwin" and not p.startswith("/private") else []
    return sorted(set(out), key=len, reverse=True)


def normalise(text: str, home: Path, roots: Optional[List[Path]] = None,
              user: Optional[str] = None) -> str:
    """Strip ANSI and replace fake HOME / temp roots / real home with `~`, real user with `persona`."""
    text = _ANSI.sub("", text).replace("\r\n", "\n").replace("\r", "\n")
    paths = [home] + list(roots or [])
    paths.append(Path(os.path.expanduser("~")))
    for p in paths:
        for v in _variants(p):
            if v not in ("", "/"):
                text = text.replace(v, "~")
    name = user if user is not None else getpass.getuser()
    if name and name != FAKE_USER:
        text = re.sub(r"(?<![A-Za-z0-9_.-])%s(?![A-Za-z0-9_-])" % re.escape(name), FAKE_USER, text)
    return text


def _resolve_cwd(cwd: str, home: Path) -> Path:
    rel = "" if cwd == "~" else cwd[2:]
    path = (home / rel) if rel else home
    real_home = home.resolve()
    real = path.resolve()
    if real != real_home and real_home not in real.parents:
        raise CaptureError("cwd %r escapes the fake HOME" % cwd)
    if not real.is_dir():
        raise CaptureError("cwd %r does not exist in the fake HOME" % cwd)
    return real


def _env(home: Path) -> dict:
    env = _git_env()
    env.update({"HOME": str(home), "NO_COLOR": "1", "LANG": "C.UTF-8", "TERM": "dumb",
                "USER": FAKE_USER, "LOGNAME": FAKE_USER, "PYTHONDONTWRITEBYTECODE": "1"})
    for k in ("LC_ALL", "PWD", "OLDPWD", "XDG_CONFIG_HOME"):
        env.pop(k, None)
    return env


def _exec(cmd: str, cwd: Path, env: dict, timeout: float):
    """Run cmd with bash; returns (combined_text, exit_code or None on timeout)."""
    proc = subprocess.Popen(["bash", "--noprofile", "--norc", "-c", cmd], cwd=str(cwd), env=env,
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, start_new_session=True)
    try:
        data, _ = proc.communicate(timeout=timeout)
        return data.decode("utf-8", "replace"), proc.returncode
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
        data, _ = proc.communicate()
        return data.decode("utf-8", "replace"), None


def _lines(text: str) -> List[str]:
    if text.endswith("\n"):
        text = text[:-1]
    return text.split("\n") if text else []


def run(episode: dict, home: Path, timeout: float = STEP_TIMEOUT) -> dict:
    """Re-run every `real` term step in the fake HOME; return a copy with fresh `out`."""
    home = Path(home)
    new = copy.deepcopy(episode)
    env = _env(home)
    roots = [home.parent]
    for chapter in new["chapters"]:
        for step in chapter["steps"]:
            if step.get("type") != "term" or step.get("source") != "real":
                continue
            cwd = _resolve_cwd(step["cwd"], home)
            text, code = _exec(step["cmd"], cwd, env, timeout)
            lines = _lines(normalise(text, home, roots))
            if code is None:
                lines.append("# timeout")
            elif code != 0:
                lines.append("# exit %d" % code)
            step["out"] = lines
    return new


def has_real_steps(episode: dict) -> bool:
    return any(s.get("type") == "term" and s.get("source") == "real"
               for c in episode["chapters"] for s in c["steps"])


def dump(episode: dict) -> str:
    return json.dumps(episode, indent=2, ensure_ascii=False) + "\n"


def capture_tree(root, episode_id: Optional[str] = None, emit=print) -> int:
    """Capture every `real` step of the episodes under root. 0 ok, 1 any failure, 2 unknown id.

    Callers must run schema.check_tree first."""
    root = Path(root)
    entries = [(p, schema.load(p)) for p in schema.episode_files(root)]
    if episode_id is not None:
        entries = [(p, e) for p, e in entries if e["id"] == episode_id]
        if not entries:
            emit("capture: no episode with id %r" % episode_id)
            return 2
    failed = 0
    for path, ep in entries:
        if not has_real_steps(ep):
            emit("%s: no real steps, skipped" % ep["id"])
            continue
        with tempfile.TemporaryDirectory(prefix="ws-capture-") as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            try:
                prepare_home(root, ep, home)
                new = run(ep, home)
            except CaptureError as exc:
                failed += 1
                emit("%s: capture failed: %s" % (ep["id"], exc))
                continue
        for chapter in new["chapters"]:
            for j, step in enumerate(chapter["steps"]):
                if step.get("type") == "term" and step.get("source") == "real":
                    emit("%s chapter %s step %d: %s (%d lines)"
                         % (ep["id"], chapter["id"], j, step["cmd"], len(step["out"])))
        text = dump(new)
        if path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")
    return 1 if failed else 0
