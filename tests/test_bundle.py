import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from html import unescape
from pathlib import Path

import build
from tests.helpers import ROOT, TempTree, minimal_episode
from tests.test_engine import CHROME, HAVE_CHROME, SKIP_MSG
from ws import bundle

NAMES = ["serie-cursor.html", "serie-claude-code.html", "control.html", "index.html"]
STAGE_NAMES = NAMES[:3]


def with_engine(tree):
    shutil.copytree(ROOT / "engine", tree.root / "engine")
    return tree


def strip_comments(html):
    """The templates carry an explanatory HTML comment that quotes the episodes tag."""
    return re.sub(r"<!--.*?-->", "", html, flags=re.S)


def episodes_in(html):
    html = strip_comments(html)
    m = re.search(r'<script type="application/json" id="episodes">(.*?)</script>', html, re.S)
    assert m, "no episodes script"
    return json.loads(m.group(1))


def two_series_tree():
    tree = with_engine(TempTree())
    tree.write("cursor", "02-b.json", minimal_episode(id="cur-b", order=2))
    tree.write("cursor", "01-a.json", minimal_episode(id="cur-a", order=1))
    tree.write("claude-code", "01-c.json", minimal_episode(id="cc-a", series="claude-code", order=1))
    return tree


def run_build(root, *extra):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = build.main(["--root", str(root), "build"] + list(extra))
    return code, out.getvalue() + err.getvalue()


class BundleContent(unittest.TestCase):
    def test_build_writes_every_file(self):
        with two_series_tree() as tree:
            paths = bundle.build(tree.root)
            self.assertEqual([p.name for p in paths], NAMES)
            for p in paths:
                self.assertEqual(p.parent, tree.root / "dist")
                self.assertTrue(p.is_file())

    def test_self_contained(self):
        with two_series_tree() as tree:
            for p in bundle.build(tree.root):
                if p.name == "index.html":  # its own rules: tests/test_index.py
                    continue
                html = p.read_text(encoding="utf-8")
                self.assertNotRegex(html, r"\bsrc=", p.name)
                self.assertNotRegex(html, r"""\bhref=(?!["']?#)""", p.name)
                self.assertNotIn("url(http", html, p.name)
                self.assertNotRegex(html, r"<!--(CSS|JS|EPISODES)-->", p.name)

    def test_stage_files_carry_only_their_series_control_carries_all(self):
        with two_series_tree() as tree:
            bundle.build(tree.root)
            d = tree.root / "dist"
            cur = episodes_in((d / "serie-cursor.html").read_text(encoding="utf-8"))
            cc = episodes_in((d / "serie-claude-code.html").read_text(encoding="utf-8"))
            ctl = episodes_in((d / "control.html").read_text(encoding="utf-8"))
            self.assertEqual([e["id"] for e in cur], ["cur-a", "cur-b"])
            self.assertEqual([e["id"] for e in cc], ["cc-a"])
            self.assertEqual([e["id"] for e in ctl], ["cc-a", "cur-a", "cur-b"])

    def test_zero_episodes_for_a_series_still_builds(self):
        with with_engine(TempTree()) as tree:
            tree.write("cursor", "01-a.json", minimal_episode(id="cur-a"))
            bundle.build(tree.root)
            html = (tree.root / "dist" / "serie-claude-code.html").read_text(encoding="utf-8")
            self.assertEqual(episodes_in(html), [])

    def test_slot_order_and_script_per_file(self):
        with two_series_tree() as tree:
            bundle.build(tree.root)
            d = tree.root / "dist"
            for name, last in (("serie-cursor.html", "Stage ="), ("control.html", "Control =")):
                html = strip_comments((d / name).read_text(encoding="utf-8"))
                scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
                self.assertEqual(len(scripts), 4, name)
                for s, marker in zip(scripts, ["Nav =", "Render =", "Animate =", last]):
                    self.assertIn("var " + marker, s, name)
            html = (d / "serie-cursor.html").read_text(encoding="utf-8")
            self.assertIn("--ws-w", html.split("</style>")[0])

    def test_script_close_in_step_text_does_not_break_out(self):
        evil = "</script><script>alert(1)</script><!-- & </SCRIPT>"
        ep = minimal_episode(id="evil")
        ep["chapters"][0]["steps"][1]["text"] = evil
        with with_engine(TempTree()) as tree:
            tree.write("cursor", "01-e.json", ep)
            bundle.build(tree.root)
            for name in ("serie-cursor.html", "control.html"):
                html = strip_comments((tree.root / "dist" / name).read_text(encoding="utf-8"))
                m = re.search(r'id="episodes">(.*?)</script>', html, re.S)
                self.assertNotRegex(m.group(1), r"[<>&]")
                self.assertEqual(html.lower().count("</script"), 5, name)
                self.assertEqual(episodes_in(html), [ep])

    def test_capture_only_steps_are_stripped_from_every_bundle(self):
        ep = minimal_episode(id="co")
        steps = ep["chapters"][0]["steps"]
        steps.insert(1, {"type": "term", "cmd": "ia step done", "out": ["done"], "source": "real",
                         "cwd": "~", "capture_only": True})
        with with_engine(TempTree()) as tree:
            src = tree.write("cursor", "01-co.json", ep)
            before = src.read_text(encoding="utf-8")
            bundle.build(tree.root)
            for name in ("serie-cursor.html", "control.html"):
                got = episodes_in((tree.root / "dist" / name).read_text(encoding="utf-8"))[0]
                cmds = [s.get("cmd") for s in got["chapters"][0]["steps"]]
                self.assertNotIn("ia step done", cmds, name)
                self.assertEqual(len(got["chapters"][0]["steps"]), len(steps) - 1, name)
            self.assertEqual(src.read_text(encoding="utf-8"), before, "the JSON keeps the step")

    def test_a_page_step_carries_its_html_and_not_its_path(self):
        ep = minimal_episode(id="pg")
        ep["chapters"][0]["steps"].append({"type": "page", "title": "vista.html", "src": "pages/v.html",
                                           "source": "real"})
        with with_engine(TempTree()) as tree:
            tree.write("cursor", "01-pg.json", ep)
            (tree.root / "episodes" / "pages").mkdir()
            (tree.root / "episodes" / "pages" / "v.html").write_text("<p>Vista</p></script>", encoding="utf-8")
            bundle.build(tree.root)
            text = (tree.root / "dist" / "serie-cursor.html").read_text(encoding="utf-8")
            page = episodes_in(text)[0]["chapters"][0]["steps"][-1]
            self.assertEqual(page["html"], "<p>Vista</p></script>")
            self.assertNotIn("src", page)
            self.assertEqual(text.count("</script>"), text.count("<script"), "the page cannot close a script")

    def test_episode_key_order_is_kept(self):
        ep = minimal_episode(id="zz")
        with with_engine(TempTree()) as tree:
            tree.write("cursor", "01-z.json", ep)
            bundle.build(tree.root)
            html = (tree.root / "dist" / "control.html").read_text(encoding="utf-8")
            keys = list(episodes_in(html)[0].keys())
            self.assertEqual(keys, list(ep.keys()))

    def test_engine_file_with_script_close_fails_and_writes_nothing(self):
        with two_series_tree() as tree:
            (tree.root / "engine" / "nav.js").write_text('var s = "</ScRiPt>";', encoding="utf-8")
            with self.assertRaises(bundle.BundleError):
                bundle.build(tree.root)
            self.assertFalse((tree.root / "dist").exists())

    def test_missing_slot_fails(self):
        with two_series_tree() as tree:
            p = tree.root / "engine" / "stage.html"
            p.write_text(p.read_text(encoding="utf-8").replace("<!--JS-->", ""), encoding="utf-8")
            with self.assertRaises(bundle.BundleError):
                bundle.build(tree.root)

    def test_deterministic(self):
        with two_series_tree() as tree:
            first = {p.name: p.read_bytes() for p in bundle.build(tree.root)}
            second = {p.name: p.read_bytes() for p in bundle.build(tree.root)}
            self.assertEqual(first, second)
            for data in first.values():
                self.assertNotIn(b"\r", data)


class BuildCommand(unittest.TestCase):
    def test_build_ok_writes_dist(self):
        with two_series_tree() as tree:
            code, out = run_build(tree.root)
            self.assertEqual(code, 0, out)
            for n in NAMES:
                self.assertTrue((tree.root / "dist" / n).is_file())

    def test_validate_failure_exits_1_and_writes_nothing(self):
        with two_series_tree() as tree:
            bad = minimal_episode(id="bad")
            del bad["pitch"]
            tree.write("cursor", "03-bad.json", bad)
            code, out = run_build(tree.root)
            self.assertEqual(code, 1, out)
            self.assertFalse((tree.root / "dist").exists())

    def test_privacy_failure_exits_1_and_writes_nothing(self):
        with two_series_tree() as tree:
            leak = minimal_episode(id="leak")
            leak["chapters"][0]["steps"][1]["text"] = "mirá /Users/someone/x"
            tree.write("cursor", "03-leak.json", leak)
            code, out = run_build(tree.root)
            self.assertEqual(code, 1, out)
            self.assertIn("user-path-mac", out)
            self.assertFalse((tree.root / "dist").exists())

    def test_privacy_failure_keeps_an_existing_dist_untouched(self):
        with two_series_tree() as tree:
            self.assertEqual(run_build(tree.root)[0], 0)
            before = {n: (tree.root / "dist" / n).read_bytes() for n in NAMES}
            leak = minimal_episode(id="leak")
            leak["chapters"][0]["steps"][1]["text"] = "mirá /Users/someone/x"
            tree.write("cursor", "03-leak.json", leak)
            self.assertEqual(run_build(tree.root)[0], 1)
            after = {n: (tree.root / "dist" / n).read_bytes() for n in NAMES}
            self.assertEqual(before, after)

    def test_privacy_scan_covers_the_bundled_output(self):
        with two_series_tree() as tree:
            js = tree.root / "engine" / "nav.js"
            js.write_text(js.read_text(encoding="utf-8") + '\nvar p = "/Users/someone/x";\n',
                          encoding="utf-8")
            code, out = run_build(tree.root)
            self.assertEqual(code, 1, out)
            self.assertIn("dist/", out)
            self.assertFalse((tree.root / "dist").exists())

    def test_bundle_error_exits_1_and_writes_nothing(self):
        with two_series_tree() as tree:
            (tree.root / "engine" / "nav.js").write_text("</script>", encoding="utf-8")
            code, out = run_build(tree.root)
            self.assertEqual(code, 1, out)
            self.assertFalse((tree.root / "dist").exists())


class CommittedDist(unittest.TestCase):
    def test_committed_dist_is_up_to_date(self):
        fresh = bundle.render(ROOT)
        self.assertEqual(sorted(fresh), sorted(NAMES))
        for name, text in fresh.items():
            path = ROOT / "dist" / name
            self.assertTrue(path.is_file(), "dist/%s missing: run `python3 build.py build`" % name)
            self.assertEqual(path.read_bytes(), text.encode("utf-8"),
                             "dist/%s is stale: run `python3 build.py build`" % name)


@unittest.skipUnless(HAVE_CHROME, SKIP_MSG)
class StaticPreview(unittest.TestCase):
    def dump(self, url):
        with tempfile.TemporaryDirectory() as profile:
            cmd = [CHROME, "--headless=new", "--disable-gpu", "--allow-file-access-from-files",
                   "--user-data-dir=" + profile, "--virtual-time-budget=3000", "--dump-dom", url]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  universal_newlines=True, timeout=120)
        # only the rendered canvas: the page also embeds every step as JSON
        m = re.search(r'<div id="ws-canvas"[^>]*>(.*?)<div id="ws-blackout"', proc.stdout, re.S)
        self.assertTrue(m, "no #ws-canvas in the dumped DOM")
        return unescape(m.group(1))

    def test_hash_renders_that_step_in_the_built_file(self):
        ep = minimal_episode(id="prev-ep")
        ep["chapters"][0]["steps"][1]["text"] = "TEXTO-DEL-PASO-ASK"
        ep["chapters"][0]["steps"][3]["md"] = "TEXTO-DEL-PASO-SAY"
        with with_engine(TempTree()) as tree:
            tree.write("cursor", "01-p.json", ep)
            bundle.build(tree.root)
            page = (tree.root / "dist" / "serie-cursor.html").as_uri()
            # flattened: 0 card, 1 term, 2 ask, 3 tool, 4 say; the hash is 1-based (#id/1 = index 0)
            ask = self.dump(page + "#prev-ep/3")
            self.assertNotIn("ws-fade-in", ask)
            self.assertIn("TEXTO-DEL-PASO-ASK", ask)
            self.assertNotIn("TEXTO-DEL-PASO-SAY", ask)
            say = self.dump(page + "#prev-ep/5")
            self.assertIn("TEXTO-DEL-PASO-SAY", say)


if __name__ == "__main__":
    unittest.main()
