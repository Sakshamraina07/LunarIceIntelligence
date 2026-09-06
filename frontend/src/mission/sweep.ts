/**
 * sweep.ts — the precomputed joint screen, read as a static artifact.
 *
 * WHY THIS FILE EXISTS
 * --------------------
 * Stage 09's four sliders used to re-query `/api/mission/{crater}`, which
 * re-runs the pipeline and therefore needs the 9 GB of Chandrayaan-2 and LOLA
 * products. No deployed host has them, so on the live site the sliders did
 * nothing at all — while the two sweep TABLES beside them, already static,
 * rendered correctly. One stage, two data paths, and only one of them worked.
 *
 * `backend/scripts/emit_sweep_grid.py` measures the joint criterion at every
 * threshold pair offline and writes `analysis/sweep_grid.json`. The sliders now
 * index into that. Stage 09 needs no host, which is the same move the verdict,
 * the rasters, the searched sites, the Phase 4 traverse and the criteria probe
 * already made.
 *
 * WHAT IS AND IS NOT IN THE FILE
 * ------------------------------
 * `counts` is MEASURED — a pixel count per threshold pair. Area is that count
 * times the frame's own cell area, still MEASURED. Volume is deliberately NOT
 * in the artifact: it is area × assumed depth × assumed pore fraction, and both
 * assumptions are untested, so it is DERIVED and computed here, at the point of
 * display, beside its own mark. Putting it in the file would have let a DERIVED
 * number inherit the file's MEASURED provenance by proximity.
 */

export interface SweepAxis {
  values: number[];
  grid_source: string;
  provenance: string;
}

export interface SweepGrid {
  schema: string;
  crater_id: string;
  generated_utc: string;
  computed_by: string;
  cell_km2: number;
  valid_px: number;
  published_operating_point: {
    cpr_threshold: number; dop_threshold: number;
    cpr_index: number; dop_index: number;
    candidate_px: number; candidate_area_km2: number;
    provenance: string;
  };
  crossing: {
    cpr_value: number;
    provenance: string;
    definition: string;
    factor_below_published: number;
    algebraic_ceiling: number;
    relative_agreement: number;
    statement: string;
  };
  cpr_axis: SweepAxis;
  dop_axis: SweepAxis;
  counts: number[][];
  counts_note: string;
}

export async function loadSweepGrid(): Promise<SweepGrid | null> {
  try {
    const r = await fetch(`${import.meta.env.BASE_URL}analysis/sweep_grid.json`,
                          { cache: 'no-cache' });
    if (!r.ok) {
      console.info(`[sweep] analysis/sweep_grid.json -> HTTP ${r.status}. `
        + 'Stage 09 shows its precomputed tables and no interactive grid; '
        + 'nothing is invented in its place.');
      return null;
    }
    const g = (await r.json()) as SweepGrid;
    // A shape check, not a cast. The wire is allowed to disagree with the type
    // and the type is not evidence — that mistake blanked the production page
    // once already (METHODS §0, the sub-kind).
    if (!Array.isArray(g?.counts) || !Array.isArray(g?.cpr_axis?.values)
        || !Array.isArray(g?.dop_axis?.values)
        || g.counts.length !== g.cpr_axis.values.length) {
      console.error('[sweep] sweep_grid.json does not have the shape it declares; '
        + 'the interactive grid is withheld rather than indexed into blindly.');
      return null;
    }
    return g;
  } catch (e) {
    console.info(`[sweep] sweep_grid.json unavailable (${e instanceof Error ? e.message : e}).`);
    return null;
  }
}

/** Nearest axis index to a value. The axis is not evenly spaced — the CPR axis
 *  is geometric, because the whole structure lives below 0.0043 — so a slider
 *  addresses an INDEX and this maps a value onto one. */
export function nearestIndex(values: number[], v: number): number {
  let best = 0;
  let bestD = Infinity;
  for (let i = 0; i < values.length; i++) {
    const d = Math.abs(values[i] - v);
    if (d < bestD) { bestD = d; best = i; }
  }
  return best;
}

export interface SweepReadout {
  cprThreshold: number;
  dopThreshold: number;
  candidatePx: number;
  /** MEASURED: count × the frame's own cell area. */
  areaKm2: number;
  /** DERIVED: area × assumed depth × assumed pore fraction. Both untested. */
  volumeM3: number;
  isPublishedPoint: boolean;
}

export function readSweep(g: SweepGrid, i: number, j: number,
                          depthM: number, fraction: number): SweepReadout {
  const px = g.counts[i]?.[j] ?? 0;
  const areaKm2 = px * g.cell_km2;
  return {
    cprThreshold: g.cpr_axis.values[i],
    dopThreshold: g.dop_axis.values[j],
    candidatePx: px,
    areaKm2,
    volumeM3: areaKm2 * 1e6 * depthM * fraction,
    isPublishedPoint: i === g.published_operating_point.cpr_index
                   && j === g.published_operating_point.dop_index,
  };
}
