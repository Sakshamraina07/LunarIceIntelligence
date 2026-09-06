/**
 * StepPanel.tsx — the 12 workflow stages.
 *
 * SOURCE OF TRUTH: the precomputed analysis asset (public/analysis/<crater>.json),
 * the same file the verdict card reads. NOT GET /api/mission/{crater}.
 *
 * Why the swap. The backend recomputes on a 100 x 100 bilinear resample of the
 * padded frame and takes every statistic over the whole frame, 84 % of which is
 * never-observed padding. Measured on this scene:
 *
 *     quantity     native, masked    100² bilinear    error
 *     CPR mean     0.001312          0.000238         5.5x low
 *     CPR max      0.053411          0.043846         18 % low
 *     DOP mean     0.057053          0.009463         6.0x low
 *     DOP p50      0.047532          0.000000         destroyed
 *
 * So these twelve panels and the verdict card above them were printing
 * different numbers for the same quantities, on the same screen, and only one
 * set carried provenance marks. Now there is one producer.
 *
 * RULES THIS FILE OBEYS
 *   · Every figure is an AnalysisValue rendered through <Figure>, which cannot
 *     draw a number without its mark, and draws an em dash plus the recorded
 *     reason when the value is null.
 *   · No threshold, weight or physical constant is written here. Thresholds come
 *     from analysis.thresholds, weights from analysis.hazard_model, tier
 *     assumptions from analysis.volume_tiers. The previous version hardcoded
 *     "remain below 40 K" (there is no thermal model anywhere in this project),
 *     "RandomForest n=50" (the forest is withdrawn), "Gating Rule: CPR > 1.0"
 *     beside the live threshold, and "Slope ≤ 12°" beside a 20° cutoff.
 *   · A step whose status is UNAVAILABLE renders its absence and its reason. It
 *     does not render an empty table, which reads as a measured zero.
 *
 * The backend `mission` prop is still accepted, and is used for exactly two
 * things that are genuinely on-demand and carry no scientific claim: the crater
 * catalogue selection state, and the PDF download link. It is optional, so the
 * panel renders with the backend stopped.
 */
import type { MissionState, CraterInfo, CandidateLandingSite } from '../types/mission';
import type { Analysis, SweepAxis, SearchedSites } from './analysis';
import type { Traverse } from './traverse';
import { showValue, showPercent, stepStatus } from './analysis';
import { Figure, Pv, StepUnavailable } from './Prov';
import { getReportPdfUrl, API_ORIGIN, BACKEND_COPY,
         type BackendState, type ReportState } from '../services/api';
import { readSweep, nearestIndex, type SweepGrid } from './sweep';
import { Check, X, Minus, Download, Crosshair } from 'lucide-react';

interface Props {
  step: number;
  /** Which of the three backend states the fetch layer observed. Never derived
   *  from `mission != null`, which cannot tell "nothing answered" from "it
   *  answered and said it has nothing" -- the defect that put three sentences
   *  from one boolean on one screen. */
  backend: BackendState;
  /** Whether an `ok` host is serving REAL or generated data. Orthogonal to the
   *  three states: `backend` describes the connection, this the payload. */
  backendReal: boolean;
  /** The precomputed joint screen. `null` means the artifact is absent, and
   *  stage 09 then shows its tables and withholds the interactive grid rather
   *  than indexing into something that is not there. */
  sweepGrid: SweepGrid | null;
  /** The REPORT's own availability, measured at /report/status. Not derived from
   *  `backend`, which is the mission endpoint and a different capability. */
  reportState: ReportState;
  /** The measured producer. `null` means no analysis exists for this crater. */
  analysis: Analysis | null;
  /** On-demand backend. Optional: the panel must render without it. */
  mission: MissionState | null;
  craterId: string;
  craters: Record<string, CraterInfo>;
  onSelectCrater: (id: string) => void;
  selectedLandingSite: CandidateLandingSite | null;
  onSelectLandingSite: (s: CandidateLandingSite) => void;
  roverAlgo: string;
  setRoverAlgo: (a: string) => void;
  cprTh: number; dopTh: number; iceDepth: number; iceFrac: number;
  onUpdateParams: (p: Record<string, number>) => void;
  /** Turn on the criteria probe and let the reader check this screen's verdict
   *  anywhere on the map. Offered HERE because this is the panel that states
   *  the null, and a conclusion is worth more when the instrument behind it is
   *  one click away rather than buried in a layer list. */
  probeOn: boolean;
  onProbe: (on: boolean) => void;
  /**
   * Phase 3 and Phase 4, read straight from their own artifacts.
   *
   * Stages 06 and 07 used to say the landing sites were hardcoded offsets and
   * that no traverse was planned — printed beside five searched sites and five
   * drawn routes, because that prose was written before those phases ran and
   * nothing forced it to keep up. Both stages now report from the artifact when
   * it exists, and fall back to the absence notice only when it does not.
   */
  searchedSites: SearchedSites | null;
  traverse: Traverse | null;
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

/** The card shown when no analysis asset exists at all. */
function NoAnalysis({ craterId }: { craterId: string }) {
  return (
    <div className="mc-card mc-card--pending mc-fadein">
      <div className="mc-eyebrow">Stage data</div>
      <div className="mc-mod-title">Analysis Not Precomputed</div>
      <div className="mc-nores">
        No measured analysis has been generated for this target, so these stages
        have nothing to render. They are deliberately left blank rather than
        filled from the on-demand backend, which resamples to 100 × 100 and
        averages across the never-observed void.
        <div className="mc-nores-cmd">python backend/scripts/build_analysis.py {craterId}</div>
      </div>
    </div>
  );
}

/** A sweep table. Every area cell is a pixel count; every volume cell is derived. */
function SweepTable({ axis, unitLabel }: { axis: SweepAxis; unitLabel: string }) {
  const anyNonZero = axis.rows.some((r) => (r.candidate_px ?? 0) > 0);
  return (
    <>
      <table className="mc-table" style={{ marginTop: '0.5rem' }}>
        <thead>
          <tr>
            <th>{unitLabel}</th>
            <th>Pixels</th>
            <th>Area km²</th>
            <th>Volume m³</th>
          </tr>
        </thead>
        <tbody>
          {axis.rows.map((r, i) => (
            <tr key={i} className={r.is_configured_value ? 'mc-tr--sel' : ''}>
              <td style={{ fontFamily: "'JetBrains Mono',monospace" }}>
                {r.threshold}
                {r.is_configured_value && <span style={{ color: 'var(--mc-accent)' }}> ●</span>}
              </td>
              <td>{r.candidate_px?.toLocaleString() ?? '—'}</td>
              <td>{r.candidate_area_km2.toFixed(2)}</td>
              <td>{r.volume_m3.toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mc-metric-sub" style={{ marginTop: '0.4rem' }}>
        ● marks the configured operating point. Held constant:{' '}
        {Object.entries(axis.held_constant).map(([k, v]) => `${k.replace(/_/g, ' ')} ${v}`).join(', ')}.
        Grid: {axis.grid_source}.
        {!anyNonZero && ' Every row is zero — that flat line is the measurement, not an empty table.'}
      </div>
    </>
  );
}

export function StepPanel(props: Props) {
  const { step, analysis, mission } = props;

  if (!analysis) return <NoAnalysis craterId={props.craterId} />;

  const v = analysis.values;
  const th = analysis.thresholds;
  const status = stepStatus(analysis, step);

  // ── STEP 1 · Target Selection ─────────────────────────────────
  if (step === 1) {
    return (
      <div className="mc-card mc-fadein">
        <Head eyebrow="Stage 01 · Target" title="South Polar Crater Selection"
          desc="Only craters with a calibrated Chandrayaan-2 swath ingested and a precomputed analysis are selectable. The rest stay disabled rather than being served another crater's numbers." />
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '0.9rem' }}>
          {Object.values(props.craters).map((c) => {
            const active = c.is_active ?? true;
            const sel = props.craterId === c.id;
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
        <div className="mc-details">
          <div className="mc-kv-grid">
            <div><div className="mc-kv-k">Product</div><div className="mc-kv-v" style={{ fontSize: '0.6rem', wordBreak: 'break-all' }}>{analysis.product_id ?? 'NO DATA'}</div></div>
            <div><div className="mc-kv-k">Instrument</div><div className="mc-kv-v" style={{ fontSize: '0.68rem' }}>{analysis.instrument}</div></div>
            <div><div className="mc-kv-k">Observed</div><div className="mc-kv-v" style={{ fontSize: '0.68rem' }}>{analysis.observation_date?.slice(0, 10) ?? 'NO DATA'}</div></div>
            <div><div className="mc-kv-k">Grid</div><div className="mc-kv-v" style={{ fontSize: '0.68rem' }}>{analysis.grid.lines} × {analysis.grid.samples} @ {analysis.grid.metres_per_pixel} m/px</div></div>
          </div>
        </div>
      </div>
    );
  }

  // ── STEP 2 · Shadow & PSR ─────────────────────────────────────
  if (step === 2) {
    return (
      <div className="mc-card mc-fadein">
        <Head eyebrow="Stage 02 · Optical" title="Permanent Shadow & Cold Traps"
          desc="A permanently shadowed region needs a horizon computation: for each azimuth, the elevation angle of the highest terrain along that ray. This build has one — swept over 360 azimuths of the full LOLA polar array, with the Sun modelled as a finite disc." />
        <div className="mc-metrics" style={{ marginTop: '0.9rem' }}>
          <Figure k="PSR Area" v={v.psr_area_km2} />
          <Figure k="Doubly Shadowed" v={v.doubly_shadowed_area_km2} />
          <Figure k="Mean Illumination" v={v.mean_illumination_fraction} />
          <Figure k="Thermal Stability" v={v.thermal_stability_k} />
        </div>
        <div className="mc-note" style={{ marginTop: '0.8rem', borderLeftColor: 'var(--mc-warn)' }}>
          Note what is <em>not</em> claimed here. There is no temperature anywhere in this
          project — no Diviner product is on disk and no thermal model runs — so no
          statement about how cold these hollows stay can be made from this build.
          The shadow itself <em>is</em> computed, from measured LOLA topography rather
          than assumed: a horizon at every azimuth, validated against the LOLA team's own
          published PSR mask at a Jaccard of 0.714. Thermal stability below is inferred
          from that geometry alone, which is why it is marked DERIVED and not MEASURED.
        </div>
      </div>
    );
  }

  // ── STEP 3 · DFSAR Radar ──────────────────────────────────────
  if (step === 3) {
    return (
      <div className="mc-card mc-fadein">
        <Head eyebrow="Stage 03 · Radar" title="DFSAR Polarimetric Screening"
          desc="Circular polarisation ratio and degree of polarisation over the amplitude mask at native resolution. Statistics are taken over measured pixels only — never across the void." />
        <div className="mc-metrics" style={{ marginTop: '0.9rem' }}>
          <Figure k="Channel imbalance (CPR proxy), mean" v={v.cpr_mean}
            sub={`median ${showValue(v.cpr_p50)} · p99 ${showValue(v.cpr_p99)} · peak ${showValue(v.cpr_max)}`} />
          <Figure k="DOP mean" v={v.dop_mean}
            sub={`median ${showValue(v.dop_p50)} · p99 ${showValue(v.dop_p99)} · min ${showValue(v.dop_min)}`} />
          <Figure k="Measured swath" v={v.measured_area_km2} digits={0}
            sub={`of ${analysis.grid.frame_area_km2.toLocaleString()} km² frame · ISRO pointed ${showValue(v.pointed_area_km2, 0)} km²`} />
          <Figure k="Passing both criteria" v={v.screening_pass_fraction} percent
            sub={`of the measured swath — CPR > ${th.cpr_threshold}, DOP < ${th.dop_threshold}`} />
        </div>
        <div className="mc-details">
          <div className="mc-details-k">Each criterion separately, over the measured swath</div>
          <table className="mc-table" style={{ marginTop: '0.4rem' }}>
            <thead><tr><th>Criterion</th><th>Threshold</th><th>% of swath</th></tr></thead>
            <tbody>
              <tr>
                <td>CPR above threshold</td>
                <td style={{ fontFamily: "'JetBrains Mono',monospace" }}>&gt; {th.cpr_threshold}</td>
                <td>{showPercent(v.cpr_pass_fraction)} %</td>
              </tr>
              <tr>
                <td>DOP below threshold</td>
                <td style={{ fontFamily: "'JetBrains Mono',monospace" }}>&lt; {th.dop_threshold}</td>
                <td>{showPercent(v.dop_pass_fraction)} %</td>
              </tr>
            </tbody>
          </table>
          <div className="mc-metric-sub" style={{ marginTop: '0.4rem' }}>
            Thresholds read from {th.source}. {th.note}
          </div>
        </div>
      </div>
    );
  }

  // ── STEP 4 · Ice Criteria Screen ──────────────────────────────
  if (step === 4) {
    return (
      <div className="mc-card mc-fadein">
        <Head eyebrow="Stage 04 · Screen" title="Ice Criteria Screen"
          desc="The ice-screening criteria, each with its measured value beside the threshold it is tested against. This is a screen, not a probability — there is no classifier in this pipeline. They are a different set from the six landing-site criteria in stage 06." />
        <div className="mc-metrics" style={{ marginTop: '0.9rem' }}>
          <Figure k="Candidate Area" v={v.candidate_area_km2} digits={2}
            sub={`${showPercent(v.screening_pass_fraction)} % of the measured swath`} />
          {/* INFORMATIVE passes, matching the verdict card. Rendering
              criteria_passed here while the card renders
              criteria_informative_passed would put 1 and 0 for the same thing on
              one screen -- the divergence class the cross-path gate exists for,
              except within a single page. */}
          <Figure k="Criteria passed" v={v.criteria_informative_passed ?? v.criteria_passed}
            digits={0}
            suffix={` / ${analysis.verdict.criteria_evaluable} evaluable`}
            sub={(analysis.verdict.criteria_uninformative_passed
              ? `${analysis.verdict.criteria_uninformative_passed} more passes but is not evidence · `
              : '')
              + `${analysis.verdict.criteria_withheld} withheld of ${analysis.verdict.criteria_total} named`} />
        </div>
        <div className="mc-details">
          <div className="mc-details-k">Evidence checklist</div>
          <ul className="mc-why mc-why--ev">
            {analysis.evidence.map((e) => {
              const missing = e.measured === null || e.measured === undefined;
              const Ico = missing ? Minus : e.passed ? Check : X;
              const cls = missing ? 'mc-why-na' : e.passed ? 'mc-why-yes' : 'mc-why-no';
              return (
                <li key={e.criterion} className="mc-ev" title={e.note}>
                  <Ico size={14} className={`mc-why-ico ${cls}`} />
                  <div className="mc-ev-body">
                    <div className="mc-ev-head">
                      <span className={missing ? 'mc-ev-label mc-ev-label--na' : 'mc-ev-label'}>{e.label}</span>
                      <Pv p={e.provenance} />
                    </div>
                    <div className="mc-ev-meta">
                      <span className="mc-ev-mlabel">{e.measured_label}</span>
                      <span className={missing ? 'mc-ev-num mc-ev-num--na' : 'mc-ev-num'}>
                        {missing ? '—' : e.measured}
                      </span>
                      {e.threshold !== null && e.threshold !== 0 && e.comparison && (
                        <span className="mc-ev-th">vs {e.comparison} {e.threshold}</span>
                      )}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
        <div className="mc-note" style={{ marginTop: '0.8rem', borderLeftColor: 'var(--mc-warn)' }}>
          <strong style={{ color: 'var(--mc-accent)' }}>
            Screening {analysis.verdict.screening_status === 'PASS' ? 'PASSED' : 'NOT PASSED'}.
          </strong>{' '}
          {analysis.verdict.criteria_note}
        </div>

        {/* DON'T TAKE IT ON TRUST — CHECK IT.
            This panel asserts a verdict over a whole frame. The probe lets a
            reader point at any spot and read the same two criteria there, with
            the measured values and the margins. It is not a predictor and there
            is nothing to predict: the button says what it does. */}
        <button
          className={`mc-probe-cta ${props.probeOn ? 'mc-probe-cta--on' : ''}`}
          onClick={() => props.onProbe(!props.probeOn)}
        >
          <Crosshair size={13} />
          <span>
            <b>{props.probeOn ? 'Probe is on — click the map' : 'Check this anywhere on the map'}</b>
            Reads the measured CPR and DOP at any point, against these same
            thresholds and the detection floor. It does not locate ice.
          </span>
        </button>
        <div className="mc-details">
          <div className="mc-details-k">P(ice) — withdrawn</div>
          <div className="mc-na">
            <span className="mc-na-dash">—</span>
            <span>{v.p_ice_max?.reason}<Pv p="UNAVAILABLE" /></span>
          </div>
        </div>
      </div>
    );
  }

  // ── STEP 5 · Terrain Hazards ──────────────────────────────────
  if (step === 5) {
    const hm = analysis.hazard_model;
    const applied = Object.entries(hm.weights_applied).filter(([, w]) => w > 0);
    return (
      <div className="mc-card mc-fadein">
        <Head eyebrow="Stage 05 · Safety" title="Terrain Hazard Scoring"
          desc="Slope, roughness and a composite hazard, all computed from measured LOLA topography. The blend and its divisors are stated below rather than described in prose." />
        <div className="mc-metrics" style={{ marginTop: '0.9rem' }}>
          <Figure k="Slope mean" v={v.mean_slope_deg} digits={2}
            sub={`median ${showValue(v.slope_p50_deg, 2)}° · p99 ${showValue(v.slope_p99_deg, 2)}° · max ${showValue(v.max_slope_deg, 1)}°`} />
          <Figure k="Traversable" v={v.slope_fraction_below_20deg} percent digits={1}
            sub={`at or below ${hm.slope_risk_reference_deg}° (MAX_TRAVERSABLE_SLOPE_DEG) · `
                 + `${showPercent(v.slope_fraction_below_12deg, 1)} % at or below `
                 + `${th.critical_landing_slope_deg}° (CRITICAL_LANDING_SLOPE_DEG)`} />
          <Figure k="Roughness mean" v={v.mean_roughness_m} digits={2}
            sub={`median ${showValue(v.roughness_p50_m, 2)} m · p99 ${showValue(v.roughness_p99_m, 2)} m`} />
          <Figure k="Hazard mean" v={v.mean_hazard} digits={3}
            sub={`median ${showValue(v.hazard_p50, 3)} · p99 ${showValue(v.hazard_p99, 3)}`} />
        </div>
        <div className="mc-details">
          <div className="mc-details-k">The blend actually applied</div>
          <table className="mc-table" style={{ marginTop: '0.4rem' }}>
            <thead><tr><th>Term</th><th>Weight in config</th><th>Weight applied</th></tr></thead>
            <tbody>
              {Object.entries(hm.weights_in_config).map(([name, w]) => {
                const key = name.replace('WEIGHT_', '').toLowerCase();
                const app = hm.weights_applied[key] ?? 0;
                return (
                  <tr key={name}>
                    <td>{key}</td>
                    <td style={{ fontFamily: "'JetBrains Mono',monospace" }}>{w}</td>
                    <td style={{ fontFamily: "'JetBrains Mono',monospace", color: app > 0 ? undefined : 'var(--mc-warn)' }}>
                      {app > 0 ? app : 'NO DATA'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div className="mc-metric-sub" style={{ marginTop: '0.4rem' }}>
            {applied.map(([k]) => k).join(' + ')} ÷ {hm.denominator}
            {hm.renormalised && ' — renormalised, because the boulder term is absent rather than zero'}.
            Slope risk referenced to {hm.slope_risk_reference_deg}°, roughness to {hm.roughness_risk_reference_m} m.
          </div>
        </div>
        <div className="mc-note" style={{ marginTop: '0.8rem', borderLeftColor: 'var(--mc-warn)' }}>
          {hm.boulder.reason}
        </div>
      </div>
    );
  }

  // ── STEP 6 · Landing Sites ────────────────────────────────────
  if (step === 6) {
    const searched = props.searchedSites;
    return (
      <div className="mc-card mc-fadein">
        <Head eyebrow="Stage 06 · Landing" title="Landing Site Ranking"
          desc={searched
            ? 'The argmax of a search on six LANDING-SITE criteria — slope, roughness, '
              + 'hazard, amplitude mask, cold-trap distance and illumination — over every '
              + 'native 25 m pixel in the frame, with non-maximum suppression so the five '
              + 'are five places and not five pixels of one. These are not the six '
              + 'ice-screening criteria on the verdict card.'
            : 'A landing site should be the argmax of a search over the frame. These are not that yet.'} />

        {/* THE SEARCH RESULT, FROM THE SEARCH'S OWN FILE.
            Not restated from the analysis document, which does not hold it and
            says so — one answer, one source. Where the search has not been run
            on this host the absence notice below is what shows, unchanged. */}
        {searched ? (
          <>
            <div className="mc-metrics" style={{ marginTop: '0.9rem' }}>
              <div className="mc-metric">
                <div className="mc-metric-k">Pixels searched<Pv p="MEASURED" /></div>
                <div className="mc-metric-v">
                  {(searched.search.pixels_evaluated as number).toLocaleString()}
                </div>
                <div className="mc-metric-sub">
                  every native {String(searched.search.metres_per_pixel)} m cell, vectorised
                </div>
              </div>
              <div className="mc-metric">
                <div className="mc-metric-k">Separation<Pv p="MEASURED" /></div>
                <div className="mc-metric-v">{String(searched.search.nms_separation_km)} km</div>
                <div className="mc-metric-sub">
                  non-maximum suppression, {String(searched.search.nms_separation_px)} px
                </div>
              </div>
            </div>

            <div className="mc-details">
              <div className="mc-details-k">The five sites<Pv p="MEASURED" /></div>
              <table className="mc-table">
                <thead><tr><th>#</th><th>Lat</th><th>Lon</th><th>Score</th><th>PSR</th><th>Terrain</th></tr></thead>
                <tbody>
                  {searched.sites.map((st) => {
                    const suspect = /SUSPECT/i.test(st.interpolation_check.verdict);
                    return (
                      <tr key={st.rank}>
                        <td style={{ fontFamily: "'JetBrains Mono',monospace" }}>{st.rank}</td>
                        <td>{st.lat_deg.toFixed(3)}°</td>
                        <td>{st.lon_deg.toFixed(3)}°</td>
                        <td>{st.suitability_score.toFixed(4)}</td>
                        <td>{st.ice_access.psr_distance_km.toFixed(2)} km</td>
                        <td style={{ color: suspect ? 'var(--mc-warn)' : 'var(--mc-text-mute)' }}>
                          {suspect ? 'SUSPECT' : 'OK'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {/* The distance is to a MODELLED cold trap. Said here as well as on
                  the map, because a column headed "PSR" beside a landing site
                  reads as a distance to ice if nothing says otherwise. */}
              <div className="mc-metric-sub" style={{ marginTop: '0.45rem' }}>
                PSR is the distance to the nearest <b>modelled</b> cold trap — where ice
                could persist under the horizon computation, not where ice is. Terrain is
                the interpolation guard: whether the ground is genuinely smooth or is
                where the LOLA data ran out.
              </div>
            </div>

            {/* Why the ranking is what it is, from the file's own note rather
                than from a second opinion written here. */}
            <div className="mc-note" style={{ marginTop: '0.7rem' }}>
              Ranked by {searched.ranking_note.determined_by.join(' and ')}.{' '}
              {searched.ranking_note.safety_is_inert_here ? searched.ranking_note.why : ''}
            </div>
          </>
        ) : (
          <>
            <StepUnavailable title="Landing site selection" basis={status?.basis ?? ''} />
            <div className="mc-metrics" style={{ marginTop: '0.9rem' }}>
              <Figure k="Recommended site" v={v.landing_site} />
              <Figure k="Sites evaluated" v={v.landing_sites_evaluated} />
            </div>
          </>
        )}
        {mission && mission.landing_sites.length > 0 && (
          <div className="mc-details">
            <div className="mc-details-k">
              What the on-demand backend still returns
              <Pv p="UNAVAILABLE" />
            </div>
            <div className="mc-metric-sub" style={{ marginBottom: '0.4rem' }}>
              Shown so the map markers can be identified, not as a result. These
              five positions are hardcoded grid offsets scored after the fact; the
              recommendation is the best of five asserted points, not of a search.
            </div>
            <table className="mc-table">
              <thead><tr><th>#</th><th>Site</th><th>Slope</th><th>Hazard</th><th>Dist</th><th>Score</th></tr></thead>
              <tbody>
                {mission.landing_sites.map((s) => {
                  const sel = props.selectedLandingSite?.site_id === s.site_id;
                  return (
                    <tr key={s.site_id} className={sel ? 'mc-tr--sel' : ''} onClick={() => props.onSelectLandingSite(s)}>
                      <td style={{ fontFamily: "'JetBrains Mono',monospace" }}>{s.is_recommended ? '★' : ''}{s.rank}</td>
                      <td>{s.name}</td>
                      <td>{s.slope_deg}°</td>
                      <td>{s.hazard_score}</td>
                      <td>{s.distance_to_target_km} km</td>
                      <td style={{ color: 'var(--mc-text-mute)' }}>{s.composite_landing_score}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {props.selectedLandingSite && (
              <div className="mc-note" style={{ marginTop: '0.6rem' }}>
                <strong style={{ color: 'var(--mc-accent)' }}>{props.selectedLandingSite.name}:</strong>{' '}
                {props.selectedLandingSite.selection_rationale.join(' · ')}
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  // ── STEP 7 · Rover Traverse ───────────────────────────────────
  if (step === 7) {
    const routes = mission?.rover_routes ?? {};
    const trv = props.traverse;
    const conn = trv ? trv.connectivity[String(trv.planning.resolution_m)] : undefined;
    const reach = trv
      ? trv.primary_site_to_cold_trap.filter((r) => r.status === 'REACHABLE')
      : [];
    return (
      <div className="mc-card mc-fadein">
        <Head eyebrow="Stage 07 · Rover" title="Multi-Strategy Traverse"
          desc={trv
            ? trv.planning.algorithm + ' at a stated ' + trv.planning.resolution_m
              + ' m planning resolution. Connectivity is established before any distance is quoted.'
            : 'A traverse needs a target worth reaching and a cost surface at a stated planning resolution. Neither is wired to the measured producer yet.'} />

        {trv ? (
          <>
            {/* CONNECTIVITY FIRST, the same order plan_traverse.py reports in:
                "how far" is meaningless until "can it get there at all" has an
                answer, and an UNREACHABLE that is really reporting the cell size
                would be the hazard-saturation defect one level up. */}
            {conn && (
              <div className="mc-metrics" style={{ marginTop: '0.9rem' }}>
                <div className="mc-metric">
                  <div className="mc-metric-k">Sites connected<Pv p="MEASURED" /></div>
                  <div className="mc-metric-v">{conn.sites_in_largest}/{conn.n_sites}</div>
                  <div className="mc-metric-sub">
                    in one component holding{' '}
                    {(conn.largest_component_fraction_of_passable * 100).toFixed(1)}% of all
                    passable cells — the graph does not fragment
                  </div>
                </div>
                <div className="mc-metric">
                  <div className="mc-metric-k">Passable<Pv p="MEASURED" /></div>
                  <div className="mc-metric-v">{(conn.passable_fraction * 100).toFixed(1)}<small> %</small></div>
                  <div className="mc-metric-sub">
                    of {conn.cells.toLocaleString()} planning cells; a cell containing any
                    impassable 25 m face is impassable
                  </div>
                </div>
              </div>
            )}

            <div className="mc-details">
              <div className="mc-details-k">Site to modelled cold trap<Pv p="MEASURED" /></div>
              <table className="mc-table">
                <thead><tr><th>#</th><th>Length</th><th>Climb</th><th>Energy</th><th>Points</th></tr></thead>
                <tbody>
                  {trv.primary_site_to_cold_trap.map((r) => (
                    <tr key={r.rank}>
                      <td style={{ fontFamily: "'JetBrains Mono',monospace" }}>{r.rank}</td>
                      {r.status === 'REACHABLE' ? (
                        <>
                          <td>{(r.length_m! / 1000).toFixed(2)} km</td>
                          <td>{r.climb_m} m</td>
                          <td>{r.energy_J_per_kg?.toLocaleString()} J/kg</td>
                          <td style={{ color: 'var(--mc-text-mute)' }}>{r.cells}</td>
                        </>
                      ) : (
                        /* An explicit state, never a distance of 0 — a zero here
                           would read as "no travel needed". */
                        <td colSpan={4} style={{ color: 'var(--mc-warn)' }}>UNREACHABLE — {r.why}</td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="mc-metric-sub" style={{ marginTop: '0.45rem' }}>
                Every length is a multiple of {trv.planning.resolution_m} m, or{' '}
                {(trv.planning.resolution_m * Math.SQRT2).toFixed(1)} m diagonally:{' '}
                ±{trv.planning.resolution_m / 2} m. Energy is{' '}
                <b>{trv.energy_proxy.provenance}</b> and per kilogram, so no rover mass is
                invented; µ<sub>roll</sub> = {trv.energy_proxy.mu_roll} is an assumed rolling
                resistance, not a measurement.
              </div>
            </div>

            {reach.length > 0 && (
              <div className="mc-note" style={{ marginTop: '0.7rem', borderLeftColor: 'var(--mc-warn)' }}>
                {reach[0].target}
              </div>
            )}
          </>
        ) : (
          <>
            <StepUnavailable title="Traverse planning" basis={status?.basis ?? ''} />
            <div className="mc-metrics" style={{ marginTop: '0.9rem' }}>
              <Figure k="Traverse distance" v={v.rover_traverse_km} digits={2} />
              <Figure k="Traverse energy" v={v.rover_energy_wh} digits={0} />
            </div>
          </>
        )}
        {Object.keys(routes).length > 0 && (
          <div className="mc-details">
            <div className="mc-details-k">
              What the on-demand backend still returns
              <Pv p="UNAVAILABLE" />
            </div>
            <div className="mc-metric-sub" style={{ marginBottom: '0.4rem' }}>
              Shown so the drawn polylines can be identified. Every strategy runs
              from a hardcoded site to the grid centre, so these are three routes
              between two asserted points, not a planned traverse.
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {['Shortest', 'Safest', 'Science-Aware'].map((k) => {
                const r = routes[k];
                if (!r) return null;
                return (
                  <div key={k} className="mc-metric">
                    <div className="mc-row">
                      <span style={{ color: 'var(--mc-text)', fontWeight: 600, fontSize: '0.8rem' }}>{k}</span>
                      <span className="mc-metric-sub">
                        {r.algorithm_used} · {r.path_found ? `${r.total_distance_km} km` : 'UNREACHABLE'}
                      </span>
                    </div>
                    <div className="mc-metric-sub" style={{ marginTop: '0.35rem' }}>
                      {r.path_found
                        ? `${r.estimated_travel_time_hours} h · ${r.total_energy_wh} Wh · hazard ${r.mean_hazard_encountered} · peak slope ${r.max_slope_encountered_deg}°`
                        : r.failure_reason}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    );
  }

  // ── STEP 8 · Volume Estimate ──────────────────────────────────
  if (step === 8) {
    return (
      <div className="mc-card mc-fadein">
        <Head eyebrow="Stage 08 · Volume" title="Ice-Equivalent Volume"
          desc="Volume = candidate area × assumed depth × assumed pore fraction. The area is measured; both multipliers are assumptions and are printed with every tier." />
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '0.9rem' }}>
          {analysis.volume_tiers.map((t) => (
            <div key={t.tier} className="mc-metric" style={{ borderColor: t.tier === 'expected' ? 'var(--mc-line-strong)' : undefined }}>
              <div className="mc-row">
                <span style={{ color: t.tier === 'expected' ? 'var(--mc-accent)' : 'var(--mc-text)', fontWeight: 600, fontSize: '0.78rem', textTransform: 'capitalize' }}>
                  {t.tier}
                  <Pv p={t.provenance} />
                </span>
                <span className="mc-metric-sub">
                  depth {t.assumed_depth_m} m · pore {(t.assumed_pore_fraction * 100).toFixed(0)} %
                </span>
              </div>
              <div className="mc-metric-v" style={{ fontSize: '1rem', marginTop: '0.25rem' }}>
                {t.volume_m3.toLocaleString()}<small> m³</small>
              </div>
              <div className="mc-metric-sub">
                {t.volume_m3_per_km2.toLocaleString()} m³ per km² of candidate area
              </div>
            </div>
          ))}
        </div>
        <div className="mc-note" style={{ marginTop: '0.8rem', borderLeftColor: 'var(--mc-warn)' }}>
          The candidate area is {showValue(v.candidate_area_km2, 2)} km², a measured zero, so all
          three tiers are zero. The per-km² rate is shown beside each so the
          assumptions remain legible — those rates are what the tiers would give
          against any area, and none of them is a measurement.
        </div>
      </div>
    );
  }

  // ── STEP 9 · Sensitivity Studio ───────────────────────────────
  if (step === 9) {
    const sliders = [
      // The THRESHOLD is genuinely a CPR threshold -- it is the published
      // criterion this build is screening against, from Sinha et al. It keeps
      // the name. What the build measures against it is not CPR, and that is
      // said where the measurement is shown, not here.
      { label: 'CPR Threshold (published criterion)', val: props.cprTh, min: 0.6, max: 1.6, step: 0.05, key: 'cprThreshold', fmt: (n: number) => n.toFixed(2) },
      { label: 'DOP Threshold', val: props.dopTh, min: 0.06, max: 0.20, step: 0.01, key: 'dopThreshold', fmt: (n: number) => n.toFixed(2) },
      { label: 'Assumed Depth (m)', val: props.iceDepth, min: 1, max: 12, step: 0.5, key: 'iceDepthM', fmt: (n: number) => `${n}` },
      { label: 'Ice Fraction', val: props.iceFrac, min: 0.03, max: 0.35, step: 0.01, key: 'iceFraction', fmt: (n: number) => `${(n * 100).toFixed(0)}%` },
    ];
    const sens = analysis.sensitivity;
    // The sliders address an INDEX, because neither axis is evenly spaced: the
    // CPR axis is geometric, the whole structure living below 0.0043. The
    // threshold VALUE stays the state that is held, so nothing else in the app
    // has to learn about grid indices.
    const grid = props.sweepGrid;
    const ci = grid ? nearestIndex(grid.cpr_axis.values, props.cprTh) : 0;
    const dj = grid ? nearestIndex(grid.dop_axis.values, props.dopTh) : 0;
    return (
      <div className="mc-card mc-fadein">
        <Head eyebrow="Stage 09 · Sweep" title="Sensitivity Studio"
          desc="Each row below re-thresholds the native arrays and counts pixels. The area column is a measurement at every row, not a baseline scaled by a formula." />

        {/* THE HOST-STATE BLOCK WAS HERE AND HAS MOVED AGAIN, TO STAGE 12.
            It was put on this stage because this was the only screen a
            no-raster host cost anything: the four sliders below re-queried the
            pipeline. emit_sweep_grid.py then precomputed the joint screen, the
            sliders became a read of a static artifact, and this stage stopped
            depending on a host at all.

            Leaving a host-state badge on a stage with no host dependency would
            be the same defect it was moved here to fix, one commit later and in
            the opposite direction. The only consumer left is the PDF, so the
            block now sits in stage 12 beside the control it describes. */}
        <div className="mc-details">
          <div className="mc-details-k">
            CPR threshold sweep
            <Pv p={sens.cpr_threshold.rows.length ? 'MEASURED' : 'UNAVAILABLE'} />
          </div>
          <SweepTable axis={sens.cpr_threshold} unitLabel="CPR >" />
        </div>

        <div className="mc-details">
          <div className="mc-details-k">
            DOP threshold sweep
            <Pv p="MEASURED" />
          </div>
          <SweepTable axis={sens.dop_threshold} unitLabel="DOP <" />
        </div>

        <div className="mc-note" style={{ marginTop: '0.8rem' }}>{sens.note}</div>

        <div className="mc-details">
          <div className="mc-details-k">Columns deliberately absent</div>
          <ul className="mc-why" style={{ marginTop: 0 }}>
            {Object.entries(sens.withheld_columns).map(([k, why]) => (
              <li key={k}>
                <Minus size={14} className="mc-why-ico mc-why-na" />
                <span style={{ color: 'var(--mc-text-mute)' }}>
                  <strong>{k.replace(/_/g, ' ')}</strong> — {why}
                </span>
              </li>
            ))}
          </ul>
        </div>

        {/* ── THE INTERACTIVE SCREEN, READ FROM A STATIC ARTIFACT ──────────
            These sliders used to re-query /api/mission/{crater}, which re-runs
            the pipeline and needs the 9 GB of rasters. No deployed host has
            them, so on the live site they did nothing — beside two tables that
            worked, on the same stage. They now index into a grid measured
            offline at every threshold pair, so this stage needs no host.

            THE CPR AXIS DELIBERATELY RUNS FAR BELOW THE PUBLISHED CRITERION.
            A slider spanning CPR ∈ [0.6, 1.6] would read 0.00 km² at every
            position, because nothing in this swath comes within a factor of 235
            of the published threshold. A control whose output never moves is a
            vacuous criterion behind a control surface — it looks like a broken
            widget, and it is what the NON-DISCRIMINATING gate exists to catch.
            The axis is built from the measured field instead, and the published
            value is carried ON it and marked, so the degenerate point is
            visible rather than cropped away. */}
        {grid ? (() => {
          const r = readSweep(grid, ci, dj, props.iceDepth, props.iceFrac);
          const axisSliders = [
            { label: 'CPR threshold', idx: ci, n: grid.cpr_axis.values.length,
              onIdx: (i: number) => props.onUpdateParams({ cprThreshold: grid.cpr_axis.values[i] }),
              shown: r.cprThreshold < 0.01 ? r.cprThreshold.toExponential(3) : r.cprThreshold.toFixed(3) },
            { label: 'DOP threshold', idx: dj, n: grid.dop_axis.values.length,
              onIdx: (j: number) => props.onUpdateParams({ dopThreshold: grid.dop_axis.values[j] }),
              shown: r.dopThreshold.toFixed(4) },
          ];
          return (
            <div className="mc-details">
              <div className="mc-details-k">
                The screen, at any threshold pair
                <Pv p="MEASURED" />
              </div>
              <div className="mc-metric-sub" style={{ marginBottom: '0.6rem' }}>
                Precomputed over the native arrays — {grid.counts.length}×
                {grid.dop_axis.values.length} threshold pairs, each an exact pixel
                count. No host is queried.
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.7rem' }}>
                {axisSliders.map((s) => (
                  <div key={s.label}>
                    <div className="mc-slider-row">
                      <span>{s.label}</span>
                      <span style={{ color: 'var(--mc-accent)', fontFamily: "'JetBrains Mono',monospace" }}>
                        {s.shown}
                      </span>
                    </div>
                    <input className="mc-slider" type="range" min={0} max={s.n - 1} step={1}
                      value={s.idx} onChange={(e) => s.onIdx(parseInt(e.target.value, 10))} />
                  </div>
                ))}
                {sliders.slice(2).map((s) => (
                  <div key={s.key}>
                    <div className="mc-slider-row">
                      <span>{s.label}</span>
                      <span style={{ color: 'var(--mc-accent)', fontFamily: "'JetBrains Mono',monospace" }}>{s.fmt(s.val)}</span>
                    </div>
                    <input className="mc-slider" type="range" min={s.min} max={s.max} step={s.step} value={s.val}
                      onChange={(e) => props.onUpdateParams({ [s.key]: parseFloat(e.target.value) })} />
                  </div>
                ))}
              </div>

              <div className="mc-metrics" style={{ marginTop: '0.9rem' }}>
                <Figure k="Candidate pixels" digits={0}
                  v={{ value: r.candidatePx, unit: 'px', provenance: 'MEASURED' }}
                  sub="an exact count over the native arrays at this threshold pair" />
                <Figure k="Candidate area" digits={4}
                  v={{ value: r.areaKm2, unit: 'km²', provenance: 'MEASURED' }}
                  sub="that count × the frame's own cell area" />
                <Figure k="Ice volume" digits={0}
                  v={{ value: r.volumeM3, unit: 'm³', provenance: 'DERIVED' }}
                  sub="area × assumed depth × assumed pore fraction — both untested assumptions" />
              </div>
              {r.isPublishedPoint && (
                <div className="mc-note" style={{ marginTop: '0.6rem' }}>
                  This is the published operating point — CPR &gt; {grid.published_operating_point.cpr_threshold},
                  DOP &lt; {grid.published_operating_point.dop_threshold}. The area here is
                  the headline verdict, and it is a measured zero.
                </div>
              )}
              <div className="mc-note" style={{ marginTop: '0.6rem' }}>
                <strong>Where the answer changes.</strong> {grid.crossing.statement}
              </div>
              <div className="mc-metric-sub" style={{ marginTop: '0.5rem' }}>
                CPR axis — {grid.cpr_axis.grid_source}
              </div>
            </div>
          );
        })() : (
          <div className="mc-details">
            <div className="mc-details-k">The screen, at any threshold pair</div>
            <div className="mc-na">
              <span className="mc-na-dash">—</span>
              <span>
                analysis/sweep_grid.json is not present, so the interactive grid is
                withheld rather than indexed into. The two tables above are
                unaffected — they are a different artifact.
                <Pv p="UNAVAILABLE" />
              </span>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ── STEP 10 · Ablation ────────────────────────────────────────
  if (step === 10) {
    return (
      <div className="mc-card mc-fadein">
        <Head eyebrow="Stage 10 · Research" title="Planner Ablation"
          desc="A real ablation reruns the planner with each hazard weight zeroed in turn and reports the measured deltas in distance, mean hazard and peak slope." />
        <StepUnavailable title="Ablation" basis={status?.basis ?? ''} />
        <div className="mc-metrics" style={{ marginTop: '0.9rem' }}>
          <Figure k="Ablation runs" v={v.ablation_runs} />
        </div>
        <div className="mc-note" style={{ marginTop: '0.8rem', borderLeftColor: 'var(--mc-warn)' }}>
          Boulder risk will remain absent from that table when it arrives:{' '}
          {analysis.hazard_model.boulder.reason}
        </div>
      </div>
    );
  }

  // ── STEP 11 · Viva Rationale ──────────────────────────────────
  if (step === 11) {
    const passed = analysis.evidence.filter((e) => e.passed);
    const failed = analysis.evidence.filter((e) => !e.passed && e.provenance !== 'UNAVAILABLE');
    const withheld = analysis.evidence.filter((e) => e.provenance === 'UNAVAILABLE');
    return (
      <div className="mc-card mc-fadein">
        <Head eyebrow="Stage 11 · Defense" title="Defensible Rationale"
          desc="Every line below is read from this run's own analysis file. Nothing here is written into the component." />
        <div className="mc-details">
          <div className="mc-details-k">Satisfied</div>
          <ul className="mc-why" style={{ marginTop: 0 }}>
            {passed.length ? passed.map((e) => (
              <li key={e.criterion} title={e.note}>
                <Check size={14} className="mc-why-ico mc-why-yes" />
                <span>{e.label} — {e.measured_label} {e.measured} {e.comparison} {e.threshold}</span>
              </li>
            )) : (
              <li><X size={14} className="mc-why-ico mc-why-no" /><span style={{ color: 'var(--mc-text-mute)' }}>None satisfied this run</span></li>
            )}
          </ul>
        </div>
        {failed.length > 0 && (
          <div className="mc-details">
            <div className="mc-details-k">Tested and not satisfied</div>
            <ul className="mc-why" style={{ marginTop: 0 }}>
              {failed.map((e) => (
                <li key={e.criterion} title={e.note}>
                  <X size={14} className="mc-why-ico mc-why-no" />
                  <span>{e.label} — {e.measured_label} {e.measured} against {e.comparison} {e.threshold}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {withheld.length > 0 && (
          <div className="mc-details">
            <div className="mc-details-k">Withheld — not tested, and not evidence against ice</div>
            <ul className="mc-why" style={{ marginTop: 0 }}>
              {withheld.map((e) => (
                <li key={e.criterion} title={e.note}>
                  <Minus size={14} className="mc-why-ico mc-why-na" />
                  <span style={{ color: 'var(--mc-text-mute)' }}>{e.label} — {e.measured_label}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        <div className="mc-note" style={{ marginTop: '0.8rem', borderLeftColor: 'var(--mc-warn)' }}>
          {analysis.verdict.null_result_caveat}
        </div>
      </div>
    );
  }

  // ── STEP 12 · Mission Report ──────────────────────────────────
  if (step === 12) {
    return (
      <div className="mc-card mc-fadein">
        <Head eyebrow="Stage 12 · Report" title="Mission Decision Report"
          desc="Every figure in the PDF is either computed from the product named below or printed as NO DATA." />
        <div className="mc-details">
          <div className="mc-kv-grid">
            <div><div className="mc-kv-k">Crater</div><div className="mc-kv-v">{analysis.crater_name}</div></div>
            <div><div className="mc-kv-k">Verdict mode</div><div className="mc-kv-v">{analysis.data_mode}</div></div>
            <div><div className="mc-kv-k">Product</div><div className="mc-kv-v" style={{ fontSize: '0.62rem', wordBreak: 'break-all' }}>{analysis.product_id ?? 'NO DATA'}</div></div>
            <div><div className="mc-kv-k">Generated</div><div className="mc-kv-v" style={{ fontSize: '0.7rem' }}>{analysis.generated_utc.slice(0, 16).replace('T', ' ')} UTC</div></div>
          </div>
        </div>
        <div className="mc-details">
          <div className="mc-details-k">Source rasters</div>
          <ul className="mc-why" style={{ marginTop: 0 }}>
            {Object.entries(analysis.source_rasters).map(([k, path]) => (
              <li key={k}>
                <Check size={14} className="mc-why-ico mc-why-yes" />
                <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: '0.65rem' }}>{k}: {path}</span>
              </li>
            ))}
          </ul>
        </div>
        {/* THE HOST-STATE BADGE LIVES HERE, not in the global header, and not on
            stage 09 where it first moved. The PDF is now the ONLY thing on any
            screen that needs the on-demand host -- the sweep grid took the last
            other dependency away -- so the badge sits beside the control it
            describes. Nothing was deleted in either move. */}
        <div className={`mc-hoststate mc-hoststate--${props.backend}`}>
          <div className="mc-hoststate-badge">
            <span className="mc-badge-dot" />
            {props.backend === 'ok' && !props.backendReal
              ? 'LIVE · SIMULATED PAYLOAD'
              : BACKEND_COPY[props.backend].badge}
          </div>
          <div className="mc-hoststate-body">
            {props.backend === 'unreachable' &&
              `Nothing answered at ${API_ORIGIN}. `}
            {props.backend === 'not_ingested' &&
              'The backend answered and reports it holds no ingested rasters for '
              + 'this crater — it is reachable, and it has nothing to serve. '}
            {props.backend === 'pending' &&
              'Waiting for the analysis backend. '}
            {props.backend === 'ok' && props.backendReal &&
              'The backend answered and holds the ingested rasters for this '
              + 'crater. '}
            {props.backend === 'ok' && !props.backendReal &&
              'The backend answered, but reports its payload is generated rather '
              + 'than measured, so the sliders below re-run a simulation and not '
              + 'this product. '}
            {/* WRITTEN FOR THE STAGE IT IS ON. The first version of this text was
                written for stage 09 and moved here verbatim, where it went on
                saying "the two sweep tables below are static artifacts" — on a
                stage that has no sweep tables. The same drift, a fourth time,
                caused by the move that was fixing the third. A sentence about
                what is on the screen has to be checked against the screen, which
                is now a G15 assertion rather than a resolution to be careful. */}
            {props.backend === 'ok'
              ? 'The report below is rendered from them.'
              : <>This describes <strong>the mission endpoint</strong>, which
                  recomputes and needs the rasters. It does <strong>not</strong>
                  describe the report below: that is a rendering of the committed
                  analysis artifacts, needs no rasters, and is issued by this host.
                  Nothing on any screen is degraded — the verdict, the rasters, the
                  searched landing sites, the Phase 4 traverse, the criteria probe
                  and stage 09's precomputed sweep are all static artifacts, and
                  every number in them is the number a host with the rasters would
                  print.</>}
          </div>
        </div>

        {/* THIS WAS THE LAST `mission ? … : …` STANDING IN FOR THREE STATES.
            It printed "the backend, which is not reachable" on a screen whose
            own header said the backend had answered — the identical defect the
            badge and banner were fixed for, surviving one stage further down
            because nothing had looked at stage 12. It is now a function of the
            observed state, like every other sentence about the host. */}
        {/* THE REPORT'S OWN STATE, not the mission endpoint's. This read
            `props.backend === 'ok'` and so hid a working download behind the
            NOT_INGESTED state of a different endpoint. */}
        {props.reportState === 'available' ? (
          <a className="mc-btn mc-btn--solid" style={{ marginTop: '0.9rem', width: '100%', justifyContent: 'center' }}
            href={getReportPdfUrl(props.craterId)} target="_blank" rel="noopener noreferrer">
            <Download size={14} /> Download PDF Report
          </a>
        ) : (
          <div className="mc-na" style={{ marginTop: '0.9rem' }}>
            <span className="mc-na-dash">—</span>
            <span>
              {props.reportState === 'no_artifacts'
                ? 'The report endpoint answered and this host does not carry the '
                  + 'committed analysis artifacts the report renders, so it returns '
                  + '409 and no document is issued. A report rendered from a host '
                  + 'with less data would be a thinner document presented as the '
                  + 'same one.'
                : props.reportState === 'unreachable'
                  ? `Nothing answered at ${API_ORIGIN}, so no report can be requested.`
                  : 'Asking the report endpoint.'}
              {' '}The measured analysis above is unaffected — it is a static asset.
              <Pv p="UNAVAILABLE" />
            </span>
          </div>
        )}
      </div>
    );
  }

  return null;
}
