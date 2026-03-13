'use strict';

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const stateDir = String(process.env.BROWSERACT_STATE_DIR || '/docker/fleet/state/browseract_bootstrap/publish').trim();
const username = String(process.env.BROWSERACT_USERNAME || '').trim();
const password = String(process.env.BROWSERACT_PASSWORD || '').trim();
const workflowName = String(process.env.BROWSERACT_WORKFLOW_NAME || '').trim();
const workflowId = String(process.env.BROWSERACT_WORKFLOW_ID || '').trim();

if (!username || !password) {
  throw new Error('BROWSERACT_USERNAME and BROWSERACT_PASSWORD are required');
}
if (!workflowName && !workflowId) {
  throw new Error('BROWSERACT_WORKFLOW_NAME or BROWSERACT_WORKFLOW_ID is required');
}

fs.mkdirSync(stateDir, { recursive: true });

async function snap(page, name) {
  if (!page || page.isClosed()) {
    return;
  }
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
    // BrowserAct can invalidate the current dashboard page during publish flows.
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

async function ensureWorkflowList(page) {
  const currentUrl = String(page.url() || '');
  if (/\/reception\/workflow-list/i.test(currentUrl)) {
    return;
  }
  await page.goto('https://app.browseract.com/reception/workflow-list', {
    waitUntil: 'domcontentloaded',
    timeout: 120000,
  });
  await safeWait(page, 2500);
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
    await page.goto('https://app.browseract.com/reception/workflow-list', {
      waitUntil: 'domcontentloaded',
      timeout: 120000,
    });
    await safeWait(page, 2000);
  }
}

async function findWorkflowTitle(page) {
  await ensureWorkflowList(page);
  const escapedName = workflowName.replace(/["\\]/g, '\\$&');
  const selectors = [
    `div[title="${escapedName}"]`,
    `[title="${escapedName}"]`,
    `text="${workflowName}"`,
  ];
  const deadline = Date.now() + 30000;
  while (Date.now() < deadline) {
    const locator = await firstVisibleLocator(page, selectors);
    if (locator) {
      return locator;
    }
    const text = await bodyText(page);
    if (/404: This page could not be found/i.test(text) || /Return Home/i.test(text)) {
      await ensureWorkflowList(page);
    } else {
      await page.reload({ waitUntil: 'domcontentloaded', timeout: 120000 }).catch(() => {});
      await safeWait(page, 2000);
    }
  }
  throw new Error(`Timed out locating workflow card for ${workflowName}`);
}

async function locateCard(page) {
  const title = await findWorkflowTitle(page);
  return title.locator('xpath=ancestor::div[contains(@class,"group relative")][1]');
}

async function extractWorkflowIdFromCard(card) {
  try {
    return await card.evaluate((element) => {
      const text = String(element.textContent || '');
      const match = text.match(/ID\s*:?\s*([A-Za-z0-9_-]{6,})/i);
      return match ? match[1] : '';
    });
  } catch {
    return '';
  }
}

async function builderLooksReady(page) {
  const selectors = [
    'button[data-sentry-element="ButtonAddNode"]',
    '[data-testid^="rf__node-"]',
    '.react-flow',
  ];
  const locator = await firstVisibleLocator(page, selectors);
  if (locator) {
    return true;
  }
  const currentUrl = String(page.url() || '');
  return /\/workflow\/.+\/orchestration/i.test(currentUrl) && !/wrong turn|return home/i.test(await bodyText(page));
}

async function openBuilderSurface(page) {
  if (await builderLooksReady(page)) {
    return { workflowId: workflowId || '', page };
  }
  await ensureWorkflowList(page);
  let resolvedId = workflowId;
  if (resolvedId) {
    await page.goto(`https://www.browseract.com/workflow/${resolvedId}/orchestration`, {
      waitUntil: 'domcontentloaded',
      timeout: 120000,
    });
    await safeWait(page, 4000);
    if (await builderLooksReady(page)) {
      return { workflowId: resolvedId, page };
    }
  }
  if (!workflowName) {
    throw new Error(`Could not open workflow ${workflowId}`);
  }
  const card = await locateCard(page);
  resolvedId = resolvedId || await extractWorkflowIdFromCard(card);
  await card.hover({ force: true, timeout: 10000 });
  await safeWait(page, 1000);
  const buildLabel = card.locator('div.group\\/do').filter({ hasText: /^Build$/ }).first();
  const buildParent = buildLabel.locator('xpath=ancestor::div[contains(@class,"group/do")][1]').first();
  await buildLabel.waitFor({ state: 'visible', timeout: 10000 }).catch(async () => {
    await card.locator('div').filter({ hasText: /^Build$/ }).last().waitFor({ state: 'visible', timeout: 5000 });
  });
  const currentUrl = String(page.url() || '');
  const popupPromise = page
    .waitForEvent('popup', { timeout: 10000 })
    .then(async (popup) => {
      await popup.waitForLoadState('domcontentloaded', { timeout: 20000 }).catch(() => {});
      await safeWait(popup, 3000);
      return popup;
    })
    .catch(() => null);
  const sameTabPromise = Promise.race([
    page
      .waitForURL((url) => {
        const value = String(url || '');
        return value !== currentUrl && /\/workflow\/.+\/orchestration/i.test(value);
      }, { timeout: 10000 })
      .then(async () => {
        await safeWait(page, 3000);
        return page;
      })
      .catch(() => null),
    page
      .waitForSelector('button[data-sentry-element="ButtonAddNode"], [data-testid^="rf__node-"], .react-flow', { timeout: 10000 })
      .then(async () => {
        await safeWait(page, 1500);
        return page;
      })
      .catch(() => null),
  ]);
  await buildParent.click({ timeout: 10000, force: true }).catch(async () => {
    await buildLabel.click({ timeout: 10000, force: true });
  });
  const surface = await Promise.race([
    popupPromise,
    sameTabPromise,
    safeWait(page, 12000).then(() => null),
  ]);
  if (surface && surface !== page) {
    try {
      await page.close();
    } catch {
      // ignore
    }
  }
  const target = surface || page;
  if (resolvedId && !(await builderLooksReady(target))) {
    await target.goto(`https://www.browseract.com/workflow/${resolvedId}/orchestration`, {
      waitUntil: 'domcontentloaded',
      timeout: 120000,
    });
    await safeWait(target, 4000);
  }
  if (!(await builderLooksReady(target))) {
    const text = await bodyText(target);
    throw new Error(`Could not reach builder surface for ${workflowName || workflowId}: ${text.slice(0, 300)}`);
  }
  return { workflowId: resolvedId || '', page: target };
}

async function clickPublishFlow(page) {
  const publishButton = await firstVisibleLocator(page, [
    'button:has-text("Publish")',
    'button.ant-btn:has-text("Publish")',
    '[data-sentry-element="AppButton"]:has-text("Publish")',
  ]);
  if (!publishButton) {
    throw new Error('Could not find publish button in builder');
  }
  await publishButton.click({ timeout: 10000, force: true });
  await safeWait(page, 1500);

  const publishVersionButton = await firstVisibleLocator(page, [
    'button:has-text("Publish as New Version")',
    'button.ant-btn:has-text("Publish as New Version")',
    'button:has-text("Publish")',
  ]);
  if (!publishVersionButton) {
    throw new Error('Could not find publish confirmation button');
  }
  await publishVersionButton.click({ timeout: 10000, force: true });
  await safeWait(page, 1500);

  const continueModal = page.locator('.ant-modal-confirm').filter({
    hasText: /There are collection nodes in the workflow, but no output nodes/i,
  }).first();
  try {
    await continueModal.waitFor({ state: 'visible', timeout: 5000 });
    const okButton = continueModal.locator('button').filter({ hasText: /^OK$/ }).first();
    await okButton.waitFor({ state: 'visible', timeout: 5000 });
    await okButton.click({ timeout: 10000 });
    await safeWait(page, 3000);
  } catch {
    // no extra publish confirmation needed
  }
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1024 } });
    await ensureLogin(page);
    await snap(page, '01-list');
    const opened = await openBuilderSurface(page);
    const builderPage = opened.page || page;
    const resolvedId = opened.workflowId || '';
    await snap(builderPage, '02-builder');
    await clickPublishFlow(builderPage);
    await snap(builderPage, '03-publish-popover');
    await safeWait(builderPage, 4000);
    await snap(builderPage, '04-after-publish');

    const text = await bodyText(builderPage);
    const urlWorkflowId = (String(builderPage.url() || '').match(/\/workflow\/([^/]+)\/orchestration/i) || [])[1] || '';
    const published = !/Last Published\s*:\s*-/i.test(text);
    const result = {
      status: 'ok',
      workflow_id: resolvedId || urlWorkflowId,
      workflow_name: workflowName || '',
      popup_url: String(builderPage.url() || ''),
      published,
      state_dir: stateDir,
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
