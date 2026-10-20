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

    def test_github_ssh_remote_is_not_an_email(self):
        # Every skill episode clones over SSH; `git@github.com` is GitHub's transport
        # user, not a person. Only that exact address passes.
        with _env():
            rules = privacy.rules()
        ok = "git clone git@github.com:org/repo.git x"
        self.assertFalse(any(r.search(ok) for r in rules.values()), ok)
        for bad in ("jane@github.com", "git@github.com.evil.io", "agit@github.com",
                    "git@github.community", "git@gitlab.com"):
            with self.subTest(bad=bad):
                self.assertTrue(any(r.search(bad) for r in rules.values()), bad)

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

    def test_inline_flag_and_repeated_named_group_lines(self):
        import warnings
        terms = self.put("terms.txt", "(?i)alpha\\d\n(?P<g>beta)\n(?P<g>gamma)\n(delta)\\1\n")
        f = self.put("demo/x.txt", "ALPHA1\nbeta\ngamma\ndeltadelta\ndeltax\n")
        with _env(WS_LEAK_TERMS=str(terms)), warnings.catch_warnings():
            warnings.simplefilter("error")
            out = privacy.scan([f])
        self.assertEqual([o.split(":")[1] for o in out], ["1", "2", "3", "4"])
        self.assertTrue(all(": leak-term: " in o for o in out))

    def test_missing_terms_file_is_error(self):
        with _env(WS_LEAK_TERMS=str(self.root / "nope.txt")):
            with self.assertRaises(ValueError):
                privacy.rules()


class TestAllowList(Tmp):
    """privacy-allow.txt: names the workshop teaches, exempt from leak terms only."""

    def scan_with(self, allow_text, line, terms="brain\n"):
        t = self.put("terms.txt", terms)
        a = self.put("allow.txt", allow_text) if allow_text is not None else self.root / "none.txt"
        f = self.put("demo/x.txt", line + "\n")
        with _env(WS_LEAK_TERMS=str(t)), mock.patch.object(privacy, "ALLOW_FILE", a):
            return privacy.scan([f])

    def test_allowed_name_hides_a_leak_term_inside_it(self):
        self.assertEqual(self.scan_with("# skills\nproduct-brain-mcp\n", "next: product-brain-mcp"), [])

    def test_allowed_name_is_case_insensitive(self):
        self.assertEqual(self.scan_with("product-brain-mcp\n", "Next: Product-Brain-MCP"), [])

    def test_the_term_outside_an_allowed_name_still_hits(self):
        out = self.scan_with("product-brain-mcp\n", "product-brain-mcp and a brain elsewhere")
        self.assertEqual(len(out), 1)
        self.assertIn(": leak-term: ", out[0])

    def test_a_term_crossing_the_edge_of_an_allowed_name_still_hits(self):
        out = self.scan_with("product-brain-mcp\n", "product-brain-mcp-acme", terms="mcp-acme\n")
        self.assertEqual(len(out), 1)

    def test_allowed_name_inside_a_longer_word_is_not_exempt(self):
        out = self.scan_with("product-brain\n", "see myproduct-brainy here", terms="brain\n")
        self.assertEqual(len(out), 1)

    def test_allowed_name_next_to_punctuation_is_exempt(self):
        for line in ("(product-brain-mcp)", "`product-brain-mcp`.", "«product-brain-mcp»", "product-brain-mcp"):
            self.assertEqual(self.scan_with("product-brain-mcp\n", line), [], line)

    def test_allow_list_never_hides_generic_rules(self):
        out = self.scan_with("jane.doe@corp.io\n", "mail jane.doe@corp.io")
        self.assertEqual(len(out), 1)
        self.assertIn(": email: ", out[0])

    def test_missing_allow_file_allows_nothing(self):
        self.assertEqual(len(self.scan_with(None, "product-brain-mcp")), 1)

    def test_repo_allow_file_exists_and_names_the_skill_episodes(self):
        names = privacy.allowed()
        self.assertIn("product-brain-mcp", names)
        self.assertTrue(all(n == n.strip() and n and not n.startswith("#") for n in names))


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
