"""`build.py duration`: narration math, the 6-12 min range and the Chrome-measured screen time."""
from __future__ import annotations

import contextlib
import io
import subprocess
import unittest
from unittest import mock

import build
from tests.helpers import ROOT, TempTree, minimal_episode
from tests.test_engine import HAVE_CHROME, SKIP_MSG
from ws import duration, schema

MIN = 60000


def run_cli(root, *args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = build.main(["--root", str(root)] + list(args))
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue() + err.getvalue()


def ep_notes(*notes, **over):
    ep = minimal_episode(**over)
    ep["chapters"] = [{"id": "c%d" % i, "title": "C", "screen": "terminal",
                       "steps": [{"type": "say", "md": "x", "source": "inferido", "notes": n}]}
                      for i, n in enumerate(notes)]
    return ep


def fake_measure(table):
    """table: {episode id: (total_ms, [chapter ms...])}."""
    def measure(root, episodes):
        return {e["id"]: {"total": table[e["id"]][0],
                          "chapters": [{"id": c["id"], "ms": ms}
                                       for c, ms in zip(e["chapters"], table[e["id"]][1])]}
                for e in episodes}
    return measure


class Narration(unittest.TestCase):
    def test_words_of_every_step_notes_and_nothing_else(self):
        ep = ep_notes("uno dos tres", "cuatro cinco")
        ep["chapters"][0]["steps"][0]["md"] = "ignorada ignorada ignorada ignorada"
        ep["chapters"][0]["faq"] = [{"q": "no cuenta", "a": "no cuenta"}]
        self.assertEqual(duration.narration_words(ep), 5)

    def test_missing_notes_count_zero_and_ms_is_150_wpm(self):
        ep = ep_notes("a " * 150)
        del ep["chapters"][0]["steps"][0]["notes"]
        self.assertEqual(duration.narration_words(ep), 0)
        self.assertEqual(duration.narration_ms(150), MIN)

    def test_format(self):
        self.assertEqual(duration.fmt(0), "0:00")
        self.assertEqual(duration.fmt(MIN + 5000), "1:05")
        self.assertEqual(duration.fmt(59600), "1:00")


class Report(unittest.TestCase):
    def setUp(self):
        self.tree = TempTree()
        self.addCleanup(self.tree.__exit__, None, None, None)

    def run_duration(self, table, *args):
        with mock.patch.object(duration, "measure", fake_measure(table)), \
                mock.patch.object(duration, "chrome_available", lambda: True):
            return run_cli(self.tree.root, "duration", *args)

    def test_lines_per_episode_and_chapter_in_range_exit_0(self):
        self.tree.write("cursor", "01-a.json", ep_notes("w " * 300, "w " * 300, id="a", order=1))
        code, out = self.run_duration({"a": (4 * MIN, [2 * MIN, 2 * MIN])})
        self.assertEqual(code, 0, out)
        self.assertIn("a: screen 4:00 · narración 4:00 · total 8:00", out)
        self.assertIn("c0: screen 2:00 · narración 2:00 · total 4:00", out)
        self.assertIn("c1: screen 2:00 · narración 2:00 · total 4:00", out)

    def test_out_of_range_exits_1_and_names_the_episode(self):
        self.tree.write("cursor", "01-a.json", ep_notes("w " * 30, id="a", order=1))
        self.tree.write("cursor", "02-b.json", ep_notes("w " * 30, id="b", order=2))
        code, out = self.run_duration({"a": (8 * MIN, [8 * MIN]), "b": (13 * MIN, [13 * MIN])})
        self.assertEqual(code, 1, out)
        self.assertIn("duration: b is outside 6-12 min", out)
        self.assertNotIn("duration: a is outside", out)

    def test_too_short_is_also_out_of_range(self):
        self.tree.write("cursor", "01-a.json", ep_notes("w", id="a", order=1))
        code, out = self.run_duration({"a": (MIN, [MIN])})
        self.assertEqual(code, 1, out)

    def test_order_0_is_listed_but_ignored_by_the_exit_code(self):
        self.tree.write("cursor", "00-z.json", ep_notes("w", id="z", order=0))
        code, out = self.run_duration({"z": (2 * MIN, [2 * MIN])})
        self.assertEqual(code, 0, out)
        self.assertIn("z: screen 2:00", out)
        self.assertIn("setup intro", out)

    def test_an_episode_is_checked_against_its_own_minutes(self):
        self.tree.write("cursor", "01-a.json", ep_notes("w", id="a", order=1, minutes=[1, 4]))
        self.tree.write("cursor", "02-b.json", ep_notes("w", id="b", order=2, minutes=[8, 15]))
        code, out = self.run_duration({"a": (2 * MIN, [2 * MIN]), "b": (13 * MIN, [13 * MIN])})
        self.assertEqual(code, 0, out)
        self.assertIn("a: screen 2:00", out)
        self.assertIn("(rango 1-4 min)", out)
        code, out = self.run_duration({"a": (5 * MIN, [5 * MIN]), "b": (7 * MIN, [7 * MIN])})
        self.assertEqual(code, 1, out)
        self.assertIn("duration: a is outside 1-4 min", out)
        self.assertIn("duration: b is outside 8-15 min", out)

    def test_without_minutes_the_range_is_6_to_12(self):
        self.tree.write("cursor", "01-a.json", ep_notes("w", id="a", order=1))
        code, out = self.run_duration({"a": (13 * MIN, [13 * MIN])})
        self.assertEqual(code, 1, out)
        self.assertIn("(rango 6-12 min)", out)
        self.assertIn("duration: a is outside 6-12 min", out)

    def test_order_0_with_its_own_minutes_is_checked(self):
        self.tree.write("cursor", "00-z.json", ep_notes("w", id="z", order=0, minutes=[1, 2]))
        code, out = self.run_duration({"z": (3 * MIN, [3 * MIN])})
        self.assertEqual(code, 1, out)
        self.assertIn("duration: z is outside 1-2 min", out)

    def test_episode_filter_and_unknown_id(self):
        self.tree.write("cursor", "01-a.json", ep_notes("w", id="a", order=1))
        self.tree.write("cursor", "02-b.json", ep_notes("w", id="b", order=2))
        code, out = self.run_duration({"a": (8 * MIN, [8 * MIN]), "b": (8 * MIN, [8 * MIN])},
                                      "--episode", "b")
        self.assertEqual(code, 0, out)
        self.assertIn("b: screen", out)
        self.assertNotIn("a: screen", out)
        code, out = self.run_duration({}, "--episode", "zzz")
        self.assertEqual(code, 2, out)

    def test_measure_failures_exit_2_without_a_traceback(self):
        self.tree.write("cursor", "01-a.json", ep_notes("w", id="a", order=1))
        for exc in (subprocess.TimeoutExpired("chrome", 1), RuntimeError("no json"), KeyError("a")):
            def boom(root, episodes, exc=exc):
                raise exc
            with mock.patch.object(duration, "measure", boom), \
                    mock.patch.object(duration, "chrome_available", lambda: True):
                code, out = run_cli(self.tree.root, "duration")
            self.assertEqual(code, 2, out)
            self.assertIn("duration: ", out)

    def test_malformed_episode_json_exits_2(self):
        d = self.tree.root / "episodes" / "cursor"
        d.mkdir(parents=True)
        (d / "01-a.json").write_text("{not json", encoding="utf-8")
        with mock.patch.object(duration, "chrome_available", lambda: True):
            code, out = run_cli(self.tree.root, "duration")
        self.assertEqual(code, 2, out)
        self.assertIn("duration: ", out)

    def test_capture_only_steps_count_neither_on_screen_nor_in_narration(self):
        ep = ep_notes("w " * 300, id="a", order=1)
        ep["chapters"][0]["steps"].append({"type": "term", "cmd": "prep", "out": [], "source": "real", "cwd": "~",
                                           "capture_only": True, "notes": "w " * 600})
        self.tree.write("cursor", "01-a.json", ep)
        seen = []

        def measure(root, episodes):
            seen.extend(len(c["steps"]) for e in episodes for c in e["chapters"])
            return fake_measure({"a": (4 * MIN, [4 * MIN])})(root, episodes)
        with mock.patch.object(duration, "measure", measure), \
                mock.patch.object(duration, "chrome_available", lambda: True):
            code, out = run_cli(self.tree.root, "duration")
        self.assertEqual(code, 0, out)
        self.assertEqual(seen, [1], "Chrome must measure the steps the stage shows")
        self.assertIn("a: screen 4:00 · narración 2:00 · total 6:00", out)
        self.assertIn("c0: screen 4:00 · narración 2:00", out)

    def test_a_chapter_count_mismatch_exits_2_instead_of_dropping_chapters(self):
        self.tree.write("cursor", "01-a.json", ep_notes("w " * 300, "w " * 300, id="a", order=1))
        code, out = self.run_duration({"a": (4 * MIN, [4 * MIN])})
        self.assertEqual(code, 2, out)
        self.assertIn("2 chapters but Chrome measured 1", out)

    def test_without_chrome_it_skips_and_exits_0(self):
        self.tree.write("cursor", "01-a.json", ep_notes("w", id="a", order=1))
        with mock.patch.object(duration, "chrome_available", lambda: False):
            code, out = run_cli(self.tree.root, "duration")
        self.assertEqual(code, 0, out)
        self.assertIn("skipped", out)


@unittest.skipUnless(HAVE_CHROME, SKIP_MSG)
class RealEpisodes(unittest.TestCase):
    def test_every_episode_prints_its_line_and_exits_0(self):
        code, out = run_cli(ROOT, "duration")
        self.assertEqual(code, 0, out)
        for ep_id in [e["id"] for e in schema.load_all(ROOT)]:
            self.assertRegex(out, r"(?m)^%s: screen \d+:\d\d · narración \d+:\d\d · total \d+:\d\d" % ep_id)

    def test_screen_time_comes_from_the_engine(self):
        got = duration.measure(ROOT, [minimal_episode()])["demo"]
        self.assertGreater(got["total"], 0)
        self.assertEqual(len(got["chapters"]), 1)


if __name__ == "__main__":
    unittest.main()
