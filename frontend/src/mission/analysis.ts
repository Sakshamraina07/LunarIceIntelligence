/**
 * analysis.ts — loader and types for the PRECOMPUTED analysis asset.
 *
 * Why this exists
 * ---------------
 * The headline verdict used to come from GET /api/mission/{crater}. On Render
 * that endpoint cannot see the SAR rasters (`/data/` and `*.tif` are gitignored,
 * and the paths in mission_service.py are Windows absolutes), so it silently
 * degrades to a seeded DEMO generator and returns invented values with HTTP 200:
 * P(ice) 0.96, screening PASSED, 5/5 evidence ticks, 17.58 M m³ of ice — beside a
 * map rendering the real measured radar swath.
 *
 * So the verdict is computed offline by `backend/scripts/build_analysis.py` from
 * the native 25 m/px rasters and committed to `public/analysis/<crater>.json`,
 * next to `layers.json`. This module reads that file. There is no fallback: if
 * the asset is absent for a crater, the UI renders em dashes and says so. A
 * simulated value must never occupy the slot a measured one would.
 *
 * Every value carries its own provenance mark, because this scene mixes
 * observations with models:
 *   MEASURED    — an observation, or a direct geometric consequence of one:
 *                 calibrated Chandrayaan-2 DFSAR, or LOLA topography.
 *   MODELLED    — a model output with no ground truth in this project to check
 *                 it against: the illumination proxy, and P(ice).
 *   DERIVED     — an assumption model on top of one of the above.
 *   UNAVAILABLE — cannot be computed honestly; render an em dash + the reason.
 */

export type Provenance = 'MEASURED' | 'MODELLED' | 'DERIVED' | 'UNAVAILABLE';

/** One headline number plus the mark the UI is required to render beside it. */
export interface AnalysisValue {
  /** `null` means the number does not exist. Do not substitute anything. */
  value: number | null;
  unit: string;
  provenance: Provenance;
  note?: string;
  /** Present when `value` is null: what to show where the number would have been. */
  reason?: string;
}

/** One screening criterion, carrying the measured figure beside the actual threshold. */
export interface AnalysisEvidence {
  criterion: string;
  label: string;
  measured: number | null;
  measured_label: string;
  threshold: number | null;
  comparison: string | null;
  passed: boolean;
  provenance: Provenance;
  note: string;
}

export interface AnalysisMask {
  source: string;
  pixels: number;
  fraction: number;
  area_km2: number;
  meaning: string;
}

export interface Analysis {
  schema: string;
  crater_id: string;
  crater_name: string;
  latitude_deg: number;
  longitude_deg: number;
  generated_utc: string;
  generator: string;
  data_mode: 'REAL';
  why_static: string;
  supersedes: string;
  product_id: string | null;
  instrument: string;
  observation_date: string | null;
  grid: {
    lines: number;
    samples: number;
    metres_per_pixel: number;
    cell_area_km2: number;
    frame_area_km2: number;
    note: string;
  };
  masks: {
    amplitude: AnalysisMask;
    footprint: AnalysisMask;
    returned_over_pointed: number;
  };
  source_rasters: Record<string, string>;
  thresholds: {
    cpr_threshold: number;
    dop_threshold: number;
    source: string;
    unchanged: boolean;
    note: string;
  };
  provenance_legend: Record<string, string>;
  verdict: {
    screening_status: 'PASS' | 'FAIL';
    criteria_passed: number;
    criteria_total: number;
    label: string;
    sublabel: string;
    confidence: string;
    headline: AnalysisValue;
    null_result_caveat: string;
  };
  values: Record<string, AnalysisValue>;
  evidence: AnalysisEvidence[];
  measured_statistics: Record<string, unknown>;
  notes: string[];
}

const SCHEMA = 'lunar-ice/analysis/1';

/** Short mark rendered next to every value. Blunt on purpose. */
export const PROV_MARK: Record<Provenance, string> = {
  MEASURED: 'MEASURED',
  MODELLED: 'MODELLED',
  DERIVED: 'DERIVED',
  UNAVAILABLE: 'NO DATA',
};

/**
 * Fetch the precomputed analysis for a crater.
 *
 * Returns `null` when no asset has been generated for that crater — the caller
 * must then render "not precomputed" rather than reaching for the backend,
 * which is the exact substitution this whole module exists to prevent.
 */
export async function loadAnalysis(craterId: string): Promise<Analysis | null> {
  const url = `${import.meta.env.BASE_URL}analysis/${craterId}.json`;
  let res: Response;
  try {
    res = await fetch(url, { cache: 'no-cache' });
  } catch {
    return null;
  }
  if (!res.ok) return null;

  let doc: Analysis;
  try {
    doc = (await res.json()) as Analysis;
  } catch {
    return null;
  }
  // A wrong schema is treated as absent. Half-understood provenance is worse
  // than none, because it would render marks that no longer mean what they say.
  if (doc?.schema !== SCHEMA) return null;
  return doc;
}

/** Format an AnalysisValue for display. `null` becomes an em dash, never a number. */
export function showValue(v: AnalysisValue | undefined, digits?: number): string {
  if (!v || v.value === null || v.value === undefined) return '—';
  const n = v.value;
  if (digits !== undefined) return n.toFixed(digits);
  if (n === 0) return '0';
  const abs = Math.abs(n);
  if (abs >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (abs >= 100) return n.toFixed(0);
  if (abs >= 1) return n.toFixed(2);
  if (abs >= 0.01) return n.toFixed(3);
  return n.toExponential(2);
}

/** True when the UI must degrade the cell instead of printing a figure. */
export function isMissing(v: AnalysisValue | undefined): boolean {
  return !v || v.value === null || v.value === undefined;
}
