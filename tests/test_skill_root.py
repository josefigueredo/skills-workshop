"""A skill keeps its own episodes under <skill>/workshop/ (episodes/<series>/, episodes/pages/) and builds them with
this workshop's engine; the workshop keeps a mirror (build.py sync)."""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import build
from tests.helpers import ROOT, TempTree, minimal_episode
from tests.test_bundle import with_engine
from ws import bundle, capture, paths, stamp

TEMPLATE = ROOT / "templates" / "skill-pages.yml"


def run_cli(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = build.main(list(argv))
    return code, out.getvalue()


def page_episode(**over):
    ep = minimal_episode(**over)
    ep["chapters"][0]["steps"].append(
        {"type": "page", "title": "Vista", "src": "pages/%s-vista.html" % ep["id"], "source": "real"})
    return ep


class SkillTree:
    """A skills root holding one skill repo with a workshop/ content folder."""

    def __init__(self, repo="demo-skill"):
        self._tmp = tempfile.TemporaryDirectory()
        self.skills = Path(self._tmp.name)
        self.repo = repo
        self.path = self.skills / repo
        (self.path / ".git").mkdir(parents=True)
        self.content = self.path / "workshop"
        (self.content / "episodes").mkdir(parents=True)

    def write(self, series, name, episode, pages=()):
        d = self.content / "episodes" / series
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(json.dumps(episode), encoding="utf-8")
        for page in pages:
            p = self.content / "episodes" / "pages" / page
            p.parent.mkdir(exist_ok=True)
            p.write_text("<p>%s</p>\n" % page, encoding="utf-8")

    def env(self):
        return mock.patch.dict(os.environ, {"WS_SKILLS_ROOT": str(self.skills)})

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._tmp.cleanup()


class ContentRootTests(unittest.TestCase):
    """A root with no engine/ or demo/ of its own uses this workshop's."""

    def test_engine_and_demo_fall_back_to_the_workshop(self):
        with TempTree() as tree:
            self.assertEqual(paths.engine_dir(tree.root), ROOT / "engine")
            self.assertEqual(paths.demo_dir(tree.root), ROOT / "demo")
        with with_engine(TempTree()) as tree:
            self.assertEqual(paths.engine_dir(tree.root), tree.root / "engine")

    def test_build_from_a_content_root_uses_the_workshop_engine(self):
        with TempTree() as tree:
            tree.write("cursor", "01-a.json", minimal_episode(id="cur-a"))
            code, out = run_cli("--root", str(tree.root), "build")
            self.assertEqual(code, 0, out)
            html = (tree.root / "dist" / "serie-cursor.html").read_text(encoding="utf-8")
            self.assertIn("--ws-font-ui", html)
            self.assertFalse((tree.root / "engine").exists())

    def test_an_empty_series_gets_no_page_and_no_heading(self):
        with TempTree() as tree:
            tree.write("cursor", "01-a.json", minimal_episode(id="cur-a"))
            rendered = bundle.render(tree.root)
            self.assertNotIn("serie-claude-code.html", rendered)
            self.assertIn("serie-cursor.html", rendered)
            self.assertNotIn("Serie Claude Code", rendered["index.html"])
            self.assertNotIn("Todavía no hay episodios", rendered["index.html"])

    def test_skills_default_to_the_workshop_parent_for_a_content_root(self):
        env = {k: v for k, v in os.environ.items() if k != "WS_SKILLS_ROOT"}
        with TempTree() as tree, mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(capture.skill_source(tree.root, "x"), ROOT.parent / "x")

    def test_capture_of_a_content_root_builds_the_workshop_demo(self):
        with SkillTree() as skill, tempfile.TemporaryDirectory() as home:
            subprocess.run(["git", "init", "-q", str(skill.path)], check=True)
            (skill.path / "SKILL.md").write_text("x\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(skill.path), "add", "SKILL.md"], check=True)
            subprocess.run(["git", "-C", str(skill.path), "-c", "user.name=Demo", "-c", "user.email=demo@example.com",
                            "commit", "-qm", "x"], check=True)
            sha = subprocess.run(["git", "-C", str(skill.path), "rev-parse", "HEAD"], check=True,
                                 stdout=subprocess.PIPE, universal_newlines=True).stdout.strip()
            ep = minimal_episode(skill={"repo": skill.repo, "commit": sha, "date": "x"})
            with skill.env():
                capture.prepare_home(skill.content, ep, Path(home))
            self.assertTrue((Path(home) / "mi-servicio" / ".git").is_dir())


class StampTests(unittest.TestCase):
    def test_build_writes_the_stamp_of_the_episodes(self):
        with TempTree() as tree:
            tree.write("cursor", "01-a.json", minimal_episode(id="cur-a"))
            bundle.build(tree.root)
            text = (tree.root / "dist" / stamp.FILE).read_text(encoding="utf-8")
            self.assertEqual(text, stamp.digest(tree.root) + "\n")

    def test_stamp_changes_with_any_episode_file_but_not_hidden_ones(self):
        with TempTree() as tree:
            tree.write("cursor", "01-a.json", minimal_episode(id="cur-a"))
            first = stamp.digest(tree.root)
            (tree.root / "episodes" / ".DS_Store").write_bytes(b"junk")
            self.assertEqual(stamp.digest(tree.root), first)
            (tree.root / "episodes" / "pages").mkdir()
            (tree.root / "episodes" / "pages" / "x.html").write_text("<p>x</p>", encoding="utf-8")
            self.assertNotEqual(stamp.digest(tree.root), first)


def template_check_script():
    """The stamp check embedded in the Pages workflow template (between the PY heredoc markers)."""
    text = TEMPLATE.read_text(encoding="utf-8")
    m = re.search(r"python3 - <<'PY'\n(.*?)\n\s*PY\n", text, re.S)
    assert m, "no stamp check in the template"
    lines = m.group(1).splitlines()
    indent = min(len(l) - len(l.lstrip()) for l in lines if l.strip())
    return "\n".join(l[indent:] for l in lines) + "\n"


class PagesTemplateTests(unittest.TestCase):
    def run_check(self, repo):
        return subprocess.run(["python3", "-c", template_check_script()], cwd=str(repo),
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)

    def test_template_publishes_workshop_dist_from_main(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("branches: [main]", text)
        self.assertIn("path: workshop/dist", text)
        self.assertIn("actions/deploy-pages@v4", text)

    def test_template_check_passes_on_a_fresh_build_and_fails_when_stale(self):
        with SkillTree() as skill:
            skill.write("cursor", "01-demo.json", minimal_episode())
            code, out = run_cli("--root", str(skill.content), "build")
            self.assertEqual(code, 0, out)
            ok = self.run_check(skill.path)
            self.assertEqual(ok.returncode, 0, ok.stdout)
            skill.write("cursor", "01-demo.json", minimal_episode(title="otro"))
            stale = self.run_check(skill.path)
            self.assertEqual(stale.returncode, 1, stale.stdout)
            self.assertIn("build.py --root", stale.stdout)


class SyncTests(unittest.TestCase):
    """build.py sync copies each skill's episodes into this workshop's episodes/ (the mirror)."""

    def setUp(self):
        self.ws = with_engine(TempTree())
        self.addCleanup(self.ws.__exit__, None, None, None)
        self.skill = SkillTree()
        self.addCleanup(self.skill.__exit__, None, None, None)

    def sync(self, *extra):
        with self.skill.env():
            return run_cli("--root", str(self.ws.root), "sync", *extra)

    def built_skill(self, episode, pages=()):
        self.skill.write("cursor", "03-demo.json", episode, pages)
        code, out = run_cli("--root", str(self.skill.content), "build")
        self.assertEqual(code, 0, out)

    def test_copies_the_episode_and_its_pages(self):
        self.built_skill(page_episode(skill={"repo": "demo-skill", "commit": "abc1234", "date": "x"}),
                         ["demo-vista.html"])
        code, out = self.sync("--repo", "demo-skill")
        self.assertEqual(code, 0, out)
        mirror = self.ws.root / "episodes"
        self.assertEqual((mirror / "cursor" / "03-demo.json").read_bytes(),
                         (self.skill.content / "episodes" / "cursor" / "03-demo.json").read_bytes())
        self.assertTrue((mirror / "pages" / "demo-vista.html").is_file())

    def test_repos_default_to_those_of_the_mirror(self):
        self.built_skill(minimal_episode(skill={"repo": "demo-skill", "commit": "abc1234", "date": "x"}))
        self.ws.write("cursor", "03-demo.json", minimal_episode(title="viejo"))
        code, out = self.sync()
        self.assertEqual(code, 0, out)
        got = json.loads((self.ws.root / "episodes" / "cursor" / "03-demo.json").read_text(encoding="utf-8"))
        self.assertEqual(got["title"], "demo")

    def test_check_reports_drift_and_writes_nothing(self):
        self.built_skill(minimal_episode())
        self.ws.write("cursor", "03-demo.json", minimal_episode(title="viejo"))
        before = (self.ws.root / "episodes" / "cursor" / "03-demo.json").read_bytes()
        code, out = self.sync("--check")
        self.assertEqual(code, 1, out)
        self.assertIn("03-demo.json", out)
        self.assertEqual((self.ws.root / "episodes" / "cursor" / "03-demo.json").read_bytes(), before)

    def test_check_is_clean_after_a_sync(self):
        self.built_skill(minimal_episode())
        self.sync("--repo", "demo-skill")
        code, out = self.sync("--check")
        self.assertEqual(code, 0, out)

    def test_removes_a_mirror_episode_the_skill_no_longer_has(self):
        self.built_skill(minimal_episode())
        self.ws.write("cursor", "04-viejo.json", minimal_episode(id="viejo", order=4))
        code, out = self.sync()
        self.assertEqual(code, 0, out)
        self.assertFalse((self.ws.root / "episodes" / "cursor" / "04-viejo.json").exists())
        self.assertIn("04-viejo.json", out)

    def test_stale_skill_dist_is_reported(self):
        self.built_skill(minimal_episode())
        self.skill.write("cursor", "03-demo.json", minimal_episode(title="sin armar"))
        code, out = self.sync("--repo", "demo-skill")
        self.assertEqual(code, 1, out)
        self.assertIn("dist", out)
        self.assertIn("build.py --root", out)

    def test_a_skill_without_a_workshop_folder_is_an_error(self):
        (self.skill.content / "episodes").rename(self.skill.content / "otra")
        code, out = self.sync("--repo", "demo-skill")
        self.assertEqual(code, 1, out)
        self.assertIn("workshop/episodes", out)

    def test_episodes_of_the_workshop_itself_are_kept(self):
        self.built_skill(minimal_episode())
        own = minimal_episode(id="antes", order=0, skill={"repo": paths.WORKSHOP_REPO, "commit": "a", "date": "x"})
        self.ws.write("cursor", "00-antes.json", own)
        code, out = self.sync()
        self.assertEqual(code, 0, out)
        self.assertTrue((self.ws.root / "episodes" / "cursor" / "00-antes.json").is_file())


if __name__ == "__main__":
    unittest.main()
