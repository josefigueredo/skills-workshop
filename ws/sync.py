"""`build.py sync`: copy each skill's episodes (<skill>/workshop/episodes/) into this workshop's episodes/.

The skill is the source; the workshop's episodes/ is a mirror that the series pages are built from. The skill is
found like capture finds it ($WS_SKILLS_ROOT, else next to the workshop) and read from its working tree. Each skill's
committed workshop/dist/ is also re-rendered with this engine: a stale one is reported, since its Pages publish it."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, List, Optional

from ws import bundle, capture, paths, schema, stamp


def _rel(path: Path, base: Path) -> str:
    return path.relative_to(base).as_posix()


def mirror_repos(root: Path) -> List[str]:
    """skill.repo of every mirror episode, except the workshop's own."""
    repos = set()
    for p in schema.episode_files(root):
        repo = (schema.load(p).get("skill") or {}).get("repo")
        if isinstance(repo, str) and repo not in (paths.WORKSHOP_REPO, root.resolve().name):
            repos.add(repo)
    return sorted(repos)


def _wanted(content: Path) -> Dict[str, Path]:
    """{path under episodes/: source file} for the skill's episodes and the pages they show."""
    base = content / "episodes"
    out: Dict[str, Path] = {}
    for p in schema.episode_files(content):
        out[_rel(p, base)] = p
        for st in schema.page_steps(schema.load(p)):
            out[st["src"]] = base / st["src"]
    return out


def dist_is_fresh(content: Path) -> bool:
    dist = content / "dist"
    rendered = bundle.render(content)
    for name, html in rendered.items():
        f = dist / name
        if not f.is_file() or f.read_bytes() != html.encode("utf-8"):
            return False
    f = dist / stamp.FILE
    return f.is_file() and f.read_text(encoding="utf-8") == stamp.digest(content) + "\n"


def sync_repo(root: Path, repo: str, check: bool, emit: Callable) -> int:
    source = capture.find_skill(root, repo)
    if source is None:
        emit("%s: cannot verify its workshop/dist: no clone in %s (set WS_SKILLS_ROOT to the folder that holds it)"
             % (repo, ", ".join(str(c) for c in capture.skill_candidates(root, repo))))
        return 1
    content = source / "workshop"
    if not (content / "episodes").is_dir():
        emit("%s: no workshop/episodes in %s (is the skill's branch with its episodes checked out?)"
             % (repo, content.parent))
        return 1
    problems = schema.check_tree(content)
    if problems:
        for p in problems:
            emit("%s: %s" % (repo, p))
        emit("%s: %d problem(s): mirror left as it is" % (repo, len(problems)))
        return 1
    mirror = root / "episodes"
    wanted = _wanted(content)
    changes = []
    for rel, src in sorted(wanted.items()):
        dest = mirror / rel
        if not dest.is_file() or dest.read_bytes() != src.read_bytes():
            changes.append(("copy", rel, src))
    for p in schema.episode_files(root):
        rel = _rel(p, mirror)
        if rel not in wanted and (schema.load(p).get("skill") or {}).get("repo") == repo:
            changes.append(("remove", rel, p))
    code = 0
    for action, rel, path in changes:
        if check:
            emit("%s: episodes/%s differs from the skill (run build.py sync)" % (repo, rel))
            code = 1
            continue
        dest = mirror / rel
        if action == "copy":
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(path.read_bytes())
        else:
            dest.unlink()
        emit("%s: %s episodes/%s" % (repo, "copied" if action == "copy" else "removed", rel))
    try:
        fresh = dist_is_fresh(content)
    except bundle.BundleError as exc:
        emit("%s: cannot render its episodes (%s)" % (repo, exc))
        return 1
    if not fresh:
        emit("%s: workshop/dist is out of date: run `python3 build.py --root %s build` and commit it in the skill"
             % (repo, content))
        code = 1
    if not changes and code == 0:
        emit("%s: up to date" % repo)
    return code


def run(root, repos: Optional[List[str]] = None, check: bool = False, emit: Callable = print) -> int:
    """0 everything in step, 1 any drift (check), missing skill or stale skill dist."""
    root = Path(root)
    code = 0
    for repo in repos or mirror_repos(root):
        code = max(code, sync_repo(root, repo, check, emit))
    return code
