/**
 * missionData.ts
 * Typed frontend service that bridges the landing experience to the existing
 * FastAPI backend WITHOUT performing any scientific computation in the browser.
 *
 * Architecture:
 *   Three.js / React UI  ->  this service layer  ->  FastAPI backend  ->  modules A-G
 *
 * The landing page renders instantly from the demo target catalogue
 * (data/targets.ts). If the backend is reachable, this service enriches the
 * targets that map to a real mission crater with live pipeline values (PSR
 * fraction, cautious ice status) and flips their `demo` flag to false. All
 * scientific numbers therefore originate in the backend, never here.
 */

import { SOUTH_POLE_TARGETS, type LunarTarget } from '../data/targets';

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
    return { online: true, mode: data.mode, version: data.version };
  } catch {
    return { online: false };
  }
}

/** Map a backend ice result to the cautious evidence tier used by the UI. */
function evidenceFromScreening(status: string, likelihood: number): LunarTarget['evidence'] {
  if (status === 'PASS' && likelihood >= 0.5) return 'promising';
  if (status === 'PASS') return 'candidate';
  return 'watch';
}

/**
 * Enrich demo targets with live backend values where a `craterId` exists.
 * Returns the (possibly enriched) target list plus whether the backend was used.
 * Never throws — always degrades gracefully to the demo catalogue.
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
        const psrFraction = mission?.psr?.psr_area_fraction ?? t.psrFraction;
        const status = mission?.ice?.scientific_screening_status ?? 'FAIL';
        const likelihood = mission?.ice?.ml_ice_likelihood_mean ?? 0;
        const evidence = evidenceFromScreening(status, likelihood);
        const label =
          evidence === 'promising'
            ? 'Promising candidate'
            : evidence === 'candidate'
              ? 'Evidence consistent with potential ice'
              : 'Region under watch';
        return { ...t, psrFraction, evidence, label, demo: false } satisfies LunarTarget;
      } catch {
        return t;
      }
    })
  );

  const anyLive = enriched.some((t) => !t.demo);
  return { targets: enriched, live: anyLive };
}
