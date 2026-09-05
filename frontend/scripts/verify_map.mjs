/**
 * verify_map.mjs — one command, all of the v7 gate evidence, reproducible.
 *
 *     node frontend/scripts/verify_map.mjs
 *
 * Replaces the ad-hoc "paste a probe into the browser and poke at it" pass that
 * produced the v7 §2/§3 numbers the first time. Same measurements, but committed,
 * deterministic and re-runnable by a human later.
 *
 * WHAT IT PRODUCES (all under docs/):
 *   map_before_relief.png  map_before_cpr.png      1600 x 900, identical view
 *   map_after_relief.png   map_after_cpr.png
 *   verify_map.json        every number below, machine-readable
 *
 * WHAT IT MEASURES
 *   · mean RGB and sRGB relative luminance inside each of the three coverage
 *     tiers, SAMPLED OFF A CANVAS — the base <img> drawn through its own COMPUTED
 *     CSS filter, then the mc-void pane's real SVG rasterised on top. No formula
 *     is recomputed; if the CSS changes, these numbers change.
 *   · the hillshade 8-bit histogram before and after the filter change, by
 *     shelling out to backend/scripts/hillshade_histogram.py (numpy/PIL only).
 *   · site / target / waypoint coverage counts, read from the live coverage key.
 *   · three independent proofs that the hatch RENDERED rather than falling back.
 *   · agreement between pointInPolygon() and what the browser actually filled.
 *
 * ZERO NEW DEPENDENCIES. Node 22 ships a global WebSocket, so this speaks the
 * Chrome DevTools Protocol directly to whichever Chrome or Edge is already
 * installed. Nothing is added to package.json; nothing is added to
 * requirements.txt.
 *
 * TWO AUTOMATION FACTS, BOTH MEASURED IN THIS PROJECT, BOTH LOAD-BEARING HERE
 *   1. document.hidden can be true under automation, so requestAnimationFrame
 *      never fires and every ANIMATED Leaflet move silently stalls. This script
 *      therefore never calls flyTo / flyToBounds / zoomIn / zoomOut. Only
 *      setView(centre, z, { animate: false }).
 *   2. The overlay swaps a 640 px preview for the full raster asynchronously, so
 *      a screenshot on a timer can catch the preview and report the wrong thing.
 *      Every capture waits on the image's own load state AND on naturalWidth
 *      matching the manifest's full width.
 *
 * HOW "BEFORE" IS OBTAINED. Not from git. The pre-v7 styling is re-applied in the
 * live DOM — scrim #03060c at 0.82 / 0.5, hatch off, base filter
 * contrast(1.14) brightness(1.16) saturate(0.92) — so BEFORE and AFTER differ in
 * nothing but the styling under test: same build, same view, same viewport, same
 * data. The override is inline style on the three void paths and on the base img,
 * and it is removed again before the AFTER pass.
 */
import { spawn, spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..');           // frontend/scripts -> repo root

// ── args ───────────────────────────────────────────────────────────
const argv = process.argv.slice(2);
const arg = (name, fallback) => {
  const i = argv.indexOf(`--${name}`);
  return i >= 0 && argv[i + 1] ? argv[i + 1] : fallback;
};
const CFG = {
  url: arg('url', process.env.VERIFY_URL || 'http://localhost:3000/#/mission'),
  out: path.resolve(ROOT, arg('out', 'docs')),
  zoom: Number(arg('zoom', '4')),
  centre: arg('centre', '45.063095292111406,128.73496854368935').split(',').map(Number),
  step: Number(arg('step', '3')),            // canvas sampling stride in px
  width: Number(arg('width', '1600')),
  height: Number(arg('height', '900')),
  headful: argv.includes('--headful'),
};

const BROWSERS = [
  process.env.VERIFY_BROWSER,
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  `${process.env.LOCALAPPDATA || ''}/Google/Chrome/Application/chrome.exe`,
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
  '/usr/bin/google-chrome',
  '/usr/bin/chromium',
].filter(Boolean);

const log = (...a) => console.log(...a);
const fail = (msg) => { console.error(`\n  verify_map: ${msg}\n`); process.exit(2); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
// ── browser launch ─────────────────────────────────────────────────
//
// --remote-debugging-port=0 lets the browser pick a free port and write it into
// DevToolsActivePort inside the profile dir, whose second line is the browser
// websocket path. Hardcoding 9222 breaks the moment anything else holds it.
function launchBrowser() {
  const bin = BROWSERS.find((b) => existsSync(b));
  if (!bin) fail(`no Chrome or Edge found. Tried:\n    ${BROWSERS.join('\n    ')}\n  `
    + 'Set VERIFY_BROWSER=<path to chrome.exe>.');
  const profile = mkdtempSync(path.join(tmpdir(), 'verify-map-'));
  const args = [
    CFG.headful ? '--headless=false' : '--headless=new',
    '--remote-debugging-port=0',
    `--user-data-dir=${profile}`,
    `--window-size=${CFG.width},${CFG.height}`,
    '--force-device-scale-factor=1',
    '--hide-scrollbars',
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-extensions',
    '--remote-allow-origins=*',
    'about:blank',
  ].filter((a) => a !== '--headless=false');
  const proc = spawn(bin, args, { stdio: 'ignore' });
  return { proc, profile, bin };
}

async function devtoolsUrl(profile, proc) {
  const portFile = path.join(profile, 'DevToolsActivePort');
  for (let i = 0; i < 200; i++) {
    if (proc.exitCode !== null) fail(`browser exited with code ${proc.exitCode}`);
    if (existsSync(portFile)) {
      const [port, wsPath] = readFileSync(portFile, 'utf8').trim().split('\n');
      if (port && wsPath) return `ws://127.0.0.1:${port}${wsPath}`;
    }
    await sleep(100);
  }
  fail('browser never wrote DevToolsActivePort (20 s)');
}
// ── minimal CDP client ─────────────────────────────────────────────
class CDP {
  constructor(ws) {
    this.ws = ws; this.id = 0; this.pending = new Map(); this.waiters = [];
    ws.onmessage = (ev) => {
      const msg = JSON.parse(typeof ev.data === 'string' ? ev.data : String(ev.data));
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        if (msg.error) reject(new Error(`${msg.error.message} (${msg.error.code})`));
        else resolve(msg.result);
      } else if (msg.method) {
        this.waiters = this.waiters.filter((w) => {
          if (w.method !== msg.method) return true;
          w.resolve(msg.params); return false;
        });
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

  once(method, timeout = 30000) {
    return new Promise((resolve, reject) => {
      const w = { method, resolve };
      this.waiters.push(w);
      setTimeout(() => {
        this.waiters = this.waiters.filter((x) => x !== w);
        reject(new Error(`timed out waiting for ${method}`));
      }, timeout);
    });
  }
}
// ── the in-page harness ────────────────────────────────────────────
//
// Written as a real function and shipped with .toString(), so it is source the
// linter and the editor can see rather than a quoted blob. Node never runs it.
function harness() {
  const H = {};
  const NS = 'http://www.w3.org/2000/svg';

  /** Find the live Leaflet map by walking the React fiber, not by exporting a
   *  global out of production code. */
  H.init = async function () {
    // 90 s, not 20: a cold mission request recomputes the whole pipeline on the
    // backend, and the map element does not exist until that resolves. Waiting on
    // the element rather than on a fixed timer is the point.
    for (let i = 0; i < 360 && !document.querySelector('.mc-map'); i++) await new Promise((r) => setTimeout(r, 250));
    const el = document.querySelector('.mc-map');
    if (!el) {
      return { error: 'no .mc-map after 90 s',
               loading: !!document.querySelector('.mc-loading'),
               title: document.title,
               hash: location.hash,
               rootChildren: (document.getElementById('root') || {}).childElementCount,
               bodyText: (document.body.innerText || '').replace(/\s+/g, ' ').slice(0, 400),
               errors: (window.__mcErrors || []).slice(0, 10) };
    }
    // Leaflet adds .leaflet-container to the element it initialises, so that class
    // is the signal L.map() has actually run. The presence of .mc-map only proves
    // React rendered the div — the map instance is assigned later, inside an effect,
    // and walking the fiber in that gap finds nothing.
    for (let i = 0; i < 240 && !document.querySelector('.mc-map.leaflet-container, .mc-map .leaflet-container'); i++) {
      await new Promise((r) => setTimeout(r, 250));
    }

    const findMap = () => {
      const key = Object.keys(el).find((k) => k.startsWith('__reactFiber$'));
      if (!key) return null;
      let f = el[key], hops = 0;
      while (f && hops < 30) {
        let h = f.memoizedState, i = 0;
        while (h && i < 40) {
          const v = h.memoizedState;
          if (v && typeof v === 'object' && v.current && typeof v.current.getZoom === 'function') return v.current;
          h = h.next; i++;
        }
        f = f.return; hops++;
      }
      return null;
    };
    let map = null;
    for (let i = 0; i < 240 && !map; i++) {
      map = findMap();
      if (!map) await new Promise((r) => setTimeout(r, 250));
    }
    if (!map) {
      return { error: 'leaflet map not found on the fiber chain after 60 s',
               leafletContainer: !!document.querySelector('.leaflet-container'),
               fiberKey: !!Object.keys(el).find((k) => k.startsWith('__reactFiber$')),
               errors: (window.__mcErrors || []).slice(0, 10) };
    }
    H.map = map;
    map.invalidateSize();

    const mf = await (await fetch('/layers/layers.json')).json();
    H.manifest = mf;
    const Ht = mf.crs.height_units, W = mf.crs.width_units;
    const toCrs = (pts) => pts.map(([fy, fx]) => [Ht * (1 - fy), W * fx]);
    H.geom = {
      H: Ht, W,
      ring: toCrs(mf.footprint.ring_unit_coords),
      swathRing: mf.footprint.swath ? toCrs(mf.footprint.swath.ring_unit_coords) : [],
      nativeZoom: mf.crs.native_zoom,
      fullWidth: (mf.layers.find((l) => l.id === 'hillshade') || {}).width,
      baseProvenance: (mf.layers.find((l) => l.id === 'hillshade') || {}).provenance,
    };
    return { ok: true, zoom: map.getZoom(), size: map.getSize(),
             ring: H.geom.ring.length, swath: H.geom.swathRing.length,
             fullWidth: H.geom.fullWidth, baseProvenance: H.geom.baseProvenance };
  };
  /** Ray-cast crossing number, half-open in latitude — the same test
   *  MissionMap.tsx uses, so agreement between the two is meaningful. */
  H.pip = function (poly, y, x) {
    let inside = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const yi = poly[i][0], xi = poly[i][1], yj = poly[j][0], xj = poly[j][1];
      if (((yi > y) !== (yj > y)) && (x < ((xj - xi) * (y - yi)) / (yj - yi) + xi)) inside = !inside;
    }
    return inside;
  };

  H.tier = function (lat, lng) {
    const g = H.geom;
    if (H.pip(g.ring, lat, lng)) return 'amplitude';
    if (g.swathRing.length > 2 && H.pip(g.swathRing, lat, lng)) return 'swath';
    return 'outside';
  };

  H.relLum = function (r, g, b) {
    const f = (v) => { v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };

  /** Wait on the image's own load state, never on a timer: the overlay swaps a
   *  640 px preview for the full raster asynchronously, and a timed screenshot
   *  can catch the preview and report the wrong picture. */
  H.waitRaster = async function (selector, fullWidth) {
    for (let i = 0; i < 240; i++) {
      const img = document.querySelector(selector);
      if (img && img.complete && img.naturalWidth === fullWidth) {
        return { src: img.currentSrc.split('/').pop(), naturalWidth: img.naturalWidth, waited_ms: i * 125 };
      }
      await new Promise((r) => setTimeout(r, 125));
    }
    const img = document.querySelector(selector);
    return { error: 'raster never reached full width', selector,
             have: img ? { complete: img.complete, naturalWidth: img.naturalWidth,
                           src: img.currentSrc.split('/').pop() } : null };
  };
  H.setLayer = function (label) {
    const btn = [...document.querySelectorAll('.mc-layer')].find((b) => (b.textContent || '').includes(label));
    if (!btn) return { error: 'no layer button matching ' + label,
                       have: [...document.querySelectorAll('.mc-layer')].map((b) => b.textContent.trim()) };
    if (!btn.className.includes('mc-layer--on')) btn.click();
    return { clicked: label, on: btn.className.includes('mc-layer--on') };
  };

  H.setView = function (lat, lng, z) {
    // animate:false only — document.hidden can be true under automation, and then
    // rAF never fires and an animated move stalls forever.
    H.map.invalidateSize();
    H.map.setView([lat, lng], z, { animate: false });
    const c = H.map.getCenter(), s = H.map.getSize();
    return { zoom: H.map.getZoom(), centre: [c.lat, c.lng], size: [s.x, s.y] };
  };

  /**
   * Re-apply the pre-v7 styling in the DOM so BEFORE and AFTER differ in nothing
   * but the thing under test. `state` is 'before' or 'after'.
   */
  H.setState = function (state) {
    const svg = H.map.getPane('mc-void').querySelector('svg');
    const paths = [...svg.querySelectorAll('path')];
    const img = H.map.getContainer().querySelector('img.mc-raster--base');
    if (!H.saved) H.saved = { styles: paths.map((p) => p.getAttribute('style') || ''), filter: img.style.filter || '' };
    if (state === 'before') {
      img.style.filter = 'contrast(1.14) brightness(1.16) saturate(0.92)';
      paths[0].setAttribute('style', 'fill:#03060c;fill-opacity:0.82');   // outer scrim
      if (paths[1]) paths[1].setAttribute('style', 'fill:none;fill-opacity:0');  // hatch off
      if (paths[2]) paths[2].setAttribute('style', 'fill:#03060c;fill-opacity:0.5'); // swath scrim
    } else {
      paths.forEach((p, i) => {
        const s = H.saved.styles[i];
        if (s) p.setAttribute('style', s); else p.removeAttribute('style');
      });
      if (H.saved.filter) img.style.filter = H.saved.filter; else img.style.removeProperty('filter');
    }
    return { state, paths: paths.length, paints: paths.map((p) => {
      const cs = getComputedStyle(p);
      return cs.fill + ' @ ' + cs.fillOpacity + ' [' + (p.getAttribute('class') || '-') + ']';
    }), baseFilter: getComputedStyle(img).filter };
  };
  /**
   * Rasterise the void pane's REAL svg. paint(i) overrides the fills for the
   * confusion test.
   *
   * THE TRAP, MEASURED THE HARD WAY: Leaflet writes an inline
   * transform: translate3d(minX, minY, 0) onto the overlay <svg>. Serialising
   * that element into a standalone data: URL keeps the transform, and it then
   * applies a SECOND time inside the raster — moving the scrim by (-117, -71) on a
   * 1167 x 705 map, about one ribbon width, which put ~46 % of the amplitude
   * ribbon in the "scrimmed" bucket. Stripping style+class off the clone root
   * collapses the confusion matrix onto its diagonal at 99.8 %. Keep the strip.
   *
   * Child style attributes are stripped too, and fill is copied from the source's
   * COMPUTED style, so (a) the BEFORE inline override still rasterises correctly
   * and (b) the hatch's CSS-supplied url(#mc-hatch-void) survives as an attribute.
   */
  H.rasterVoid = async function (paint) {
    const svg = H.map.getPane('mc-void').querySelector('svg');
    if (!svg) return null;
    const clone = svg.cloneNode(true);
    clone.removeAttribute('class');
    clone.removeAttribute('style');
    clone.setAttribute('xmlns', NS);
    const src = svg.querySelectorAll('path'), dst = clone.querySelectorAll('path');
    const paints = [];
    src.forEach((p, i) => {
      const cs = getComputedStyle(p);
      dst[i].removeAttribute('style');
      dst[i].removeAttribute('class');
      dst[i].setAttribute('fill', paint ? paint(i) : cs.fill);
      dst[i].setAttribute('fill-opacity', paint ? '1' : cs.fillOpacity);
      paints.push(cs.fill + ' @ ' + cs.fillOpacity + ' [' + (p.getAttribute('class') || '-') + ']');
    });
    const url = 'data:image/svg+xml;charset=utf-8,'
      + encodeURIComponent(new XMLSerializer().serializeToString(clone));
    const im = new Image();
    await new Promise((res, rej) => { im.onload = res; im.onerror = () => rej(new Error('svg raster failed')); im.src = url; });
    const mr = H.map.getContainer().getBoundingClientRect(), sr = svg.getBoundingClientRect();
    return { im, paints, dx: sr.x - mr.x, dy: sr.y - mr.y, w: sr.width, h: sr.height,
             patternsInDefs: clone.querySelectorAll('pattern').length };
  };
  /** Two canvases: base-only, and base + the real void SVG. Everything else is
   *  averaging. The base is drawn through its own COMPUTED filter, so a CSS
   *  change moves these numbers. */
  H.canvases = async function (paint) {
    const mapEl = H.map.getContainer(), mr = mapEl.getBoundingClientRect();
    const CW = Math.round(mr.width), CH = Math.round(mr.height);
    const mk = () => {
      const c = document.createElement('canvas'); c.width = CW; c.height = CH;
      return c.getContext('2d', { willReadFrequently: true });
    };
    const img = mapEl.querySelector('img.mc-raster--base');
    const filt = img ? getComputedStyle(img).filter : 'NO BASE IMG';
    const drawBase = (ctx) => {
      if (!img) return;
      const ir = img.getBoundingClientRect();
      ctx.filter = filt === 'none' ? 'none' : filt;
      ctx.drawImage(img, ir.x - mr.x, ir.y - mr.y, ir.width, ir.height);
      ctx.filter = 'none';
    };
    const cb = mk(), cc = mk();
    drawBase(cb); drawBase(cc);
    const R = await H.rasterVoid(paint);
    if (R) cc.drawImage(R.im, R.dx, R.dy, R.w, R.h);
    return { CW, CH, filt, R,
             B: cb.getImageData(0, 0, CW, CH).data,
             C: cc.getImageData(0, 0, CW, CH).data };
  };

  H.measure = async function (step) {
    step = step || 3;
    const { CW, CH, filt, R, B, C } = await H.canvases(null);
    const acc = {};
    for (const k of ['amplitude', 'swath', 'outside']) acc[k] = { n: 0, br: 0, bg: 0, bb: 0, cr: 0, cg: 0, cb: 0, bl: 0, cl: 0 };
    let tot = 0;
    for (let y = 0; y < CH; y += step) for (let x = 0; x < CW; x += step) {
      const ll = H.map.containerPointToLatLng([x, y]);
      if (ll.lat < 0 || ll.lat > H.geom.H || ll.lng < 0 || ll.lng > H.geom.W) continue;
      const a = acc[H.tier(ll.lat, ll.lng)], i = (y * CW + x) * 4;
      tot++; a.n++;
      a.br += B[i]; a.bg += B[i + 1]; a.bb += B[i + 2];
      a.cr += C[i]; a.cg += C[i + 1]; a.cb += C[i + 2];
      a.bl += H.relLum(B[i], B[i + 1], B[i + 2]);
      a.cl += H.relLum(C[i], C[i + 1], C[i + 2]);
    }
    const out = { filter: filt, voidPaints: R ? R.paints : 'NO VOID SVG',
                  patternsInDefs: R ? R.patternsInDefs : 0,
                  view: { zoom: H.map.getZoom(), centre: H.map.getCenter(), size: [CW, CH] }, tiers: {} };
    for (const k in acc) {
      const a = acc[k];
      if (!a.n) { out.tiers[k] = { samples: 0 }; continue; }
      const r = (v) => +v.toFixed(1);
      out.tiers[k] = {
        samples: a.n, pct_of_frame_in_view: +(100 * a.n / tot).toFixed(2),
        base_rgb: [r(a.br / a.n), r(a.bg / a.n), r(a.bb / a.n)],
        composite_rgb: [r(a.cr / a.n), r(a.cg / a.n), r(a.cb / a.n)],
        base_relLum: +(a.bl / a.n).toFixed(4),
        composite_relLum: +(a.cl / a.n).toFixed(4),
        fraction_of_base: +((a.cl / a.n) / (a.bl / a.n)).toFixed(4),
      };
    }
    return out;
  };
  /**
   * Is the hatch PAINTING, or has it silently fallen back to a flat fill?
   *
   * A flat fill changes every pixel of the tier by the same amount, so the
   * per-pixel delta is unimodal. A hatch changes on-line pixels more than
   * between-line pixels, so the delta is BIMODAL. sd and the top modes tell the
   * two apart without trusting any style read.
   */
  H.delta = async function (step) {
    step = step || 2;
    const { CW, CH, B, C } = await H.canvases(null);
    const hist = { amplitude: new Array(256).fill(0), swath: new Array(256).fill(0), outside: new Array(256).fill(0) };
    for (let y = 0; y < CH; y += step) for (let x = 0; x < CW; x += step) {
      const ll = H.map.containerPointToLatLng([x, y]);
      if (ll.lat < 0 || ll.lat > H.geom.H || ll.lng < 0 || ll.lng > H.geom.W) continue;
      const i = (y * CW + x) * 4;
      hist[H.tier(ll.lat, ll.lng)][Math.max(0, Math.min(255, B[i + 1] - C[i + 1]))]++;
    }
    const stats = {};
    for (const k in hist) {
      const h = hist[k], n = h.reduce((s, v) => s + v, 0);
      if (!n) { stats[k] = { n: 0 }; continue; }
      const mean = h.reduce((s, v, d) => s + v * d, 0) / n;
      const varc = h.reduce((s, v, d) => s + v * (d - mean) ** 2, 0) / n;
      const modes = h.map((v, d) => ({ d, pct: +(100 * v / n).toFixed(1) }))
        .sort((a, b) => b.pct - a.pct).slice(0, 5);
      stats[k] = { n, mean: +mean.toFixed(2), sd: +Math.sqrt(varc).toFixed(2), modes };
    }
    return stats;
  };

  /** Does pointInPolygon agree with what the browser actually filled? */
  H.confusion = async function (step) {
    step = step || 4;
    const mr = H.map.getContainer().getBoundingClientRect();
    const CW = Math.round(mr.width), CH = Math.round(mr.height);
    // Void path 0 and path 1 both cover the OUTER region (flat tint, then hatch);
    // path 2 is the swath tint. Painting per REGION, not per index, is what makes
    // this test measure geometry rather than the number of layers stacked.
    const R = await H.rasterVoid((i) => (i === 2 ? '#ff00ff' : '#ffc800'));
    if (!R) return { error: 'NO VOID SVG' };
    const cv = document.createElement('canvas'); cv.width = CW; cv.height = CH;
    const ctx = cv.getContext('2d', { willReadFrequently: true });
    ctx.drawImage(R.im, R.dx, R.dy, R.w, R.h);
    const D = ctx.getImageData(0, 0, CW, CH).data;
    const conf = {};
    for (let y = 0; y < CH; y += step) for (let x = 0; x < CW; x += step) {
      const ll = H.map.containerPointToLatLng([x, y]);
      if (ll.lat < 0 || ll.lat > H.geom.H || ll.lng < 0 || ll.lng > H.geom.W) continue;
      const i = (y * CW + x) * 4;
      const painted = D[i + 3] < 8 ? 'unpainted'
        : (D[i] > 128 && D[i + 1] > 128 && D[i + 2] < 128) ? 'outerVoid'
        : (D[i] > 128 && D[i + 2] > 128 && D[i + 1] < 128) ? 'swathTint' : 'mixed/AA';
      const key = H.tier(ll.lat, ll.lng) + ' -> ' + painted;
      conf[key] = (conf[key] || 0) + 1;
    }
    const good = (conf['amplitude -> unpainted'] || 0) + (conf['outside -> outerVoid'] || 0)
      + (conf['swath -> swathTint'] || 0);
    const all = Object.values(conf).reduce((s, v) => s + v, 0);
    return { conf, onDiagonalPct: +(100 * good / all).toFixed(2), samples: all };
  };
  /** Read the counts the map itself computed, rather than recomputing them here —
   *  the point is to check what a viewer is told. */
  H.coverage = function () {
    const txt = (sel) => { const e = document.querySelector(sel); return e ? e.textContent.trim() : null; };
    const rows = [...document.querySelectorAll('.mc-cov-row')].map((r) => r.textContent.replace(/\s+/g, ' ').trim());
    return {
      panel: !!document.querySelector('.mc-map-coverage'),
      rows,
      sites: txt('.mc-cov-sites'),
      target: txt('.mc-cov-target'),
      routes: [...document.querySelectorAll('.mc-cov-route')].map((e) => e.textContent.trim()),
    };
  };

  /** Style-read proofs 1 and 2: the pattern exists in the pane's defs, and CSS
   *  beat Leaflet's fill presentation attribute on the hatch path. */
  H.hatchProof = function () {
    const svg = H.map.getPane('mc-void').querySelector('svg');
    const hatch = svg ? svg.querySelector('path.mc-void-hatch') : null;
    return {
      svgRootExists: !!svg,
      patternInDefs: !!(svg && svg.querySelector('#mc-hatch-void')),
      patternCount: svg ? svg.querySelectorAll('pattern').length : 0,
      hatchPathExists: !!hatch,
      computedFill: hatch ? getComputedStyle(hatch).fill : null,
      computedFillOpacity: hatch ? getComputedStyle(hatch).fillOpacity : null,
      fellBackToFlat: !!(hatch && hatch.className.baseVal.includes('mc-void-scrim--flat')),
    };
  };

  /** Which data mode the app is actually in — a report that does not say this can
   *  be read as describing the wrong build. */
  /** Which data mode the app is actually in, and WHICH BACKEND ANSWERED — a report
   *  that does not say this can be read as describing the wrong build. Measured
   *  once: frontend/.env.local can point the dev server at the deployed backend, in
   *  which case every target / waypoint number on screen is that host's, not the
   *  local pipeline's. Text nodes are read from chips only, and STYLE / SCRIPT are
   *  excluded — Vite injects mc.css as a <style> element whose text matches these
   *  keywords, and an unfiltered walk dumps the whole stylesheet into the log.
   *  Known limitation, left as-is because the network fields above are the load-
   *  bearing ones: the children.length === 0 test skips .mc-badge, whose text sits
   *  next to a child dot <span>, so the topbar's "VERDICT · …" and "STUDIO · …"
   *  badges do not appear in chips. Read dataMode/apiOrigin for the mode, not chips. */
  H.mode = async function () {
    const SKIP = /^(STYLE|SCRIPT|TITLE|NOSCRIPT|TEMPLATE|LINK|META)$/;
    const chips = [...document.querySelectorAll('.mc-topbar *, .mc-verdict *, .mc-map-coverage *')]
      .filter((e) => !SKIP.test(e.tagName) && e.children.length === 0)
      .map((e) => (e.textContent || '').replace(/\s+/g, ' ').trim())
      .filter((t) => t.length > 0 && t.length <= 90 && /VERDICT|STUDIO|DEMO|REAL|PRECOMPUTED|SIMULATED|COVERAGE|PLACEHOLDER/i.test(t));

    const req = performance.getEntriesByType('resource')
      .map((r) => r.name)
      .filter((n) => /\/api\/mission\//.test(n));
    const missionUrl = req.length ? req[req.length - 1] : null;

    let dataMode = null;
    if (missionUrl) {
      try {
        const r = await fetch(missionUrl, { signal: AbortSignal.timeout(15000) });
        dataMode = (await r.json()).data_mode ?? null;
      } catch (e) { dataMode = 'unreadable: ' + (e && e.name); }
    }
    return { chips: [...new Set(chips)].slice(0, 8), missionUrl, dataMode, apiOrigin: missionUrl ? new URL(missionUrl).origin : null };
  };

  H.consoleErrors = function () { return (window.__mcErrors || []).slice(0, 20); };

  window.__mc = H;
  return 'installed';
}
// ── the run ────────────────────────────────────────────────────────
const PASSES = [
  { state: 'before', layer: 'Surface Relief',      id: 'hillshade',   file: 'map_before_relief.png' },
  { state: 'before', layer: 'Radar Signals (CPR)', id: 'cpr_heatmap', file: 'map_before_cpr.png' },
  { state: 'after',  layer: 'Radar Signals (CPR)', id: 'cpr_heatmap', file: 'map_after_cpr.png' },
  { state: 'after',  layer: 'Surface Relief',      id: 'hillshade',   file: 'map_after_relief.png' },
];

const ERR_HOOK = 'window.__mcErrors=[];'
  + "addEventListener('error',function(e){window.__mcErrors.push('error: '+e.message)});"
  + "addEventListener('unhandledrejection',function(e){window.__mcErrors.push('rejection: '+e.reason)});"
  + '(function(){var ce=console.error;console.error=function(){'
  + "window.__mcErrors.push('console.error: '+Array.prototype.map.call(arguments,String).join(' '));"
  + 'return ce.apply(console,arguments)}})();';

function python(args) {
  for (const exe of ['python', 'py', 'python3']) {
    const r = spawnSync(exe, args, { cwd: ROOT, encoding: 'utf8',
                                     env: { ...process.env, PYTHONIOENCODING: 'utf-8' } });
    if (!r.error) return r.stdout + (r.stderr || '');
  }
  return '  (no python on PATH — histogram skipped)';
}

async function main() {
  log('\n══ verify_map ═════════════════════════════════════════════════════');
  log(`  url     ${CFG.url}`);
  log(`  out     ${CFG.out}`);
  log(`  view    zoom ${CFG.zoom}  centre [${CFG.centre.join(', ')}]  viewport ${CFG.width}x${CFG.height}`);

  // Vite here binds IPv6-only ([::1]:3000), so a hardcoded 127.0.0.1 gets
  // ECONNREFUSED while localhost works. Probe both spellings and keep whichever
  // answers, instead of telling the user their running server is down.
  const probe = async (u) => {
    try {
      const r = await fetch(new URL(u).origin, { signal: AbortSignal.timeout(4000) });
      return r.ok || r.status < 500;
    } catch { return false; }
  };
  const swap = (u) => {
    const x = new URL(u);
    x.hostname = x.hostname === 'localhost' ? '127.0.0.1' : 'localhost';
    return x.toString();
  };
  if (!(await probe(CFG.url))) {
    const alt = swap(CFG.url);
    if (await probe(alt)) {
      log(`  note    ${new URL(CFG.url).origin} refused; using ${new URL(alt).origin} instead`);
      CFG.url = alt;
    } else {
      fail(`dev server not answering at ${new URL(CFG.url).origin} or ${new URL(alt).origin}.\n`
        + '  Start it first:  npm run dev --prefix frontend');
    }
  }

  if (!existsSync(CFG.out)) mkdirSync(CFG.out, { recursive: true });

  const { proc, profile, bin } = launchBrowser();
  log(`  browser ${bin}`);
  const cdp = await CDP.connect(await devtoolsUrl(profile, proc));
  const { targetId } = await cdp.send('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await cdp.send('Target.attachToTarget', { targetId, flatten: true });
  const S = (m, p) => cdp.send(m, p, sessionId);
  await S('Page.enable');
  await S('Runtime.enable');
  await S('Emulation.setDeviceMetricsOverride',
    { width: CFG.width, height: CFG.height, deviceScaleFactor: 1, mobile: false });
  await S('Page.addScriptToEvaluateOnNewDocument', { source: ERR_HOOK });

  const ev = async (expression) => {
    const r = await S('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) {
      throw new Error(`page threw: ${r.exceptionDetails.exception?.description
        || r.exceptionDetails.text} \n  while evaluating: ${expression.slice(0, 160)}`);
    }
    return r.result.value;
  };

  const loaded = cdp.once('Page.loadEventFired', 45000);
  await S('Page.navigate', { url: CFG.url });
  await loaded;

  await ev(`(${harness.toString()})()`);
  const init = await ev('window.__mc.init()');
  if (init.error) fail(`harness init failed: ${init.error}\n  ${JSON.stringify(init, null, 2).replace(/\n/g, '\n  ')}`);
  log(`  map     ${init.size.x}x${init.size.y} px · ring ${init.ring} pts · swath ${init.swath} pts`
    + `\n  base    ${init.fullWidth} px wide · provenance "${init.baseProvenance}"`);

  const mode = await ev('window.__mc.mode()');
  log(`  backend data_mode ${mode.dataMode} · api ${mode.apiOrigin}`
    + `\n  chips   ${(mode.chips || []).join(' | ') || '(none)'}`);

  const report = { generated_utc: new Date().toISOString(), url: CFG.url, browser: bin,
                   viewport: [CFG.width, CFG.height], view: { zoom: CFG.zoom, centre: CFG.centre },
                   sampling_step_px: CFG.step, mode, init, passes: {}, gate: {} };

  for (const p of PASSES) {
    const key = `${p.state}_${p.id}`;
    await ev(`window.__mc.setState('${p.state}')`);
    const sel = await ev(`window.__mc.setLayer(${JSON.stringify(p.layer)})`);
    if (sel.error) fail(`${sel.error}\n  have: ${JSON.stringify(sel.have)}`);
    // Wait on the image, not the clock: the base is always present, the science
    // overlay only for non-hillshade layers.
    const waited = { base: await ev(`window.__mc.waitRaster('img.mc-raster--base', ${init.fullWidth})`) };
    if (p.id !== 'hillshade') {
      waited.science = await ev(`window.__mc.waitRaster('img.mc-raster--science', ${init.fullWidth})`);
    }
    for (const [k, w] of Object.entries(waited)) if (w.error) fail(`${k}: ${w.error} ${JSON.stringify(w.have)}`);
    const view = await ev(`window.__mc.setView(${CFG.centre[0]}, ${CFG.centre[1]}, ${CFG.zoom})`);
    const paints = await ev(`window.__mc.setState('${p.state}')`);
    const m = await ev(`window.__mc.measure(${CFG.step})`);
    const shot = await S('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
    writeFileSync(path.join(CFG.out, p.file), Buffer.from(shot.data, 'base64'));
    report.passes[key] = { ...p, view, waited, baseFilter: paints.baseFilter,
                           voidPaints: paints.paints, tiers: m.tiers,
                           patternsInDefs: m.patternsInDefs };
    log(`  shot    docs/${p.file}  (${p.state}, ${p.layer}, base filter "${paints.baseFilter}")`);
  }
  // The state is 'after' at this point (last pass), which is the one whose hatch,
  // geometry agreement and coverage counts the gate asks about.
  report.hatchProof = await ev('window.__mc.hatchProof()');
  report.delta = await ev(`window.__mc.delta(${Math.max(1, CFG.step - 1)})`);
  report.confusion = await ev('window.__mc.confusion(4)');
  report.coverage = await ev('window.__mc.coverage()');
  report.pageErrors = await ev('window.__mc.consoleErrors()');

  log('\n── hillshade histogram, before and after the filter change ─────────');
  report.histogram_old = python(['backend/scripts/hillshade_histogram.py', '1.14', '1.16']);
  report.histogram_new = python(['backend/scripts/hillshade_histogram.py', '1.04', '1.02']);
  log(report.histogram_old.trimEnd());
  log(report.histogram_new.trimEnd());

  // ── gate ─────────────────────────────────────────────────────────
  const B = report.passes.before_hillshade.tiers, A = report.passes.after_hillshade.tiers;
  const g = report.gate;
  g.never_observed_at_least_0_60 = { value: A.outside.fraction_of_base, pass: A.outside.fraction_of_base >= 0.60 };
  g.never_observed_target_0_70 = { value: A.outside.fraction_of_base, pass: A.outside.fraction_of_base >= 0.68 };
  g.pointed_target_0_90 = { value: A.swath.fraction_of_base, pass: A.swath.fraction_of_base >= 0.88 };
  g.ribbon_untouched = { value: A.amplitude.fraction_of_base, pass: A.amplitude.fraction_of_base >= 0.99 };
  g.tiers_separable = (() => {
    const v = [A.amplitude.fraction_of_base, A.swath.fraction_of_base, A.outside.fraction_of_base];
    const gaps = [v[0] - v[1], v[1] - v[2]];
    // JND for a large flat field is roughly 1-2 %; require every step to clear 4 %.
    return { gaps: gaps.map((x) => +x.toFixed(4)), pass: gaps.every((x) => x >= 0.04) };
  })();
  g.hatch_rendered = {
    patternInDefs: report.hatchProof.patternInDefs,
    computedFill: report.hatchProof.computedFill,
    fellBackToFlat: report.hatchProof.fellBackToFlat,
    delta_sd_outside: report.delta.outside.sd,
    delta_sd_swath: report.delta.swath.sd,
    pass: report.hatchProof.patternInDefs
      && /url\(/.test(report.hatchProof.computedFill || '')
      && !report.hatchProof.fellBackToFlat
      && report.delta.outside.sd > 3 * report.delta.swath.sd / 2,
  };
  g.geometry_agrees = { value: report.confusion.onDiagonalPct, pass: report.confusion.onDiagonalPct >= 99 };
  g.no_page_errors = { value: report.pageErrors, pass: report.pageErrors.length === 0 };
  // ── print ────────────────────────────────────────────────────────
  const row = (label, b, a) => log(
    `  ${label.padEnd(22)}${String(b.pct_of_frame_in_view).padStart(6)} %   `
    + `${b.composite_rgb.map((v) => String(v).padStart(5)).join(',')}  ${String(b.fraction_of_base).padStart(6)}   `
    + `${a.composite_rgb.map((v) => String(v).padStart(5)).join(',')}  ${String(a.fraction_of_base).padStart(6)}`);

  log('\n── tier luminance, SAMPLED OFF THE CANVAS (Surface Relief pass) ────');
  log('  tier                  % frame   BEFORE composite rgb  /base   AFTER composite rgb   /base');
  row('amplitude ribbon', B.amplitude, A.amplitude);
  row('pointed, no return', B.swath, A.swath);
  row('never observed', B.outside, A.outside);

  const C = report.passes.before_cpr_heatmap.tiers, D2 = report.passes.after_cpr_heatmap.tiers;
  log('\n── same, with Radar Signals (CPR) selected ────────────────────────');
  row('amplitude ribbon', C.amplitude, D2.amplitude);
  row('pointed, no return', C.swath, D2.swath);
  row('never observed', C.outside, D2.outside);

  log('\n── hatch rendered, not fallen back ────────────────────────────────');
  log(`  pattern in defs        ${report.hatchProof.patternInDefs} (${report.hatchProof.patternCount} pattern node/s)`);
  log(`  computed fill          ${report.hatchProof.computedFill} @ ${report.hatchProof.computedFillOpacity}`);
  log(`  flat-fallback class    ${report.hatchProof.fellBackToFlat}`);
  for (const k of ['outside', 'swath']) {
    const d = report.delta[k];
    log(`  delta ${k.padEnd(10)} n ${String(d.n).padStart(7)}  mean ${String(d.mean).padStart(6)}  `
      + `sd ${String(d.sd).padStart(5)}  modes ${d.modes.map((m) => `${m.d}:${m.pct}%`).join('  ')}`);
  }
  log('  (a flat fill moves every pixel equally -> unimodal, low sd; a hatch does not)');

  log('\n── geometry vs. what the browser filled ───────────────────────────');
  log(`  on-diagonal ${report.confusion.onDiagonalPct} % of ${report.confusion.samples} samples`);
  Object.entries(report.confusion.conf).sort((a, b) => b[1] - a[1])
    .forEach(([k, v]) => log(`    ${k.padEnd(34)}${String(v).padStart(7)}`));

  log('\n── coverage, as the map itself reports it ─────────────────────────');
  report.coverage.rows.forEach((r) => log(`  ${r}`));
  log(`  ${report.coverage.sites}`);
  log(`  ${report.coverage.target}`);
  report.coverage.routes.forEach((r) => log(`  ${r}`));

  log('\n── gate ───────────────────────────────────────────────────────────');
  let allPass = true;
  for (const [k, v] of Object.entries(g)) {
    allPass = allPass && v.pass;
    const detail = v.value !== undefined ? JSON.stringify(v.value)
      : v.gaps !== undefined ? `gaps ${JSON.stringify(v.gaps)}` : '';
    log(`  ${v.pass ? 'PASS' : 'FAIL'}  ${k.padEnd(30)} ${String(detail).slice(0, 60)}`);
  }
  if (report.pageErrors.length) report.pageErrors.forEach((e) => log(`        page error: ${e}`));

  writeFileSync(path.join(CFG.out, 'verify_map.json'), JSON.stringify(report, null, 2));
  log(`\n  wrote   docs/verify_map.json`);
  log(`  ${allPass ? 'GATE PASS' : 'GATE FAIL'}\n`);

  cdp.ws.close();
  proc.kill();
  try { rmSync(profile, { recursive: true, force: true }); } catch { /* profile is in tmp */ }
  process.exit(allPass ? 0 : 1);
}

main().catch((e) => { console.error(e); process.exit(3); });
