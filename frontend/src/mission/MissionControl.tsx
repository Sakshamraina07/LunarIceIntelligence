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
import { MissionMap, type MissionMapHandle, groundResolutionLabel, loadManifest } from './MissionMap';
import { VerdictCard } from './VerdictCard';
import { StepPanel } from './StepPanel';
import { STEPS, LAYERS, LAYER_MAP } from './config';
import type { LayerDef } from './config';
import { loadAnalysis, PROV_MARK, isMissing, showValue } from './analysis';
import type { Analysis, AnalysisValue, Provenance } from './analysis';
import { Download, ZoomIn, ZoomOut, Maximize2, MapPin, Check } from 'lucide-react';
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

function provBadge(l: LayerDef): string {
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
    { k: 'CPR (mean)', v: v.cpr_mean, sub: cprMax != null ? `peak ${cprMax.toPrecision(3)}` : 'over measured px' },
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
      k: 'Top 1% CPR',
      v: v.cpr_p99,
      sub: 'ranking within this swath — not a detection',
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
  const [showRoute, setShowRoute] = useState(true);
  const [selectedSite, setSelectedSite] = useState<CandidateLandingSite | null>(null);
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
  useEffect(() => {
    loadManifest().then((m) => {
      if (!m) return;
      setLayerCopy(Object.fromEntries(m.layers.map((l) => [l.id, l.description])));
    });
  }, []);

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
            activeRoverStrategies={activeRoutes}
            selectedLandingSite={selectedSite}
            onSelectLandingSite={setSelectedSite}
            onCoords={setCoords}
            onZoom={setZoom}
          />

          {/* layer control */}
          <div className="mc-map-overlay mc-map-panel mc-layerctl">
            <div className="mc-layerctl-head">Layers</div>
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
            <button className={`mc-layer ${showRoute ? 'mc-layer--on' : ''}`} onClick={() => setShowRoute((v) => !v)}>
              <span className="mc-layer-sw" style={{ background: '#4fd1e6' }} /> Rover Route
              <Check size={13} className="mc-layer-check" />
            </button>
          </div>

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
                <span className={`mc-prov mc-prov--${legend.provenance}`}>{provBadge(legend)}</span>
              </div>
              <div className="mc-legend-bar" style={{ background: legend.gradient }} />
              <div className="mc-legend-ends"><span>{legend.low}</span><span>{legend.high}</span></div>
              {/* From layers.json, not from config.ts. The manifest is written by
                  the same script that renders the pixels, so this caption cannot
                  describe a different formula than the image it sits under. */}
              {layerCopy[activeLayer] && <div className="mc-legend-hint">{layerCopy[activeLayer]}</div>}
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
              TERRAIN LOADED · {error ? 'ANALYSIS UNAVAILABLE' : loading ? 'ANALYSIS PENDING' : 'NO ANALYSIS'}
              <div className="mc-map-vectorstate-sub">
                {error
                  ? 'Landing sites and rover routes need the on-demand backend, which is not reachable. Every raster above is a static asset and is unaffected.'
                  : 'Rasters are served from the CDN and are already drawn. Landing-site and route vectors follow when the backend responds.'}
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

