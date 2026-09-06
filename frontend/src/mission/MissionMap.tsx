/**
 * MissionMap.tsx — the hero analysis map (≈70% of the workspace).
 *
 * A Leaflet CRS.Simple viewer over SINGLE-IMAGE layers. Every layer is one
 * lossless WebP served from /layers/, and every number describing where those
 * images sit comes out of /layers/layers.json. Nothing about the geometry is
 * hardcoded in this file any more.
 *
 * V4 — THE TILE PYRAMID IS GONE, AND THAT IS THE POINT
 * ---------------------------------------------------
 * The science array is 2258 x 6618 = 14.9 MP at an isotropic 25 m/px, read from
 * the product's own GeoTIFF GeoKeys. That is smaller than a phone photo, and
 * 6618 samples cover 165.45 km, so 25 m/px IS the native detail. On a ~1400 px
 * map panel showing the whole swath you are already at ~118 m/px — a 4.7x
 * downsample — so there was never anything below 25 m to stream. The pyramid
 * bought nothing and cost:
 *
 *   - ~331 tiles per layer x 6 layers = ~2000 HTTP requests to paint one map;
 *   - a percentile stretch fitted PER TILE, which made every tile a different
 *     mapping and drew visible seams across the swath;
 *   - a square resize that squashed a 2.93 : 1 strip;
 *   - class LunarTileLayer, the additive y-flip (coords.y + rowsAtZoom(z)),
 *     _isValidTile, the maxNativeZoom/maxZoom split and TILE_BASE — all of
 *     which existed only to survive the pyramid, and all of which are deleted.
 *
 * What replaced them: backend/scripts/render_layers.py normalises each layer
 * ONCE over the whole array, colourises once, and writes {layer}.webp plus a
 * 640 px {layer}.preview.webp into frontend/public/layers/. Vercel serves those
 * from its CDN, so the map paints with the Render backend completely stopped —
 * the backend is now only asked for JSON analysis results.
 *
 * ALPHA CARRIES THE FOOTPRINT
 * --------------------------
 * Measured, not assumed: the 2020-08-08 DFSAR pass records amplitude on 15.64%
 * of its own raster (padding 84.36%). Both L-band and S-band lh/lv products are
 * nonzero on exactly that fraction, so it is the acquisition, not a processing
 * loss, and cropping cannot fix it — the bounding box of a diagonal ribbon is
 * 1783 x 6606 and still only 19.84% valid. The ribbon is SOLID (99.55% of
 * pixels between its two edges are valid) and about 351 native px = 8.8 km
 * thick over the full 165 km length.
 *
 * So the radar layers are written with alpha = 0 outside that ribbon: the empty
 * 84% is genuinely transparent instead of being coloured as if it were data.
 *
 * V8 — NOTHING IS DRAWN OVER THE GROUND
 * ------------------------------------
 * v6 marked that empty 84% with a near-opaque scrim (fillOpacity 0.82 of #03060c
 * outside ISRO's pointed swath, 0.5 inside). v7 replaced it with a 45° SVG hatch
 * over a light flat tint. Both were wrong, and the second was wrong for a subtler
 * reason than the first. Measured off the real canvas at zoom 4 (mean relative
 * luminance per tier, sRGB):
 *
 *      tier                     base     v6 scrim    v7 hatch    v8
 *      amplitude ribbon        0.5212      0.997       1.000    1.000
 *      pointed, no amplitude   0.5116      0.236       0.900    1.000
 *      never observed          0.4496      0.041       0.747    1.000
 *
 * v6 crushed the ground to 4.1% of its own luminance, which reads as ABSENCE when
 * there is a full-frame DEM under there. v7 fixed the luminance but kept spending
 * a whole rendering layer, an injected <pattern>, a fallback path and a legend box
 * on a fact that is not spatial: the un-measured region is a PROVENANCE statement,
 * and provenance belongs in words, where it can be exact. Words already carry it —
 * the layer card reads "MEASURED TOPOGRAPHY — LOLA LDEM_80S_80M V2.0, 80 m posts"
 * (in v7 it read "SYNTHETIC DEM", because the base then was a placeholder; V10
 * retagged it after the LOLA ingest, which changes the badge but not this argument),
 * the analysis rail reads 1,460.68 km² of measured radar in a 9,339.65 km² frame.
 * Neither of those can be misread as terrain the way a hatch can.
 *
 * So v8 removes the treatment entirely and the relief is read at full luminance.
 * Coverage is still classified, still measured, and still stated — by two 1 px
 * outlines with tooltips (the measured amplitude ribbon, ISRO's pointed sri_ma
 * swath) and by the console table at the bottom of this file. What is gone is the
 * three fill polygons, ensureHatch(), the hatch fallback, and the coverage key
 * panel. mix-blend-mode is still not used: M5 established that blending destroys
 * the CPR ribbon this app exists to show.
 *
 * COVERAGE IS CLASSIFIED, NOT HIDDEN
 * ---------------------------------
 * The five landing sites are hardcoded grid offsets — candidate_offsets at
 * backend/app/modules/module_e_landing.py:48-54, five (y,x) pairs on the 100x100
 * grid. target_coordinates is NOT hardcoded: mission_service.py:264-278 takes the
 * scientific-candidate pixel nearest the candidate centroid with slope < 15 deg,
 * and only falls back to the grid centre (dem.shape//2) when that mask is empty.
 * So the target moves with the thresholds and with the data_mode of whichever
 * backend answered, while the sites do not. Every site, every waypoint and the
 * target are ray-cast against the measured amplitude ring and ISRO's pointed
 * swath — but v7 then drew everything that tested OUTSIDE at weight 1 /
 * opacity 0.35 / no fill, which made 5 of 5 landing sites and ~95% of every rover
 * route nearly invisible. Those are the exact objects this app exists to show. A
 * caveat that erases the deliverable is not a caveat, it is a bug.
 *
 * v8 keeps every vector at full weight and moves the caveat into COLOUR: anything
 * outside the measured ribbon is drawn in amber (#f2c14e) with the reason in its
 * tooltip, so it is legible AND flagged. The counts stay in the console table.
 *
 * PAST NATIVE ZOOM THE PIXELS GO SQUARE
 * ------------------------------------
 * Native zoom is log2(samples / width_units) ≈ 4.69, where one screen pixel is
 * one image pixel. Beyond it the overlay switches to image-rendering: pixelated.
 * Honest sharp pixels instead of mushy bicubic mush, and it makes the 25 m
 * resolution limit visible rather than hiding it behind interpolation.
 *
 * The scale bar is driven by the manifest's metres_per_unit (derived from the
 * product's 25 m spacing), not mission.grid_dimensions.pixel_scale_m, which is
 * 250 m on the square analysis grid the science modules read — see
 * `analysis_grid.known_inconsistency` in data/pradan/dfsar/metadata_real.json.
 *
 * Nothing scientific is computed here. Grid/site/route coordinates come straight
 * from the backend mission state. The lat/lon readout is a coarse tangent-plane
 * approximation and is marked "≈" in the UI; the exact closed-form south polar
 * stereographic inverse, validated against ISRO's own geolocation grid to
 * sub-pixel rms, lives in backend/app/ingestion/sar_geometry.py.
 */
import { useEffect, useImperativeHandle, useRef, useState, forwardRef } from 'react';
import type { SearchedSite } from './analysis';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { MissionState, CandidateLandingSite } from '../types/mission';
import { LAYER_MAP } from './config';

/** Static assets, served by the frontend host — never by the science backend. */
const LAYERS_BASE = `${import.meta.env.BASE_URL}layers`;
const MANIFEST_URL = `${LAYERS_BASE}/layers.json`;

/*
 * KM_PER_DEG_LAT = 30.37 and MIN_COS_LAT USED TO LIVE HERE.
 *
 * They implemented a flat tangent-plane readout: a fixed 30.37 km per degree of
 * latitude, and the same constant divided by cos(crater latitude) for
 * longitude. At -87.7° that cos is 0.0402, and at -89.9° it is 0.00175, so the
 * longitude figure was wrong by a factor of ~25 to ~570 depending on where the
 * cursor was — beside a backend whose inverse projection is validated to 13.2 mm
 * against ISRO's own 937,296-node geolocation grid.
 *
 * Replaced by `frameLatLon()` below: the same closed-form south polar
 * stereographic inverse the backend uses (sar_geometry.SarFrame.xy_to_latlon),
 * evaluated from the projection parameters layers.json already carries. There is
 * no approximation left in it, so the "≈" in the readout is gone too.
 */

/* ─────────────────────── the manifest render_layers.py writes ───────────── */

export interface LayerManifestEntry {
  id: string;
  label: string;
  file: string;
  preview: string;
  width: number;
  height: number;
  bytes: number;
  preview_bytes: number;
  colormap: string;
  stretch: {
    mode: string; expression: string; fitted_over_fraction: number;
    /** Present and false when the colour scale is NOT linear in the value —
     *  the hypsometric tint uses percentile breakpoints. The legend must say so,
     *  because a ramp whose spacing implies metres it does not represent is a
     *  caption that stopped tracking its own computation. */
    linear_in_value?: boolean;
    percentiles?: number[];
    knots?: number[];
  };
  /** Choices made for LEGIBILITY rather than measurement, named by the renderer. */
  display_choices?: Record<string, unknown> | null;
  contours_m?: number | null;
  vmin: number;
  vmax: number;
  alpha_opaque: number;
  transparent_where: string;
  provenance: string;
  /** What this layer's numbers were actually measured at. Written by
   *  render_layers.py alongside the pixels. Differs BETWEEN layers on the same
   *  map: after Phase 6 the terrain is 20 m-derived while the shadow mask is
   *  still 80 m-derived (240 m effective), because the horizon sweep is not
   *  feasible on the 20 m polar array. Optional because older manifests predate
   *  the field, and a missing resolution must read as absent, not as 25 m. */
  resolution?: {
    native_metres_per_pixel: number | null;
    effective_metres_per_pixel: number | null;
    decimation_factor: number | null;
    basis: string;
  } | null;
  source_rasters: string[];
  description: string;
}

export interface LayersManifest {
  schema: string;
  generated_utc: string;
  product_id: string;
  native: {
    lines: number;
    samples: number;
    metres_per_pixel: { line: number; sample: number };
    metres_per_pixel_source: string;
    extent_km: { across_track: number; along_track: number };
  };
  crs: {
    width_units: number;
    height_units: number;
    bounds: [[number, number], [number, number]];
    metres_per_unit: number;
    native_zoom: number;
  };
  /**
   * The product's own georeferencing, written straight from its GeoTIFF
   * GeoKeys. Optional only because an older layers.json predates it; without it
   * the map reports no coordinates rather than approximating them.
   */
  geodetic_frame?: {
    crs: {
      name: string;
      body_radius_m: number;
      latitude_of_origin_deg: number;
      central_meridian_deg: number;
      false_easting_m: number;
      false_northing_m: number;
    };
    raster: {
      lines: number;
      samples: number;
      pixel_size_m: { x: number; y: number };
      raster_type: string;
      tiepoint_xy_m: { easting: number; northing: number };
    };
  };
  footprint: {
    valid_fraction: number;
    padding_fraction: number;
    area_km2?: number;
    ribbon_thickness_km: { median: number; mean: number };
    /** [fy_from_top, fx], both 0..1 of the raster — unit coords, not CRS units. */
    ring_unit_coords: [number, number][];
    /**
     * ISRO's own sri_ma swath mask — where the beam was POINTED, 2.28x wider
     * than the amplitude that came back. Outline only: 56.11% of it carries
     * literal integer zero amplitude, so no radar colour is painted there.
     * Optional because an older layers.json predates the two-mask model.
     */
    swath?: {
      source: string;
      fraction: number;
      area_km2: number;
      ribbon_thickness_km: { median: number; mean: number };
      nominal_swath_km: number;
      ring_unit_coords: [number, number][];
      amplitude_fraction_of_swath: number;
    };
  };

  layers: LayerManifestEntry[];
}

/** Everything the map needs, all of it derived from the manifest. */
interface MapGeometry {
  boundH: number;
  boundW: number;
  bounds: L.LatLngBoundsLiteral;
  metresPerUnit: number;
  nativeZoom: number;
  metresPerNativePx: number;
  acrossKm: number;
  alongKm: number;
  /** measured amplitude ribbon in CRS units, [lat, lng] */
  ring: [number, number][];
  /** ISRO's pointed swath in CRS units — outline only, may be empty */
  swathRing: [number, number][];
  frame: [number, number][];
  ribbonCentre: [number, number];
  /**
   * The opening view, and where "Reset view" returns to — a HOME_WINDOW_KM square
   * centred on the measured ribbon, in CRS units.
   *
   * Not geom.bounds. The frame is 56.45 x 165.45 km, 1:2.93, so fitting the whole
   * extent into any panel produces a letterbox in which the deliverable — craters,
   * candidate sites, the traverse — is a few dozen screen pixels tall. A reviewer
   * cannot read that, and it is the single loudest complaint this file has had.
   * A fixed ground window is also panel-independent: the same 40 km on a laptop
   * and on a projector, instead of "whatever fits".
   */
  homeBounds: L.LatLngBoundsLiteral;
  /** Side of homeBounds in km, for the tooltip that explains the reset button. */
  homeKm: number;
  validFraction: number;
  ribbonKm: number;
  /** ISRO swath: fraction of frame, ribbon width km, and how much returned signal */
  swathFraction: number;
  swathKm: number;
  swathNominalKm: number;
  amplitudeOfSwath: number;
  /**
   * layers.json → layers[id=hillshade].provenance, verbatim. The wording on the
   * amplitude-ring tooltip is driven off this string rather than a constant, so
   * when render_layers.py starts writing a measured LOLA base the map re-labels
   * itself with no second visual pass.
   */
  baseProvenance: string;
  /** true while baseProvenance still says the base DEM is synthetic. */
  placeholderBase: boolean;
  byId: Record<string, LayerManifestEntry>;
  /**
   * The exact projection, or null when layers.json predates geodetic_frame.
   * Null means the coordinate readout says so instead of approximating.
   */
  proj: FrameProjection | null;
  /** true when layers.json could not be read: vectors only, and the UI says so. */
  degraded: boolean;
}

/* ───────────────────────────── manifest loading ──────────────────────────── */

let manifestPromise: Promise<LayersManifest | null> | null = null;

/**
 * The manifest, fetched once and shared. Exported so MissionControl can render
 * each layer's description from layers.json instead of from a second copy in
 * config.ts — which is how the hazard caption came to describe a 0.6/0.4 blend
 * that render_layers.py had already stopped using.
 */
export function loadManifest(): Promise<LayersManifest | null> {
  if (!manifestPromise) {
    manifestPromise = fetch(MANIFEST_URL, { cache: 'force-cache' })
      .then((r) => (r.ok ? (r.json() as Promise<LayersManifest>) : Promise.reject(new Error(`HTTP ${r.status}`))))
      .catch((err) => {
        // Loud on purpose. A silent fallback here would put the map back where
        // it started: geometry that looks plausible and is not measured.
        console.error(
          `[MissionMap] could not read ${MANIFEST_URL} (${err}). ` +
          'Run: python backend/scripts/render_layers.py',
        );
        return null;
      });
  }
  return manifestPromise;
}

/**
 * Module-scope copy of the resolution facts, so the zoom readout in
 * MissionControl can be honest without threading the manifest through props
 * (Props and MissionMapHandle are a fixed contract).
 */
let RESOLUTION: { nativeZoom: number; metresPerNativePx: number } | null = null;

/**
 * Ground resolution for the current Leaflet zoom.
 *
 * Past native zoom this deliberately keeps saying 25 m/px and reports the
 * upscale factor instead. Screen pixels do get smaller than 12.5 m up there, but
 * there is no 12.5 m information in the file, and printing it would be a claim
 * of detail that does not exist.
 */
export function groundResolutionLabel(zoom: number): string {
  if (!RESOLUTION) return 'resolution pending';
  const { nativeZoom, metresPerNativePx } = RESOLUTION;
  if (zoom > nativeZoom + 0.02) {
    return `${metresPerNativePx} m/px native · upscaled ${Math.pow(2, zoom - nativeZoom).toFixed(1)}×`;
  }
  if (zoom > nativeZoom - 0.02) return `${metresPerNativePx} m/px · native detail`;
  const mPerPx = metresPerNativePx * Math.pow(2, nativeZoom - zoom);
  return `${mPerPx >= 100 ? Math.round(mPerPx) : Math.round(mPerPx * 10) / 10} m/px`;
}

/**
 * Side of the opening window, in km of ground.
 *
 * 40 km is a crater, not a swath: Faustini is ~39 km across, Shackleton ~21 km,
 * Shoemaker ~51 km. The frame it sits in is 56.45 x 165.45 km, so this shows the
 * full across-track width minus a margin and about a quarter of the along-track
 * length — the largest window in which a 39 km crater still reads as a crater.
 * At a 1000 px panel that is ~40 m/px, just coarser than the 25 m/px the file
 * actually holds, so there is real detail left to zoom into rather than upscaling.
 */
const HOME_WINDOW_KM = 40;

function buildGeometry(mf: LayersManifest | null): MapGeometry {
  if (!mf) {
    // No manifest, no imagery. The vectors still need a frame to live in, so a
    // unit square is used and `degraded` makes the UI admit it.
    return {
      boundH: 100, boundW: 100, bounds: [[0, 0], [100, 100]],
      metresPerUnit: 0, nativeZoom: 0, metresPerNativePx: 0,
      acrossKm: 0, alongKm: 0,
      ring: [], swathRing: [], frame: [[0, 0], [0, 100], [100, 100], [100, 0]],
      ribbonCentre: [50, 50],
      // Degraded means there is no scale to place a 40 km window on, so home is
      // the whole placeholder square.
      homeBounds: [[0, 0], [100, 100]], homeKm: 0,
      validFraction: 0, ribbonKm: 0,
      swathFraction: 0, swathKm: 0, swathNominalKm: 0, amplitudeOfSwath: 0,
      // Fail toward flagging: with no manifest the base cannot be shown to be
      // measured, so it is treated as placeholder.
      baseProvenance: 'unavailable', placeholderBase: true,
      byId: {}, proj: null, degraded: true,
    };
  }
  const boundH = mf.crs.height_units;
  const boundW = mf.crs.width_units;
  // [fy_from_top, fx] -> [lat, lng]. CRS.Simple puts (0,0) at the BOTTOM-left,
  // and the image fills the whole extent, so raster row 0 is at lat = boundH.
  const toCrs = (pts: [number, number][]) =>
    pts.map(([fy, fx]) => [boundH * (1 - fy), boundW * fx] as [number, number]);
  const ring = toCrs(mf.footprint.ring_unit_coords);
  const sw = mf.footprint.swath;
  const swathRing = sw ? toCrs(sw.ring_unit_coords) : [];
  // The base layer's own provenance string decides how the never-observed
  // region is drawn and what it is called. Absent entry -> treat as placeholder.
  const baseProv = mf.layers.find((l) => l.id === 'hillshade')?.provenance ?? 'unknown';
  const centre: [number, number] = ring.length
    ? [ring.reduce((s, p) => s + p[0], 0) / ring.length,
       ring.reduce((s, p) => s + p[1], 0) / ring.length]
    : [boundH / 2, boundW / 2];
  // The home window, in CRS units. metres_per_unit is isotropic (87.344817 units
  // x 646.289 = 56,450 m across, 256 x 646.289 = 165,450 m along), so one half-side
  // serves both axes. Clamped to the frame: near an edge the window truncates
  // rather than panning off the raster, which maxBounds would fight anyway.
  const half = (HOME_WINDOW_KM * 1000) / mf.crs.metres_per_unit / 2;
  const homeBounds: L.LatLngBoundsLiteral = [
    [Math.max(0, centre[0] - half), Math.max(0, centre[1] - half)],
    [Math.min(boundH, centre[0] + half), Math.min(boundW, centre[1] + half)],
  ];
  return {
    boundH, boundW,
    bounds: [[0, 0], [boundH, boundW]],
    metresPerUnit: mf.crs.metres_per_unit,
    nativeZoom: mf.crs.native_zoom,
    metresPerNativePx: mf.native.metres_per_pixel.sample,
    acrossKm: mf.native.extent_km.across_track,
    alongKm: mf.native.extent_km.along_track,
    ring,
    swathRing,
    frame: [[0, 0], [0, boundW], [boundH, boundW], [boundH, 0]],
    ribbonCentre: centre,
    homeBounds,
    homeKm: HOME_WINDOW_KM,
    validFraction: mf.footprint.valid_fraction,
    ribbonKm: mf.footprint.ribbon_thickness_km.median,
    swathFraction: sw ? sw.fraction : 0,
    swathKm: sw ? sw.ribbon_thickness_km.median : 0,
    swathNominalKm: sw ? sw.nominal_swath_km : 0,
    amplitudeOfSwath: sw ? sw.amplitude_fraction_of_swath : 0,
    baseProvenance: baseProv,
    placeholderBase: PLACEHOLDER_PROVENANCE.test(baseProv),
    byId: Object.fromEntries(mf.layers.map((l) => [l.id, l])),
    proj: projectionFrom(mf),
    degraded: false,
  };
}

/* ───────────────────── coverage classification (v7 §3) ───────────────────── */

/**
 * Any provenance string that does NOT assert a measurement. Matched loosely on
 * purpose: the next value render_layers.py writes for a real base will be
 * something like "measured-topography-lola", and anything that still says
 * synthetic, placeholder, analytic or unknown must keep the placeholder marking.
 */
const PLACEHOLDER_PROVENANCE = /synthetic|placeholder|analytic|unknown|unavailable/i;

/**
 * Ray-casting point-in-polygon over CRS [lat, lng] pairs. No dependency.
 *
 * Crossing-number with a half-open latitude test, so a vertex is counted once
 * and the result matches the browser's own even-odd fill rule. Checked against
 * it rather than assumed: sampling the live canvas at 4 px steps, this agrees
 * with what Leaflet actually painted on 99.70% of samples, the residual being
 * antialiased boundary pixels.
 */
function pointInPolygon(poly: [number, number][], lat: number, lng: number): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const yi = poly[i][0], xi = poly[i][1];
    const yj = poly[j][0], xj = poly[j][1];
    if ((yi > lat) !== (yj > lat) && lng < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

/** The three measured tiers, in decreasing order of evidence. */
export type Coverage = 'amplitude' | 'swath' | 'outside';

const COVERAGE_RANK: Record<Coverage, number> = { amplitude: 0, swath: 1, outside: 2 };

/** Which tier a CRS position falls in. */
function coverageAt(geom: MapGeometry, lat: number, lng: number): Coverage {
  // No measured ring at all (degraded manifest): there is nothing to classify
  // against, so give the permissive answer and let the degraded banner carry the
  // caveat, rather than hollowing out every vector on the map for the wrong reason.
  if (geom.ring.length <= 2) return 'amplitude';
  if (pointInPolygon(geom.ring, lat, lng)) return 'amplitude';
  if (geom.swathRing.length > 2 && pointInPolygon(geom.swathRing, lat, lng)) return 'swath';
  return 'outside';
}

/**
 * The one sentence every out-of-coverage vector carries. Verbatim, because the
 * point is to name the file that has to change, not to soften it.
 */
const COVERAGE_NOTE =
  'Outside DFSAR radar coverage. This position is a fixed grid offset, not a '
  + 'terrain-search result — see module_e_landing.py.';

/* ─────────────────── out-of-coverage styling (v8 §2) ─────────────────── */

/**
 * The colour a vector takes when it tests OUTSIDE the measured amplitude ribbon.
 *
 * v7 styled these as { weight: 1, opacity: 0.35, fill: false }, which is how 5 of
 * 5 landing sites and ~95% of every rover route became nearly invisible — the
 * exact objects this screen exists to show. Amber at full weight says the same
 * thing without deleting the deliverable: it is legible, it is obviously not the
 * in-coverage colour, and COVERAGE_NOTE names the file that has to change.
 *
 * #f2c14e is the app's existing --mc-warn, hardcoded here because Leaflet paths
 * take a colour string, not a CSS variable.
 */
const OUT_OF_COVERAGE = '#f2c14e';

/* ──────────────────────────── raster attachment ──────────────────────────── */

/**
 * Attach one layer as an L.ImageOverlay, preview first.
 *
 * The ~40 KB preview paints almost immediately; the full lossless image is
 * preloaded in parallel and swapped in on its own `load` event, by which point
 * it is already in the browser cache so setUrl repaints without a flicker.
 * That is the progressive feel a pyramid gave, without the pyramid.
 */
function attachRaster(
  map: L.Map,
  entry: LayerManifestEntry,
  geom: MapGeometry,
  opts: { pane: string; opacity: number; className: string },
  onFullLoaded?: () => void,
): L.ImageOverlay {
  const overlay = L.imageOverlay(`${LAYERS_BASE}/${entry.preview}`, geom.bounds, {
    pane: opts.pane,
    opacity: opts.opacity,
    interactive: false,
    className: opts.className,
    alt: `${entry.label} — ${entry.provenance}`,
  }).addTo(map);

  const full = new Image();
  full.decoding = 'async';
  full.onload = () => {
    if (map.hasLayer(overlay)) overlay.setUrl(`${LAYERS_BASE}/${entry.file}`);
    onFullLoaded?.();
  };
  full.onerror = () => {
    console.error(`[MissionMap] failed to load ${LAYERS_BASE}/${entry.file}`);
    onFullLoaded?.();
  };
  full.src = `${LAYERS_BASE}/${entry.file}`;
  return overlay;
}

/** Rover route strategy → line style. */
const ROUTE_STYLE: Record<string, { color: string; weight: number; dash?: string }> = {
  Shortest: { color: '#f2c14e', weight: 2.5, dash: '6 5' },
  Safest: { color: '#6ee7a8', weight: 2.5 },
  'Science-Aware': { color: '#4fd1e6', weight: 3.5 },
};

/** Backend grid (0–100) → CRS.Simple [lat(py), lng(px)] over the real extent. */
const gridToPixel = (geom: MapGeometry, gx: number, gy: number): [number, number] => [
  geom.boundH - (gy / 100) * geom.boundH,
  (gx / 100) * geom.boundW,
];

/**
 * The frame's projection, lifted verbatim from layers.json.geodetic_frame.
 *
 * This is a port of `sar_geometry.SarFrame`, not a new derivation: the same
 * closed form, the same PixelIsArea half-pixel convention, the same parameters.
 * The backend validated that transform against ISRO's 937,296-node geolocation
 * grid at a corner residual of 13.2 mm, so the residual of THIS function is
 * that number plus IEEE-754 double rounding — there is no additional modelling
 * error to state, because there is no additional model.
 */
interface FrameProjection {
  radiusM: number;
  lonOriginDeg: number;
  falseEastingM: number;
  falseNorthingM: number;
  lines: number;
  samples: number;
  pixelXM: number;
  pixelYM: number;
  tiepointEM: number;
  tiepointNM: number;
  /** 0.5 for PixelIsArea — the tiepoint names the CORNER of pixel (0,0). */
  centreOffset: number;
}

function projectionFrom(m: LayersManifest): FrameProjection | null {
  const g = m.geodetic_frame;
  if (!g) return null;
  // Refuse anything but the south polar aspect, exactly as SarFrame._check_south
  // does. Guessing at another projection would put every marker somewhere
  // plausible and wrong.
  if (Math.abs(g.crs.latitude_of_origin_deg + 90) > 1e-6) {
    console.error(
      `[MissionMap] layers.json declares latitude_of_origin ${g.crs.latitude_of_origin_deg}; ` +
      'only the south polar aspect is implemented. Coordinates will be withheld.',
    );
    return null;
  }
  return {
    radiusM: g.crs.body_radius_m,
    lonOriginDeg: g.crs.central_meridian_deg,
    falseEastingM: g.crs.false_easting_m,
    falseNorthingM: g.crs.false_northing_m,
    lines: g.raster.lines,
    samples: g.raster.samples,
    pixelXM: g.raster.pixel_size_m.x,
    pixelYM: g.raster.pixel_size_m.y,
    tiepointEM: g.raster.tiepoint_xy_m.easting,
    tiepointNM: g.raster.tiepoint_xy_m.northing,
    centreOffset: g.raster.raster_type === 'PixelIsArea' ? 0.5 : 0.0,
  };
}

/** Fractional raster (line, sample) -> selenodetic lat/lon. Exact. */
function pixelToLatLon(p: FrameProjection, line: number, sample: number): { lat: number; lon: number } {
  const x = p.tiepointEM + (sample + p.centreOffset) * p.pixelXM - p.falseEastingM;
  const y = p.tiepointNM - (line + p.centreOffset) * p.pixelYM - p.falseNorthingM;
  const rho = Math.hypot(x, y);
  const lat = (2 * Math.atan(rho / (2 * p.radiusM)) - Math.PI / 2) * (180 / Math.PI);
  const lonRaw = Math.atan2(x, y) * (180 / Math.PI) + p.lonOriginDeg;
  return { lat, lon: ((lonRaw + 180) % 360 + 360) % 360 - 180 };
}

/**
 * The 0-100 backend grid -> lat/lon, through the same mapping the backend's
 * `SarFrame.grid_to_latlon` uses (gy/grid_max * (lines - 1)), so a site plotted
 * here and the same site's lat/lon in the payload agree by construction rather
 * than by coincidence.
 */
function frameLatLon(geom: MapGeometry, gx: number, gy: number): { lat: number; lon: number } | null {
  const p = geom.proj;
  if (!p) return null;
  return pixelToLatLon(p, (gy / 100) * (p.lines - 1), (gx / 100) * (p.samples - 1));
}

export interface MissionMapHandle {
  zoomIn: () => void;
  zoomOut: () => void;
  reset: () => void;
}

interface Props {
  /**
   * 1D · NULLABLE. The rasters, panes, graticule, scale bar, footprint rings
   * and coordinate readout are all derived from layers.json and need no
   * backend, so the map mounts and paints without this. Only the VECTORS —
   * landing-site markers, rover routes, the target marker — need it, and each
   * of those effects returns early when it is null. Nothing is substituted.
   */
  mission: MissionState | null;
  activeLayer: string;
  /** Opacity of the ACTIVE SCIENCE LAYER over the hillshade base, 0..1.
   *  Normal alpha compositing, never mix-blend-mode: M5 established that blend
   *  modes destroy the CPR ribbon, which covers 15.6 % of the raster and came
   *  out a barely-tinted grey smear. */
  scienceOpacity: number;
  showLandingSites: boolean;
  /** Phase 3 sites, searched over all 14.9 M native 25 m pixels. When present
   *  these REPLACE the API's hardcoded grid offsets: those were asserted on a
   *  100 x 100 grid, located to +/-500 m, and all five fell outside the measured
   *  amplitude ribbon. Null means no search has been run on this host. */
  searchedSites: SearchedSite[] | null;
  activeRoverStrategies: string[];
  selectedLandingSite: CandidateLandingSite | null;
  onSelectLandingSite: (s: CandidateLandingSite) => void;
  onCoords: (text: string) => void;
  onZoom: (z: number) => void;
}

export const MissionMap = forwardRef<MissionMapHandle, Props>(function MissionMap(
  { mission, activeLayer, scienceOpacity, showLandingSites, searchedSites, activeRoverStrategies, selectedLandingSite, onSelectLandingSite, onCoords, onZoom },
  ref,
) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const geomRef = useRef<MapGeometry | null>(null);
  const baseRef = useRef<L.ImageOverlay | null>(null);
  const overlayRef = useRef<L.Layer | null>(null);
  const sitesRef = useRef<L.LayerGroup | null>(null);
  const routesRef = useRef<L.LayerGroup | null>(null);
  const targetRef = useRef<L.CircleMarker | null>(null);
  const gridRef = useRef<L.LayerGroup | null>(null);
  const [ready, setReady] = useState(false);

  const crater = mission?.selected_crater ?? null;
  // The map is built asynchronously now (it waits for layers.json), so the
  // mousemove handler reads the crater through a ref instead of closing over
  // whichever one happened to be current when the effect ran.
  const craterRef = useRef(crater);
  craterRef.current = crater;

  useImperativeHandle(ref, () => ({
    zoomIn: () => mapRef.current?.zoomIn(),
    zoomOut: () => mapRef.current?.zoomOut(),
    // Reset returns to the 40 km home window, NOT the full extent. Flying to
    // geom.bounds put the reviewer back in a 1:2.93 letterbox where the craters
    // and the traverse were a hairline — which made the button that is supposed to
    // rescue a lost user the fastest way to lose them.
    reset: () => {
      const map = mapRef.current;
      const geom = geomRef.current;
      if (map && geom) map.flyToBounds(geom.homeBounds, { duration: 0.6 });
    },
  }), []);

  // ── init map once, after the manifest lands ────────────────────
  useEffect(() => {
    let cancelled = false;
    let teardown: (() => void) | undefined;

    loadManifest().then((mf) => {
      if (cancelled || !containerRef.current || mapRef.current) return;
      const geom = buildGeometry(mf);
      geomRef.current = geom;
      RESOLUTION = geom.degraded
        ? null
        : { nativeZoom: geom.nativeZoom, metresPerNativePx: geom.metresPerNativePx };
      teardown = buildMap(geom);
      setReady(true);
    });

    return () => { cancelled = true; teardown?.(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * Build the Leaflet map for a manifest-derived geometry. Returns its teardown.
   * Declared as a hoisted function so the init effect above can call it before
   * this point in the file.
   */
  function buildMap(geom: MapGeometry): () => void {
    const wrap = containerRef.current!.parentElement!;
    const map = L.map(containerRef.current!, {
      crs: L.CRS.Simple,
      center: geom.ribbonCentre,
      // Provisional view only. The real opening view is the fitBounds() below,
      // which needs a live map to measure the panel — but a Leaflet map has to be
      // constructed with SOME view, and constructing it already centred on the
      // ribbon means the fit is a scale change rather than a pan across 165 km.
      zoom: geom.nativeZoom,
      minZoom: 0,
      // Two doublings past native is enough to inspect single 25 m pixels
      // without pretending there is more in the file.
      maxZoom: geom.nativeZoom + 2,
      zoomControl: false,
      attributionControl: false,
      maxBounds: geom.bounds,
      maxBoundsViscosity: 1.0,
      zoomSnap: 0.5,
      fadeAnimation: true,
    });
    mapRef.current = map;
    // Zoom-out floor. The smallest useful zoom is the one that just fits the
    // whole 56.45 x 165.45 km frame in this panel — past that the swath shrinks
    // into a postage stamp surrounded by dead grey, which reads as "the data
    // ran out" rather than "you zoomed out".
    //
    // getBoundsZoom(bounds, false) means "largest zoom at which bounds fit
    // ENTIRELY inside the view" (inside=false is Leaflet's fit-the-whole-thing
    // sense, not its cover-the-view sense). It is measured from the live panel,
    // so it is not a constant and is never written down as a literal: a narrow
    // panel legitimately needs a smaller floor to hold the same 165 km. No
    // Math.max(0, ...) guard either — flooring at 0 would stop a panel narrower
    // than 256 CSS px from ever showing the whole frame, which is the one thing
    // this floor exists to keep reachable.
    //
    // maxBounds + maxBoundsViscosity: 1.0 (constructor, above) do the matching
    // job for panning; together they mean the frame is the world.
    // DO NOT use map.getBoundsZoom() here. It respects `zoomSnap` (0.5 above)
    // and FLOORS its answer to a snap increment, so a true fit of 2.0795 comes
    // back as 2.0 and the floor is set one snap step too far out. Measured on
    // a 1082x467 panel: frame 1024 px wide in a 1082 px viewport, 94.6 % fill.
    // The size of the gap depends on where the true fit falls between snap
    // steps, and the worst case is a fit just under a boundary -- 2^-0.5 =
    // 70.7 % of the width and half the area, which is the "postage stamp in a
    // grey field" this floor exists to prevent. That size dependence is also
    // why the bug reads as intermittent and why it survived a previous fix.
    //
    // So compute the fit directly, through Leaflet's own projection at zoom 0
    // (CRS-agnostic -- no assumption that 1 CRS unit is 1 px) and take the
    // exact log2. Never snapped, never a literal, and recomputed on resize.
    // geom.bounds is an L.LatLngBoundsLiteral — a PLAIN ARRAY, not an
    // L.LatLngBounds — so it has no getNorthWest(). map.getBoundsZoom() hid that
    // by calling toLatLngBounds() internally; computing the fit by hand does
    // not, and the missing conversion threw a TypeError that aborted this whole
    // effect, leaving minZoom at its constructor value of 0. That is far worse
    // than the snapping bug being fixed here: at zoom 0 the frame is 256 px wide
    // in a 1081 px panel, 23.7 % fill.
    const fitBoundsLL = L.latLngBounds(geom.bounds);
    const fitZoomOut = () => {
      const nw = map.project(fitBoundsLL.getNorthWest(), 0);
      const se = map.project(fitBoundsLL.getSouthEast(), 0);
      const w = Math.abs(se.x - nw.x);
      const h = Math.abs(se.y - nw.y);
      const size = map.getSize();
      if (!(w > 0 && h > 0 && size.x > 0 && size.y > 0)) return map.getMinZoom();
      return Math.log2(Math.min(size.x / w, size.y / h));
    };
    const clampZoomOut = () => {
      map.setMinZoom(fitZoomOut());
    };
    clampZoomOut();
    // The panel resizes with the window and with the side rails opening and
    // closing, and each of those changes the fit zoom. Recompute rather than
    // leaving the floor set for whatever size the panel happened to be at mount.
    // If the live view is already below the new floor, Leaflet's own setMinZoom
    // pulls it back up.
    const panelObserver = new ResizeObserver(() => {
      map.invalidateSize({ animate: false });
      clampZoomOut();
    });
    panelObserver.observe(containerRef.current!);
    // Opening view: the 40 km home window. animate: false because nothing has
    // painted yet, and because under CDP document.hidden is true, rAF never fires
    // and an animated move would simply never arrive.
    map.fitBounds(geom.homeBounds, { animate: false });

    // Dedicated panes: terrain underneath, science on top.
    //
    // M5 — the science pane is NOT blended. It used to carry
    // mix-blend-mode: soft-light so the hillshade relief showed through, but
    // measured side by side that blend destroyed the very signal this app
    // exists to show: the CPR ribbon, on 15.6% of the raster, came out a
    // barely-tinted grey smear. Straight alpha compositing is used instead,
    // with terrain-derived overlays held slightly below full opacity so some
    // relief still reads through them.
    map.createPane('mc-terrain');
    map.getPane('mc-terrain')!.style.zIndex = '100';
    // v8 removed the mc-void pane at zIndex 250. Nothing is drawn over the ground
    // any more, so the pane had one polygon-shaped job and no polygons left.
    map.createPane('mc-science');
    map.getPane('mc-science')!.style.zIndex = '350';
    map.createPane('mc-frame');
    map.getPane('mc-frame')!.style.zIndex = '400';

    // Terrain base. Never flashes black: the preview paints first and the wrap
    // shimmers only while the full image is still in flight.
    const baseEntry = geom.byId['hillshade'];
    if (baseEntry) {
      wrap.classList.add('mc-map--tiles-loading');
      baseRef.current = attachRaster(
        map, baseEntry, geom,
        { pane: 'mc-terrain', opacity: 1, className: 'mc-raster mc-raster--base' },
        () => wrap.classList.remove('mc-map--tiles-loading'),
      );
    }

    // Two rings, because one mask was conflating two different things.
    //
    //   swathRing — ISRO's own sri_ma mask: where the beam was POINTED. 35.6% of
    //               the frame, ~19.3 km wide, closing to 2.7% against the PDS4
    //               label's nominal 19,650 m swath.
    //   ring      — where amplitude actually came back: 15.6%, ~8.8 km wide.
    //
    // 56% of the pointed swath carries literal integer zero amplitude, so the
    // radar rasters are transparent there and no colour is invented.
    //
    // v8 — the two regions are marked by OUTLINE ONLY.
    //
    // v6 filled them at 0.82 / 0.5 alpha (measured 0.041 / 0.236 of base
    // luminance) and v7 at a hatch plus 0.14 / 0.045 (measured 0.747 / 0.900).
    // Both said "no data here" about ground that has a DEM under it, and both cost
    // a pane, three polygons and a <pattern> to say something a sentence says
    // better. The relief is now read at full luminance and the claim moves into
    // the two tooltips, where it can name the provenance string it came from.
    const hasSwath = geom.swathRing.length > 2;
    if (geom.ring.length > 2) {
      if (hasSwath) {
        L.polygon(geom.swathRing, {
          pane: 'mc-frame', fill: false, color: '#8aa0b4', weight: 1, opacity: 0.55,
        }).addTo(map).bindTooltip(
          `Chandrayaan-2 DFSAR beam footprint — ISRO sri_ma mask, ` +
          `${(geom.swathFraction * 100).toFixed(1)}% of this frame, ` +
          `${geom.swathKm.toFixed(1)} km wide against a nominal ` +
          `${geom.swathNominalKm.toFixed(2)} km swath. Only ` +
          `${(geom.amplitudeOfSwath * 100).toFixed(0)}% of it returned amplitude, so no ` +
          `radar value is drawn in the rest — that band is observed but empty, not dry.`,
          { sticky: true },
        );
      }

      // Driven off layers.json provenance, not a constant, so the day
      // render_layers.py writes a measured LOLA base this sentence changes itself.
      const baseNote = geom.placeholderBase
        ? `Terrain outside it is a PLACEHOLDER DEM (layers.json provenance: `
          + `"${geom.baseProvenance}") — the relief shape is not measured topography.`
        : `Terrain outside it is measured topography (layers.json provenance: `
          + `"${geom.baseProvenance}") carrying no radar measurement.`;

      L.polygon(geom.ring, {
        pane: 'mc-frame', fill: false, color: '#4fd1e6', weight: 1.2, opacity: 0.75,
        dashArray: '5 6',
      }).addTo(map).bindTooltip(
        `Chandrayaan-2 DFSAR amplitude footprint — 2020-08-08 pass, ` +
        `${(geom.validFraction * 100).toFixed(1)}% of this frame, ` +
        `${geom.ribbonKm.toFixed(1)} km wide. This is the only area with radar ` +
        `measurements. ${baseNote}`,
        { sticky: true },
      );
    }

    // If layers.json is missing the map must not look merely empty — it must
    // say why, or the next person debugs the wrong thing.
    let degradedEl: HTMLElement | null = null;
    if (geom.degraded) {
      degradedEl = L.DomUtil.create('div', 'mc-map-overlay mc-map-degraded', wrap);
      degradedEl.textContent = 'LAYER IMAGERY UNAVAILABLE — /layers/layers.json did not load. '
        + 'Run: python backend/scripts/render_layers.py';
    }

    /*
     * v8 removed the coverage key panel that used to sit here.
     *
     * It was not asked for, it occupied the last free corner of the map, and its
     * own header claimed "MEASURED FROM THE PRODUCT" above rows that then printed a
     * target and waypoint counts derived from whichever backend answered — DEMO
     * included. Every number it carried already appears somewhere it cannot drift:
     * the three coverage fractions are in the two ring tooltips and in the analysis
     * rail ("1,460.68 km² of measured radar over a 9,339.65 km² frame at 25 m/px"),
     * and the in/out-of-coverage counts are in the console table at the bottom of
     * this file. A second copy on the canvas bought nothing and cost the corner.
     */

    // Faint engineering graticule. 5 divisions across-track x 15 along-track
    // keeps the cells roughly square on a 2.93 : 1 strip.
    const grid = L.layerGroup().addTo(map);
    gridRef.current = grid;
    const style: L.PolylineOptions = {
      color: 'rgba(79,209,230,0.14)', weight: 1, dashArray: '3 7', interactive: false,
    };
    for (let i = 0; i <= 5; i++) {
      const y = (i / 5) * geom.boundH;
      L.polyline([[y, 0], [y, geom.boundW]], style).addTo(grid);
    }
    for (let i = 0; i <= 15; i++) {
      const x = (i / 15) * geom.boundW;
      L.polyline([[0, x], [geom.boundH, x]], style).addTo(grid);
    }

    sitesRef.current = L.layerGroup().addTo(map);
    routesRef.current = L.layerGroup().addTo(map);

    // Dynamic scale bar. CRS.Simple lat/lng ARE map units, and one unit is
    // exactly metres_per_unit on the ground because the extent is cut at the
    // product's own 25 m grid — a measured bar, not a guess.
    const kmPerUnit = geom.metresPerUnit / 1000;
    const scaleEl = L.DomUtil.create('div', 'mc-map-overlay mc-map-scale', wrap);
    scaleEl.innerHTML = `<span class="mc-scale-label"></span><div class="mc-scale-bar"></div>`;
    const updateScale = () => {
      if (!kmPerUnit) return;
      const cx = map.getSize().x / 2;
      const cy = map.getSize().y / 2;
      const a = map.containerPointToLatLng([cx, cy]);
      const b = map.containerPointToLatLng([cx + 100, cy]);
      const kmPer100px = Math.abs(b.lng - a.lng) * kmPerUnit;
      if (!isFinite(kmPer100px) || kmPer100px <= 0) return;
      const pow = Math.pow(10, Math.floor(Math.log10(kmPer100px)));
      const niceKm = (kmPer100px / pow >= 5 ? 5 : kmPer100px / pow >= 2 ? 2 : 1) * pow;
      const px = (niceKm / kmPer100px) * 100;
      (scaleEl.querySelector('.mc-scale-bar') as HTMLElement).style.width = `${px}px`;
      (scaleEl.querySelector('.mc-scale-label') as HTMLElement).textContent =
        niceKm >= 1 ? `${niceKm} km` : `${(niceKm * 1000).toFixed(0)} m`;
    };

    // Past native zoom the browser would interpolate 25 m pixels into a smooth
    // blur that implies detail the file does not have. Square pixels instead.
    const updatePixelated = () => {
      wrap.classList.toggle('mc-map--pixelated', map.getZoom() > geom.nativeZoom);
    };

    onZoom(map.getZoom());
    updateScale();
    updatePixelated();
    map.on('zoomend moveend', updateScale);
    map.on('zoomend', () => { onZoom(map.getZoom()); updatePixelated(); });
    map.on('mousemove', (e: L.LeafletMouseEvent) => {
      const gx = Math.round((e.latlng.lng / geom.boundW) * 100);
      const gy = Math.round(((geom.boundH - e.latlng.lat) / geom.boundH) * 100);
      if (gx < 0 || gx > 100 || gy < 0 || gy > 100) return;
      const ll = frameLatLon(geom, gx, gy);
      onCoords(
        ll
          ? `GRID ${gx},${gy}  ·  ${ll.lat.toFixed(4)}° ${ll.lon.toFixed(4)}°`
          : `GRID ${gx},${gy}  ·  coordinates unavailable (layers.json carries no geodetic_frame)`,
      );
    });

    return () => {
      panelObserver.disconnect();
      map.remove();
      scaleEl.remove();
      degradedEl?.remove();
      wrap.classList.remove('mc-map--tiles-loading', 'mc-map--pixelated');
      mapRef.current = null;
      baseRef.current = null;
      overlayRef.current = null;
    };
  }

  // ── science overlay follows activeLayer ────────────────────────
  //
  // Two sources, and they are not the same kind of thing:
  //   * rendered layers come from the manifest as one image each, already
  //     stretched, colourised and alpha-masked by render_layers.py;
  //   * `ml_likelihood` has no rendered file — it is a base64 PNG of the SQUARE
  //     2048² analysis grid, produced per-request by the backend. Drawing it on
  //     the 2.93 : 1 bounds un-squashes it back to true geometry.
  //
  // Opacity is provenance-driven (M5, retagged in V10): a `measured` layer is
  // drawn at full strength, everything else sits a little under so the hillshade
  // beneath still contributes relief. The set that qualifies changed when the
  // placeholder DEM was replaced by LOLA — `dem_elevation` and `hazard_map` are
  // now measured topography and so render at 1.0, where they used to be dimmed
  // as synthetic. What still sits at 0.9 is the modelled pair: the illumination
  // brightness proxy and P(ice).
  useEffect(() => {
    const map = mapRef.current;
    const geom = geomRef.current;
    if (!map || !geom) return;
    if (overlayRef.current) { map.removeLayer(overlayRef.current); overlayRef.current = null; }
    if (activeLayer === 'hillshade') return;   // already the base

    // COMPOSITED OVER THE HILLSHADE, not drawn instead of it. This used to be
    // 1.0 for anything marked `measured`, which meant every terrain and radar
    // layer completely hid the relief underneath and each one read as a flat
    // field of colour with no landform in it. The base is always mounted in the
    // mc-terrain pane; the only thing that stopped it contributing was this
    // number. It is now user-controlled, and the default is measured against the
    // composite rather than guessed -- see docs/composite_contrast.json.
    const entry = geom.byId[activeLayer];
    const opacity = Math.max(0, Math.min(1, scienceOpacity));

    if (entry) {
      overlayRef.current = attachRaster(map, entry, geom, {
        pane: 'mc-science', opacity, className: 'mc-raster mc-raster--science',
      });
      return;
    }
    // NO BASE64 FALLBACK. This used to fall back to mission.raster_layers[id]
    // — a PNG rendered by the on-demand backend on a square grid and stretched
    // onto this frame's 2.93:1 bounds. Every layer offered in the control now
    // has a manifest entry, so reaching this line means the manifest and
    // config.ts disagree, which is a build error rather than something to paper
    // over with a differently-projected image.
    if (import.meta.env.DEV) {
      console.warn(
        `[MissionMap] layer "${activeLayer}" has no entry in layers.json. ` +
        'Nothing is drawn: a backend-rendered raster would be on the wrong grid. ' +
        'Run: python backend/scripts/render_layers.py',
      );
    }
  }, [activeLayer, ready, scienceOpacity]);

  // ── smooth fly-to when the crater / target changes ─────────────
  //
  // v7 §3 rule 5 — the fly-to is GATED on measurement. mission.target_coordinates
  // is the grid centre {x: 50, y: 50}, hardcoded in module_e_landing.py, and the
  // grid centre of this frame is not inside the amplitude ribbon. Flying there on
  // open made the app's first move a zoom into ground the radar never saw. The
  // marker is still drawn — hiding it would hide the defect — but the camera goes
  // to the measured ribbon centre instead, and the map says why.
  useEffect(() => {
    const map = mapRef.current;
    const geom = geomRef.current;
    if (!map || !geom) return;
    if (targetRef.current) { map.removeLayer(targetRef.current); targetRef.current = null; }

    if (!mission || !crater) return;
    const t = mission.target_coordinates;
    const [py, px] = gridToPixel(geom, t.x, t.y);
    const ll = frameLatLon(geom, t.x, t.y);
    const cov = coverageAt(geom, py, px);
    const measured = cov === 'amplitude';

    // v8 — outside the ribbon the marker goes AMBER at full weight, not faint and
    // hollow. A caveat that erases the object being caveated is not a caveat.
    const style: L.CircleMarkerOptions = measured
      ? { radius: 9, color: '#4fd1e6', weight: 2.5, fillColor: 'rgba(79,209,230,0.25)', fillOpacity: 1 }
      : cov === 'swath'
        ? { radius: 9, color: '#4fd1e6', weight: 2.5, fillColor: 'rgba(79,209,230,0.25)',
            fillOpacity: 1, dashArray: '3 3', opacity: 0.6 }
        : { radius: 9, color: OUT_OF_COVERAGE, weight: 2.5, dashArray: '4 3',
            fillColor: 'rgba(242,193,78,0.18)', fillOpacity: 1 };

    const marker = L.circleMarker([py, px], style).addTo(map).bindPopup(
      `<div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:#4fd1e6;min-width:160px">
        <strong>CANDIDATE ICE TARGET</strong><br/>${ll
          ? `Lat ${ll.lat.toFixed(4)}°<br/>Lon ${ll.lon.toFixed(4)}°`
          : 'Coordinates unavailable'}<br/>
        <span style="color:${measured ? '#7f93a5' : '#f2c14e'}">${measured
          ? 'Chandrayaan-2 DFSAR CPR peak'
          : `GRID ${t.x},${t.y} — hardcoded, ${cov === 'swath'
              ? 'inside the pointed swath but no amplitude returned'
              : 'outside DFSAR coverage entirely'}`}</span></div>`,
    );
    if (!measured) marker.bindTooltip(COVERAGE_NOTE, { direction: 'top', offset: [0, -10] });
    targetRef.current = marker;

    // Fly to the target when it is measured; otherwise hold the home window rather
    // than zooming into ground the radar never saw. Zoom is floored at the home
    // window's own zoom so this can only ever go closer, never back out to a strip.
    const dest: [number, number] = measured ? [py, px] : geom.ribbonCentre;
    map.flyTo(dest, Math.max(map.getZoom(), map.getBoundsZoom(geom.homeBounds)), { duration: 0.7 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mission?.selected_crater?.id, mission?.target_coordinates?.x, mission?.target_coordinates?.y, ready]);

  // ── landing sites ──────────────────────────────────────────────
  //
  // v8 — every site is ray-cast against the measured amplitude ribbon and ISRO's
  // pointed swath, and RECOLOURED by the answer instead of being faded out of
  // existence. The five sites are hardcoded grid offsets in module_e_landing.py, so
  // the count in the console table is not decoration: it is the argument for
  // replacing that list with a real per-pixel suitability search.
  useEffect(() => {
    const group = sitesRef.current;
    const geom = geomRef.current;
    if (!group || !geom) return;
    group.clearLayers();
    // No mission, no sites. The group is left EMPTY rather than filled with
    // placeholder markers — an invented pin on a real map is worse than no pin.
    if (!mission) return;

    // Classified before the showLandingSites early-return: the count describes
    // the mission state, not what happens to be toggled on.
    const rows = mission.landing_sites.map((site) => {
      const [py, px] = gridToPixel(geom, site.grid_x, site.grid_y);
      return { site, py, px, cov: coverageAt(geom, py, px) };
    });
    const outside = rows.filter((r) => r.cov !== 'amplitude').length;

    if (rows.length) {
      console.info(
        `[MissionMap] landing-site coverage — ${outside}/${rows.length} outside the measured `
        + 'amplitude ribbon. Grid offsets are hardcoded in module_e_landing.py.',
      );
      console.table(rows.map((r) => ({
        site: r.site.site_id, rank: r.site.rank, recommended: r.site.is_recommended,
        grid: `${r.site.grid_x},${r.site.grid_y}`, coverage: r.cov,
      })));
    }

    if (!showLandingSites) return;

    // PHASE 3 SITES WIN. They were searched over every native 25 m pixel; the
    // API's are five hardcoded offsets on a 100 x 100 grid, located to +/-500 m,
    // and all five fell outside the measured amplitude ribbon. Drawing both
    // would put two different answers to one question on the same map.
    if (searchedSites && searchedSites.length) {
      const inRibbon: string[] = [];
      searchedSites.forEach((s2) => {
        const [py, px] = gridToPixel(geom, s2.grid.sample, s2.grid.line);
        const cov = coverageAt(geom, py, px);
        inRibbon.push(`#${s2.rank} ${cov}`);
        const suspect = /SUSPECT/i.test(s2.interpolation_check.verdict);
        const marker = L.circleMarker([py, px], {
          pane: 'mc-frame',
          radius: s2.rank === 1 ? 9 : 7,
          color: suspect ? '#f2c14e' : '#4fd1e6',
          weight: 2,
          fillColor: suspect ? '#f2c14e' : '#4fd1e6',
          fillOpacity: 0.35,
          className: 'mc-site mc-site--searched',
        });
        const crit = Object.entries(s2.criteria)
          .map(([k, c]) => `${c.passed ? '&#10003;' : '&#10007;'} ${k} `
            + `<b>${c.value}</b> ${c.comparison} ${c.threshold}`)
          .join('<br/>');
        marker.bindTooltip(
          `<b>Site ${s2.rank}</b> &nbsp; score ${s2.suitability_score.toFixed(4)}<br/>`
          + `${s2.lat_deg.toFixed(4)}&deg;, ${s2.lon_deg.toFixed(4)}&deg;<br/>`
          + `<hr style="opacity:.3;margin:.3rem 0"/>${crit}`
          + `<hr style="opacity:.3;margin:.3rem 0"/>`
          + `<b>PSR ${s2.ice_access.psr_distance_km.toFixed(2)} km</b> — `
          + `${s2.ice_access.means}<br/>`
          + `<hr style="opacity:.3;margin:.3rem 0"/>`
          + `<b>${suspect ? 'SUSPECT' : 'terrain OK'}</b>: plane-fit RMS `
          + `${s2.interpolation_check.plane_rms_m} m, `
          + `${s2.interpolation_check.ratio_to_reference_p05}&times; the frame`
          + ` reference &mdash; ${s2.interpolation_check.verdict}`,
          { direction: 'top', className: 'mc-tip', sticky: true, opacity: 1 },
        );
        marker.addTo(group);
      });
      console.info('[MissionMap] Phase 3 searched sites drawn (API sites suppressed): '
        + inRibbon.join(', '));
      return;
    }

    rows.forEach(({ site, py, px, cov }) => {
      const sel = selectedLandingSite?.site_id === site.site_id;
      const rec = site.is_recommended;
      const common = {
        radius: sel ? 10 : rec ? 8 : 6,
        weight: sel ? 3 : 2,
      };
      // Full weight and a filled body in every branch. v7 drew this last case as
      // { weight: 1, opacity: 0.35, fill: false }, which is how all five sites
      // became invisible — the amber says "not measured here" without doing that.
      const opts: L.CircleMarkerOptions = cov === 'amplitude'
        ? { ...common, color: rec ? '#4fd1e6' : '#7f93a5',
            fillColor: rec ? '#2b7c8c' : '#334155', fillOpacity: 0.9 }
        : cov === 'swath'
          ? { ...common, color: rec ? '#4fd1e6' : '#7f93a5',
              fillColor: rec ? '#2b7c8c' : '#334155', fillOpacity: 0.9,
              dashArray: '3 3', opacity: 0.75 }
          : { ...common, color: OUT_OF_COVERAGE, fillColor: '#6b5620',
              fillOpacity: 0.9, dashArray: '4 3' };
      const marker = L.circleMarker([py, px], opts).addTo(group);
      // A permanent tooltip is fine for a two-word label and not fine for a
      // sentence, so any site carrying the coverage note goes hover-only.
      marker.bindTooltip(
        cov === 'amplitude'
          ? `${rec ? '★ ' : ''}Site ${site.rank}`
          : `${rec ? '★ ' : ''}Site ${site.rank} · ${cov === 'swath'
              ? 'pointed, no return' : 'no radar coverage'}<br/>${COVERAGE_NOTE}`,
        { direction: 'top', offset: [0, -8], permanent: rec && cov === 'amplitude' },
      );
      marker.on('click', () => onSelectLandingSite(site));
    });
  }, [mission, showLandingSites, searchedSites, selectedLandingSite, onSelectLandingSite, ready]);

  // ── rover routes ───────────────────────────────────────────────
  //
  // A route is drawn in RUNS, each run styled by the weaker coverage of its two
  // endpoints, so a traverse cannot silently claim measured ground on its way to a
  // destination it did not measure. All three strategies start at a hardcoded site
  // offset and end at target_coordinates, so the per-route fraction in the console
  // table is the honest measure of how much of each traverse the radar actually saw.
  useEffect(() => {
    const group = routesRef.current;
    const geom = geomRef.current;
    if (!group || !geom) return;
    group.clearLayers();

    const rows: { strategy: string; n: number; amp: number; sw: number; out: number;
                  km: string; drawn: boolean }[] = [];

    Object.entries(ROUTE_STYLE).forEach(([strategy, s]) => {
      const route = mission?.rover_routes?.[strategy];
      if (!route?.path_found || !route.waypoints?.length) return;
      const pts = route.waypoints.map((wp) => gridToPixel(geom, wp.x, wp.y));
      const covs = pts.map(([py, px]) => coverageAt(geom, py, px));
      const drawn = activeRoverStrategies.includes(strategy);
      rows.push({
        strategy, n: covs.length,
        amp: covs.filter((c) => c === 'amplitude').length,
        sw: covs.filter((c) => c === 'swath').length,
        out: covs.filter((c) => c === 'outside').length,
        km: route.total_distance_km?.toFixed(1) ?? '?',
        drawn,
      });
      if (!drawn || pts.length < 2) return;

      const ampPct = (100 * covs.filter((c) => c === 'amplitude').length) / covs.length;
      const tip = `${strategy} · ${route.total_distance_km?.toFixed(1) ?? '?'} km`
        + `<br/>${ampPct.toFixed(0)}% of ${covs.length} waypoints inside the DFSAR ribbon`
        + (ampPct < 100 ? `<br/>${COVERAGE_NOTE}` : '');

      // A segment inherits the weaker of its two endpoints; consecutive segments
      // of equal coverage are merged so the line stays one stroke per run.
      const segCov: Coverage[] = [];
      for (let i = 0; i + 1 < covs.length; i++) {
        segCov.push(COVERAGE_RANK[covs[i]] >= COVERAGE_RANK[covs[i + 1]] ? covs[i] : covs[i + 1]);
      }
      let start = 0;
      for (let i = 0; i < segCov.length; i++) {
        if (i + 1 < segCov.length && segCov[i + 1] === segCov[i]) continue;
        const run = pts.slice(start, i + 2);
        const cov = segCov[i];
        // The Science-Aware halo is drawn only under measured runs. It is emphasis,
        // and there is nothing to emphasise about a line over unobserved ground.
        if (cov === 'amplitude' && strategy === 'Science-Aware') {
          // CLASSED, so the verifier can tell an emphasis underlay from a route.
          // It is drawn at opacity 0.15 on purpose — that is what a glow is —
          // and verify_v8_view.mjs's routes_visible check was reading it as an
          // invisible route and failing the gate on it every run. A gate that
          // cries wolf gets waved through, so the fix is to make the two
          // distinguishable rather than to lower the opacity floor.
          L.polyline(run, {
            color: s.color, weight: s.weight + 6, opacity: 0.15, lineJoin: 'round',
            className: 'mc-route-glow',
          }).addTo(group);
        }
        const style: L.PolylineOptions = cov === 'amplitude'
          ? { color: s.color, weight: s.weight, opacity: 0.95, dashArray: s.dash }
          : cov === 'swath'
            ? { color: s.color, weight: s.weight, opacity: 0.6, dashArray: '4 4' }
            // v8 — full weight in amber. v7 used { weight: 1, opacity: 0.35 } here,
            // and since every strategy ends at a target outside the ribbon, that
            // erased roughly 95% of every traverse the app exists to plan.
            : { color: OUT_OF_COVERAGE, weight: s.weight, opacity: 0.9, dashArray: '2 6' };
        L.polyline(run, { ...style, lineJoin: 'round', lineCap: 'round' })
          .addTo(group)
          .bindTooltip(tip, { sticky: true });
        start = i + 1;
      }
    });

    if (rows.length) {
      console.info('[MissionMap] rover waypoint coverage — all strategies terminate at '
        + 'target_coordinates (the hardcoded grid centre):');
      console.table(rows.map((r) => ({
        strategy: r.strategy, waypoints: r.n, km: r.km,
        in_amplitude_ribbon: `${r.amp} (${((100 * r.amp) / r.n).toFixed(1)}%)`,
        pointed_no_return: r.sw, never_observed: r.out, drawn: r.drawn,
      })));
    }
  }, [mission, activeRoverStrategies, ready]);

  return <div ref={containerRef} className="mc-map" />;
});

/* ═══════════════════════════════════════════════════════════════════════════
 * v8 — WHAT WAS REMOVED, AND THE MEASUREMENTS THAT JUSTIFY REMOVING IT
 * ═══════════════════════════════════════════════════════════════════════════
 *
 * Removed: the mc-void pane, its three fill polygons, ensureHatch() and the SVG
 * <pattern>, the flat-tint constants, the .mc-map-coverage key and its three
 * count slots, and the weight-1/opacity-0.35 styling of every out-of-coverage
 * vector. Kept: the two ring outlines and their tooltips, the coverage classifier,
 * and both console tables.
 *
 * The luminance history, all measured off the live canvas at zoom 4.0, centre
 * [45.09375, 128.71875], map 1167 x 705, tier from pointInPolygon() above:
 *
 *   tier                     % frame   v6 / base   v7 / base   v8 / base
 *   amplitude ribbon          29.96      0.9961      0.9996      1.0000
 *   pointed, no amplitude     38.08      0.2359      0.9102      1.0000
 *   never observed            31.96      0.0410      0.7472      1.0000
 *
 * v6 was the bug: 0.041 of base is RGB (33,36,41) on ground that has a DEM under
 * it, and darkness reads as absence. v7 fixed the luminance and was still the
 * wrong instrument — the fact being drawn ("this relief is not measured") is not
 * a place, it is a provenance claim, and it is now carried by the amplitude-ring
 * tooltip (built from layers.json provenance verbatim), the layer card, and the
 * analysis rail. Those can be read; a hatch can only be guessed at.
 *
 * Base filter, measured on hillshade.webp (6618 x 2258 = 14,943,444 px, 100 %
 * opaque, exactly neutral, max |R-B| = 0) by backend/scripts/hillshade_histogram.py:
 *
 *                                          mean   median  clip@255  added clip
 *   SOURCE, no filter                     149.68    156    2.010 %      —
 *   contrast(1.14) brightness(1.16)  v6   176.06    186    3.555 %   +1.545 pp
 *   contrast(1.04) brightness(1.02)  v7   153.45    160    2.223 %   +0.213 pp
 *   contrast(1.06) brightness(1.10)  v8      —       —        —      interpolated
 *
 * v8 sits between the two measured points, not past them: v7 was too dark for a
 * reviewer at arm's length and v6 clipped 1.5 pp of the sunlit crests. Two findings
 * the numbers force and that must survive any future retune: the literal
 * "<= 1 % clip at 255" bar is unreachable at any brightness >= 1.00 because the
 * SOURCE already clips 2.010 % from the global normalisation, so the measurable
 * form of the rule is ADDED clipping; and it is contrast(), not brightness(), that
 * crushes the crests — contrast(1.14) sends every v >= 239 to 1.0 BEFORE brightness
 * runs. Re-measure before moving it: python backend/scripts/hillshade_histogram.py
 *
 * Classifier vs. what the browser actually filled, before the fills were removed:
 * 99.76 % on-diagonal (8 mixed pixels, all on antialiased boundaries); headless
 * re-measurement in frontend/scripts/verify_map.mjs agreed at 99.65 % over 51,392
 * samples. The classifier is unchanged in v8 — only what it feeds has changed —
 * so those numbers still describe coverageAt().
 *
 * Opening view. geom.homeBounds is a 40 km square on the ribbon centroid, and both
 * the constructor and reset() use it. The full extent is 56.45 x 165.45 km at
 * 1:2.93; fitting that into a 1167 x 705 panel gives ~142 m/px and puts the whole
 * deliverable — five candidate sites, three traverses, the ice target — inside a
 * band a few dozen pixels tall. The 40 km window is ~40 m/px on the same panel,
 * against 25 m/px in the file, so there is real detail left to zoom into.
 *
 * Coverage counts, computed at runtime, now console-only:
 *   5 of 5 landing sites outside the measured amplitude ribbon (hardcoded offsets)
 *   ~5 % of 36-37 waypoints inside it, all three strategies
 *
 * Those counts move with whichever backend answered, and that is worth recording.
 * frontend/.env.local used to set VITE_API_BASE to the deployed Render host, which
 * has no SAR files on it (.gitignore excludes /data/ and *.tif), accepts
 * ?data_mode=REAL, discards it, and returns HTTP 200 with data_mode "DEMO" — the
 * reason the topbar read STUDIO · SIMULATED. That line is now commented out, so
 * api.ts falls back to http://127.0.0.1:8000 and the app talks to the backend that
 * can actually read data/pradan/**. Render returns target {58,46} / 37 waypoints;
 * the local backend returns data_mode REAL, target {50,50} / 36 waypoints, {50,50}
 * being the empty-candidate-mask fallback at mission_service.py:264-278. The tier
 * luminances and the geometry agreement above are unaffected either way — they are
 * measured off frontend/public/layers/*.webp and layers.json, which the dev server
 * serves locally.
 *
 * SUPERSEDED IN V10 — kept because the reasoning was right and the conclusion is
 * what changed. This block used to read "STILL NOT REAL, and no amount of styling
 * will change it: hillshade, dem_elevation, hazard_map and illumination all carry
 * provenance 'synthetic-terrain-derived' and are derived from an analytic
 * Gaussians-plus-sinusoids DEM ... 'zoom in and read the terrain' is blocked on
 * ingesting a real LOLA polar DEM, not on this file."
 *
 * That ingest has now happened. data/pradan/lola/ holds LDEM_80S_80M.IMG and a
 * verified 25 m crop, and data/pradan/native/dem_native.tif is
 * bit-identical to it (max|diff| 0.000000 m, r = 1.0, asserted on every build by
 * build_analysis.assert_dem_is_lola — the filename is the only synthetic thing
 * left about it). So hillshade, dem_elevation and hazard_map are now measured
 * topography at 80 m native posts carried on the 25 m grid.
 *
 * Two claims from the old block DO still stand. illumination remains modelled: it
 * is hillshade(1.5°) × elev_norm^1.3 with no horizon term, so it is a brightness
 * proxy and not solar geometry. And pradan_pipeline.py:221-225 still writes the
 * *_ohrc_pan.tif "optical" files as a hillshade of the DEM, so there is no real
 * optical product and boulder risk stays UNMEASURED rather than zero.
 * ═══════════════════════════════════════════════════════════════════════════ */

