/**
 * missionData.ts
 * Typed frontend service that bridges the landing experience to the existing
 * FastAPI backend WITHOUT performing any scientific computation in the browser.
 *
 * Architecture:
 *   Three.js / React UI  ->  this service layer  ->  FastAPI backend  ->  modules A-G
 *
 * This is the ONLY place a screening verdict enters the landing page.
 * `data/targets.ts` ships geography and nothing else, so a target renders as
 * NOT INGESTED until a REAL payload lands here and fills `label`, `evidence` and
 * `psrFraction` together. A backend that is offline, erroring, or answering
 * NOT_INGESTED leaves the target exactly as it was: unscreened.
 */

import { SOUTH_POLE_TARGETS, type EvidenceLevel, type LunarTarget } from '../data/targets';

const API_BASE_URL = `${(import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000').replace(/\/$/, '')}/api`;

export interface BackendHealth {
  online: boolean;
  mode?: string;
  version?: string;
}

export async function pingBackend(timeoutMs = 2500): Promise<BackendHealth> {
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), timeoutMs);
    const res = await fetch(`${API_BASE_URL}/health`, { signal: ctrl.signal });
    clearTimeout(t);
    if (!res.ok) return { online: false };
    const data = await res.json();
    // `requested_data_mode` is what the server was asked for, not what any
    // crater resolved to. Eligibility is per crater and decided below.
    return { online: true, mode: data.requested_data_mode, version: data.version };
  } catch {
    return { online: false };
  }
}

/** Map a backend ice result to the cautious evidence tier used by the UI. */
function evidenceFromScreening(status: string, likelihood: number): EvidenceLevel {
  if (status === 'PASS' && likelihood >= 0.5) return 'promising';
  if (status === 'PASS') return 'candidate';
  return 'watch';
}

/**
 * Fill in screening verdicts for targets the backend can actually vouch for.
 * Returns the target list plus whether any verdict came back. Never throws.
 *
 * THE GATE, in three parts, all of which must hold:
 *   1. `status === 'OK'` — the response is a mission, not the NOT_INGESTED
 *      absent state. That state carries no `psr`/`ice` keys at all, so an
 *      optional-chained read of it yields undefined rather than a zero.
 *   2. `data_mode === 'REAL'` — the pipeline ran on an ingested product.
 *   3. `psr_area_fraction` and the two ice fields are present. If any is
 *      missing the target stays unscreened; no field is defaulted, because a
 *      default here is a verdict nobody computed.
 */
export async function loadTargets(): Promise<{ targets: LunarTarget[]; live: boolean }> {
  const health = await pingBackend();
  if (!health.online) return { targets: SOUTH_POLE_TARGETS, live: false };

  const enriched = await Promise.all(
    SOUTH_POLE_TARGETS.map(async (t) => {
      if (!t.craterId) return t;
      try {
        const res = await fetch(`${API_BASE_URL}/mission/${t.craterId}`);
        if (!res.ok) return t;
        const mission = await res.json();
        if (mission?.status !== 'OK' || mission?.data_mode !== 'REAL') return t;

        const psrFraction = mission?.psr?.psr_area_fraction;
        const status = mission?.ice?.scientific_screening_status;
        const likelihood = mission?.ice?.ml_ice_likelihood_mean;
        if (
          typeof psrFraction !== 'number' ||
          typeof status !== 'string' ||
          typeof likelihood !== 'number'
        ) {
          return t;
        }

        const evidence = evidenceFromScreening(status, likelihood);
        const label =
          evidence === 'promising'
            ? 'Promising candidate'
            : evidence === 'candidate'
              ? 'Evidence consistent with potential ice'
              : 'Region under watch';
        return {
          ...t,
          psrFraction,
          evidence,
          label,
          productId: mission?.gate?.product_id ?? undefined,
        } satisfies LunarTarget;
      } catch {
        return t;
      }
    })
  );

  const anyLive = enriched.some((t) => t.label !== undefined);
  return { targets: enriched, live: anyLive };
}
