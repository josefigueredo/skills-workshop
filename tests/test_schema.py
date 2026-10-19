import copy
import subprocess
import sys
import unittest

from tests.helpers import ROOT, TempTree, minimal_episode
from ws import schema


def step_of(ep, i):
    return ep["chapters"][0]["steps"][i]


class SchemaTests(unittest.TestCase):
    def test_minimal_episode_is_valid(self):
        self.assertEqual(schema.validate(minimal_episode(), "x.json"), [])

    def test_unknown_step_type_names_file_chapter_and_step(self):
        ep = minimal_episode()
        ep["chapters"][0]["steps"][1] = {"type": "foo", "source": "real"}
        msgs = schema.validate(ep, "x.json")
        self.assertEqual(len(msgs), 1)
        self.assertIn("x.json", msgs[0])
        self.assertIn("chapter 0 (instalar) step 1", msgs[0])
        self.assertIn("unknown step type 'foo'", msgs[0])

    def test_missing_required_field_per_type(self):
        for i, step in enumerate(minimal_episode()["chapters"][0]["steps"]):
            for field in [k for k in step if k not in ("type", "source", "cwd")]:
                with self.subTest(type=step["type"], field=field):
                    ep = minimal_episode()
                    del step_of(ep, i)[field]
                    msgs = schema.validate(ep, "x.json")
                    self.assertEqual(len(msgs), 1, msgs)
                    self.assertIn("chapter 0 (instalar) step %d" % i, msgs[0])
                    self.assertIn("missing '%s'" % field, msgs[0])

    def test_source_required_and_closed_set(self):
        ep = minimal_episode()
        del step_of(ep, 1)["source"]
        self.assertIn("missing 'source'", schema.validate(ep, "x.json")[0])
        ep = minimal_episode()
        step_of(ep, 1)["source"] = "guess"
        self.assertIn("source must be 'real' or 'inferido'", schema.validate(ep, "x.json")[0])

    def test_real_term_needs_cwd(self):
        ep = minimal_episode()
        del step_of(ep, 0)["cwd"]
        self.assertIn("real term step needs 'cwd'", schema.validate(ep, "x.json")[0])
        ep = minimal_episode()
        step_of(ep, 0)["cwd"] = "demo/mi-servicio"
        self.assertIn("must start with '~'", schema.validate(ep, "x.json")[0])
        ep = minimal_episode()
        step_of(ep, 0)["source"] = "inferido"
        del step_of(ep, 0)["cwd"]
        self.assertEqual(schema.validate(ep, "x.json"), [])

    def test_unknown_screen(self):
        ep = minimal_episode()
        ep["chapters"][0]["screen"] = "hologram"
        msgs = schema.validate(ep, "x.json")
        self.assertEqual(len(msgs), 1)
        self.assertIn("unknown screen 'hologram'", msgs[0])

    def test_optional_fields_are_typed(self):
        ep = minimal_episode()
        step_of(ep, 1)["pause"] = "yes"
        step_of(ep, 2)["notes"] = 5
        self.assertEqual(len(schema.validate(ep, "x.json")), 2)

    def test_top_level_and_chapter_requirements(self):
        for field in ("id", "series", "order", "title", "pitch", "skill", "workspace", "chapters"):
            with self.subTest(field=field):
                ep = minimal_episode()
                del ep[field]
                self.assertTrue(any("missing '%s'" % field in m for m in schema.validate(ep, "x.json")))
        ep = minimal_episode(chapters=[])
        self.assertTrue(any("chapters" in m for m in schema.validate(ep, "x.json")))
        ep = minimal_episode()
        ep["pitch"] = {"ask": "a"}
        self.assertTrue(any("pitch" in m and "does" in m for m in schema.validate(ep, "x.json")))
        ep = minimal_episode()
        ep["workspace"] = {}
        self.assertTrue(any("workspace" in m and "repo" in m for m in schema.validate(ep, "x.json")))
        for field in ("id", "title", "screen", "steps"):
            ep = minimal_episode()
            del ep["chapters"][0][field]
            self.assertTrue(any("missing '%s'" % field in m for m in schema.validate(ep, "x.json")), field)
        ep = minimal_episode(series="nope")
        self.assertTrue(any("series" in m for m in schema.validate(ep, "x.json")))

    def test_faq_items_need_q_and_a(self):
        ep = minimal_episode()
        ep["chapters"][0]["faq"] = [{"q": "¿?"}]
        msgs = schema.validate(ep, "x.json")
        self.assertEqual(len(msgs), 1)
        self.assertIn("faq 0", msgs[0])
        self.assertIn("missing 'a'", msgs[0])

    def test_chapter_ids_unique_within_episode(self):
        ep = minimal_episode()
        ep["chapters"].append(copy.deepcopy(ep["chapters"][0]))
        msgs = schema.validate(ep, "x.json")
        self.assertEqual(len(msgs), 1)
        self.assertIn("duplicate chapter id 'instalar'", msgs[0])


class TreeTests(unittest.TestCase):
    def test_load_all_sorted_by_series_then_order(self):
        with TempTree() as t:
            t.write("cursor", "b.json", minimal_episode(id="b", order=2))
            t.write("cursor", "a.json", minimal_episode(id="a", order=1))
            t.write("claude-code", "c.json", minimal_episode(id="c", series="claude-code", order=1))
            got = [(e["series"], e["order"]) for e in schema.load_all(t.root)]
            self.assertEqual(got, [("claude-code", 1), ("cursor", 1), ("cursor", 2)])

    def test_series_matches_folder(self):
        with TempTree() as t:
            t.write("cursor", "a.json", minimal_episode(series="claude-code"))
            msgs = schema.check_tree(t.root)
            self.assertEqual(len(msgs), 1)
            self.assertIn("folder 'cursor'", msgs[0])
            self.assertIn("series 'claude-code'", msgs[0])

    def test_duplicate_ids_across_files(self):
        with TempTree() as t:
            t.write("cursor", "a.json", minimal_episode(id="same", order=1))
            t.write("cursor", "b.json", minimal_episode(id="same", order=2))
            msgs = schema.check_tree(t.root)
            self.assertEqual(len(msgs), 1)
            self.assertIn("duplicate episode id 'same'", msgs[0])

    def test_bad_json_is_reported_not_raised(self):
        with TempTree() as t:
            (t.root / "episodes" / "cursor").mkdir()
            (t.root / "episodes" / "cursor" / "a.json").write_text("{nope", encoding="utf-8")
            msgs = schema.check_tree(t.root)
            self.assertEqual(len(msgs), 1)
            self.assertIn("invalid JSON", msgs[0])


class CliTests(unittest.TestCase):
    def run_cli(self, *args, root=None):
        cmd = [sys.executable, str(ROOT / "build.py")]
        if root is not None:
            cmd += ["--root", str(root)]
        return subprocess.run(cmd + list(args), capture_output=True, text=True)

    def test_validate_cli_exit_codes(self):
        with TempTree() as t:
            t.write("cursor", "ok.json", minimal_episode())
            r = self.run_cli("validate", root=t.root)
            self.assertEqual(r.returncode, 0, r.stderr)
            t.write("cursor", "bad.json", minimal_episode(id="bad", order=2, chapters=[]))
            r = self.run_cli("validate", root=t.root)
            self.assertEqual(r.returncode, 1)
            self.assertIn("bad.json", r.stdout)
        self.assertEqual(self.run_cli("--nope").returncode, 2)
        self.assertEqual(self.run_cli().returncode, 2)


if __name__ == "__main__":
    unittest.main()
