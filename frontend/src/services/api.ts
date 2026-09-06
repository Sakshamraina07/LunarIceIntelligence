import type { MissionState, CraterInfo, SensitivityAnalysisResult } from '../types/mission';

// Backend origin. In production set VITE_API_BASE (e.g. https://lunariceintelligence.onrender.com)
// on Vercel; falls back to the local FastAPI dev server otherwise.
export const API_ORIGIN = (import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000').replace(/\/$/, '');

/**
 * THE THREE BACKEND STATES, NAMED ONCE.
 *
 * The screen carried two of these at the same time and contradicted itself: a
 * panel saying the backend "is not reachable" beside one saying it "is reachable
 * but reports NOT_INGESTED", under a badge reading OFFLINE, while the backend
 * was answering. Three different sentences derived from `error != null`, which
 * cannot distinguish them.
 *
 *   'unreachable'  nothing answered — DNS, refused, CORS, mixed content
 *   'not_ingested' it answered, and said it holds no rasters for this crater
 *   'ok'           it answered with a full payload
 *
 * Every badge, banner and sentence about backend state reads THIS. A UI that
 * derives three states from one boolean will get one of them wrong, and it did.
 */
export type BackendState = 'pending' | 'unreachable' | 'not_ingested' | 'ok';

export class MissionUnavailable extends Error {
  readonly state: Exclude<BackendState, 'pending' | 'ok'>;
  constructor(state: Exclude<BackendState, 'pending' | 'ok'>, message: string) {
    super(message);
    this.name = 'MissionUnavailable';
    this.state = state;
  }
}

/** One place decides how each state is worded. */
export const BACKEND_COPY: Record<BackendState, { badge: string; heading: string }> = {
  pending: { badge: 'CHECKING HOST', heading: 'CHECKING HOST' },
  unreachable: { badge: 'BACKEND UNREACHABLE', heading: 'BACKEND UNREACHABLE' },
  not_ingested: { badge: 'NO RASTERS ON HOST', heading: 'NO RASTERS ON HOST' },
  ok: { badge: 'LIVE', heading: 'LIVE' },
};

/**
 * WHAT THE ON-DEMAND BACKEND IS ACTUALLY FOR.
 *
 * `NEEDS_BACKEND` WAS HERE AND HAS NO CONSUMER LEFT, WHICH IS THE RESULT.
 *
 * It existed because one sentence naming what a no-raster host costs had been
 * wrong four times: it claimed the landing sites and rover routes (static), then
 * "the sensitivity studio, the stage panels and the PDF" (the sweep tables were
 * static too), then "the four re-query sliders in stage 09, and the PDF" --
 * falsified by the commit that precomputed those sliders -- and finally it was
 * carried to stage 12 still describing stage 09's surroundings.
 *
 * The constant was the right response to a sentence with no generator. It is
 * removed now for the right reason: after the sweep grid, NOTHING on the map
 * screen needs the on-demand host, so there is no list to keep. The single
 * remaining consumer is the PDF, and the control that offers it names its own
 * state in its own words, where a reader is looking at it.
 *
 * If something on a screen ever needs the host again, it says so itself, beside
 * itself. A shared sentence describing other components' health is a description
 * with no computation behind it, and this project has now watched that exact
 * shape fail four times in a row.
 */
const API_BASE_URL = `${API_ORIGIN}/api`;

export async function fetchHealthCheck() {
  const res = await fetch(`${API_BASE_URL}/health`);
  if (!res.ok) throw new Error('Backend health check failed');
  return res.json();
}

export async function fetchCraters(): Promise<Record<string, CraterInfo>> {
  const res = await fetch(`${API_BASE_URL}/craters`);
  if (!res.ok) throw new Error('Failed to load craters');
  return res.json();
}

export async function fetchMissionState(
  craterId: string,
  options: {
    dataMode?: string;
    cprThreshold?: number;
    dopThreshold?: number;
    iceDepthM?: number;
    iceFraction?: number;
    algorithm?: string;
  } = {}
): Promise<MissionState> {
  const params = new URLSearchParams();
  if (options.dataMode) params.append('data_mode', options.dataMode);
  if (options.cprThreshold !== undefined) params.append('cpr_threshold', options.cprThreshold.toString());
  if (options.dopThreshold !== undefined) params.append('dop_threshold', options.dopThreshold.toString());
  if (options.iceDepthM !== undefined) params.append('ice_depth_m', options.iceDepthM.toString());
  if (options.iceFraction !== undefined) params.append('ice_fraction', options.iceFraction.toString());
  if (options.algorithm) params.append('algorithm', options.algorithm);

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/mission/${craterId}?${params.toString()}`);
  } catch (e) {
    // A rejected fetch is the network layer: DNS, refused connection, CORS,
    // mixed content. NOTHING ANSWERED. That is a different fact from a backend
    // that answered and said it holds no rasters, and the UI is required to say
    // which one it is.
    throw new MissionUnavailable('unreachable',
      `No response from ${API_ORIGIN}: ${e instanceof Error ? e.message : String(e)}`);
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ message: `HTTP ${res.status}` }));
    // An HTTP error IS a response, so the backend is reachable.
    throw new MissionUnavailable('not_ingested',
      err.message || err?.detail?.message || `The backend answered HTTP ${res.status}`);
  }
  const doc = await res.json();

  // A 200 IS NOT A PAYLOAD. The backend answers 200 with `status:
  // "NOT_INGESTED"` when it is reachable and holds none of the rasters — which
  // is exactly what the deployed instance does, because the 9 GB of Chandrayaan-2
  // and LOLA products are gitignored and are not on that host. That document has
  // no `target_coordinates`, no `landing_sites` and no `rover_routes`.
  //
  // It used to be returned as if it were a MissionState. Every consumer then
  // read fields the type promised were there, `mission.target_coordinates.x`
  // threw inside a React effect, the tree unmounted, and the deployed page was
  // blank. Rejecting here means `mission` non-null carries the meaning every
  // consumer already assumed, instead of each of them having to re-derive it.
  //
  // A backend too old to send `status` is treated as OK: absent is not
  // NOT_INGESTED, and inventing a degraded state for it would be the same
  // mistake pointed the other way.
  if (doc && typeof doc.status === 'string' && doc.status !== 'OK') {
    const why = doc?.gate?.reason ?? doc?.gate?.message ?? doc.status;
    throw new MissionUnavailable('not_ingested',
      `The mission backend is reachable but reports ${doc.status}: ${why}`);
  }
  return doc as MissionState;
}

export async function fetchSensitivity(parameterName: string, baseAreaKm2: number): Promise<SensitivityAnalysisResult> {
  const res = await fetch(`${API_BASE_URL}/sensitivity/${parameterName}?base_area_km2=${baseAreaKm2}`);
  if (!res.ok) throw new Error('Failed to load sensitivity analysis');
  return res.json();
}

export function getReportPdfUrl(craterId: string): string {
  return `${API_BASE_URL}/report/pdf/${craterId}`;
}

export async function askAICopilot(
  prompt: string,
  craterId: string,
  missionContext?: MissionState | null
): Promise<{
  success: boolean;
  provider: string;
  model: string;
  answer: string;
  context_used: boolean;
}> {
  const res = await fetch(`${API_BASE_URL}/copilot/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prompt,
      crater_id: craterId,
      mission_context: missionContext || null,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Copilot connection error' }));
    throw new Error(err.detail || 'Copilot error');
  }
  return res.json();
}

