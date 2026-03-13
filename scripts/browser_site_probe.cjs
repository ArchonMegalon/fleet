'use strict';

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const targetUrl = String(process.env.PROBE_TARGET_URL || '').trim();
const probeName = String(process.env.PROBE_NAME || 'site').trim() || 'site';
const stateRoot = String(process.env.PROBE_STATE_ROOT || '/docker/fleet/state/browser_probe').trim() || '/docker/fleet/state/browser_probe';

if (!targetUrl) {
  throw new Error('PROBE_TARGET_URL is required');
}

const stateDir = path.join(stateRoot, probeName.replace(/[^a-z0-9._-]+/gi, '-'));
fs.mkdirSync(stateDir, { recursive: true });

async function main() {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1024 } });
    await page.goto(targetUrl, { waitUntil: 'domcontentloaded', timeout: 120000 });
    await page.waitForTimeout(5000);
    const screenshotPath = path.join(stateDir, 'page.png');
    const htmlPath = path.join(stateDir, 'page.html');
    const jsonPath = path.join(stateDir, 'summary.json');
    await page.screenshot({ path: screenshotPath, fullPage: true });
    fs.writeFileSync(htmlPath, await page.content(), 'utf8');
    const summary = await page.evaluate(() => {
      function clean(value) {
        return String(value || '').replace(/\s+/g, ' ').trim();
      }
      function firstN(items, n = 20) {
        return items.slice(0, n);
      }
      const textareas = Array.from(document.querySelectorAll('textarea')).map((el) => ({
        placeholder: clean(el.getAttribute('placeholder')),
        name: clean(el.getAttribute('name')),
        id: clean(el.getAttribute('id')),
      }));
      const inputs = Array.from(document.querySelectorAll('input')).map((el) => ({
        type: clean(el.getAttribute('type')),
        placeholder: clean(el.getAttribute('placeholder')),
        name: clean(el.getAttribute('name')),
        id: clean(el.getAttribute('id')),
      }));
      const buttons = Array.from(document.querySelectorAll('button, [role="button"], a'))
        .map((el) => ({
          tag: el.tagName.toLowerCase(),
          text: clean(el.textContent),
          href: clean(el.getAttribute('href')),
          id: clean(el.getAttribute('id')),
          className: clean(el.getAttribute('class')),
        }))
        .filter((entry) => entry.text || entry.href);
      const contenteditables = Array.from(document.querySelectorAll('[contenteditable="true"], [data-lexical-editor="true"]')).map((el) => ({
        role: clean(el.getAttribute('role')),
        placeholder: clean(el.getAttribute('placeholder')),
        className: clean(el.getAttribute('class')),
        text: clean(el.textContent),
      }));
      const headings = Array.from(document.querySelectorAll('h1, h2, h3')).map((el) => clean(el.textContent)).filter(Boolean);
      return {
        url: location.href,
        title: document.title,
        headings: firstN(headings),
        textareas: firstN(textareas),
        inputs: firstN(inputs, 30),
        buttons: firstN(buttons, 40),
        contenteditables: firstN(contenteditables),
      };
    });
    fs.writeFileSync(jsonPath, `${JSON.stringify(summary, null, 2)}\n`, 'utf8');
    process.stdout.write(`${JSON.stringify({ status: 'ok', state_dir: stateDir, summary }, null, 2)}\n`);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message}\n`);
  process.exit(1);
});
