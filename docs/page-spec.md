# Page spec reference

`render.py` turns one JSON file into static HTML. The JSON holds content only; the renderer owns every
element, class and script. The executable registry is the source of truth:

```bash
python3 render.py --list-components      # all components, required/optional fields, when to use
python3 render.py --describe table       # one component
```

## Shape

Multi-page site:

```json
{
  "schema_version": 1,
  "site": {
    "title": "Series title (used in <title>)",
    "lang": "zh-CN",
    "palette": "jade",
    "density": "reading",
    "wordmark": "Short name", "wordmark_accent": "Document type",
    "static": ["figures"],
    "extra_guides": [{"title": "Repository", "href": "https://example.org"}],
    "footer": "Who wrote it, how it was produced"
  },
  "pages": [
    {
      "slug": "index",
      "nav_title": "Overview", "nav_note": "One line under the Guides entry",
      "eyebrow": "Date · status",
      "title": "Headline that states the conclusion",
      "lead": "One sentence: reader, scope, outcome.",
      "facts": [{"label": "N", "value": "200"}],
      "sections": [
        {"id": "finding", "label": "Finding", "title": "Section title", "components": [ ... ]}
      ],
      "sources": [{"title": "Paper or file", "href": "https://…", "detail": "what it supports"}]
    }
  ]
}
```

A single page may also be given directly as one page object (no `site` / `pages`).

| Field | Meaning |
| --- | --- |
| `site.palette` | `jade` (default) or `cobalt`. Override with `--palette`. |
| `site.density` | `reading` (default, 1040 px content), `balanced` (1240 px), `dense` (1400 px, tighter spacing). The whole content container changes width; text never gets its own narrower width. |
| `site.static` | Files or folders, relative to the spec, copied next to the pages (figures, data). |
| `site.guides_open` | Guides rail open on first desktop load. Default: open when there is more than one page. |
| `pages[].slug` | Output file name `<slug>.html`; `[a-z0-9-]`. |
| `sections[].id` | Anchor id `[a-z][a-z0-9-]*`, unique per page. |
| `sections[].outline_label` | Shorter text for the Outline entry. |

## Navigation

- **Guides** (left rail) = the `pages` list, in order, with the current page marked. Plus optional `extra_guides`.
- **Outline** (right rail) = built in the browser from every `h2` / `h3` inside `<main>`: section titles are h2,
  `prose.title` is h3. Headings inside components (cards, steps, evidence) are skipped.
- A hero index appears when a page has four or more sections. Previous / next page links appear at the bottom.

## Text fields

All text is HTML-escaped. A small inline subset is converted:

| Write | Get |
| --- | --- |
| `` `code` `` | inline code |
| `**bold**` | bold |
| `[label](https://…)` | link (external links open in a new tab; `javascript:` / `data:` rejected) |
| `\\( x^2 \\)` in JSON (i.e. `\( x^2 \)`) | inline math (KaTeX) |
| `\\[ … \\]` | display math inside text |

Remember to double backslashes in JSON: `"\\frac{1}{2}"`.

## Components

| Type | Required | Optional | Use for |
| --- | --- | --- | --- |
| `prose` | `body` | `title`, `points`, `ordered`, `after` | running text; `title` becomes an Outline h3 |
| `title-panel` | `title`, `body` | `label`, `meta` | the one conclusion a reader must not miss |
| `notice` | `body` | `label`, `tone` | a caveat that changes interpretation (`info/success/warning/danger`) |
| `table` | `columns`, `rows` | `caption`, `numeric_columns` | rows that share fields; a row is a list or `{cells, recommended}` |
| `evidence-list` | `items[]{kind,title,body,source}` | `mark` | facts vs inferences vs open questions |
| `sequence` | `items[]{title,body}` | | ordered steps, timeline, next actions |
| `delta-grid` | `before`, `after` | `before_label`, `after_label` | what changed in a revision |
| `object-grid` | `items[]{title,body}` | `label` | peer items without a common schema |
| `resource-index` | `items[]{title,href,description}` | `eyebrow` | links to files, data, code |
| `figure` | `src`, `alt`, `caption` | `label` | one image / SVG, click to zoom |
| `media-grid` | `items[]` (figure fields) | | figures side by side |
| `mermaid` | `code`, `caption` | `label` | flowchart / sequence / state diagram |
| `code-panel` | `code` | `label` | exact code or commands |
| `math-panel` | `items[]{latex}` | `title`, `note`, `label` | display equations with explanations |
| `fact-strip` | `items[]{label,value}` (2–6) | | compact metadata |

Aliases accepted for compatibility: `compare-matrix` → `table`, `decision-panel` → `title-panel`,
`callout` → `notice`, `diagram` → `mermaid`.

## Errors

Unknown components, missing required fields, duplicate ids, wrong table row widths and unsafe URLs stop
the render with a message naming the field. Fix the spec; do not edit the generated HTML.
