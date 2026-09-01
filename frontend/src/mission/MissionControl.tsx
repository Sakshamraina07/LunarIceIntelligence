/**
 * MissionControl.tsx — the post-landing analysis environment. Orchestrates the
 * hero map (≈70%) + intelligence rail (≈30%), a top command bar, a 12-stage
 * progress stepper and a bottom context bar. State is ported from the old
 * App.tsx; all scientific values still come from the FastAPI backend.
 */
import { useEffect, useRef, useState } from 'react';
import { fetchCraters, fetchMissionState, getReportPdfUrl } from '../services/api';
import type { MissionState, CraterInfo, CandidateLandingSite } from '../types/mission';
import { MissionMap, type MissionMapHandle } from './MissionMap';
import { VerdictCard } from './VerdictCard';
import { StepPanel } from './StepPanel';
import { STEPS, LAYERS, LAYER_MAP } from './config';
import { Download, ZoomIn, ZoomOut, Maximize2, MapPin, Check } from 'lucide-react';
import './mc.css';

const STEP_LAYER: Record<number, string> = {
  1: 'hillshade', 2: 'illumination', 3: 'cpr_heatmap', 4: 'ml_likelihood',
  5: 'hazard_map', 6: 'hillshade', 7: 'hillshade', 8: 'dem_elevation',
  9: 'cpr_heatmap', 10: 'hazard_map', 11: 'hillshade', 12: 'hillshade',
};

export default function MissionControl() {
  const [craters, setCraters] = useState<Record<string, CraterInfo>>({});
  const [craterId, setCraterId] = useState('faustini');
  const [mission, setMission] = useState<MissionState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [step, setStep] = useState(1);
  const [activeLayer, setActiveLayer] = useState('cpr_heatmap');
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

  const mapRef = useRef<MissionMapHandle>(null);

  useEffect(() => {
    fetchCraters().then(setCraters).catch(() =>
      setError('Cannot reach the Lunar Intelligence backend on port 8000.'));
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    // REAL locally (raw SAR present); DEMO in hosted deploys where the 9GB
    // dataset isn't available — set VITE_DATA_MODE=DEMO on Vercel. UI badge reflects this.
    const dataMode = (import.meta.env.VITE_DATA_MODE as string) ?? 'REAL';
    fetchMissionState(craterId, { dataMode, cprThreshold: cprTh, dopThreshold: dopTh, iceDepthM: iceDepth, iceFraction: iceFrac, algorithm: roverAlgo })
      .then((d) => { setMission(d); setSelectedSite(d.recommended_landing_site); setLoading(false); })
      .catch((e) => { setError(e.message || 'Mission execution error'); setLoading(false); });
  }, [craterId, cprTh, dopTh, iceDepth, iceFrac, roverAlgo]);

  const gotoStep = (s: number) => { setStep(s); if (STEP_LAYER[s]) setActiveLayer(STEP_LAYER[s]); };
  const activeRoutes = showRoute ? ['Shortest', 'Safest', 'Science-Aware'] : [];
  const legend = LAYER_MAP[activeLayer];
  // Honesty: reflect the EFFECTIVE data mode the backend actually used, not the
  // crater's capability flag. A real-capable crater served from a host without the
  // raw SAR files comes back as DEMO — the badge must say DEMO, never "REAL".
  const isReal = mission?.data_mode === 'REAL';

  // PLACEHOLDER_RENDER
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
          <span className={`mc-badge ${isReal ? 'mc-badge--real' : 'mc-badge--demo'}`}>
            <span className="mc-badge-dot" /> {isReal ? 'REAL DATA' : 'DEMO'}
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
          {mission && (
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
          )}

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

          {/* legend */}
          {legend && (
            <div className="mc-map-overlay mc-map-panel mc-map-legend">
              <div className="mc-legend-title">{legend.label}</div>
              <div className="mc-legend-bar" style={{ background: legend.gradient }} />
              <div className="mc-legend-ends"><span>{legend.low}</span><span>{legend.high}</span></div>
              {legend.description && <div className="mc-legend-hint">{legend.description}</div>}
            </div>
          )}

          {/* readout */}
          <div className="mc-map-overlay mc-map-panel mc-map-readout">
            <div>{coords}</div>
            <div style={{ color: 'var(--mc-accent)' }}>
              ZOOM {zoom} · {zoom > 3 ? 'UPSCALED (max native detail)' : `${Math.min(zoom, 3)} native`}
            </div>
          </div>

          {loading && (
            <div className="mc-loading"><div className="mc-ring" /><div>Executing computational pipeline…</div></div>
          )}
          {error && <div className="mc-error">{error}</div>}
        </div>

        {/* intelligence rail */}
        <div className="mc-rail">
          {mission && <VerdictCard mission={mission} />}
          {mission && (
            <StepPanel
              step={step}
              mission={mission}
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
          )}
        </div>
      </div>

      {/* ── bottom context bar ── */}
      {mission && (
        <div className="mc-contextbar">
          {[
            { k: 'CPR (mean)', v: `${mission.radar.mean_cpr}`, sub: `peak ${mission.radar.max_cpr}` },
            { k: 'DOP (mean)', v: `${mission.radar.mean_dop}`, sub: `min ${mission.radar.min_dop}` },
            { k: 'PSR Area', v: `${mission.psr.psr_area_km2}`, sub: 'km² shadowed' },
            { k: 'Mean Slope', v: `${mission.terrain.mean_slope_deg}°`, sub: `max ${mission.terrain.max_slope_deg}°` },
            { k: 'Peak P(ice)', v: `${Math.round((mission.ice.ml_ice_likelihood_max ?? 0) * 100)}%`, sub: mission.ice.scientific_screening_status === 'PASS' ? 'screen passed' : 'screen not passed' },
            { k: 'Ice Volume', v: `${(mission.volume.expected_volume_m3 / 1e6).toFixed(2)}M`, sub: 'm³ expected' },
            { k: 'Rover', v: mission.rover_routes['Science-Aware']?.path_found ? `${mission.rover_routes['Science-Aware'].total_distance_km} km` : 'no path', sub: 'science-aware' },
          ].map((c) => (
            <div className="mc-ctx" key={c.k}>
              <span className="mc-ctx-k">{c.k}</span>
              <span className="mc-ctx-v">{c.v}</span>
              <span className="mc-ctx-sub">{c.sub}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
