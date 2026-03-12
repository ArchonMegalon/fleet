'use strict';

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const stateDir = '/docker/fleet/state/browseract_bootstrap/node_edit_probe';
const username = String(process.env.BROWSERACT_USERNAME || '').trim();
const password = String(process.env.BROWSERACT_PASSWORD || '').trim();
const workflowName = String(process.env.BROWSERACT_WORKFLOW_NAME || 'browseract_architect').trim() || 'browseract_architect';

if (!username || !password) {
  throw new Error('BROWSERACT_USERNAME and BROWSERACT_PASSWORD are required');
}

fs.mkdirSync(stateDir, { recursive: true });

async function snap(page, name) {
  await page.screenshot({ path: path.join(stateDir, `${name}.png`), fullPage: true });
  fs.writeFileSync(path.join(stateDir, `${name}.html`), await page.content(), 'utf8');
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

async function clickFirst(page, selectors) {
  const locator = await firstVisibleLocator(page, selectors);
  if (!locator) {
    throw new Error(`Could not find clickable target: ${selectors.join(' | ')}`);
  }
  await locator.click({ timeout: 10000 });
}

async function fillFirst(page, selectors, value) {
  const locator = await firstVisibleLocator(page, selectors);
  if (!locator) {
    throw new Error(`Could not find fill target: ${selectors.join(' | ')}`);
  }
  await locator.fill(value, { timeout: 10000 });
}

async function bodyText(page) {
  try {
    return await page.locator('body').innerText({ timeout: 3000 });
  } catch {
    return '';
  }
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
    return false;
  }
  await page.waitForTimeout(1500);
  return true;
}

async function ensureLogin(page) {
  await page.goto('https://app.browseract.com/reception/workflow-list', {
    waitUntil: 'domcontentloaded',
    timeout: 120000,
  });
  await page.waitForTimeout(2000);
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
      await page.waitForTimeout(2000);
    }
    loginNeeded = await page.locator('input[type="password"], input[name="password"]').count();
  }
  if (loginNeeded > 0 || /login|sign in|sign up/i.test(await page.title()) || /sign up/i.test(await bodyText(page))) {
    await maybeSwitchSignupToLogin(page);
    await fillFirst(page, ['#formLogin_email', 'input[type="email"]', 'input[name="email"]'], username);
    await fillFirst(page, ['#formLogin_password', 'input[type="password"]', 'input[name="password"]'], password);
    await clickFirst(page, ['form#formLogin button[type="submit"]', 'button[type="submit"]', 'button:has-text("Log In")', 'button:has-text("Sign in")', 'button:has-text("Log in")']);
    await page.waitForLoadState('domcontentloaded', { timeout: 120000 }).catch(() => {});
    await page.waitForTimeout(5000);
    await page.goto('https://app.browseract.com/reception/workflow-list', {
      waitUntil: 'domcontentloaded',
      timeout: 120000,
    });
    await page.waitForTimeout(2000);
  }
}

async function openBuilderPopup(page) {
  const title = page.locator(`div[title="${workflowName}"]`).first();
  await title.waitFor({ state: 'visible', timeout: 15000 });
  const card = title.locator('xpath=ancestor::div[contains(@class,"group relative")][1]');
  await card.hover({ force: true, timeout: 10000 });
  await page.waitForTimeout(1000);
  const buildLabel = card.locator('div').filter({ hasText: /^Build$/ }).last();
  await buildLabel.waitFor({ state: 'visible', timeout: 10000 });
  const popupPromise = page.waitForEvent('popup', { timeout: 10000 });
  await buildLabel.click({ timeout: 10000, force: true });
  const popup = await popupPromise;
  await popup.waitForLoadState('domcontentloaded', { timeout: 20000 }).catch(() => {});
  await popup.waitForTimeout(3000);
  return popup;
}

async function countInputs(node) {
  return {
    inputs: await node.locator('input').count(),
    textareas: await node.locator('textarea').count(),
  };
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1024 } });
    await ensureLogin(page);
    const popup = await openBuilderPopup(page);
    const node = popup.locator('.react-flow__node').filter({ hasText: 'Visit Page_1' }).first();
    await node.waitFor({ state: 'visible', timeout: 10000 });
    await snap(popup, '01-before');

    const urlLabel = node.getByText(/^URL$/).first();
    await urlLabel.click({ timeout: 3000 }).catch(() => {});
    await popup.waitForTimeout(1000);
    await snap(popup, '02-after-label-click');

    const rowButtons = node.locator('button');
    const buttonCount = await rowButtons.count();
    if (buttonCount > 0) {
      await rowButtons.last().click({ timeout: 3000, force: true }).catch(() => {});
      await popup.waitForTimeout(1000);
      await snap(popup, '03-after-button-click');
    }

    await node.dblclick({ timeout: 3000 }).catch(() => {});
    await popup.waitForTimeout(1000);
    await snap(popup, '04-after-double-click');

    const result = {
      status: 'ok',
      state_dir: stateDir,
      counts: {
        before: await countInputs(node),
      },
    };
    fs.writeFileSync(path.join(stateDir, 'result.json'), JSON.stringify(result, null, 2), 'utf8');
    console.log(JSON.stringify(result));
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
