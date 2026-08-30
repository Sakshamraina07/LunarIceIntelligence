/**
 * lunarBasemap.ts
 * Adapter/service layer for lunar surface imagery used by the 3D Moon.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * CHANDRAYAAN-2 / ISRO DATA INTEGRATION — INVESTIGATION SUMMARY (2026-08-30)
 * ─────────────────────────────────────────────────────────────────────────────
 * The landing page was required to attempt LIVE use of official ISRO /
 * Chandrayaan-2 lunar map data rather than fabricating a texture. Findings:
 *
 * 1. ISRO PRADAN (https://pradan.issdc.gov.in) is the official Chandrayaan-2
 *    archive (DFSAR radar, OHRC imagery, TMC-2 DEM). It requires account
 *    registration/login and serves PDS4 *bundle downloads*. It exposes NO
 *    public, CORS-enabled, real-time tile / WMS / WMTS API that a browser can
 *    call directly. => A live in-browser Chandrayaan-2 feed from ISRO is NOT
 *    currently possible without a server-side proxy + credentials.
 *
 * 2. This repository already INGESTED real Chandrayaan-2 DFSAR data (observation
 *    2020-08-08, Faustini region, product ch2_sar_ncxl_20200808...) into
 *    data/pradan/ and pre-processed it into XYZ tile pyramids served by the
 *    FastAPI backend at  {backend}/tiles/{crater}/{layer}/{z}/{x}/{y}.png.
 *    Those tiles are REAL (offline-processed) Chandrayaan-2-derived layers.
 *
 * 3. Public, CORS-enabled LIVE lunar basemaps that DO work in-browser (verified
 *    with an Origin header): NASA Moon Trek (LRO WAC global mosaic) and USGS
 *    planetarymaps WMS. These are LRO products (not Chandrayaan-2) but provide
 *    a scientifically real global context layer.
 *
 * DECISION: the 3D hero renders from a REAL local lunar DEM (public/lunar-dem.png)
 * for credible crater relief, and this service exposes swappable providers so the
 * NASA Moon Trek live imagery or the backend Chandrayaan-2 tiles can be dropped
 * in without touching the scene code. Nothing here fakes a real-time ISRO link.
 * ─────────────────────────────────────────────────────────────────────────────
 */

export type BasemapKind = 'live-wmts' | 'backend-xyz' | 'static-dem';

export interface LunarBasemapProvider {
  id: string;
  label: string;
  kind: BasemapKind;
  /** Whether this source is confirmed usable directly from the browser. */
  browserUsable: boolean;
  /** True = genuine live/public data. False = local demo/fallback asset. */
  live: boolean;
  attribution: string;
  /**
   * Tile URL template for XYZ/WMTS providers. `{z}/{x}/{y}` placeholders.
   * Null for single-image (equirectangular) providers.
   */
  tileUrlTemplate: string | null;
  /** Single equirectangular texture URL for the 3D sphere, if applicable. */
  equirectUrl: string | null;
  notes: string;
}

const BACKEND_BASE = 'http://127.0.0.1:8000';

/**
 * NASA Moon Trek — LRO WAC global mosaic. Verified live + `Access-Control-
 * Allow-Origin: *`. WMTS tile order is {z}/{y}/{x}. Real lunar imagery, usable
 * as a live global context layer / future sphere texture.
 */
export const NASA_MOON_TREK_WAC: LunarBasemapProvider = {
  id: 'nasa-trek-wac',
  label: 'NASA Moon Trek · LRO WAC Global (live)',
  kind: 'live-wmts',
  browserUsable: true,
  live: true,
  attribution: 'NASA / ASU / LRO WAC · trek.nasa.gov',
  tileUrlTemplate:
    'https://trek.nasa.gov/tiles/Moon/EQ/LRO_WAC_Mosaic_Global_303ppd_v02/1.0.0/default/default028mm/{z}/{y}/{x}.jpg',
  equirectUrl: null,
  notes:
    'Confirmed HTTP 200 + CORS "*". LRO (not Chandrayaan-2) but real, public and live.',
};

/**
 * Backend Chandrayaan-2 derived tiles. REAL DFSAR data, offline-processed into
 * an XYZ pyramid and served by the local FastAPI backend. Not a live ISRO feed.
 */
export function backendChandrayaanTiles(
  crater = 'faustini',
  layer = 'hillshade'
): LunarBasemapProvider {
  return {
    id: `backend-${crater}-${layer}`,
    label: `Chandrayaan-2 ${layer} · ${crater} (local backend)`,
    kind: 'backend-xyz',
    browserUsable: true,
    live: false, // real data, but served offline — NOT a live ISRO connection
    attribution: 'ISRO Chandrayaan-2 DFSAR (offline-processed) · local backend',
    tileUrlTemplate: `${BACKEND_BASE}/tiles/${crater}/${layer}/{z}/{x}/{y}.png`,
    equirectUrl: null,
    notes:
      'Real Chandrayaan-2-derived radar/terrain tiles. Requires the FastAPI backend running on :8000.',
  };
}

/**
 * Local static lunar DEM. A real 1024x1024 lunar elevation raster shipped with
 * the repo (public/lunar-dem.png). Used as the DEFAULT hero surface: reliable,
 * offline, and gives genuine crater relief via displacement/bump mapping.
 */
export const STATIC_DEM: LunarBasemapProvider = {
  id: 'static-dem',
  label: 'Lunar DEM (bundled, offline)',
  kind: 'static-dem',
  browserUsable: true,
  live: false,
  attribution: 'Lunar digital elevation model (bundled demo asset)',
  tileUrlTemplate: null,
  equirectUrl: '/lunar-dem.png',
  notes: 'Real elevation raster used for displacement + bump on the 3D sphere.',
};

/**
 * The provider the scene renders by default. Swap this (or make it env-driven)
 * to promote the live NASA Moon Trek layer or backend Chandrayaan-2 tiles once
 * a sphere-tiling / proxy strategy is in place.
 */
export const DEFAULT_SURFACE_PROVIDER = STATIC_DEM;

export const ALL_PROVIDERS: LunarBasemapProvider[] = [
  STATIC_DEM,
  NASA_MOON_TREK_WAC,
  backendChandrayaanTiles(),
];
