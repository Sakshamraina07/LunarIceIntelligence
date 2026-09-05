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
  { id: 4, cat: 'AI', label: 'Ice Intelligence', desc: 'Continuous P(ice)', icon: Sparkles, layer: 'ml_likelihood' },
  { id: 5, cat: 'SAFETY', label: 'Terrain Hazards', desc: 'Slope & roughness', icon: Mountain, layer: 'hazard_map' },
  { id: 6, cat: 'LANDING', label: 'Landing Sites', desc: 'Algorithmic ranking', icon: Target, layer: 'hillshade' },
  { id: 7, cat: 'ROVER', label: 'Rover Traverse', desc: 'A* & science route', icon: Navigation, layer: 'hillshade' },
  { id: 8, cat: 'VOLUME', label: 'Volume Estimate', desc: '3-tier ice bounds', icon: Box, layer: 'dem_elevation' },
  { id: 9, cat: 'SWEEP', label: 'Sensitivity Studio', desc: 'Parameter sweeps', icon: Sliders, layer: 'cpr_heatmap' },
  { id: 10, cat: 'RESEARCH', label: 'Research Suite', desc: 'Ablation studies', icon: FlaskConical, layer: 'hazard_map' },
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
  description: string;
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
    description: 'Horn hillshade (sun 30° alt / 315° az) of LOLA LDEM_80S_80M V2.0. Measured topography, sampled at 80 m posts and carried on this frame’s 25 m grid — so the shape is real, but it holds no relief finer than 80 m.',
    provenance: 'measured',
  },
  {
    id: 'illumination', label: 'Shadowed Areas', swatch: '#f97316', tiled: true,
    gradient: 'linear-gradient(to right,#000004,#420a68,#932667,#dd513a,#fca50a,#fcffa4)',
    low: 'Darker', high: 'Brighter',
    description: 'A BRIGHTNESS PROXY, not a shadow map: hillshade(1.5° sun) × normalised elevation^1.3, inferno colormap. There is no horizon term in it, so it is not solar geometry and these are not cold traps. It darkens 77% of the frame, which tells you about the expression rather than the Moon. The topography underneath is measured LOLA; the shadow on top of it is not.',
    provenance: 'model',
  },
  {
    id: 'cpr_heatmap', label: 'Radar Signals (CPR)', swatch: '#06b6d4', tiled: true,
    gradient: 'linear-gradient(to right,#30123b,#4a68d8,#1ae4b6,#a4fc3c,#faba39,#d23105)',
    low: 'Lower CPR', high: 'Higher CPR',
    description: 'Chandrayaan-2 DFSAR Circular Polarisation Ratio, turbo colormap. Drawn only over the 15.6% of the frame that returned amplitude (8.8 km ribbon). ISRO’s beam footprint is 2.28× wider (35.6%, 19.3 km) and is outlined in grey — that band was observed but returned nothing, so no CPR value is drawn there. NOTE: this build’s CPR is σ_sc/σ_oc from amplitude only, max 0.053; true hybrid-polarity CPR needs the Stokes S3 phase term from the complex products.',
    provenance: 'measured',
  },
  {
    id: 'dop_heatmap', label: 'Degree of Polarisation', swatch: '#7c8fb5', tiled: true,
    gradient: 'linear-gradient(to right,#00204d,#31446b,#666970,#958f78,#cab969,#ffe945)',
    low: 'Depolarised', high: 'Polarised',
    description: 'Chandrayaan-2 DFSAR degree of polarisation, |S1|/S0, cividis colormap. Same amplitude mask as CPR. Low DOP means the return is depolarised — volume scattering rather than a smooth surface.',
    provenance: 'measured',
  },

  {
    id: 'ml_likelihood', label: 'Possible Ice P(ice)', swatch: '#c026d3', tiled: false,
    gradient: 'linear-gradient(to right,#000000,#581845,#900c3f,#c70039,#ff5733,#ffc300)',
    low: 'Unlikely', high: 'High likelihood',
    description: 'Random-Forest likelihood over six features: CPR and DOP (measured DFSAR), slope and roughness (measured LOLA, 80 m posts), and illumination + PSR mask (the modelled brightness proxy, no horizon term). There is no temperature feature — the previous copy claiming one was wrong. Read this as MODELLED and nothing stronger: the forest was fitted to SYNTHETIC labels in module_c_ice.py (uniform draws where class 1 is defined as CPR 1.05–2.5 with low DOP inside a PSR), so it encodes the CBOE threshold rule rather than any learned relationship — no ground-truth ice label exists anywhere in this project. This frame’s CPR maxes at 0.053, far outside that training range, so every pixel is an extrapolation.',
    provenance: 'model',
  },
  {
    id: 'hazard_map', label: 'Terrain Hazards', swatch: '#ef4444', tiled: true,
    gradient: 'linear-gradient(to right,#000004,#3b0f70,#8c2981,#de4968,#fe9f6d,#fcfdbf)',
    low: 'Safe pass', high: 'Impassable',
    description: 'Composite hazard = 0.6·(slope/25°) + 0.4·(roughness/40 m), magma colormap (the old JET map invented hazard edges that were not in the data). Slope and roughness are measured — computed from LOLA LDEM_80S_80M V2.0 at 80 m native posts — but the 0.6/0.4 split and both divisors are our chosen convention, not an observation. No boulder detection exists in this build (data/pradan/ohrc/ is empty), so boulder risk is UNMEASURED, not zero. CAVEAT: these are the weights this IMAGE is rendered with; the hazard NUMBER in the stat panel comes from config.py (0.5/0.3 renormalised over 0.8, divisors 20°/50 m) and is therefore not the same quantity.',
    provenance: 'measured',
  },
  {
    id: 'dem_elevation', label: 'Elevation (DEM)', swatch: '#22c55e', tiled: true,
    gradient: 'linear-gradient(to right,#440154,#3b528b,#21918c,#5ec962,#fde725)',
    low: 'Lower', high: 'Higher',
    description: 'LOLA LDEM_80S_80M V2.0 (LRO-L-LOLA-4-GDR-V1.0), 80 m native posts resampled bilinearly onto this frame’s 25 m grid, viridis colormap. Measured topography: elevation range −4246 m to +1957 m about the 1737.4 km reference sphere. Verified bit-identical to data/pradan/lola/ldem_frame_25m.tif on every build — the file it is read from is still named dem_native_synthetic.tif, and that name is now a lie kept only so existing consumers keep working.',
    provenance: 'measured',
  },
];

export const LAYER_MAP: Record<string, LayerDef> = Object.fromEntries(
  LAYERS.map((l) => [l.id, l])
);
