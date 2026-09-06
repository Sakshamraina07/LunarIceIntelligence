/**
 * ProbeReadout.tsx — what the criteria say at one point on the map.
 *
 * THE THING THIS IS NOT
 * ---------------------
 * It was asked for as a way to "predict where ice spots exactly are". There are
 * none to show and none to predict: candidate area in this frame is 0.0000 km²
 * and METHODS §1 proves the screen is empty BY CONSTRUCTION — under `DOP < 0.13`
 * the amplitude-derived CPR cannot exceed ~0.00426, whatever the terrain. A
 * panel that answered "ice is here" would fabricate the single number this
 * project exists to not fabricate.
 *
 * So it answers the checkable question instead. Point anywhere and it reports
 * the MEASURED CPR and DOP, each against its own threshold, the margin in both
 * directions, the Phase 8 detection floor the reading would have to clear to be
 * significant at all, and — where the radar returned nothing — says so as an
 * absent state rather than showing a zero.
 *
 * That is a stronger instrument than the one requested. "There is no ice" is a
 * claim a reader has to take on trust; "point anywhere and see for yourself how
 * far short it falls" is one they can check.
 */
import { Crosshair, X } from 'lucide-react';
import type { ProbeGrid, ProbeSample } from './probe';

/** Ratio short of a threshold, worded so the direction cannot be misread. */
function shortfall(v: number, threshold: number): string {
  if (v <= 0) return 'immeasurably below';
  const f = threshold / v;
  if (f >= 1000) return `${f.toExponential(1)}× below`;
  if (f >= 10) return `${f.toFixed(0)}× below`;
  return `${f.toFixed(1)}× below`;
}

function Row({ k, v, sub, mark }:
             { k: string; v: string; sub: string; mark?: 'pass' | 'fail' | 'none' }) {
  return (
    <div className="mc-probe-row">
      <div className="mc-probe-k">{k}</div>
      <div className="mc-probe-v">
        {v}
        {mark === 'pass' && <span className="mc-probe-pass">✓</span>}
        {mark === 'fail' && <span className="mc-probe-fail">✗</span>}
      </div>
      <div className="mc-probe-sub">{sub}</div>
    </div>
  );
}

interface Props {
  grid: ProbeGrid | null;
  /** true once the fetch has settled — so "loading" and "absent" stay distinct. */
  settled: boolean;
  sample: ProbeSample | null;
  onClose: () => void;
}

export function ProbeReadout({ grid, settled, sample, onClose }: Props) {
  return (
    <div className="mc-map-overlay mc-map-panel mc-probe">
      <div className="mc-probe-head">
        <Crosshair size={12} className="mc-probe-ico" />
        <span>Criteria probe</span>
        <button className="mc-probe-x" onClick={onClose} title="Close the probe">
          <X size={12} />
        </button>
      </div>

      {/* Said once, at the top, before any number: this reads out a measurement,
          it does not locate ice. Putting it after the values would let a reader
          take the first figure they saw as a detection. */}
      <div className="mc-probe-not">
        Reads the <b>measured</b> field. It does not locate ice — there is none in
        this frame to locate, and §1 shows the screen is empty by construction.
      </div>

      {!settled && <div className="mc-probe-empty">Loading the measured field…</div>}

      {settled && !grid && (
        <div className="mc-probe-empty mc-probe-empty--absent">
          No probe grid on this host. Nothing is estimated in its place.
          <code>python backend/scripts/emit_probe_grid.py</code>
        </div>
      )}

      {settled && grid && !sample && (
        <div className="mc-probe-empty">
          Click anywhere on the map.
          <span className="mc-probe-hint">
            Every reading is a block mean over {grid.header.decimation}×
            {grid.header.decimation} native {grid.header.native_metres} m pixels —
            a {grid.header.cell_metres} m cell, outlined on the map where you click.
          </span>
        </div>
      )}

      {settled && grid && sample && (() => {
        const h = grid.header;
        const cov = sample.coverage;
        const cprPass = sample.cpr !== null && sample.cpr > h.thresholds.cpr;
        const dopPass = sample.dop !== null && sample.dop < h.thresholds.dop;
        return (
          <>
            <div className={`mc-probe-cov mc-probe-cov--${cov}`}>
              {cov === 'measured' && <>MEASURED RADAR · {(sample.amplitudeFraction * 100).toFixed(0)}% of this cell returned amplitude</>}
              {cov === 'pointed-no-return' && <>POINTED, NO RETURN · the beam covered {(sample.pointedFraction * 100).toFixed(0)}% of this cell and it returned integer zero</>}
              {cov === 'never-observed' && <>NEVER OBSERVED · this cell is outside the DFSAR beam entirely</>}
            </div>

            <div className="mc-probe-pos">
              {sample.latDeg !== null && sample.lonDeg !== null
                ? `${sample.latDeg.toFixed(4)}°, ${sample.lonDeg.toFixed(4)}°`
                : 'coordinates unavailable — layers.json carries no geodetic_frame'}
              <span> · line {sample.line.toFixed(0)}, sample {sample.sample.toFixed(0)}</span>
            </div>

            {/* THE TWO SCREENING CRITERIA — the whole point of the panel. */}
            {cov === 'measured' ? (
              <>
                <Row
                  k="CPR"
                  v={sample.cpr!.toExponential(3)}
                  mark={cprPass ? 'pass' : 'fail'}
                  sub={`needs > ${h.thresholds.cpr.toFixed(2)} — `
                    + `${shortfall(sample.cpr!, h.thresholds.cpr)} it`}
                />
                <Row
                  k="DOP"
                  v={sample.dop!.toFixed(4)}
                  mark={dopPass ? 'pass' : 'fail'}
                  sub={dopPass
                    ? `needs < ${h.thresholds.dop} — passes, with `
                      + `${(h.thresholds.dop - sample.dop!).toFixed(4)} to spare`
                    : `needs < ${h.thresholds.dop} — over by `
                      + `${(sample.dop! - h.thresholds.dop).toFixed(4)}`}
                />

                {/* Why the pass can never happen here, stated at this point with
                    this point's own numbers rather than as a general remark. */}
                <div className="mc-probe-why">
                  {dopPass ? (
                    <>DOP passes here, and that is exactly what caps CPR: the two are
                      functions of one variable, so <code>DOP &lt; {h.algebraic_ceiling.under_dop_below}</code> bounds
                      CPR at <b>{h.algebraic_ceiling.cpr_cap.toFixed(7)}</b>. This cell reads{' '}
                      {sample.cpr!.toExponential(2)} and <b>no value above that cap is
                      reachable</b>, whatever the terrain.</>
                  ) : (
                    <>DOP fails here, so this cell is excluded before CPR is consulted.
                      Had it passed, <code>DOP &lt; {h.algebraic_ceiling.under_dop_below}</code> would
                      have capped CPR at {h.algebraic_ceiling.cpr_cap.toFixed(7)} — the two
                      criteria are functions of one variable and cannot both be satisfied.</>
                  )}
                </div>

                <div className="mc-probe-floor">
                  <b>Detection floor {h.detection_floor.value}</b> at the measured
                  N&nbsp;=&nbsp;{h.detection_floor.looks}. A single pixel must read above
                  it to be significantly over a threshold of {h.thresholds.cpr.toFixed(2)} at{' '}
                  {(h.detection_floor.confidence * 100).toFixed(0)}% confidence. This cell is{' '}
                  <b>{shortfall(sample.cpr!, h.detection_floor.value)}</b> that floor.
                </div>
              </>
            ) : (
              <div className="mc-probe-nodata">
                <b>NO DATA</b> — no radar amplitude in this cell, so CPR and DOP do not
                exist here. They are not zero and they are not low; they are absent.
                {cov === 'pointed-no-return'
                  ? ' The beam was pointed here and 56.11% of ISRO’s own swath mask'
                    + ' carries literal integer zero — observed and empty, not dry.'
                  : ' This ground was never inside the beam on the 2020-08-08 pass.'}
              </div>
            )}

            {/* Everything that IS defined everywhere. Terrain and illumination are
                computed over the whole frame, so they have an answer even where
                the radar does not — and saying so is the point of separating them. */}
            <div className="mc-probe-terrain">
              <Row k="Elevation" v={`${sample.elevationM.toFixed(0)} m`}
                   sub="LOLA LDEM_80S_20M, carried onto the 25 m grid" />
              <Row k="Illumination" v={sample.illumination.toFixed(3)}
                   sub="lit fraction, horizon computation over 360 azimuths" />
              <Row k="Permanent shadow" v={`${(sample.psrFraction * 100).toFixed(0)}%`}
                   sub="of this cell, from the same horizon computation" />
            </div>

            <div className="mc-probe-cell-note">
              {h.decimation_note} Cell {sample.cell.gy}, {sample.cell.gx} of{' '}
              {h.shape[0]}×{h.shape[1]}.
            </div>
          </>
        );
      })()}
    </div>
  );
}
