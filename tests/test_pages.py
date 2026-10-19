"""The GitHub Pages workflow: its shape is checked as text (no YAML parser in the stdlib)."""
from __future__ import annotations

import re
import unittest

from tests.helpers import ROOT

WORKFLOW = ROOT / ".github" / "workflows" / "pages.yml"


class PagesWorkflow(unittest.TestCase):
    def setUp(self):
        self.assertTrue(WORKFLOW.is_file(), "missing %s" % WORKFLOW)
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_triggers(self):
        self.assertRegex(self.text, r"(?m)^on:\n  push:\n    branches: \[main\]\n  workflow_dispatch:")

    def test_permissions_and_concurrency(self):
        for line in ("pages: write", "id-token: write", "contents: read"):
            self.assertIn("  " + line, self.text)
        self.assertRegex(self.text, r"(?m)^concurrency:\n  group: pages\n")

    def test_steps_in_order(self):
        order = ["actions/checkout@v4", "actions/setup-python@v5", "python3 build.py validate",
                 "python3 -m unittest tests.test_bundle", "actions/configure-pages@v5",
                 "actions/upload-pages-artifact@v3", "actions/deploy-pages@v4"]
        pos = [self.text.find(s) for s in order]
        self.assertNotIn(-1, pos, dict(zip(order, pos)))
        self.assertEqual(pos, sorted(pos))
        self.assertIn('python-version: "3.12"', self.text)
        self.assertRegex(self.text, r"upload-pages-artifact@v3\n\s+with:\n\s+path: dist")

    def test_deploy_environment(self):
        self.assertRegex(self.text, r"environment:\n\s+name: github-pages")

    def test_no_secrets_or_personal_data(self):
        self.assertNotRegex(self.text, r"/Users/|secrets\.")


if __name__ == "__main__":
    unittest.main()
