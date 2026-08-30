/**
 * config.ts — static configuration for Mission Control: the 12 workflow
 * stages and the map raster layers. Kept data-only so the UI components stay
 * declarative. Layer ids match the backend tile pyramid folder names
 * (/tiles/faustini/{layer}) and the mission.raster_layers base64 fallbacks.
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
  tiled: boolean;
  gradient: string;
  low: string;
  high: string;
  description: string;
}

/** Raster layers offered in the map's LAYERS control (single-select). */
export const LAYERS: LayerDef[] = [
  {
    id: 'hillshade', label: 'Surface Relief', swatch: '#9ca3af', tiled: true,
    gradient: 'linear-gradient(to right,#111827,#4b5563,#9ca3af,#f3f4f6)',
    low: 'Deep shadow', high: 'Sunlit rim',
    description: 'Analytical shaded relief from the LOLA DEM — the base lunar surface.',
  },
  {
    id: 'illumination', label: 'Shadowed Areas', swatch: '#f97316', tiled: true,
    gradient: 'linear-gradient(to right,#000000,#8b0000,#ff4500,#ffff00,#ffffff)',
    low: '0% — true PSR', high: '100% sunlit',
    description: 'Grazing solar illumination (1.5° sun). Black = permanently shadowed cold trap.',
  },
  {
    id: 'cpr_heatmap', label: 'Radar Signals (CPR)', swatch: '#06b6d4', tiled: true,
    gradient: 'linear-gradient(to right,#0000ff,#00ffff,#00ff00,#ffff00,#ff0000)',
    low: 'Dry regolith', high: 'Ice-like anomaly',
    description: 'Chandrayaan-2 DFSAR Circular Polarisation Ratio. High CPR can indicate icy backscatter.',
  },
  {
    id: 'ml_likelihood', label: 'Possible Ice P(ice)', swatch: '#c026d3', tiled: false,
    gradient: 'linear-gradient(to right,#000000,#581845,#900c3f,#c70039,#ff5733,#ffc300)',
    low: 'Unlikely', high: 'High likelihood',
    description: 'Random-Forest ice likelihood from fused radar, slope and temperature features.',
  },
  {
    id: 'hazard_map', label: 'Terrain Hazards', swatch: '#ef4444', tiled: true,
    gradient: 'linear-gradient(to right,#000080,#00ffff,#ffff00,#ff0000)',
    low: 'Safe pass', high: 'Impassable',
    description: 'Composite hazard = slope + roughness + boulders. Red marks cliff barriers.',
  },
  {
    id: 'dem_elevation', label: 'Elevation (DEM)', swatch: '#22c55e', tiled: true,
    gradient: 'linear-gradient(to right,#440154,#3b528b,#21918c,#5ec962,#fde725)',
    low: 'Crater floor', high: 'Rim crest',
    description: 'LOLA topographic relief. Purple = deep cold-trap floor, yellow = sunlit rim.',
  },
];

export const LAYER_MAP: Record<string, LayerDef> = Object.fromEntries(
  LAYERS.map((l) => [l.id, l])
);
