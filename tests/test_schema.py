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
        self.assertIn("'cwd'", schema.validate(ep, "x.json")[0])
        ep = minimal_episode()
        step_of(ep, 0)["source"] = "inferido"
        del step_of(ep, 0)["cwd"]
        self.assertEqual(schema.validate(ep, "x.json"), [])

    def test_real_cwd_is_strictly_home_relative(self):
        for good in ("~", "~/mi-servicio", "~/mi-servicio/api"):
            with self.subTest(cwd=good):
                ep = minimal_episode()
                step_of(ep, 0)["cwd"] = good
                self.assertEqual(schema.validate(ep, "x.json"), [])
        for bad in ("~foo", "~root", "~/..", "~/a/../b", "~/mi-servicio/../..", "~\\x"):
            with self.subTest(cwd=bad):
                ep = minimal_episode()
                step_of(ep, 0)["cwd"] = bad
                msgs = schema.validate(ep, "x.json")
                self.assertEqual(len(msgs), 1, msgs)
                self.assertIn("'cwd'", msgs[0])

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

    def test_in_zsh_only_on_term(self):
        ep = minimal_episode()
        ep["chapters"][0]["screen"] = "cursor-full"
        step_of(ep, 0)["in"] = "zsh"
        self.assertEqual(schema.validate(ep, "x.json"), [])
        step_of(ep, 0)["in"] = "chat"
        step_of(ep, 1)["in"] = "zsh"
        msgs = schema.validate(ep, "x.json")
        self.assertEqual(len(msgs), 2, msgs)
        self.assertIn("step 0: 'in' must be \"zsh\"", msgs[0])
        self.assertIn("step 1: 'in' is only valid on a term step", msgs[1])

    def test_in_zsh_only_in_cursor_full_or_claude_code_chapter(self):
        for screen in ("terminal", "cursor-agent"):
            with self.subTest(screen=screen):
                ep = minimal_episode()
                ep["chapters"][0]["screen"] = screen
                step_of(ep, 0)["in"] = "zsh"
                msgs = schema.validate(ep, "x.json")
                self.assertEqual(len(msgs), 1, msgs)
                self.assertIn("chapter 0 (instalar) step 0: 'in' \"zsh\" is only valid in a cursor-full or "
                              "claude-code chapter", msgs[0])

    def test_in_zsh_on_claude_code_is_the_persons_bang_command(self):
        ep = minimal_episode()
        ep["chapters"][0]["screen"] = "claude-code"
        step_of(ep, 0)["in"] = "zsh"
        self.assertEqual(schema.validate(ep, "x.json"), [])

    def test_unknown_keys_are_rejected_everywhere(self):
        cases = [
            ("top level", lambda e: e.update(titel="x"), "x.json: unknown key 'titel'"),
            ("pitch", lambda e: e["pitch"].update(extra=1), "x.json: pitch: unknown key 'extra'"),
            ("skill", lambda e: e["skill"].update(sha="1"), "x.json: skill: unknown key 'sha'"),
            ("workspace", lambda e: e["workspace"].update(file=[]), "x.json: workspace: unknown key 'file'"),
            ("chapter", lambda e: e["chapters"][0].update(subtitel="x"),
             "x.json chapter 0 (instalar): unknown key 'subtitel'"),
            ("step", lambda e: step_of(e, 1).update(txt="x"),
             "x.json chapter 0 (instalar) step 1: unknown key 'txt'"),
            ("misspelt capture-only", lambda e: step_of(e, 0).update(**{"capture-only": True}),
             "x.json chapter 0 (instalar) step 0: unknown key 'capture-only'"),
            ("term key on ask", lambda e: step_of(e, 1).update(cwd="~"),
             "x.json chapter 0 (instalar) step 1: unknown key 'cwd'"),
            ("faq", lambda e: e["chapters"][0].update(faq=[{"q": "a", "a": "b", "x": 1}]),
             "x.json chapter 0 (instalar) faq 0: unknown key 'x'"),
        ]
        for name, mutate, text in cases:
            with self.subTest(name):
                ep = minimal_episode()
                mutate(ep)
                msgs = schema.validate(ep, "x.json")
                self.assertEqual(msgs, [text], msgs)

    def test_allowed_optional_keys_stay_valid(self):
        ep = minimal_episode()
        ep["workspace"].update(files=["a"], chats=[{"title": "t", "age": "2d"}])
        ep["chapters"][0].update(subtitle="s", faq=[{"q": "a", "a": "b"}])
        ep["chapters"][0]["screen"] = "cursor-full"
        for st in ep["chapters"][0]["steps"]:
            st.update(notes="n", pause=True)
        step_of(ep, 0).update(**{"in": "zsh", "capture_only": True})
        self.assertEqual(schema.validate(ep, "x.json"), [])

    def test_capture_only_only_on_real_term(self):
        ep = minimal_episode()
        step_of(ep, 0)["capture_only"] = True
        self.assertEqual(schema.validate(ep, "x.json"), [])
        cases = [
            (lambda s: s.update(capture_only="yes"), 0, "'capture_only' must be true"),
            (lambda s: s.update(capture_only=False), 0, "'capture_only' must be true"),
            (lambda s: s.update(capture_only=True), 1, "'capture_only' is only valid on a real term step"),
        ]
        for mutate, i, text in cases:
            with self.subTest(text=text, step=i):
                e = minimal_episode()
                mutate(step_of(e, i))
                msgs = schema.validate(e, "x.json")
                self.assertEqual(len(msgs), 1, msgs)
                self.assertIn("step %d: %s" % (i, text), msgs[0])
        e = minimal_episode()
        step_of(e, 0).update(source="inferido", capture_only=True)
        msgs = schema.validate(e, "x.json")
        self.assertEqual(len(msgs), 1, msgs)
        self.assertIn("only valid on a real term step", msgs[0])

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

    def test_page_step_needs_a_title_and_an_html_file_under_pages(self):
        def with_page(src):
            ep = minimal_episode()
            ep["chapters"][0]["steps"].append({"type": "page", "title": "vista.html", "src": src, "source": "real"})
            return schema.validate(ep, "x.json")
        self.assertEqual(with_page("pages/jtk-vista.html"), [])
        for bad in ("/etc/x.html", "pages/../x.html", "x.html", "pages/v.txt", "pages/sub/v.html"):
            with self.subTest(src=bad):
                msgs = with_page(bad)
                self.assertEqual(len(msgs), 1, msgs)
                self.assertIn("'src' must be 'pages/<name>.html'", msgs[0])

    def test_an_approve_step_shows_lines_or_the_real_window_page(self):
        def with_approve(**over):
            ep = minimal_episode()
            step = {"type": "approve", "title": "Crear en PLAT", "button": "Apruebo 4", "source": "real"}
            step.update(over)
            ep["chapters"][0]["steps"].append(step)
            return schema.validate(ep, "x.json")
        self.assertEqual(with_approve(src="pages/jtk-crear.html", window="jtk · Jira", width=520, height=300), [])
        self.assertEqual(with_approve(lines=["a"]), [])
        self.assertIn("missing 'lines'", with_approve()[0])
        self.assertIn("'src' must be 'pages/<name>.html'", with_approve(src="x.html")[0])
        for key, bad in (("window", 3), ("width", "520"), ("height", 0), ("width", 4000)):
            with self.subTest(key=key):
                msgs = with_approve(src="pages/v.html", **{key: bad})
                self.assertEqual(len(msgs), 1, msgs)
                self.assertIn("'%s'" % key, msgs[0])

    def test_a_page_file_that_does_not_exist_is_reported(self):
        with TempTree() as t:
            ep = minimal_episode()
            ep["chapters"][0]["steps"].append({"type": "page", "title": "v", "src": "pages/v.html", "source": "real"})
            ep["chapters"][0]["steps"].append({"type": "approve", "title": "A", "button": "Apruebo 1",
                                               "src": "pages/w.html", "source": "real"})
            t.write("cursor", "a.json", ep)
            msgs = schema.check_tree(t.root)
            self.assertEqual(len(msgs), 2, msgs)
            self.assertIn("episodes/pages/v.html does not exist", msgs[0])
            self.assertIn("episodes/pages/w.html does not exist", msgs[1])
            (t.root / "episodes" / "pages").mkdir()
            (t.root / "episodes" / "pages" / "v.html").write_text("<p>v</p>", encoding="utf-8")
            (t.root / "episodes" / "pages" / "w.html").write_text("<p>w</p>", encoding="utf-8")
            self.assertEqual(schema.check_tree(t.root), [])

    def test_a_real_page_step_can_name_the_file_capture_copies_from_the_fake_home(self):
        def with_capture(value, source="real", stype="page"):
            ep = minimal_episode()
            step = {"type": stype, "title": "r.html", "src": "pages/r.html", "source": source, "capture": value}
            if stype == "approve":
                step["button"] = "Apruebo 1"
            ep["chapters"][0]["steps"].append(step)
            return schema.validate(ep, "x.json")
        self.assertEqual(with_capture("~/auditorias/r.html"), [])
        for bad in ("/etc/r.html", "~/../r.html", "r.html", "~", 3):
            with self.subTest(capture=bad):
                msgs = with_capture(bad)
                self.assertEqual(len(msgs), 1, msgs)
                self.assertIn("'capture'", msgs[0])
        self.assertIn("'capture' is only valid on a real page step", with_capture("~/r.html", source="inferido")[0])
        self.assertIn("unknown key 'capture'", with_capture("~/r.html", stype="approve")[0])

    def test_a_captured_page_may_be_missing_only_while_capturing(self):
        with TempTree() as t:
            ep = minimal_episode()
            ep["chapters"][0]["steps"].append({"type": "page", "title": "r", "src": "pages/r.html", "source": "real",
                                               "capture": "~/r.html"})
            ep["chapters"][0]["steps"].append({"type": "page", "title": "v", "src": "pages/v.html", "source": "real"})
            t.write("cursor", "a.json", ep)
            msgs = schema.check_tree(t.root)
            self.assertEqual(len(msgs), 2, msgs)
            msgs = schema.check_tree(t.root, capturing=True)
            self.assertEqual(len(msgs), 1, msgs)
            self.assertIn("episodes/pages/v.html does not exist", msgs[0])

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


class CierreChainTests(unittest.TestCase):
    """The last `say` of each episode's last chapter (the «Cierre») must name the next episode.

    Cursor 00 (Antes de empezar, order 0) IS part of the chain: its Cierre
    already announces episode 1 (inherited-audit), so a reorder would break it.
    """

    @staticmethod
    def closing_say(ep):
        steps = [s for s in ep["chapters"][-1]["steps"] if s.get("type") == "say"]
        return steps[-1]["md"]

    @classmethod
    def by_series(cls):
        out = {}
        for ep in schema.load_all(ROOT):
            out.setdefault(ep["series"], []).append(ep)
        return out

    def test_each_cierre_names_the_next_episode(self):
        for series, eps in self.by_series().items():
            for ep, nxt in zip(eps, eps[1:]):
                md = self.closing_say(ep)
                self.assertIn(nxt["id"], md, "%s/%s: Cierre does not name %s" % (series, ep["id"], nxt["id"]))
                for other in eps:
                    if other["id"] not in (nxt["id"],) and other is not ep:
                        self.assertNotIn("Próximo episodio: " + other["id"], md)

    def test_last_cursor_episode_names_the_claude_code_series(self):
        last = self.by_series()["cursor"][-1]
        self.assertIn("Claude Code", self.closing_say(last))
        first_cc = self.by_series()["claude-code"][0]
        self.assertIn(first_cc["id"], self.closing_say(last))

    def test_last_claude_code_episode_names_no_next_episode(self):
        series = self.by_series()
        last = series["claude-code"][-1]
        md = self.closing_say(last)
        self.assertNotIn("Próximo episodio", md)
        self.assertNotIn("Próxima serie", md)
        for eps in series.values():
            for ep in eps:
                if ep is not last:
                    self.assertNotIn("Próximo episodio: " + ep["id"], md)


if __name__ == "__main__":
    unittest.main()
