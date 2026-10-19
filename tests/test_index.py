"""The landing page dist/index.html: generated, self-contained, escaped, private."""
from __future__ import annotations

import re
import unittest

from tests.helpers import ROOT, TempTree, minimal_episode
from tests.test_bundle import run_build, two_series_tree, with_engine
from ws import bundle, privacy, schema

DOCS = "https://github.com/josefigueredo/skills-workshop/blob/main/docs/"


def links(html):
    return re.findall(r'\b(?:href|src)="([^"]*)"', html)


class IndexPage(unittest.TestCase):
    def test_render_includes_index(self):
        with two_series_tree() as tree:
            self.assertIn("index.html", bundle.render(tree.root))

    def test_build_writes_index_to_dist(self):
        with two_series_tree() as tree:
            code, out = run_build(tree.root)
            self.assertEqual(code, 0, out)
            self.assertTrue((tree.root / "dist" / "index.html").is_file())

    def test_header_and_primary_link(self):
        with two_series_tree() as tree:
            html = bundle.render(tree.root)["index.html"]
            self.assertIn("Taller de skills de team", html)
            self.assertIn('href="control.html"', html)
            self.assertIn("Presentar", html)
            self.assertIn("compartí solo la ventana del escenario", html)
            self.assertIn("var(--ws-k-grad)", html)
            self.assertIn("--ws-font-ui", html)  # tokens.css inlined

    def test_lists_episodes_per_series_with_preview_links(self):
        with two_series_tree() as tree:
            html = bundle.render(tree.root)["index.html"]
            self.assertIn('href="serie-cursor.html#cur-a/1"', html)
            self.assertIn('href="serie-cursor.html#cur-b/1"', html)
            self.assertIn('href="serie-claude-code.html#cc-a/1"', html)
            self.assertLess(html.index("#cur-a/1"), html.index("#cur-b/1"))
            self.assertIn("Hace algo.", html)
            self.assertIn("1 capítulo", html)

    def test_chapter_count_is_pluralised(self):
        ep = minimal_episode(id="two")
        ep["chapters"].append(dict(ep["chapters"][0], id="otro"))
        with with_engine(TempTree()) as tree:
            tree.write("cursor", "01-t.json", ep)
            self.assertIn("2 capítulos", bundle.render(tree.root)["index.html"])

    def test_empty_series_says_so(self):
        with with_engine(TempTree()) as tree:
            tree.write("cursor", "01-a.json", minimal_episode(id="cur-a"))
            html = bundle.render(tree.root)["index.html"]
            self.assertIn("Todavía no hay episodios", html)

    def test_episode_text_is_escaped(self):
        ep = minimal_episode(id="evil", title="<b>T</b> & \"q\"")
        ep["pitch"]["does"] = "<script>alert(1)</script>"
        with with_engine(TempTree()) as tree:
            tree.write("cursor", "01-e.json", ep)
            html = bundle.render(tree.root)["index.html"]
            self.assertNotIn("<script>alert(1)", html)
            self.assertNotIn("<b>T</b>", html)
            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
            self.assertIn("&amp;", html)

    def test_no_external_resources_except_github_docs(self):
        with two_series_tree() as tree:
            html = bundle.render(tree.root)["index.html"]
            self.assertNotRegex(html, r"\bsrc=")
            self.assertNotIn("url(http", html)
            self.assertNotRegex(html, r"<script|<link|<img|@import")
            external = [l for l in links(html) if re.match(r"[a-z][a-z0-9+.-]*:", l, re.I)]
            self.assertEqual(sorted(external), [DOCS + "guion.md", DOCS + "presentar.md"])
            for l in links(html):
                if l not in external:
                    self.assertRegex(l, r"^(control\.html|serie-[a-z-]+\.html#[A-Za-z0-9._-]+/1)$")

    def test_privacy_scan_covers_the_index(self):
        with two_series_tree() as tree:
            js = tree.root / "engine" / "tokens.css"
            js.write_text(js.read_text(encoding="utf-8") + "\n/* /Users/someone/x */\n", encoding="utf-8")
            code, out = run_build(tree.root)
            self.assertEqual(code, 1, out)
            self.assertIn("dist/index.html", out)
            self.assertFalse((tree.root / "dist").exists())

    def test_committed_index_lists_the_committed_episodes(self):
        html = (ROOT / "dist" / "index.html").read_text(encoding="utf-8")
        for ep in schema.load_all(ROOT):
            self.assertIn('href="serie-%s.html#%s/1"' % (ep["series"], ep["id"]), html)
        self.assertEqual(privacy.scan_text(html, "dist/index.html"), [])


if __name__ == "__main__":
    unittest.main()
