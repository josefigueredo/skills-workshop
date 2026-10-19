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


if __name__ == "__main__":
    unittest.main()
