'use strict';

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const stateDir = String(process.env.BROWSERACT_STATE_DIR || '/docker/fleet/state/browseract_bootstrap/materialize').trim() || '/docker/fleet/state/browseract_bootstrap/materialize';
const packetPath = String(process.env.BROWSERACT_PACKET_PATH || '/docker/fleet/state/browseract_bootstrap/browseract_architect.packet.json').trim() || '/docker/fleet/state/browseract_bootstrap/browseract_architect.packet.json';
const username = String(process.env.BROWSERACT_USERNAME || '').trim();
const password = String(process.env.BROWSERACT_PASSWORD || '').trim();
const workflowName = String(process.env.BROWSERACT_WORKFLOW_NAME || '').trim();
const captureSnapshots = !/^(0|false|no)$/i.test(String(process.env.BROWSERACT_CAPTURE_SNAPSHOTS || '1').trim());
const captureHtml = !/^(0|false|no)$/i.test(String(process.env.BROWSERACT_CAPTURE_HTML || '0').trim());

if (!username || !password) {
  throw new Error('BROWSERACT_USERNAME and BROWSERACT_PASSWORD are required');
}

if (!fs.existsSync(packetPath)) {
  throw new Error(`Missing packet: ${packetPath}`);
}

const packet = JSON.parse(fs.readFileSync(packetPath, 'utf8'));
const resolvedWorkflowName = workflowName || String(packet.workflow_name || 'browseract_architect').trim() || 'browseract_architect';
const workflowDescription = String(packet.description || '').trim();
fs.mkdirSync(stateDir, { recursive: true });

function actionLabelForPacketNode(node) {
  switch (String(node && node.type ? node.type : '').trim()) {
    case 'visit_page':
      return 'Visit Page';
    case 'click':
      return 'Click Element';
    case 'input_text':
      return 'Input Text';
    case 'wait':
      return 'Wait';
    case 'extract':
      return 'Extract Data';
    case 'output':
      return null;
    case 'repeat':
      return 'Loop List';
    default:
      return null;
  }
}

function slugify(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

async function snap(page, name) {
  if (!captureSnapshots) {
    return;
  }
  if (!page || page.isClosed()) {
    return;
  }
  const png = path.join(stateDir, `${name}.png`);
  const html = path.join(stateDir, `${name}.html`);
  const meta = path.join(stateDir, `${name}.json`);
  try {
    await page.screenshot({ path: png, fullPage: true });
  } catch (error) {
    const message = String(error && error.message ? error.message : error);
    if (/Target page, context or browser has been closed/i.test(message)) {
      return;
    }
    throw error;
  }
  if (captureHtml) {
    try {
      fs.writeFileSync(html, await page.content(), 'utf8');
    } catch (error) {
      const message = String(error && error.message ? error.message : error);
      if (!/Target page, context or browser has been closed/i.test(message)) {
        throw error;
      }
    }
  }
  fs.writeFileSync(
    meta,
    JSON.stringify(
      {
        url: String(page.url() || ''),
        title: await page.title().catch(() => ''),
      },
      null,
      2
    ),
    'utf8'
  );
}

function appendConfigLog(payload) {
  fs.appendFileSync(path.join(stateDir, 'config-log.jsonl'), `${JSON.stringify(payload)}\n`, 'utf8');
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

async function clickFirst(page, selectors, label) {
  const locator = await firstVisibleLocator(page, selectors);
  if (!locator) {
    throw new Error(`Could not find clickable target: ${label}`);
  }
  await locator.scrollIntoViewIfNeeded().catch(() => {});
  await locator.click({ timeout: 10000, force: true });
}

async function fillFirst(page, selectors, value, label) {
  const locator = await firstVisibleLocator(page, selectors);
  if (!locator) {
    throw new Error(`Could not find input target: ${label}`);
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

async function safeWait(page, timeoutMs) {
  try {
    if (!page || page.isClosed()) {
      return;
    }
    await page.waitForTimeout(timeoutMs);
  } catch {
    // BrowserAct can invalidate the current dashboard page during create/publish flows.
  }
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

async function maybeConfirmPublish(page) {
  const continueModal = page.locator('.ant-modal-confirm').filter({
    hasText: /There are collection nodes in the workflow, but no output nodes/i,
  }).first();
  try {
    await continueModal.waitFor({ state: 'visible', timeout: 5000 });
    const okButton = continueModal.locator('button').filter({ hasText: /^OK$/ }).first();
    await okButton.waitFor({ state: 'visible', timeout: 5000 });
    await okButton.click({ timeout: 10000 });
    await safeWait(page, 3000);
    return true;
  } catch {
    return false;
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

async function reviveDashboardPage(context, page) {
  if (page && !page.isClosed()) {
    return page;
  }
  const fresh = await context.newPage();
  await ensureLogin(fresh);
  await maybeDismiss(fresh);
  await maybeCloseCreateModal(fresh);
  return fresh;
}

async function findWorkflowTitle(page) {
  await ensureWorkflowList(page);
  const escapedName = resolvedWorkflowName.replace(/["\\]/g, '\\$&');
  const selectors = [
    `div[title="${escapedName}"]`,
    `[title="${escapedName}"]`,
    `text="${resolvedWorkflowName}"`,
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
  throw new Error(`Timed out locating workflow card for ${resolvedWorkflowName}`);
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

async function maybeDismiss(page) {
  const selectors = [
    'button:has-text("Accept")',
    'button:has-text("Got it")',
    'button:has-text("Skip")',
    'button:has-text("Close")',
  ];
  for (const selector of selectors) {
    const locator = page.locator(selector).first();
    try {
      if (await locator.isVisible({ timeout: 500 })) {
        await locator.click({ timeout: 2000 });
        return;
      }
    } catch {
      // ignore
    }
  }
}

async function maybeCloseCreateModal(page) {
  const cancel = page.locator('.ant-modal button').filter({ hasText: /^Cancel$/ }).first();
  try {
    await cancel.waitFor({ state: 'visible', timeout: 1500 });
    await cancel.click({ timeout: 5000 });
    await safeWait(page, 1000);
    return true;
  } catch {
    return false;
  }
}

async function clickPreferredCreateButton(page) {
  const deadline = Date.now() + 20000;
  while (Date.now() < deadline) {
    const explicitCreate = await firstVisibleLocator(page, [
      'button[data-sentry-component="ButtonCreate"]',
      'button[data-sentry-element="AppButton"]:has-text("Create")',
      'button.ant-btn:has-text("Create")',
      'button:has-text("Create")',
    ]);
    if (explicitCreate) {
      await explicitCreate.scrollIntoViewIfNeeded().catch(() => {});
      await explicitCreate.click({ timeout: 10000, force: true }).catch(async () => {
        await page.evaluate(() => {
          const direct = document.querySelector('button[data-sentry-component="ButtonCreate"]');
          if (direct instanceof HTMLElement) {
            direct.scrollIntoView({ block: 'center', inline: 'center' });
            direct.click();
          }
        }).catch(() => {});
      });
      await safeWait(page, 2500);
      return true;
    }
    const domClicked = await page.evaluate(() => {
      const direct = document.querySelector('button[data-sentry-component="ButtonCreate"]');
      if (direct instanceof HTMLElement) {
        direct.click();
        return true;
      }
      return false;
    }).catch(() => false);
    if (domClicked) {
      await safeWait(page, 2500);
      return true;
    }
    await safeWait(page, 1000);
  }
  const clicked = await page.evaluate(() => {
    const myTemplates = Array.from(document.querySelectorAll('a[href="/reception/my-template"]')).find((node) =>
      /my templates/i.test(node.textContent || '')
    );
    if (myTemplates) {
      const parent = myTemplates.parentElement;
      if (parent) {
        const createButton = Array.from(parent.querySelectorAll('button')).find((node) =>
          /create/i.test(node.textContent || '')
        );
        if (createButton) {
          createButton.click();
          return true;
        }
      }
    }
    return false;
  }).catch(() => false);
  if (clicked) {
    await safeWait(page, 2500);
  }
  return clicked;
}

async function waitForCreateSurface(page, timeoutMs = 45000) {
  const deadline = Date.now() + timeoutMs;
  const readinessSelectors = [
    'input[name="name"]',
    'input[placeholder*="workflow" i]',
    'button:has-text("Create workflow")',
    'button:has-text("New workflow")',
    'a:has-text("Create workflow")',
    'a:has-text("New workflow")',
    '[data-testid="create-workflow"]',
    'text=/Custom Workflow/i',
  ];
  while (Date.now() < deadline) {
    const locator = await firstVisibleLocator(page, readinessSelectors);
    if (locator) {
      return true;
    }
    await safeWait(page, 1500);
  }
  return false;
}

async function workflowExists(page) {
  await ensureWorkflowList(page);
  const escapedName = resolvedWorkflowName.replace(/["\\]/g, '\\$&');
  const selectors = [
    `div[title="${escapedName}"]`,
    `[title="${escapedName}"]`,
    `text="${resolvedWorkflowName}"`,
  ];
  try {
    const locator = await firstVisibleLocator(page, selectors);
    if (locator) {
      return true;
    }
    const text = await bodyText(page);
    return text.includes(resolvedWorkflowName);
  } catch {
    return false;
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
  return /\/workflow\/.+\/orchestration/i.test(currentUrl);
}

async function openBuilderSurface(page) {
  if (await builderLooksReady(page)) {
    return page;
  }
  await ensureWorkflowList(page);
  const card = await locateCard(page);
  const workflowId = await extractWorkflowIdFromCard(card);
  if (workflowId) {
    try {
      await page.goto(`https://www.browseract.com/workflow/${workflowId}/orchestration`, {
        waitUntil: 'domcontentloaded',
        timeout: 20000,
      });
      await safeWait(page, 3000);
      if (await builderLooksReady(page)) {
        return page;
      }
    } catch {
      // fall back to UI-driven open below
    }
    await ensureWorkflowList(page);
  }
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
  if (surface) {
    return surface;
  }

  const cardTitle = card.locator(`div[title="${resolvedWorkflowName}"]`).first();
  try {
    await cardTitle.click({ timeout: 5000, force: true });
    const titleSurface = await Promise.race([
      page
        .waitForURL((url) => /\/workflow\/.+\/orchestration/i.test(String(url || '')), { timeout: 10000 })
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
    if (titleSurface) {
      return titleSurface;
    }
  } catch {
    // ignore fallback click errors
  }
  throw new Error(`Could not open BrowserAct builder surface for ${resolvedWorkflowName}`);
}

async function openWorkflowSurfaceById(context, workflowId) {
  if (!workflowId) {
    throw new Error(`Missing workflow id for ${resolvedWorkflowName}`);
  }
  const fresh = await context.newPage();
  await ensureLogin(fresh);
  await maybeDismiss(fresh);
  await maybeCloseCreateModal(fresh);
  await fresh.goto(`https://www.browseract.com/workflow/${workflowId}/orchestration`, {
    waitUntil: 'domcontentloaded',
    timeout: 30000,
  });
  await safeWait(fresh, 3000);
  if (!(await builderLooksReady(fresh))) {
    throw new Error(`Builder surface not ready for workflow ${workflowId}`);
  }
  return fresh;
}

async function listCurrentNodeLabels(popup) {
  return await popup.evaluate(() => {
    const nodes = Array.from(document.querySelectorAll('[data-testid^="rf__node-"]'));
    return nodes
      .filter((node) => {
        const cls = String(node.className || '');
        return !cls.includes('react-flow__node-START') && !cls.includes('react-flow__node-ADD_NODE_BUTTON');
      })
      .map((node) => {
        const imgAlt = node.querySelector('img[alt]')?.getAttribute('alt') || '';
        if (imgAlt) {
          return imgAlt.trim();
        }
        const normalizedText = (node.textContent || '').replace(/\s+/g, ' ').trim();
        const knownLabel = normalizedText.match(/(?:Finish:\s*)?((?:Visit Page|Click Element|Input Text|Wait|Extract Data(?: Item)?|Output Data|Loop List)_\d+)/i);
        if (knownLabel && knownLabel[1]) {
          return knownLabel[1].trim();
        }
        return normalizedText;
      })
      .filter(Boolean);
  });
}

async function workflowHasEquivalentLabel(popup, expectedLabel) {
  const labels = await listCurrentNodeLabels(popup);
  if (labels.includes(expectedLabel)) {
    return true;
  }
  if (/^Output Data_\d+$/i.test(expectedLabel)) {
    const body = await bodyText(popup);
    return new RegExp(`(?:Finish:\\s*)?${expectedLabel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`, 'i').test(body);
  }
  return false;
}

function synthesizeClickDescription(node) {
  const label = String(node && node.label ? node.label : '').trim();
  const description = String(node && node.config && node.config.description ? node.config.description : '').trim();
  const selector = String(node && node.config && node.config.selector ? node.config.selector : '').trim();
  if (description) {
    return description;
  }
  if (/new workflow/i.test(label)) {
    return 'Open the create workflow action in the BrowserAct dashboard.';
  }
  if (/save draft/i.test(label)) {
    return 'Save the current workflow as a draft.';
  }
  if (/publish/i.test(label)) {
    return 'Publish the workflow as a new version.';
  }
  return selector || label || 'Click the required BrowserAct UI action.';
}

function synthesizeInputFieldDescription(node) {
  const label = String(node && node.label ? node.label : '').trim();
  const description = String(node && node.config && node.config.description ? node.config.description : '').trim();
  const selector = String(node && node.config && node.config.selector ? node.config.selector : '').trim();
  if (description) {
    return description;
  }
  if (/workflow name/i.test(label)) {
    return 'The workflow name input field in the BrowserAct create workflow dialog.';
  }
  if (/workflow description/i.test(label)) {
    return 'The workflow description field in the BrowserAct create workflow dialog.';
  }
  return selector || label || 'The target input field in the BrowserAct builder.';
}

function synthesizeInputValue(node) {
  const cfg = node && node.config ? node.config : {};
  if (cfg.value_from_input) {
    return `/${cfg.value_from_input}`;
  }
  if (cfg.value_from_secret) {
    return `/${cfg.value_from_secret}`;
  }
  if (cfg.value) {
    return String(cfg.value);
  }
  return '';
}

function synthesizeLoopDescription(node) {
  const label = String(node && node.label ? node.label : '').trim();
  const cfg = node && node.config ? node.config : {};
  const description = String(cfg.description || '').trim();
  if (description) {
    return description;
  }
  if (/add nodes/i.test(label)) {
    return 'Iterate over the node entries supplied in the builder packet and add them to the workflow in order.';
  }
  if (/wire edges/i.test(label)) {
    return 'Iterate over the edge entries supplied in the builder packet and connect the workflow nodes in order.';
  }
  const repeatSource = String(cfg.repeat_source || '').trim();
  const stepContract = String(cfg.step_contract || '').trim();
  return [repeatSource, stepContract].filter(Boolean).join(' | ') || label || 'Iterate over the supplied packet list.';
}

function synthesizeWaitDescription(node) {
  const label = String(node && node.label ? node.label : '').trim();
  const description = String(node && node.config && node.config.description ? node.config.description : '').trim();
  const selector = String(node && node.config && node.config.selector ? node.config.selector : '').trim();
  const timeout = String(node && node.config && node.config.timeout_ms ? node.config.timeout_ms : '').trim();
  if (description) {
    return description;
  }
  const parts = [];
  if (selector) {
    parts.push(`Wait until ${selector} is visible and ready.`);
  }
  if (timeout) {
    parts.push(`Use a timeout of ${timeout}ms.`);
  }
  return parts.join(' ') || label || 'Wait for the target page state to be ready.';
}

function synthesizeExtractDescription(node) {
  const label = String(node && node.label ? node.label : '').trim();
  const description = String(node && node.config && node.config.description ? node.config.description : '').trim();
  const selector = String(node && node.config && node.config.selector ? node.config.selector : '').trim();
  const field = String(node && node.config && node.config.field_name ? node.config.field_name : '').trim();
  const mode = String(node && node.config && node.config.mode ? node.config.mode : '').trim();
  if (description) {
    return description;
  }
  const parts = [];
  if (selector) {
    parts.push(`Extract data from ${selector}.`);
  }
  if (field) {
    parts.push(`Store it as ${field}.`);
  }
  if (mode) {
    parts.push(`Use ${mode} mode.`);
  }
  return parts.join(' ') || label || 'Extract the generated result data from the page.';
}

async function configureNodeInline(popup, expectedLabel, packetNode, stepIndex) {
  const escapedExpectedLabel = expectedLabel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const hiddenLabelInput = popup.locator(`input[maxlength="32"][value="${expectedLabel}"]`);
  let node = popup
    .locator('.react-flow__node')
    .filter({ has: hiddenLabelInput })
    .first();
  try {
    await node.waitFor({ state: 'visible', timeout: 2500 });
  } catch {
    node = popup
      .locator('.react-flow__node')
      .filter({ hasText: new RegExp(`^\\s*${escapedExpectedLabel}\\b`, 'i') })
      .first();
  }
  try {
    await node.waitFor({ state: 'visible', timeout: 1500 });
  } catch {
    node = popup
      .locator('.react-flow__node')
      .filter({ has: popup.locator(`img[alt="${expectedLabel}"]`) })
      .first();
  }
  if (/^Output Data_\d+$/i.test(expectedLabel)) {
    node = popup
      .locator('.react-flow__node')
      .filter({ hasText: new RegExp(`(?:Finish:\\s*)?${expectedLabel}$`, 'i') })
      .first();
  }
  try {
    await node.scrollIntoViewIfNeeded().catch(() => {});
    await node.waitFor({ state: 'visible', timeout: 4000 });
  } catch {
    node = popup
      .locator('[data-testid^="rf__node-"]')
      .filter({
        hasNot: popup.locator('.react-flow__node-START, .react-flow__node-ADD_NODE_BUTTON'),
      })
      .nth(Math.max(0, stepIndex - 1));
    await node.scrollIntoViewIfNeeded().catch(() => {});
    await node.waitFor({ state: 'visible', timeout: 10000 });
  }
  const type = String(packetNode && packetNode.type ? packetNode.type : '').trim();
  const editorSelector = [
    '[contenteditable="true"][role="textbox"]',
    '[contenteditable="true"][data-lexical-editor="true"]',
    'textarea',
    'input[type="number"]',
    'input[inputmode="decimal"]',
    'input[inputmode="numeric"]',
    'input.ant-input:not([maxlength="32"])',
    'input[placeholder]:not([maxlength="32"])',
    'input:not([type="radio"]):not([type="checkbox"]):not([type="hidden"]):not([maxlength="32"])',
  ].join(', ');
  let editors = node.locator(editorSelector);
  let editorCount = await editors.count();
  let visibleEditor = await lastVisibleEditor(editors);
  if (!visibleEditor) {
    const header = node.locator('.ant-collapse-header').first();
    await header.waitFor({ state: 'visible', timeout: 5000 });
    await header.click({ timeout: 10000, force: true }).catch(() => {});
    await safeWait(popup, 800);
    editors = node.locator(editorSelector);
    editorCount = await editors.count();
    visibleEditor = await lastVisibleEditor(editors);
  }
  appendConfigLog({
    step: stepIndex,
    expectedLabel,
    type,
    editor_count: editorCount,
    has_visible_editor: Boolean(visibleEditor),
  });

  async function setEditorValue(editor, value) {
    const useVariableBinding = typeof value === 'string' && value.startsWith('/');
    await editor.waitFor({ state: 'visible', timeout: 10000 });
    const tagName = await editor.evaluate((element) => element.tagName.toLowerCase());
    if (tagName === 'textarea' || tagName === 'input') {
      await editor.click({ timeout: 10000, force: true });
      await popup.keyboard.press(process.platform === 'darwin' ? 'Meta+A' : 'Control+A').catch(() => {});
      await popup.keyboard.press('Backspace').catch(() => {});
      if (useVariableBinding) {
        await popup.keyboard.type(value, { delay: 40 }).catch(async () => {
          await editor.fill(value, { timeout: 10000 });
        });
      } else {
        await editor.fill(value, { timeout: 10000 });
      }
      if (useVariableBinding) {
        await safeWait(popup, 700);
        const selected = await trySelectTypeaheadValue(popup, value);
        if (!selected) {
          await popup.keyboard.press('ArrowDown').catch(() => {});
          await safeWait(popup, 200);
          await popup.keyboard.press('Enter').catch(() => {});
        }
      }
      await editor.press('Tab').catch(() => {});
      return;
    }
    await editor.click({ timeout: 10000, force: true });
    if (useVariableBinding) {
      await popup.keyboard.press(process.platform === 'darwin' ? 'Meta+A' : 'Control+A').catch(() => {});
      await popup.keyboard.press('Backspace').catch(() => {});
      await popup.keyboard.type(value, { delay: 40 }).catch(() => {});
      await safeWait(popup, 700);
      const selected = await trySelectTypeaheadValue(popup, value);
      if (!selected) {
        await popup.keyboard.press('ArrowDown').catch(() => {});
        await safeWait(popup, 200);
        await popup.keyboard.press('Enter').catch(() => {});
      }
    } else {
      await editor.evaluate((element, nextValue) => {
        element.innerHTML = '';
        element.textContent = nextValue;
        element.focus();
        const inputEvent = new InputEvent('input', {
          bubbles: true,
          cancelable: true,
          inputType: 'insertReplacementText',
          data: nextValue,
        });
        element.dispatchEvent(inputEvent);
        const changeEvent = new Event('change', { bubbles: true });
        element.dispatchEvent(changeEvent);
      }, value);
    }
    await editor.press('Tab').catch(() => {});
  }

  async function trySelectTypeaheadValue(pageLike, rawValue) {
    const normalized = String(rawValue || '').replace(/^\//, '').trim().toLowerCase();
    if (!normalized) {
      return false;
    }
    const options = pageLike.locator(
      '[aria-label="Typeahead menu"][role="listbox"] [role="option"], [aria-label="Typeahead menu"][role="listbox"] *'
    );
    const optionCount = await options.count().catch(() => 0);
    for (let index = 0; index < optionCount; index += 1) {
      const option = options.nth(index);
      try {
        if (!(await option.isVisible({ timeout: 250 }))) {
          continue;
        }
        const text = String((await option.innerText({ timeout: 250 }).catch(() => '')) || '')
          .replace(/\s+/g, ' ')
          .trim()
          .toLowerCase();
        if (!text) {
          continue;
        }
        if (text === normalized || text.includes(normalized)) {
          await option.click({ timeout: 3000, force: true }).catch(() => {});
          await safeWait(pageLike, 250);
          return true;
        }
      } catch {
        // keep scanning
      }
    }
    return false;
  }

  async function lastVisibleEditor(locator) {
    const total = await locator.count();
    for (let index = total - 1; index >= 0; index -= 1) {
      const candidate = locator.nth(index);
      try {
        if (await candidate.isVisible({ timeout: 500 })) {
          return candidate;
        }
      } catch {
        // continue scanning
      }
    }
    if (total > 0) {
      return locator.nth(total - 1);
    }
    return null;
  }

  async function fillEditorsSequentially(values) {
    let nextIndex = 0;
    const total = await editors.count();
    for (let editorIndex = 0; editorIndex < total && nextIndex < values.length; editorIndex += 1) {
      const value = values[nextIndex];
      if (!value) {
        nextIndex += 1;
        continue;
      }
      const editor = editors.nth(editorIndex);
      try {
        await setEditorValue(editor, value);
        nextIndex += 1;
      } catch {
        // keep scanning for the next visible writable editor
      }
    }
    if (nextIndex < values.length) {
      throw new Error(`Could not fill all editors for ${expectedLabel}`);
    }
  }

  async function writeNodeValues(selector, values) {
    if (Array.isArray(values) && values.some((value) => typeof value === 'string' && value.startsWith('/'))) {
      return false;
    }
    return await node.evaluate(
      (element, payload) => {
        const values = Array.isArray(payload.values) ? payload.values.filter(Boolean) : [];
        if (!values.length) {
          return false;
        }
        const candidates = Array.from(element.querySelectorAll(payload.selector || ''));
        if (!candidates.length) {
          return false;
        }
        const assignValue = (target, value) => {
          if (!target || !value) {
            return false;
          }
          if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) {
            target.focus();
            target.value = value;
            target.dispatchEvent(new Event('input', { bubbles: true }));
            target.dispatchEvent(new Event('change', { bubbles: true }));
            return true;
          }
          if (target.getAttribute && target.getAttribute('contenteditable') === 'true') {
            target.textContent = value;
            target.dispatchEvent(new InputEvent('input', { bubbles: true, data: value, inputType: 'insertText' }));
            target.dispatchEvent(new Event('change', { bubbles: true }));
            return true;
          }
          return false;
        };
        if (values.length === 1) {
          return assignValue(candidates[candidates.length - 1], values[0]);
        }
        const first = assignValue(candidates[0], values[0]);
        const last = assignValue(candidates[candidates.length - 1], values[values.length - 1]);
        return first && last;
      },
      { selector, values }
    );
  }

  async function writeFieldByLabel(label, value) {
    if (!label || !value) {
      return false;
    }
    if (typeof value === 'string' && value.startsWith('/')) {
      return false;
    }
    return await node.evaluate(
      (element, payload) => {
        const normalize = (input) => String(input || '').replace(/\s+/g, ' ').trim().toLowerCase();
        const wanted = normalize(payload.label);
        const nextValue = String(payload.value || '');
        if (!wanted || !nextValue) {
          return false;
        }
        const isWritable = (target) => {
          if (!(target instanceof HTMLElement)) {
            return false;
          }
          if (target instanceof HTMLInputElement) {
            if (target.type === 'hidden' || target.type === 'radio' || target.type === 'checkbox') {
              return false;
            }
            if (target.maxLength === 32) {
              return false;
            }
            return true;
          }
          if (target instanceof HTMLTextAreaElement) {
            return true;
          }
          return target.getAttribute('contenteditable') === 'true';
        };
        const setValue = (target) => {
          if (!isWritable(target)) {
            return false;
          }
          if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) {
            target.focus();
            target.value = nextValue;
            target.dispatchEvent(new Event('input', { bubbles: true }));
            target.dispatchEvent(new Event('change', { bubbles: true }));
            target.dispatchEvent(new Event('blur', { bubbles: true }));
            return true;
          }
          if (target instanceof HTMLElement && target.getAttribute('contenteditable') === 'true') {
            target.focus();
            target.textContent = nextValue;
            target.dispatchEvent(
              new InputEvent('input', {
                bubbles: true,
                cancelable: true,
                inputType: 'insertReplacementText',
                data: nextValue,
              })
            );
            target.dispatchEvent(new Event('change', { bubbles: true }));
            target.dispatchEvent(new Event('blur', { bubbles: true }));
            return true;
          }
          return false;
        };
        const writableSelector = String(payload.selector || '');
        const labelNodes = Array.from(element.querySelectorAll('*')).filter((candidate) => {
          const text = normalize(candidate.textContent);
          if (!text) {
            return false;
          }
          if (text === wanted) {
            return true;
          }
          return text.startsWith(wanted) && text.length <= wanted.length + 40;
        });
        const seen = new Set();
        const tryContainer = (container) => {
          if (!(container instanceof HTMLElement)) {
            return false;
          }
          if (seen.has(container)) {
            return false;
          }
          seen.add(container);
          const editors = Array.from(container.querySelectorAll(writableSelector)).filter((candidate) =>
            isWritable(candidate)
          );
          for (const editor of editors) {
            if (setValue(editor)) {
              return true;
            }
          }
          return false;
        };
        for (const labelNode of labelNodes) {
          let current = labelNode;
          for (let depth = 0; depth < 6 && current; depth += 1) {
            if (tryContainer(current)) {
              return true;
            }
            current = current.parentElement;
          }
          let sibling = labelNode.nextElementSibling;
          while (sibling) {
            if (tryContainer(sibling)) {
              return true;
            }
            sibling = sibling.nextElementSibling;
          }
        }
        return false;
      },
      { label, value, selector: editorSelector }
    );
  }

  if (type === 'visit_page') {
    const url = String(packetNode && packetNode.config && packetNode.config.url ? packetNode.config.url : '').trim();
    if (url) {
      appendConfigLog({
        step: stepIndex,
        expectedLabel,
        type,
        phase: 'visit_page_before_write',
        url,
      });
      const wroteUrlByLabel = await writeFieldByLabel('URL', url);
      const wroteUrl = wroteUrlByLabel || await writeNodeValues(editorSelector, [url]);
      const visitEditors = node.locator(editorSelector);
      const visitEditorCount = await visitEditors.count();
      appendConfigLog({
        step: stepIndex,
        expectedLabel,
        type,
        phase: 'visit_page_after_write',
        wrote_url_by_label: wroteUrlByLabel,
        wrote_url: wroteUrl,
        visit_editor_count: visitEditorCount,
      });
      if (!wroteUrl) {
        let targetEditor = null;
        if (visitEditorCount > 0) {
          targetEditor = await lastVisibleEditor(visitEditors);
        }
        if (!targetEditor) {
          targetEditor = visibleEditor;
        }
        if (!targetEditor) {
          throw new Error(`Could not locate a writable URL editor for ${expectedLabel}`);
        }
        await setEditorValue(targetEditor, url);
        appendConfigLog({
          step: stepIndex,
          expectedLabel,
          type,
          phase: 'visit_page_after_set',
        });
      }
      const currentTabRadio = node.locator('label').filter({ hasText: /^Current Tab Access$/ }).first();
      await currentTabRadio.click({ timeout: 5000, force: true }).catch(() => {});
    }
  } else if (type === 'click') {
    await fillEditorsSequentially([synthesizeClickDescription(packetNode)]);
  } else if (type === 'input_text') {
    const inputValue = synthesizeInputValue(packetNode);
    const fieldDescription = synthesizeInputFieldDescription(packetNode);
    let wroteFieldDescription = fieldDescription ? await writeFieldByLabel('Input Field Position', fieldDescription) : false;
    let wroteTextValue = inputValue ? await writeFieldByLabel('Text to Input', inputValue) : false;
    const nodeText = await node.innerText().catch(() => '');
    if (fieldDescription && wroteFieldDescription && !nodeText.includes(fieldDescription)) {
      wroteFieldDescription = false;
    }
    if (inputValue && wroteTextValue && !nodeText.includes(inputValue)) {
      wroteTextValue = false;
    }
    appendConfigLog({
      step: stepIndex,
      expectedLabel,
      type,
      phase: 'input_text_after_label_write',
      wrote_field_description: wroteFieldDescription,
      wrote_text_value: wroteTextValue,
      node_text: nodeText,
    });
    if (!wroteFieldDescription || !wroteTextValue) {
      const textInputLabelVisible = /Text to Input/i.test(nodeText);
      const hasSamplePrompt = /View Sample/i.test(nodeText);
      if (textInputLabelVisible || hasSamplePrompt) {
        const directValues = [];
        if (fieldDescription && !wroteFieldDescription && !/Element Location Description/i.test(nodeText)) {
          directValues.push(fieldDescription);
        }
        if (inputValue && !wroteTextValue) {
          directValues.push(inputValue);
        }
        if (directValues.length) {
          const textEditors = node.locator(editorSelector);
          const textEditorCount = await textEditors.count();
          if (textEditorCount > 0) {
            const wroteValues = await writeNodeValues(editorSelector, directValues);
            if (!wroteValues) {
              let targetEditor = await lastVisibleEditor(textEditors);
              if (!targetEditor) {
                targetEditor = visibleEditor;
              }
              if (targetEditor && inputValue && !wroteTextValue) {
                await setEditorValue(targetEditor, inputValue);
              } else if (!targetEditor) {
                throw new Error(`Could not locate a writable text editor for ${expectedLabel}`);
              }
            }
          }
        }
      } else {
        const fallbackValues = [];
        if (fieldDescription && !wroteFieldDescription) {
          fallbackValues.push(fieldDescription);
        }
        if (inputValue && !wroteTextValue) {
          fallbackValues.push(inputValue);
        }
        if (fallbackValues.length) {
          await fillEditorsSequentially(fallbackValues);
        }
      }
    }
  } else if (type === 'wait') {
    const numericEditors = node.locator('input[type="number"], input[inputmode="decimal"], input[inputmode="numeric"]');
    const numericCount = await numericEditors.count();
    const timeoutMs = Number(packetNode && packetNode.config && packetNode.config.timeout_ms ? packetNode.config.timeout_ms : 5000);
    const timeoutSeconds = String(Math.max(1, Math.ceil(timeoutMs / 1000)));
    const wroteWaitByLabel = await writeFieldByLabel('Seconds to Proceed', timeoutSeconds);
    if (!wroteWaitByLabel && numericCount > 0) {
      await setEditorValue(numericEditors.first(), timeoutSeconds);
    } else if (!wroteWaitByLabel) {
      await fillEditorsSequentially([synthesizeWaitDescription(packetNode)]);
    }
  } else if (type === 'extract') {
    const extractEditors = node.locator([
      'input.ant-input:not([maxlength="32"])',
      'input[placeholder]:not([maxlength="32"])',
      'input:not([type="radio"]):not([type="checkbox"]):not([type="hidden"]):not([maxlength="32"])',
      'textarea',
      '[contenteditable="true"][role="textbox"]',
      '[contenteditable="true"][data-lexical-editor="true"]',
    ].join(', '));
    const extractCount = await extractEditors.count();
    if (extractCount > 0) {
      const fieldName = String(packetNode && packetNode.config && packetNode.config.field_name ? packetNode.config.field_name : '').trim() || 'generated_prompt';
      const targetEditor = await lastVisibleEditor(extractEditors);
      if (targetEditor) {
        await setEditorValue(targetEditor, fieldName);
      }
    } else {
      await fillEditorsSequentially([synthesizeExtractDescription(packetNode)]);
    }
  } else if (type === 'output') {
    appendConfigLog({
      step: stepIndex,
      expectedLabel,
      type,
      phase: 'output_passthrough',
      reason: 'skip_output_edit_to_avoid_builder_hang',
    });
  } else if (type === 'repeat') {
    await fillEditorsSequentially([synthesizeLoopDescription(packetNode)]);
  }

  await safeWait(popup, 1000);
  await snap(popup, `06-configure-${String(stepIndex).padStart(2, '0')}-${slugify(expectedLabel)}`);
}

async function addActionNode(popup, actionLabel, expectedLabel, stepIndex) {
  const beforeLabels = await listCurrentNodeLabels(popup);

  const addButton = popup.locator('button[data-sentry-element="ButtonAddNode"]').last();
  await addButton.waitFor({ state: 'visible', timeout: 10000 });
  await addButton.click({ timeout: 10000 });
  await safeWait(popup, 1500);
  await snap(popup, `03-library-${String(stepIndex).padStart(2, '0')}-${slugify(actionLabel)}`);

  const librarySearch = await firstVisibleLocator(popup, [
    'input[placeholder*="Search" i]',
    'input[placeholder*="search" i]',
    'input[type="search"]',
  ]);
  if (librarySearch) {
    await librarySearch.fill(actionLabel, { timeout: 10000 }).catch(() => {});
    await safeWait(popup, 1200);
  }

  const exactPattern = new RegExp(`^${actionLabel}$`);
  const relaxedPattern =
    actionLabel === 'Output Data'
      ? /Output/i
      : actionLabel === 'Extract Data'
        ? /Extract Data(?: Item)?/i
        : new RegExp(actionLabel.replace(/\s+/g, '.*'), 'i');
  const drawerScope = popup.locator('.ant-drawer-body, .ant-drawer-content, .ant-drawer-content-wrapper').first();
  const libraryItem = drawerScope.getByText(exactPattern, { exact: true }).first();
  const relaxedItem = drawerScope.getByText(relaxedPattern).first();
  let visibleLibraryItem = null;
  for (let attempt = 0; attempt < 12; attempt += 1) {
    try {
      await libraryItem.waitFor({ state: 'visible', timeout: 500 });
      visibleLibraryItem = libraryItem;
      break;
    } catch {
      try {
        await relaxedItem.waitFor({ state: 'visible', timeout: 500 });
        visibleLibraryItem = relaxedItem;
        break;
      } catch {
        const drawerBody = await firstVisibleLocator(popup, [
          '.ant-drawer-body',
          '.ant-drawer-content',
          '.ant-drawer-content-wrapper',
        ]);
        if (drawerBody) {
          await drawerBody.evaluate((element) => {
            element.scrollBy({ top: 560, behavior: 'instant' });
          }).catch(() => {});
        } else {
          await popup.mouse.wheel(0, 560).catch(() => {});
        }
        await safeWait(popup, 400);
      }
    }
  }
  if (!visibleLibraryItem) {
    throw new Error(`Could not locate BrowserAct library action ${actionLabel}`);
  }
  try {
    await visibleLibraryItem.click({ timeout: 10000, force: true });
  } catch {
    const fallbackTarget = drawerScope.getByText(relaxedPattern).first();
    await fallbackTarget.click({ timeout: 10000, force: true });
  }
  await safeWait(popup, 1500);
  await snap(popup, `04-after-insert-${String(stepIndex).padStart(2, '0')}-${slugify(actionLabel)}`);

  let matched = false;
  for (let attempt = 0; attempt < 30; attempt += 1) {
    const labels = await listCurrentNodeLabels(popup);
    if (labels.includes(expectedLabel)) {
      matched = true;
      break;
    }
    if (labels.length > beforeLabels.length) {
      matched = true;
      break;
    }
    const text = await bodyText(popup);
    if (text.includes('Current Tab Access') || text.includes('New Tab Execution') || text.includes('URL')) {
      matched = true;
      break;
    }
    await safeWait(popup, 500);
  }
  if (!matched) {
    await snap(popup, `05-timeout-${String(stepIndex).padStart(2, '0')}-${slugify(actionLabel)}`);
    throw new Error(`Timed out waiting for ${expectedLabel}`);
  }

  await snap(popup, `10-materialize-${String(stepIndex).padStart(2, '0')}-${slugify(actionLabel)}`);
  return await listCurrentNodeLabels(popup);
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1024 } });
    let page = await context.newPage();
    let builderSurface = null;
    await ensureLogin(page);
    await maybeDismiss(page);
    await maybeCloseCreateModal(page);
    await snap(page, '01-list');
    const exists = await workflowExists(page);
    if (!exists) {
      const nameAlreadyVisible = await firstVisibleLocator(page, [
        'input[name="name"]',
        'input[placeholder*="workflow" i]',
      ]);
      if (!nameAlreadyVisible) {
        const preferredClicked = await clickPreferredCreateButton(page);
        if (!preferredClicked) {
          await clickFirst(
            page,
            [
              'button[data-sentry-component="ButtonCreate"]',
              'button[data-sentry-element="AppButton"]:has-text("Create")',
              'button:has-text("Create workflow")',
              'button:has-text("New workflow")',
              'a:has-text("Create workflow")',
              'a:has-text("New workflow")',
              '[data-testid="create-workflow"]',
              'button:has-text("Create")',
              'text=/Custom Workflow/i',
            ],
            'create workflow'
          );
          await safeWait(page, 2500);
        }
      }
      page = await reviveDashboardPage(context, page);
      const createSurfaceReady = await waitForCreateSurface(page, 45000).catch(() => false);
      if (!createSurfaceReady && !(await workflowExists(page))) {
        await snap(page, '01a-create-surface-missing');
        throw new Error(`Create workflow surface did not appear for ${resolvedWorkflowName}`);
      }
      await fillFirst(
        page,
        [
          'input[name="name"]',
          'input[placeholder*="workflow" i]',
          'input',
        ],
        resolvedWorkflowName,
        'workflow name'
      );
      if (workflowDescription) {
        const descriptionLocator = await firstVisibleLocator(page, [
          'textarea[name="description"]',
          'textarea',
          'input[name="description"]',
        ]);
        if (descriptionLocator) {
          await descriptionLocator.fill(workflowDescription, { timeout: 10000 });
        }
      }
      await snap(page, '01a-create-metadata');
      const createCurrentUrl = String(page.url() || '');
      const createPopupPromise = page
        .waitForEvent('popup', { timeout: 10000 })
        .then(async (popup) => {
          await popup.waitForLoadState('domcontentloaded', { timeout: 20000 }).catch(() => {});
          await safeWait(popup, 3000);
          return popup;
        })
        .catch(() => null);
      const createSameTabPromise = Promise.race([
        page
          .waitForURL((url) => {
            const value = String(url || '');
            return value !== createCurrentUrl && /\/workflow\/.+\/orchestration/i.test(value);
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
      await clickFirst(
        page,
        [
          '[role="dialog"] .ant-modal-footer button.ant-btn-primary',
          '.ant-modal .ant-modal-footer button.ant-btn-primary',
          '[role="dialog"] button.ant-btn-primary:has-text("Create")',
          '.ant-modal button.ant-btn-primary:has-text("Create")',
        ],
        'create workflow submit'
      ).catch(() => {});
      await page.waitForLoadState('domcontentloaded', { timeout: 120000 }).catch(() => {});
      builderSurface = await Promise.race([
        createPopupPromise,
        createSameTabPromise,
        safeWait(page, 12000).then(() => null),
      ]);
      if (builderSurface) {
        await snap(builderSurface, '01b-created');
      } else {
        page = await reviveDashboardPage(context, page);
        await snap(page, '01b-created');
      }
    }
    page = await reviveDashboardPage(context, page);
    let workflowId = '';
    if (builderSurface) {
      const builderUrl = String(builderSurface.url() || '');
      const match = builderUrl.match(/\/workflow\/([^/]+)\/orchestration/i);
      if (match && match[1]) {
        workflowId = match[1];
      }
    }
    if (!workflowId) {
      await ensureWorkflowList(page);
      const workflowCard = await locateCard(page);
      workflowId = await extractWorkflowIdFromCard(workflowCard);
    }
    let popup = builderSurface || (await openBuilderSurface(page));
    await snap(popup, '02-builder-open');

    const materializedNodes = packet.nodes.filter((node) => Boolean(actionLabelForPacketNode(node)));
    const desiredActions = materializedNodes.map(actionLabelForPacketNode).filter(Boolean);
    const desiredLabels = [];
    const desiredCounts = new Map();
    for (const actionLabel of desiredActions) {
      const nextCount = (desiredCounts.get(actionLabel) || 0) + 1;
      desiredCounts.set(actionLabel, nextCount);
      desiredLabels.push(`${actionLabel}_${nextCount}`);
    }

    let labels = await listCurrentNodeLabels(popup);
    for (let index = 0; index < materializedNodes.length && index < desiredLabels.length; index += 1) {
      const expectedLabel = desiredLabels[index];
      const actionLabel = desiredActions[index];
      const packetNode = materializedNodes[index];
      let attempt = 0;
      while (true) {
        try {
          if (!popup || popup.isClosed()) {
            popup = await openWorkflowSurfaceById(context, workflowId);
          }
          let labelPresent =
            labels.includes(expectedLabel) ||
            (await workflowHasEquivalentLabel(popup, expectedLabel));
          if (!labelPresent) {
            labels = await addActionNode(popup, actionLabel, expectedLabel, index + 1);
            labelPresent =
              labels.includes(expectedLabel) ||
              (await workflowHasEquivalentLabel(popup, expectedLabel));
          }
          if (!labelPresent) {
            throw new Error(`Missing expected BrowserAct node ${expectedLabel}`);
          }
          await configureNodeInline(popup, expectedLabel, packetNode, index + 1);
          labels = await listCurrentNodeLabels(popup);
          break;
        } catch (error) {
          const message = String(error && error.message ? error.message : error);
          if (attempt < 1 && /Target page, context or browser has been closed/i.test(message)) {
            popup = await openWorkflowSurfaceById(context, workflowId);
            labels = await listCurrentNodeLabels(popup);
            attempt += 1;
            continue;
          }
          throw error;
        }
      }
    }

    let published = false;
    try {
      const publishButton = popup.locator('button').filter({ hasText: /^Publish$/ }).first();
      await publishButton.waitFor({ state: 'visible', timeout: 5000 });
      await publishButton.click({ timeout: 10000 });
      await safeWait(popup, 1500);
      const publishVersionButton = popup.locator('button').filter({ hasText: /^Publish as New Version$/ }).first();
      try {
        await publishVersionButton.waitFor({ state: 'visible', timeout: 5000 });
        await publishVersionButton.click({ timeout: 10000 });
        await safeWait(popup, 1500);
        await maybeConfirmPublish(popup);
        await safeWait(popup, 3000);
        published = true;
      } catch {
        // keep draft if publish confirmation is unavailable
      }
    } catch {
      // keep draft if publish flow needs extra manual confirmation later
    }

    await snap(popup, '11-builder-final');
    const result = {
      status: 'ok',
      workflow_id: workflowId,
      workflow_name: resolvedWorkflowName,
      popup_url: popup.url(),
      published,
      labels: await listCurrentNodeLabels(popup),
      state_dir: stateDir,
    };
    fs.writeFileSync(path.join(stateDir, 'result.json'), JSON.stringify(result, null, 2), 'utf8');
    console.log(JSON.stringify(result));
  } catch (error) {
    const detail = {
      status: 'error',
      message: String(error && error.message ? error.message : error),
      stack: String(error && error.stack ? error.stack : ''),
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
