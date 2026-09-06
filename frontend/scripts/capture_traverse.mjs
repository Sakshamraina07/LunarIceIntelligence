/**
 * capture_traverse.mjs — evidence shots of the two things this pass added.
 *
 *     node frontend/scripts/capture_traverse.mjs [--url http://localhost:3000]
 *
 * WHY A SCRIPT AND NOT A SCREENSHOT BY HAND
 * -----------------------------------------
 * Same reason `capture_layers.mjs` exists: a view driven by hand is a different
 * view every time, so two shots taken a week apart cannot be compared and the
 * one that looks worse is never provably the one that IS worse. This fixes the
 * window, the route, the zoom and the rover's position along the route, so a
 * later run differs only where the app differs.
 *
 * ZERO NEW DEPENDENCIES — CDP over the global WebSocket in Node 22, exactly as
 * capture_layers.mjs does it.
 *
 * Writes docs/evidence/traverse/*.png and prints what it asserted about each.
 */
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const OUT = path.join(ROOT, 'docs', 'evidence', 'traverse');
const CFG = { width: 1600, height: 940 };

const argUrl = process.argv.indexOf('--url');
const URL_BASE = argUrl > -1 ? process.argv[argUrl + 1] : 'http://localhost:3000';

const BROWSERS = [
  process.env.VERIFY_BROWSER,
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  `${process.env.LOCALAPPDATA || ''}/Google/Chrome/Application/chrome.exe`,
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
  '/usr/bin/google-chrome', '/usr/bin/chromium',
].filter(Boolean);

const log = (...a) => console.log(...a);
const fail = (m) => { console.error(`\n  capture_traverse: ${m}\n`); process.exit(2); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function launchBrowser() {
  const bin = BROWSERS.find((b) => existsSync(b));
  if (!bin) fail('no Chrome or Edge found. Set VERIFY_BROWSER=<path>.');
  const profile = mkdtempSync(path.join(tmpdir(), 'capture-traverse-'));
  const proc = spawn(bin, [
    '--headless=new', '--remote-debugging-port=0', `--user-data-dir=${profile}`,
    `--window-size=${CFG.width},${CFG.height}`, '--force-device-scale-factor=1',
    '--hide-scrollbars', '--disable-gpu', '--no-first-run',
    '--no-default-browser-check', '--disable-extensions',
    '--remote-allow-origins=*', 'about:blank',
  ], { stdio: 'ignore' });
  return { proc, profile, bin };
}

async function devtoolsUrl(profile, proc) {
  const f = path.join(profile, 'DevToolsActivePort');
  for (let i = 0; i < 200; i++) {
    if (proc.exitCode !== null) fail(`browser exited with code ${proc.exitCode}`);
    if (existsSync(f)) {
      const [port, ws] = readFileSync(f, 'utf8').trim().split('\n');
      if (port && ws) return `ws://127.0.0.1:${port}${ws}`;
    }
    await sleep(100);
  }
  fail('browser never wrote DevToolsActivePort (20 s)');
}

class CDP {
  constructor(ws) {
    this.ws = ws; this.id = 0; this.pending = new Map();
    ws.onmessage = (ev) => {
      const m = JSON.parse(typeof ev.data === 'string' ? ev.data : String(ev.data));
      if (m.id && this.pending.has(m.id)) {
        const { resolve, reject } = this.pending.get(m.id);
        this.pending.delete(m.id);
        if (m.error) reject(new Error(m.error.message)); else resolve(m.result);
      }
    };
  }
  static async connect(url) {
    const ws = new WebSocket(url);
    await new Promise((res, rej) => {
      ws.onopen = res; ws.onerror = () => rej(new Error('ws refused'));
    });
    return new CDP(ws);
  }
  send(method, params = {}, sessionId) {
    const id = ++this.id;
    this.ws.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
    return new Promise((resolve, reject) => this.pending.set(id, { resolve, reject }));
  }
}

async function main() {
  mkdirSync(OUT, { recursive: true });
  const { proc, profile, bin } = launchBrowser();
  log(`  browser: ${bin}`);
  const cdp = await CDP.connect(await devtoolsUrl(profile, proc));
  const { targetId } = await cdp.send('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await cdp.send('Target.attachToTarget', { targetId, flatten: true });
  const S = (m, p) => cdp.send(m, p, sessionId);
  await S('Page.enable');
  await S('Runtime.enable');
  await S('Emulation.setDeviceMetricsOverride',
          { width: CFG.width, height: CFG.height, deviceScaleFactor: 1, mobile: false });

  const ev = async (expr) => {
    const r = await S('Runtime.evaluate',
                      { expression: expr, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.text
      + ' :: ' + (r.exceptionDetails.exception?.description ?? ''));
    return r.result.value;
  };

  await S('Page.navigate', { url: `${URL_BASE}/#mission` });
  await sleep(9000);

  const shot = async (name) => {
    const { data } = await S('Page.captureScreenshot', { format: 'png' });
    const f = path.join(OUT, `${name}.png`);
    writeFileSync(f, Buffer.from(data, 'base64'));
    log(`  wrote ${path.relative(ROOT, f)}`);
    return f;
  };

  // ── 1. the traverse, with the rover part way along route 1 ────────────────
  //
  // Position is set through the SLIDER, not by poking state: the odometer that
  // appears in the shot is then the one the app computed, not one this script
  // asserted. A capture that set the number it photographs would be a picture
  // of its own argument.
  const odo = await ev(`(async () => {
    const pick = (n) => [...document.querySelectorAll('.mc-trv-item')]
      .find(x => x.textContent.includes('Site ' + n));
    pick(1).click();
    await new Promise(r => setTimeout(r, 2400));
    document.querySelector('.mc-map-tools button[title="Zoom in"]').click();
    await new Promise(r => setTimeout(r, 1200));
    const inp = document.querySelector('.mc-trv-scrub input');
    const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    set.call(inp, '520');
    inp.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise(r => setTimeout(r, 900));
    return document.querySelector('.mc-trv-odo').innerText.replace(/\\s+/g, ' ');
  })()`);
  const counts = await ev(`({
    routes: document.querySelectorAll('.mc-traverse').length,
    waypoints: document.querySelectorAll('.mc-traverse-wp').length,
    ends: document.querySelectorAll('.mc-route-end').length,
    rover: document.querySelectorAll('.mc-rover-icon').length,
    labels: document.querySelectorAll('.mc-wp-label').length,
  })`);
  log(`  traverse — ${counts.routes} routes, ${counts.waypoints} waypoints, `
    + `${counts.ends} endpoints, ${counts.rover} rover, ${counts.labels} distance ticks`);
  log(`  odometer — ${odo}`);
  await shot('01-traverse-rover');

  // ── 2. the probe, reading a measured cell ────────────────────────────────
  const probe = await ev(`(async () => {
    const b = [...document.querySelectorAll('.mc-layer')]
      .find(x => x.textContent.includes('Criteria Probe'));
    if (!b.classList.contains('mc-layer--on')) b.click();
    await new Promise(r => setTimeout(r, 3000));
    const el = document.querySelector('.leaflet-container');
    const rc = el.getBoundingClientRect();
    // Aim at the rover: that is inside the amplitude ribbon by construction,
    // because the route starts at a site whose in_amplitude_mask criterion
    // passed. Clicking a fixed screen fraction would depend on the view.
    const rv = document.querySelector('.mc-rover-icon').getBoundingClientRect();
    for (const t of ['mousedown', 'mouseup', 'click'])
      el.dispatchEvent(new MouseEvent(t, { bubbles: true, cancelable: true,
        clientX: rv.x + rv.width / 2, clientY: rv.y + rv.height / 2,
        view: window, button: 0 }));
    await new Promise(r => setTimeout(r, 800));
    return document.querySelector('.mc-probe').innerText.replace(/\\n+/g, ' | ');
  })()`);
  log('  probe    — ' + probe.slice(0, 300));
  await shot('02-probe');

  await S('Target.closeTarget', { targetId });
  proc.kill();

  // Refuse to report success on an empty draw. A capture script that writes a
  // blank PNG and exits 0 is the third instance of METHODS §0's second pattern.
  if (counts.routes < 1 || counts.waypoints < 1 || counts.rover !== 1) {
    fail(`nothing to capture: ${counts.routes} routes, ${counts.waypoints} waypoints, `
       + `${counts.rover} rover. The shots would be evidence of nothing.`);
  }
  log('\n  both shots taken with the app driven through its own controls.');
  return 0;
}

main().catch((e) => fail(e.stack ?? String(e)));
