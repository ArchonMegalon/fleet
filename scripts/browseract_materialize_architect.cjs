'use strict';

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const stateDir = '/docker/fleet/state/browseract_bootstrap/materialize';
const packetPath = '/docker/fleet/state/browseract_bootstrap/browseract_architect.packet.json';
const username = String(process.env.BROWSERACT_USERNAME || '').trim();
const password = String(process.env.BROWSERACT_PASSWORD || '').trim();
const workflowName = String(process.env.BROWSERACT_WORKFLOW_NAME || 'browseract_architect').trim() || 'browseract_architect';

if (!username || !password) {
  throw new Error('BROWSERACT_USERNAME and BROWSERACT_PASSWORD are required');
}

if (!fs.existsSync(packetPath)) {
  throw new Error(`Missing packet: ${packetPath}`);
}

const packet = JSON.parse(fs.readFileSync(packetPath, 'utf8'));
fs.mkdirSync(stateDir, { recursive: true });

function actionLabelForPacketNode(node) {
  switch (String(node && node.type ? node.type : '').trim()) {
    case 'visit_page':
      return 'Visit Page';
    case 'click':
      return 'Click Element';
    case 'input_text':
      return 'Input Text';
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
  const png = path.join(stateDir, `${name}.png`);
  const html = path.join(stateDir, `${name}.html`);
  await page.screenshot({ path: png, fullPage: true });
  fs.writeFileSync(html, await page.content(), 'utf8');
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
  await locator.click({ timeout: 10000 });
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
  await page.waitForTimeout(1500);
  await page.locator('#formLogin_email').waitFor({ state: 'visible', timeout: 5000 }).catch(() => {});
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
    await page.waitForTimeout(5000);
    await page.goto('https://app.browseract.com/reception/workflow-list', {
      waitUntil: 'domcontentloaded',
      timeout: 120000,
    });
    await page.waitForTimeout(2000);
  }
}

async function locateCard(page) {
  const title = page.locator(`div[title="${workflowName}"]`).first();
  await title.waitFor({ state: 'visible', timeout: 15000 });
  return title.locator('xpath=ancestor::div[contains(@class,"group relative")][1]');
}

async function openBuilderPopup(page) {
  const card = await locateCard(page);
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
        return (node.textContent || '').replace(/\s+/g, ' ').trim();
      })
      .filter(Boolean);
  });
}

function synthesizeClickDescription(node) {
  const label = String(node && node.label ? node.label : '').trim();
  const selector = String(node && node.config && node.config.selector ? node.config.selector : '').trim();
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
  const selector = String(node && node.config && node.config.selector ? node.config.selector : '').trim();
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

async function configureNodeInline(popup, expectedLabel, packetNode, stepIndex) {
  const node = popup.locator('.react-flow__node').filter({ hasText: expectedLabel }).first();
  await node.waitFor({ state: 'visible', timeout: 10000 });
  const header = node.locator('.ant-collapse-header').first();
  await header.waitFor({ state: 'visible', timeout: 5000 });
  await header.click({ timeout: 10000, force: true }).catch(() => {});
  await popup.waitForTimeout(800);

  const type = String(packetNode && packetNode.type ? packetNode.type : '').trim();
  const nodeButtons = node.locator('button');
  const buttonCount = await nodeButtons.count();
  if (buttonCount > 0) {
    await nodeButtons.last().click({ timeout: 3000, force: true }).catch(() => {});
  }
  await popup.waitForTimeout(800);

  const textareas = node.locator('textarea');
  const textboxes = node.locator('[contenteditable="true"][role="textbox"]');
  const inputs = node.locator('input.ant-input:not([maxlength="32"]), input[placeholder], textarea, [contenteditable="true"][role="textbox"]');
  appendConfigLog({
    step: stepIndex,
    expectedLabel,
    type,
    textarea_count: await textareas.count(),
    textbox_count: await textboxes.count(),
    input_count: await inputs.count(),
  });
  if (type === 'visit_page') {
    const url = String(packetNode && packetNode.config && packetNode.config.url ? packetNode.config.url : '').trim();
    if (url) {
      if (await textboxes.count()) {
        const textbox = textboxes.first();
        await textbox.waitFor({ state: 'visible', timeout: 5000 });
        await textbox.fill(url, { timeout: 10000 });
        await textbox.press('Tab').catch(() => {});
      } else if (await textareas.count()) {
        await textareas.first().fill(url, { timeout: 10000 });
        await textareas.first().press('Tab').catch(() => {});
      } else {
        const urlInput = node.locator('input.ant-input:not([maxlength="32"]), input[placeholder]').first();
        await urlInput.waitFor({ state: 'visible', timeout: 5000 });
        await urlInput.fill(url, { timeout: 10000 });
        await urlInput.press('Tab').catch(() => {});
      }
    }
  } else if (type === 'click') {
    const textboxCount = await textboxes.count();
    if (textboxCount > 0) {
      await textboxes.first().fill(synthesizeClickDescription(packetNode), { timeout: 10000 });
      await textboxes.first().press('Tab').catch(() => {});
    } else if (await textareas.count() > 0) {
      await textareas.first().fill(synthesizeClickDescription(packetNode), { timeout: 10000 });
      await textareas.first().press('Tab').catch(() => {});
    }
  } else if (type === 'input_text') {
    const textboxCount = await textboxes.count();
    const count = await textareas.count();
    if (textboxCount > 0) {
      await textboxes.nth(0).fill(synthesizeInputFieldDescription(packetNode), { timeout: 10000 });
      await textboxes.nth(0).press('Tab').catch(() => {});
    } else if (count > 0) {
      await textareas.nth(0).fill(synthesizeInputFieldDescription(packetNode), { timeout: 10000 });
      await textareas.nth(0).press('Tab').catch(() => {});
    }
    if (textboxCount > 1) {
      await textboxes.nth(1).fill(synthesizeInputValue(packetNode), { timeout: 10000 });
      await textboxes.nth(1).press('Tab').catch(() => {});
    } else if (count > 1) {
      await textareas.nth(1).fill(synthesizeInputValue(packetNode), { timeout: 10000 });
      await textareas.nth(1).press('Tab').catch(() => {});
    }
  } else if (type === 'repeat') {
    const textboxCount = await textboxes.count();
    if (textboxCount > 0) {
      await textboxes.first().fill(synthesizeLoopDescription(packetNode), { timeout: 10000 });
      await textboxes.first().press('Tab').catch(() => {});
    } else if (await textareas.count() > 0) {
      await textareas.first().fill(synthesizeLoopDescription(packetNode), { timeout: 10000 });
      await textareas.first().press('Tab').catch(() => {});
    }
  }

  await popup.waitForTimeout(1000);
  await snap(popup, `06-configure-${String(stepIndex).padStart(2, '0')}-${slugify(expectedLabel)}`);
}

async function addActionNode(popup, actionLabel, stepIndex) {
  const beforeLabels = await listCurrentNodeLabels(popup);
  const expectedOrdinal =
    beforeLabels.filter((label) => label.toLowerCase().startsWith(actionLabel.toLowerCase())).length + 1;
  const expectedLabel = `${actionLabel}_${expectedOrdinal}`;

  const addButton = popup.locator('button[data-sentry-element="ButtonAddNode"]').last();
  await addButton.waitFor({ state: 'visible', timeout: 10000 });
  await addButton.click({ timeout: 10000 });
  await popup.waitForTimeout(1500);
  await snap(popup, `03-library-${String(stepIndex).padStart(2, '0')}-${slugify(actionLabel)}`);

  const libraryItem = popup.locator('li').filter({ has: popup.locator('h3', { hasText: new RegExp(`^${actionLabel}$`) }) }).first();
  await libraryItem.waitFor({ state: 'visible', timeout: 10000 });
  try {
    await libraryItem.click({ timeout: 10000 });
  } catch {
    await libraryItem.locator('h3').filter({ hasText: new RegExp(`^${actionLabel}$`) }).first().click({ timeout: 10000, force: true });
  }
  await popup.waitForTimeout(1500);
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
    await popup.waitForTimeout(500);
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
    const page = await browser.newPage({ viewport: { width: 1440, height: 1024 } });
    await ensureLogin(page);
    await snap(page, '01-list');
    const popup = await openBuilderPopup(page);
    await snap(popup, '02-builder-open');

    const desiredActions = packet.nodes.map(actionLabelForPacketNode).filter(Boolean);
    let labels = await listCurrentNodeLabels(popup);
    for (let index = labels.length; index < desiredActions.length; index += 1) {
      labels = await addActionNode(popup, desiredActions[index], index + 1);
    }

    labels = await listCurrentNodeLabels(popup);
    for (let index = 0; index < packet.nodes.length && index < labels.length; index += 1) {
      await configureNodeInline(popup, labels[index], packet.nodes[index], index + 1);
    }

    let published = false;
    try {
      const publishButton = popup.locator('button').filter({ hasText: /^Publish$/ }).first();
      await publishButton.waitFor({ state: 'visible', timeout: 5000 });
      await publishButton.click({ timeout: 10000 });
      await popup.waitForTimeout(2500);
      published = true;
    } catch {
      // keep draft if publish flow needs extra manual confirmation later
    }

    await snap(popup, '11-builder-final');
    const result = {
      status: 'ok',
      workflow_name: workflowName,
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
