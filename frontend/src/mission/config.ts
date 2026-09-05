/**
 * config.ts — static configuration for Mission Control: the 12 workflow
 * stages and the map raster layers. Kept data-only so the UI components stay
 * declarative.
 *
 * Layer ids match the single-image layer files written by
 * backend/scripts/render_layers.py into frontend/public/layers/ (and indexed by
 * layers.json), plus the mission.raster_layers base64 fallbacks for layers the
 * backend renders per request. They used to match tile-pyramid folder names;
 * the pyramid is gone.
 *
 * LAYER COPY LIVES IN THE MANIFEST, NOT HERE. Each entry below carries only the
 * presentation bits the manifest has no opinion about — the swatch colour, the
 * legend gradient, and the two end labels. The prose description and the
 * measured constants are read from layers.json at render time, because two
 * copies of the same constant is two chances for one of them to go stale, and
 * one already had.
 *
 * There are SIX layers, not seven. `ml_likelihood` was removed: it had no
 * manifest entry, so it was the one layer whose pixels came from the on-demand
 * backend as a base64 PNG on a square 2048² grid, squashed onto this frame's
 * 2.93:1 bounds and drawn beside five correctly-projected measured rasters. The
 * model behind it is withdrawn (see module_c_ice.py).
 *
 * Layer copy is provenance-honest. It used to say four of these six layers came
 * from an ANALYTIC PLACEHOLDER DEM. That is no longer true: the elevation raster
 * now holds LOLA LDEM_80S_80M V2.0 (80 m posts, bilinear to this frame's 25 m
 * grid), verified bit-identical to data/pradan/lola/ldem_frame_25m.tif on every
 * build. So relief, elevation and hazard are measured. What is still a model is
 * the ILLUMINATION layer — a brightness proxy with no horizon term in it — and
 * P(ice). Every layer carries a `provenance` tag that the legend renders as a
 * badge, so the map cannot imply a measurement it lacks.
 * Ground truth for these tags: data/pradan/lola/ldem_frame_25m.provenance.json,
 * data/pradan/dfsar/metadata_real.json (`product_provenance`) and
 * frontend/public/layers/layers.json (`layers[].provenance`).
 *
 * The `gradient` strings below must match the colormap each layer is actually
 * rendered with, or the legend lies about the picture. Current pairings:
 * hillshade=grayscale, illumination=inferno, cpr_heatmap=turbo, hazard_map=magma,
 * dem_elevation=viridis. COLORMAP_JET is no longer used anywhere — its
 * non-monotonic lightness manufactured false edges in smooth data.
 */
import {
  Orbit, Sun, Radio, Sparkles, Mountain, Target,
  Navigation, Box, Sliders, FlaskConical, HelpCircle, FileText,
  type LucideIcon,
} from 'lucide-react';

export interface StepDef {
  id: number;
  cat: string;
  label: string;
  desc: string;
  icon: LucideIcon;
  /** raster layer auto-selected on the map when this stage opens */
  layer: string;
}

export const STEPS: StepDef[] = [
  { id: 1, cat: 'SITE', label: 'Target Selection', desc: 'South-polar catalogue', icon: Orbit, layer: 'hillshade' },
  { id: 2, cat: 'OPTICAL', label: 'Shadow & PSR', desc: 'Illumination & cold traps', icon: Sun, layer: 'illumination' },
  { id: 3, cat: 'RADAR', label: 'DFSAR Radar', desc: 'CPR & DOP screening', icon: Radio, layer: 'cpr_heatmap' },
  { id: 4, cat: 'SCREEN', label: 'Ice Criteria Screen', desc: 'CPR & DOP criteria', icon: Sparkles, layer: 'cpr_heatmap' },
  { id: 5, cat: 'SAFETY', label: 'Terrain Hazards', desc: 'Slope & roughness', icon: Mountain, layer: 'hazard_map' },
  { id: 6, cat: 'LANDING', label: 'Landing Sites', desc: 'Algorithmic ranking', icon: Target, layer: 'hillshade' },
  { id: 7, cat: 'ROVER', label: 'Rover Traverse', desc: 'A* & science route', icon: Navigation, layer: 'hillshade' },
  { id: 8, cat: 'VOLUME', label: 'Volume Estimate', desc: '3-tier ice bounds', icon: Box, layer: 'dem_elevation' },
  { id: 9, cat: 'SWEEP', label: 'Sensitivity Studio', desc: 'Parameter sweeps', icon: Sliders, layer: 'cpr_heatmap' },
  { id: 10, cat: 'RESEARCH', label: 'Planner Ablation', desc: 'Weight ablation', icon: FlaskConical, layer: 'hazard_map' },
  { id: 11, cat: 'DEFENSE', label: 'Viva Rationale', desc: 'Defensible reasoning', icon: HelpCircle, layer: 'hillshade' },
  { id: 12, cat: 'REPORT', label: 'Mission Report', desc: 'PDF / JSON export', icon: FileText, layer: 'hillshade' },
];

export interface LayerDef {
  id: string;
  label: string;
  swatch: string;
  /**
   * True when render_layers.py writes a pre-rendered image for this layer into
   * frontend/public/layers/. False means the pixels arrive as a base64 PNG in
   * mission.raster_layers instead (only `ml_likelihood` today).
   *
   * Historical name: this used to mean "has a tile pyramid". MissionMap no
   * longer branches on it — it looks the id up in layers.json and falls back to
   * mission.raster_layers — so it is documentation now, not control flow.
   */
  tiled: boolean;
  gradient: string;
  low: string;
  high: string;
  /**
   * NO `description` FIELD. It used to hold a paragraph per layer restating
   * constants that layers.json already carries — valid_fraction, ribbon
   * thickness, vmin/vmax, the hazard weights — and they had already drifted:
   * the hazard entry here still described a 0.6/0.4 blend over 25 deg / 40 m
   * divisors and warned that the picture and the number were "not the same
   * quantity", while render_layers.py had since been changed to call
   * module_d_terrain.compute_hazard_score, the same function the number comes
   * from. The manifest's own `description` is now rendered instead, so the
   * caption cannot disagree with the pixels it captions.
   */
  /**
   * Where the pixels actually come from. Rendered as a badge on the map legend
   * so no layer can imply a measurement it does not have.
   *
   *   'measured'  — an observation, or a direct geometric consequence of one:
   *                 calibrated Chandrayaan-2 DFSAR radar, or LOLA topography
   *                 (LDEM_80S_80M V2.0, 80 m posts — see
   *                 data/pradan/lola/ldem_frame_25m.provenance.json)
   *   'synthetic' — derived from an invented raster. NO LAYER USES THIS NOW; the
   *                 placeholder DEM was replaced by LOLA. Kept so a crater with
   *                 no real product can still be labelled honestly.
   *   'model'     — a model's output, not an observation: the illumination proxy
   *                 and the P(ice) likelihood
   */
  provenance: 'measured' | 'synthetic' | 'model';
}

/** Raster layers offered in the map's LAYERS control (single-select). */
export const LAYERS: LayerDef[] = [
  {
    id: 'hillshade', label: 'Surface Relief', swatch: '#9ca3af', tiled: true,
    gradient: 'linear-gradient(to right,#111827,#4b5563,#9ca3af,#f3f4f6)',
    low: 'Deep shadow', high: 'Sunlit rim',
    provenance: 'measured',
  },
  {
    id: 'illumination', label: 'Solar Illumination', swatch: '#f97316', tiled: true,
    gradient: 'linear-gradient(to right,#000004,#420a68,#932667,#dd513a,#fca50a,#fcffa4)',
    low: 'Never lit (PSR)', high: 'Most lit',
    // Was 'model', for a brightness proxy with no horizon term. Phase 2 replaced
    // that with a horizon computation over the full LOLA polar array, so this is
    // now a geometric consequence of measured topography. The badge itself is
    // driven from layers.json (see provBadge in MissionControl), so this field
    // is the fallback rather than the authority.
    provenance: 'measured',
  },
  {
    id: 'cpr_heatmap', label: 'Radar Signals (CPR)', swatch: '#06b6d4', tiled: true,
    gradient: 'linear-gradient(to right,#30123b,#4a68d8,#1ae4b6,#a4fc3c,#faba39,#d23105)',
    low: 'Lower CPR', high: 'Higher CPR',
    provenance: 'measured',
  },
  {
    id: 'dop_heatmap', label: 'Degree of Polarisation', swatch: '#7c8fb5', tiled: true,
    gradient: 'linear-gradient(to right,#00204d,#31446b,#666970,#958f78,#cab969,#ffe945)',
    low: 'Depolarised', high: 'Polarised',
    provenance: 'measured',
  },

  {
    id: 'hazard_map', label: 'Terrain Hazards', swatch: '#ef4444', tiled: true,
    gradient: 'linear-gradient(to right,#000004,#3b0f70,#8c2981,#de4968,#fe9f6d,#fcfdbf)',
    low: 'Safe pass', high: 'Impassable',
    provenance: 'measured',
  },
  {
    id: 'dem_elevation', label: 'Elevation (DEM)', swatch: '#22c55e', tiled: true,
    gradient: 'linear-gradient(to right,#440154,#3b528b,#21918c,#5ec962,#fde725)',
    low: 'Lower', high: 'Higher',
    provenance: 'measured',
  },
];

export const LAYER_MAP: Record<string, LayerDef> = Object.fromEntries(
  LAYERS.map((l) => [l.id, l])
);
