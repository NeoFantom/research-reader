/* research-reader runtime: theme, rails, auto Outline, scroll-spy, figure zoom, KaTeX, Mermaid.
   No dependencies besides the optional vendored KaTeX / Mermaid scripts loaded before this file. */
(() => {
  'use strict';
  const root = document.documentElement;
  const store = {
    get(key) { try { return localStorage.getItem('rr-' + key); } catch (_) { return null; } },
    set(key, value) { try { localStorage.setItem('rr-' + key, value); } catch (_) { /* private mode */ } },
  };
  const shell = document.getElementById('pageShell');

  /* ---------- theme ---------- */
  function applyTheme(theme) {
    root.setAttribute('data-theme', theme);
    store.set('theme', theme);
    const button = document.getElementById('themeBtn');
    if (button) button.textContent = theme === 'dark' ? '☀' : '◐';
  }
  const prefersDark = window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches;
  applyTheme(store.get('theme') || (prefersDark ? 'dark' : 'light'));
  window.toggleTheme = () => {
    applyTheme(root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
    renderMermaid();
  };

  /* ---------- rails ---------- */
  function applyRails(guides, outline) {
    if (!shell) return;
    shell.dataset.guides = guides;
    shell.dataset.outline = outline;
    store.set('guides', guides);
    store.set('outline', outline);
    document.querySelector('.guides-rail .rail-toggle')?.setAttribute('aria-expanded', String(guides === 'open'));
    document.querySelector('.outline-rail .rail-toggle')?.setAttribute('aria-expanded', String(outline === 'open'));
  }
  window.toggleGuides = () => shell && applyRails(shell.dataset.guides === 'open' ? 'closed' : 'open', shell.dataset.outline);
  window.toggleOutline = () => shell && applyRails(shell.dataset.guides, shell.dataset.outline === 'open' ? 'closed' : 'open');
  const narrow = matchMedia('(max-width:840px)').matches;
  // Narrow screens always start with both rails collapsed; wide screens remember the reader's choice.
  applyRails(narrow ? 'closed' : (store.get('guides') || (shell?.dataset.guides ?? 'closed')),
             narrow ? 'closed' : (store.get('outline') || (shell?.dataset.outline ?? 'open')));
  if (narrow) {
    // Close a drawer after the reader follows one of its links.
    document.querySelectorAll('.rail-body a').forEach((a) => a.addEventListener('click', () => applyRails('closed', 'closed')));
  }

  /* ---------- Outline: generated from h2/h3 inside <main> ---------- */
  function slugify(text, used) {
    let base = text.trim().toLowerCase().replace(/[\s·:：,，.。/()（）]+/g, '-').replace(/[^\p{L}\p{N}-]/gu, '').replace(/^-+|-+$/g, '') || 'section';
    let slug = base, n = 2;
    while (used.has(slug) || document.getElementById(slug)) slug = `${base}-${n++}`;
    used.add(slug);
    return slug;
  }
  const outlineNav = document.querySelector('.outline-nav');
  const headings = [...document.querySelectorAll('main h2, main h3')].filter((h) => !h.closest('[data-outline-skip]'));
  if (outlineNav && !outlineNav.children.length) {
    const used = new Set();
    let h2Count = 0, h3Count = 0;
    headings.forEach((h) => {
      if (!h.id) h.id = slugify(h.textContent, used);
      const depth = h.tagName === 'H2' ? 2 : 3;
      if (depth === 2) { h2Count += 1; h3Count = 0; } else { h3Count += 1; }
      const a = document.createElement('a');
      a.href = '#' + h.id;
      a.dataset.target = h.id;
      a.className = 'depth-' + depth;
      const num = document.createElement('span');
      num.textContent = depth === 2 ? String(h2Count).padStart(2, '0') : `${h2Count}.${h3Count}`;
      a.append(num, document.createTextNode(h.dataset.outlineLabel || h.textContent.trim()));
      outlineNav.append(a);
    });
  }

  /* ---------- scroll-spy ---------- */
  const links = [...document.querySelectorAll('.outline-nav a[data-target]')];
  if (links.length) {
    const targets = links.map((a) => document.getElementById(a.dataset.target)).filter(Boolean);
    const update = () => {
      let active = targets[0]?.id;
      for (const t of targets) if (t.getBoundingClientRect().top <= innerHeight * 0.3) active = t.id;
      links.forEach((a) => {
        const on = a.dataset.target === active;
        a.classList.toggle('active', on);
        if (on) a.setAttribute('aria-current', 'location'); else a.removeAttribute('aria-current');
      });
    };
    addEventListener('scroll', update, { passive: true });
    addEventListener('resize', update);
    update();
  }

  /* ---------- figure zoom ---------- */
  const modal = document.getElementById('modal');
  const inner = document.getElementById('modalInner');
  window.closeModal = () => { modal?.classList.remove('on'); document.body.style.overflow = ''; };
  document.querySelectorAll('.figure.zoomable').forEach((fig) => {
    fig.addEventListener('click', () => {
      const media = fig.querySelector('.figure-body img, .figure-body svg');
      if (!media || !modal || !inner) return;
      const copy = media.cloneNode(true);
      copy.removeAttribute('width'); copy.removeAttribute('height');
      copy.classList.add('zoomed-media');
      inner.replaceChildren(copy);
      modal.classList.add('on');
      document.body.style.overflow = 'hidden';
    });
  });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') window.closeModal(); });

  /* ---------- math (KaTeX, vendored) ---------- */
  if (window.katex) {
    document.querySelectorAll('[data-latex]').forEach((node) => {
      try {
        katex.render(node.dataset.latex, node, { displayMode: node.dataset.display !== 'inline', throwOnError: true });
      } catch (err) {
        node.classList.add('math-error');
        node.title = String(err);
      }
    });
    if (window.renderMathInElement) {
      const scope = document.querySelector('.page-main') || document.body;
      renderMathInElement(scope, {
        delimiters: [
          { left: '\\[', right: '\\]', display: true },
          { left: '\\(', right: '\\)', display: false },
          { left: '$$', right: '$$', display: true },
        ],
        ignoredTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code'],
        ignoredClasses: ['no-math', 'mermaid'],
        throwOnError: false,
      });
    }
  }

  /* ---------- diagrams (Mermaid, vendored) ---------- */
  const diagrams = [...document.querySelectorAll('pre.mermaid')];
  diagrams.forEach((node) => { node.dataset.source = node.textContent; });
  function renderMermaid() {
    if (!window.mermaid || !diagrams.length) return;
    const css = getComputedStyle(root);
    const v = (name) => css.getPropertyValue(name).trim();
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: 'strict',
      theme: 'base',
      fontFamily: v('--font-body'),
      themeVariables: {
        background: v('--bg'),
        primaryColor: v('--surface'),
        primaryTextColor: v('--fg'),
        primaryBorderColor: v('--accent'),
        secondaryColor: v('--accent-soft'),
        tertiaryColor: v('--surface-2'),
        lineColor: v('--fg-2'),
        textColor: v('--fg'),
        clusterBkg: v('--surface'),
        clusterBorder: v('--border'),
        edgeLabelBackground: v('--bg'),
        fontSize: '15px',
      },
      flowchart: { htmlLabels: true, curve: 'basis' },
    });
    diagrams.forEach((node) => { node.removeAttribute('data-processed'); node.textContent = node.dataset.source; });
    mermaid.run({ nodes: diagrams }).catch((err) => console.warn('mermaid:', err));
  }
  renderMermaid();
})();
