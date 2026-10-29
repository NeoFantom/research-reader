---
name: research-reader
description: Render long, reading-oriented research material (progress reports, revision notes, analyses for a collaborator or advisor to review) as a static multi-page HTML site with page navigation on the left, an auto-generated outline on the right, math, tables, figures and Mermaid diagrams. The agent writes a JSON content spec; render.py writes all HTML/CSS/JS. Not for live presentations or slides.
---

# research-reader

You produce **content as JSON**. `render.py` produces the HTML. Never hand-write or post-edit the page
HTML, CSS, JavaScript or class names. This keeps output identical across models and sessions.

This file works as a skill for any agent that can read files and run `python3`. Paths below are relative
to the folder containing this file; call it `$RR`.

## Use it when

- The reader will **read and review** at their own pace: research progress, method write-ups, result
  analyses, "what changed in this revision", an audit of AI-produced work.
- The material has structure worth navigating: several sections, or several pages.

## Do not use it when

- It will be **projected and talked over** (talks, live demos, workshops). The layout is built for
  dense reading: small navigation rails, long sections, many equations. On a projector that becomes
  small text and too many words. Use a slide tool or a big-type, figure-first page instead.
- The answer is a few paragraphs. Reply in plain text.

## Workflow

1. Decide the pages. One page per question the reader asks (overview / methods / results is typical).
   Single page is fine for short material.
2. Look up components instead of guessing:
   ```bash
   python3 $RR/render.py --list-components
   python3 $RR/render.py --describe math-panel
   ```
   Full field reference: `$RR/docs/page-spec.md`. Working example: `$RR/examples/oscillator-sync/site.json`.
3. Write `site.json` next to the material (figures in a folder listed in `site.static`).
4. Validate, then render:
   ```bash
   python3 $RR/render.py site.json --check
   python3 $RR/render.py site.json -o out/
   ```
   `out/` gets one `<slug>.html` per page plus `assets/` (CSS, JS, vendored KaTeX, Mermaid, fonts).
   The folder opens offline by double-clicking any page; it can also be served by any static file server.
5. Look at the result in a browser at desktop and phone width (or run `tests/browser_check.mjs`, see README).
6. Tell the user the spec path and the output folder.

If the registry lacks a representation you need, say so and stop; adding a component is a change to
`render.py` and `assets/reader.css`, not something to improvise inside one page.

## Content rules

- `title` states the **conclusion**, not the topic. `lead` is one sentence: reader, scope, outcome.
- Put the single most important finding in a `title-panel` near the top of the first page.
- Keep numbers exact, with units and where they came from. Never invent values to fill a layout.
- In `evidence-list`, mark `fact` only for something with a source, measurement or test output;
  reasoning without direct evidence is `inference`; unanswered items are `open`.
- Say in every figure caption whether it shows **data** or is an **illustration**.
- Choose tables for exact comparison, `sequence` for order, `delta-grid` for before/after,
  cards (`object-grid`) only for repeated peer items. Long prose stays in `prose`, not in cards.
- Section titles must be specific to the content; never keep generic names like "Overview" or "Results"
  when a sentence fits.
- Math: inline `\\( … \\)` inside any text field, display equations in `math-panel` (`latex` without
  delimiters). Backslashes are doubled in JSON.
- Remove private data (credentials, personal emails, internal hostnames) before rendering.

## Layout rules (owned by the renderer; do not override)

- Left **Guides** = between pages. Right **Outline** = within the page, built from h2/h3. Never mix them.
- Body text, lists, tables, figures and code share one centered content width. To get shorter lines,
  choose `density: reading`; never narrow text alone.
- Light and dark themes, two palettes (`jade`, `cobalt`), print styles and phone layout are built in.
