/**
 * traverse.ts — loader and types for the Phase 4 traverse plan.
 *
 * The routes were computed offline by `backend/scripts/plan_traverse.py`:
 * Dijkstra over an 8-connected grid at a stated 100 m planning resolution,
 * connectivity reported BEFORE any distance, `UNREACHABLE` an explicit state
 * that is never rendered as a distance of zero.
 *
 * WHAT THE DESTINATION IS
 * -----------------------
 * Each route runs from a searched landing site to the nearest MODELLED cold
 * trap — where ice COULD persist under the horizon computation, not where ice
 * IS. Candidate ice area in this frame is 0.00 km² and no radar detection
 * supports any of these targets. Every route record carries that sentence in
 * its own `target` field and the UI renders it from there rather than from a
 * second copy, so the caption cannot drift away from the computation.
 *
 * THE GRID
 * --------
 * `polyline_grid` is `[line, sample]` on the 100 m PLANNING grid, not on the
 * 25 m raster the map draws. `planning.resolution_m / native_metres` is the
 * factor, read from the file rather than assumed — see `planningScale`.
 */

export interface TraverseRoute {
  rank: number;
  status: 'REACHABLE' | 'UNREACHABLE';
  /** null when UNREACHABLE. A zero here would read as "no travel needed". */
  length_m: number | null;
  climb_m?: number;
  energy_J_per_kg?: number;
  provenance_energy?: string;
  quantisation_m?: number;
  cells?: number;
  /** [line, sample] pairs on the PLANNING grid. */
  polyline_grid?: [number, number][];
  polyline_latlon?: [number, number][];
  target?: string;
  why?: string;
}

export interface Traverse {
  schema: string;
  generated_utc: string;
  generator: string;
  planning: {
    resolution_m: number;
    quantisation_note: string;
    impassable_rule: string;
    hazard_weight: number;
    algorithm: string;
  };
  connectivity: Record<string, {
    k: number; eff_m: number; cells: number; passable_fraction: number;
    components: number; largest_component_cells: number;
    largest_component_fraction_of_passable: number;
    sites_in_largest: number; n_sites: number;
  }>;
  energy_proxy: {
    provenance: string; formula: string;
    g_moon_m_s2: number; mu_roll: number; note: string;
  };
  primary_site_to_cold_trap: TraverseRoute[];
  capability_pairwise_matrix_m: (number | null)[][];
  capability_detour_ratios: Record<string, {
    straight_m: number; route_m: number | null; detour_ratio: number | null;
  }>;
  capability_tour: {
    method: string; order: number[]; total_length_m: number;
    is_a_mission_plan: boolean; note: string;
  };
  site_source: string;
}

const SCHEMA = 'traverse/1';

/**
 * Planning cells -> native raster pixels.
 *
 * Read from the file, not written as `4`. The planner can be re-run at 50 m
 * (`--resolution 50`) and the connectivity block already reports both; a
 * hardcoded 4 would then draw every route at a quarter scale, in the wrong
 * place, with no error anywhere.
 */
export function planningScale(t: Traverse, nativeMetres: number): number {
  return t.planning.resolution_m / nativeMetres;
}

/** Absent is a real state: no traverse has been planned on this host. */
export async function loadTraverse(): Promise<Traverse | null> {
  try {
    const r = await fetch(`${import.meta.env.BASE_URL}analysis/traverse.json`, { cache: 'no-cache' });
    if (!r.ok) return null;
    const doc = (await r.json()) as Traverse;
    if (doc?.schema !== SCHEMA) {
      console.error(`[traverse] schema is "${doc?.schema}", expected "${SCHEMA}"`);
      return null;
    }
    return doc;
  } catch {
    return null;
  }
}

/**
 * Cumulative along-route distance in metres at every vertex, from the planning
 * grid: `resolution_m` per orthogonal step, `resolution_m * sqrt(2)` per
 * diagonal. This is the same sum `plan_traverse.py` reports as `length_m`, so
 * the last element must equal that field — asserted by the caller rather than
 * assumed, because two ways of measuring one route is how the traverse coverage
 * number came to disagree with itself earlier in this project.
 */
export function cumulativeMetres(r: TraverseRoute, resolutionM: number): number[] {
  const p = r.polyline_grid ?? [];
  const out = [0];
  for (let i = 1; i < p.length; i++) {
    const dl = p[i][0] - p[i - 1][0];
    const ds = p[i][1] - p[i - 1][1];
    out.push(out[i - 1] + resolutionM * Math.hypot(dl, ds));
  }
  return out;
}
