/**
 * MissionControl.tsx — the post-landing analysis environment. Orchestrates the
 * hero map (≈70%) + intelligence rail (≈30%), a top command bar, a 12-stage
 * progress stepper and a bottom context bar.
 *
 * TWO SOURCES, DELIBERATELY SEPARATE
 * ----------------------------------
 * 1. The HEADLINE VERDICT and the context bar read `public/analysis/<crater>.json`,
 *    precomputed offline by `backend/scripts/build_analysis.py` from the native
 *    25 m/px rasters. No backend, no cold start, no fallback.
 * 2. The on-demand backend still drives the sensitivity studio, custom
 *    thresholds, the stage panels and the PDF. It may fail — loudly — without
 *    taking the verdict with it.
 *
 * Why they were split: on Render the mission endpoint cannot see the SAR rasters
 * (`/data/` and `*.tif` are gitignored; the paths in mission_service.py are
 * Windows absolutes), so it degrades to a seeded DEMO generator and returns
 * P(ice) 0.96 / screening PASSED / 5-of-5 ticks / 17.58 M m³ with HTTP 200. That
 * fabricated verdict was rendered beside a map of the real measured swath. The
 * mechanism that let a simulated value occupy a measured value's slot is gone:
 * the verdict card and the context bar cannot read the backend at all.
 */
import { useEffect, useRef, useState } from 'react';
import { fetchCraters, fetchMissionState, getReportPdfUrl } from '../services/api';
import type { MissionState, CraterInfo, CandidateLandingSite } from '../types/mission';
import { MissionMap, type MissionMapHandle, type LayerManifestEntry, groundResolutionLabel, loadManifest } from './MissionMap';
import { loadSearchedSites, type SearchedSites } from './analysis';
import { Disclose } from './VerdictCard';
import { VerdictCard } from './VerdictCard';
import { StepPanel } from './StepPanel';
import { STEPS, LAYERS, LAYER_MAP } from './config';
import type { LayerDef } from './config';
import { loadAnalysis, PROV_MARK, isMissing, showValue } from './analysis';
import type { Analysis, AnalysisValue, Provenance } from './analysis';
import { ProbeReadout } from './ProbeReadout';
import { TraversePanel } from './TraversePanel';
import { loadProbeGrid, type ProbeGrid, type ProbeSample } from './probe';
import { loadTraverse, type Traverse } from './traverse';
import { Download, ZoomIn, ZoomOut, Maximize2, MapPin, Check, Crosshair, Route } from 'lucide-react';
import './mc.css';

const STEP_LAYER: Record<number, string> = {
  1: 'hillshade', 2: 'illumination', 3: 'cpr_heatmap', 4: 'ml_likelihood',
  5: 'hazard_map', 6: 'hillshade', 7: 'hillshade', 8: 'dem_elevation',
  9: 'cpr_heatmap', 10: 'hazard_map', 11: 'hillshade', 12: 'hillshade',
};

/**
 * Badge text for a layer's provenance — kept blunt on purpose.
 *
 * 'measured' is no longer synonymous with radar. Since the placeholder DEM was
 * replaced by LOLA LDEM_80S_80M V2.0, the relief, elevation and hazard layers
 * are measured *topography*, so a single 'MEASURED RADAR' string would have put
 * the wrong instrument on three of them. The badge therefore names which
 * measurement it is; the CSS class still keys on `provenance` alone so nothing
 * restyles.
 */
const RADAR_LAYERS = new Set(['cpr_heatmap', 'dop_heatmap']);

/**
 * The legend badge, driven by layers.json when it is loaded.
 *
 * config.ts is a fallback, not the authority. The manifest is written by the
 * same script that renders the pixels, so a layer cannot wear a badge that
 * describes a different computation than the one that produced it — which is
 * exactly what happened when the illumination layer became a real horizon
 * computation and the legend went on saying MODEL OUTPUT.
 */
const MANIFEST_BADGE: Record<string, string> = {
  'measured-topography': 'MEASURED TOPOGRAPHY',
  'measured-radar': 'MEASURED RADAR',
  'computed-solar-horizon': 'COMPUTED ILLUMINATION',
};
/** The six words the map treats as "this is not a measurement". */
const PLACEHOLDER_PROVENANCE = /synthetic|placeholder|analytic|unknown|unavailable/i;

/** Units per layer, so a legend end reads as a quantity rather than a bare
 *  float. Keyed by layer id because the manifest carries the numbers but not
 *  what they are of. */
const LAYER_UNITS: Record<string, { unit: string; digits: number }> = {
  dem_elevation: { unit: ' m', digits: 0 },
  hazard_map: { unit: '', digits: 2 },
  illumination: { unit: ' lit frac', digits: 3 },
  cpr_heatmap: { unit: '', digits: 4 },
  dop_heatmap: { unit: '', digits: 3 },
  hillshade: { unit: '', digits: 2 },
};

function fmtScale(v: number, id: string): string {
  const u = LAYER_UNITS[id] ?? { unit: '', digits: 3 };
  if (!Number.isFinite(v)) return '—';
  return `${v.toFixed(u.digits)}${u.unit}`;
}

function provBadge(l: LayerDef, manifestProv?: string): string {
  if (manifestProv) {
    if (PLACEHOLDER_PROVENANCE.test(manifestProv)) return 'PLACEHOLDER';
    const known = MANIFEST_BADGE[manifestProv];
    if (known) return known;
    return manifestProv.replace(/-/g, ' ').toUpperCase();
  }
  if (l.provenance === 'measured') {
    return RADAR_LAYERS.has(l.id) ? 'MEASURED RADAR' : 'MEASURED TOPOGRAPHY';
  }
  return l.provenance === 'synthetic' ? 'SYNTHETIC DEM' : 'MODEL OUTPUT';
}

/** One context-bar cell, bound to a single AnalysisValue and its provenance. */
interface CtxCell {
  k: string;
  v: AnalysisValue | undefined;
  /** Sub-line when the value exists. When it does not, the value's own reason is shown. */
  sub: string;
  digits?: number;
  suffix?: string;
}

/**
 * The eight context-bar cells. Every one is traceable to a printed statistic in
 * the generator's output; none of them can come from the backend.
 */
function contextCells(a: Analysis): CtxCell[] {
  const v = a.values;
  const cprMax = v.cpr_max?.value;
  const dopP50 = v.dop_p50?.value;
  const slopeMax = v.max_slope_deg?.value;
  return [
    { k: 'Channel imbal. (mean)', v: v.cpr_mean, sub: cprMax != null ? `peak ${cprMax.toPrecision(3)}` : 'over measured px' },
    { k: 'DOP (mean)', v: v.dop_mean, sub: dopP50 != null ? `median ${dopP50.toPrecision(3)}` : 'over measured px' },
    { k: 'PSR Area', v: v.psr_area_km2, sub: 'km² shadowed' },
    { k: 'Mean Slope', v: v.mean_slope_deg, sub: slopeMax != null ? `max ${slopeMax.toFixed(1)}°` : '', suffix: '°', digits: 2 },
    // Was "Peak P(ice)" reading v.p_ice_max — a Random Forest output whose
    // positive class lay outside this product's achievable CPR range. The cell
    // now holds the 99th percentile of the MEASURED CPR field: the threshold
    // above which the top 1 % of the swath sits. It is a ranking within this
    // scene, and the label says so in as many words, because a percentile of a
    // sub-threshold distribution is not a detection.
    {
      // Renamed with its sibling. Same quantity, same proxy, same objection:
      // METHODS 7.9.2 shows it does not measure CPR. Leaving one cell reading
      // "CPR" beside another reading "channel imbalance", both fed by the same
      // array, is the collision this project keeps finding.
      k: 'Top 1% ch. imbal.',
      v: v.cpr_p99,
      // Not a surface property. METHODS 7.9.2: this quantity responds to the
      // imbalance between the two receive channels and has zero sensitivity to
      // the circular polarisation ratio, so a high value says something about
      // the instrument's view, not about what the ground is made of. It becomes
      // a surface measurement only if 5b lands real Stokes CPR.
      sub: 'top-percentile channel imbalance — an instrument-frame ranking, not a surface property, not a detection',
      digits: 4,
    },
    { k: 'Candidate Area', v: v.candidate_area_km2, sub: 'km² passing both criteria', digits: 2 },
    { k: 'Ice Volume', v: v.expected_volume_m3, sub: 'm³ from candidate area' },
    { k: 'Rover', v: v.rover_traverse_km, sub: 'science-aware' },
  ];
}

/** Provenance chip. Present on every value in the UI, with no exceptions. */
function Pv({ p }: { p: Provenance }) {
  return <span className={`mc-pv mc-pv--${p.toLowerCase()}`}>{PROV_MARK[p]}</span>;
}

export default function MissionControl() {
  const [craters, setCraters] = useState<Record<string, CraterInfo>>({});
  const [craterId, setCraterId] = useState('faustini');
  const [mission, setMission] = useState<MissionState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Precomputed measured analysis — the ONLY source for the verdict + context bar.
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [analysisReady, setAnalysisReady] = useState(false);

  const [step, setStep] = useState(1);
  // Opens on the topography, not on a radar product. A first-time viewer needs
  // to see the landform before a false-colour ratio painted over it means
  // anything. STEP_LAYER still swings the map to cpr_heatmap on step 3.
  const [activeLayer, setActiveLayer] = useState('hillshade');
  const [showLandingSites, setShowLandingSites] = useState(true);
  // OFF BY DEFAULT. The planner is real -- Dijkstra over measured slope,
  // roughness, hazard and illumination -- but the DESTINATION is not: the
  // screen found 0.00 km2 of candidate, so there is nothing to route TO and
  // every strategy aims at a hardcoded grid centre. That is why the ROVER stat
  // reads NO DATA. Drawing a confident cyan line to an invented target, above a
  // cell saying the quantity is not computable, is the same picture-versus-
  // number disagreement this project keeps catching. The layer stays available,
  // because the cost surface IS measured and worth showing, but it is opt-in and
  // it says what it is.
  // Opacity of the active science layer over the hillshade. MEASURED, not
  // chosen: backend/scripts/composite_contrast.py composites each layer over the
  // filtered hillshade and asks whether the terrain's relief survives -- both
  // that enough high-frequency structure remains (retention >= 0.25) AND that
  // the surviving structure still CORRELATES with the base (>= 0.30), because a
  // speckly layer raises the first while destroying the second.
  //
  // The binding layer is the radar one: correlation 0.13 at 0.72, 0.29 at 0.50,
  // 0.34 at 0.45. 0.45 is the highest value at which all five layers clear both
  // floors. Numbers in docs/composite_contrast.json. The slider is there because
  // a single blend that suits every layer does not exist -- a reader who wants
  // to read the data rather than the landform should push it up.
  const [scienceOpacity, setScienceOpacity] = useState(0.45);
  const [showRoute, setShowRoute] = useState(false);
  const [selectedSite, setSelectedSite] = useState<CandidateLandingSite | null>(null);
  /** The Phase 3 sites, searched over all 14.9 M native pixels. Null means no
   *  search has been run on this host -- an absent state, not an empty list. */
  const [searched, setSearched] = useState<SearchedSites | null>(null);
  useEffect(() => { loadSearchedSites().then(setSearched); }, []);
  /* ── the criteria probe ──────────────────────────────────────────────────
   * Off by default and its 6.5 MB of float32 is fetched only when it is first
   * switched on, so a reader who never opens it never pays for it. `probeSettled`
   * keeps "still loading" and "not generated on this host" distinct: collapsing
   * them would let a slow fetch look like an absent measurement. */
  const [probeOn, setProbeOn] = useState(false);
  const [probeGrid, setProbeGrid] = useState<ProbeGrid | null>(null);
  const [probeSettled, setProbeSettled] = useState(false);
  const [probe, setProbe] = useState<ProbeSample | null>(null);

  /* ── the Phase 4 traverse ────────────────────────────────────────────────
   * Planned in Phase 4 and, until now, drawn nowhere. ON by default: it is a
   * deliverable, it is cheap (a few hundred vertices), and the request that
   * produced this was that the route be obvious rather than hidden. */
  const [traverse, setTraverse] = useState<Traverse | null>(null);
  const [traverseSettled, setTraverseSettled] = useState(false);
  const [showTraverse, setShowTraverse] = useState(true);
  const [selectedRoute, setSelectedRoute] = useState<number | null>(1);
  const [roverFraction, setRoverFraction] = useState(0);
  const [roverPlaying, setRoverPlaying] = useState(false);

  /** Select a route, park the rover at its start, and go and look at it. The
   *  five routes are spread over a 165 km frame, so most of them are outside the
   *  40 km opening window; selecting one and not moving there would answer
   *  "which points does the rover pass through" with an empty panel. */
  const pickRoute = (r: number) => {
    setSelectedRoute(r);
    setRoverFraction(0);
    setRoverPlaying(false);
    mapRef.current?.focusRoute(r);
  };

  const [coords, setCoords] = useState('Hover the map for coordinates');
  const [zoom, setZoom] = useState(1);

  const [cprTh, setCprTh] = useState(1.0);
  const [dopTh, setDopTh] = useState(0.13);
  const [iceDepth, setIceDepth] = useState(5.0);
  const [iceFrac, setIceFrac] = useState(0.15);
  const [roverAlgo, setRoverAlgo] = useState('A*');

  // Layer descriptions, read from layers.json so the legend and the pixels
  // cannot describe different formulas. Empty until the manifest lands; the
  // legend simply omits the hint until then rather than showing a stale one.
  const [layerCopy, setLayerCopy] = useState<Record<string, string>>({});
  const [layerProv, setLayerProv] = useState<Record<string, string>>({});
  const [layerRes, setLayerRes] = useState<Record<string, NonNullable<LayerManifestEntry['resolution']>>>({});
  /** vmin/vmax and the stretch, straight out of layers.json, so the legend's
   *  numbers are the ones the pixels were made with rather than a second copy
   *  maintained by hand in config.ts. */
  const [layerScale, setLayerScale] = useState<Record<string, {
    vmin: number; vmax: number; stretch?: LayerManifestEntry['stretch'];
    display: Record<string, unknown> | null; contours: number | null;
  }>>({});
  useEffect(() => {
    loadManifest().then((m) => {
      if (!m) return;
      setLayerCopy(Object.fromEntries(m.layers.map((l) => [l.id, l.description])));
      setLayerProv(Object.fromEntries(m.layers.map((l) => [l.id, l.provenance])));
      setLayerRes(Object.fromEntries(m.layers.flatMap((l) =>
        l.resolution ? [[l.id, l.resolution] as const] : [])));
      setLayerScale(Object.fromEntries(m.layers.map((l) => [l.id, {
        vmin: l.vmin, vmax: l.vmax, stretch: l.stretch,
        display: l.display_choices ?? null, contours: l.contours_m ?? null,
      }] as const)));
    });
  }, []);

  // The traverse plan. Small, and the map needs it as soon as it can paint.
  useEffect(() => {
    let live = true;
    loadTraverse().then((t) => {
      if (!live) return;
      setTraverse(t);
      setTraverseSettled(true);
      // Select the first REACHABLE route rather than assuming rank 1 is one.
      const first = t?.primary_site_to_cold_trap.find((r) => r.status === 'REACHABLE');
      setSelectedRoute(first ? first.rank : null);
    });
    return () => { live = false; };
  }, []);

  // The probe grid, fetched on first use only.
  useEffect(() => {
    if (!probeOn || probeSettled) return;
    let live = true;
    loadProbeGrid().then((g) => {
      if (!live) return;
      setProbeGrid(g);
      setProbeSettled(true);
    });
    return () => { live = false; };
  }, [probeOn, probeSettled]);

  /* Drive the rover. 22 s end to end regardless of route length, because this is
   * a reading aid and not a simulation: there is no rover, no speed and no
   * duty cycle anywhere in this project, so a "realistic" pace would be an
   * invented number dressed as a measurement. The odometer beside it counts
   * real metres off the planned route. */
  useEffect(() => {
    if (!roverPlaying) return;
    let raf = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const dt = (now - last) / 1000;
      last = now;
      setRoverFraction((f) => Math.min(1, f + dt / 22));
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [roverPlaying]);

  // Stop at the goal. Separately, because setting one piece of state from inside
  // another's updater runs twice under StrictMode and is not what an updater is
  // for.
  useEffect(() => {
    if (roverFraction >= 1 && roverPlaying) setRoverPlaying(false);
  }, [roverFraction, roverPlaying]);

  const mapRef = useRef<MissionMapHandle>(null);
  useEffect(() => {
    fetchCraters().then(setCraters).catch(() =>
      setError('Cannot reach the Lunar Intelligence backend on port 8000.'));
  }, []);

  // The verdict. Static asset, no backend involved. `null` means "not
  // precomputed for this crater" and renders as such — it never falls back.
  useEffect(() => {
    setAnalysisReady(false);
    setAnalysis(null);
    let live = true;
    loadAnalysis(craterId).then((a) => {
      if (!live) return;
      setAnalysis(a);
      setAnalysisReady(true);
    });
    return () => { live = false; };
  }, [craterId]);

  // The backend. Drives the stage panels, the sensitivity studio and the PDF.
  // Allowed to fail without touching the verdict above.
  useEffect(() => {
    setLoading(true);
    setError(null);
    const dataMode = (import.meta.env.VITE_DATA_MODE as string) ?? 'REAL';
    fetchMissionState(craterId, { dataMode, cprThreshold: cprTh, dopThreshold: dopTh, iceDepthM: iceDepth, iceFraction: iceFrac, algorithm: roverAlgo })
      .then((d) => { setMission(d); setSelectedSite(d.recommended_landing_site); setLoading(false); })
      .catch((e) => { setError(e.message || 'Mission execution error'); setLoading(false); });
  }, [craterId, cprTh, dopTh, iceDepth, iceFrac, roverAlgo]);

  const gotoStep = (s: number) => { setStep(s); if (STEP_LAYER[s]) setActiveLayer(STEP_LAYER[s]); };
  const activeRoutes = showRoute ? ['Shortest', 'Safest', 'Science-Aware'] : [];
  const legend = LAYER_MAP[activeLayer];

  // Two independent mode chips, because there are two independent data paths and
  // conflating them is exactly how a DEMO verdict came to wear a REAL label.
  const verdictReal = analysis?.data_mode === 'REAL';
  const backendReal = mission?.data_mode === 'REAL';
  const cells = analysis ? contextCells(analysis) : [];
  // Sliders re-query the backend; the precomputed verdict is fixed at the
  // config thresholds. Say so rather than letting the two silently disagree.
  const thresholdsDrifted = !!analysis &&
    (cprTh !== analysis.thresholds.cpr_threshold || dopTh !== analysis.thresholds.dop_threshold);
  return (
    <div className="mc-root">
      {/* ── top command bar ── */}
      <div className="mc-topbar">
        <div className="mc-brand">
          <span className="mc-brand-dot" />
          <span>Lunar Ice Intelligence</span>
          <span className="mc-brand-sub">South-Polar Traverse Control</span>
        </div>
        <div className="mc-topbar-actions">
          {/* verdict source */}
          <span className={`mc-badge ${verdictReal ? 'mc-badge--real' : 'mc-badge--demo'}`} title={analysis?.why_static ?? ''}>
            <span className="mc-badge-dot" />
            {analysisReady
              ? (verdictReal ? 'VERDICT · REAL, PRECOMPUTED' : 'VERDICT · NOT PRECOMPUTED')
              : 'VERDICT · LOADING'}
          </span>
          {/* on-demand backend source, named separately so it cannot borrow the above */}
          <span
            className={`mc-badge ${backendReal ? 'mc-badge--real' : 'mc-badge--demo'}`}
            title="Powers the stage panels, sensitivity studio and PDF only. Never the verdict."
          >
            <span className="mc-badge-dot" />
            STUDIO · {mission ? (backendReal ? 'REAL' : 'SIMULATED') : error ? 'OFFLINE' : '…'}
          </span>
          {mission && (
            <a className="mc-btn mc-btn--solid" href={getReportPdfUrl(craterId)} target="_blank" rel="noopener noreferrer">
              <Download size={13} /> Report
            </a>
          )}
        </div>
      </div>

      {/* ── progress stepper ── */}
      <div className="mc-stepper">
        {STEPS.map((s) => {
          const Icon = s.icon;
          const cls = s.id === step ? 'mc-step--active' : s.id < step ? 'mc-step--done' : '';
          return (
            <button key={s.id} className={`mc-step ${cls}`} onClick={() => gotoStep(s.id)}>
              <span className="mc-step-k">{String(s.id).padStart(2, '0')} · {s.cat}</span>
              <span className="mc-step-label" style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                <Icon size={12} /> {s.label}
              </span>
            </button>
          );
        })}
      </div>
      {/* ── workspace ── */}
      <div className="mc-workspace">
        <div className="mc-mapwrap">
          {/* 1D · UNCONDITIONAL. This was `{mission && <MissionMap .../>}`, so a
              backend that was down — or merely cold-starting for 30-50 s on
              Render — left the user staring at an empty panel while every pixel
              of the map was already sitting on the CDN and returns in tens of
              milliseconds. The raster layers, panes, graticule, scale bar,
              footprint rings and coordinate readout need no backend at all. Only
              the vectors do, and MissionMap draws those when `mission` is
              non-null and skips them otherwise. It does NOT draw placeholders. */}
          <MissionMap
            ref={mapRef}
            mission={mission}
            activeLayer={activeLayer}
            showLandingSites={showLandingSites}
            scienceOpacity={scienceOpacity}
            searchedSites={searched?.sites ?? null}
            traverse={showTraverse ? traverse : null}
            selectedRoute={selectedRoute}
            onSelectRoute={pickRoute}
            roverFraction={roverFraction}
            probeGrid={probeGrid}
            probeOn={probeOn}
            onProbe={setProbe}
            activeRoverStrategies={activeRoutes}
            selectedLandingSite={selectedSite}
            onSelectLandingSite={setSelectedSite}
            onCoords={setCoords}
            onZoom={setZoom}
          />

          {/* layer control */}
          <div className="mc-map-overlay mc-map-panel mc-layerctl">
            <div className="mc-layerctl-head">Layers</div>
            {/* Scrolls rather than overflowing. The legend below is capped so it
                cannot cover this, but the switcher must also survive a short
                viewport on its own. */}
            <div className="mc-layerctl-body">
            {LAYERS.map((l) => (
              <button key={l.id} className={`mc-layer ${activeLayer === l.id ? 'mc-layer--on' : ''}`} onClick={() => setActiveLayer(l.id)}>
                <span className="mc-layer-sw" style={{ background: l.swatch }} />
                {l.label}
                <Check size={13} className="mc-layer-check" />
              </button>
            ))}
            <div style={{ borderTop: '1px solid var(--mc-line)', margin: '0.3rem 0' }} />
            <button className={`mc-layer ${showLandingSites ? 'mc-layer--on' : ''}`} onClick={() => setShowLandingSites((v) => !v)}>
              <MapPin size={11} style={{ color: 'var(--mc-accent)' }} /> Landing Sites
              <Check size={13} className="mc-layer-check" />
            </button>
            {/* PHASE 4 — the measured plan. Listed above the demo path, because
                two things called "rover route" on one screen is exactly the
                confusion this panel is here to end, and this is the one with a
                computation behind it. */}
            <button className={`mc-layer ${showTraverse ? 'mc-layer--on' : ''}`} onClick={() => setShowTraverse((v) => !v)}>
              <Route size={11} style={{ color: '#4fd1e6' }} /> Traverse + Rover
              <span className="mc-layer-tag" title={
                'Dijkstra at a stated 100 m planning resolution over measured slope, '
                + 'roughness and hazard, with connectivity established before any '
                + 'distance is quoted. Every waypoint is drawn. The destination is a '
                + 'MODELLED cold trap — where ice could persist, not where ice is. '
                + 'Phase 4, docs/traverse.json.'
              }>PHASE 4</span>
              <Check size={13} className="mc-layer-check" />
            </button>
            <button className={`mc-layer ${probeOn ? 'mc-layer--on' : ''}`} onClick={() => { setProbeOn((v) => !v); setProbe(null); }}>
              <Crosshair size={11} style={{ color: '#4fd1e6' }} /> Criteria Probe
              <span className="mc-layer-tag" title={
                'Click anywhere and read the MEASURED CPR and DOP there, each against '
                + 'its threshold, and the Phase 8 detection floor. It does not locate '
                + 'ice: candidate area is 0.00 km2 and METHODS section 1 shows the '
                + 'screen is empty by construction.'
              }>MEASURE</span>
              <Check size={13} className="mc-layer-check" />
            </button>
            <button className={`mc-layer ${showRoute ? 'mc-layer--on' : ''}`} onClick={() => setShowRoute((v) => !v)}>
              <span className="mc-layer-sw" style={{ background: '#f2c14e' }} /> API Route
              <span className="mc-layer-tag" title={
                'Dijkstra over measured slope, roughness, hazard and illumination — '
                + 'but the target is a hardcoded grid centre, because the screen found '
                + '0.00 km² of candidate and there is nothing to route to. The path is '
                + 'real; the destination is not. Phase 4.'
              }>DEMO TARGET</span>
              <Check size={13} className="mc-layer-check" />
            </button>
            </div>
          </div>

          {/* The right-hand instrument stack, inboard of the zoom column. Both
              panels are opt-in and neither one is rendered when its toggle is
              off, so the map is never smaller than it has to be. */}
          {(probeOn || showTraverse) && (
            <div className="mc-mapstack">
              {probeOn && (
                <ProbeReadout grid={probeGrid} settled={probeSettled} sample={probe}
                              onClose={() => { setProbeOn(false); setProbe(null); }} />
              )}
              {showTraverse && (
                <TraversePanel
                  traverse={traverse} settled={traverseSettled}
                  selected={selectedRoute}
                  onSelect={pickRoute}
                  fraction={roverFraction} onFraction={setRoverFraction}
                  playing={roverPlaying}
                  onPlaying={(pl) => {
                    // Pressing play at the goal restarts from the site. The
                    // alternative is a button that visibly does nothing.
                    if (pl && roverFraction >= 1) setRoverFraction(0);
                    setRoverPlaying(pl);
                  }}
                />
              )}
            </div>
          )}

          {/* map tools */}
          <div className="mc-map-overlay mc-map-tools">
            <button className="mc-tool" onClick={() => mapRef.current?.zoomIn()} title="Zoom in"><ZoomIn size={15} /></button>
            <button className="mc-tool" onClick={() => mapRef.current?.zoomOut()} title="Zoom out"><ZoomOut size={15} /></button>
            <button className="mc-tool" onClick={() => mapRef.current?.reset()} title="Reset view"><Maximize2 size={14} /></button>
            <div className="mc-tool mc-north" title="North">N</div>
          </div>
          {/* legend — carries the layer's provenance badge so a synthetic-terrain
              layer can never read as a measurement (see config.ts) */}
          {legend && (
            <div className="mc-map-overlay mc-map-panel mc-map-legend">
              <div className="mc-legend-title">
                {legend.label}
                <span className={`mc-prov mc-prov--${legend.provenance}`}>
                  {provBadge(legend, layerProv[activeLayer])}
                </span>
              </div>
              {/* The default line: mark + resolution, in plain words. */}
              {layerRes[activeLayer] && (
                <div className="mc-legend-one">
                  {layerRes[activeLayer].native_metres_per_pixel} m native
                  {' → '}
                  {layerRes[activeLayer].effective_metres_per_pixel} m on this grid
                  {(layerRes[activeLayer].decimation_factor ?? 1) > 1
                    && ` · ${layerRes[activeLayer].decimation_factor}× block mean`}
                </div>
              )}
              <div className="mc-legend-bar" style={{ background: legend.gradient }} />
              {/* REAL UNITS AND THE ACTUAL vmin/vmax, read from layers.json.
                  config.ts's "Darker"/"Brighter" said nothing a reader could
                  check against the map. A legend that cannot be checked against
                  the pixels is decoration. */}
              {layerScale[activeLayer] ? (
                <div className="mc-legend-ends">
                  <span>{fmtScale(layerScale[activeLayer].vmin, legend.id)}</span>
                  <span className="mc-legend-mid">{legend.low} → {legend.high}</span>
                  <span>{fmtScale(layerScale[activeLayer].vmax, legend.id)}</span>
                </div>
              ) : (
                <div className="mc-legend-ends"><span>{legend.low}</span><span>{legend.high}</span></div>
              )}
              {layerScale[activeLayer]?.stretch?.linear_in_value === false && (
                <div className="mc-legend-warn">
                  colour scale is NOT linear in value — percentile breakpoints
                  {layerScale[activeLayer].contours
                    ? `, contours every ${layerScale[activeLayer].contours} m` : ''}
                </div>
              )}
              {activeLayer !== 'hillshade' && (
                <label className="mc-legend-op">
                  <span>over relief</span>
                  <input type="range" min={0} max={100} step={1}
                    value={Math.round(scienceOpacity * 100)}
                    onChange={(e) => setScienceOpacity(Number(e.target.value) / 100)} />
                  <span className="mc-legend-op-v">{Math.round(scienceOpacity * 100)}%</span>
                </label>
              )}
              {/* From layers.json, not from config.ts. The manifest is written by
                  the same script that renders the pixels, so this caption cannot
                  describe a different formula than the image it sits under. */}
              {/* The resolution this layer was MEASURED at, from layers.json.
                  Stated per layer because they now differ on the same map: 20 m
                  terrain under an 80 m shadow mask. A viewer comparing the two
                  has to be told, and a paragraph of caption is not enough. */}
              {/* The decimation detail moved into the disclosure above; the
                  native -> effective line is now the always-visible one. */}
              {/* PROGRESSIVE DISCLOSURE. The provenance paragraph is ~60 words
                  and was on screen at all times, competing with the map. It is
                  MOVED, not shortened: every word is still here, one click away.
                  What stays visible by default is the one line a reader needs to
                  know what they are looking at -- the mark and the resolution --
                  plus the colour bar, the scale ends and the opacity slider. */}
              {layerCopy[activeLayer] && (
                <Disclose summary="provenance, resolution and what this layer is"
                          detail={layerCopy[activeLayer]} />
              )}
            </div>
          )}

          {/* readout — ground resolution, derived from the layer manifest's own
              native_zoom so it cannot claim "native detail" at a zoom that is
              being upscaled. Past native it reports the upscale factor instead
              of a smaller m/px figure the 25 m product cannot support. */}
          <div className="mc-map-overlay mc-map-panel mc-map-readout">
            <div>{coords}</div>
            <div style={{ color: 'var(--mc-accent)' }}>
              ZOOM {zoom} · {groundResolutionLabel(zoom)}
            </div>
          </div>

          {/* The terrain and the analysis are different states and must look
              different. The map painting while the vectors are absent is not a
              failure, and it must not be dressed as a spinner over a blank panel. */}
          {!mission && (
            <div className="mc-map-overlay mc-map-panel mc-map-vectorstate">
              TERRAIN LOADED · {error ? 'STUDIO UNAVAILABLE' : loading ? 'STUDIO PENDING' : 'NO STUDIO'}
              {/* THIS SENTENCE NAMES WHAT IS ACTUALLY MISSING.
                  It used to say landing sites and rover routes need the backend.
                  Both are now static artifacts — the Phase 3 sites from
                  landing_sites.json and the Phase 4 traverse from traverse.json,
                  drawn above this banner while it claimed they could not be —
                  so the sentence had stopped describing the screen it sits on.
                  What genuinely needs the backend is the sensitivity studio, the
                  stage panels and the PDF, and those are what it names. */}
              <div className="mc-map-vectorstate-sub">
                {error
                  ? 'The sensitivity studio, the stage panels and the PDF need the on-demand '
                    + 'backend, which is not reachable. The verdict, the rasters, the searched '
                    + 'landing sites, the Phase 4 traverse and the criteria probe are all '
                    + 'static artifacts and are unaffected.'
                  : 'Rasters, sites and the traverse are static and already drawn. The '
                    + 'sensitivity studio and the stage panels follow when the backend responds.'}
              </div>
            </div>
          )}
          {error && <div className="mc-error">{error}</div>}
        </div>

        {/* intelligence rail */}
        <div className="mc-rail">
          {/* Verdict: static, measured, independent of the backend's state. */}
          <VerdictCard analysis={analysis} craterName={craters[craterId]?.name ?? craterId} />

          {thresholdsDrifted && (
            <div className="mc-drift">
              Studio thresholds (CPR &gt; {cprTh}, DOP &lt; {dopTh}) differ from the precomputed
              verdict's (CPR &gt; {analysis!.thresholds.cpr_threshold}, DOP &lt; {analysis!.thresholds.dop_threshold}).
              The card above does not move with these sliders — regenerate the analysis to change it.
            </div>
          )}

          <StepPanel
              probeOn={probeOn}
              onProbe={(on) => { setProbeOn(on); if (!on) setProbe(null); }}
              step={step}
              analysis={analysis}
              mission={mission}
              craterId={craterId}
              craters={craters}
              onSelectCrater={setCraterId}
              selectedLandingSite={selectedSite}
              onSelectLandingSite={setSelectedSite}
              roverAlgo={roverAlgo}
              setRoverAlgo={setRoverAlgo}
              cprTh={cprTh} dopTh={dopTh} iceDepth={iceDepth} iceFrac={iceFrac}
              onUpdateParams={(p) => {
                if (p.cprThreshold !== undefined) setCprTh(p.cprThreshold);
                if (p.dopThreshold !== undefined) setDopTh(p.dopThreshold);
                if (p.iceDepthM !== undefined) setIceDepth(p.iceDepthM);
                if (p.iceFraction !== undefined) setIceFrac(p.iceFraction);
              }}
          />
        </div>
      </div>
      {/* ── bottom context bar ──
          Every cell is bound to one AnalysisValue and renders that value's own
          provenance mark. A cell whose value does not exist shows an em dash and
          the reason; it is never filled from the backend. */}
      <div className="mc-contextbar">
        {!analysisReady && <div className="mc-ctx mc-ctx--empty">Loading measured analysis…</div>}
        {analysisReady && !analysis && (
          <div className="mc-ctx mc-ctx--empty">
            No precomputed analysis for {craters[craterId]?.name ?? craterId} — values withheld
            rather than simulated. Run <code>python backend/scripts/build_analysis.py {craterId}</code>.
          </div>
        )}
        {cells.map((c) => {
          const missing = isMissing(c.v);
          return (
            <div className={`mc-ctx ${missing ? 'mc-ctx--na' : ''}`} key={c.k} title={c.v?.note ?? c.v?.reason ?? ''}>
              <span className="mc-ctx-k">
                {c.k}
                {c.v && <Pv p={c.v.provenance} />}
              </span>
              <span className={`mc-ctx-v ${missing ? 'mc-ctx-v--na' : ''}`}>
                {missing ? '—' : `${showValue(c.v, c.digits)}${c.suffix ?? ''}`}
              </span>
              <span className="mc-ctx-sub">
                {missing ? (c.v?.reason ? 'not computable — see note' : 'unavailable') : c.sub}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

