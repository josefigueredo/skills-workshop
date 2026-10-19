"""Run the JS suites in headless Chrome and check what the harness reports."""
from __future__ import annotations

import os
import re
import subprocess
import unittest
from html import unescape
from pathlib import Path

from tests.helpers import ROOT

DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CHROME = os.environ.get("CHROME", DEFAULT_CHROME)
HARNESS = ROOT / "tests" / "js" / "harness.html"
HAVE_CHROME = Path(CHROME).exists()
RENDER_TESTS = 20  # exact count: a test that silently fails to register must show up
ANIMATE_TESTS = 23
PROTOCOL_TESTS = 54
CONTROL_JS = ROOT / "engine" / "control.js"
SKIP_MSG = "Chrome not found at %s (set CHROME to run the JS suites)" % CHROME


def run_suite(name: str) -> str:
    """Run tests/js/harness.html?suite=<name> and return the <pre id=result> text."""
    url = HARNESS.as_uri() + "?suite=" + name
    cmd = [CHROME, "--headless=new", "--disable-gpu", "--allow-file-access-from-files",
           "--virtual-time-budget=5000", "--dump-dom", url]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          universal_newlines=True, timeout=120)
    m = re.search(r'<pre id="result">(.*?)</pre>', proc.stdout, re.S)
    if not m:
        raise AssertionError("no result in harness output for suite %r" % name)
    return unescape(m.group(1)).strip()


@unittest.skipUnless(HAVE_CHROME, SKIP_MSG)
class EngineSuites(unittest.TestCase):
    def test_nav_suite(self):
        result = run_suite("nav")
        self.assertIn("FAIL 0", result, result)
        n = int(re.search(r"PASS (\d+)", result).group(1))
        self.assertGreaterEqual(n, 1, result)

    def test_harness_reports_failures(self):
        result = run_suite("fixture-fail")
        self.assertIn("PASS 1 FAIL 1", result, result)
        self.assertIn("fails on purpose", result)

    def assert_reports_failure(self, suite):
        result = run_suite(suite)
        n = int(re.search(r"FAIL (\d+)", result).group(1))
        self.assertGreaterEqual(n, 1, result)
        return result

    def test_suite_without_tests_fails(self):
        result = self.assert_reports_failure("fixture-empty")
        self.assertIn("zero tests", result)

    def test_missing_engine_script_fails(self):
        result = self.assert_reports_failure("fixture-missing")
        self.assertIn("does-not-exist.js", result)

    def test_missing_test_file_fails(self):
        result = self.assert_reports_failure("no-such-suite")
        self.assertIn("no-such-suite.test.js", result)

    def test_render_suite(self):
        result = run_suite("render")
        self.assertIn("FAIL 0", result, result)
        self.assertIn("PASS %d " % RENDER_TESTS, result + " ", result)

    def test_animate_suite(self):
        result = run_suite("animate")
        self.assertIn("FAIL 0", result, result)
        self.assertIn("PASS %d " % ANIMATE_TESTS, result + " ", result)

    def test_protocol_suite(self):
        result = run_suite("protocol")
        self.assertIn("FAIL 0", result, result)
        self.assertIn("PASS %d " % PROTOCOL_TESTS, result + " ", result)


def function_body(src: str, name: str) -> str:
    """Return the brace-matched body of `function <name>(...) {...}` in src ('' if absent)."""
    m = re.search(r"function\s+%s\s*\([^)]*\)\s*\{" % re.escape(name), src)
    if not m:
        return ""
    depth, i = 1, m.end()
    while i < len(src) and depth:
        depth += {"{": 1, "}": -1}.get(src[i], 0)
        i += 1
    return src[m.end():i - 1]


class StageWindowOpen(unittest.TestCase):
    def test_window_open_only_in_click_handler(self):
        src = CONTROL_JS.read_text(encoding="utf-8")
        self.assertEqual(src.count("window.open("), 1, "exactly one window.open( in control.js")
        body = function_body(src, "onOpenStageClick")
        self.assertIn("window.open(", body, "window.open( must live in onOpenStageClick")
        self.assertIn('"ws-stage"', body)
        bound = re.findall(r'(?:getElementById|\$)\("([\w-]+)"\)\.addEventListener\("click",\s*onOpenStageClick\)', src)
        self.assertIn("open-stage", bound, "onOpenStageClick bound to the «Abrir escenario» button")
        html = (ROOT / "engine" / "control.html").read_text(encoding="utf-8")
        self.assertRegex(html, r'<button[^>]*id="open-stage"[^>]*>Abrir escenario</button>')


if __name__ == "__main__":
    unittest.main()
