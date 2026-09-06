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
import { fetchCraters, fetchMissionState, getReportPdfUrl, API_ORIGIN,
         MissionUnavailable, fetchReportState,
         type BackendState, type ReportState } from '../services/api';
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
import { PanelBoundary } from './PanelBoundary';
import { ProbeReadout } from './ProbeReadout';
import { TraversePanel } from './TraversePanel';
import { loadProbeGrid, type ProbeGrid, type ProbeSample } from './probe';
import { loadTraverse, type Traverse } from './traverse';
import { loadSweepGrid, type SweepGrid } from './sweep';
import { Download, ZoomIn, ZoomOut, Maximize2, MapPin, Check, Crosshair, Route } from 'lucide-react';
import './mc.css';

/**
 * The stages the Phase 4 traverse belongs to: 06 Landing Sites and 07 Rover
 * Traverse.
 *
 * It used to draw on every stage including 01 Target Selection, where the whole
 * question is which points were targeted and five routes plus a control panel
 * are simply in the way. A deliverable shown everywhere is not emphasis; it is
 * clutter, and it hides the thing the current stage is about.
 *
 * 07 is included because that stage IS the traverse — hiding it there to satisfy
 * a literal reading of "the landing sites section" would leave the Rover
 * Traverse panel with no rover traverse on it.
 */
const TRAVERSE_STEPS = new Set([6, 7]);

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
  /* `loading` was a second name for `backend === 'pending'`. Two names for one
     condition is the shape of every defect in this file's history — the badge
     said OFFLINE from `error`, the banner said UNAVAILABLE from `error`, and the
     panel below said NOT_INGESTED from the payload. There is one state now. */
  const [error, setError] = useState<string | null>(null);
  /** Which of the three backend states we are actually in. Never inferred from
   *  `error != null`, which cannot tell "nothing answered" from "it answered
   *  and said it has nothing". */
  const [backend, setBackend] = useState<BackendState>('pending');

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
  // The precomputed joint screen. Stage 09's sliders read this instead of
  // re-querying a host that does not hold the rasters.
  const [sweepGrid, setSweepGrid] = useState<SweepGrid | null>(null);
  useEffect(() => { loadSweepGrid().then(setSweepGrid); }, []);
  // The report's OWN availability. Not `backend === 'ok'` -- that is the mission
  // endpoint, which recomputes and needs the rasters. The report renders
  // committed artifacts and is served by hosts the mission endpoint refuses.
  const [reportState, setReportState] = useState<ReportState>('pending');
  useEffect(() => { setReportState('pending'); fetchReportState(craterId).then(setReportState); },
            [craterId]);
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
  const railRef = useRef<HTMLDivElement>(null);
  const traversePanelRef = useRef<HTMLDivElement>(null);


  useEffect(() => {
    fetchCraters().then(setCraters).catch(() =>
      setError(`Cannot reach the analysis backend at ${API_ORIGIN}.`));
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
    setError(null);
    setBackend('pending');
    const dataMode = (import.meta.env.VITE_DATA_MODE as string) ?? 'REAL';
    fetchMissionState(craterId, { dataMode, cprThreshold: cprTh, dopThreshold: dopTh, iceDepthM: iceDepth, iceFraction: iceFrac, algorithm: roverAlgo })
      .then((d) => { setMission(d); setSelectedSite(d.recommended_landing_site); setBackend('ok'); })
      .catch((e) => {
        setError(e?.message || 'Mission execution error');
        setBackend(e instanceof MissionUnavailable ? e.state : 'unreachable');
      });
  }, [craterId, cprTh, dopTh, iceDepth, iceFrac, roverAlgo]);

  /**
   * Move to a stage, switch to its layer, and — for the two stages whose subject
   * is a thing on the map — go and look at that thing.
   *
   * The opening view is a fixed 40 km window on the ribbon centroid. That is the
   * right default: it is panel-independent and shows a 39 km crater as a crater.
   * It is also not where the five searched sites are, so arriving at Landing
   * Sites and having to hunt for them was the complaint. Stage 06 now fits all
   * five; stage 07 fits the selected route. Neither happens on load, so the
   * opening view keeps meaning what it meant.
   */
  const gotoStep = (s: number) => {
    setStep(s);
    if (STEP_LAYER[s]) setActiveLayer(STEP_LAYER[s]);
    // The fit itself is an EFFECT, below — not a requestAnimationFrame from
    // here. See the comment there; it is not a style preference.
  };
  const activeRoutes = showRoute ? ['Shortest', 'Safest', 'Science-Aware'] : [];
  /** The traverse is drawn only where it is the subject. */
  const traverseHere = showTraverse && TRAVERSE_STEPS.has(step) && !!traverse;

  /**
   * Fit the map to the current stage's subject, after React has committed it.
   *
   * NOT `requestAnimationFrame`, which is what this was and why it silently did
   * nothing: rAF only fires when the page actually paints, so on a background
   * tab, a throttled window, or any host that is not compositing, the callback
   * never runs and the fit never happens — with no error and no way to tell that
   * from "the fit ran and chose this view". Measured here: `focusRoute` fired
   * from a click handler worked every time while `focusSites` from an rAF fired
   * never, in the same session. An effect is React's own after-commit hook and
   * has no such condition. It also runs AFTER the map's child effects, so the
   * bounds it fits to are already drawn.
   *
   * Keyed on `step` alone: selecting a route re-fits through `pickRoute`, and
   * putting `selectedRoute` here as well would yank the view on every selection.
   */
  useEffect(() => {
    if (step === 6) mapRef.current?.focusSites();
    else if (step === 7 && selectedRoute !== null) mapRef.current?.focusRoute(selectedRoute);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  /**
   * Bring the traverse controls into view when their stage opens.
   *
   * Placing the panel high in the rail was not enough on its own: the verdict
   * card alone is taller than the rail, so the panel still started 146 % of a
   * rail-height down — present, and below the fold, which is the same as absent
   * for anyone who does not already know it is there. The rail is scrolled to it
   * instead. The verdict is one scroll up and the stage panel one scroll down;
   * nothing is hidden, the stage's own controls are simply where the eye lands.
   */
  useEffect(() => {
    if (!traverseHere) return;
    const rail = railRef.current;
    const el = traversePanelRef.current;
    if (!rail || !el) return;
    // Same reason as the fit above: this is already inside an effect, so the
    // layout is committed and there is nothing to wait for a paint for.
    // INSTANT, not smooth. Smooth scrolling is animated by the compositor and
    // does not run on a page that is not painting — the same condition that
    // stopped the stage fit when it was a requestAnimationFrame. Measured here:
    // with smooth, the panel stayed 190 % of a rail-height down. This is a
    // reposition on a stage change, not a gesture, so there is nothing to
    // animate anyway.
    rail.scrollTo({
      top: Math.max(0, el.offsetTop - rail.offsetTop - 8),
      behavior: 'auto',
    });
  }, [traverseHere, step]);
  const legend = LAYER_MAP[activeLayer];

  // Two independent mode chips, because there are two independent data paths and
  // conflating them is exactly how a DEMO verdict came to wear a REAL label.
  const verdictReal = analysis?.data_mode === 'REAL';
  // NOT DELETED WITH THE HEADER BADGE. A host can answer OK and still be
  // serving generated data, which is a fourth thing to say and not one of the
  // three states -- `ok` describes the CONNECTION, this describes the PAYLOAD.
  // It is passed to stage 09, which now owns host state, rather than dropped
  // because the chip that used to carry it moved.
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
          {/* THE HOST-STATE BADGE USED TO LIVE HERE AND IT IS NOT DELETED --
              it moved to the Sensitivity Studio stage, which is the only screen
              it describes. See StepPanel step 9.

              In the global header, beside VERDICT, it read as a system-wide
              failure. It is not one: the verdict, the rasters, the searched
              landing sites, the Phase 4 traverse, the criteria probe AND the
              stage-09 sweep tables are all static artifacts that render on a
              host with no rasters. What a no-raster host actually costs is four
              sliders and the PDF button, so the two controls that lose something
              say so THEMSELVES -- the Report control below, and stage 09.

              An indicator positioned to imply more breakage than exists is the
              same class of error as a caption that stopped tracking its
              computation; it just fails in the pessimistic direction. */}
          {/* THE REPORT CONTROL IS A FUNCTION OF THE SAME THREE STATES.
              `/report/pdf/{crater}` returns 409 unless the host has the ingested
              rasters, which the deployed host does not — the 409 is correct
              behaviour, and a button that quietly produces one is not. So the
              control says which state it is in instead of vanishing or lying. */}
          {reportState === 'available' ? (
            <a className="mc-btn mc-btn--solid" href={getReportPdfUrl(craterId)}
               target="_blank" rel="noopener noreferrer"
               title={'A rendering of the committed analysis artifacts. It needs no '
                 + 'rasters, which is why it is served by a host the mission '
                 + 'endpoint reports NOT_INGESTED for.'}>
              <Download size={13} /> Report
            </a>
          ) : (
            <span className="mc-btn mc-btn--off" title={
              reportState === 'no_artifacts'
                ? 'The report endpoint answered, and this host does not carry the '
                  + 'committed analysis artifacts the report renders, so it returns '
                  + '409 rather than a thinner document.'
                : reportState === 'unreachable'
                  ? `Nothing answered at ${API_ORIGIN}, so no report can be requested.`
                  : 'Asking the report endpoint.'
            }>
              <Download size={13} /> Report<span className="mc-btn-na">
                {reportState === 'no_artifacts' ? 'host has no analysis artifacts'
                  : reportState === 'unreachable' ? 'backend unreachable' : '…'}
              </span>
            </span>
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
          {/* THE FLOOR. One throw in this component blanked the whole page in
              production; it is contained now, and the rest of the screen — the
              verdict, the stat bar, the stage panels, all of which read static
              artifacts and need no backend — stays alive. */}
          <PanelBoundary name="Mission map">
          <MissionMap
            ref={mapRef}
            mission={mission}
            activeLayer={activeLayer}
            showLandingSites={showLandingSites}
            scienceOpacity={scienceOpacity}
            searchedSites={searched?.sites ?? null}
            traverse={traverseHere ? traverse : null}
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
          </PanelBoundary>

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
            {/* Off-stage this does not silently do nothing: it says which
                stage owns the traverse and goes there. A toggle that appears to
                fail is worse than one that is absent. */}
            <button
              className={`mc-layer ${traverseHere ? 'mc-layer--on' : ''}`}
              onClick={() => {
                if (!TRAVERSE_STEPS.has(step)) { gotoStep(6); setShowTraverse(true); return; }
                setShowTraverse((v) => !v);
              }}
              title={TRAVERSE_STEPS.has(step)
                ? undefined
                : 'The traverse is drawn on stage 06 Landing Sites and 07 Rover Traverse. '
                  + 'Click to go there.'}
            >
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
          {/* Only the probe floats over the map now. The traverse panel moved
              into the rail: it covered the top-right quadrant, which is where
              several of the searched sites are, so the panel describing the
              sites was hiding them. */}
          {probeOn && (
            <div className="mc-mapstack">
              <ProbeReadout grid={probeGrid} settled={probeSettled} sample={probe}
                            onClose={() => { setProbeOn(false); setProbe(null); }} />
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

          {/* THE HOST-STATE BANNER OVER THE MAP IS GONE, AND ITS TEXT IS NOT
              LOST — the same words, corrected for their location, are in stage
              12 beside the report control they describe.

              It was a panel over the product announcing that a subsystem was
              unavailable, on a screen where NOTHING it covered was unavailable:
              the relief, the science layers, the searched landing sites, the
              Phase 4 traverse, the criteria probe and the verdict are all static
              artifacts and all render on a host with no rasters. Once the sweep
              grid was precomputed, the last thing on this screen that needed the
              on-demand host was gone, and the banner was announcing a loss that
              no longer existed anywhere in view.

              THE MAP IS THE PRODUCT. A caveat drawn on top of it has to be about
              the map. This one never was, and after the sweep grid it was not
              about anything on the screen at all. The one control that genuinely
              loses something — Report, in the top bar — still says so itself. */}
          {/* THE RED ERROR BANNER IS GONE FROM THE MAP, AND ITS TEXT IS NOT.
              It rendered the mission endpoint's NOT_INGESTED message as an
              ERROR across the top of the product. That message is accurate and
              well written — it names the product id, names the missing rasters
              and says why a served host reports absence rather than
              substituting generated data — but it is not an error, and after
              the sweep grid and the report-status fix it describes a condition
              that costs this screen nothing at all: the relief, the science
              layers, the sites, the traverse, the probe, the verdict, stage
              09's sweep and the PDF all work without it.

              Red is a claim. Reserving it for conditions that actually break
              something is the whole point of having it, and this one broke
              nothing. The full text now sits in stage 12's host-state block,
              beside the only control that ever cared, one click away and
              verbatim. See StepPanel step 12 and G15's `hostreason` assertion. */}
        </div>

        {/* intelligence rail */}
        <div className="mc-rail" ref={railRef}>
          {/* Verdict: static, measured, independent of the backend's state. */}
          <PanelBoundary name="Verdict">
            <VerdictCard analysis={analysis} craterName={craters[craterId]?.name ?? craterId} />
          </PanelBoundary>

          {thresholdsDrifted && (
            <div className="mc-drift">
              Studio thresholds (CPR &gt; {cprTh}, DOP &lt; {dopTh}) differ from the precomputed
              verdict's (CPR &gt; {analysis!.thresholds.cpr_threshold}, DOP &lt; {analysis!.thresholds.dop_threshold}).
              The card above does not move with these sliders — regenerate the analysis to change it.
            </div>
          )}

          {/* The traverse controls, in the rail and only on the two stages they
              belong to, ABOVE the step panel: on those stages the traverse is
              what the map is showing, and a rail this tall buries anything
              underneath. The routes on the map are gated by the same flag, so a
              panel can never be describing lines that are not drawn. */}
          {traverseHere && (
            <div ref={traversePanelRef}>
            <TraversePanel
              inRail
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
            </div>
          )}

          <PanelBoundary name={`Stage ${String(step).padStart(2, '0')}`}>
          <StepPanel
              searchedSites={searched}
              traverse={traverse}
              probeOn={probeOn}
              onProbe={(on) => { setProbeOn(on); if (!on) setProbe(null); }}
              step={step}
              backend={backend}
              backendReal={backendReal}
              sweepGrid={sweepGrid}
              reportState={reportState}
              backendReason={error}
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
          </PanelBoundary>

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

