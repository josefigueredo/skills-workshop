"""Privacy check: generic rules, external leak terms, masked excerpts, CLI."""
from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import build  # noqa: E402
from ws import privacy  # noqa: E402

HITS = {
    "user-path-mac": ("see /Users/jdoe/code here", "see /Users/ alone"),
    "user-path-linux": ("at /home/jdoe/x", "at /home/ alone"),
    "email": ("mail jane.doe@corp.io now", "mail demo@example.com now"),
    "secret": ("tok ghp_abcdef123456", "tok nothing here"),
}


def _env(**kw):
    clean = {k: v for k, v in os.environ.items() if k != "WS_LEAK_TERMS"}
    clean.update(kw)
    return mock.patch.dict(os.environ, clean, clear=True)


class Tmp(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.root = Path(self._t.name)

    def put(self, rel, text, mode="w"):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if mode == "wb":
            p.write_bytes(text)
        else:
            p.write_text(text, encoding="utf-8")
        return p


class TestGenericRules(Tmp):
    def test_each_rule_hits_and_near_miss_passes(self):
        with _env():
            rules = privacy.rules()
        for label, (bad, ok) in HITS.items():
            with self.subTest(label=label):
                self.assertTrue(any(r.search(bad) for r in rules.values()), bad)
                self.assertFalse(any(r.search(ok) for r in rules.values()), ok)

    def test_other_secret_formats(self):
        with _env():
            rules = privacy.rules()
        for s in ("github_pat_11AAA", "xoxb-123", "xoxp-123", "AKIA" + "A" * 16,
                  "-----BEGIN RSA PRIVATE KEY-----", "-----BEGIN PRIVATE KEY-----"):
            self.assertTrue(any(r.search(s) for r in rules.values()), s)
        self.assertFalse(any(r.search("AKIA short") for r in rules.values()))

    def test_scan_format_and_binary_skipped(self):
        with _env():
            p = self.put("episodes/a.json", 'x\n{"m": "jane@corp.io"}\n')
            self.put("dist/b.bin", b"\xff\xfe jane@corp.io", "wb")
            out = privacy.scan([self.root / "episodes", self.root / "dist"])
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].startswith("%s:2: " % p), out[0])
        self.assertIn(": email: ", out[0])


class TestLeakTerms(Tmp):
    def test_external_terms_file_adds_patterns(self):
        terms = self.put("terms.txt", "# comment\n\nacme-secret\\d+\n")
        f = self.put("demo/x.txt", "ok line\nuses acme-secret42 here\n")
        with _env(WS_LEAK_TERMS=str(terms)):
            self.assertIn("leak-term", privacy.rules())
            out = privacy.scan([f])
        self.assertEqual(len(out), 1)
        self.assertIn(":2: leak-term: ", out[0])

    def test_without_env_only_generic(self):
        f = self.put("demo/x.txt", "acme-secret42\n")
        with _env():
            self.assertNotIn("leak-term", privacy.rules())
            self.assertEqual(privacy.scan([f]), [])

    def test_invalid_regex_is_error_naming_file_and_line(self):
        terms = self.put("terms.txt", "good\n(bad\n")
        with _env(WS_LEAK_TERMS=str(terms)):
            with self.assertRaises(ValueError) as cm:
                privacy.rules()
        self.assertIn("terms.txt:2", str(cm.exception))

    def test_missing_terms_file_is_error(self):
        with _env(WS_LEAK_TERMS=str(self.root / "nope.txt")):
            with self.assertRaises(ValueError):
                privacy.rules()


class TestExcerpt(Tmp):
    def test_excerpt_never_prints_full_secret(self):
        secret = "ghp_SUPERSECRETTOKEN1234567890"
        f = self.put("demo/x.txt", "prefix text before %s and after text\n" % secret)
        with _env():
            out = privacy.scan([f])
        self.assertEqual(len(out), 1)
        excerpt = out[0].split(": ", 3)[-1]
        self.assertLessEqual(len(excerpt), 20)
        self.assertNotIn(secret, out[0])
        self.assertNotIn("SUPERSECRET", out[0])
        self.assertIn("ghp_", excerpt)

    def test_short_match_not_fully_shown(self):
        terms = self.put("t.txt", "abc\n")
        f = self.put("demo/x.txt", "abc\n")
        with _env(WS_LEAK_TERMS=str(terms)):
            out = privacy.scan([f])
        self.assertNotIn(": abc", out[0])


class TestCli(Tmp):
    def run_cli(self, *argv):
        o, e = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
            try:
                code = build.main(list(argv))
            except SystemExit as x:
                code = x.code
        return code, o.getvalue(), e.getvalue()

    def test_check_cli_exit_1_on_hit(self):
        self.put("episodes/cursor/a.json", '{"t": "/Users/jdoe/x"}')
        with _env():
            code, out, _ = self.run_cli("--root", str(self.root), "check")
        self.assertEqual(code, 1)
        self.assertIn("user-path-mac", out)

    def test_check_cli_clean_and_missing_dirs_ok(self):
        self.put("episodes/cursor/a.json", '{"t": "demo@example.com"}')
        with _env():
            code, out, _ = self.run_cli("--root", str(self.root), "check")
        self.assertEqual(code, 0)
        self.assertIn("ok", out)

    def test_check_cli_scans_demo_and_dist(self):
        self.put("dist/a.html", "AKIA" + "B" * 16)
        with _env():
            code, _, _ = self.run_cli("--root", str(self.root), "check")
        self.assertEqual(code, 1)

    def test_check_cli_invalid_terms_exit_2(self):
        terms = self.put("t.txt", "(bad\n")
        with _env(WS_LEAK_TERMS=str(terms)):
            code, _, err = self.run_cli("--root", str(self.root), "check")
        self.assertEqual(code, 2)
        self.assertIn("t.txt:1", err)


if __name__ == "__main__":
    unittest.main()
