// Front-end checks for the static site in docs/. Run with: npm run check:ui
//
// What it does
//   1. Serves docs/ on a random local port and opens it in a Chromium-based browser (Edge or Chrome).
//   2. Runs axe-core on every tab at 1440x900 and 390x844, with and without prefers-reduced-motion.
//   3. Checks the keyboard pattern of the tab strip, marker names on the map, the site list, input
//      validation, solver status and cancel, result labels, chart text alternatives, reduced motion,
//      and that the Overview figures still equal the committed solver output.
//
// It needs network access, because Leaflet, Chart.js and the map tiles load from public hosts.
// Set CHROME_PATH to the browser executable if it is not in a standard location.
// It changes no file in the repository. Exit code 0 means every check passed.
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import net from 'node:net';
import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import puppeteer from 'puppeteer-core';

const require = createRequire(import.meta.url);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'docs');
const axeSource = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');
const TABS = ['overview', 'map', 'optimise', 'scenarios', 'insights', 'evaluation', 'reports'];

function findBrowser() {
  const c = [process.env.CHROME_PATH, 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', 'C:/Program Files/Microsoft/Edge/Application/msedge.exe', 'C:/Program Files/Google/Chrome/Application/chrome.exe', '/usr/bin/google-chrome', '/usr/bin/chromium', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'];
  const hit = c.find((p) => p && fs.existsSync(p));
  if (!hit) throw new Error('No browser found. Set CHROME_PATH to a Chrome or Edge executable.');
  return hit;
}

const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.wasm': 'application/wasm', '.pdf': 'application/pdf' };
function serve() {
  const server = http.createServer((req, res) => {
    const p = path.join(root, decodeURIComponent(new URL(req.url, 'http://x').pathname));
    if (!p.startsWith(root) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) {
      const idx = path.join(root, 'index.html');
      if (req.url === '/' || req.url.startsWith('/?')) { res.writeHead(200, { 'content-type': 'text/html' }); return res.end(fs.readFileSync(idx)); }
      res.writeHead(404); return res.end('not found');
    }
    res.writeHead(200, { 'content-type': MIME[path.extname(p)] || 'application/octet-stream' });
    res.end(fs.readFileSync(p));
  });
  return new Promise((ok) => server.listen(0, '127.0.0.1', () => ok(server)));
}

// puppeteer.launch can hand off to an already running Edge and exit, so start the browser directly with its own profile.
async function launchBrowser() {
  const port = await new Promise((ok) => { const s = net.createServer(); s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => ok(p)); }); });
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'kasco-ui-'));
  const proc = spawn(findBrowser(), ['--headless=new', `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, '--no-first-run', '--no-default-browser-check', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
  let browser;
  for (let i = 0; i < 60 && !browser; i++) {
    try { browser = await puppeteer.connect({ browserURL: `http://127.0.0.1:${port}`, defaultViewport: null, protocolTimeout: 60000 }); } catch { await sleep(500); }
  }
  if (!browser) { proc.kill(); throw new Error('Could not connect to the browser.'); }
  const close = async () => { try { await browser.close(); } catch { /* already closed */ } proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* profile still locked, the OS temp cleaner removes it */ } };
  return { browser, close };
}

const results = [];
function check(name, pass, detail = '') {
  results.push({ name, pass: !!pass, detail });
  console.log(`${pass ? 'PASS' : 'FAIL'}  ${name}${detail && !pass ? `  [${detail}]` : ''}`);
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
// A DOM-level press: focus the control and fire its click. puppeteer's own click waits for a rendered frame, which a headless page does not always deliver.
const press = (page, sel) => page.evaluate((q) => { const e = document.querySelector(q); e.focus(); e.click(); }, sel);

async function openPage(browser, base, vp, reduce) {
  const page = await browser.newPage();
  await page.bringToFront(); // a background tab gets no frames, which stalls clicks that wait for visibility
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.setViewport(vp);
  await page.emulateMediaFeatures([{ name: 'prefers-reduced-motion', value: reduce ? 'reduce' : 'no-preference' }]);
  await page.goto(base, { waitUntil: 'load' });
  await page.waitForSelector('#overview .tiles', { timeout: 60000 });
  return { page, errors };
}

async function openTab(page, id, ms) {
  await page.evaluate((t) => document.querySelector(`#tab-${t}`).click(), id);
  await sleep(ms || (id === 'map' ? 2500 : 700));
}

async function axeAll(browser, base) {
  for (const vp of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    for (const reduce of [false, true]) {
      const { page, errors } = await openPage(browser, base, vp, reduce);
      await page.evaluate(axeSource);
      const label = `${vp.width}x${vp.height}${reduce ? ' reduced-motion' : ''}`;
      for (const t of TABS) {
        await openTab(page, t);
        const v = await page.evaluate(async () => (await axe.run(document, { resultTypes: ['violations'] })).violations.map((x) => `${x.id} (${x.impact}) x${x.nodes.length}`));
        check(`axe ${label} ${t}`, v.length === 0, v.join('; '));
      }
      const m = await page.evaluate(() => ({ s: document.documentElement.scrollWidth, w: window.innerWidth }));
      check(`no horizontal page scroll ${label}`, m.s <= m.w, `${m.s} > ${m.w}`);
      check(`no script errors ${label}`, errors.length === 0, errors.join('; '));
      await page.close();
    }
  }
}

async function behaviour(browser, base) {
  const { page, errors } = await openPage(browser, base, { width: 1440, height: 900 }, false);
  const data = JSON.parse(fs.readFileSync(path.join(root, 'data', 'official_base.json'), 'utf8'));

  // Figures still equal the committed solver output
  const tile = await page.$eval('#overview .tile b', (e) => e.textContent);
  const want = `USD ${data.objective.toLocaleString('en-GB', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}M`;
  check('Overview annual cost equals the committed solver output', tile === want, `${tile} vs ${want}`);

  // Landmarks and skip link
  check('skip link and main landmark', await page.evaluate(() => !!document.querySelector('a.skip[href="#main"]') && !!document.querySelector('main#main')));

  // Tab strip
  const tabs = await page.evaluate(() => {
    const b = [...document.querySelectorAll('#tabs [role=tab]')];
    return { n: b.length, controls: b.every((x) => { const p = document.getElementById(x.getAttribute('aria-controls')); return p && p.getAttribute('role') === 'tabpanel' && p.getAttribute('aria-labelledby') === x.id; }), roving: b.filter((x) => x.tabIndex === 0).length === 1 };
  });
  check('seven tabs wired to tabpanels with one tab stop', tabs.n === 7 && tabs.controls && tabs.roving, JSON.stringify(tabs));
  await page.focus('#tab-overview');
  await page.keyboard.press('ArrowRight');
  const afterArrow = await page.evaluate(() => ({ f: document.activeElement.id, sel: document.querySelector('#tabs [aria-selected=true]').id }));
  check('ArrowRight moves focus without opening the tab', afterArrow.f === 'tab-map' && afterArrow.sel === 'tab-overview', JSON.stringify(afterArrow));
  await page.keyboard.press('End');
  await page.keyboard.press('Enter');
  await sleep(500);
  const afterEnter = await page.evaluate(() => ({ sel: document.querySelector('#tabs [aria-selected=true]').id, hash: location.hash }));
  check('End then Enter opens Reports and records the hash', afterEnter.sel === 'tab-reports' && afterEnter.hash === '#reports', JSON.stringify(afterEnter));

  // Map: marker names, site list, details panel
  await openTab(page, 'map');
  const unnamed = await page.evaluate(() => [...document.querySelectorAll('#map1 .leaflet-marker-icon[role=button]')].filter((m) => !(m.title || m.getAttribute('aria-label'))).length);
  check('every focusable map marker has a name', unnamed === 0, `${unnamed} unnamed`);
  await press(page, '#siteList button.sort[data-k="cap"]');
  const sorted = await page.evaluate(() => document.querySelector('#siteList th[aria-sort=ascending] button').dataset.k + ':' + document.activeElement.dataset.k);
  check('site list sorts and keeps focus on the sort button', sorted === 'cap:cap', sorted);
  await page.select('#siteRole', 'Refinery');
  const refRows = await page.evaluate(() => document.querySelectorAll('#siteList tbody tr').length);
  check('site list filters by role', refRows === data.refineries.length, `${refRows} vs ${data.refineries.length}`);
  await press(page, '#siteList tbody button.pick-row');
  await sleep(600);
  const sel = await page.evaluate(() => ({ detail: document.querySelector('#selDetail').textContent, popup: !!document.querySelector('#map1 .leaflet-popup'), cur: document.querySelectorAll('#siteList tr[aria-current=true]').length }));
  check('choosing a list row shows the details panel, opens the popup and marks the row', /Refinery/.test(sel.detail) && sel.popup && sel.cur === 1, JSON.stringify(sel).slice(0, 200));

  await page.evaluate(() => { document.querySelector('#siteRole').value = 'all'; document.querySelector('#siteRole').dispatchEvent(new Event('change')); });
  await page.focus('#map1 .leaflet-marker-icon[title^="Airport"]');
  await page.keyboard.press('Enter');
  await sleep(500);
  const kb = await page.evaluate(() => ({ detail: document.querySelector('#selDetail').textContent, popup: !!document.querySelector('#map1 .leaflet-popup') }));
  check('Enter on a focused map marker opens its popup and fills the details panel', /Airport/.test(kb.detail) && kb.popup, JSON.stringify(kb).slice(0, 200));
  await page.keyboard.press('Escape');
  await sleep(300);
  check('Escape closes the popup of a focused map marker', !(await page.evaluate(() => !!document.querySelector('#map1 .leaflet-popup'))));

  // Result labels
  await openTab(page, 'scenarios');
  const ev = await page.evaluate(() => [...document.querySelectorAll('#scenarios table tr')].map((r) => r.textContent).filter((t) => /Field depots/.test(t)).join(' '));
  check('scenario table labels the field-depot design as a heuristic', /Heuristic, no optimality proof/.test(ev), ev.slice(0, 160));
  const cmp = await page.evaluate(() => { document.querySelector('#cmpPick').value = 'field_depots'; document.querySelector('#cmpPick').dispatchEvent(new Event('change')); return document.querySelector('.cmpnote') ? document.querySelector('.cmpnote').textContent : ''; });
  check('side by side warns when a heuristic is compared', /heuristic/i.test(cmp), cmp);

  // Charts
  await openTab(page, 'evaluation');
  const charts = await page.evaluate(() => [...document.querySelectorAll('canvas')].map((c) => ({ role: c.getAttribute('role'), label: (c.getAttribute('aria-label') || '').length })));
  check('every chart has a text alternative', charts.length >= 4 && charts.every((c) => c.role === 'img' && c.label > 20), JSON.stringify(charts));

  // Configuration form, validation, solver status and cancel
  await openTab(page, 'optimise');
  await page.$eval('#f_yield_saf', (e) => { e.value = '0'; e.dispatchEvent(new Event('input', { bubbles: true })); });
  await press(page, '#run');
  const bad = await page.evaluate(() => ({ inv: document.querySelector('#f_yield_saf').getAttribute('aria-invalid'), msg: document.querySelector('#f_yield_saf_m').textContent, st: document.querySelector('#runState').textContent, focus: document.activeElement.id, runs: Object.keys(state.sols).filter((k) => k.startsWith('custom')).length }));
  check('invalid input blocks the run, names the field and moves focus to it', bad.inv === 'true' && bad.msg.length > 0 && /Fix 1 input/.test(bad.st) && bad.focus === 'f_yield_saf' && bad.runs === 0, JSON.stringify(bad));
  await page.$eval('#f_yield_saf', (e) => { e.value = '0.1'; e.dispatchEvent(new Event('input', { bubbles: true })); });
  const scr = await page.$eval('#screen', (e) => e.className + '|' + e.textContent.slice(0, 60));
  check('mass-balance screen fails for a yield that cannot meet demand', /fail/.test(scr), scr);
  await press(page, '#reset');
  const reset = await page.evaluate(() => ({ y: document.querySelector('#f_yield_saf').value, chg: document.querySelector('#chgState').textContent }));
  check('reset restores the official inputs', reset.y === '0.2' && /All inputs match/.test(reset.chg), JSON.stringify(reset));
  await page.$eval('#f_time_limit_s', (e) => { e.value = '10'; e.dispatchEvent(new Event('input', { bubbles: true })); });
  await press(page, '#run');
  await sleep(700);
  const live = await page.evaluate(() => ({ cancelShown: !document.querySelector('#cancel').hidden, disabled: document.querySelector('#run').disabled, busy: document.querySelector('#runResult').getAttribute('aria-busy') }));
  check('while solving: cancel shown, run disabled, result region busy', live.cancelShown && live.disabled && live.busy === 'true', JSON.stringify(live));
  await press(page, '#cancel');
  await sleep(500);
  const canc = await page.evaluate(() => ({ st: document.querySelector('#runState').textContent, ok: !document.querySelector('#run').disabled, runs: Object.keys(state.sols).filter((k) => k.startsWith('custom')).length }));
  check('cancel stops the run, adds no result and re-enables Run', /cancelled/.test(canc.st) && canc.ok && canc.runs === 0, JSON.stringify(canc));
  await page.$eval('#f_time_limit_s', (e) => { e.value = '2'; e.dispatchEvent(new Event('input', { bubbles: true })); });
  await press(page, '#run');
  await page.waitForFunction(() => /Finished|stopped/.test(document.querySelector('#runState').textContent), { timeout: 60000, polling: 250 }).catch(() => {});
  const done = await page.evaluate(() => ({ card: document.querySelector('#runState').textContent + ' | ' + document.querySelector('#runResult').textContent, runs: Object.keys(state.sols).filter((k) => k.startsWith('custom')).length }));
  check('a short real solve returns a labelled solver result', done.runs === 1 && /Solver result/.test(done.card) && /(Feasible within a proven gap|Exact within target)/.test(done.card), done.card.slice(0, 160));

  // Decision support and assistant provenance
  await openTab(page, 'insights');
  check('Decision support is labelled rule-based', await page.evaluate(() => /Rule-based recommendation/.test(document.querySelector('#insights h2').textContent)));
  await press(page, '#gOpen');
  const gp = await page.evaluate(() => ({ role: document.querySelector('#gPanel').getAttribute('role'), tag: /not verified/i.test(document.querySelector('#gPanel').textContent), focus: document.activeElement.id }));
  check('analyst panel is a labelled dialog, says not verified and takes focus', gp.role === 'dialog' && gp.tag && gp.focus === 'gKey', JSON.stringify(gp));
  await page.evaluate(axeSource);
  const dv = await page.evaluate(async () => (await axe.run(document, { resultTypes: ['violations'] })).violations.map((x) => `${x.id} (${x.impact}) x${x.nodes.length}`));
  check('axe with the analyst panel open', dv.length === 0, dv.join('; '));
  await page.keyboard.press('Escape');
  const esc = await page.evaluate(() => ({ hidden: document.querySelector('#gPanel').hidden, focus: document.activeElement.id }));
  check('Escape closes the analyst panel and returns focus', esc.hidden && esc.focus === 'gOpen', JSON.stringify(esc));
  check('no script errors in the behaviour run', errors.length === 0, errors.join('; '));

  // Every committed scenario renders on every data tab without errors, including the infeasible ones
  const before = errors.length;
  const keys = JSON.parse(fs.readFileSync(path.join(root, 'data', 'index.json'), 'utf8')).map((x) => x.key);
  for (const k of keys) {
    await page.evaluate((key) => { const sel = document.querySelector('#scenario'); sel.value = key; sel.dispatchEvent(new Event('change')); }, k);
    for (const t of ['overview', 'map', 'scenarios', 'evaluation']) await openTab(page, t, 300);
  }
  check(`all ${keys.length} committed scenarios render on four tabs without script errors`, errors.length === before, errors.slice(before).join('; '));
  await page.close();

  // Reduced motion reaches Chart.js
  const r = await openPage(browser, base, { width: 1440, height: 900 }, true);
  await openTab(r.page, 'evaluation');
  const anim = await r.page.evaluate(() => Chart.getChart('baseChart').options.animation);
  check('prefers-reduced-motion turns chart animation off', anim === false, String(anim));
  await r.page.close();
}

const server = await serve();
const base = `http://127.0.0.1:${server.address().port}/`;
const { browser, close } = await launchBrowser();
try {
  await behaviour(browser, base);
  await axeAll(browser, base);
} finally {
  await close();
  server.close();
}
const failed = results.filter((x) => !x.pass);
console.log(`\n${results.length - failed.length} of ${results.length} checks passed.`);
process.exit(failed.length ? 1 : 0);
