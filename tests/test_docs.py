"""The human docs must not point at files that do not exist."""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote

from tests.helpers import ROOT

LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)")


def broken_links(md_file: Path) -> list:
    """Relative links in md_file whose target file does not exist."""
    bad = []
    text = md_file.read_text(encoding="utf-8")
    for target in LINK.findall(text):
        if re.match(r"^([a-z][a-z0-9+.-]*:|#)", target, re.I):
            continue
        path = unquote(target.split("#", 1)[0])
        if path and not (md_file.parent / path).exists():
            bad.append(target)
    return bad


class DocsTest(unittest.TestCase):
    def test_checker_flags_a_broken_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "doc.md"
            (Path(tmp) / "ok.md").write_text("x", encoding="utf-8")
            doc.write_text("[ok](ok.md) [web](https://example.com) [anchor](#a) [roto](nada.md#x)",
                           encoding="utf-8")
            self.assertEqual(broken_links(doc), ["nada.md#x"])

    def test_relative_links_resolve(self):
        docs = [ROOT / "README.md", ROOT / "docs" / "presentar.md", ROOT / "docs" / "guion.md"]
        for doc in docs:
            self.assertTrue(doc.is_file(), "missing %s" % doc)
            self.assertEqual(broken_links(doc), [], doc.name)


if __name__ == "__main__":
    unittest.main()
