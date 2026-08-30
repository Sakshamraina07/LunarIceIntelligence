/**
 * targets.ts
 * Data-driven catalogue of lunar south-polar exploration targets used by the
 * landing experience.
 *
 * SCIENTIFIC HONESTY:
 *   - `lat`/`lon`/`diameterKm` are established geographic facts (published crater
 *     locations) — NOT invented science.
 *   - `iceEvidence` and `psrFraction` are DEMO/placeholder screening values used
 *     only for the cinematic overlay. They are clearly flagged `demo: true`.
 *   - `craterId` links a target to a real backend mission crater when one exists
 *     (Shackleton / Shoemaker / Faustini). For those, live values can later be
 *     pulled from the FastAPI backend via services/missionData.ts and will
 *     override the demo fields.
 *
 * No target claims "confirmed water ice". Labels use the approved cautious
 * language ("Possible", "Promising candidate", "Evidence consistent with ...").
 */

export type EvidenceLevel = 'watch' | 'candidate' | 'promising';

export interface LunarTarget {
  id: string;
  name: string;
  /** Selenographic latitude (deg, negative = south). Geographic fact. */
  lat: number;
  /** Selenographic longitude (deg). Geographic fact. */
  lon: number;
  /** Approximate crater diameter in km. Geographic fact. */
  diameterKm: number;
  /** Backend crater id if this target maps to a real mission pipeline crater. */
  craterId?: string;
  /** Cautious human-readable status. Never "confirmed ice". */
  label: string;
  evidence: EvidenceLevel;
  /** DEMO placeholder: fraction of the region that is permanently shadowed. */
  psrFraction: number;
  /** DEMO placeholder: qualitative note shown in the marker tooltip. */
  note: string;
  /** True while the numeric fields above are demo/fallback values. */
  demo: boolean;
}

/**
 * Published crater centres near the lunar south pole. Values sourced from the
 * IAU/USGS Gazetteer of Planetary Nomenclature (public geographic facts).
 * Screening fields remain demo placeholders until wired to the backend.
 */
export const SOUTH_POLE_TARGETS: LunarTarget[] = [
  {
    id: 'shackleton',
    name: 'Shackleton',
    lat: -89.66,
    lon: 129.2,
    diameterKm: 21,
    craterId: 'shackleton',
    label: 'Promising candidate',
    evidence: 'promising',
    psrFraction: 0.9,
    note: 'Deep polar cold-trap almost entirely in permanent shadow.',
    demo: true,
  },
  {
    id: 'shoemaker',
    name: 'Shoemaker',
    lat: -88.1,
    lon: 44.9,
    diameterKm: 51,
    craterId: 'shoemaker',
    label: 'Promising candidate',
    evidence: 'promising',
    psrFraction: 0.82,
    note: 'Large shadowed floor; historic volatile-detection interest.',
    demo: true,
  },
  {
    id: 'faustini',
    name: 'Faustini',
    lat: -87.69,
    lon: 81.46,
    diameterKm: 39,
    craterId: 'faustini',
    label: 'Evidence consistent with potential ice',
    evidence: 'candidate',
    psrFraction: 0.75,
    note: 'Covered by a real Chandrayaan-2 DFSAR radar swath (2020-08-08).',
    demo: true,
  },
  {
    id: 'cabeus',
    name: 'Cabeus',
    lat: -85.33,
    lon: -42.13,
    diameterKm: 98,
    label: 'Potential ice-bearing region',
    evidence: 'candidate',
    psrFraction: 0.6,
    note: 'LCROSS impact site — a focus of past volatile studies.',
    demo: true,
  },
  {
    id: 'haworth',
    name: 'Haworth',
    lat: -87.45,
    lon: -5.15,
    diameterKm: 51,
    label: 'Potential ice-bearing region',
    evidence: 'candidate',
    psrFraction: 0.7,
    note: 'Persistent shadowed floor adjacent to Shoemaker and Faustini.',
    demo: true,
  },
  {
    id: 'nobile',
    name: 'Nobile',
    lat: -85.2,
    lon: 53.5,
    diameterKm: 73,
    label: 'Region under watch',
    evidence: 'watch',
    psrFraction: 0.45,
    note: 'Rim region shortlisted for future surface exploration.',
    demo: true,
  },
];

/** Colour ramp for the three evidence tiers (cyan-forward scientific accents). */
export const EVIDENCE_COLORS: Record<EvidenceLevel, string> = {
  watch: '#7c8aa0',
  candidate: '#38bdf8',
  promising: '#22d3ee',
};
