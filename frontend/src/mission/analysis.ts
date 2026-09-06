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
  /** False when the criterion is SATISFIED FOR A REASON UNRELATED TO THE
   *  QUESTION. Absent means informative, so an older analysis file keeps its
   *  current rendering rather than silently becoming "not evidence". */
  informative?: boolean;
  uninformative_reason?: string;
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

/** One tier of the volume estimate, carrying its assumptions AS DATA. */
export interface VolumeTier {
  tier: string;
  assumed_depth_m: number;
  assumed_pore_fraction: number;
  volume_m3: number;
  volume_m3_per_km2: number;
  provenance: Provenance;
  source: string;
  note: string;
}

/** One row of a real sweep: a pixel count re-thresholded off the native arrays. */
export interface SweepRow {
  threshold: number;
  is_configured_value: boolean;
  candidate_px?: number;
  candidate_area_km2: number;
  candidate_area_provenance: Provenance;
  volume_m3: number;
  volume_m3_per_km2?: number;
  volume_provenance: Provenance;
}

export interface SweepAxis {
  parameter: string;
  unit: string;
  baseline: number;
  grid_source: string;
  held_constant: Record<string, number>;
  rows: SweepRow[];
}

export interface Sensitivity {
  cpr_threshold: SweepAxis;
  dop_threshold: SweepAxis;
  assumed_depth_m: SweepAxis;
  ice_fraction: SweepAxis;
  provenance: Provenance;
  computed_by: string;
  withheld_columns: Record<string, string>;
  note: string;
}

/**
 * What each of the twelve steps can honestly show. The UI reads this to decide
 * whether a step renders figures or renders its own absence — it must never
 * infer that from whether a value happens to be null, because a null with no
 * stated reason is indistinguishable from a bug.
 */
export interface StepStatus {
  n: number;
  key: string;
  title: string;
  status: 'COMPLETE' | 'UNAVAILABLE';
  basis: string;
}

export interface HazardModel {
  components: string[];
  weights_applied: Record<string, number>;
  weights_in_config: Record<string, number>;
  denominator: number;
  renormalised: boolean;
  slope_risk_reference_deg: number;
  roughness_risk_reference_m: number;
  boulder: { provenance: Provenance; value: number | null; reason: string };
  provenance: Provenance;
  note: string;
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
    max_traversable_slope_deg: number;
    critical_landing_slope_deg: number;
    source: string;
    unchanged: boolean;
    note: string;
  };
  provenance_legend: Record<string, string>;
  verdict: {
    screening_status: 'PASS' | 'FAIL';
    criteria_passed: number;
    /** Passes that actually bear on the question. `criteria_passed` counts every
     *  pass including ones that carry no evidence; this is the one to display. */
    criteria_informative_passed?: number;
    criteria_uninformative_passed?: number;
    criteria_uninformative?: { label: string; reason: string }[];
    criteria_total: number;
    /** How many criteria could be evaluated at all. The rest are WITHHELD. */
    criteria_evaluable: number;
    criteria_withheld: number;
    criteria_note: string;
    label: string;
    sublabel: string;
    confidence: string;
    headline: AnalysisValue;
    null_result_caveat: string;
  };
  values: Record<string, AnalysisValue>;
  evidence: AnalysisEvidence[];
  volume_tiers: VolumeTier[];
  sensitivity: Sensitivity;
  steps: StepStatus[];
  hazard_model: HazardModel;
  elevation: Record<string, unknown>;
  illumination_model: Record<string, unknown>;
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

/**
 * The reason a value is absent, for rendering in the place the number would
 * have been. Never returns an empty string: a dash with no explanation is the
 * failure mode this whole module exists to prevent.
 */
export function absenceReason(v: AnalysisValue | undefined, fallback: string): string {
  return v?.reason ?? v?.note ?? fallback;
}

/** A step's declared status, or a conservative UNAVAILABLE when it is absent. */
export function stepStatus(a: Analysis | null, n: number): StepStatus | null {
  return a?.steps?.find((s) => s.n === n) ?? null;
}

/**
 * Format a fraction in [0,1] as a percentage string, or an em dash.
 * Small fractions keep enough digits to stay distinguishable from zero — the
 * screening pass fraction here is 0, but the CPR pass fraction is not, and
 * "0.0 %" for both would hide a real difference.
 */
export function showPercent(v: AnalysisValue | undefined, digits = 2): string {
  if (isMissing(v)) return '—';
  const pct = (v!.value as number) * 100;
  if (pct === 0) return '0';
  if (pct < 0.01) return pct.toExponential(1);
  return pct.toFixed(digits);
}


/**
 * A landing site SEARCHED over all 14,943,444 native 25 m pixels by
 * backend/scripts/search_landing_sites.py, not asserted on a coarse grid.
 *
 * Only the resulting sites reach the screen. Every intermediate raster,
 * percentile table and enrichment figure stays in docs/, and this file is
 * written by the same script that chose the sites, so the markers and the
 * evidence behind them cannot come from two different runs.
 */
export interface SearchedSite {
  rank: number;
  grid: { line: number; sample: number };
  lat_deg: number;
  lon_deg: number;
  suitability_score: number;
  /** Distance to the nearest MODELLED cold trap, not to detected ice. */
  ice_access: { psr_distance_km: number; threshold_km: number; passed: boolean;
                means: string };
  solar_power: { illumination_fraction: number; threshold: number; passed: boolean };
  criteria: Record<string, {
    value: number; threshold: number; comparison: string; passed: boolean;
  }>;
  /** Is this smooth ground, or ground where the LOLA data ran out? */
  interpolation_check: {
    plane_rms_m: number; frame_reference_p05_m: number;
    ratio_to_reference_p05: number; verdict: string;
  };
  score_decomposition: Record<string, {
    term_value: number; weight: number; contribution: number; share_of_score: number;
  }>;
  provenance: Record<string, string>;
}

export interface SearchedSites {
  generated_utc: string;
  generator: string;
  search: Record<string, unknown>;
  ranking_note: {
    determined_by: string[];
    safety_is_inert_here: boolean;
    why: string;
    not_a_flaw_in_the_weights: string;
    term_spans: Record<string, { weight: number; min: number; max: number; span: number }>;
  };
  sites: SearchedSite[];
}

/** Absent is a real state: no search has been run on this host. */
export async function loadSearchedSites(): Promise<SearchedSites | null> {
  try {
    const r = await fetch('/analysis/landing_sites.json', { cache: 'no-cache' });
    if (!r.ok) return null;
    return (await r.json()) as SearchedSites;
  } catch {
    return null;
  }
}
