#!/usr/bin/env python3
"""Renderer tests. Standard library only:  python3 -m unittest discover -s tests"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import render  # noqa: E402

EXAMPLE = ROOT / "examples" / "oscillator-sync" / "site.json"


def page(**overrides):
    base = {"slug": "index", "title": "T", "sections": [{"id": "a", "title": "A", "components": [{"type": "prose", "body": "x"}]}]}
    base.update(overrides)
    return base


class RenderExample(unittest.TestCase):
    def test_example_site_renders_three_pages_with_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            written = render.render_site(json.loads(EXAMPLE.read_text(encoding="utf-8")), EXAMPLE.parent, out)
            self.assertEqual([p.name for p in written], ["index.html", "methods.html", "results.html"])
            for rel in ("assets/reader.css", "assets/reader.js", "assets/vendor/katex/katex.min.js", "assets/vendor/mermaid/mermaid.min.js", "figures/order-parameter.svg"):
                self.assertTrue((out / rel).is_file(), rel)
            methods = (out / "methods.html").read_text(encoding="utf-8")
            self.assertIn('aria-current="page"', methods)
            self.assertIn("mermaid.min.js", methods)
            self.assertNotIn("mermaid.min.js", (out / "index.html").read_text(encoding="utf-8"))
            self.assertIn('class="page-pager"', methods)

    def test_cli_check(self):
        result = subprocess.run([sys.executable, str(ROOT / "render.py"), str(EXAMPLE), "--check"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


class Contracts(unittest.TestCase):
    def render_one(self, **kw):
        site, pages = render.normalize(page(**kw))
        return render.render_page(site, pages, 0)

    def test_single_page_spec_is_accepted(self):
        html = self.render_one()
        self.assertIn('class="page-shell"', html)
        self.assertIn('class="outline-nav"', html)

    def test_text_is_escaped(self):
        html = self.render_one(title="<script>alert(1)</script>")
        self.assertNotIn("<script>alert(1)", html)
        self.assertIn("&lt;script&gt;", html)

    def test_inline_markup_subset(self):
        out = render.inline("use `a<b` and **bold** and [docs](https://example.org) \\(x^2\\)")
        self.assertIn("<code>a&lt;b</code>", out)
        self.assertIn("<strong>bold</strong>", out)
        self.assertIn('href="https://example.org" target="_blank"', out)
        self.assertIn("\\(x^2\\)", out)

    def test_unsafe_url_rejected(self):
        with self.assertRaises(render.SpecError):
            render.inline("[x](javascript:alert(1))")
        with self.assertRaises(render.SpecError):
            self.render_one(sections=[{"id": "a", "title": "A", "components": [{"type": "figure", "src": "javascript:x", "alt": "a", "caption": "c"}]}])

    def test_unknown_component_rejected(self):
        with self.assertRaises(render.SpecError):
            self.render_one(sections=[{"id": "a", "title": "A", "components": [{"type": "hero-banner"}]}])

    def test_duplicate_section_id_rejected(self):
        sec = {"id": "a", "title": "A", "components": []}
        with self.assertRaises(render.SpecError):
            render.normalize(page(sections=[sec, sec]))

    def test_table_row_width_checked(self):
        with self.assertRaises(render.SpecError):
            self.render_one(sections=[{"id": "a", "title": "A", "components": [{"type": "table", "columns": ["x", "y"], "rows": [["1"]]}]}])

    def test_component_headings_are_skipped_by_outline(self):
        html = self.render_one(sections=[{"id": "a", "title": "A", "components": [{"type": "sequence", "items": [{"title": "s", "body": "b"}]}]}])
        self.assertIn('class="sequence" data-outline-skip', html)

    def test_registry_lists_every_component(self):
        names = {c["name"] for c in render.registry()}
        self.assertEqual(names, set(render.COMPONENTS))


if __name__ == "__main__":
    unittest.main()
