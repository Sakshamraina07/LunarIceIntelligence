/**
 * lunarBasemap.ts
 * Surface texture provider for the 3D Moon on the landing page.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * WHAT THIS FILE IS ALLOWED TO CLAIM (PRD Phase 1C, §1.2b items 26 and 27)
 * ─────────────────────────────────────────────────────────────────────────────
 * This is decoration. It textures a spinning sphere on a marketing page; no
 * number anywhere in the product is derived from it. It therefore has exactly
 * one obligation: not to describe itself as measured data.
 *
 * TWO THINGS WERE REMOVED HERE.
 *
 * 1. `backendChandrayaanTiles()` and `ALL_PROVIDERS`. They built URLs against
 *    `{backend}/tiles/{crater}/{layer}/{z}/{x}/{y}.png` — an endpoint deleted in
 *    PRD Phase 0 along with the 510-tile pyramid it served. Nothing called them;
 *    they were a dead reference to a 404 that still read, to anyone opening the
 *    file, as a live Chandrayaan-2 integration.
 *
 * 2. The provenance claim on `/lunar-dem.png`. `STATIC_DEM` described the same
 *    file as a "Real elevation raster" in `notes` and a "bundled demo asset" in
 *    `attribution`, in the same object, and named no body, mission, instrument
 *    or resolution. The claim was tested rather than repeated, and it does not
 *    survive:
 *
 *      · 1024 x 1024, aspect 1:1. A global equirectangular lunar map is 2:1
 *        (360° x 180°). This cannot be the global product it was mounted as.
 *      · RGB, not single-channel, with max|R-G| = 100 DN and max|G-B| = 52 DN.
 *        An elevation model is a single-valued height field; a three-channel
 *        image with that much channel separation is not one.
 *      · No embedded metadata of any kind (PNG carries only a 72 dpi tag), no
 *        source note, no product id, and no history before the repository's
 *        first commit.
 *
 *    So it is relabelled as what it demonstrably is: an untraced decorative
 *    texture. NO SOURCE IS GUESSED. If its origin is later established it can be
 *    named here; until then the honest statement is that we do not know.
 *
 * NASA_MOON_TREK_WAC is kept because it is a real, verifiable, live public
 * endpoint, and because it is the obvious upgrade path for this sphere. It is
 * not currently rendered.
 *
 * (Noted for later, out of scope here: this project already holds LOLA
 * LDEM_80S_80M V2.0 on disk. Texturing the hero sphere from that product would
 * make the landing page's Moon measured instead of decorative. See docs/.)
 * ─────────────────────────────────────────────────────────────────────────────
 */

export type BasemapKind = 'live-wmts' | 'static-texture';

export interface LunarBasemapProvider {
  id: string;
  label: string;
  kind: BasemapKind;
  /** Whether this source is confirmed usable directly from the browser. */
  browserUsable: boolean;
  /** True = genuine live/public data. False = a local asset. */
  live: boolean;
  /**
   * What this imagery IS, as far as it can be established. `null` means the
   * provenance is unknown — which is a statement, not a gap to be filled with a
   * plausible one.
   */
  attribution: string | null;
  /**
   * True when this asset makes NO claim to be measured data. The scene may use
   * it freely; nothing scientific may be derived from it.
   */
  decorativeOnly: boolean;
  /** Tile URL template for WMTS providers. `{z}/{x}/{y}` placeholders. */
  tileUrlTemplate: string | null;
  /** Single equirectangular texture URL for the 3D sphere, if applicable. */
  equirectUrl: string | null;
  notes: string;
}

/**
 * NASA Moon Trek — LRO WAC global mosaic. Verified live, with
 * `Access-Control-Allow-Origin: *`. WMTS tile order is {z}/{y}/{x}. Real lunar
 * imagery from LRO (not Chandrayaan-2), and the honest upgrade path for the
 * hero sphere.
 *
 * NOTE: this is the EQUIRECTANGULAR (EQ) endpoint, which is the one that
 * responds. The polar (SP) endpoints under the same host were investigated for
 * the mission map and 404 on every path tried; see PRD §5.
 */
export const NASA_MOON_TREK_WAC: LunarBasemapProvider = {
  id: 'nasa-trek-wac',
  label: 'NASA Moon Trek · LRO WAC Global (live)',
  kind: 'live-wmts',
  browserUsable: true,
  live: true,
  attribution: 'NASA / ASU / LRO WAC · trek.nasa.gov',
  decorativeOnly: false,
  tileUrlTemplate:
    'https://trek.nasa.gov/tiles/Moon/EQ/LRO_WAC_Mosaic_Global_303ppd_v02/1.0.0/default/default028mm/{z}/{y}/{x}.jpg',
  equirectUrl: null,
  notes:
    'Confirmed HTTP 200 with CORS "*". LRO rather than Chandrayaan-2, but real, public and live.',
};

/**
 * The bundled sphere texture. Provenance UNKNOWN — see the header for the
 * measurements that withdrew the previous "Real elevation raster" claim.
 */
export const DECORATIVE_SURFACE: LunarBasemapProvider = {
  id: 'decorative-surface',
  label: 'Bundled surface texture (provenance unknown)',
  kind: 'static-texture',
  browserUsable: true,
  live: false,
  // null, not a plausible-sounding string. We do not know where this came from.
  attribution: null,
  decorativeOnly: true,
  tileUrlTemplate: null,
  equirectUrl: '/lunar-dem.png',
  notes:
    'UNTRACED DECORATIVE TEXTURE. 1024x1024 RGB PNG with no metadata. It is not an ' +
    'elevation model: a DEM is single-valued, and this carries up to 100 DN of ' +
    'separation between its colour channels. Its 1:1 aspect also rules out the ' +
    'global equirectangular product its filename suggests. Used for displacement ' +
    'and bump on the landing-page sphere purely for visual relief; no measurement ' +
    'anywhere in this project derives from it.',
};

/**
 * The provider the scene renders. Swap to NASA_MOON_TREK_WAC once a sphere
 * tiling strategy exists, or to a texture rendered from the LOLA product this
 * repository already holds.
 */
export const DEFAULT_SURFACE_PROVIDER = DECORATIVE_SURFACE;
