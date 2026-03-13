'use strict';

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const stateDir = String(process.env.BROWSERACT_STATE_DIR || '/docker/fleet/state/browseract_bootstrap/log_probe').trim();
const username = String(process.env.BROWSERACT_USERNAME || '').trim();
const password = String(process.env.BROWSERACT_PASSWORD || '').trim();
const taskId = String(process.env.BROWSERACT_TASK_ID || '').trim();

if (!username || !password) {
  throw new Error('BROWSERACT_USERNAME and BROWSERACT_PASSWORD are required');
}
if (!taskId) {
  throw new Error('BROWSERACT_TASK_ID is required');
}

fs.mkdirSync(stateDir, { recursive: true });

async function snap(page, name) {
  await page.screenshot({ path: path.join(stateDir, `${name}.png`), fullPage: true });
  fs.writeFileSync(path.join(stateDir, `${name}.html`), await page.content(), 'utf8');
}

async function bodyText(page) {
  try {
    return await page.locator('body').innerText({ timeout: 3000 });
  } catch {
    return '';
  }
}

async function safeWait(page, timeoutMs) {
  try {
    if (!page || page.isClosed()) {
      return;
    }
    await page.waitForTimeout(timeoutMs);
  } catch {
    // ignore page invalidation
  }
}

async function firstVisibleLocator(page, selectors) {
  for (const selector of selectors) {
    const locator = page.locator(selector);
    let count = 0;
    try {
      count = await locator.count();
    } catch {
      count = 0;
    }
    for (let index = 0; index < count; index += 1) {
      const candidate = locator.nth(index);
      try {
        await candidate.waitFor({ state: 'visible', timeout: 1000 });
        return candidate;
      } catch {
        // continue
      }
    }
  }
  return null;
}

async function fillFirst(page, selectors, value, label) {
  const locator = await firstVisibleLocator(page, selectors);
  if (!locator) {
    throw new Error(`Could not find input target: ${label}`);
  }
  await locator.fill(value, { timeout: 10000 });
}

async function clickFirst(page, selectors, label) {
  const locator = await firstVisibleLocator(page, selectors);
  if (!locator) {
    throw new Error(`Could not find clickable target: ${label}`);
  }
  await locator.click({ timeout: 10000, force: true });
}

async function maybeSwitchSignupToLogin(page) {
  const text = await bodyText(page);
  if (!/sign up/i.test(text)) {
    return false;
  }
  try {
    const loginLink = page.locator('form#formRegister button.btn-link').filter({ hasText: /log in/i }).first();
    await loginLink.waitFor({ state: 'visible', timeout: 3000 });
    await loginLink.click({ timeout: 10000 });
  } catch {
    try {
      await page.evaluate(() => {
        const button = Array.from(document.querySelectorAll('button.btn-link')).find((candidate) =>
          /log in/i.test(candidate.textContent || '')
        );
        if (button) {
          button.click();
        }
      });
    } catch {
      return false;
    }
  }
  await safeWait(page, 1500);
  await page.locator('#formLogin_email').waitFor({ state: 'visible', timeout: 5000 }).catch(() => {});
  return true;
}

async function ensureLogin(page) {
  await page.goto('https://app.browseract.com/reception/workflow-list', {
    waitUntil: 'domcontentloaded',
    timeout: 120000,
  });
  await safeWait(page, 2000);
  let loginNeeded = await page.locator('input[type="password"], input[name="password"]').count();
  if (loginNeeded === 0) {
    const loginButton = await firstVisibleLocator(page, [
      'a[href*="/login"]',
      'button:has-text("Login")',
      'button:has-text("Log in")',
      'button:has-text("Sign in")',
      'a:has-text("Login")',
      'a:has-text("Log in")',
      'a:has-text("Sign in")',
    ]);
    if (loginButton) {
      await loginButton.click({ timeout: 10000 });
      await page.waitForLoadState('domcontentloaded', { timeout: 120000 }).catch(() => {});
      await safeWait(page, 2000);
    }
    loginNeeded = await page.locator('input[type="password"], input[name="password"]').count();
  }
  if (loginNeeded > 0 || /login|sign in|sign up/i.test(await page.title()) || /sign up/i.test(await bodyText(page))) {
    await maybeSwitchSignupToLogin(page);
    await fillFirst(
      page,
      [
        '#formLogin_email',
        'input[type="email"]',
        'input[name="email"]',
        'input[autocomplete="username"]',
        'input[autocomplete="email"]',
      ],
      username,
      'email'
    );
    await fillFirst(
      page,
      [
        '#formLogin_password',
        'input[type="password"]',
        'input[name="password"]',
        'input[autocomplete="current-password"]',
      ],
      password,
      'password'
    );
    await clickFirst(
      page,
      [
        'form#formLogin button[type="submit"]',
        'button[type="submit"]',
        'button:has-text("Log In")',
        'button:has-text("Sign in")',
        'button:has-text("Log in")',
      ],
      'login submit'
    );
    await page.waitForLoadState('domcontentloaded', { timeout: 120000 }).catch(() => {});
    await safeWait(page, 5000);
  }
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1024 } });
    await ensureLogin(page);
    await page.goto(`https://www.browseract.com/reception/logs?keyword=${encodeURIComponent(taskId)}`, {
      waitUntil: 'domcontentloaded',
      timeout: 120000,
    });
    await safeWait(page, 5000);
    await snap(page, '01-log-page');
    let detailUrl = '';
    try {
      const detailButton = await firstVisibleLocator(page, [
        `tr[data-row-key="${taskId}"] td:last-child button:not([disabled])`,
        `tr[data-row-key="${taskId}"] button:not([disabled])`,
      ]);
      if (detailButton) {
        const currentUrl = String(page.url() || '');
        const popupPromise = page.waitForEvent('popup', { timeout: 5000 }).catch(() => null);
        await detailButton.click({ timeout: 10000, force: true });
        await safeWait(page, 3000);
        const popup = await popupPromise;
        if (popup) {
          await popup.waitForLoadState('domcontentloaded', { timeout: 20000 }).catch(() => {});
          await safeWait(popup, 3000);
          detailUrl = String(popup.url() || '');
          await snap(popup, '02-detail-page');
          fs.writeFileSync(
            path.join(stateDir, 'detail.json'),
            JSON.stringify({ url: detailUrl, text: await bodyText(popup) }, null, 2),
            'utf8'
          );
          await popup.close().catch(() => {});
        } else if (String(page.url() || '') !== currentUrl) {
          detailUrl = String(page.url() || '');
          await snap(page, '02-detail-page');
          fs.writeFileSync(
            path.join(stateDir, 'detail.json'),
            JSON.stringify({ url: detailUrl, text: await bodyText(page) }, null, 2),
            'utf8'
          );
        }
      }
    } catch {
      // keep summary-level capture even if detail drill-down fails
    }
    const text = await bodyText(page);
    const result = {
      status: 'ok',
      task_id: taskId,
      url: String(page.url() || ''),
      detail_url: detailUrl,
      text,
      state_dir: stateDir,
    };
    fs.writeFileSync(path.join(stateDir, 'result.json'), JSON.stringify(result, null, 2), 'utf8');
    console.log(JSON.stringify({ status: 'ok', task_id: taskId, url: result.url, state_dir: stateDir }));
  } catch (error) {
    const detail = {
      status: 'error',
      message: String(error && error.message ? error.message : error),
      state_dir: stateDir,
    };
    fs.writeFileSync(path.join(stateDir, 'result.json'), JSON.stringify(detail, null, 2), 'utf8');
    console.error(JSON.stringify(detail));
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(String(error && error.stack ? error.stack : error));
  process.exit(1);
});
