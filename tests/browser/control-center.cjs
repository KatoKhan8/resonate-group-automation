/* Run a real, disposable Python application and browser in the same process
   namespace. No production URL, credential, provider call or live send. */
'use strict';
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const {mkdir} = require('node:fs/promises');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE_PATH || 'playwright');
const root = path.resolve(__dirname, '../..');
const output = path.join(root, 'out/browser');

async function main() {
  await mkdir(output, {recursive: true});
  // Deliberately do not forward API keys, OIDC settings or proxy variables.
  const server = spawn(process.env.PYTHON || 'python', ['-u', '-m', 'src.web', '--demo', '--port', '0'], {
    cwd: root,
    env: {PATH: process.env.PATH, LANG: 'C.UTF-8', APP_MODE: 'demo', WEB_QUIET: '1',
      REPLY_POLL_ENABLED: '0', DIGEST_SCHEDULE: 'off'},
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let browser;
  try {
    const base = await new Promise((resolve, reject) => {
      let log = '';
      const timeout = setTimeout(() => reject(new Error('Demo server did not start in 60s: ' + log)), 60000);
      server.on('error', error => {clearTimeout(timeout); reject(error);});
      server.on('exit', code => {clearTimeout(timeout); reject(new Error('Demo exited: ' + code + '\n' + log));});
      server.stderr.on('data', chunk => {log += chunk.toString();});
      server.stdout.on('data', chunk => {
        log += chunk.toString();
        const match = log.match(/http:\/\/127\.0\.0\.1:\d+/);
        if (match) {clearTimeout(timeout); resolve(match[0]);}
      });
    });
    browser = await chromium.launch({headless: true,
      ...(process.env.BROWSER_EXECUTABLE_PATH ? {executablePath: process.env.BROWSER_EXECUTABLE_PATH} : {}),
      args: ['--no-sandbox', '--disable-gpu']});
    const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => {
      if (/Content Security Policy|Refused to (execute|apply|load)/i.test(message.text())) errors.push(message.text());
    });
    async function go(url, expected = 200) {
      const response = await page.goto(base + url);
      assert.equal(response.status(), expected, url);
      return response;
    }
    async function signIn(email) {
      await go('/logout');
      await page.selectOption('#email', email);
      await Promise.all([page.waitForURL(url => !['/login', '/logout'].includes(url.pathname)), page.getByRole('button', {name: 'Sign in', exact: true}).click()]);
    }
    await signIn('admin@productive.test');
    const routes = ['/', '/upload', '/batches', '/batches/uk-digital', '/icp', '/companies', '/contacts',
      '/segments', '/campaigns/new', '/campaigns', '/outreach', '/approvals', '/replies',
      '/reporting', '/reporting/client', '/reporting/editor', '/simulator?size=500', '/timezones',
      '/settings', '/users', '/audit', '/diagnostics', '/health', '/jobs'];
    for (const route of routes) {
      const response = await go(route);
      assert.equal(response.headers()['cache-control'], 'no-store', route + ' caches tenant data');
      assert.equal(await page.locator('main#main-content').count(), 1, route);
      assert.equal(await page.getByRole('button', {name: /^(Launch|Send now|Send live)$/i}).count(), 0, route);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
      assert.equal(overflow, false, route + ' has page overflow');
    }
    console.log('PASS: 24 desktop routes');
    await go('/');
    assert.equal(await page.locator('.brand-logo').evaluate(el => el.complete && el.naturalWidth > 0), true);
    await page.screenshot({path: path.join(output, 'dashboard.png'), fullPage: true});

    // Follow server-emitted detail links rather than inventing IDs.
    for (const [route, selector] of [['/companies', 'a[href^="/companies/"]'],
      ['/contacts', 'a[href^="/contacts/"]'], ['/campaigns', 'a[href^="/campaigns/"]:not([href="/campaigns/new"])']]) {
      await go(route);
      const href = await page.locator('main ' + selector).first().getAttribute('href');
      await go(href);
    }
    await go('/contacts');
    await page.locator('[data-filter="contacts"]').fill('no-such-visible-contact');
    assert.equal(await page.locator('#contacts tbody tr:visible').count(), 0);
    assert.match(await page.locator('#contacts-count').textContent(), /^0 of/);

    console.log('PASS: detail links and table filtering');
    // Pause navigation at the form boundary to inspect the document's pending
    // state. The next GET separately proves the real server's empty response.
    await go('/companies');
    const pending = await page.locator('#company-search').evaluate(input => {
      input.value = 'pending-state';
      const form = input.form;
      form.addEventListener('submit', event => event.preventDefault(), {once: true});
      form.requestSubmit();
      return {busy: form.getAttribute('aria-busy'),
        status: document.getElementById('page-status').textContent,
        guarded: form.dataset.submitting};
    });
    assert.equal(pending.busy, 'true');
    assert.equal(pending.guarded, 'true');
    assert.match(pending.status, /Loading/);
    await go('/companies?q=pending-state');
    assert.match(await page.locator('main').textContent(), /No companies match/);
    assert.equal(await page.locator('[aria-busy="true"]').count(), 0);

    console.log('PASS: loading state and empty results');
    // Keyboard mobile drawer, focus restoration, and narrow layouts.
    await page.setViewportSize({width: 390, height: 844});
    for (const route of ['/', '/companies', '/contacts', '/campaigns/new', '/upload', '/reporting/client', '/settings']) {
      await go(route);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
      if (overflow) console.log('Mobile overflow', route, await page.evaluate(() => Array.from(document.querySelectorAll('main *')).filter(el => el.getBoundingClientRect().right > innerWidth + 1 && el.getBoundingClientRect().width).map(el => ({tag: el.tagName, class: el.className, width: Math.round(el.getBoundingClientRect().width)})).slice(0, 12)));
      assert.equal(overflow, false, 'mobile ' + route);
    }
    await go('/');
    await page.getByRole('button', {name: 'Menu', exact: true}).click();
    assert.equal(await page.locator('#nav-toggle').getAttribute('aria-expanded'), 'true');
    assert.equal(await page.locator('.main').evaluate(el => el.inert), true);
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('#nav-toggle').evaluate(el => el === document.activeElement), true);
    await page.screenshot({path: path.join(output, 'mobile.png'), fullPage: false});
    await page.setViewportSize({width: 1440, height: 1000});

    console.log('PASS: mobile routes and keyboard drawer');
    // A file is previewed, explicitly committed, then visible in its real batch.
    await go('/upload');
    await page.locator('input[name="batch"]').fill('browser-intake');
    await page.locator('input[type="file"]').setInputFiles({name: 'companies.csv', mimeType: 'text/csv',
      buffer: Buffer.from('company,domain\nBrowser Fixture,browser-fixture.test\n')});
    assert.match(await page.locator('#upload-filename').textContent(), /companies.csv/);
    await Promise.all([page.waitForNavigation(), page.locator('main button[type="submit"]').first().click()]);
    assert.equal(await page.locator('form[action="/upload/commit"]').count(), 1);
    await Promise.all([page.waitForNavigation(), page.locator('form[action="/upload/commit"] button').click()]);
    await go('/companies?batch=browser-intake');
    assert.match(await page.locator('main').textContent(), /Browser Fixture/);

    await signIn('client@productive.test');
    await go('/reporting/client');
    assert.equal(await page.locator('a[href="/diagnostics"]').count(), 0);
    await go('/companies', 403);
    assert.match(await page.getByRole('alert').textContent(), /Permission denied/);
    assert.equal(errors.length, 0, errors.join('\n'));
    await context.close();

    // Core native forms and workspace navigation work with scripting disabled.
    const plain = await browser.newContext({javaScriptEnabled: false, viewport: {width: 390, height: 844}});
    const nojs = await plain.newPage();
    await nojs.goto(base + '/login');
    await nojs.selectOption('#email', 'ops@productive.test');
    await Promise.all([nojs.waitForURL(url => !['/login', '/logout'].includes(url.pathname)), nojs.getByRole('button', {name: 'Sign in', exact: true}).click()]);
    assert.equal(await nojs.locator('.side').isVisible(), true);
    assert.equal(await nojs.getByRole('button', {name: 'Switch', exact: true}).isVisible(), true);
    await plain.close();
    console.log(`PASS: ${routes.length} screens, details, CSP, assets, filters, loading, mobile keyboard, upload/commit, client RBAC and no-JS navigation.`);
    console.log('Screenshots: out/browser/dashboard.png, out/browser/mobile.png');
  } finally {
    if (browser) await browser.close();
    server.kill('SIGTERM');
    await new Promise(resolve => server.exitCode !== null ? resolve() : server.once('exit', resolve));
  }
}
main().catch(error => {console.error(error); process.exitCode = 1;});
