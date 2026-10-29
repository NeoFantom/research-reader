#!/usr/bin/env python3
"""Render a research-reader JSON spec (one page or a multi-page site) into static HTML.

The spec holds content only. This script owns every element, class name, script and
stylesheet reference, so whoever writes the spec (a person or an agent) never writes HTML.
Python standard library only.

    python3 render.py site.json -o out/          # render every page + copy assets/
    python3 render.py site.json --check          # validate only
    python3 render.py --list-components          # component registry as JSON
    python3 render.py --describe figure          # one component contract
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
PALETTES = {"jade", "cobalt"}
DENSITIES = {"reading", "balanced", "dense"}
UI = {
    "zh": {
        "skip": "跳到正文", "guides": "Guides", "guides_hint": "页间导航", "guides_label": "本站页面",
        "outline": "Outline", "outline_hint": "本页目录", "outline_label": "本页章节",
        "theme": "切换明暗", "zoom": "放大", "close": "关闭", "prev": "上一页", "next": "下一页",
        "sources": "来源与出处", "figure": "Figure", "code": "Code", "math": "Mathematics",
    },
    "en": {
        "skip": "Skip to content", "guides": "Guides", "guides_hint": "between pages", "guides_label": "Pages in this site",
        "outline": "Outline", "outline_hint": "on this page", "outline_label": "On this page",
        "theme": "Toggle theme", "zoom": "Zoom", "close": "Close", "prev": "Previous", "next": "Next",
        "sources": "Sources", "figure": "Figure", "code": "Code", "math": "Mathematics",
    },
}


class SpecError(ValueError):
    pass


# ---------------------------------------------------------------- text helpers

def e(value: Any) -> str:
    return html.escape(str(value), quote=True)


def safe_url(value: Any, field: str) -> str:
    url = str(value).strip()
    if not url or re.match(r"(?i)^\s*(javascript|vbscript|data):", url):
        raise SpecError(f"{field}: unsafe or empty URL")
    return url


def link_attrs(href: str) -> str:
    return ' target="_blank" rel="noopener noreferrer"' if href.startswith(("http://", "https://")) else ""


_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def inline(text: Any) -> str:
    """Escape text, then allow a tiny safe subset: `code`, **bold**, [label](url).
    TeX between \\( \\) or \\[ \\] is left as text for KaTeX to render in the browser."""
    out = []
    for i, part in enumerate(_CODE.split(str(text))):
        if i % 2:
            out.append(f"<code>{e(part)}</code>")
            continue
        chunk = e(part)
        chunk = _BOLD.sub(r"<strong>\1</strong>", chunk)

        def repl(m: re.Match[str]) -> str:
            href = safe_url(html.unescape(m.group(2)), "inline link")
            return f'<a href="{e(href)}"{link_attrs(href)}>{m.group(1)}</a>'

        out.append(_LINK.sub(repl, chunk))
    return "".join(out)


def paragraphs(value: Any) -> str:
    items = value if isinstance(value, list) else [value]
    return "".join(f"<p>{inline(item)}</p>" for item in items if str(item).strip())


def require(data: Any, where: str, *keys: str) -> None:
    if not isinstance(data, dict):
        raise SpecError(f"{where}: expected an object")
    missing = [k for k in keys if k not in data or data[k] in (None, "", [])]
    if missing:
        raise SpecError(f"{where}: missing required field(s): {', '.join(missing)}")


def items_of(data: dict[str, Any], where: str) -> list[Any]:
    require(data, where, "items")
    if not isinstance(data["items"], list):
        raise SpecError(f"{where}.items must be a list")
    return data["items"]


# ---------------------------------------------------------------- components
# Every renderer returns one HTML fragment. Containers whose internal headings must not
# appear in the Outline carry data-outline-skip.

def c_prose(d: dict[str, Any], ctx: dict[str, Any]) -> str:
    require(d, "prose", "body")
    head = f"<h3>{inline(d['title'])}</h3>" if d.get("title") else ""
    tag = "ol" if d.get("ordered") else "ul"
    points = d.get("points") or []
    listing = f"<{tag}>" + "".join(f"<li>{inline(p)}</li>" for p in points) + f"</{tag}>" if points else ""
    after = paragraphs(d["after"]) if d.get("after") else ""
    return f'<div class="prose">{head}{paragraphs(d["body"])}{listing}{after}</div>'


def c_title_panel(d: dict[str, Any], ctx: dict[str, Any]) -> str:
    require(d, "title-panel", "title", "body")
    label = f'<p class="component-label">{e(d["label"])}</p>' if d.get("label") else ""
    meta = f'<p class="component-meta">{inline(d["meta"])}</p>' if d.get("meta") else ""
    return f'<article class="title-panel" data-outline-skip>{label}<p class="panel-title">{inline(d["title"])}</p>{paragraphs(d["body"])}{meta}</article>'


def c_notice(d: dict[str, Any], ctx: dict[str, Any]) -> str:
    require(d, "notice", "body")
    tone = d.get("tone", "info")
    if tone not in {"info", "success", "warning", "danger"}:
        raise SpecError("notice.tone must be info, success, warning or danger")
    label = f'<p class="component-label">{e(d["label"])}</p>' if d.get("label") else ""
    cls = "" if tone == "info" else f" {tone}"
    return f'<aside class="notice{cls}" data-outline-skip>{label}{paragraphs(d["body"])}</aside>'


def c_table(d: dict[str, Any], ctx: dict[str, Any]) -> str:
    require(d, "table", "columns", "rows")
    cols = d["columns"]
    if not isinstance(cols, list) or len(cols) < 2:
        raise SpecError("table.columns must list at least two headers")
    numeric = set(d.get("numeric_columns", []))
    def cell(tag: str, i: int, v: Any) -> str:
        cls = ' class="num"' if i in numeric else ""
        return f"<{tag}{cls}>{inline(v)}</{tag}>"
    head = "".join(cell("th", i, c) for i, c in enumerate(cols))
    body = []
    for n, row in enumerate(d["rows"]):
        cells = row.get("cells") if isinstance(row, dict) else row
        if not isinstance(cells, list) or len(cells) != len(cols):
            raise SpecError(f"table.rows[{n}] must have {len(cols)} cells")
        cls = ' class="recommended"' if isinstance(row, dict) and row.get("recommended") else ""
        body.append(f"<tr{cls}>" + "".join(cell("td", i, v) for i, v in enumerate(cells)) + "</tr>")
    caption = f'<div class="table-caption">{inline(d["caption"])}</div>' if d.get("caption") else ""
    return f'<div class="table-shell"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>{caption}</div>'


def c_evidence(d: dict[str, Any], ctx: dict[str, Any]) -> str:
    counters = {"fact": 0, "inference": 0, "open": 0}
    prefix = {"fact": "F", "inference": "I", "open": "Q"}
    rows = []
    for n, it in enumerate(items_of(d, "evidence-list")):
        require(it, f"evidence-list.items[{n}]", "kind", "title", "body", "source")
        kind = it["kind"]
        if kind not in counters:
            raise SpecError("evidence kind must be fact, inference or open")
        counters[kind] += 1
        mark = e(it.get("mark", f"{prefix[kind]}{counters[kind]}"))
        rows.append(f'<article class="evidence-item" data-kind="{kind}"><span class="evidence-mark">{mark}</span><div><h3>{inline(it["title"])}</h3>{paragraphs(it["body"])}<small>{inline(it["source"])}</small></div></article>')
    return '<div class="evidence-list" data-outline-skip>' + "".join(rows) + "</div>"


def c_sequence(d: dict[str, Any], ctx: dict[str, Any]) -> str:
    steps = []
    for n, it in enumerate(items_of(d, "sequence")):
        require(it, f"sequence.items[{n}]", "title", "body")
        steps.append(f'<article class="sequence-step"><div><h3>{inline(it["title"])}</h3>{paragraphs(it["body"])}</div></article>')
    return '<div class="sequence" data-outline-skip>' + "".join(steps) + "</div>"


def c_delta(d: dict[str, Any], ctx: dict[str, Any]) -> str:
    require(d, "delta-grid", "before", "after")
    parts = []
    for side, default in (("before", "Before"), ("after", "After")):
        blk = d[side]
        require(blk, f"delta-grid.{side}", "title", "body")
        parts.append(f'<article class="delta {side}"><p class="component-label">{e(d.get(side + "_label", default))}</p><h3>{inline(blk["title"])}</h3>{paragraphs(blk["body"])}</article>')
    return '<div class="delta-grid" data-outline-skip>' + "".join(parts) + "</div>"


def c_object_grid(d: dict[str, Any], ctx: dict[str, Any]) -> str:
    cards = []
    for n, it in enumerate(items_of(d, "object-grid")):
        require(it, f"object-grid.items[{n}]", "title", "body")
        label = f'<p class="component-label">{e(it["label"])}</p>' if it.get("label") else ""
        cards.append(f'<article class="object-card">{label}<h3>{inline(it["title"])}</h3>{paragraphs(it["body"])}</article>')
    return '<div class="object-grid" data-outline-skip>' + "".join(cards) + "</div>"


def c_resource_index(d: dict[str, Any], ctx: dict[str, Any]) -> str:
    cards = []
    for n, it in enumerate(items_of(d, "resource-index")):
        require(it, f"resource-index.items[{n}]", "title", "href", "description")
        href = safe_url(it["href"], "resource-index.href")
        eyebrow = f"<code>{e(it['eyebrow'])}</code>" if it.get("eyebrow") else ""
        cards.append(f'<a class="resource-card" href="{e(href)}"{link_attrs(href)}>{eyebrow}<h3>{e(it["title"])}</h3><p>{e(it["description"])}</p></a>')
    return '<div class="resource-index" data-outline-skip>' + "".join(cards) + "</div>"


def _figure_shell(label: str, body: str, caption: str, ctx: dict[str, Any]) -> str:
    zoom = e(ctx["ui"]["zoom"])
    return f'<figure class="figure zoomable"><div class="figure-bar"><span>{e(label)}</span><button type="button" tabindex="-1">{zoom}</button></div><div class="figure-body">{body}</div><figcaption>{inline(caption)}</figcaption></figure>'


def c_figure(d: dict[str, Any], ctx: dict[str, Any]) -> str:
    require(d, "figure", "src", "alt", "caption")
    src = safe_url(d["src"], "figure.src")
    ctx["figure_no"] += 1
    label = d.get("label", f'{ctx["ui"]["figure"]} {ctx["figure_no"]:02d}')
    return _figure_shell(label, f'<img src="{e(src)}" alt="{e(d["alt"])}" loading="lazy">', d["caption"], ctx)


def c_media_grid(d: dict[str, Any], ctx: dict[str, Any]) -> str:
    return '<div class="media-grid">' + "".join(c_figure(it, ctx) for it in items_of(d, "media-grid")) + "</div>"


def c_mermaid(d: dict[str, Any], ctx: dict[str, Any]) -> str:
    require(d, "mermaid", "code", "caption")
    ctx["uses_mermaid"] = True
    ctx["figure_no"] += 1
    label = d.get("label", f'{ctx["ui"]["figure"]} {ctx["figure_no"]:02d} · diagram')
    body = f'<div class="mermaid-host"><pre class="mermaid">{e(d["code"])}</pre></div>'
    return _figure_shell(label, body, d["caption"], ctx)


def c_code(d: dict[str, Any], ctx: dict[str, Any]) -> str:
    require(d, "code-panel", "code")
    return f'<div class="code-panel"><span class="code-label">{e(d.get("label", ctx["ui"]["code"]))}</span><pre><code>{e(d["code"])}</code></pre></div>'


def c_math(d: dict[str, Any], ctx: dict[str, Any]) -> str:
    rows = []
    for n, it in enumerate(items_of(d, "math-panel")):
        require(it, f"math-panel.items[{n}]", "latex")
        title = f"<h3>{inline(it['title'])}</h3>" if it.get("title") else ""
        note = f"<p>{inline(it['note'])}</p>" if it.get("note") else ""
        latex = e(it["latex"])
        rows.append(f'<article class="math-row"><div class="math-copy">{title}{note}</div><div class="math-render" data-latex="{latex}"><code>{latex}</code></div></article>')
    label = e(d.get("label", ctx["ui"]["math"]))
    return f'<div class="math-panel" data-outline-skip><p class="component-label">{label}</p>{"".join(rows)}</div>'


def c_fact_strip(d: dict[str, Any], ctx: dict[str, Any]) -> str:
    facts = items_of(d, "fact-strip")
    if not 2 <= len(facts) <= 6:
        raise SpecError("fact-strip.items must contain two to six facts")
    for n, it in enumerate(facts):
        require(it, f"fact-strip.items[{n}]", "label", "value")
    return fact_strip_html(facts)


def fact_strip_html(facts: list[dict[str, Any]]) -> str:
    return '<div class="fact-strip">' + "".join(f"<span><b>{e(f['label'])}</b>{inline(f['value'])}</span>" for f in facts) + "</div>"


COMPONENTS: dict[str, dict[str, Any]] = {
    "prose": {"render": c_prose, "required": ["body"], "optional": ["title", "points", "ordered", "after"],
              "use_when": "Running text. `title` becomes an h3 and appears in the Outline. `body` is a string or list of paragraphs."},
    "title-panel": {"render": c_title_panel, "required": ["title", "body"], "optional": ["label", "meta"],
                    "use_when": "The one conclusion a reader must not miss: key finding, verdict, decision."},
    "notice": {"render": c_notice, "required": ["body"], "optional": ["label", "tone"],
               "use_when": "A caveat that changes interpretation. tone: info|success|warning|danger."},
    "table": {"render": c_table, "required": ["columns", "rows"], "optional": ["caption", "numeric_columns"],
              "use_when": "Rows sharing the same fields. rows[] is a list of cell lists, or {cells, recommended}."},
    "evidence-list": {"render": c_evidence, "required": ["items"], "optional": [],
                      "use_when": "Claims with provenance. items[]: kind (fact|inference|open), title, body, source; optional mark."},
    "sequence": {"render": c_sequence, "required": ["items"], "optional": [],
                 "use_when": "Ordered steps, timeline, next actions. items[]: title, body."},
    "delta-grid": {"render": c_delta, "required": ["before", "after"], "optional": ["before_label", "after_label"],
                   "use_when": "Before/after of a revision. before/after: {title, body}."},
    "object-grid": {"render": c_object_grid, "required": ["items"], "optional": [],
                    "use_when": "Peer items without a shared comparison schema. items[]: title, body; optional label."},
    "resource-index": {"render": c_resource_index, "required": ["items"], "optional": [],
                       "use_when": "Links to files, datasets, code. items[]: title, href, description; optional eyebrow."},
    "figure": {"render": c_figure, "required": ["src", "alt", "caption"], "optional": ["label"],
               "use_when": "One image or SVG file, zoomable. Say in the caption whether it is data or illustration."},
    "media-grid": {"render": c_media_grid, "required": ["items"], "optional": [],
                   "use_when": "Two or more figures side by side. items[] use figure fields."},
    "mermaid": {"render": c_mermaid, "required": ["code", "caption"], "optional": ["label"],
                "use_when": "Flowchart, sequence or state diagram written in Mermaid syntax (rendered by vendored Mermaid)."},
    "code-panel": {"render": c_code, "required": ["code"], "optional": ["label"],
                   "use_when": "Exact code, command or configuration."},
    "math-panel": {"render": c_math, "required": ["items"], "optional": ["label"],
                   "use_when": "Display equations with explanations. items[]: latex; optional title, note. Inline math elsewhere: \\( ... \\)."},
    "fact-strip": {"render": c_fact_strip, "required": ["items"], "optional": [],
                   "use_when": "Two to six short factual fields: date, version, status, data size."},
}
ALIASES = {"compare-matrix": "table", "decision-panel": "title-panel", "callout": "notice", "diagram": "mermaid"}


def render_component(d: dict[str, Any], ctx: dict[str, Any]) -> str:
    require(d, "component", "type")
    name = ALIASES.get(d["type"], d["type"])
    if name not in COMPONENTS:
        raise SpecError(f"unknown component type: {d['type']} (see --list-components)")
    fn: Callable[[dict[str, Any], dict[str, Any]], str] = COMPONENTS[name]["render"]
    return fn(d, ctx)


# ---------------------------------------------------------------- pages

def normalize(spec: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Accept either {site, pages:[...]} or a single page object."""
    if not isinstance(spec, dict):
        raise SpecError("spec must be a JSON object")
    if spec.get("schema_version", 1) != 1:
        raise SpecError("schema_version must be 1")
    if "pages" in spec:
        site = spec.get("site", {})
        pages = spec["pages"]
        if not isinstance(pages, list) or not pages:
            raise SpecError("pages must be a non-empty list")
    else:
        site = {k: spec[k] for k in ("lang", "palette", "density", "wordmark", "wordmark_accent", "footer", "static") if k in spec}
        pages = [{"slug": spec.get("slug", "index"), **spec}]
    if site.get("palette", "jade") not in PALETTES:
        raise SpecError(f"site.palette must be one of {sorted(PALETTES)}")
    if site.get("density", "reading") not in DENSITIES:
        raise SpecError(f"site.density must be one of {sorted(DENSITIES)}")
    slugs: set[str] = set()
    for n, p in enumerate(pages):
        require(p, f"pages[{n}]", "slug", "title", "sections")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", p["slug"]):
            raise SpecError(f"pages[{n}].slug must match [a-z0-9][a-z0-9-]*")
        if p["slug"] in slugs:
            raise SpecError(f"duplicate page slug: {p['slug']}")
        slugs.add(p["slug"])
        ids: set[str] = set()
        for m, s in enumerate(p["sections"]):
            require(s, f"pages[{n}].sections[{m}]", "id", "title", "components")
            if not re.fullmatch(r"[a-z][a-z0-9-]*", s["id"]) or s["id"] in ids:
                raise SpecError(f"pages[{n}].sections[{m}].id invalid or duplicate: {s['id']}")
            ids.add(s["id"])
    return site, pages


def render_page(site: dict[str, Any], pages: list[dict[str, Any]], index: int) -> str:
    page = pages[index]
    lang = site.get("lang", "zh-CN")
    ui = UI["zh" if lang.lower().startswith("zh") else "en"]
    ctx: dict[str, Any] = {"ui": ui, "figure_no": 0, "uses_mermaid": False}
    palette = site.get("palette", "jade")
    density = site.get("density", "reading")
    many = len(pages) > 1

    guides = []
    for n, p in enumerate(pages):
        current = ' aria-current="page"' if n == index else ""
        note = f"<small>{e(p['nav_note'])}</small>" if p.get("nav_note") else ""
        guides.append(f'<a href="{e(p["slug"])}.html"{current}><span>{n + 1:02d}</span><span><strong>{e(p.get("nav_title", p["title"]))}</strong>{note}</span></a>')
    for n, g in enumerate(site.get("extra_guides", [])):
        require(g, f"site.extra_guides[{n}]", "title", "href")
        href = safe_url(g["href"], "extra_guides.href")
        guides.append(f'<a href="{e(href)}"{link_attrs(href)}><span>↗</span><span><strong>{e(g["title"])}</strong></span></a>')

    sections = page["sections"]
    wordmark = ""
    if site.get("wordmark"):
        accent = f" <span>{e(site['wordmark_accent'])}</span>" if site.get("wordmark_accent") else ""
        wordmark = f'<div class="wordmark">{e(site["wordmark"])}{accent}</div>'
    eyebrow = f'<p class="eyebrow">{e(page["eyebrow"])}</p>' if page.get("eyebrow") else ""
    lead = f'<p class="lead">{inline(page["lead"])}</p>' if page.get("lead") else ""
    facts = page.get("facts") or []
    for n, f in enumerate(facts):
        require(f, f"facts[{n}]", "label", "value")
    hero_index = ""
    if len(sections) >= 4:
        hero_index = '<nav class="hero-index" aria-label="Sections">' + "".join(
            f'<a href="#{e(s["id"])}"><span>{n:02d}</span><strong>{e(s["title"])}</strong></a>' for n, s in enumerate(sections, 1)
        ) + "</nav>"
    hero = f'<header class="hero" id="top"><div class="wrap">{wordmark}{eyebrow}<h1>{inline(page["title"])}</h1>{lead}{fact_strip_html(facts) if facts else ""}{hero_index}</div></header>'

    body = []
    for n, s in enumerate(sections, 1):
        alt = " alt" if s.get("alternate", n % 2 == 0) else ""
        label = f'<p class="eyebrow">{e(s["label"])}</p>' if s.get("label") else ""
        outline_attr = f' data-outline-label="{e(s["outline_label"])}"' if s.get("outline_label") else ""
        comps = "".join(render_component(c, ctx) for c in s["components"])
        body.append(
            f'<section class="section-band{alt}"><div class="wrap"><div class="section-heading"><span class="section-number">{n:02d}</span>'
            f'<div>{label}<h2 id="{e(s["id"])}"{outline_attr}>{inline(s["title"])}</h2></div></div>{comps}</div></section>'
        )
    sources = page.get("sources") or []
    if sources:
        items = []
        for n, src in enumerate(sources):
            require(src, f"sources[{n}]", "title", "detail")
            if src.get("href"):
                href = safe_url(src["href"], "sources.href")
                ext = " ↗" if link_attrs(href) else ""
                head = f'<a href="{e(href)}"{link_attrs(href)}>{e(src["title"])}{ext}</a>'
            else:
                head = f"<strong>{e(src['title'])}</strong>"
            items.append(f'<article class="source-item">{head}<small>{inline(src["detail"])}</small></article>')
        alt = " alt" if (len(sections) + 1) % 2 == 0 else ""
        body.append(f'<section class="section-band{alt}"><div class="wrap"><p class="eyebrow">Sources</p><h2 id="sources">{e(page.get("sources_title", ui["sources"]))}</h2><div class="source-ledger">{"".join(items)}</div></div></section>')

    pager = ""
    if many:
        links = []
        if index > 0:
            p = pages[index - 1]
            links.append(f'<a class="prev" href="{e(p["slug"])}.html"><small>← {ui["prev"]}</small><strong>{e(p.get("nav_title", p["title"]))}</strong></a>')
        if index < len(pages) - 1:
            p = pages[index + 1]
            links.append(f'<a class="next" href="{e(p["slug"])}.html"><small>{ui["next"]} →</small><strong>{e(p.get("nav_title", p["title"]))}</strong></a>')
        pager = f'<nav class="page-pager" aria-label="Pages">{"".join(links)}</nav>'
    footer = inline(site.get("footer", "Rendered with research-reader"))

    title = re.sub(r"\\[()\[\]]", "", str(page["title"]))
    site_title = site.get("title")
    doc_title = f"{title} · {site_title}" if site_title and site_title != title else title
    mermaid_tag = '<script defer src="assets/vendor/mermaid/mermaid.min.js"></script>' if ctx["uses_mermaid"] else ""
    guides_open = "open" if site.get("guides_open", many) else "closed"

    return f"""<!doctype html>
<html lang="{e(lang)}" data-palette="{e(palette)}" data-density="{e(density)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{e(page.get('description', page.get('lead', '')))}">
<title>{e(doc_title)}</title>
<script>try{{var t=localStorage.getItem('rr-theme')||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');document.documentElement.setAttribute('data-theme',t)}}catch(_){{}}</script>
<link rel="stylesheet" href="assets/vendor/katex/katex.min.css">
<link rel="stylesheet" href="assets/reader.css">
<script defer src="assets/vendor/katex/katex.min.js"></script>
<script defer src="assets/vendor/katex/contrib/auto-render.min.js"></script>
{mermaid_tag}
<script defer src="assets/reader.js"></script>
</head>
<body>
<a class="skip-link" href="#content">{ui['skip']}</a>
<div class="page-shell" id="pageShell" data-guides="{guides_open}" data-outline="open">
<aside class="rail guides-rail" aria-label="Guides">
<button class="rail-toggle" type="button" onclick="toggleGuides()" aria-expanded="{str(guides_open == 'open').lower()}"><span>{ui['guides']}</span><b>{ui['guides_hint']}</b></button>
<div class="rail-body guides-body"><span class="rail-label">{ui['guides_label']}</span><nav class="guides-nav">{''.join(guides)}</nav></div>
</aside>
<div class="page-main">
{hero}
<main id="content">{''.join(body)}<div class="wrap">{pager}</div></main>
<footer class="footer"><div class="wrap">{footer}</div></footer>
</div>
<aside class="rail outline-rail" aria-label="Outline">
<button class="rail-toggle" type="button" onclick="toggleOutline()" aria-expanded="true"><span>{ui['outline']}</span><b>{ui['outline_hint']}</b></button>
<div class="rail-body outline-body"><span class="rail-label">{ui['outline_label']}</span><nav class="outline-nav"></nav>
<div class="rail-tools"><button class="icon-button" id="themeBtn" type="button" onclick="toggleTheme()" aria-label="{ui['theme']}">◐</button></div></div>
</aside>
</div>
<div id="modal" role="dialog" aria-modal="true" onclick="closeModal()"><button class="modal-close" type="button" aria-label="{ui['close']}" onclick="closeModal()">×</button><div id="modalInner" onclick="event.stopPropagation()"></div></div>
</body>
</html>
"""


def render_site(spec: dict[str, Any], spec_dir: Path, out: Path | None) -> list[Path]:
    site, pages = normalize(spec)
    rendered = [(p["slug"], render_page(site, pages, i)) for i, p in enumerate(pages)]
    if out is None:
        return []
    out.mkdir(parents=True, exist_ok=True)
    if (out / "assets").resolve() != ASSETS.resolve():
        shutil.copytree(ASSETS, out / "assets", dirs_exist_ok=True)
    for rel in site.get("static", []):
        src = (spec_dir / rel).resolve()
        if not src.exists():
            raise SpecError(f"site.static entry not found: {rel}")
        dst = out / Path(rel).name
        if src != dst.resolve():
            (shutil.copytree(src, dst, dirs_exist_ok=True) if src.is_dir() else shutil.copy2(src, dst))
    written = []
    for slug, page_html in rendered:
        path = out / f"{slug}.html"
        path.write_text(page_html, encoding="utf-8")
        written.append(path)
    return written


def registry(name: str | None = None) -> Any:
    def public(n: str) -> dict[str, Any]:
        return {"name": n, **{k: v for k, v in COMPONENTS[n].items() if k != "render"}}
    return public(name) if name else [public(n) for n in COMPONENTS]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", nargs="?", type=Path)
    ap.add_argument("-o", "--output", type=Path, help="output directory")
    ap.add_argument("--check", action="store_true", help="validate without writing")
    ap.add_argument("--list-components", action="store_true")
    ap.add_argument("--describe", metavar="COMPONENT")
    ap.add_argument("--palette", choices=sorted(PALETTES), help="override site.palette")
    a = ap.parse_args()
    if a.list_components:
        print(json.dumps(registry(), ensure_ascii=False, indent=2))
        return 0
    if a.describe:
        name = ALIASES.get(a.describe, a.describe)
        if name not in COMPONENTS:
            print(f"ERROR: unknown component: {a.describe}", file=sys.stderr)
            return 2
        print(json.dumps(registry(name), ensure_ascii=False, indent=2))
        return 0
    if not a.spec:
        ap.error("spec is required")
    if not a.check and not a.output:
        ap.error("--output is required unless --check is given")
    try:
        spec = json.loads(a.spec.read_text(encoding="utf-8"))
        if a.palette:
            target = spec.setdefault("site", {}) if "pages" in spec else spec
            target["palette"] = a.palette
        written = render_site(spec, a.spec.resolve().parent, None if a.check else a.output)
    except (OSError, json.JSONDecodeError, SpecError) as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1
    if a.check:
        print(f"OK: {a.spec}")
    for path in written:
        print(f"OK: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
