/**
 * verify_v8_view.mjs — the four v8 / Step-4b view checks, as numbers.
 *
 *     node frontend/scripts/verify_v8_view.mjs
 *
 * verify_map.mjs cannot answer these: it asserts the mc-void pane and the
 * .mc-map-coverage key EXIST, and v8 deleted both. Running it now crashes on
 * getPane('mc-void').querySelector, which is a true negative reported as a tool
 * failure. This script asks the four questions v8 actually raises:
 *
 *   (a) is the coverage panel gone from the DOM?
 *   (b) is the mc-void pane gone from the map?
 *   (c) is the OPENING view the 40 km home window, not the 1:2.93 full strip?
 *   (d) does "Reset view" return to that window?
 *
 * plus a census of the five landing sites and three rover routes: how many are
 * drawn at all, and how many are drawn in amber (#f2c14e = "not measured here").
 * v7 drew both classes at weight 1 / opacity 0.35 / fill:false, which is how all
 * five sites became invisible; "visible" is therefore a thing to MEASURE, not to
 * assume from the fact that a marker object exists.
 *
 * ANIMATION. document.hidden can be true under automation, and then rAF never
 * fires and every animated Leaflet move stalls forever. MissionControl's reset
 * button calls flyToBounds, which is animated. So check (d) FIRST measures
 * whether rAF actually fires in this browser, and only clicks the button if it
 * does; otherwise it says so and falls back to reading the flyToBounds
 * DESTINATION off a moveend-free instrumented map. The fallback is labelled as a
 * weaker check in the output rather than silently reported as the same thing.
 *
 * ZERO NEW DEPENDENCIES — CDP over the global WebSocket in Node 22, same as
 * verify_map.mjs. Nothing added to package.json.
 */
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..');

const argv = process.argv.slice(2);
const arg = (n, d) => { const i = argv.indexOf(`--${n}`); return i >= 0 && argv[i + 1] ? argv[i + 1] : d; };
const CFG = {
  url: arg('url', process.env.VERIFY_URL || 'http://localhost:3000/#/mission'),
  out: path.resolve(ROOT, arg('out', 'docs')),
  width: Number(arg('width', '1600')),
  height: Number(arg('height', '900')),
  // --tag before keeps the Pass A artifacts alongside the Pass B ones instead of
  // overwriting them. Working rule 1 allows exactly one "before" pass when the
  // handoff asks for before/after evidence, and V10.1 Step 0 asks for it.
  tag: arg('tag', ''),
};
const SUF = CFG.tag ? `.${CFG.tag}` : '';
const AMBER = '#f2c14e';

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
const fail = (m) => { console.error(`\n  verify_v8_view: ${m}\n`); process.exit(2); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function launchBrowser() {
  const bin = BROWSERS.find((b) => existsSync(b));
  if (!bin) fail(`no Chrome or Edge found. Set VERIFY_BROWSER=<path>. Tried:\n    ${BROWSERS.join('\n    ')}`);
  const profile = mkdtempSync(path.join(tmpdir(), 'verify-v8-'));
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
    this.ws = ws; this.id = 0; this.pending = new Map(); this.waiters = [];
    ws.onmessage = (ev) => {
      const m = JSON.parse(typeof ev.data === 'string' ? ev.data : String(ev.data));
      if (m.id && this.pending.has(m.id)) {
        const { resolve, reject } = this.pending.get(m.id);
        this.pending.delete(m.id);
        if (m.error) reject(new Error(`${m.error.message} (${m.error.code})`)); else resolve(m.result);
      } else if (m.method) {
        this.waiters = this.waiters.filter((w) => (w.method !== m.method ? true : (w.resolve(m.params), false)));
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

  once(method, timeout = 45000) {
    return new Promise((resolve, reject) => {
      const w = { method, resolve };
      this.waiters.push(w);
      setTimeout(() => { this.waiters = this.waiters.filter((x) => x !== w); reject(new Error(`timed out waiting for ${method}`)); }, timeout);
    });
  }
}

/** Runs in the page. Shipped with .toString() so it stays real, lintable source. */
function harness() {
  const H = {};
  const HOME_WINDOW_KM = 40;      // must track MissionMap.tsx:300

  H.init = async function () {
    for (let i = 0; i < 360 && !document.querySelector('.mc-map'); i++) await new Promise((r) => setTimeout(r, 250));
    const el = document.querySelector('.mc-map');
    if (!el) {
      return { error: 'no .mc-map after 90 s', hash: location.hash,
               loading: !!document.querySelector('.mc-loading'),
               bodyText: (document.body.innerText || '').replace(/\s+/g, ' ').slice(0, 400),
               errors: (window.__mcErrors || []).slice(0, 10) };
    }
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
    for (let i = 0; i < 240 && !map; i++) { map = findMap(); if (!map) await new Promise((r) => setTimeout(r, 250)); }
    if (!map) return { error: 'leaflet map not found on the fiber chain after 60 s',
                       errors: (window.__mcErrors || []).slice(0, 10) };
    H.map = map;

    const mf = await (await fetch('/layers/layers.json')).json();
    H.mf = mf;
    const Ht = mf.crs.height_units, W = mf.crs.width_units;
    const toCrs = (pts) => pts.map(([fy, fx]) => [Ht * (1 - fy), W * fx]);
    const ring = toCrs(mf.footprint.ring_unit_coords);
    const centre = ring.length
      ? [ring.reduce((s, p) => s + p[0], 0) / ring.length, ring.reduce((s, p) => s + p[1], 0) / ring.length]
      : [Ht / 2, W / 2];
    // Recomputed here exactly as buildGeometry does, so check (c) compares the
    // live view against an independently derived window rather than against a
    // number the component reports about itself.
    const half = (HOME_WINDOW_KM * 1000) / mf.crs.metres_per_unit / 2;
    H.geom = {
      H: Ht, W, ring, centre, mpu: mf.crs.metres_per_unit, homeKm: HOME_WINDOW_KM,
      home: [[Math.max(0, centre[0] - half), Math.max(0, centre[1] - half)],
             [Math.min(Ht, centre[0] + half), Math.min(W, centre[1] + half)]],
      full: [[0, 0], [Ht, W]],
    };
    return { ok: true, zoom: map.getZoom(), size: map.getSize(), ringPts: ring.length,
             homeUnits: H.geom.home, mpu: H.geom.mpu };
  };

  /** (a) the coverage key. Every selector the v7 key used, all expected absent. */
  H.coveragePanel = function () {
    const sels = ['.mc-map-coverage', '.mc-cov-row', '.mc-cov-sites', '.mc-cov-target', '.mc-cov-route'];
    const found = {};
    sels.forEach((s) => { found[s] = document.querySelectorAll(s).length; });
    // Also catch a renamed-but-still-present key: any element whose text reads
    // like the old legend. Absence of a class is weaker than absence of the thing.
    const legendish = [...document.querySelectorAll('.mc-map *')]
      .filter((e) => e.children.length === 0)
      .map((e) => (e.textContent || '').replace(/\s+/g, ' ').trim())
      .filter((t) => /never observed|pointed, no return|no radar coverage/i.test(t));
    return { found, total: Object.values(found).reduce((a, b) => a + b, 0),
             legendishTextInMap: [...new Set(legendish)].slice(0, 6) };
  };

  /** (b) the mc-void pane. */
  H.voidPane = function () {
    let pane = null, threw = null;
    try { pane = H.map.getPane('mc-void') || null; } catch (e) { threw = String(e && e.message); }
    const panes = Object.keys(H.map.getPanes());
    return {
      paneObject: pane ? 'PRESENT' : 'absent', threw,
      panesOnMap: panes,
      domNodes: document.querySelectorAll('.leaflet-mc-void-pane, [class*="mc-void"]').length,
      hatchPattern: document.querySelectorAll('#mc-hatch-void, pattern').length,
    };
  };

  /** Visible bounds, plus the same numbers in km so the strip is unmistakable. */
  H.viewport = function () {
    const b = H.map.getBounds(), g = H.geom;
    const s = b.getSouthWest(), n = b.getNorthEast();
    const hUnits = n.lat - s.lat, wUnits = n.lng - s.lng;
    const homeH = g.home[1][0] - g.home[0][0], homeW = g.home[1][1] - g.home[0][1];
    return {
      zoom: H.map.getZoom(),
      centre: [+H.map.getCenter().lat.toFixed(4), +H.map.getCenter().lng.toFixed(4)],
      units: { h: +hUnits.toFixed(4), w: +wUnits.toFixed(4) },
      km: { h: +(hUnits * g.mpu / 1000).toFixed(2), w: +(wUnits * g.mpu / 1000).toFixed(2) },
      home_km: { h: +(homeH * g.mpu / 1000).toFixed(2), w: +(homeW * g.mpu / 1000).toFixed(2) },
      full_km: { h: +(g.H * g.mpu / 1000).toFixed(2), w: +(g.W * g.mpu / 1000).toFixed(2) },
      // The discriminator: the full strip is 2.93:1 and 165 km along-track. A 40 km
      // window is neither. Ratio is of the VISIBLE frame content, not the viewport.
      contains_full_width: wUnits >= g.W * 0.98,
      centred_on_ribbon: Math.abs(H.map.getCenter().lat - g.centre[0]) < homeH
                      && Math.abs(H.map.getCenter().lng - g.centre[1]) < homeW,
    };
  };

  /** Does requestAnimationFrame actually fire here? Everything about check (d)
   *  depends on the answer, so it is measured rather than assumed either way. */
  H.rafFires = function () {
    return new Promise((resolve) => {
      let fired = false;
      requestAnimationFrame(() => { fired = true; });
      setTimeout(() => resolve({ fired, documentHidden: document.hidden,
                                 visibilityState: document.visibilityState }), 1200);
    });
  };

  /** (d) Reset view. Pans and zooms away first — a reset that "works" because
   *  nothing moved proves nothing. */
  H.reset = async function (rafWorks) {
    const g = H.geom;
    const away = [g.H * 0.9, g.W * 0.06];
    H.map.setView(away, Math.max(0, H.map.getZoom() - 2), { animate: false });
    const before = H.viewport();

    const btn = [...document.querySelectorAll('button')]
      .find((b) => (b.getAttribute('title') || '') === 'Reset view');
    if (!btn) return { error: 'no button[title="Reset view"] found', before,
                       buttons: [...document.querySelectorAll('.mc-tool')].map((b) => b.getAttribute('title')) };

    // Instrument the destination regardless of whether the animation can run:
    // flyToBounds computes its target synchronously via getBoundsZoom + fitBounds
    // maths, so capturing the call arguments is a real measurement of intent even
    // when rAF is dead. It is reported as intent, never as arrival.
    H.flyCalls = [];
    const realFly = H.map.flyToBounds.bind(H.map);
    H.map.flyToBounds = function (b, o) { H.flyCalls.push({ bounds: [[b[0][0], b[0][1]], [b[1][0], b[1][1]]] }); return realFly(b, o); };

    btn.click();

    let arrived = null;
    if (rafWorks) {
      await new Promise((resolve) => {
        let done = false;
        const fin = () => { if (!done) { done = true; H.map.off('moveend', fin); H.map.off('zoomend', fin); resolve(); } };
        H.map.on('moveend', fin); H.map.on('zoomend', fin);
        setTimeout(fin, 8000);
      });
      await new Promise((r) => setTimeout(r, 400));
      arrived = H.viewport();
    }
    H.map.flyToBounds = realFly;

    // Second, animation-free measurement of the same intent: what fitBounds on the
    // recorded destination actually produces. This is the number to trust when rAF
    // is dead, and a cross-check on `arrived` when it is not.
    let fitted = null;
    const dest = H.flyCalls.length ? H.flyCalls[H.flyCalls.length - 1].bounds : null;
    if (dest) { H.map.fitBounds(dest, { animate: false }); fitted = H.viewport(); }

    return { before, arrived, fitted, flyCalls: H.flyCalls,
             destMatchesHome: dest ? (Math.abs(dest[0][0] - g.home[0][0]) < 1e-6
               && Math.abs(dest[0][1] - g.home[0][1]) < 1e-6
               && Math.abs(dest[1][0] - g.home[1][0]) < 1e-6
               && Math.abs(dest[1][1] - g.home[1][1]) < 1e-6) : false };
  };

  /**
   * Sites and routes: drawn at all, and drawn in amber?
   *
   * Read off COMPUTED stroke and the geometry's own bounding box, not off the
   * options objects. v7's regression was weight 1 / opacity 0.35 / fill:false —
   * every marker existed, every marker was invisible. So "visible" here means a
   * measured stroke-width, a measured opacity and a non-degenerate box.
   */
  H.overlays = function () {
    const norm = (c) => {
      const m = /^rgba?\(([^)]+)\)$/.exec(c || '');
      if (!m) return (c || '').toLowerCase();
      const [r, g, b] = m[1].split(',').map((v) => parseInt(v, 10));
      return '#' + [r, g, b].map((v) => v.toString(16).padStart(2, '0')).join('');
    };
    const amber = norm('rgb(242, 193, 78)');
    const rows = [];
    document.querySelectorAll('.leaflet-overlay-pane path, .leaflet-pane path').forEach((p) => {
      const cs = getComputedStyle(p);
      const bb = p.getBBox ? p.getBBox() : { width: 0, height: 0 };
      const d = p.getAttribute('d') || '';
      const cmds = (d.match(/[MLAaCc]/g) || []).length;
      rows.push({
        kind: cs.fill && cs.fill !== 'none' && /a\s*[\d.]+\s*\)|^#|rgb/.test(cs.fill) && cmds <= 12
          ? 'marker' : 'line',
        stroke: norm(cs.stroke),
        strokeWidth: +parseFloat(cs.strokeWidth || '0').toFixed(2),
        strokeOpacity: +parseFloat(cs.strokeOpacity || '1').toFixed(2),
        fill: norm(cs.fill), fillOpacity: +parseFloat(cs.fillOpacity || '0').toFixed(2),
        dashed: (cs.strokeDasharray || 'none') !== 'none',
        box: [Math.round(bb.width), Math.round(bb.height)],
        amber: norm(cs.stroke) === amber,
        // STYLED is the v7 failure condition inverted, and it is geometry-free on
        // purpose: v7 shipped { weight: 1, opacity: 0.35, fill: false }, so the
        // defect was entirely in the paint. A path can fail `visible` merely by
        // being scrolled off-screen, but it can only fail `styled` by being drawn
        // too faint to see. Gate on styled; report visible.
        styled: parseFloat(cs.strokeWidth || '0') >= 1
             && parseFloat(cs.strokeOpacity || '1') >= 0.3,
        // Visible = styled AND geometrically present in the current viewport.
        visible: parseFloat(cs.strokeWidth || '0') >= 1
              && parseFloat(cs.strokeOpacity || '1') >= 0.3
              && (bb.width > 0.5 || bb.height > 0.5),
      });
    });
    const markers = rows.filter((r) => r.kind === 'marker');
    const lines = rows.filter((r) => r.kind === 'line');
    const tally = (a) => ({ n: a.length, visible: a.filter((r) => r.visible).length,
                            styled: a.filter((r) => r.styled).length,
                            faint: a.filter((r) => !r.styled).length,
                            amber: a.filter((r) => r.amber).length,
                            amberAndVisible: a.filter((r) => r.amber && r.visible).length });
    return { paths: rows.length, markers: tally(markers), lines: tally(lines),
             faintPaths: rows.filter((r) => !r.styled)
               .map((r) => ({ kind: r.kind, stroke: r.stroke, w: r.strokeWidth,
                              o: r.strokeOpacity, box: r.box })).slice(0, 12),
             sample: rows.slice(0, 24) };
  };

  /**
   * Step 0 — the raster overlay inventory.
   *
   * The question is whether more than one image is being painted per active layer.
   * A soft low-resolution copy showing through a sharp one is what a washed-out
   * blob looks like, and the only way to tell that from real terrain is to count
   * the <img> nodes and read their natural sizes: the preview is 640 px wide, the
   * full raster is 6618. So this reports naturalWidth, not just the URL — a cache
   * serving a stale file keeps the URL and changes the pixels.
   *
   * expectedActiveLayers is derived from the UI, not asserted: the base hillshade
   * is always mounted, plus one science overlay whenever the selected layer is not
   * the base itself. `.mc-layer--on` is the selected-button class in
   * MissionControl.tsx:222, and the last two buttons are the sites/route toggles
   * rather than raster layers, so they are excluded by label.
   */
  H.rasterInventory = function () {
    const nodes = [...document.querySelectorAll('.mc-map .leaflet-image-layer')].map((n) => {
      const cs = getComputedStyle(n);
      let pane = 'unknown';
      for (const [name, el] of Object.entries(H.map.getPanes())) {
        if (el.contains(n)) { pane = name; break; }
      }
      return {
        src: (n.getAttribute('src') || '').replace(/^.*\/layers\//, 'layers/'),
        isPreview: /\.preview\.webp(\?|$)/.test(n.getAttribute('src') || ''),
        natural: [n.naturalWidth, n.naturalHeight],
        transform: cs.transform === 'none' ? n.style.transform : cs.transform,
        opacity: +parseFloat(cs.opacity || '1').toFixed(3),
        className: n.className,
        pane,
        alt: n.getAttribute('alt') || '',
      };
    });

    const overlays = [];
    // Duck-typed, not `instanceof L.ImageOverlay`: Leaflet is bundled by Vite, so
    // there is no global `L` in the page and the instanceof would throw a
    // ReferenceError before any fallback could run. An ImageOverlay carries a
    // string _url, an _image node and getBounds; a TileLayer carries _tiles.
    H.map.eachLayer((l) => {
      const looksLikeImageOverlay = typeof l._url === 'string' && typeof l.getBounds === 'function'
        && !l._tiles && (l._image !== undefined || /leaflet-image-layer/.test(String(l.options && l.options.className)));
      if (!looksLikeImageOverlay) return;
      {
        const b = l.getBounds();
        overlays.push({
          url: String(l._url).replace(/^.*\/layers\//, 'layers/').slice(0, 90),
          bounds: [[b.getSouth(), b.getWest()], [b.getNorth(), b.getEast()]],
          pane: l.options && l.options.pane, opacity: l.options && l.options.opacity,
          className: (l.options && l.options.className) || '',
        });
      }
    });

    // Bounds equality against layers.json, to 1e-9 units, plus the covered area
    // fraction so a partial raster reports how partial rather than just "false".
    const gb = H.mf.crs.bounds;
    const gArea = (gb[1][0] - gb[0][0]) * (gb[1][1] - gb[0][1]);
    const base = overlays.find((o) => /mc-raster--base/.test(o.className)) || overlays[0];
    let boundsVerdict = { checked: false };
    if (base) {
      const ob = base.bounds;
      const d = [ob[0][0] - gb[0][0], ob[0][1] - gb[0][1], ob[1][0] - gb[1][0], ob[1][1] - gb[1][1]];
      const oArea = (ob[1][0] - ob[0][0]) * (ob[1][1] - ob[0][1]);
      boundsVerdict = {
        checked: true, overlay: ob, manifest: gb,
        residual_units: d.map((v) => +v.toFixed(9)),
        equal: d.every((v) => Math.abs(v) < 1e-9),
        covered_fraction: +(oArea / gArea).toFixed(6),
      };
    }

    const layerButtons = [...document.querySelectorAll('.mc-layer')].map((b) => ({
      label: (b.textContent || '').replace(/\s+/g, ' ').trim(),
      on: /mc-layer--on/.test(b.className),
    }));
    const rasterButtons = layerButtons.filter((b) => !/^(Landing Sites|Rover Route)$/.test(b.label));
    const activeRaster = rasterButtons.find((b) => b.on) || null;
    const expectedActiveLayers = 1 + (activeRaster && activeRaster.label !== 'Surface Relief' ? 1 : 0);

    return {
      imgNodes: nodes,
      imageOverlays: overlays,
      counts: {
        imgNodes: nodes.length, imageOverlays: overlays.length,
        previewsStillMounted: nodes.filter((n) => n.isPreview).length,
        base: overlays.filter((o) => /mc-raster--base/.test(o.className)).length,
        science: overlays.filter((o) => /mc-raster--science/.test(o.className)).length,
        uniqueUrls: new Set(overlays.map((o) => o.url)).size,
      },
      expectedActiveLayers,
      activeRasterLabel: activeRaster ? activeRaster.label : null,
      // Hypothesis 4: a tile pyramid bleeding in would put a tile pane in .mc-map.
      tilePaneInMap: document.querySelectorAll('.mc-map .leaflet-tile-pane').length,
      tileImgsInMap: document.querySelectorAll('.mc-map img.leaflet-tile').length,
      // Hypothesis 4, the other mount point: GISMapViewer lives outside .mc-map.
      tileImgsAnywhere: document.querySelectorAll('img.leaflet-tile').length,
      tileUrlSample: [...document.querySelectorAll('img.leaflet-tile')]
        .slice(0, 4).map((n) => (n.getAttribute('src') || '').slice(-60)),
      boundsVerdict,
    };
  };

  H.consoleLines = function () { return (window.__mcLines || []).slice(0, 40); };

  H.errors = function () { return (window.__mcErrors || []).slice(0, 20); };

  /**
   * Census at full extent. REQUIRED, and the reason is a measurement error this
   * script made on its first run: Leaflet clips SVG paths outside the viewport, so
   * getBBox() on an off-screen circleMarker returns a zero box. Censusing only at
   * the 40 km opening view therefore reported 2/6 markers "visible" and read as a
   * v7-style styling regression, when four of the six were simply off-screen — the
   * sites are spread across a 165 km frame and the opening window shows 67 km of
   * it. At full extent nothing is clipped, so `visible` measures STYLING alone,
   * which is the thing v7 broke and the thing worth gating on. Both numbers are
   * reported: in-window is a real fact too, just a different one.
   */
  H.overlaysAtFullExtent = function () {
    H.map.fitBounds(H.geom.full, { animate: false });
    const at = H.overlays();
    return { view: H.viewport(), overlays: at };
  };

  window.__mc8 = H;
  return 'installed';
}

// MissionMap logs its landing-site and rover-coverage tables through console.info
// /console.table. Those tables are the app's own count of how much of each
// traverse the radar actually saw, so they are captured rather than recomputed.
const HOOK = 'window.__mcErrors=[];window.__mcLines=[];'
  + "addEventListener('error',function(e){window.__mcErrors.push('error: '+e.message)});"
  + "addEventListener('unhandledrejection',function(e){window.__mcErrors.push('rejection: '+e.reason)});"
  + '(function(){var ce=console.error,ci=console.info,ct=console.table;'
  + "console.error=function(){window.__mcErrors.push('console.error: '+Array.prototype.map.call(arguments,String).join(' '));return ce.apply(console,arguments)};"
  + "console.info=function(){window.__mcLines.push('info: '+Array.prototype.map.call(arguments,String).join(' '));return ci.apply(console,arguments)};"
  + 'console.table=function(d){try{window.__mcLines.push("table: "+JSON.stringify(d))}catch(e){}return ct.apply(console,arguments)}})();';

async function main() {
  log('\n══ verify_v8_view ═════════════════════════════════════════════════');
  log(`  url     ${CFG.url}`);

  const probe = async (u) => {
    try { const r = await fetch(new URL(u).origin, { signal: AbortSignal.timeout(4000) }); return r.ok || r.status < 500; }
    catch { return false; }
  };
  const swap = (u) => { const x = new URL(u); x.hostname = x.hostname === 'localhost' ? '127.0.0.1' : 'localhost'; return x.toString(); };
  if (!(await probe(CFG.url))) {
    const alt = swap(CFG.url);
    if (await probe(alt)) { log(`  note    ${new URL(CFG.url).origin} refused; using ${new URL(alt).origin}`); CFG.url = alt; }
    else fail(`dev server not answering at ${new URL(CFG.url).origin} or ${new URL(alt).origin}.\n`
      + '  Start it first:  npm run dev --prefix frontend');
  }
  if (!existsSync(CFG.out)) mkdirSync(CFG.out, { recursive: true });

  const { proc, profile, bin } = launchBrowser();
  log(`  browser ${bin}`);
  const cdp = await CDP.connect(await devtoolsUrl(profile, proc));
  const { targetId } = await cdp.send('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await cdp.send('Target.attachToTarget', { targetId, flatten: true });
  const S = (m, p) => cdp.send(m, p, sessionId);
  await S('Page.enable'); await S('Runtime.enable');
  await S('Emulation.setDeviceMetricsOverride', { width: CFG.width, height: CFG.height, deviceScaleFactor: 1, mobile: false });
  await S('Page.addScriptToEvaluateOnNewDocument', { source: HOOK });

  const ev = async (expr) => {
    const r = await S('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) throw new Error(`page threw: ${r.exceptionDetails.exception?.description || r.exceptionDetails.text}\n  in: ${expr.slice(0, 140)}`);
    return r.result.value;
  };

  const loaded = cdp.once('Page.loadEventFired', 45000);
  await S('Page.navigate', { url: CFG.url });
  await loaded;
  await ev(`(${harness.toString()})()`);

  const init = await ev('window.__mc8.init()');
  if (init.error) fail(`harness init failed: ${init.error}\n  ${JSON.stringify(init, null, 2).replace(/\n/g, '\n  ')}`);
  log(`  map     ${init.size.x}x${init.size.y} px · ring ${init.ringPts} pts · zoom ${init.zoom}`);
  log(`  m/unit  ${init.mpu}`);

  // OPENING view captured before anything else touches the map.
  const opening = await ev('window.__mc8.viewport()');
  const overlays = await ev('window.__mc8.overlays()');
  const panel = await ev('window.__mc8.coveragePanel()');
  const voidPane = await ev('window.__mc8.voidPane()');
  const rasters = await ev('window.__mc8.rasterInventory()');
  const shotOpening = await S('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  writeFileSync(path.join(CFG.out, `v8_opening_view${SUF}.png`), Buffer.from(shotOpening.data, 'base64'));

  const raf = await ev('window.__mc8.rafFires()');
  const reset = await ev(`window.__mc8.reset(${raf.fired})`);
  const shotReset = await S('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  writeFileSync(path.join(CFG.out, `v8_after_reset${SUF}.png`), Buffer.from(shotReset.data, 'base64'));

  // Second census, at full extent. The first run of this script gated on the
  // opening-view census and reported 2/6 markers visible, which reads as the v7
  // invisible-marker regression and is not what it measures: Leaflet's SVG
  // renderer calls _empty() on every path and writes d="M0 0" for a circleMarker
  // whose pixel bounds do not intersect the renderer viewport, so an off-screen
  // marker has a 0x0 getBBox() no matter how boldly it is styled. Four of the six
  // markers sit outside the 40 km opening window — the sites span a 165 km frame.
  // At full extent nothing is clipped, so this census measures STYLING only, which
  // is the actual v8 question. Both are kept: in-window is a real fact, just a
  // different one, and the gate now names which it is testing.
  const overlaysFull = await ev('window.__mc8.overlaysAtFullExtent()');
  const shotFull = await S('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  writeFileSync(path.join(CFG.out, `v8_full_extent${SUF}.png`), Buffer.from(shotFull.data, 'base64'));

  const lines = await ev('window.__mc8.consoleLines()');
  const errors = await ev('window.__mc8.errors()');

  // ── report ───────────────────────────────────────────────────────
  log('\n── (a) coverage panel removed ──────────────────────────────────────');
  Object.entries(panel.found).forEach(([s, n]) => log(`  ${s.padEnd(20)} ${n} node(s)`));
  if (panel.legendishTextInMap.length) log(`  legend-like text still in .mc-map: ${JSON.stringify(panel.legendishTextInMap)}`);
  else log('  no legend-like text inside .mc-map');

  log('\n── (b) mc-void pane removed ────────────────────────────────────────');
  log(`  getPane('mc-void')     ${voidPane.paneObject}${voidPane.threw ? ` (threw: ${voidPane.threw})` : ''}`);
  log(`  panes on the map       ${voidPane.panesOnMap.filter((p) => p.startsWith('mc-')).join(', ') || '(none custom)'}`);
  log(`  DOM nodes matching     ${voidPane.domNodes}`);
  log(`  <pattern> nodes        ${voidPane.hatchPattern}`);

  const km = (v) => `${v.w} x ${v.h} km`;
  log('\n── (c) opening view is the 40 km window, not the full strip ────────');
  log(`  opening visible        ${km(opening.km)}  (zoom ${opening.zoom}, centre ${opening.centre.join(', ')})`);
  log(`  home window            ${km(opening.home_km)}`);
  log(`  full frame             ${km(opening.full_km)}`);
  log(`  contains full width    ${opening.contains_full_width}  (true would mean the 1:2.93 strip)`);
  log(`  centred on ribbon      ${opening.centred_on_ribbon}`);

  log('\n── (d) "Reset view" returns to that window ─────────────────────────');
  log(`  rAF fires here         ${raf.fired}  (document.hidden ${raf.documentHidden}, ${raf.visibilityState})`);
  if (reset.error) {
    log(`  ERROR ${reset.error}  buttons: ${JSON.stringify(reset.buttons)}`);
  } else {
    log(`  moved away to          ${km(reset.before.km)}  (zoom ${reset.before.zoom})`);
    log(`  flyToBounds called     ${reset.flyCalls.length}x, destination == homeBounds: ${reset.destMatchesHome}`);
    if (reset.arrived) log(`  ARRIVED (animated)     ${km(reset.arrived.km)}  (zoom ${reset.arrived.zoom}) — measured, not inferred`);
    else log('  ARRIVED (animated)     not measurable: rAF does not fire, so flyToBounds cannot complete');
    if (reset.fitted) log(`  destination fitted     ${km(reset.fitted.km)}  (zoom ${reset.fitted.zoom}) — animation-free equivalent`);
  }

  log('\n── (0) raster overlay inventory ────────────────────────────────────');
  log(`  active raster layer    ${rasters.activeRasterLabel}`);
  log(`  expectedActiveLayers   ${rasters.expectedActiveLayers}`);
  log(`  imageOverlays.length   ${rasters.counts.imageOverlays}`
    + `  (base ${rasters.counts.base}, science ${rasters.counts.science},`
    + ` unique urls ${rasters.counts.uniqueUrls})`);
  log(`  <img> image-layer nodes ${rasters.counts.imgNodes}`
    + `  previews still mounted ${rasters.counts.previewsStillMounted}`);
  rasters.imgNodes.forEach((n) => log(`    [${n.pane}] ${n.natural[0]}x${n.natural[1]} op ${n.opacity}`
    + `  ${n.isPreview ? 'PREVIEW ' : ''}${n.src}`));
  rasters.imageOverlays.forEach((o) => log(`    overlay pane=${o.pane} op=${o.opacity} ${o.url}`));
  log(`  tile pane inside .mc-map  ${rasters.tilePaneInMap}   tile <img> in .mc-map ${rasters.tileImgsInMap}`);
  log(`  tile <img> anywhere on page ${rasters.tileImgsAnywhere}`
    + (rasters.tileUrlSample.length ? `  e.g. ${JSON.stringify(rasters.tileUrlSample)}` : ''));
  const bv = rasters.boundsVerdict;
  if (bv.checked) {
    log(`  base bounds == layers.json crs.bounds: ${bv.equal}`
      + `  residual ${JSON.stringify(bv.residual_units)} units`);
    log(`  covered fraction of the manifest extent: ${bv.covered_fraction}`);
  } else log('  base overlay not found — bounds not checked');

  log('\n── landing sites and rover routes: drawn, and drawn in amber? ──────');

  const ofull = overlaysFull.overlays;
  log(`  AT OPENING VIEW (${km(opening.km)}) — in-window census, clipping included`);
  log(`  svg paths in panes     ${overlays.paths}`);
  log(`  markers (sites/target) n ${overlays.markers.n}  visible ${overlays.markers.visible}  `
    + `amber ${overlays.markers.amber}  amber+visible ${overlays.markers.amberAndVisible}`);
  log(`  lines (routes/rings)   n ${overlays.lines.n}  visible ${overlays.lines.visible}  `
    + `amber ${overlays.lines.amber}  amber+visible ${overlays.lines.amberAndVisible}`);
  log(`\n  AT FULL EXTENT (${km(overlaysFull.view.km)}) — nothing clipped, so this is STYLING`);
  log(`  svg paths in panes     ${ofull.paths}`);
  log(`  markers (sites/target) n ${ofull.markers.n}  visible ${ofull.markers.visible}  `
    + `amber ${ofull.markers.amber}  amber+visible ${ofull.markers.amberAndVisible}`);
  log(`  lines (routes/rings)   n ${ofull.lines.n}  visible ${ofull.lines.visible}  `
    + `amber ${ofull.lines.amber}  amber+visible ${ofull.lines.amberAndVisible}`);
  log(`  markers off-screen at the opening view: ${ofull.markers.visible - overlays.markers.visible} of ${ofull.markers.n}`);
  lines.filter((l) => /landing-site coverage|rover waypoint coverage|table:/.test(l))
    .forEach((l) => log(`  ${l.slice(0, 300)}`));

  // ── gate ─────────────────────────────────────────────────────────
  const gate = {
    zero_one_overlay_per_layer: {
      value: `${rasters.counts.imageOverlays} overlays vs ${rasters.expectedActiveLayers} expected,`
           + ` ${rasters.counts.previewsStillMounted} preview(s) mounted,`
           + ` ${rasters.tileImgsInMap} tile img in .mc-map`,
      pass: rasters.counts.imageOverlays === rasters.expectedActiveLayers
         && rasters.counts.uniqueUrls === rasters.counts.imageOverlays
         && rasters.tileImgsInMap === 0,
    },
    a_no_coverage_panel: { value: panel.total, pass: panel.total === 0 },
    b_no_void_pane: {
      value: `${voidPane.paneObject}, ${voidPane.domNodes} dom, ${voidPane.hatchPattern} pattern`,
      pass: voidPane.paneObject === 'absent' && voidPane.domNodes === 0 && voidPane.hatchPattern === 0,
    },
    c_opening_is_home_window: {
      value: `${opening.km.w}x${opening.km.h} km vs home ${opening.home_km.w}x${opening.home_km.h}`,
      // Leaflet fits to a discrete zoom, so the visible window is >= the requested
      // one; the test is that it is the same ORDER as home and nowhere near full.
      pass: !opening.contains_full_width
         && opening.km.w <= opening.home_km.w * 2.2
         && opening.km.w >= opening.home_km.w * 0.5
         && opening.centred_on_ribbon,
    },
    d_reset_returns_home: {
      value: reset.error
        ? reset.error
        : `dest==home ${reset.destMatchesHome}` + (reset.arrived
          ? `, arrived ${reset.arrived.km.w}x${reset.arrived.km.h} km`
          : `, fitted ${reset.fitted ? `${reset.fitted.km.w}x${reset.fitted.km.h} km` : 'n/a'} (rAF dead)`),
      pass: !reset.error && reset.destMatchesHome && !!(reset.arrived || reset.fitted)
         && !(reset.arrived || reset.fitted).contains_full_width,
      measured_animated: !!reset.arrived,
    },
    // Gated on FULL EXTENT, because at the 40 km opening window Leaflet writes
    // d="M0 0" for off-screen circleMarkers and a clipped marker is not a faint
    // one. `styled` is geometry-free and is the exact v7 defect condition.
    sites_visible: {
      value: `${ofull.markers.visible}/${ofull.markers.n} visible at full extent`
           + ` (${overlays.markers.visible}/${overlays.markers.n} in the 40 km window),`
           + ` faint ${ofull.markers.faint}`,
      pass: ofull.markers.n >= 6 && ofull.markers.visible === ofull.markers.n
         && ofull.markers.faint === 0,
    },
    routes_visible: {
      value: `${ofull.lines.visible}/${ofull.lines.n} visible at full extent,`
           + ` faint ${ofull.lines.faint}`,
      pass: ofull.lines.visible >= 3 && ofull.lines.faint === 0,
    },
    no_page_errors: { value: errors, pass: errors.length === 0 },
  };

  log('\n── gate ───────────────────────────────────────────────────────────');
  let allPass = true;
  for (const [k, v] of Object.entries(gate)) {
    allPass = allPass && v.pass;
    log(`  ${v.pass ? 'PASS' : 'FAIL'}  ${k.padEnd(26)} ${String(JSON.stringify(v.value)).slice(0, 70)}`);
  }
  if (!gate.d_reset_returns_home.measured_animated) {
    log('  NOTE  (d) was verified on the flyToBounds destination and an animation-free');
    log('        fitBounds of it, NOT on an observed animated arrival. Weaker evidence.');
  }
  errors.forEach((e) => log(`        page error: ${e}`));
  if (ofull.faintPaths.length) {
    log('  FAINT PATHS (the v7 condition) — these are drawn too weakly to see:');
    ofull.faintPaths.forEach((p) => log(`        ${p.kind} stroke ${p.stroke} w ${p.w} o ${p.o} box ${p.box.join('x')}`));
  }

  const report = { generated_utc: new Date().toISOString(), url: CFG.url, browser: bin,
                   viewport: [CFG.width, CFG.height], init, opening, panel, voidPane, rasters,
                   raf, reset, overlays, overlaysFull, consoleLines: lines, errors, gate };
  writeFileSync(path.join(CFG.out, `verify_v8_view${SUF}.json`), JSON.stringify(report, null, 2));
  log(`\n  wrote   docs/verify_v8_view${SUF}.json, docs/v8_opening_view${SUF}.png,`
    + ` docs/v8_after_reset${SUF}.png, docs/v8_full_extent${SUF}.png`);
  log(`  ${allPass ? 'GATE PASS' : 'GATE FAIL'}\n`);

  cdp.ws.close();
  proc.kill();
  try { rmSync(profile, { recursive: true, force: true }); } catch { /* tmp */ }
  process.exit(allPass ? 0 : 1);
}

main().catch((e) => { console.error(e); process.exit(3); });
