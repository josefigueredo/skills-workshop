"""`build.py new`: the episode skeleton, and the COMPLETAR gate on validate/build."""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import build
from tests.helpers import TempTree, minimal_episode
from tests.test_bundle import run_build, with_engine
from ws import scaffold, schema


def run_cli(root, *args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = build.main(["--root", str(root)] + list(args))
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue() + err.getvalue()


def make_skill_repo(parent: Path, name: str) -> str:
    repo = parent / name
    repo.mkdir()
    git = ["git", "-C", str(repo), "-c", "user.name=Demo", "-c", "user.email=demo@example.com"]
    subprocess.run(git + ["init", "-q"], check=True)
    (repo / "README.md").write_text("x", encoding="utf-8")
    subprocess.run(git + ["add", "."], check=True)
    subprocess.run(git + ["commit", "-q", "-m", "init"], check=True)
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"], check=True,
                          stdout=subprocess.PIPE, universal_newlines=True).stdout.strip()


def env_without_skills_root(**extra):
    env = {k: v for k, v in os.environ.items() if k != "WS_SKILLS_ROOT"}
    env.update(extra)
    return mock.patch.dict(os.environ, env, clear=True)


class Skeleton(unittest.TestCase):
    def setUp(self):
        self.ep = scaffold.skeleton("mi-skill", "cursor", 3, "COMPLETAR", "2026-10-19")

    def test_it_is_schema_valid(self):
        self.assertEqual(schema.validate(self.ep, "x.json"), [])

    def test_fixed_structure(self):
        got = [(c["id"], c["screen"]) for c in self.ep["chapters"]]
        self.assertEqual(got, [("instalar", "terminal"), ("caso-principal", "cursor-full"),
                               ("otro-caso", "cursor-agent"), ("si-algo-falla", "terminal"),
                               ("cierre", "cursor-agent")])

    def test_header_fields(self):
        self.assertEqual((self.ep["id"], self.ep["series"], self.ep["order"]), ("mi-skill", "cursor", 3))
        self.assertEqual(self.ep["skill"], {"repo": "mi-skill", "commit": "COMPLETAR", "date": "2026-10-19"})

    def test_every_step_is_a_marked_inferido_placeholder_with_notes(self):
        for ch in self.ep["chapters"]:
            self.assertEqual(len(ch["faq"]), 2)
            for item in ch["faq"]:
                self.assertIn("COMPLETAR", item["q"] + item["a"])
            self.assertTrue(ch["steps"])
            for st in ch["steps"]:
                self.assertEqual(st["source"], "inferido")
                self.assertEqual(st["notes"], "COMPLETAR")
                text = st.get("text") or st.get("md") or st.get("cmd")
                self.assertTrue(text.startswith("COMPLETAR: "), st)

    def test_skeleton_is_flagged_as_pending(self):
        self.assertTrue(scaffold.pending(self.ep, "f.json"))


class Placeholders(unittest.TestCase):
    def test_message_names_file_chapter_and_step(self):
        ep = minimal_episode()
        ep["chapters"][0]["steps"][1]["text"] = "COMPLETAR: la pregunta"
        self.assertEqual(scaffold.pending(ep, "cursor/01-a.json"),
                         ["cursor/01-a.json chapter 0 (instalar) step 1: COMPLETAR still in 'text'"])

    def test_chapter_and_top_level_fields(self):
        ep = minimal_episode()
        ep["pitch"]["does"] = "COMPLETAR: qué hace"
        ep["chapters"][0]["faq"] = [{"q": "¿?", "a": "COMPLETAR"}]
        ep["chapters"][0]["subtitle"] = "COMPLETAR"
        got = scaffold.pending(ep, "f.json")
        self.assertIn("f.json: COMPLETAR still in 'pitch.does'", got)
        self.assertIn("f.json chapter 0 (instalar): COMPLETAR still in 'faq 0.a'", got)
        self.assertIn("f.json chapter 0 (instalar): COMPLETAR still in 'subtitle'", got)

    def test_clean_episode_has_none(self):
        self.assertEqual(scaffold.pending(minimal_episode(), "f.json"), [])

    def test_check_tree_and_validate_report_it(self):
        ep = minimal_episode()
        ep["chapters"][0]["steps"][1]["text"] = "COMPLETAR: x"
        with TempTree() as tree:
            tree.write("cursor", "01-a.json", ep)
            problems = schema.check_tree(tree.root)
            self.assertEqual(problems, ["cursor/01-a.json chapter 0 (instalar) step 1: COMPLETAR still in 'text'"])
            code, out = run_cli(tree.root, "validate")
            self.assertEqual(code, 1)
            self.assertIn("COMPLETAR still in 'text'", out)

    def test_build_fails_and_writes_nothing(self):
        ep = minimal_episode()
        ep["chapters"][0]["steps"][1]["text"] = "COMPLETAR: x"
        with with_engine(TempTree()) as tree:
            tree.write("cursor", "01-a.json", ep)
            code, out = run_build(tree.root)
            self.assertEqual(code, 1, out)
            self.assertIn("cursor/01-a.json chapter 0 (instalar) step 1", out)
            self.assertFalse((tree.root / "dist").exists())


class NewCommand(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.skills = Path(self._t.name)
        self.tree = TempTree()
        self.addCleanup(self.tree.__exit__, None, None, None)

    def path(self, series, name):
        return self.tree.root / "episodes" / series / name

    def test_writes_a_valid_skeleton_with_the_next_free_order(self):
        self.tree.write("cursor", "00-a.json", minimal_episode(id="a", order=0))
        self.tree.write("cursor", "04-b.json", minimal_episode(id="b", order=4))
        with env_without_skills_root(WS_SKILLS_ROOT=str(self.skills)):
            code, out = run_cli(self.tree.root, "new", "mi-skill")
        self.assertEqual(code, 0, out)
        p = self.path("cursor", "05-mi-skill.json")
        self.assertTrue(p.is_file(), out)
        self.assertIn("05-mi-skill.json", out)
        ep = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual((ep["id"], ep["series"], ep["order"]), ("mi-skill", "cursor", 5))
        self.assertEqual(schema.validate(ep, "x"), [])

    def test_first_episode_of_a_series_is_order_1(self):
        with env_without_skills_root(WS_SKILLS_ROOT=str(self.skills)):
            code, out = run_cli(self.tree.root, "new", "x-skill", "--series", "claude-code")
        self.assertEqual(code, 0, out)
        self.assertTrue(self.path("claude-code", "01-x-skill.json").is_file())

    def test_explicit_order(self):
        with env_without_skills_root(WS_SKILLS_ROOT=str(self.skills)):
            code, out = run_cli(self.tree.root, "new", "x-skill", "--order", "7")
        self.assertEqual(code, 0, out)
        self.assertTrue(self.path("cursor", "07-x-skill.json").is_file())

    def test_commit_comes_from_the_skill_repo_when_available(self):
        short = make_skill_repo(self.skills, "mi-skill")
        with env_without_skills_root(WS_SKILLS_ROOT=str(self.skills)):
            self.assertEqual(run_cli(self.tree.root, "new", "mi-skill")[0], 0)
        ep = json.loads(self.path("cursor", "01-mi-skill.json").read_text(encoding="utf-8"))
        self.assertEqual(ep["skill"]["commit"], short)
        self.assertRegex(ep["skill"]["date"], r"^\d{4}-\d{2}-\d{2}$")

    def test_commit_is_a_placeholder_without_the_repo(self):
        with env_without_skills_root(WS_SKILLS_ROOT=str(self.skills)):
            self.assertEqual(run_cli(self.tree.root, "new", "ausente")[0], 0)
        ep = json.loads(self.path("cursor", "01-ausente.json").read_text(encoding="utf-8"))
        self.assertEqual(ep["skill"]["commit"], "COMPLETAR")

    def test_refuses_to_overwrite(self):
        with env_without_skills_root(WS_SKILLS_ROOT=str(self.skills)):
            self.assertEqual(run_cli(self.tree.root, "new", "mi-skill", "--order", "2")[0], 0)
            p = self.path("cursor", "02-mi-skill.json")
            p.write_text('{"mine": true}', encoding="utf-8")
            code, out = run_cli(self.tree.root, "new", "mi-skill", "--order", "2")
        self.assertEqual(code, 1, out)
        self.assertEqual(p.read_text(encoding="utf-8"), '{"mine": true}')

    def test_refuses_a_second_episode_with_the_same_id_or_order(self):
        with env_without_skills_root(WS_SKILLS_ROOT=str(self.skills)):
            self.assertEqual(run_cli(self.tree.root, "new", "mi-skill", "--order", "2")[0], 0)
            self.assertEqual(run_cli(self.tree.root, "new", "mi-skill", "--order", "3")[0], 1)
            self.assertEqual(run_cli(self.tree.root, "new", "otra", "--order", "2")[0], 1)
        self.assertEqual(len(list((self.tree.root / "episodes" / "cursor").glob("*.json"))), 1)

    def test_id_names_the_episode_after_the_skill_in_a_monorepo(self):
        repo = "teamwayofwork"
        with env_without_skills_root(WS_SKILLS_ROOT=str(self.skills)):
            code, out = run_cli(self.tree.root, "new", repo, "--id", "auditing-repos", "--order", "2")
            self.assertEqual(code, 0, out)
            p = self.path("cursor", "02-auditing-repos.json")
            self.assertTrue(p.is_file(), out)
            ep = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual((ep["id"], ep["skill"]["repo"]), ("auditing-repos", repo))
            code, out = run_cli(self.tree.root, "new", repo, "--id", "np-api")
            self.assertEqual(code, 0, out)
            self.assertTrue(self.path("cursor", "03-np-api.json").is_file(), out)
            code, out = run_cli(self.tree.root, "new", repo, "--id", "np-api", "--order", "9")
        self.assertEqual(code, 1, out)
        self.assertIn("np-api", out)

    def test_scaffold_create_takes_an_id(self):
        with env_without_skills_root(WS_SKILLS_ROOT=str(self.skills)):
            p = scaffold.create(self.tree.root, "mono", id="uno")
            self.assertEqual(p.name, "01-uno.json")
            with self.assertRaises(scaffold.ScaffoldError):
                scaffold.create(self.tree.root, "mono", id="uno")
            with self.assertRaises(scaffold.ScaffoldError):
                scaffold.create(self.tree.root, "mono", id="../x")

    def test_rejects_unsafe_names_and_bad_series(self):
        for bad in ("../x", "a/b", "A B", "_x", ""):
            self.assertEqual(run_cli(self.tree.root, "new", bad)[0], 1, bad)
        self.assertEqual(run_cli(self.tree.root, "new", "ok", "--series", "nope")[0], 2)
        self.assertFalse(list((self.tree.root / "episodes").glob("*/*.json")))

    def test_new_skeleton_then_validate_names_every_pending_place(self):
        with env_without_skills_root(WS_SKILLS_ROOT=str(self.skills)):
            run_cli(self.tree.root, "new", "mi-skill")
        code, out = run_cli(self.tree.root, "validate")
        self.assertEqual(code, 1)
        self.assertIn("cursor/01-mi-skill.json chapter 0 (instalar) step 0: COMPLETAR still in 'cmd'", out)
        self.assertIn("chapter 4 (cierre)", out)


if __name__ == "__main__":
    unittest.main()
