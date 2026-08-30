/**
 * lunarCRS.ts
 *
 * Defines a custom Leaflet CRS for the Lunar South Pole using
 * Polar Stereographic projection (ESPG:30100 analog).
 *
 * Moon radius: 1,737,400 m
 * Projection origin: lat_0=-90, lon_0=0 (South Pole)
 *
 * This prevents the severe Web Mercator distortion at -90° latitude.
 *
 * Usage:
 *   import { LunarSouthPoleCRS } from '@/utils/lunarCRS';
 *   const map = L.map(el, { crs: LunarSouthPoleCRS });
 */

import L from 'leaflet';
import proj4 from 'proj4';
import 'proj4leaflet';

// Lunar South Pole Polar Stereographic projection string
const LUNAR_SOUTH_POLE_PROJ =
  '+proj=stere +lat_0=-90 +lon_0=0 +k=1 +x_0=0 +y_0=0 +a=1737400 +b=1737400 +units=m +no_defs';

// Moon radius (m)
const MOON_RADIUS = 1_737_400;

// Scale factor: pixel-meters at various zoom levels (rough estimate for reference tile size)
// At zoom 0: tile covers full lunar circumference = 2π * R ≈ 10.917M m across 256 px
const LUNAR_SCALE_DENOMINATOR_Z0 = (2 * Math.PI * MOON_RADIUS) / 256;

const resolutions = Array.from({ length: 10 }, (_, z) =>
  LUNAR_SCALE_DENOMINATOR_Z0 / Math.pow(2, z)
);

const origin: [number, number] = [-MOON_RADIUS * Math.PI, MOON_RADIUS * Math.PI];

// Register proj4 definition for this projection
proj4.defs('MOON:SP', LUNAR_SOUTH_POLE_PROJ);

/**
 * Leaflet CRS for Lunar South Pole Polar Stereographic.
 * Use with L.Proj.CRS from proj4leaflet.
 */
export const LunarSouthPoleCRS: L.CRS = (L as any).Proj.CRS('MOON:SP', LUNAR_SOUTH_POLE_PROJ, {
  resolutions,
  origin,
  bounds: L.bounds(
    [-MOON_RADIUS * Math.PI, -MOON_RADIUS * Math.PI],
    [MOON_RADIUS * Math.PI, MOON_RADIUS * Math.PI]
  ),
});

/**
 * Fallback: Standard EPSG:4326 CRS for equirectangular lunar maps.
 * Use this if the WMS endpoint only supports geographic coordinates.
 */
export const LunarEPSG4326CRS: L.CRS = L.CRS.EPSG4326;
