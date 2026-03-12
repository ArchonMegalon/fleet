'use strict';

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const stateDir = '/docker/fleet/state/browseract_bootstrap/live';
const packetPath = '/docker/fleet/state/browseract_bootstrap/browseract_architect.packet.json';
const username = String(process.env.BROWSERACT_USERNAME || '').trim();
const password = String(process.env.BROWSERACT_PASSWORD || '').trim();

if (!username || !password) {
  throw new Error('BROWSERACT_USERNAME and BROWSERACT_PASSWORD are required');
}

if (!fs.existsSync(packetPath)) {
  throw new Error(`Missing packet: ${packetPath}`);
}

const packet = JSON.parse(fs.readFileSync(packetPath, 'utf8'));
const workflowName = String(packet.workflow_name || 'browseract_architect').trim() || 'browseract_architect';
const description = String(packet.description || '').trim();

fs.mkdirSync(stateDir, { recursive: true });

async function snap(page, name) {
  const png = path.join(stateDir, `${name}.png`);
  const html = path.join(stateDir, `${name}.html`);
  await page.screenshot({ path: png, fullPage: true });
  fs.writeFileSync(html, await page.content(), 'utf8');
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
    await page.waitForTimeout(1000);
    return true;
  } catch {
    return false;
  }
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
    await page.waitForTimeout(1500);
  }
  return false;
}

async function maybeOpenBuilder(page, workflowName) {
  try {
    const title = page.locator(`div[title="${workflowName}"]`).first();
    await title.waitFor({ state: 'visible', timeout: 8000 });
    const card = title.locator('xpath=ancestor::div[contains(@class,"group relative")][1]');
    const buildTarget = card.getByText(/^Build$/i).first();
    await buildTarget.waitFor({ state: 'visible', timeout: 5000 });
    await buildTarget.click({ timeout: 10000 });
    await page.waitForLoadState('domcontentloaded', { timeout: 120000 }).catch(() => {});
    await page.waitForTimeout(5000);
    return true;
  } catch {
    return false;
  }
}

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

async function workflowExists(page) {
  const title = page.locator(`div[title="${workflowName}"]`).first();
  try {
    await title.waitFor({ state: 'visible', timeout: 5000 });
    return true;
  } catch {
    return false;
  }
}

async function openWorkflowBuilderPopup(page) {
  const title = page.locator(`div[title="${workflowName}"]`).first();
  await title.waitFor({ state: 'visible', timeout: 15000 });
  const card = title.locator('xpath=ancestor::div[contains(@class,"group relative")][1]');
  await card.hover({ timeout: 10000 });
  const buildLabel = card.locator('div').filter({ hasText: /^Build$/ }).last();
  await buildLabel.waitFor({ state: 'visible', timeout: 5000 });
  const popupPromise = page.waitForEvent('popup', { timeout: 10000 });
  try {
    await buildLabel.click({ timeout: 10000 });
  } catch {
    await buildLabel.click({ timeout: 10000, force: true });
  }
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

async function addActionNode(popup, actionLabel, stepIndex) {
  const beforeLabels = await listCurrentNodeLabels(popup);
  const expectedOrdinal =
    beforeLabels.filter((label) => label.toLowerCase().startsWith(actionLabel.toLowerCase())).length + 1;
  const expectedLabel = `${actionLabel}_${expectedOrdinal}`;
  const addButtons = popup.locator('button[data-sentry-element="ButtonAddNode"]');
  const addCount = await addButtons.count();
  if (addCount < 1) {
    throw new Error(`No add-node button available for ${actionLabel}`);
  }
  const addButton = addButtons.nth(addCount - 1);
  await addButton.waitFor({ state: 'visible', timeout: 10000 });
  await addButton.click({ timeout: 10000 });
  await popup.waitForTimeout(1500);

  const libraryItem = popup.locator('li').filter({ has: popup.locator('h3', { hasText: new RegExp(`^${actionLabel}$`) }) }).first();
  await libraryItem.waitFor({ state: 'visible', timeout: 10000 });
  const dropTarget = popup.locator('button[data-sentry-element="ButtonAddNode"]').last();
  await dropTarget.waitFor({ state: 'visible', timeout: 10000 });
  try {
    await libraryItem.dragTo(dropTarget, { timeout: 10000 });
  } catch {
    const src = await libraryItem.boundingBox();
    const dst = await dropTarget.boundingBox();
    if (!src || !dst) {
      throw new Error(`Could not compute drag coordinates for ${actionLabel}`);
    }
    await popup.mouse.move(src.x + src.width / 2, src.y + src.height / 2);
    await popup.mouse.down();
    await popup.mouse.move(dst.x + dst.width / 2, dst.y + dst.height / 2, { steps: 20 });
    await popup.mouse.up();
  }

  await popup.waitForFunction(
    (targetLabel) => {
      return (document.body.innerText || '').includes(targetLabel);
    },
    expectedLabel,
    { timeout: 15000 }
  );
  await popup.waitForTimeout(1500);
  await snap(popup, `10-materialize-${String(stepIndex).padStart(2, '0')}-${slugify(actionLabel)}`);
  return await listCurrentNodeLabels(popup);
}

async function materializeWorkflow(popup) {
  const desiredActions = packet.nodes.map(actionLabelForPacketNode).filter(Boolean);
  let currentLabels = await listCurrentNodeLabels(popup);
  for (let index = currentLabels.length; index < desiredActions.length; index += 1) {
    currentLabels = await addActionNode(popup, desiredActions[index], index + 1);
  }
  return currentLabels;
}

async function bodyText(page) {
  try {
    return await page.locator('body').innerText({ timeout: 3000 });
  } catch {
    return '';
  }
}

async function maybeSwitchSignupToLogin(page, snapName) {
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
  if (snapName) {
    await snap(page, snapName);
  }
  return true;
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1024 } });
  let builderPopup = null;

  try {
    await page.goto('https://app.browseract.com', { waitUntil: 'domcontentloaded', timeout: 120000 });
    await page.waitForTimeout(1500);
    await snap(page, '01-landing');

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
        await snap(page, '02-login-page');
      }
      loginNeeded = await page.locator('input[type="password"], input[name="password"]').count();
    }

    if (loginNeeded > 0 || /login|sign in|sign up/i.test(await page.title()) || /sign up/i.test(await bodyText(page))) {
      await maybeSwitchSignupToLogin(page, '03-login-form');
      await fillFirst(
        page,
        [
          '#formLogin_email',
          'input[type="email"]',
          'input[name="email"]',
          'input[autocomplete="username"]',
          'input[autocomplete="email"]',
          'input[placeholder*="email" i]',
          'input[placeholder*="mail" i]',
          'input[aria-label*="email" i]',
          'input:not([type="password"])',
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
          'input[placeholder*="password" i]',
          'input[aria-label*="password" i]',
        ],
        password,
        'password'
      );
      await snap(page, '03-filled-login');
      await clickFirst(
        page,
        [
          'form#formLogin button[type="submit"]',
          'button[type="submit"]',
          'button:has-text("Log In")',
          'button:has-text("Sign in")',
          'button:has-text("Log in")',
          'button:has-text("Continue")',
        ],
        'login submit'
      );
      await page.waitForLoadState('domcontentloaded', { timeout: 120000 }).catch(() => {});
      await page.waitForTimeout(6000);
      await page.goto('https://app.browseract.com/reception/workflow-list', {
        waitUntil: 'domcontentloaded',
        timeout: 120000,
      }).catch(() => {});
      await waitForCreateSurface(page, 45000).catch(() => false);
      await snap(page, '04-after-login');
    }

    await maybeDismiss(page);
    await maybeCloseCreateModal(page);

    const exists = await workflowExists(page);

    if (!exists) {
      const nameAlreadyVisible = await firstVisibleLocator(page, [
        'input[name="name"]',
        'input[placeholder*="workflow" i]',
      ]);
      if (!nameAlreadyVisible) {
        await clickFirst(
          page,
          [
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
        await page.waitForTimeout(2500);
      }
      await snap(page, '05-create-workflow');

      await fillFirst(
        page,
        [
          'input[name="name"]',
          'input[placeholder*="workflow" i]',
          'input',
        ],
        workflowName,
        'workflow name'
      );

      if (description) {
        const descriptionLocator = await firstVisibleLocator(page, [
          'textarea[name="description"]',
          'textarea',
          'input[name="description"]',
        ]);
        if (descriptionLocator) {
          await descriptionLocator.fill(description, { timeout: 10000 });
        }
      }

      await snap(page, '06-metadata-filled');

      try {
        await clickFirst(
          page,
          [
            '[role="dialog"] button:has-text("Create")',
            '.ant-modal button:has-text("Create")',
            'button:has-text("Create")',
          ],
          'create workflow submit'
        );
        await page.waitForLoadState('domcontentloaded', { timeout: 120000 }).catch(() => {});
        await page.waitForTimeout(4000);
        await snap(page, '07-after-create-submit');
      } catch {
        // continue if auto-submitted
      }
    }

    builderPopup = await openWorkflowBuilderPopup(page);
    await snap(builderPopup, '09-builder');
    const materializedLabels = await materializeWorkflow(builderPopup);

    let publishClicked = false;
    try {
      const publishButton = builderPopup.locator('button').filter({ hasText: /^Publish$/ }).first();
      await publishButton.waitFor({ state: 'visible', timeout: 5000 });
      await publishButton.click({ timeout: 10000 });
      await builderPopup.waitForTimeout(2500);
      publishClicked = true;
    } catch {
      // builder may autosave or require extra publish flow; keep draft evidence
    }

    await snap(builderPopup, '11-builder-final');

    const currentUrl = builderPopup ? builderPopup.url() : page.url();
    const result = {
      status: 'ok',
      workflow_name: workflowName,
      published: publishClicked,
      builder_opened: Boolean(builderPopup),
      materialized_labels: builderPopup ? await listCurrentNodeLabels(builderPopup) : [],
      current_url: currentUrl,
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
    try {
      await snap(page, '99-error');
    } catch {}
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
