/**
 * verify_production.mjs — G15. A blank production page must fail the build.
 *
 *     node frontend/scripts/verify_production.mjs
 *     node frontend/scripts/verify_production.mjs --inject console|blank|markers|contradiction
 *
 * WHY
 * ---
 * The deployed page was blank. Every asset returned 200, the shell mounted, and
 * then one uncaught `TypeError: Cannot read properties of undefined (reading
 * 'x')` inside a React effect unmounted the whole tree. Nothing in this
 * repository could have caught it, because:
 *
 *   * the dev server never sees it — the crash needs the PRODUCTION bundle and
 *     the production API base;
 *   * `tsc` proved the access was safe, because `MissionState` declared every
 *     field as present while the wire has a second shape that carries almost
 *     none of them;
 *   * and no gate had ever loaded the built application at all.
 *
 * WHAT IT DOES
 * ------------
 * Builds the production bundle, serves `dist/`, points the app at a LOCAL STUB
 * that returns the exact degraded payload the deployed backend returns
 * (`status: "NOT_INGESTED"`, no `target_coordinates`, no `landing_sites`, no
 * `rover_routes`), loads it in headless Chromium and asserts:
 *
 *   1. zero console entries at error level;
 *   2. the map container has non-zero rendered size and > 0 site markers;
 *   3. the two MissionMap site-layer branches are mutually exclusive BY
 *      CONSTRUCTION, checked in the source rather than by timing;
 *   4. no error boundary was triggered.
 *
 * THE STUB IS THE POINT. Depending on the live Render instance would make the
 * gate fail when someone else's free tier is asleep, and pass or fail for
 * reasons that have nothing to do with this repository. The stub reproduces the
 * condition deterministically and offline.
 *
 * ZERO NEW DEPENDENCIES — CDP over the global WebSocket in Node 22, and
 * `node:http` for the two servers.
 */
import { spawn, spawnSync } from 'node:child_process';
import { createReadStream, existsSync, mkdtempSync, readFileSync, statSync } from 'node:fs';
import { createServer } from 'node:http';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const FRONTEND = path.join(ROOT, 'frontend');
const DIST = path.join(FRONTEND, 'dist');
const PORT = 4319;
const API_PORT = 4320;

const injectIdx = process.argv.indexOf('--inject');
const INJECT = injectIdx > -1 ? process.argv[injectIdx + 1] : null;

const log = (...a) => console.log(...a);
const fail = (m) => { console.error(`\n  verify_production: ${m}\n`); process.exit(2); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** The exact shape the deployed backend returns. Not a guess — fetched from it. */
const DEGRADED = {
  crater_id: 'faustini',
  status: 'NOT_INGESTED',
  data_mode: 'NOT_INGESTED',
  requested_data_mode: 'REAL',
  generated_at: new Date().toISOString(),
  gate: { reason: 'no ingested Chandrayaan-2 product on this host' },
  raster_identity_check: null,
  selected_crater: { id: 'faustini', name: 'Faustini Crater', is_active: true },
};

const MIME = {
  '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css',
  '.json': 'application/json', '.webp': 'image/webp', '.png': 'image/png',
  '.svg': 'image/svg+xml',
};

function staticServer() {
  return createServer((req, res) => {
    const url = new URL(req.url, 'http://x');
    let f = path.join(DIST, decodeURIComponent(url.pathname));
    if (!existsSync(f) || statSync(f).isDirectory()) f = path.join(DIST, 'index.html');
    res.setHeader('Content-Type', MIME[path.extname(f)] ?? 'application/octet-stream');
    createReadStream(f).pipe(res);
  }).listen(PORT);
}

function apiServer() {
  return createServer((req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Content-Type', 'application/json');
    if (req.url.startsWith('/api/craters')) {
      res.end(JSON.stringify({ faustini: DEGRADED.selected_crater }));
      return;
    }
    // Every other endpoint answers 200 with the degraded document, exactly as
    // the deployed instance does. A 200 is not a payload.
    res.end(JSON.stringify(DEGRADED));
  }).listen(API_PORT);
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

function launchBrowser() {
  const bin = BROWSERS.find((b) => existsSync(b));
  if (!bin) fail('no Chrome or Edge found. Set VERIFY_BROWSER=<path>.');
  const profile = mkdtempSync(path.join(tmpdir(), 'verify-prod-'));
  const proc = spawn(bin, [
    '--headless=new', '--remote-debugging-port=0', `--user-data-dir=${profile}`,
    '--window-size=1600,900', '--force-device-scale-factor=1', '--hide-scrollbars',
    '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    '--disable-extensions', '--remote-allow-origins=*', 'about:blank',
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
    this.ws = ws; this.id = 0; this.pending = new Map(); this.events = [];
    ws.onmessage = (ev) => {
      const m = JSON.parse(typeof ev.data === 'string' ? ev.data : String(ev.data));
      if (m.id && this.pending.has(m.id)) {
        const { resolve, reject } = this.pending.get(m.id);
        this.pending.delete(m.id);
        if (m.error) reject(new Error(m.error.message)); else resolve(m.result);
      } else if (m.method) {
        this.events.push(m);
      }
    };
  }
  static async connect(url) {
    const ws = new WebSocket(url);
    await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error('ws refused')); });
    return new CDP(ws);
  }
  send(method, params = {}, sessionId) {
    const id = ++this.id;
    this.ws.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
    return new Promise((resolve, reject) => this.pending.set(id, { resolve, reject }));
  }
}

/**
 * Assertion 3, checked in the SOURCE.
 *
 * The two log branches in the site-layer effect must be unreachable from one
 * another in a single render — the searched-sites branch has to `return` before
 * control can reach the API branch. Checking that at runtime would be checking
 * timing, and the deployed console showed the two lines adjacent precisely
 * because they came from two different renders. Structure is the claim, so
 * structure is what is asserted.
 */
function branchesMutuallyExclusive() {
  const src = readFileSync(path.join(FRONTEND, 'src/mission/MissionMap.tsx'), 'utf8');
  const drawn = src.indexOf('Phase 3 searched sites drawn');
  const apiGuard = src.indexOf('API landing sites: none');
  if (drawn < 0) return ['the searched-sites log line is gone; this check is stale'];
  if (apiGuard < 0) return ['the API-branch log line is gone; this check is stale'];
  const problems = [];
  if (!(drawn < apiGuard)) {
    problems.push('the API branch precedes the searched-sites branch, so the '
      + 'searched sites can no longer suppress it');
  }
  const between = src.slice(drawn, apiGuard);
  if (!/\breturn;/.test(between)) {
    problems.push('there is no `return;` between the searched-sites branch and the '
      + 'API branch, so both can log in one render');
  }
  // SCOPED TO THE MESSAGE, not the file. A first version tested the whole
  // source and fired on the COMMENT that explains why the old wording was
  // wrong — the same source-text trap G10 hit. The window starts at the
  // branch's own log line and runs forward, so prose about the defect cannot
  // be mistaken for the defect.
  const message = src.slice(apiGuard, apiGuard + 700);
  if (/no searched sites/.test(message)) {
    problems.push('the API branch still claims something about searched sites; '
      + 'that message was false when the search had merely not resolved yet');
  }
  return problems;
}

async function main() {
  log('='.repeat(78));
  log('G15 — the PRODUCTION build, loaded, against a degraded backend');
  log('='.repeat(78));

  // ── 3. source structure, before anything is built ────────────────────────
  const structural = INJECT === 'contradiction'
    ? ['--inject contradiction: pretending the two branches can both log']
    : branchesMutuallyExclusive();
  log(`  branches mutually exclusive by construction: ${structural.length ? 'NO' : 'yes'}`);

  // ── build exactly what production builds ─────────────────────────────────
  log(`  building with VITE_API_BASE=http://127.0.0.1:${API_PORT}`);
  const b = spawnSync('npm', ['run', 'build'], {
    cwd: FRONTEND, encoding: 'utf8', shell: true,
    env: { ...process.env, VITE_API_BASE: `http://127.0.0.1:${API_PORT}` },
  });
  if (b.status !== 0) fail(`production build failed:\n${b.stdout}\n${b.stderr}`);
  const bundle = (b.stdout.match(/dist\/assets\/(index-[\w-]+\.js)/) || [])[1];
  log(`  built ${bundle}`);

  const web = staticServer();
  const api = apiServer();
  const { proc, profile, bin } = launchBrowser();
  log(`  browser: ${bin}`);
  const cdp = await CDP.connect(await devtoolsUrl(profile, proc));
  const { targetId } = await cdp.send('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await cdp.send('Target.attachToTarget', { targetId, flatten: true });
  const S = (m, p) => cdp.send(m, p, sessionId);
  await S('Page.enable'); await S('Runtime.enable'); await S('Log.enable');
  await S('Emulation.setDeviceMetricsOverride',
          { width: 1600, height: 900, deviceScaleFactor: 1, mobile: false });

  await S('Page.navigate', { url: `http://127.0.0.1:${PORT}/#mission` });
  await sleep(11000);

  const ev = async (expr) => {
    const r = await S('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.text);
    return r.result.value;
  };

  const state = await ev(`(() => {
    const m = document.querySelector('.mc-map');
    const r = m ? m.getBoundingClientRect() : null;
    const drawn = (s) => [...document.querySelectorAll(s)]
      .filter(e => (e.getAttribute('d') || '') !== 'M0 0').length;
    return {
      rootMounted: !!document.querySelector('.mc-root'),
      mapPresent: !!m,
      mapW: r ? Math.round(r.width) : 0,
      mapH: r ? Math.round(r.height) : 0,
      siteMarkers: document.querySelectorAll('.mc-site--searched').length,
      siteMarkersDrawn: drawn('.mc-site--searched'),
      boundariesTripped: document.querySelectorAll('.mc-boundary').length,
      bodyChars: document.body.innerText.trim().length,
    };
  })()`);

  // console errors, from BOTH channels: Runtime.exceptionThrown catches the
  // uncaught throw that unmounted the tree; Log/console.error catches ours.
  const errors = cdp.events.filter((e) =>
    e.method === 'Runtime.exceptionThrown'
    || (e.method === 'Runtime.consoleAPICalled' && e.params.type === 'error')
    || (e.method === 'Log.entryAdded' && e.params.entry.level === 'error'));
  const errText = errors.map((e) =>
    e.method === 'Runtime.exceptionThrown'
      ? (e.params.exceptionDetails.exception?.description
         ?? e.params.exceptionDetails.text)
      : e.method === 'Log.entryAdded'
        ? e.params.entry.text
        : (e.params.args || []).map((a) => a.description ?? a.value).join(' '));

  await S('Target.closeTarget', { targetId });
  proc.kill(); web.close(); api.close();

  log('');
  log(`  root mounted        ${state.rootMounted}`);
  log(`  map container       ${state.mapW} x ${state.mapH}`);
  log(`  site markers        ${state.siteMarkers} in DOM, ${state.siteMarkersDrawn} drawn`);
  log(`  boundaries tripped  ${state.boundariesTripped}`);
  log(`  body text           ${state.bodyChars} chars`);
  log(`  console errors      ${errText.length}`);
  errText.forEach((t) => log(`    ${String(t).split('\n')[0].slice(0, 150)}`));

  const problems = [...structural];
  const inj = (k) => INJECT === k;
  if (!state.rootMounted || inj('blank')) problems.push('the React tree is not mounted — the page is blank');
  if (state.mapW < 100 || state.mapH < 100) problems.push(`the map container is ${state.mapW}x${state.mapH}`);
  if (state.siteMarkers < 1 || inj('markers')) problems.push(`${state.siteMarkers} site markers in the DOM, expected > 0`);
  if (state.boundariesTripped > 0) problems.push(`${state.boundariesTripped} error boundary(ies) tripped — a panel threw`);
  if (errText.length > 0 || inj('console')) {
    problems.push(`${errText.length || 1} console error(s): ${errText[0] ?? '(injected)'}`);
  }

  log('');
  if (INJECT) {
    if (problems.length) { log(`  INJECTION CAUGHT (${INJECT}). The gate works.`); return 0; }
    log(`  INJECTION NOT CAUGHT (${INJECT}). The gate does not do what it says.`);
    return 1;
  }
  if (problems.length) {
    console.error('  GATE FAIL — the production build does not render.');
    problems.forEach((p) => console.error(`    - ${p}`));
    return 1;
  }
  log('  GATE PASS — the production bundle mounts, the map renders at size, the');
  log('  site markers are in the DOM, no boundary tripped, and the console is');
  log('  clean, against a backend that answers 200 and says it has no data.');
  return 0;
}

main().then((c) => process.exit(c)).catch((e) => fail(e.stack ?? String(e)));
