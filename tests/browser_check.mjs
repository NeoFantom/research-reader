// Headless browser check: opens rendered pages over file:// (offline), fails on console errors
// or failed requests, verifies KaTeX/Mermaid/Outline rendered, checks text and figure edges align,
// and writes screenshots.
//
//   npm i --no-save playwright-core          # once; uses an installed Chrome/Chromium
//   CHROME=/usr/bin/google-chrome node tests/browser_check.mjs examples/oscillator-sync/dist docs/screenshots
import { chromium } from 'playwright-core';
import { readdirSync, mkdirSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';

const dist = resolve(process.argv[2] || 'examples/oscillator-sync/dist');
const shots = resolve(process.argv[3] || 'docs/screenshots');
mkdirSync(shots, { recursive: true });
const pages = readdirSync(dist).filter((f) => f.endsWith('.html')).sort();
const viewports = [
  { name: 'desktop-1920', width: 1920, height: 1080 },
  { name: 'mobile-390', width: 390, height: 844, isMobile: true, deviceScaleFactor: 2 },
];

const browser = await chromium.launch({ executablePath: process.env.CHROME || undefined });
let failures = 0;
for (const vp of viewports) {
  for (const theme of ['light', 'dark']) {
    const context = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, isMobile: !!vp.isMobile, deviceScaleFactor: vp.deviceScaleFactor || 1, offline: true });
    await context.addInitScript((t) => { try { localStorage.clear(); localStorage.setItem('rr-theme', t); } catch (_) {} }, theme);
    for (const file of pages) {
      const page = await context.newPage();
      const problems = [];
      page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') problems.push(`console.${m.type()}: ${m.text()}`); });
      page.on('pageerror', (err) => problems.push(`pageerror: ${err.message}`));
      page.on('requestfailed', (r) => problems.push(`requestfailed: ${r.url()}`));
      await page.goto(pathToFileURL(join(dist, file)).href, { waitUntil: 'load' });
      await page.addStyleTag({ content: 'html{scroll-behavior:auto!important}' });
      await page.waitForTimeout(1500);
      const report = await page.evaluate(() => {
        const q = (s) => document.querySelectorAll(s).length;
        const wrap = document.querySelector('.section-band .wrap');
        const inner = wrap && wrap.getBoundingClientRect();
        const pad = wrap ? parseFloat(getComputedStyle(wrap).paddingLeft) : 0;
        const right = inner ? inner.right - pad : 0;
        // every paragraph container and every figure/table must reach the same right edge
        const blocks = [...document.querySelectorAll('.section-band .wrap > .prose, .section-band .wrap > .figure, .section-band .wrap > .table-shell, .section-band .wrap > .title-panel')];
        const misaligned = blocks.filter((b) => Math.abs(b.getBoundingClientRect().right - right) > 1).length;
        const main = document.querySelector('.page-main').getBoundingClientRect();
        return {
          outline: q('.outline-nav a'),
          mathPending: q('[data-latex] > code') + (/\\\(|\\\[/.test(document.querySelector('.page-main').innerText) ? 1 : 0),
          mathErrors: q('.math-error, .katex-error'),
          katex: q('.katex'),
          mermaidSource: [...document.querySelectorAll('pre.mermaid')].filter((n) => !n.querySelector('svg')).length,
          misaligned,
          leftGap: Math.round(inner ? inner.left + pad - main.left : 0),
          rightGap: Math.round(inner ? main.right - right : 0),
          hScroll: document.documentElement.scrollWidth > innerWidth + 1,
        };
      });
      const bad = [...problems];
      if (!report.outline) bad.push('outline empty');
      if (report.mathPending || report.mathErrors) bad.push(`math not rendered: ${JSON.stringify(report)}`);
      if (report.mermaidSource) bad.push('mermaid not rendered');
      if (report.misaligned) bad.push(`${report.misaligned} block(s) not aligned to the content edge`);
      if (report.hScroll) bad.push('horizontal page scroll');
      if (vp.width >= 1200 && Math.abs(report.leftGap - report.rightGap) > 2) bad.push(`content not centered: ${report.leftGap} vs ${report.rightGap}`);
      console.log(`${bad.length ? 'FAIL' : 'ok  '} ${vp.name} ${theme} ${file} katex=${report.katex} outline=${report.outline} gaps=${report.leftGap}/${report.rightGap}`);
      bad.forEach((b) => console.log('     ' + b));
      failures += bad.length ? 1 : 0;
      const stem = `${file.replace('.html', '')}-${vp.name}-${theme}`;
      if (theme === 'light' || file === 'index.html') await page.screenshot({ path: join(shots, `${stem}.png`) });
      if (theme === 'light' && file === 'results.html' && vp.width >= 1200) {
        await page.locator('#dynamics').scrollIntoViewIfNeeded();
        await page.evaluate(() => scrollBy(0, -40));
        await page.waitForTimeout(300);
        await page.screenshot({ path: join(shots, `results-${vp.name}-figures.png`) });
      }
      if (theme === 'light' && file === 'methods.html') {
        await page.evaluate(() => document.getElementById('pipeline').scrollIntoView());
        await page.waitForTimeout(300);
        await page.screenshot({ path: join(shots, `methods-${vp.name}-mermaid.png`) });
        await page.evaluate(() => document.getElementById('model').scrollIntoView());
        await page.waitForTimeout(300);
        await page.screenshot({ path: join(shots, `methods-${vp.name}-math.png`) });
      }
      await page.close();
    }
    await context.close();
  }
}
await browser.close();
console.log(failures ? `\n${failures} page check(s) failed` : '\nall page checks passed');
process.exit(failures ? 1 : 0);
