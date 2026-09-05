import type { MissionState, CraterInfo, SensitivityAnalysisResult } from '../types/mission';

// Backend origin. In production set VITE_API_BASE (e.g. https://lunariceintelligence.onrender.com)
// on Vercel; falls back to the local FastAPI dev server otherwise.
export const API_ORIGIN = (import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000').replace(/\/$/, '');
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

  const res = await fetch(`${API_BASE_URL}/mission/${craterId}?${params.toString()}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ message: 'Network error' }));
    throw new Error(err.message || 'Failed to fetch mission state');
  }
  return res.json();
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

