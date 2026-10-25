"""Capture of `real` terminal steps: run them against the demo in a fake HOME."""
from __future__ import annotations

import copy
import fcntl
import getpass
import json
import os
import pty
import pwd
import re
import select
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import termios
import time
from pathlib import Path
from typing import List, Optional

from ws import paths, privacy, schema

DEMO_NAME = "Demo"
DEMO_EMAIL = "demo@example.com"
STEP_TIMEOUT = 120
FAKE_USER = "persona"
FAKE_HOST = "mi-mac"
SYSTEM_PATH_DIRS = ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin")

_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[@-Z\\-_]")
_SGR = re.compile(r"\x1b\[[0-9;]*m")
# The terminal a `color` step runs in: as wide as the stage's terminal fits.
TTY_COLS, TTY_ROWS = 120, 40


class CaptureError(Exception):
    """A capture could not run (bad prepare, missing cwd, ...). Others keep going."""


def skill_candidates(root: Path, repo: str) -> List[Path]:
    """Every `<dir>/<repo>` to look in: each folder of $WS_SKILLS_ROOT (split on os.pathsep),
    else the workshop repo's parent (this workshop's for a skill's content root)."""
    env = os.environ.get("WS_SKILLS_ROOT")
    dirs = [Path(d) for d in env.split(os.pathsep) if d] if env else []
    if not dirs:
        dirs = [paths.workshop_root(root).resolve().parent]
    return [d / repo for d in dirs]


def _is_git(path: Path) -> bool:
    return (path / ".git").exists() or (path / "HEAD").exists()


def skill_source(root: Path, repo: str) -> Path:
    """The first candidate holding a git dir, else the default `root.parent/<repo>`."""
    cands = skill_candidates(root, repo)
    for c in cands:
        if _is_git(c):
            return c
    return paths.workshop_root(root).resolve().parent / repo


def _under(path: str, base: str) -> bool:
    path, base = os.path.realpath(path), os.path.realpath(base)
    return path == base or path.startswith(base.rstrip("/") + "/")


def _path() -> str:
    """Explicit PATH: system and Homebrew dirs that exist, plus the running python's dir.

    Never a directory under the real home."""
    real_home = os.path.expanduser("~")
    dirs = [d for d in SYSTEM_PATH_DIRS if os.path.isdir(d)]
    exe = os.path.dirname(os.path.realpath(sys.executable))
    if exe not in dirs and not _under(exe, real_home):
        dirs.append(exe)
    return os.pathsep.join(dirs)


def scratch_env(home: Path) -> dict:
    """The only environment a step (or setup/clone) ever sees: built from scratch."""
    return {
        "PATH": _path(), "HOME": str(home), "NO_COLOR": "1", "LANG": "C.UTF-8", "TERM": "dumb",
        "USER": FAKE_USER, "LOGNAME": FAKE_USER, "PYTHONDONTWRITEBYTECODE": "1",
        "GIT_AUTHOR_NAME": DEMO_NAME, "GIT_AUTHOR_EMAIL": DEMO_EMAIL,
        "GIT_COMMITTER_NAME": DEMO_NAME, "GIT_COMMITTER_EMAIL": DEMO_EMAIL,
        "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
    }


def _run_quiet(args: List[str], what: str, env: dict, cwd: Optional[Path] = None) -> str:
    r = subprocess.run(args, cwd=str(cwd) if cwd else None, env=env,
                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, universal_newlines=True)
    if r.returncode != 0:
        raise CaptureError("%s failed (exit %d): %s" % (what, r.returncode, r.stdout.strip()))
    return r.stdout.strip()


def prepare_home(root: Path, episode: dict, home: Path) -> None:
    """Build the demo at home/mi-servicio and the episode's skill at home/skills/<repo>."""
    root, home = Path(root), Path(home)
    env = scratch_env(home)
    _run_quiet(["bash", str(paths.demo_dir(root) / "setup.sh"), str(home)], "demo/setup.sh", env)
    skill = episode["skill"]
    repo, commit = skill["repo"], skill["commit"]
    src = skill_source(root, repo)
    if not _is_git(src):
        tried = ", ".join(str(c) for c in skill_candidates(root, repo))
        raise CaptureError("skill repo %r not found (commit %s); tried: %s; set WS_SKILLS_ROOT"
                           % (repo, commit, tried))
    dest = home / "skills" / repo
    (home / "skills").mkdir(exist_ok=True)
    try:
        try:
            origin = _run_quiet(["git", "-C", str(src), "remote", "get-url", "origin"],
                                "origin lookup", env)
        except CaptureError:
            origin = ""
        _run_quiet(["git", "clone", "-q", str(src), str(dest)], "clone of %r" % repo, env)
        _run_quiet(["git", "-c", "advice.detachedHead=false", "checkout", "-q", commit],
                   "checkout of commit %s" % commit, env, cwd=dest)
        if origin:
            _run_quiet(["git", "remote", "set-url", "origin", origin], "origin reset", env, cwd=dest)
        else:
            _run_quiet(["git", "remote", "remove", "origin"], "origin removal", env, cwd=dest)
    except CaptureError as exc:
        raise CaptureError("skill %r at commit %s (source %s): %s" % (repo, commit, src, exc))
    # Episode-specific demo state (e.g. seeded worker output): demo/prep/<id>.sh <home>.
    prep = paths.demo_dir(root) / "prep" / ("%s.sh" % episode["id"])
    if prep.is_file():
        _run_quiet(["bash", str(prep), str(home)], "demo/prep/%s.sh" % episode["id"], env)


def _variants(path) -> List[str]:
    p = str(path)
    out = [p, os.path.realpath(p)]
    out += ["/private" + p] if sys.platform == "darwin" and not p.startswith("/private") else []
    return sorted(set(out), key=len, reverse=True)


def _login_names(user: Optional[str]) -> List[str]:
    names = set()
    if user is not None:
        names.add(user)
    else:
        names.add(getpass.getuser())
        try:
            names.add(pwd.getpwuid(os.getuid()).pw_name)
        except (KeyError, OSError):
            pass
    return sorted((n for n in names if n and n != FAKE_USER), key=len, reverse=True)


def _hostnames() -> List[str]:
    full = socket.gethostname()
    names = {full, full.split(".")[0]}
    return sorted((n for n in names if n), key=len, reverse=True)


_BOUND = r"(?![A-Za-z0-9_-])"


def normalise(text: str, home: Path, roots: Optional[List[Path]] = None,
              user: Optional[str] = None, keep_sgr: bool = False) -> str:
    """Strip ANSI (all of it, or all but the SGR colour codes with keep_sgr); fake HOME / temp roots / real home -> `~`; real login names -> `persona`;
    hostname -> `mi-mac`. Matches end at a boundary (`/Users/x` never eats `/Users/xavier`)."""
    strip = (lambda m: m.group(0) if _SGR.fullmatch(m.group(0)) else "") if keep_sgr else ""
    text = _ANSI.sub(strip, text).replace("\r\n", "\n").replace("\r", "\n")
    paths = [home] + list(roots or [])
    paths.append(Path(os.path.expanduser("~")))
    for p in paths:
        for v in _variants(p):
            if v not in ("", "/"):
                text = re.sub(re.escape(v) + _BOUND, "~", text)
    for name in _login_names(user):
        text = re.sub(r"(?<![A-Za-z0-9_.-])%s%s" % (re.escape(name), _BOUND), FAKE_USER, text)
    for host in _hostnames():
        text = re.sub(r"(?<![A-Za-z0-9_.-])%s%s" % (re.escape(host), _BOUND), FAKE_HOST, text)
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


def color_env(env: dict) -> dict:
    """A `color` step's environment: the scratch one as a truecolor terminal, with NO_COLOR unset."""
    out = {k: v for k, v in env.items() if k != "NO_COLOR"}
    out.update({"TERM": "xterm-256color", "COLORTERM": "truecolor"})
    return out


def _exec_tty(cmd: str, cwd: Path, env: dict, timeout: float):
    """Like _exec, but stdout and stderr are a pseudo-terminal, so the tool paints as in a real one."""
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", TTY_ROWS, TTY_COLS, 0, 0))
    try:
        proc = subprocess.Popen(["bash", "--noprofile", "--norc", "-c", cmd], cwd=str(cwd), env=color_env(env),
                                stdin=subprocess.DEVNULL, stdout=slave, stderr=slave, start_new_session=True)
    finally:
        os.close(slave)
    chunks, deadline, timed_out = [], time.monotonic() + timeout, False
    try:
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                timed_out = True
                break
            ready, _, _ = select.select([master], [], [], min(left, 0.2))
            if not ready:
                if proc.poll() is not None:
                    break
                continue
            try:
                data = os.read(master, 65536)
            except OSError:  # Linux: EIO once every writer closed the terminal
                break
            if not data:
                break
            chunks.append(data)
    finally:
        os.close(master)
    text = b"".join(chunks).decode("utf-8", "replace")
    if not timed_out:
        # The output can close while the command keeps running: the deadline still holds.
        try:
            return text, proc.wait(timeout=max(deadline - time.monotonic(), 0))
        except subprocess.TimeoutExpired:
            pass
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        pass
    proc.wait()
    return text, None


def _lines(text: str) -> List[str]:
    if text.endswith("\n"):
        text = text[:-1]
    return text.split("\n") if text else []


def run(episode: dict, home: Path, timeout: float = STEP_TIMEOUT) -> dict:
    """Re-run every `real` term step in the fake HOME; return a copy with fresh `out`."""
    home = Path(home)
    new = copy.deepcopy(episode)
    env = scratch_env(home)
    roots = [home.parent]
    for chapter in new["chapters"]:
        for step in chapter["steps"]:
            if step.get("type") != "term" or step.get("source") != "real":
                continue
            cwd = _resolve_cwd(step["cwd"], home)
            color = step.get("color") is True
            text, code = (_exec_tty if color else _exec)(step["cmd"], cwd, env, timeout)
            lines = _lines(normalise(text, home, roots, keep_sgr=color))
            if code is None:
                lines.append("# timeout")
            elif code != 0:
                lines.append("# exit %d" % code)
            step["out"] = lines
    return new


def harvest(episode: dict, home: Path) -> List[tuple]:
    """(src, capture, text) for each page step with `capture`: the file the real steps wrote in the fake HOME,
    normalised like their output. Raises CaptureError when a file is not there."""
    home = Path(home)
    pages = []
    for chapter in episode["chapters"]:
        for step in chapter["steps"]:
            if step.get("type") != "page" or "capture" not in step:
                continue
            path = home / step["capture"][2:]
            if not path.is_file():
                raise CaptureError("page %s: the real steps did not write %s" % (step["src"], step["capture"]))
            text = path.read_text(encoding="utf-8", errors="replace")
            pages.append((step["src"], step["capture"], normalise(text, home, [home.parent])))
    return pages


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
                pages = harvest(new, home)
            except CaptureError as exc:
                failed += 1
                emit("%s: capture failed: %s" % (ep["id"], exc))
                continue
        text = dump(new)
        try:
            hits = privacy.scan_text(text, "%s/%s" % (path.parent.name, path.name))
            for src, _, page in pages:
                hits += privacy.scan_text(page, src)
        except ValueError as exc:
            hits = ["privacy rules unavailable: %s" % exc]
        if hits:
            failed += 1
            for h in hits:
                emit(h)
            emit("%s: capture failed: %d privacy hit(s); file left untouched" % (ep["id"], len(hits)))
            continue
        for chapter in new["chapters"]:
            for j, step in enumerate(chapter["steps"]):
                if step.get("type") == "term" and step.get("source") == "real":
                    emit("%s chapter %s step %d: %s (%d lines)"
                         % (ep["id"], chapter["id"], j, step["cmd"], len(step["out"])))
        for src, origin, page in pages:
            dest = root / "episodes" / src
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.is_file() or dest.read_text(encoding="utf-8") != page:
                dest.write_text(page, encoding="utf-8")
            emit("%s: episodes/%s from %s" % (ep["id"], src, origin))
        if path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")
    return 1 if failed else 0
