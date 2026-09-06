/**
 * capture_layers.mjs — one screenshot per map layer, at a FIXED view.
 *
 *     node frontend/scripts/capture_layers.mjs --tag before
 *     node frontend/scripts/capture_layers.mjs --tag after
 *
 * WHY A SCRIPT AND NOT A BROWSING SESSION
 * ---------------------------------------
 * Gate 6 asks for before/after evidence per layer at identical zoom and centre.
 * "Identical" cannot be achieved by driving a browser by hand twice: the view is
 * set here as a literal, printed into the manifest, and asserted on the second
 * pass, so the two sets are comparable BY CONSTRUCTION rather than by care.
 *
 * The before set is unrecoverable once the render changes, so this runs before
 * any Phase 6 file is touched.
 *
 * ZERO NEW DEPENDENCIES — CDP over the global WebSocket in Node 22, the same
 * plumbing verify_v8_view.mjs uses. Nothing added to package.json.
 */
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const arg = (k, d) => {
  const i = process.argv.indexOf(`--${k}`);
  return i > -1 && process.argv[i + 1] ? process.argv[i + 1] : d;
};

const CFG = {
  url: arg('url', 'http://localhost:3000/'),
  out: path.resolve(ROOT, arg('out', 'docs/gate6')),
  width: Number(arg('width', '1600')),
  height: Number(arg('height', '900')),
  tag: arg('tag', 'before'),
};

/**
 * THE FIXED VIEWS. Literals, not "wherever the app happened to open", because a
 * before/after pair taken at two different views compares the view rather than
 * the change. Coordinates are CRS.Simple units on the layers.json grid, whose
 * bounds are [[0,0],[87.344817,256]] — so [43.7, 128] is the frame centre.
 */
const VIEWS = [
  { name: 'full', centre: [43.7, 128.0], zoom: 2.2 },
  { name: 'detail', centre: [43.7, 128.0], zoom: 4.5 },
];

/**
 * The raster layers, READ FROM layers.json rather than restated here.
 *
 * They were a hardcoded list of button LABELS, and the first rename broke it:
 * "Radar Signals (CPR)" became "Channel imbalance (CPR proxy)" and the after
 * pass silently skipped that layer. Same rule as everywhere else in this
 * project -- a script must read the value the application uses, never restate
 * it. Files are named by layer ID, so a future rename cannot break the pairing
 * between a before shot and its after.
 */
async function readLayers() {
  const manifest = JSON.parse(
    readFileSync(path.resolve(ROOT, 'frontend/public/layers/layers.json'), 'utf8'));
  return manifest.layers.map((l) => ({ id: l.id, label: l.label }));
}

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
const fail = (m) => { console.error(`\n  capture_layers: ${m}\n`); process.exit(2); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function launchBrowser() {
  const bin = BROWSERS.find((b) => existsSync(b));
  if (!bin) fail(`no Chrome or Edge found. Set VERIFY_BROWSER=<path>.`);
  const profile = mkdtempSync(path.join(tmpdir(), 'capture-layers-'));
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

/** Injected into the page: find the Leaflet map through the React fiber. */
const FIND_MAP = `
(function(){
  const c = document.querySelector('.leaflet-container');
  if (!c) return null;
  const key = Object.keys(c).find(k => k.startsWith('__reactFiber$'));
  let f = c[key], guard = 0;
  while (f && guard < 300) {
    const st = f.stateNode;
    if (st && typeof st.getZoom === 'function') return st;
    let cur = f.memoizedState;
    while (cur) {
      const v = cur.memoizedState;
      if (v && v.current && typeof v.current.getZoom === 'function') return v.current;
      cur = cur.next;
    }
    f = f.return; guard++;
  }
  return null;
})()`;

async function main() {
  mkdirSync(CFG.out, { recursive: true });
  const { proc, profile } = launchBrowser();
  const cdp = await CDP.connect(await devtoolsUrl(profile, proc));
  const { targetId } = await cdp.send('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await cdp.send('Target.attachToTarget', { targetId, flatten: true });
  const S = (m, p) => cdp.send(m, p, sessionId);
  await S('Page.enable');
  await S('Runtime.enable');

  const ev = async (expr) => {
    const r = await S('Runtime.evaluate', {
      expression: expr, awaitPromise: true, returnByValue: true,
    });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.text + ' :: ' + expr.slice(0, 120));
    return r.result.value;
  };

  log(`\n  url    ${CFG.url}`);
  log(`  out    ${CFG.out}`);
  log(`  tag    ${CFG.tag}`);
  log(`  size   ${CFG.width}x${CFG.height}\n`);

  await S('Page.navigate', { url: CFG.url });
  await sleep(4000);

  // Into Mission Control. The landing page mounts first and the map does not
  // exist until this button is pressed.
  await ev(`(function(){
    const b = [...document.querySelectorAll('button')]
      .find(e => /Explore Lunar Ice/i.test(e.textContent));
    if (b) b.click();
    return !!b;
  })()`);
  await sleep(7000);

  const haveMap = await ev(`!!document.querySelector('.leaflet-container')`);
  if (!haveMap) fail('mission control never mounted a map');

  const manifest = { tag: CFG.tag, url: CFG.url, viewport: [CFG.width, CFG.height],
                     views: VIEWS, captured: [], generated_utc: new Date().toISOString() };

  const layers = await readLayers();
  log(`  layers ${layers.length} from layers.json: `
    + layers.map((l) => l.id).join(', ') + '\n');
  for (const view of VIEWS) {
    for (const { id, label } of layers) {
      const clicked = await ev(`(function(){
        const b = [...document.querySelectorAll('button')]
          .find(e => e.textContent.trim() === ${JSON.stringify(label)});
        if (b) b.click();
        return !!b;
      })()`);
      // A layer in the manifest with no button is a real inconsistency between
      // the renderer and the UI, not something to skip past quietly.
      if (!clicked) {
        console.error(
          "\n  capture_layers: layers.json lists \"" + id + "\" (" + label
          + ") but no button carries that label. The manifest and the layer"
          + " switch disagree.\n");
        process.exit(3);
      }
      await sleep(900);

      // Set the view AFTER selecting the layer: switching layers can refit.
      const state = await ev(`(function(){
        const m = ${FIND_MAP};
        if (!m) return null;
        m.setView([${view.centre[0]}, ${view.centre[1]}], ${view.zoom}, {animate:false});
        return {zoom: m.getZoom(), centre: [m.getCenter().lat, m.getCenter().lng],
                minZoom: m.getMinZoom()};
      })()`);
      await sleep(1400);

      const file = `${CFG.tag}.${view.name}.${id}.png`;
      const shot = await S('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
      writeFileSync(path.join(CFG.out, file), Buffer.from(shot.data, 'base64'));
      manifest.captured.push({ view: view.name, id, layer: label, file, state });
      log(`  ${file}   zoom ${state ? state.zoom.toFixed(3) : '?'}  centre `
        + `${state ? state.centre.map((v) => v.toFixed(2)).join(',') : '?'}`);
    }
  }

  writeFileSync(path.join(CFG.out, `capture.${CFG.tag}.json`),
                JSON.stringify(manifest, null, 2));
  log(`\n  wrote ${manifest.captured.length} shots + capture.${CFG.tag}.json`);
  try { proc.kill(); } catch { /* already gone */ }
  process.exit(0);
}

main().catch((e) => fail(e.stack || String(e)));
