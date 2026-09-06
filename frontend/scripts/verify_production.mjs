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
const stateIdx = process.argv.indexOf('--state');
/** Which backend state to put the stub in. Production's is not_ingested. */
const STATE = stateIdx > -1 ? process.argv[stateIdx + 1] : 'not_ingested';

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

/**
 * The stub, in whichever of the three backend states the run is testing.
 *
 *   'not_ingested' answers 200 with the degraded document the deployed instance
 *                  returns. This is production's state and the default.
 *   'unreachable'  refuses the connection outright, so `fetch` rejects.
 *   'ok'           answers with a payload carrying the fields the UI reads.
 *
 * The UI must name these three apart. It used to derive all three from
 * `error != null`, which cannot, and put "is not reachable" on the same screen
 * as "is reachable but reports NOT_INGESTED" under a badge reading OFFLINE.
 */
function apiServer(state) {
  if (state === 'unreachable') return null;          // nothing listening
  return createServer((req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Content-Type', 'application/json');
    if (req.url.startsWith('/api/craters')) {
      res.end(JSON.stringify({ faustini: DEGRADED.selected_crater }));
      return;
    }
    if (state === 'ok') { res.end(JSON.stringify(OK_PAYLOAD)); return; }
    res.end(JSON.stringify(DEGRADED));
  }).listen(API_PORT);
}

/**
 * A payload complete enough for the UI's OK path. Only the fields MissionMap and
 * MissionControl actually read; anything absent here would be a field the UI
 * must already tolerate.
 */
const OK_PAYLOAD = {
  ...DEGRADED,
  status: 'OK',
  data_mode: 'REAL',
  target_coordinates: { x: 50, y: 50 },
  landing_sites: [],
  recommended_landing_site: null,
  rover_routes: {},
  grid_dimensions: { width: 100, height: 100, pixel_scale_m: 25 },
  raster_layers: {},
};

/**
 * Assertion 5: no two rendered strings make opposite claims about reachability,
 * and the badge matches the state the fetch layer observed.
 *
 * Phrases are matched on the RENDERED TEXT, not the source, because the defect
 * was two sentences that were each individually defensible and jointly false.
 */
function contradictions(text, state) {
  const said = {
    unreachable: /not reachable|unreachable|nothing answered|no response/i.test(text),
    reachable: /is reachable|backend answered|answered and reports|reachable and holds/i.test(text),
  };
  const problems = [];
  if (said.unreachable && said.reachable) {
    problems.push('the page claims the backend is BOTH reachable and not reachable');
  }
  // THE BADGE MOVED TO STAGE 09 and this gate moved with it. Matching the
  // header would now pass vacuously -- there is no host-state badge there --
  // which is the failure mode where a check keeps its green light by no longer
  // looking at anything. `text` is stage 09's own rendered text.
  const badge = (text.match(/(BACKEND UNREACHABLE|NO RASTERS ON HOST|CHECKING HOST|LIVE(?: · SIMULATED PAYLOAD)?)/) || [])[0]
    || '(no host-state badge)';
  const expect = { ok: /^LIVE/, not_ingested: /^NO RASTERS ON HOST$/,
                   unreachable: /^BACKEND UNREACHABLE$/ }[state];
  if (expect && !expect.test(badge)) {
    problems.push(`stage-09 host badge reads "${badge.trim()}" in state ${state}`);
  }
  if (state === 'not_ingested' && said.unreachable) {
    problems.push('the backend answered, and the page says it is not reachable');
  }
  if (state === 'unreachable' && said.reachable) {
    problems.push('nothing answered, and the page says the backend is reachable');
  }
  return { problems, badge };
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
  log(`G15 — the PRODUCTION build, loaded, backend state: ${STATE}`);
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
  const api = apiServer(STATE);
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
      text: document.body.innerText,
      // The header's BADGES only, not the whole bar.
      //
      // NOTE: no backticks in this comment -- it lives inside a template
      // literal, and the first version of it terminated the string.
      // The first version of this CHECK read the whole .mc-topbar bar and
      // failed in state unreachable on the Report control, which says "backend
      // unreachable" because it is REQUIRED to name the state it is in. That is
      // a control describing itself, which is correct; what moved to stage 09 is
      // a free-standing badge describing the SYSTEM. A check that cannot tell
      // those apart would have forced the Report control to go quiet, i.e. it
      // would have caused the exact defect this file exists to prevent.
      headerBadges: [...document.querySelectorAll('.mc-topbar .mc-badge')]
        .map(e => e.innerText).join(' | '),
      // Anything drawn ON the map that talks about host state. The map is the
      // product; a caveat over it has to be about the map, and after the sweep
      // grid nothing on this screen needs the on-demand host at all.
      mapOverlayText: [...document.querySelectorAll('.mc-map-overlay')]
        .map(e => e.innerText).join(' | '),
      // Anything styled as a FAILURE on the main screen. Red is a claim that
      // something is broken; the mission endpoint's NOT_INGESTED state breaks
      // nothing here, and it was being painted across the top of the map.
      errorBanners: [...document.querySelectorAll('.mc-error')]
        .map(e => e.innerText).join(' | '),
    };
  })()`);

  // ── walk to the stage that owns host state ───────────────────────────────
  // Stage 12. It was stage 09 for exactly one commit: 09 was the only screen a
  // no-raster host cost anything, until emit_sweep_grid.py precomputed the joint
  // screen and its sliders stopped querying. The PDF is the last consumer, so
  // the badge sits beside it. This gate followed it BOTH times rather than
  // keeping a green light by no longer looking.
  //
  // Clicked rather than deep-linked, because the click is the path a reader
  // takes and a stage that only renders when addressed directly is not one
  // click away.
  const visit = async (n) => {
    await ev(`(() => {
      const b = [...document.querySelectorAll('.mc-step')]
        .find(e => e.innerText.trim().startsWith('${n}'));
      if (b) b.click();
      return !!b;
    })()`);
    await sleep(1200);
    return ev(`(() => {
      const el = document.querySelector('.mc-hoststate');
      const card = el ? el.closest('.mc-card') : null;
      return {
        present: !!el,
        text: el ? el.innerText : '',
        panelText: (document.querySelector('.mc-rail')?.innerText) || '',
        // Does the card the block sits in actually CONTAIN a sweep table? The
        // block's text was written for stage 09 and moved to stage 12 verbatim,
        // where it went on saying "the two sweep tables below" on a stage that
        // has none. A sentence about what is on the screen is checkable against
        // the screen, so it is checked.
        hasSweepTable: !!(card && /CPR threshold sweep|DOP threshold sweep/
          .test(card.innerText)),
        // STRUCTURAL, not a phrase list. The first version matched the words
        // the not_ingested branch happens to use, and failed in unreachable,
        // where the same control correctly says something else. A check that
        // enumerates the wordings of a control will fail every time the control
        // gains a state -- which is the defect this whole file is about.
        hasReport: !!(card && (card.querySelector('a[href*="/report/pdf"]')
                               || card.querySelector('.mc-na'))),
      };
    })()`);
  };
  // Stage 09 first: it must NOT claim a host dependency it no longer has.
  const stage9 = await visit('09');
  const hostStage = await visit('12');

  // console errors, from BOTH channels: Runtime.exceptionThrown catches the
  // uncaught throw that unmounted the tree; Log/console.error catches ours.
  const errors = cdp.events.filter((e) =>
    e.method === 'Runtime.exceptionThrown'
    || (e.method === 'Runtime.consoleAPICalled' && e.params.type === 'error')
    || (e.method === 'Log.entryAdded' && e.params.entry.level === 'error'));
  // A REFUSED CONNECTION IS THE STATE UNDER TEST, NOT AN APP ERROR. In
  // `--state unreachable` the browser logs `net::ERR_CONNECTION_REFUSED` for
  // each API request, at network level, because nothing is listening — that is
  // the condition being asserted, and failing on it would make the state
  // untestable. The exclusion is deliberately narrow: only network-level
  // resource-load failures, only in that state. Anything the APPLICATION logs
  // through console.error, and any uncaught exception, still fails in every
  // state.
  const isExpectedNetworkNoise = (e) =>
    STATE === 'unreachable'
    && e.method === 'Log.entryAdded'
    && e.params.entry.source === 'network'
    && /ERR_(CONNECTION_REFUSED|FAILED|NAME_NOT_RESOLVED)/.test(e.params.entry.text);

  const appErrors = errors.filter((e) => !isExpectedNetworkNoise(e));
  const excluded = errors.length - appErrors.length;
  if (excluded) log(`  (${excluded} network-level refusal(s) excluded — that is the state under test)`);
  const errText = appErrors.map((e) =>
    e.method === 'Runtime.exceptionThrown'
      ? (e.params.exceptionDetails.exception?.description
         ?? e.params.exceptionDetails.text)
      : e.method === 'Log.entryAdded'
        ? e.params.entry.text
        : (e.params.args || []).map((a) => a.description ?? a.value).join(' '));

  await S('Target.closeTarget', { targetId });
  proc.kill(); web.close(); if (api) api.close();

  log('');
  log(`  root mounted        ${state.rootMounted}`);
  log(`  map container       ${state.mapW} x ${state.mapH}`);
  log(`  site markers        ${state.siteMarkers} in DOM, ${state.siteMarkersDrawn} drawn`);
  log(`  boundaries tripped  ${state.boundariesTripped}`);
  log(`  body text           ${state.bodyChars} chars`);
  log(`  console errors      ${errText.length} (application-level)`);
  errText.forEach((t) => log(`    ${String(t).split('\n')[0].slice(0, 150)}`));

  const problems = [...structural];
  const inj = (k) => INJECT === k;
  if (!state.rootMounted || inj('blank')) problems.push('the React tree is not mounted — the page is blank');
  if (state.mapW < 100 || state.mapH < 100) problems.push(`the map container is ${state.mapW}x${state.mapH}`);
  if (state.siteMarkers < 1 || inj('markers')) problems.push(`${state.siteMarkers} site markers in the DOM, expected > 0`);
  if (state.boundariesTripped > 0) problems.push(`${state.boundariesTripped} error boundary(ies) tripped — a panel threw`);

  // ── 5. the three backend states, named apart ────────────────────────────
  const c = contradictions(INJECT === 'contradictstate'
    ? hostStage.text + ' the backend is not reachable and is reachable'
    : hostStage.text, STATE);
  log(`  backend state       ${STATE}, stage-12 badge "${c.badge.trim()}"`);
  problems.push(...c.problems);

  // 5a. the badge and its explanation SURVIVED the move. "Move it, delete
  //     nothing" is only true if the destination actually renders it.
  if (!hostStage.present || INJECT === 'nohoststate') {
    problems.push('stage 12 renders no .mc-hoststate block — the host-state badge '
      + 'and its explanation were removed rather than moved');
  }
  if (hostStage.present && hostStage.text.trim().length < 80) {
    problems.push(`the host-state block is ${hostStage.text.trim().length} chars; `
      + 'the explanation did not come with the badge');
  }
  // 5c-bis. THE BLOCK'S TEXT MUST DESCRIBE THE CARD IT IS IN.
  //     It claimed "the two sweep tables below are static artifacts" after being
  //     moved to a stage with no sweep tables — the same drift as the sentence
  //     it was moved to fix, one commit later. Any "below" claim is checked
  //     against the card's own content.
  const saysTables = /sweep tables? below|tables below/i.test(
    INJECT === 'wrongstage' ? hostStage.text + ' the two sweep tables below' : hostStage.text);
  if (saysTables && !hostStage.hasSweepTable) {
    problems.push('the host-state block says "sweep tables below" on a card that '
      + 'contains no sweep table — the text was moved without being reread');
  }
  const saysReport = /report below/i.test(hostStage.text);
  if (saysReport && !hostStage.hasReport) {
    problems.push('the host-state block says "report below" on a card that '
      + 'contains no report control');
  }

  // 5c-ter. NOTHING ON THE MAP ANNOUNCES HOST STATE.
  //     A banner over the product said a subsystem was unavailable on a screen
  //     where everything it covered was present: relief, science layers, sites,
  //     traverse, probe and verdict are all static. After the sweep grid it was
  //     announcing a loss that existed nowhere in view.
  const mapText = INJECT === 'maphostbanner'
    ? state.mapOverlayText + ' NO RASTERS ON HOST' : state.mapOverlayText;
  if (/NO RASTERS ON HOST|BACKEND UNREACHABLE|STUDIO ·|CHECKING HOST/.test(mapText)) {
    problems.push('a host-state banner is drawn over the map; nothing on that '
      + 'screen depends on the on-demand host');
  }

  // 5c-quater. NO HOST-STATE CONDITION IS PAINTED AS AN ERROR.
  const hostErrText = INJECT === 'hosterror'
    ? state.errorBanners + ' reports NOT_INGESTED' : state.errorBanners;
  if (/NOT_INGESTED|no ingested raster|not reachable|unreachable/i.test(hostErrText)) {
    problems.push('a host-state condition is rendered as an error banner on the '
      + 'main screen; nothing there depends on the mission endpoint');
  }

  // 5c-quinquies. AND ITS TEXT SURVIVED THE MOVE.
  //     "Move it, delete nothing" is only true if the destination renders it.
  //     The endpoint's own words -- the product id and the missing rasters --
  //     are the clearest writing in the app and must stay reachable in full.
  if (STATE === 'not_ingested') {
    const kept = /NOT_INGESTED|ingested raster/i.test(
      INJECT === 'hostreason' ? '' : hostStage.text);
    if (!kept) {
      problems.push("the mission endpoint's own reason is not rendered anywhere on "
        + 'the stage that owns host state; it was dropped rather than moved');
    }
  }

  // 5d. AND IT LEFT STAGE 09. A host-state badge on a stage with no host
  //     dependency is the same defect as one in the global header, one scope
  //     smaller — it tells a reader something is degraded that is not.
  if (stage9.present || INJECT === 'staleststage') {
    problems.push('stage 09 still renders a host-state block, but its sweep grid '
      + 'is precomputed and it depends on no host');
  }

  // 5b. and it did NOT stay in the header, where it read as a global failure.
  const headerHost = /BACKEND UNREACHABLE|NO RASTERS ON HOST|STUDIO ·/
    .test(INJECT === 'badgeinheader'
      ? state.headerBadges + ' | NO RASTERS ON HOST' : state.headerBadges);
  if (headerHost) {
    problems.push('a host-state badge is back in the global header, where it '
      + 'reads as a system-wide failure; it belongs on stage 09');
  }

  // 5c. the whole point of the move: a no-raster host must NOT be described as
  //     breaking the sweep tables, which are static and render fine.
  const claimsTablesBroken = /sweep tables[^.]*(unavailable|cannot|not available)/i
    .test(INJECT === 'tablesbroken'
      ? stage9.panelText + ' the sweep tables are unavailable' : stage9.panelText);
  if (claimsTablesBroken) {
    problems.push('stage 09 claims its sweep tables are unavailable; they are '
      + 'static artifacts and render on a host with no rasters');
  }
  log(`  stage-12 host block ${hostStage.present ? `${hostStage.text.trim().length} chars` : 'ABSENT'}`
      + `, stage-09 clean: ${!stage9.present}`
      + `, header badges: "${state.headerBadges}"`);
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
  log(`  GATE PASS — in backend state "${STATE}" the production bundle mounts, the`);
  log('  map renders at size, the site markers are in the DOM, no boundary tripped,');
  log('  the console is clean of application errors, and no two rendered strings');
  log('  disagree about whether the backend is reachable.');
  return 0;
}

/**
 * `--all-states` runs the three backend states in sequence, as separate
 * processes.
 *
 * Separate processes rather than a loop inside one: each state needs its own
 * browser, its own stub and its own listening port, and a leaked handle from one
 * state would make the next one's result depend on the previous one's cleanup.
 * The cost is two extra builds of a bundle that takes seven seconds.
 */
if (process.argv.includes('--all-states')) {
  const states = ['not_ingested', 'unreachable', 'ok'];
  let bad = 0;
  for (const st of states) {
    const r = spawnSync(process.execPath, [fileURLToPath(import.meta.url), '--state', st],
                        { stdio: 'inherit' });
    if (r.status !== 0) bad++;
  }
  console.log(bad
    ? `
  ${bad} of ${states.length} backend states FAILED.`
    : `
  all ${states.length} backend states pass: ${states.join(', ')}.`);
  process.exit(bad ? 1 : 0);
}

main().then((c) => process.exit(c)).catch((e) => fail(e.stack ?? String(e)));
