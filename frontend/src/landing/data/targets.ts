/**
 * targets.ts
 * Data-driven catalogue of lunar south-polar exploration targets used by the
 * landing experience.
 *
 * WHAT IS A FACT HERE AND WHAT IS NOT:
 *   - `lat`/`lon`/`diameterKm`/`name` are published geographic facts from the
 *     IAU/USGS Gazetteer of Planetary Nomenclature. They stay, unconditionally.
 *   - `note` is a published descriptive fact (an impact site, a documented
 *     shadowed floor), not a result of ours.
 *   - `label`, `evidence` and `psrFraction` are SCREENING VERDICTS. They are
 *     OPTIONAL and this file supplies none of them. Nothing in the repository
 *     may hardcode a verdict: they are written only by
 *     `services/missionData.ts` from a backend payload whose `data_mode` is
 *     REAL, and they arrive together or not at all.
 *
 * They used to be hardcoded — `psrFraction: 0.9`, `evidence: 'promising'`,
 * `label: 'Promising candidate'` — behind a `demo: true` flag. The flag was
 * visible in the source and invisible on the Moon: the marker glowed the
 * "promising" cyan and the panel read "Promising candidate" for craters this
 * project has never screened. Six targets, six verdicts, one ingested swath.
 *
 * A target with no verdict is not a target with a zero verdict. Absent fields
 * make the renderers show NOT INGESTED · NO DFSAR SWATH IN THIS BUILD, which is
 * what the build can defend.
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
  /** Published descriptive context. Never a result of this pipeline. */
  note: string;

  /**
   * SCREENING VERDICT — absent unless a REAL backend run produced it.
   * Never assign these in source. `missionData.ts` sets all three together.
   */
  label?: string;
  evidence?: EvidenceLevel;
  /** Fraction of the region in permanent shadow, measured from LOLA/DFSAR. */
  psrFraction?: number;
  /** Backend product id the verdict came from. Present iff the verdict is. */
  productId?: string;
}

/** True when a target has been screened against an ingested radar swath. */
export function isScreened(
  t: LunarTarget,
): t is LunarTarget & { label: string; evidence: EvidenceLevel } {
  return t.label !== undefined && t.evidence !== undefined;
}

/** Shown wherever a verdict would be, when there is no verdict. */
export const NOT_INGESTED_LABEL = 'NOT INGESTED · NO DFSAR SWATH IN THIS BUILD';

/** Marker colour for a target carrying no verdict: neutral, not a tier. */
export const UNSCREENED_COLOR = '#5b6472';

/**
 * Published crater centres near the lunar south pole (IAU/USGS Gazetteer).
 * No screening fields: see the header. `craterId` marks the three craters the
 * backend knows by name; only one of them has an ingested product, and the
 * backend — not this file — decides which.
 */
export const SOUTH_POLE_TARGETS: LunarTarget[] = [
  {
    id: 'shackleton',
    name: 'Shackleton',
    lat: -89.66,
    lon: 129.2,
    diameterKm: 21,
    craterId: 'shackleton',
    note: 'Rim-crest crater at the pole; floor documented as permanently shadowed.',
  },
  {
    id: 'shoemaker',
    name: 'Shoemaker',
    lat: -88.1,
    lon: 44.9,
    diameterKm: 51,
    craterId: 'shoemaker',
    note: 'Large degraded basin with an extensive shadowed floor.',
  },
  {
    id: 'faustini',
    name: 'Faustini',
    lat: -87.69,
    lon: 81.46,
    diameterKm: 39,
    craterId: 'faustini',
    note: 'Covered by a real Chandrayaan-2 DFSAR radar swath (2020-08-08).',
  },
  {
    id: 'cabeus',
    name: 'Cabeus',
    lat: -85.33,
    lon: -42.13,
    diameterKm: 98,
    note: 'LCROSS impact site — a focus of past volatile studies.',
  },
  {
    id: 'haworth',
    name: 'Haworth',
    lat: -87.45,
    lon: -5.15,
    diameterKm: 51,
    note: 'Shadowed floor adjacent to Shoemaker and Faustini.',
  },
  {
    id: 'nobile',
    name: 'Nobile',
    lat: -85.2,
    lon: 53.5,
    diameterKm: 73,
    note: 'Rim region shortlisted for future surface exploration.',
  },
];

/** Colour ramp for the three evidence tiers (cyan-forward scientific accents). */
export const EVIDENCE_COLORS: Record<EvidenceLevel, string> = {
  watch: '#7c8aa0',
  candidate: '#38bdf8',
  promising: '#22d3ee',
};

/** The colour a marker should use: its tier if screened, neutral if not. */
export function targetColor(t: LunarTarget): string {
  return t.evidence ? EVIDENCE_COLORS[t.evidence] : UNSCREENED_COLOR;
}
