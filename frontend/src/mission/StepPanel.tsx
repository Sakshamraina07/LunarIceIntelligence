/**
 * StepPanel.tsx — the 12 workflow modules, redrawn in the Mission Control
 * design language (.mc-*). Each module is driven by the real backend mission
 * state; nothing scientific is computed here. Steps whose figures are
 * illustrative (route trade-off narrative, ablation walk-through, viva prompts)
 * are labelled as such and, where possible, derived from live route data so we
 * never fabricate a backend result.
 */
import { useState } from 'react';
import type {
  MissionState, CraterInfo, CandidateLandingSite, SensitivityAnalysisResult,
} from '../types/mission';
import { fetchSensitivity, getReportPdfUrl } from '../services/api';
import { Check, X, Download, Play } from 'lucide-react';

interface Props {
  step: number;
  mission: MissionState;
  craters: Record<string, CraterInfo>;
  onSelectCrater: (id: string) => void;
  selectedLandingSite: CandidateLandingSite | null;
  onSelectLandingSite: (s: CandidateLandingSite) => void;
  roverAlgo: string;
  setRoverAlgo: (a: string) => void;
  cprTh: number; dopTh: number; iceDepth: number; iceFrac: number;
  onUpdateParams: (p: Record<string, number>) => void;
}

function Head({ eyebrow, title, desc }: { eyebrow: string; title: string; desc: string }) {
  return (
    <div>
      <div className="mc-eyebrow">{eyebrow}</div>
      <div className="mc-mod-title">{title}</div>
      <div className="mc-mod-desc">{desc}</div>
    </div>
  );
}

function Metric({ k, v, sub }: { k: string; v: string; sub?: string; }) {
  return (
    <div className="mc-metric">
      <div className="mc-metric-k">{k}</div>
      <div className="mc-metric-v">{v}</div>
      {sub && <div className="mc-metric-sub">{sub}</div>}
    </div>
  );
}

export function StepPanel(props: Props) {
  const { step, mission } = props;
  const [sweep, setSweep] = useState<SensitivityAnalysisResult | null>(null);

  const runSweep = async (name: string) => {
    try {
      setSweep(await fetchSensitivity(name, mission.ice.scientific_candidate_area_km2));
    } catch (e) { console.error(e); }
  };

  // ── STEP 1 · Target Selection ─────────────────────────────────
  if (step === 1) {
    return (
      <div className="mc-card mc-fadein">
        <Head eyebrow="Stage 01 · Target" title="South Polar Crater Selection"
          desc="Only craters with calibrated Chandrayaan-2 swaths on disk are selectable — the rest stay disabled for honesty." />
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '0.9rem' }}>
          {Object.values(props.craters).map((c) => {
            const active = c.is_active ?? true;
            const sel = mission.selected_crater.id === c.id;
            return (
              <button key={c.id} disabled={!active} onClick={() => active && props.onSelectCrater(c.id)}
                className={`mc-chipbtn ${sel ? 'mc-chipbtn--on' : ''}`}
                style={{ justifyContent: 'space-between', padding: '0.6rem 0.7rem', opacity: active ? 1 : 0.45, cursor: active ? 'pointer' : 'not-allowed' }}>
                <span style={{ display: 'flex', flexDirection: 'column', gap: '0.15rem', textAlign: 'left' }}>
                  <span style={{ color: sel ? 'var(--mc-accent)' : 'var(--mc-text)', fontWeight: 600 }}>{c.name}</span>
                  <span style={{ color: 'var(--mc-text-mute)', fontSize: '0.62rem' }}>
                    {c.latitude_deg}° · {c.longitude_deg}° · ⌀{c.diameter_km} km
                  </span>
                </span>
                <span style={{ color: active ? 'var(--mc-good)' : 'var(--mc-warn)', fontSize: '0.56rem' }}>
                  {active ? 'REAL DATA' : (c.status_label || 'PENDING')}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  // ── STEP 2 · Shadow & PSR ─────────────────────────────────────
  if (step === 2) {
    const p = mission.psr;
    return (
      <div className="mc-card mc-fadein">
        <Head eyebrow="Stage 02 · Optical" title="Permanent Shadow & Cold Traps"
          desc="Grazing-sun ray tracing (1.5° elevation) finds hollows that stay below 40 K — where ice can persist." />
        <div className="mc-metrics" style={{ marginTop: '0.9rem' }}>
          <Metric k="PSR Area" v={`${p.psr_area_km2} km²`} sub={`${(p.psr_area_fraction * 100).toFixed(1)}% of domain`} />
          <Metric k="Doubly Shadowed" v={`${p.doubly_shadowed_area_km2} km²`} sub="Shielded from rim glow" />
          <Metric k="Mean Illumination" v={`${(p.mean_illumination_fraction * 100).toFixed(1)}%`} sub="Grazing-sun ratio" />
          <Metric k="Shadow Depth" v={`${p.shadow_depth_estimate_m} m`} sub={`Confidence ${p.confidence_level}`} />
        </div>
        <div className="mc-note" style={{ marginTop: '0.8rem' }}>
          True doubly-shadowed pockets remain below 40 K through the full day/night cycle, enabling volatile retention over billions of years.
        </div>
      </div>
    );
  }

  // ── STEP 3 · DFSAR Radar ──────────────────────────────────────
  if (step === 3) {
    const r = mission.radar;
    return (
      <div className="mc-card mc-fadein">
        <Head eyebrow="Stage 03 · Radar" title="DFSAR Polarimetric Screening"
          desc="Stokes decomposition of the dual-pol swath into CPR and DOP. Icy backscatter reads as high CPR / low DOP." />
        <div className="mc-metrics" style={{ marginTop: '0.9rem' }}>
          <Metric k="Mean CPR" v={`${r.mean_cpr}`} sub={`Peak ${r.max_cpr} · gate > ${r.cpr_threshold_used}`} />
          <Metric k="Mean DOP" v={`${r.mean_dop}`} sub={`Min ${r.min_dop} · gate < ${r.dop_threshold_used}`} />
          <Metric k="Anomaly Area" v={`${r.radar_anomalous_area_km2} km²`} sub={`${(r.screening_pass_fraction * 100).toFixed(2)}% of area`} />
          <Metric k="Gating Rule" v="CPR > 1.0" sub="Coherent backscatter" />
        </div>
        <div className="mc-note" style={{ marginTop: '0.8rem' }}>{r.scientific_interpretation}</div>
      </div>
    );
  }

  // ── STEP 4 · Ice Intelligence ─────────────────────────────────
  if (step === 4) {
    const ice = mission.ice;
    return (
      <div className="mc-card mc-fadein">
        <Head eyebrow="Stage 04 · AI" title="Ice Intelligence — P(ice)"
          desc="Random-Forest likelihood fused with deterministic physical screening (CPR / DOP / shadow overlap)." />
        <div className="mc-metrics" style={{ marginTop: '0.9rem' }}>
          <Metric k="Candidate Area" v={`${ice.scientific_candidate_area_km2} km²`} sub="Passed strict gating" />
          <Metric k="P(ice) mean / peak" v={`${ice.ml_ice_likelihood_mean} / ${ice.ml_ice_likelihood_max}`} sub="RandomForest n=50" />
        </div>
        <div className="mc-details">
          <div className="mc-details-k">Evidence checklist</div>
          <ul className="mc-why">
            {Object.entries(ice.evidence_checklist).map(([k, v]) => (
              <li key={k}>
                {v ? <Check size={14} className="mc-why-ico mc-why-yes" /> : <X size={14} className="mc-why-ico mc-why-no" />}
                <span style={{ color: v ? 'var(--mc-text)' : 'var(--mc-text-mute)' }}>{k.replace(/_/g, ' ')}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="mc-note" style={{ marginTop: '0.8rem' }}>
          <strong style={{ color: 'var(--mc-accent)' }}>Screening {ice.scientific_screening_status === 'PASS' ? 'PASSED' : 'NOT PASSED'}.</strong>{' '}
          {ice.explainability_notes.slice(0, 2).join(' ')}
        </div>
      </div>
    );
  }

  // ── STEP 5 · Terrain Hazards ──────────────────────────────────
  if (step === 5) {
    const t = mission.terrain;
    return (
      <div className="mc-card mc-fadein">
        <Head eyebrow="Stage 05 · Safety" title="Terrain Hazard Scoring"
          desc="Composite hazard = 0.50·slope + 0.30·roughness + 0.20·boulders. Slopes > 20° are impassable." />
        <div className="mc-metrics" style={{ marginTop: '0.9rem' }}>
          <Metric k="Mean Slope" v={`${t.mean_slope_deg}°`} sub={`Max ${t.max_slope_deg}°`} />
          <Metric k="Traversable" v={`${(t.safe_slope_fraction * 100).toFixed(1)}%`} sub="Slope ≤ 12°" />
          <Metric k="Mean Roughness" v={`${t.mean_roughness}`} sub="Local TRI" />
          <Metric k="Critical Zone" v={`${t.high_hazard_area_km2} km²`} sub="Hazard ≥ 0.70" />
        </div>
        <div className="mc-note" style={{ marginTop: '0.8rem' }}>Mean composite hazard score {t.mean_hazard_score}. Rover tilt safety cutoff is 20°.</div>
      </div>
    );
  }
  // ── STEP 6 · Landing Sites ────────────────────────────────────
  if (step === 6) {
    return (
      <div className="mc-card mc-fadein">
        <Head eyebrow="Stage 06 · Landing" title="Landing Site Ranking"
          desc="Rim ridges scored on safety (40%), illumination (25%), science (20%), distance penalty (15%)." />
        <table className="mc-table" style={{ marginTop: '0.9rem' }}>
          <thead><tr><th>#</th><th>Site</th><th>Slope</th><th>Illum</th><th>Dist</th><th>Score</th></tr></thead>
          <tbody>
            {mission.landing_sites.map((s) => {
              const sel = props.selectedLandingSite?.site_id === s.site_id;
              return (
                <tr key={s.site_id} className={sel ? 'mc-tr--sel' : ''} onClick={() => props.onSelectLandingSite(s)}>
                  <td style={{ fontFamily: "'JetBrains Mono',monospace" }}>{s.is_recommended ? '★' : ''}{s.rank}</td>
                  <td>{s.name}</td>
                  <td>{s.slope_deg}°</td>
                  <td>{(s.illumination_fraction * 100).toFixed(0)}%</td>
                  <td>{s.distance_to_target_km} km</td>
                  <td style={{ color: 'var(--mc-accent)', fontWeight: 600 }}>{s.composite_landing_score}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {props.selectedLandingSite && (
          <div className="mc-note" style={{ marginTop: '0.8rem' }}>
            <strong style={{ color: 'var(--mc-accent)' }}>{props.selectedLandingSite.name}:</strong>{' '}
            {props.selectedLandingSite.selection_rationale.join(' · ')}
          </div>
        )}
      </div>
    );
  }

  // ── STEP 7 · Rover Traverse ───────────────────────────────────
  if (step === 7) {
    const routes = mission.rover_routes;
    return (
      <div className="mc-card mc-fadein">
        <div className="mc-row">
          <Head eyebrow="Stage 07 · Rover" title="Multi-Strategy Traverse"
            desc="Shortest, Safest and Science-Aware routes via A* / Dijkstra graph search." />
          <select className="mc-select" value={props.roverAlgo} onChange={(e) => props.setRoverAlgo(e.target.value)}>
            <option value="A*">A*</option>
            <option value="Dijkstra">Dijkstra</option>
          </select>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '0.9rem' }}>
          {['Shortest', 'Safest', 'Science-Aware'].map((k) => {
            const r = routes[k];
            if (!r) return null;
            const sci = k === 'Science-Aware';
            return (
              <div key={k} className="mc-metric" style={{ borderColor: sci ? 'var(--mc-line-strong)' : undefined }}>
                <div className="mc-row">
                  <span style={{ color: sci ? 'var(--mc-accent)' : 'var(--mc-text)', fontWeight: 600, fontSize: '0.8rem' }}>{k}</span>
                  <span className="mc-metric-sub">{r.algorithm_used} · {r.path_found ? `${r.total_distance_km} km` : 'no path'}</span>
                </div>
                <div className="mc-metric-sub" style={{ marginTop: '0.35rem' }}>
                  {r.estimated_travel_time_hours} h · {r.total_energy_wh} Wh · hazard {r.mean_hazard_encountered} · science {r.total_scientific_value_collected}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // ── STEP 8 · Volume Estimate ──────────────────────────────────
  if (step === 8) {
    const v = mission.volume;
    const tiers = [
      { k: 'Conservative', vol: v.conservative_volume_m3, mass: v.conservative_mass_metric_tons, a: v.conservative_assumptions },
      { k: 'Expected', vol: v.expected_volume_m3, mass: v.expected_mass_metric_tons, a: v.expected_assumptions },
      { k: 'Upper Bound', vol: v.upper_volume_m3, mass: v.upper_mass_metric_tons, a: v.upper_assumptions },
    ];
    return (
      <div className="mc-card mc-fadein">
        <Head eyebrow="Stage 08 · Volume" title="Ice-Equivalent Volume"
          desc="Volume = candidate area × assumed depth × ice fraction, across a 3-tier uncertainty band." />
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '0.9rem' }}>
          {tiers.map((t) => (
            <div key={t.k} className="mc-metric" style={{ borderColor: t.k === 'Expected' ? 'var(--mc-line-strong)' : undefined }}>
              <div className="mc-row">
                <span style={{ color: t.k === 'Expected' ? 'var(--mc-accent)' : 'var(--mc-text)', fontWeight: 600, fontSize: '0.78rem' }}>{t.k}</span>
                <span className="mc-metric-sub">depth {t.a.assumed_depth_m}m · {(t.a.ice_volume_fraction * 100).toFixed(0)}%</span>
              </div>
              <div className="mc-metric-v" style={{ fontSize: '1rem', marginTop: '0.25rem' }}>{(t.vol / 1e6).toFixed(2)}M m³</div>
              <div className="mc-metric-sub">{t.mass.toLocaleString()} metric tons</div>
            </div>
          ))}
        </div>
        <div className="mc-note" style={{ marginTop: '0.8rem', borderLeftColor: 'var(--mc-warn)' }}>{v.limitation_statement}</div>
      </div>
    );
  }

  // ── STEP 9 · Sensitivity Studio ───────────────────────────────
  if (step === 9) {
    const sliders = [
      { label: 'CPR Threshold', val: props.cprTh, min: 0.6, max: 1.6, step: 0.05, key: 'cprThreshold', fmt: (n: number) => n.toFixed(2) },
      { label: 'DOP Threshold', val: props.dopTh, min: 0.06, max: 0.20, step: 0.01, key: 'dopThreshold', fmt: (n: number) => n.toFixed(2) },
      { label: 'Assumed Depth (m)', val: props.iceDepth, min: 1, max: 12, step: 0.5, key: 'iceDepthM', fmt: (n: number) => `${n}` },
      { label: 'Ice Fraction', val: props.iceFrac, min: 0.03, max: 0.35, step: 0.01, key: 'iceFraction', fmt: (n: number) => `${(n * 100).toFixed(0)}%` },
    ];
    return (
      <div className="mc-card mc-fadein">
        <Head eyebrow="Stage 09 · Sweep" title="Sensitivity Studio"
          desc="Vary the core thresholds live and re-run the pipeline to prove results are stable, not brittle." />
        <div style={{ marginTop: '0.9rem', display: 'flex', flexDirection: 'column', gap: '0.7rem' }}>
          {sliders.map((s) => (
            <div key={s.key}>
              <div className="mc-slider-row"><span>{s.label}</span><span style={{ color: 'var(--mc-accent)', fontFamily: "'JetBrains Mono',monospace" }}>{s.fmt(s.val)}</span></div>
              <input className="mc-slider" type="range" min={s.min} max={s.max} step={s.step} value={s.val}
                onChange={(e) => props.onUpdateParams({ [s.key]: parseFloat(e.target.value) })} />
            </div>
          ))}
        </div>
        <div className="mc-details">
          <div className="mc-details-k">Parametric sweep</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.4rem' }}>
            {['cpr_threshold', 'dop_threshold', 'assumed_depth_m', 'ice_fraction'].map((n) => (
              <button key={n} className="mc-chipbtn" onClick={() => runSweep(n)}>
                <Play size={11} /> {n.replace(/_/g, ' ')}
              </button>
            ))}
          </div>
          {sweep && (
            <div className="mc-note" style={{ marginTop: '0.7rem' }}>
              <strong style={{ color: 'var(--mc-accent)' }}>{sweep.parameter_tested}</strong> — {sweep.sensitivity_summary}
              <table className="mc-table" style={{ marginTop: '0.5rem' }}>
                <thead><tr><th>Value</th><th>Area km²</th><th>Vol M m³</th></tr></thead>
                <tbody>
                  {sweep.results.map((pt, i) => (
                    <tr key={i}><td>{pt.parameter_value}</td><td>{pt.candidate_ice_area_km2}</td><td>{(pt.expected_volume_m3 / 1e6).toFixed(2)}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    );
  }
  // ── STEP 10 · Research Suite ──────────────────────────────────
  if (step === 10) {
    const routes = mission.rover_routes;
    const rows = ['Shortest', 'Safest', 'Science-Aware'].map((k) => routes[k]).filter(Boolean);
    const base = routes['Shortest']?.total_scientific_value_collected || 0;
    return (
      <div className="mc-card mc-fadein">
        <Head eyebrow="Stage 10 · Research" title="Route Trade-Off & Ablation"
          desc="Live comparison of the three planned routes — no fabricated accuracy claims, figures come from the router." />
        <table className="mc-table" style={{ marginTop: '0.9rem' }}>
          <thead><tr><th>Strategy</th><th>Dist</th><th>Hazard</th><th>Science</th></tr></thead>
          <tbody>
            {rows.map((r) => {
              const sci = r.strategy === 'Science-Aware';
              const gain = base > 0 && sci ? ` (+${Math.round((r.total_scientific_value_collected / base - 1) * 100)}%)` : '';
              return (
                <tr key={r.strategy} className={sci ? 'mc-tr--sel' : ''}>
                  <td style={{ color: sci ? 'var(--mc-accent)' : undefined }}>{r.strategy}</td>
                  <td>{r.total_distance_km} km</td>
                  <td>{r.mean_hazard_encountered}</td>
                  <td style={{ fontWeight: sci ? 600 : 400 }}>{r.total_scientific_value_collected}{gain}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <div className="mc-note" style={{ marginTop: '0.8rem' }}>
          The Science-Aware route trades a modest distance overhead for markedly higher volatile sampling by routing through secondary cold traps. Ablation ordering (distance → slope → roughness → boulders → solar → science) is illustrative of the cost model's construction.
        </div>
      </div>
    );
  }

  // ── STEP 11 · Viva Rationale ──────────────────────────────────
  if (step === 11) {
    const site = mission.recommended_landing_site;
    const ice = mission.ice;
    const passed = Object.entries(ice.evidence_checklist).filter(([, v]) => v).map(([k]) => k.replace(/_/g, ' '));
    const failed = Object.entries(ice.evidence_checklist).filter(([, v]) => !v).map(([k]) => k.replace(/_/g, ' '));
    return (
      <div className="mc-card mc-fadein">
        <Head eyebrow="Stage 11 · Defense" title="Defensible Rationale"
          desc="Every claim below is derived from this run's computed state — ready to defend in a viva." />
        <div className="mc-details">
          <div className="mc-details-k">Why this landing site</div>
          <ul className="mc-why" style={{ marginTop: 0 }}>
            {site.selection_rationale.map((r, i) => (
              <li key={i}><Check size={14} className="mc-why-ico mc-why-yes" /><span>{r}</span></li>
            ))}
          </ul>
        </div>
        <div className="mc-details">
          <div className="mc-details-k">Ice evidence — satisfied</div>
          <ul className="mc-why" style={{ marginTop: 0 }}>
            {passed.length ? passed.map((k) => (
              <li key={k}><Check size={14} className="mc-why-ico mc-why-yes" /><span>{k}</span></li>
            )) : <li><X size={14} className="mc-why-ico mc-why-no" /><span style={{ color: 'var(--mc-text-mute)' }}>None satisfied this run</span></li>}
          </ul>
        </div>
        {failed.length > 0 && (
          <div className="mc-note" style={{ marginTop: '0.8rem', borderLeftColor: 'var(--mc-warn)' }}>
            Honest caveat — not yet satisfied: {failed.join(', ')}. Peak P(ice) {ice.ml_ice_likelihood_max}; screening {ice.scientific_screening_status === 'PASS' ? 'passed' : 'not passed'}.
          </div>
        )}
      </div>
    );
  }

  // ── STEP 12 · Mission Report ──────────────────────────────────
  if (step === 12) {
    return (
      <div className="mc-card mc-fadein">
        <Head eyebrow="Stage 12 · Report" title="Mission Decision Report"
          desc="Publication-ready PDF/JSON with full provenance and the source product id." />
        <div className="mc-details">
          <div className="mc-kv-grid">
            <div><div className="mc-kv-k">Crater</div><div className="mc-kv-v">{mission.selected_crater.name}</div></div>
            <div><div className="mc-kv-k">Mode</div><div className="mc-kv-v">{mission.data_mode}</div></div>
            {/* Was `Seed`, reading psr.provenance.random_seed — a demo-generator
                field that is null on a REAL run. The product id is what makes
                this report reproducible. */}
            <div><div className="mc-kv-k">Product</div><div className="mc-kv-v" style={{ fontSize: '0.62rem', wordBreak: 'break-all' }}>{mission.selected_crater.product_id ?? 'NO DATA'}</div></div>
            <div><div className="mc-kv-k">Generated</div><div className="mc-kv-v" style={{ fontSize: '0.7rem' }}>{new Date(mission.generated_at).toLocaleString()}</div></div>
          </div>
        </div>
        <a className="mc-btn mc-btn--solid" style={{ marginTop: '0.9rem', width: '100%', justifyContent: 'center' }}
          href={getReportPdfUrl(mission.selected_crater.id)} target="_blank" rel="noopener noreferrer">
          <Download size={14} /> Download PDF Report
        </a>
      </div>
    );
  }

  return null;
}

