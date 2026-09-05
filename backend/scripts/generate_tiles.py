"""
Build the Leaflet XYZ tile pyramid for the Chandrayaan-2 DFSAR swath.

Output: backend/tiles/faustini/{layer}/{z}/{x}/{y}.png

Geometry (M0) -- the pyramid is now cut at the product's NATIVE extent
---------------------------------------------------------------------
The `sri` product is 2258 lines x 6618 samples at 25 m x 25 m, i.e. a
56.45 x 165.45 km strip with a 2.93 : 1 aspect ratio. The previous revision
resized that strip into a square before tiling, which stretched every pixel
2.93x along track: hillshade came out streaked, slopes were wrong by the same
factor, and the swath geometry did not match ISRO's own browse image.

Nothing is resized to a square any more. Each zoom level z holds the native
array downsampled by 2**(max_zoom - z), and max_zoom is derived from the extent
rather than assumed:

    max_zoom = ceil(log2(max(samples, lines) / 256))

Tile alignment (M0b) -- the padding has to go on the correct side
----------------------------------------------------------------
A non-square image almost never fills a whole number of 256 px tiles, so the
last tile row and column are short and must be padded. WHICH SIDE gets the
padding is not cosmetic, because Leaflet's CRS.Simple pins the tile grid at
CRS (0, 0) -- which, with its (1, 0, -1, 0) transformation, is the BOTTOM-left
of the map -- and tile rows then grow upward into negative pixel space.

So the bottom edge of the last tile row lands exactly on lat 0, and every
pixel of slack accumulates at the TOP of the pyramid:

    slack = rows * 256 - height_px      (46 px at z5, 114 px at z1, 229 px at z2)

The previous revision wrote each short slice top-aligned (`out[:h, :w] = rgba`),
which pushed the whole swath `slack` pixels ABOVE the bounds it is supposed to
fill. Markers and rover routes, which are placed from the CRS bounds directly,
were then correct while the imagery underneath them was not -- the sites looked
like they were falling off the bottom of the swath.

Each level is now composited into a full rows*256 x cols*256 canvas with the
data BOTTOM-aligned in y (`pad_top = rows * 256 - h`) and LEFT-aligned in x,
which is what the flipped y axis and the un-flipped x axis respectively require.
`pad_top_px` is recorded per level in pyramid.json.

Normalisation (M1 / M1b)
------------------------
vmin/vmax are computed ONCE per layer over valid pixels of the native array and
reused for every tile at every zoom. Previously each 256x256 tile stretched
itself independently, so neighbouring tiles used different scales and the map
read as patchwork. Tiles that contain no valid pixel are skipped rather than
written as flat colour.

Terrain spacing (M2)
--------------------
Slope, roughness, hazard and hillshade use the real 25 m ground spacing from the
product's GeoTIFF frame, not the previous hardcoded 250 m. They are computed
once at native resolution and then downsampled, so the terrain looks the same at
every zoom.

Contrast (M3)
-------------
Radar layers are stretched with log1p(a / p50) clamped at p99.5 of valid pixels;
magnitude and terrain layers use a linear robust-percentile stretch.

HONESTY NOTE: hillshade / dem_elevation / hazard_map / illumination are derived
from a SYNTHETIC PLACEHOLDER DEM (see process_real_sar_pipeline.py). They are
labelled `synthetic-terrain-derived` in pyramid.json. Only cpr_heatmap and
dop_heatmap come from measured radar.
"""

from __future__ import annotations

import json
import math
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
import tifffile
from PIL import Image

BACKEND_DIR = Path(__file__).resolve().parents[1]
BASE_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ingestion.sar_geometry import read_geotiff_frame  # noqa: E402

TILES_DIR = BACKEND_DIR / "tiles" / "faustini"
PRADAN_DIR = BASE_DIR / "data" / "pradan"
NATIVE_DIR = PRADAN_DIR / "native"
RAW_DIR = PRADAN_DIR / "raw" / "data" / "calibrated" / "20200808"
PRODUCT_STEM = "ch2_sar_ncxl_20200808t201154198"

TILE_PX = 256


def pyramid_geometry(lines: int, samples: int, tile_px: int = TILE_PX) -> dict:
    """
    Derive the pyramid from the native extent instead of assuming a depth.

    Returns max_zoom, the per-zoom array size and tile-grid size, and the
    Leaflet CRS.Simple extent the frontend must use. One CRS unit equals one
    native pixel divided by 2**max_zoom, which is what makes zoom == max_zoom
    land exactly on native resolution.
    """
    longest = max(lines, samples)
    max_zoom = int(math.ceil(math.log2(longest / float(tile_px))))
    levels = []
    for z in range(max_zoom + 1):
        step = 2 ** (max_zoom - z)
        w = max(1, int(math.ceil(samples / step)))
        h = max(1, int(math.ceil(lines / step)))
        cols = int(math.ceil(w / tile_px))
        rows = int(math.ceil(h / tile_px))
        levels.append({
            "z": z,
            "downsample": step,
            "width_px": w,
            "height_px": h,
            "cols": cols,
            "rows": rows,
            # M0b: rows of transparent padding that must sit ABOVE the data so the
            # last tile row stays flush with CRS lat 0. See the module docstring.
            "pad_top_px": rows * tile_px - h,
            "pad_right_px": cols * tile_px - w,
        })
    return {
        "native": {"lines": lines, "samples": samples},
        "tile_px": tile_px,
        "max_zoom": max_zoom,
        "crs_extent": {"width": samples / float(2 ** max_zoom),
                       "height": lines / float(2 ** max_zoom)},
        "levels": levels,
        "tiles_per_layer_if_full": sum(l["cols"] * l["rows"] for l in levels),
    }


# --- M3: contrast stretches, fitted once per layer over valid pixels --------
def fit_stretch(data: np.ndarray, valid: np.ndarray, mode: str) -> dict:
    """
    Compute the single normalisation this layer will use everywhere.
    `mode` is 'log' (heavy-tailed radar ratios) or 'linear' (magnitudes, terrain).
    """
    sub = data[valid & np.isfinite(data)]
    if sub.size == 0:
        return {"mode": "linear", "vmin": 0.0, "vmax": 1.0, "valid_pixels": 0}
    if mode == "log":
        p50 = float(np.percentile(sub, 50))
        hi = float(np.percentile(sub, 99.5))
        ref = p50 if p50 > 0 else float(np.percentile(sub[sub > 0], 50)) if np.any(sub > 0) else 1.0
        ref = max(ref, 1e-12)
        return {"mode": "log", "ref": ref, "vmax": max(hi, ref * 1.0000001),
                "p50": p50, "p99_5": hi, "valid_pixels": int(sub.size)}
    lo = float(np.percentile(sub, 2))
    hi = float(np.percentile(sub, 98))
    if hi <= lo:
        hi = lo + 1.0
    return {"mode": "linear", "vmin": lo, "vmax": hi, "valid_pixels": int(sub.size)}


def apply_stretch(a: np.ndarray, st: dict) -> np.ndarray:
    """Map raw values to 0..1 using a stretch produced by `fit_stretch`."""
    if st["mode"] == "log":
        ref = st["ref"]
        denom = math.log1p(max(st["vmax"], ref) / ref)
        out = np.log1p(np.maximum(a, 0.0) / ref) / max(denom, 1e-12)
    else:
        out = (a - st["vmin"]) / (st["vmax"] - st["vmin"])
    return np.clip(out, 0.0, 1.0)


def describe_stretch(st: dict) -> str:
    if st["mode"] == "log":
        return (f"log1p(a / {st['ref']:.6g}) / log1p({st['vmax']:.6g} / {st['ref']:.6g})"
                f"   [p50={st['p50']:.6g}, p99.5={st['p99_5']:.6g}]")
    return f"linear on [{st['vmin']:.6g}, {st['vmax']:.6g}]  (p2..p98)"


# --- M2: terrain metrics at the product's real ground spacing ---------------
def compute_hillshade(dem: np.ndarray, spacing_m, altitude_deg=30.0, azimuth_deg=315.0) -> np.ndarray:
    """Horn hillshade. `spacing_m` is (metres_per_line, metres_per_sample)."""
    sy, sx = spacing_m
    rad_alt = math.radians(altitude_deg)
    rad_az = math.radians(azimuth_deg)
    dy, dx = np.gradient(dem, sy, sx)
    slope = np.pi / 2.0 - np.arctan(np.hypot(dx, dy))
    aspect = np.arctan2(-dx, dy)
    shaded = (math.sin(rad_alt) * np.sin(slope)
              + math.cos(rad_alt) * np.cos(slope) * np.cos(rad_az - aspect))
    return np.clip((shaded + 1.0) / 2.0, 0.0, 1.0).astype(np.float32)


def compute_terrain(dem: np.ndarray, spacing_m) -> dict:
    from scipy.ndimage import uniform_filter
    sy, sx = spacing_m
    dy, dx = np.gradient(dem, sy, sx)
    slope_deg = np.degrees(np.arctan(np.hypot(dx, dy))).astype(np.float32)
    mean_elev = uniform_filter(dem, size=5)
    roughness = np.sqrt(np.maximum(0.0, uniform_filter(dem ** 2, size=5) - mean_elev ** 2)).astype(np.float32)
    hazard = np.clip(0.6 * (slope_deg / 25.0) + 0.4 * (roughness / 40.0), 0.0, 1.0).astype(np.float32)
    return {"slope_deg": slope_deg, "roughness_m": roughness, "hazard": hazard}


def percentile_table(name: str, a: np.ndarray, mask: np.ndarray) -> str:
    sub = a[mask & np.isfinite(a)]
    if sub.size == 0:
        return f"  {name:14s} (no valid pixels)"
    qs = (1, 5, 25, 50, 75, 95, 99)
    vals = "  ".join(f"p{q}={np.percentile(sub, q):9.4f}" for q in qs)
    return f"  {name:14s} min={sub.min():9.4f}  {vals}  max={sub.max():9.4f}"


def histogram_table(name: str, norm01: np.ndarray, mask: np.ndarray, bins: int = 20) -> str:
    sub = norm01[mask]
    if sub.size == 0:
        return f"  {name}: no valid pixels"
    counts, _ = np.histogram(sub, bins=bins, range=(0.0, 1.0))
    frac = counts / max(counts.sum(), 1)
    bars = "".join(".:-=+*#@"[min(7, int(f * 8 / max(frac.max(), 1e-9)))] for f in frac)
    return (f"  {name:14s} |{bars}|  occupied bins {int((counts > 0).sum())}/{bins}  "
            f"peak bin {frac.max() * 100:.1f}%")


def _tile_rgba(norm: np.ndarray, valid: np.ndarray, colormap, alpha_valid: int) -> np.ndarray:
    """
    One 256x256 RGBA tile.

    Slices handed in here are already exactly 256x256 because generate_layer_tiles
    composites each level into a padded canvas first (M0b). The reshape below is
    kept only as a guard so a future caller cannot silently emit a short tile.
    """
    u8 = (np.clip(norm, 0.0, 1.0) * 255.0).astype(np.uint8)
    if colormap is None:
        rgb = cv2.cvtColor(u8, cv2.COLOR_GRAY2RGB)
    else:
        rgb = cv2.cvtColor(cv2.applyColorMap(u8, colormap), cv2.COLOR_BGR2RGB)
    alpha = np.where(valid, alpha_valid, 0).astype(np.uint8)
    rgba = np.dstack([rgb, alpha])
    h, w = rgba.shape[:2]
    if (h, w) != (TILE_PX, TILE_PX):
        out = np.zeros((TILE_PX, TILE_PX, 4), dtype=np.uint8)
        out[:h, :w] = rgba
        rgba = out
    return rgba


def _masked_downsample(data: np.ndarray, valid: np.ndarray, w: int, h: int):
    """
    Area-average that ignores padding, so the swath edge does not get a dark
    halo from averaging real returns against off-swath zeros.
    """
    if (data.shape[1], data.shape[0]) == (w, h):
        return data, valid
    vf = valid.astype(np.float32)
    num = cv2.resize(data * vf, (w, h), interpolation=cv2.INTER_AREA)
    den = cv2.resize(vf, (w, h), interpolation=cv2.INTER_AREA)
    out = np.divide(num, den, out=np.zeros_like(num), where=den > 1e-6)
    return out, den > 0.25


def generate_layer_tiles(layer_name: str, data: np.ndarray, valid: np.ndarray,
                         geom: dict, stretch: dict, colormap=None,
                         alpha_valid: int = 255) -> dict:
    layer_dir = TILES_DIR / layer_name
    if layer_dir.exists():
        shutil.rmtree(layer_dir)
    layer_dir.mkdir(parents=True, exist_ok=True)

    written = skipped = 0
    for lvl in geom["levels"]:
        z, w, h = lvl["z"], lvl["width_px"], lvl["height_px"]
        cols, rows, pad_top = lvl["cols"], lvl["rows"], lvl["pad_top_px"]
        d_z, v_z = _masked_downsample(data, valid, w, h)
        norm_z = apply_stretch(d_z, stretch)

        # M0b: composite into the full padded tile canvas with the data
        # BOTTOM-aligned in y and LEFT-aligned in x. CRS.Simple pins the tile
        # grid to lat 0 at the bottom, so top-aligning here (what the previous
        # revision did) lifted the whole swath pad_top pixels off its bounds.
        canvas_n = np.zeros((rows * TILE_PX, cols * TILE_PX), np.float32)
        canvas_v = np.zeros((rows * TILE_PX, cols * TILE_PX), bool)
        canvas_n[pad_top:pad_top + h, :w] = norm_z
        canvas_v[pad_top:pad_top + h, :w] = v_z
        del d_z, v_z, norm_z

        for x in range(cols):
            for y in range(rows):
                ys, xs = slice(y * TILE_PX, (y + 1) * TILE_PX), slice(x * TILE_PX, (x + 1) * TILE_PX)
                vs = canvas_v[ys, xs]
                if not vs.any():
                    skipped += 1
                    continue
                ns = canvas_n[ys, xs]
                out = layer_dir / str(z) / str(x)
                out.mkdir(parents=True, exist_ok=True)
                Image.fromarray(_tile_rgba(ns, vs, colormap, alpha_valid)).save(
                    out / f"{y}.png", format="PNG", optimize=True)
                written += 1
        del canvas_n, canvas_v
    print(f"  {layer_name:15s} {written:5d} tiles written, {skipped:4d} all-padding tiles skipped"
          f"   stretch: {describe_stretch(stretch)}")
    return {"layer": layer_name, "tiles_written": written, "tiles_skipped_empty": skipped,
            "stretch": {k: (round(v, 9) if isinstance(v, float) else v) for k, v in stretch.items()},
            "colormap": "grayscale" if colormap is None else int(colormap),
            "alpha_valid": alpha_valid}


def main() -> None:
    print("=" * 78)
    print("BUILDING NATIVE-EXTENT CHANDRAYAAN-2 DFSAR TILE PYRAMID")
    print("=" * 78)

    need = {"cpr": NATIVE_DIR / "cpr_native.tif", "dop": NATIVE_DIR / "dop_native.tif",
            "s0": NATIVE_DIR / "s0_native.tif", "dem": NATIVE_DIR / "dem_native_synthetic.tif",
            "valid": NATIVE_DIR / "valid_native.tif"}
    missing = [str(p) for p in need.values() if not p.exists()]
    if missing:
        raise SystemExit("missing native products -- run process_real_sar_pipeline.py first:\n  "
                         + "\n  ".join(missing))

    cpr = tifffile.imread(str(need["cpr"])).astype(np.float32)
    dop = tifffile.imread(str(need["dop"])).astype(np.float32)
    s0 = tifffile.imread(str(need["s0"])).astype(np.float32)
    dem = tifffile.imread(str(need["dem"])).astype(np.float32)
    valid = tifffile.imread(str(need["valid"])) > 0
    lines, samples = dem.shape

    # M2: real ground spacing, straight from the product's own GeoTIFF frame.
    spacing = (25.0, 25.0)
    frame_src = "fallback 25 m (raw bundle absent)"
    lh_tif = RAW_DIR / f"{PRODUCT_STEM}_d_sri_xx_cp_lh_d18.tif"
    if lh_tif.exists():
        frame = read_geotiff_frame(lh_tif)
        spacing = frame.metres_per_pixel((lines, samples))
        frame_src = frame.source

    geom = pyramid_geometry(lines, samples)
    print(f"\nNative extent      {lines} lines x {samples} samples  (aspect {samples / lines:.2f} : 1)")
    print(f"Ground spacing     {spacing[0]:.3f} m per line x {spacing[1]:.3f} m per sample")
    print(f"  from             {frame_src}")
    print(f"Pyramid depth      max_zoom = {geom['max_zoom']}  (derived, not assumed)")
    print(f"Leaflet CRS extent width {geom['crs_extent']['width']:.6f} x "
          f"height {geom['crs_extent']['height']:.6f}")
    print(f"Valid footprint    {valid.mean() * 100:.2f} % of the raster")
    print("\n  z  downsample   array px        tile grid   tiles   pad top (px, transparent)")
    for l in geom["levels"]:
        print(f"  {l['z']}  1/{l['downsample']:<9d} {l['width_px']:5d} x {l['height_px']:<5d} "
              f"  {l['cols']:3d} x {l['rows']:<3d}    {l['cols'] * l['rows']:5d}   {l['pad_top_px']:5d}"
              f"   (right {l['pad_right_px']})")
    print("  pad top is placed ABOVE the data so the last tile row stays flush with CRS lat 0;")
    print("  top-aligning it instead lifted the imagery off its bounds by exactly these amounts.")

    # --- terrain, computed once at native resolution ---------------------
    print("\n--- M2: terrain metrics, before (250 m assumed) vs after (real spacing) ---")
    old = compute_terrain(dem, (250.0, 250.0))
    new = compute_terrain(dem, spacing)
    all_true = np.ones_like(valid, dtype=bool)
    for key in ("slope_deg", "roughness_m", "hazard"):
        print(percentile_table(f"{key} BEFORE", old[key], all_true))
        print(percentile_table(f"{key} AFTER ", new[key], all_true))
    del old

    hillshade = compute_hillshade(dem, spacing)
    illumination = np.clip(
        hillshade * ((dem - dem.min()) / (np.ptp(dem) + 1e-6)) ** 1.2, 0.0, 1.0).astype(np.float32)

    # --- M1/M3: one stretch per layer, fitted over valid pixels only ------
    print("\n--- M1/M3: per-layer stretch fitted once over valid pixels ---")
    layers = [
        ("hillshade", hillshade, all_true, "linear", None, 255, "synthetic-terrain-derived"),
        ("dem_elevation", dem, all_true, "linear", cv2.COLORMAP_VIRIDIS, 255, "synthetic-terrain-derived"),
        ("hazard_map", new["hazard"], all_true, "linear", cv2.COLORMAP_JET, 255, "synthetic-terrain-derived"),
        ("illumination", illumination, all_true, "linear", cv2.COLORMAP_HOT, 255, "synthetic-terrain-derived"),
        ("cpr_heatmap", cpr, valid, "log", cv2.COLORMAP_TURBO, 230, "measured-radar"),
        ("dop_heatmap", dop, valid, "log", cv2.COLORMAP_CIVIDIS, 230, "measured-radar"),
    ]

    print("\n  histogram of the 0..1 normalised values, 20 bins (before = old per-tile "
          "p1/p99 style global linear, after = this layer's fitted stretch)")
    manifest_layers = []
    for name, data, mask, mode, cmap, alpha, prov in layers:
        st_lin = fit_stretch(data, mask, "linear")
        st = fit_stretch(data, mask, mode)
        print(histogram_table(f"{name} BEFORE", apply_stretch(data, st_lin), mask))
        print(histogram_table(f"{name} AFTER ", apply_stretch(data, st), mask))
        entry = generate_layer_tiles(name, data, mask, geom, st, cmap, alpha)
        entry["provenance"] = prov
        manifest_layers.append(entry)

    manifest = {
        "generated_from": {
            "native_products": str(NATIVE_DIR.relative_to(BASE_DIR)),
            "georeferencing_source": frame_src,
        },
        "geometry": geom,
        "ground_spacing_m": {"per_line": spacing[0], "per_sample": spacing[1]},
        "valid_footprint_fraction": round(float(valid.mean()), 6),
        "layers": manifest_layers,
        "frontend_constants": {
            "NATIVE_LINES": lines,
            "NATIVE_SAMPLES": samples,
            "MAX_NATIVE": geom["max_zoom"],
            "BOUND_H": geom["crs_extent"]["height"],
            "BOUND_W": geom["crs_extent"]["width"],
            "TILE_ROWS_AT_MAX": geom["levels"][-1]["rows"],
            "TILE_COLS_AT_MAX": geom["levels"][-1]["cols"],
        },
        "tile_alignment": (
            "Each level is composited into a rows*256 x cols*256 canvas with the data "
            "BOTTOM-aligned in y (pad_top_px transparent rows above it) and LEFT-aligned "
            "in x. Leaflet CRS.Simple pins the tile grid at CRS (0,0) = the bottom-left of "
            "the bounds and grows rows upward, so the last tile row must end exactly on "
            "lat 0. Frontend contract: disk row = coords.y + rows_at_zoom(z), additive."
        ),
        "honesty_note": ("hillshade / dem_elevation / hazard_map / illumination are derived "
                         "from a synthetic placeholder DEM; only cpr_heatmap and dop_heatmap "
                         "are measured radar."),
    }
    TILES_DIR.mkdir(parents=True, exist_ok=True)
    with open(TILES_DIR / "pyramid.json", "w") as f:
        json.dump(manifest, f, indent=2)

    fc = manifest["frontend_constants"]
    print("\n" + "=" * 78)
    print("PASTE THESE INTO frontend/src/mission/MissionMap.tsx")
    print("=" * 78)
    print(f"const NATIVE_LINES = {fc['NATIVE_LINES']};")
    print(f"const NATIVE_SAMPLES = {fc['NATIVE_SAMPLES']};")
    print(f"const MAX_NATIVE = {fc['MAX_NATIVE']};")
    print(f"// CRS extent = native / 2**MAX_NATIVE  ->  "
          f"{fc['BOUND_H']} x {fc['BOUND_W']}")
    print(f"// tile grid at z={fc['MAX_NATIVE']}: {fc['TILE_COLS_AT_MAX']} cols x "
          f"{fc['TILE_ROWS_AT_MAX']} rows")
    print("=" * 78)
    print(f"\nManifest -> {TILES_DIR / 'pyramid.json'}")


if __name__ == "__main__":
    main()
