'use strict';

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const stateDir = '/docker/fleet/state/browseract_bootstrap/live_probe';
const username = String(process.env.BROWSERACT_USERNAME || '').trim();
const password = String(process.env.BROWSERACT_PASSWORD || '').trim();
const workflowName = String(process.env.BROWSERACT_WORKFLOW_NAME || 'browseract_architect').trim() || 'browseract_architect';

if (!username || !password) {
  throw new Error('BROWSERACT_USERNAME and BROWSERACT_PASSWORD are required');
}

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

async function dumpCardDetails(card) {
  return await card.evaluate((node) => {
    const text = (node.textContent || '').replace(/\s+/g, ' ').trim();
    return {
      text,
      html: node.outerHTML.slice(0, 8000),
    };
  });
}

async function pageState(page) {
  const body = await bodyText(page);
  return {
    url: page.url(),
    title: await page.title(),
    body_excerpt: body.slice(0, 1200),
    has_publish: /publish/i.test(body),
    has_node_word: /\bnode\b/i.test(body),
    has_workflow_list: /AI Workflows/i.test(body),
  };
}


async function collectNodeDetails(page, labelText) {
  return await page.evaluate((targetLabel) => {
    const nodes = Array.from(document.querySelectorAll('[data-testid^="rf__node-"]'));
    const node = nodes.find((candidate) => (candidate.textContent || '').includes(targetLabel));
    if (!node) {
      return null;
    }
    const inputs = Array.from(node.querySelectorAll('input, textarea, select')).map((el) => ({
      tag: el.tagName.toLowerCase(),
      type: el.getAttribute('type') || '',
      name: el.getAttribute('name') || '',
      placeholder: el.getAttribute('placeholder') || '',
      value: el.value || '',
    }));
    const buttons = Array.from(node.querySelectorAll('button')).map((el) => (el.textContent || '').replace(/\s+/g, ' ').trim()).filter(Boolean);
    return {
      text: (node.textContent || '').replace(/\s+/g, ' ').trim(),
      inputs,
      buttons,
      testid: node.getAttribute('data-testid') || '',
      className: node.className || '',
    };
  }, labelText);
}
async function popupStateWithAddNode(popup, snapPrefix) {
  const state = await pageState(popup);
  const addNode = popup.locator('button[data-sentry-element="ButtonAddNode"]').first();
  let addNodeState = null;
  let addedVisitPageState = null;
  try {
    await addNode.waitFor({ state: 'visible', timeout: 10000 });
    await addNode.click({ timeout: 10000 });
    await popup.waitForTimeout(3000);
    try {
      await popup.screenshot({ path: path.join(stateDir, `${snapPrefix}-add-node.png`), fullPage: true });
      fs.writeFileSync(path.join(stateDir, `${snapPrefix}-add-node.html`), await popup.content(), 'utf8');
    } catch {
      // continue
    }
    addNodeState = await pageState(popup);
    try {
      const visitPage = popup.locator('li').filter({ has: popup.locator('h3', { hasText: /^Visit Page$/ }) }).first();
      const pane = popup.locator('.react-flow__pane').first();
      await visitPage.waitFor({ state: 'visible', timeout: 5000 });
      await pane.waitFor({ state: 'visible', timeout: 5000 });
      try {
        await visitPage.dragTo(pane, { timeout: 10000, targetPosition: { x: 260, y: 260 } });
      } catch {
        const src = await visitPage.boundingBox();
        const dst = await pane.boundingBox();
        if (!src || !dst) {
          throw new Error('drag bounding boxes unavailable');
        }
        await popup.mouse.move(src.x + src.width / 2, src.y + src.height / 2);
        await popup.mouse.down();
        await popup.mouse.move(dst.x + 260, dst.y + 260, { steps: 20 });
        await popup.mouse.up();
      }
      await popup.waitForTimeout(3000);
      try {
        await popup.screenshot({ path: path.join(stateDir, `${snapPrefix}-visit-page.png`), fullPage: true });
        fs.writeFileSync(path.join(stateDir, `${snapPrefix}-visit-page.html`), await popup.content(), 'utf8');
      } catch {
        // continue
      }
      addedVisitPageState = await pageState(popup);
      addedVisitPageState.node_details = await collectNodeDetails(popup, 'Visit Page_1');
    } catch {
      addedVisitPageState = null;
    }
  } catch {
    addNodeState = null;
  }
  return { ...state, add_node: addNodeState, visit_page_added: addedVisitPageState };
}

async function buildTargets(card) {
  const title = card.locator(`div[title="${workflowName}"]`).first();
  const buildLabel = card.locator('div').filter({ hasText: /^Build$/ }).last();
  const buildParent = buildLabel.locator('xpath=ancestor::div[contains(@class,"group/do")][1]');
  return { title, buildLabel, buildParent, card };
}

async function locateCardByTitle(page, titleText) {
  const title = page.locator(`div[title="${titleText}"]`).first();
  await title.waitFor({ state: 'visible', timeout: 15000 });
  return title.locator('xpath=ancestor::div[contains(@class,"group relative")][1]');
}

async function attemptClick(page, label, locator, snapPrefix) {
  const before = await pageState(page);
  const popupPromise = page.waitForEvent('popup', { timeout: 8000 }).catch(() => null);
  try {
    await locator.click({ timeout: 10000 });
  } catch {
    await locator.click({ timeout: 10000, force: true });
  }
  const popup = await popupPromise;
  let popupState = null;
  if (popup) {
    await popup.waitForLoadState('domcontentloaded', { timeout: 20000 }).catch(() => {});
    await popup.waitForTimeout(3000);
    popupState = await popupStateWithAddNode(popup, snapPrefix);
    try {
      await popup.screenshot({ path: path.join(stateDir, `${snapPrefix}-popup.png`), fullPage: true });
      fs.writeFileSync(path.join(stateDir, `${snapPrefix}-popup.html`), await popup.content(), 'utf8');
    } catch {
      // continue
    }
    await popup.close().catch(() => {});
  }
  await page.waitForLoadState('domcontentloaded', { timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(4000);
  await snap(page, snapPrefix);
  const after = await pageState(page);
  return { label, before, after, popup: popupState };
}

async function openListPage(browser) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1024 } });
  await ensureLogin(page);
  return page;
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await openListPage(browser);
    await snap(page, '01-list');
    const card = await locateCard(page);
    const details = await dumpCardDetails(card);
    fs.writeFileSync(path.join(stateDir, 'card.json'), JSON.stringify(details, null, 2), 'utf8');
    await card.hover({ force: true, timeout: 10000 });
    await page.waitForTimeout(1000);
    const targets = await buildTargets(card);
    const results = [];

    await snap(page, '02-hovered');
    results.push(await attemptClick(page, 'build_label', targets.buildLabel, '03-after-build-label'));
    await page.close();

    const page2 = await openListPage(browser);
    const card2 = await locateCard(page2);
    await card2.hover({ force: true, timeout: 10000 });
    await page2.waitForTimeout(1000);
    const targets2 = await buildTargets(card2);
    results.push(await attemptClick(page2, 'build_parent', targets2.buildParent, '04-after-build-parent'));
    await page2.close();

    const page3 = await openListPage(browser);
    const card3 = await locateCard(page3);
    await card3.hover({ force: true, timeout: 10000 });
    await page3.waitForTimeout(1000);
    const targets3 = await buildTargets(card3);
    results.push(await attemptClick(page3, 'title', targets3.title, '05-after-title-click'));
    await page3.close();

    const page4 = await openListPage(browser);
    const card4 = await locateCard(page4);
    await card4.hover({ force: true, timeout: 10000 });
    await page4.waitForTimeout(1000);
    results.push(await attemptClick(page4, 'card', card4, '06-after-card-click'));
    await page4.close();

    const page5 = await openListPage(browser);
    const controlCard = await locateCardByTitle(page5, 'Workflow-260312-02');
    await controlCard.hover({ force: true, timeout: 10000 });
    await page5.waitForTimeout(1000);
    const controlBuildLabel = controlCard.locator('div').filter({ hasText: /^Build$/ }).last();
    const controlBuildParent = controlBuildLabel.locator('xpath=ancestor::div[contains(@class,"group/do")][1]');
    results.push(await attemptClick(page5, 'control_build_parent', controlBuildParent, '07-after-control-build-parent'));
    await page5.close();

    const output = {
      status: 'ok',
      workflow_name: workflowName,
      attempts: results,
      state_dir: stateDir,
    };
    fs.writeFileSync(path.join(stateDir, 'result.json'), JSON.stringify(output, null, 2), 'utf8');
    console.log(JSON.stringify(output));
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
