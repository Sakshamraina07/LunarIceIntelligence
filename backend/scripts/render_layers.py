"""
render_layers.py -- render every map layer as ONE image. Replaces the tile
pyramid built by the deleted generate_tiles.py.

Why the pyramid went away
-------------------------
The science array is 2258 x 6618 = 14.9 megapixels at an isotropic 25.0 m/px
(read from the product's own GeoTIFF GeoKeys, not assumed). That is smaller than
a phone photo. 6618 samples cover 165.45 km, so native detail IS 25 m/px; a
~1400 px map panel showing the whole swath is already at ~118 m/px, a 4.7x
downsample. There is no detail below 25 m to stream, so a pyramid bought
nothing and cost a great deal:

  * ~331 tiles per layer x 6 layers = ~2000 HTTP requests to paint one map.
  * Per-tile percentile normalisation, which made every tile a different
    stretch and manufactured visible seams.
  * cv2.resize(..., (zoom_dim, zoom_dim)) squashed a 2.93:1 swath into squares.
  * Image.save(..., optimize=True) per tile, which is what made regeneration
    take minutes.

All of that is replaced by: normalise ONCE over the whole array, colourise once,
write one lossless image per layer plus a small preview, and let the frontend
CDN serve them. Six requests, no seams, one stretch.

What this script does NOT do
---------------------------
It does not compute illumination from solar geometry. `illumination` is a shading
heuristic (hillshade x normalised elevation), tagged
provenance="modelled-from-measured-topography" so the UI cannot badge it as a
PSR product. No true cold traps are computed anywhere in this build.

The DEM is no longer synthetic. dem_native_synthetic.tif keeps its filename for
compatibility but now holds LOLA polar topography; the four terrain layers are
tagged provenance="measured-topography" and every one of their descriptions
states the LOLA product's NATIVE post spacing, which is coarser than the grid
they are rendered on. That number, not the grid spacing, is what bounds what
these layers can show.

Outputs -> frontend/public/layers/
  {layer}.webp            full resolution, lossless, RGBA (alpha = footprint)
  {layer}.preview.webp    ~640 px wide, same stretch, for instant first paint
  layers.json             manifest: bounds, stretch, vmin/vmax, colormap,
                          provenance, geodetic frame, measured footprint ring

Run:  python backend/scripts/render_layers.py
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import tifffile
from PIL import Image

BASE_DIR = Path(__file__).resolve().parents[2]        # -> repository root
BACKEND_DIR = Path(__file__).resolve().parents[1]     # -> backend/
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

NATIVE_DIR = BASE_DIR / "data" / "pradan" / "native"
DFSAR_DIR = BASE_DIR / "data" / "pradan" / "dfsar"
LOLA_SIDECAR = BASE_DIR / "data" / "pradan" / "lola" / "ldem_frame_25m.provenance.json"
RAW_DIR = BASE_DIR / "data" / "pradan" / "raw" / "data" / "calibrated" / "20200808"
OUT_DIR = BASE_DIR / "frontend" / "public" / "layers"

PRODUCT_STEM = "ch2_sar_ncxl_20200808t201154198"
LH_TIF = RAW_DIR / f"{PRODUCT_STEM}_d_sri_xx_cp_lh_d18.tif"
LH_XML = RAW_DIR / f"{PRODUCT_STEM}_d_sri_xx_cp_xx_d18.xml"

# Leaflet CRS.Simple convention. 256 is OUR choice of horizontal unit count --
# it is not data, and nothing downstream may assume the vertical extent: the
# frontend reads height_units out of layers.json.
CRS_WIDTH_UNITS = 256.0
PREVIEW_WIDTH = 640
FALLBACK_SPACING = (25.0, 25.0)   # (metres per line, metres per sample)

# The spacing generate_tiles.py and mission_service.py hardcoded. Kept only so
# the M2 before/after table has an honest "before" column to print.
LEGACY_SPACING_M = 250.0


# ---------------------------------------------------------------------------
# stretches -- ported verbatim in intent from generate_tiles.py, but now fitted
# ONCE against the whole array instead of once per tile. That single change is
# what removes the seams.
# ---------------------------------------------------------------------------

def fit_stretch(data: np.ndarray, valid: np.ndarray, mode: str) -> dict:
    """
    Fit a display stretch over VALID pixels only.

    Radar layers pass a footprint mask, so the 84% of the frame with no return
    never drags the percentiles down. Dense (terrain) layers pass all-finite.
    """
    sub = data[valid & np.isfinite(data)]
    if sub.size == 0:
        return {"mode": "linear", "vmin": 0.0, "vmax": 1.0, "valid_pixels": 0}
    if mode == "log":
        p50 = float(np.percentile(sub, 50))
        hi = float(np.percentile(sub, 99.5))
        ref = p50 if p50 > 0 else (float(np.percentile(sub[sub > 0], 50)) if np.any(sub > 0) else 1.0)
        ref = max(ref, 1e-12)
        return {"mode": "log", "ref": ref, "vmax": max(hi, ref * 1.0000001),
                "p50": p50, "p99_5": hi, "valid_pixels": int(sub.size)}
    lo = float(np.percentile(sub, 2))
    hi = float(np.percentile(sub, 98))
    if hi <= lo:
        hi = lo + 1.0
    return {"mode": "linear", "vmin": lo, "vmax": hi,
            "p2": lo, "p98": hi, "valid_pixels": int(sub.size)}


def apply_stretch(a: np.ndarray, st: dict) -> np.ndarray:
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


def stretch_range(st: dict) -> tuple[float, float]:
    """The (vmin, vmax) the legend should print for this stretch."""
    if st["mode"] == "log":
        return 0.0, float(st["vmax"])
    return float(st["vmin"]), float(st["vmax"])


# ---------------------------------------------------------------------------
# terrain -- unchanged maths, but the gradient spacing now comes from the frame
# ---------------------------------------------------------------------------

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
    """Slope / roughness / hazard for the rendered layers.

    The hazard definition is NOT redefined here. It is imported from
    app/modules/module_d_terrain.py, which is the single source: the same
    function produces the number in the stat panel (via build_analysis.py) and
    the colours in this PNG, so the picture and the figure cannot drift apart.

    What was here before was a second, undocumented formula —
    0.6*(slope/25) + 0.4*(roughness/40) — with divisors that cite nothing. The
    module's divisors are MAX_TRAVERSABLE_SLOPE_DEG (20 deg, the rover tilt
    limit) and 50 m of local relief, and its weights come from config.py.
    Boulder risk is a zeros array with w_boulder=0.0, i.e. weighted out rather
    than fed in as a measurement of "no rocks": there is no OHRC product for
    this frame, so hazard here is slope + roughness, renormalised.
    """
    from scipy.ndimage import uniform_filter

    from app.modules.module_d_terrain import compute_hazard_score

    sy, sx = spacing_m
    dy, dx = np.gradient(dem, sy, sx)
    slope_deg = np.degrees(np.arctan(np.hypot(dx, dy))).astype(np.float32)
    mean_elev = uniform_filter(dem, size=5)
    roughness = np.sqrt(np.maximum(0.0, uniform_filter(dem ** 2, size=5) - mean_elev ** 2)).astype(np.float32)
    hazard = compute_hazard_score(slope_deg, roughness,
                                  np.zeros_like(slope_deg, np.float32),
                                  w_boulder=0.0)
    return {"slope_deg": slope_deg, "roughness_m": roughness, "hazard": hazard}


def hazard_formula_before_after(slope_deg: np.ndarray, roughness: np.ndarray,
                                mask: np.ndarray) -> tuple[str, dict]:
    """Print what collapsing to one hazard definition did to the rendered layer.

    The stat-panel hazard number is unaffected — it always came from
    module_d_terrain via build_analysis.py. Only the PICTURE changes, and this
    table is how much.
    """
    from app.modules.module_d_terrain import compute_hazard_score

    old = np.clip(0.6 * (slope_deg / 25.0) + 0.4 * (roughness / 40.0), 0.0, 1.0).astype(np.float32)
    new = compute_hazard_score(slope_deg, roughness,
                               np.zeros_like(slope_deg, np.float32), w_boulder=0.0)

    sel = mask & np.isfinite(slope_deg)
    qs = (1, 5, 25, 50, 75, 90, 95, 99, 100)
    o, n = old[sel], new[sel]
    lines = [
        "\n  --- hazard layer: render_layers' own formula vs module_d_terrain "
        "(single source) ---",
        "  OLD (deleted): clip(0.60*slope/25 + 0.40*roughness/40)   "
        "-- divisors uncited",
        "  NEW (module) : (0.50*clip(slope/20) + 0.30*clip(roughness/50)) / 0.80  "
        "-- 20 deg = MAX_TRAVERSABLE_SLOPE_DEG",
        "  " + " ".join(f"p{q}" .rjust(8) for q in qs),
        "  old " + " ".join(f"{float(np.percentile(o, q)):8.4f}" for q in qs),
        "  new " + " ".join(f"{float(np.percentile(n, q)):8.4f}" for q in qs),
        f"  mean  old={float(o.mean()):.4f}  new={float(n.mean()):.4f}   "
        f"frac>0.5  old={float((o > 0.5).mean()) * 100:.3f}%  "
        f"new={float((n > 0.5).mean()) * 100:.3f}%",
        f"  frac>0.7  old={float((o > 0.7).mean()) * 100:.3f}%  "
        f"new={float((n > 0.7).mean()) * 100:.3f}%   "
        f"(the stat-panel number is unchanged: it was already module_d_terrain)",
    ]
    summary = {
        "old_formula": "clip(0.60*slope/25 + 0.40*roughness/40)",
        "new_formula": "module_d_terrain.compute_hazard_score(w_boulder=0.0)",
        "old_mean": round(float(o.mean()), 4),
        "new_mean": round(float(n.mean()), 4),
        "old_p50": round(float(np.percentile(o, 50)), 4),
        "new_p50": round(float(np.percentile(n, 50)), 4),
        "old_p99": round(float(np.percentile(o, 99)), 4),
        "new_p99": round(float(np.percentile(n, 99)), 4),
        "old_frac_gt_0p5_pct": round(float((o > 0.5).mean()) * 100, 3),
        "new_frac_gt_0p5_pct": round(float((n > 0.5).mean()) * 100, 3),
        "stat_panel_number_changed": False,
    }
    return "\n".join(lines), summary


# ---------------------------------------------------------------------------
# evidence printing
# ---------------------------------------------------------------------------

def percentile_table(name: str, a: np.ndarray, mask: np.ndarray) -> str:
    sub = a[mask & np.isfinite(a)]
    if sub.size == 0:
        return f"  {name:14s} (no valid pixels)"
    qs = (1, 5, 25, 50, 75, 95, 99)
    vals = "  ".join(f"p{q}={np.percentile(sub, q):9.4f}" for q in qs)
    return f"  {name:14s} min={sub.min():9.4f}  {vals}  max={sub.max():9.4f}"


def histogram_table(name: str, a: np.ndarray, mask: np.ndarray, bins: int = 20) -> str:
    """
    20-bin ASCII histogram. Windows consoles are cp1252, so bars are '#', never
    Unicode block glyphs.
    """
    sub = a[mask & np.isfinite(a)]
    if sub.size == 0:
        return f"  {name}: no valid pixels"
    lo, hi = float(sub.min()), float(sub.max())
    if hi <= lo:
        hi = lo + 1e-9
    counts, edges = np.histogram(sub, bins=bins, range=(lo, hi))
    peak = max(int(counts.max()), 1)
    out = [f"  {name}   {sub.size:,} px   range {lo:.6g} .. {hi:.6g}"]
    for i, c in enumerate(counts):
        bar = "#" * int(round(38.0 * c / peak))
        out.append(f"    [{edges[i]:11.5g} .. {edges[i + 1]:11.5g})  {100.0 * c / sub.size:6.2f}%  {bar}")
    return "\n".join(out)


def u8_distribution(name: str, u8: np.ndarray, mask: np.ndarray) -> str:
    """
    Where the 8-bit codes actually land. A stretch that leaves 90% of pixels in
    codes 0-12 is the 'faded and patchy' bug, so this is the number that proves
    the stretch choice rather than asserting it.
    """
    sub = u8[mask]
    if sub.size == 0:
        return f"  {name}: no valid pixels"
    counts = np.bincount(sub.ravel(), minlength=256).astype(np.float64)
    counts /= max(counts.sum(), 1.0)
    binned = counts.reshape(16, 16).sum(axis=1)
    peak = max(float(binned.max()), 1e-12)
    out = [f"  {name}  8-bit code distribution over valid pixels "
           f"(mean={sub.mean():.1f}, p5={np.percentile(sub, 5):.0f}, p95={np.percentile(sub, 95):.0f})"]
    for i, frac in enumerate(binned):
        bar = "#" * int(round(38.0 * frac / peak))
        out.append(f"    codes {i * 16:3d}-{i * 16 + 15:3d}  {100.0 * frac:6.2f}%  {bar}")
    return "\n".join(out)

# ---------------------------------------------------------------------------
# rasterising
# ---------------------------------------------------------------------------

# Perceptually uniform maps only. COLORMAP_JET is deliberately absent: its
# lightness is non-monotonic, so it invents bright/dark bands where the data is
# smooth. A reviewer who knows scientific visualisation will call that out, and
# on a hazard map a manufactured edge is a manufactured cliff.
COLORMAPS = {
    "grayscale": None,
    "viridis": cv2.COLORMAP_VIRIDIS,
    "magma": cv2.COLORMAP_MAGMA,
    "inferno": cv2.COLORMAP_INFERNO,
    "cividis": cv2.COLORMAP_CIVIDIS,
    "turbo": cv2.COLORMAP_TURBO,
}


def colorize(u8: np.ndarray, cmap_name: str) -> np.ndarray:
    """uint8 -> RGB uint8. cv2 emits BGR, so convert; getting this backwards is
    how a 'viridis' layer silently ships as its own mirror image."""
    cmap = COLORMAPS[cmap_name]
    if cmap is None:
        return np.dstack([u8, u8, u8])
    return cv2.cvtColor(cv2.applyColorMap(u8, cmap), cv2.COLOR_BGR2RGB)


def save_rgba(path: Path, rgba: np.ndarray) -> tuple[Path, int]:
    """
    Lossless WebP. Scientific rasters do not get lossy compression -- JPEG-style
    ringing around a bright CPR speckle would look exactly like more speckle.
    PNG at compress_level=6 is the fallback if this PIL build lacks WebP.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.fromarray(rgba, mode="RGBA")
    try:
        img.save(str(path), format="WEBP", lossless=True, quality=100, method=4)
    except Exception as exc:                                    # pragma: no cover
        print(f"    ! WebP unavailable ({exc}) -- writing PNG instead")
        path = path.with_suffix(".png")
        img.save(str(path), format="PNG", compress_level=6)
    return path, path.stat().st_size


def make_preview(rgb: np.ndarray, alpha: np.ndarray, width: int) -> np.ndarray:
    """
    Masked area-average downsample. Plain resize would average the transparent
    padding into the ribbon edge and draw a dark halo around the real data, so
    colour is weighted by alpha and divided back out.
    """
    h, w = alpha.shape
    ph = max(1, int(round(h * width / float(w))))
    a = alpha.astype(np.float32) / 255.0
    num = cv2.resize(rgb.astype(np.float32) * a[..., None], (width, ph), interpolation=cv2.INTER_AREA)
    den = cv2.resize(a, (width, ph), interpolation=cv2.INTER_AREA)
    prgb = np.clip(num / np.maximum(den, 1e-6)[..., None], 0.0, 255.0).astype(np.uint8)
    palpha = np.clip(den * 255.0, 0.0, 255.0).astype(np.uint8)
    return np.dstack([prgb, palpha])


def footprint_ring_normalised(mask: np.ndarray, step: int = 64, min_run: int = 8):
    """
    Trace a mask's ribbon and return it in UNIT coordinates ([fy_from_top, fx],
    both 0..1). Unit coordinates because the frontend's CRS extent now comes from
    the manifest -- a ring baked in Leaflet units would silently break the day
    the extent convention changes.

    Called twice: once for ISRO's swath mask (the beam footprint) and once for
    the amplitude mask (where signal actually returned). Both rings ship in the
    manifest so the map can draw the real 19.65 km swath without implying that
    radar values exist across all of it.

    Same measurement as backend/scripts/print_footprint_polygon.py: the band is
    99.55% dense between its two edges, so first/last set line bounds it.
    """
    lines, samples = mask.shape
    cols, top, bot, thick = [], [], [], []
    for c in range(0, samples, step):
        idx = np.flatnonzero(mask[:, c])
        if idx.size < min_run:
            continue
        cols.append(c)
        top.append(int(idx[0]))
        bot.append(int(idx[-1]))
        thick.append(int(idx.size))
    ring = [[round(t / lines, 6), round(c / samples, 6)] for c, t in zip(cols, top)]
    ring += [[round(b / lines, 6), round(c / samples, 6)]
             for c, b in zip(reversed(cols), reversed(bot))]
    return ring, np.asarray(thick), np.asarray(cols)

# ---------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------

def load_inputs() -> dict:
    need = {
        "cpr": NATIVE_DIR / "cpr_native.tif",
        "dop": NATIVE_DIR / "dop_native.tif",
        "s0": NATIVE_DIR / "s0_native.tif",
        "dem": NATIVE_DIR / "dem_native_synthetic.tif",
        "valid": NATIVE_DIR / "valid_native.tif",
    }
    missing = [str(p) for p in need.values() if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "native products missing -- run process_real_sar_pipeline.py first:\n  "
            + "\n  ".join(missing))

    out = {}
    for key, path in need.items():
        arr = tifffile.imread(str(path))
        out[key] = (arr > 0) if key == "valid" else arr.astype(np.float32)

    # ISRO's own swath mask (sri_ma > 0). Written by process_real_sar_pipeline.py
    # alongside valid_native.tif. It is the swath the beam was POINTED at, which
    # is 2.28x wider than the amplitude that came back -- see the two-mask model
    # in that script's docstring. Optional so an older data/ still renders.
    fp_path = NATIVE_DIR / "footprint_native.tif"
    if fp_path.exists():
        out["footprint"] = tifffile.imread(str(fp_path)) > 0
        out["footprint_source"] = "native/footprint_native.tif (ISRO sri_ma > 0)"
    else:
        out["footprint"] = out["valid"]
        out["footprint_source"] = ("footprint_native.tif absent -- falling back to the "
                                   "amplitude mask; re-run process_real_sar_pipeline.py")

    shapes = {k: v.shape for k, v in out.items() if isinstance(v, np.ndarray)}
    if len(set(shapes.values())) != 1:
        raise ValueError(f"native rasters disagree on shape: {shapes}")
    return out


def resolve_spacing() -> tuple[tuple[float, float], str]:
    """
    Ground spacing from the product's own GeoTIFF GeoKeys via P0
    (app/ingestion/sar_geometry). Falls back to the documented 25 m only if the
    PDS4 bundle is not on this host, and says so out loud when it does.
    """
    if LH_TIF.exists() and LH_XML.exists():
        try:
            from app.ingestion.sar_geometry import read_geotiff_frame
            frame = read_geotiff_frame(LH_TIF, LH_XML)
            mpp_line, mpp_sample = frame.metres_per_pixel()
            return (float(mpp_line), float(mpp_sample)), f"GeoTIFF GeoKeys of {LH_TIF.name}"
        except Exception as exc:
            print(f"  ! could not read the frame ({exc}); falling back to {FALLBACK_SPACING}")
    return FALLBACK_SPACING, "FALLBACK CONSTANT -- PDS4 bundle not present on this host"


def load_geodetic_frame() -> dict:
    """The P0 geodetic frame, copied into the manifest so the UI never has to
    hardcode bounds, latitudes or the projection."""
    meta_path = DFSAR_DIR / "metadata_real.json"
    if not meta_path.exists():
        return {"unavailable": f"{meta_path} not found -- run process_real_sar_pipeline.py"}
    with open(meta_path) as f:
        return json.load(f).get("geodetic_frame", {})

# ---------------------------------------------------------------------------
# M2 -- gradient spacing. Printed as a before/after table because "I fixed the
# spacing" is a claim; a percentile table is evidence.
# ---------------------------------------------------------------------------

def m2_before_after(dem: np.ndarray, spacing: tuple[float, float], mask: np.ndarray) -> dict:
    print("\n" + "-" * 78)
    print(f"M2  gradient spacing: {LEGACY_SPACING_M} m (uniform, hardcoded)  ->  "
          f"{spacing[0]} m / {spacing[1]} m (line / sample, from the frame)")
    print("-" * 78)

    before = compute_terrain(dem, (LEGACY_SPACING_M, LEGACY_SPACING_M))
    after = compute_terrain(dem, spacing)

    for key, unit in (("slope_deg", "deg"), ("hazard", "0..1"), ("roughness_m", "m")):
        print(f"\n  {key}  ({unit})")
        print(percentile_table("BEFORE", before[key], mask))
        print(percentile_table("AFTER", after[key], mask))

    ratio = LEGACY_SPACING_M / spacing[1]
    print(f"\n  Slope scales with 1/spacing, so the {ratio:.0f}x finer spacing makes every "
          f"gradient {ratio:.0f}x steeper.")
    print("  Roughness is a windowed elevation standard deviation and therefore "
          "SPACING-INVARIANT:")
    print("  the two roughness rows above are identical on purpose. This change did "
          "not improve roughness.")
    print("  config.py thresholds are deliberately NOT retuned here (handoff v3/v4).")

    summary = {
        "legacy_spacing_m": LEGACY_SPACING_M,
        "frame_spacing_m": {"line": spacing[0], "sample": spacing[1]},
        "slope_deg_p50": {"before": round(float(np.percentile(before["slope_deg"][mask], 50)), 4),
                          "after": round(float(np.percentile(after["slope_deg"][mask], 50)), 4)},
        "hazard_p50": {"before": round(float(np.percentile(before["hazard"][mask], 50)), 4),
                       "after": round(float(np.percentile(after["hazard"][mask], 50)), 4)},
        "roughness_m_p50": {"before": round(float(np.percentile(before["roughness_m"][mask], 50)), 4),
                            "after": round(float(np.percentile(after["roughness_m"][mask], 50)), 4)},
        "note": "roughness is spacing-invariant; before == after is correct, not a bug",
    }
    del before
    return {"terrain": after, "summary": summary}


# ---------------------------------------------------------------------------
# the layer table
# ---------------------------------------------------------------------------

def dem_provenance() -> dict:
    """The elevation sidecar written by ingest_lola_polar_dem.py, or a hard stop.

    Four of the six layers are terrain-derived, so their provenance string is
    only as good as this file. Refusing to render without it is deliberate: the
    previous failure mode was a manifest that said one thing while the pixels
    said another.
    """
    if not LOLA_SIDECAR.is_file():
        raise FileNotFoundError(
            f"{LOLA_SIDECAR} missing. The terrain layers cannot state their own "
            "provenance without it. Run:\n"
            "    python backend/scripts/ingest_lola_polar_dem.py\n"
            "    python backend/scripts/process_real_sar_pipeline.py"
        )
    p = json.loads(LOLA_SIDECAR.read_text())
    for key in ("provenance", "native_metres_per_pixel", "output_metres_per_pixel"):
        if key not in p:
            raise KeyError(f"{LOLA_SIDECAR.name} has no '{key}'; re-run the ingest.")
    banned = ("synthetic", "placeholder", "analytic", "unknown", "unavailable")
    hits = [w for w in banned if w in str(p["provenance"]).lower()]
    if hits:
        raise ValueError(
            f"the elevation provenance string {p['provenance']!r} contains {hits}, "
            "so the frontend would badge these layers as placeholders. Fix the "
            "ingest, do not weaken the check here."
        )
    return p


DEM_PROV = dem_provenance()
DEM_NOTE = (
    f"derived from data/pradan/native/dem_native_synthetic.tif, which despite its "
    f"filename now holds {DEM_PROV['provenance']} — real LOLA topography. The "
    f"filename is retained only so existing consumers keep working. Elevation was "
    f"measured at {DEM_PROV['native_metres_per_pixel']:g} m posts and resampled to "
    f"{DEM_PROV['output_metres_per_pixel']:g} m, so this layer carries no relief "
    f"finer than {DEM_PROV['native_metres_per_pixel']:g} m."
)


def build_layers(src: dict, terrain: dict, hillshade: np.ndarray,
                 illumination: np.ndarray) -> list[dict]:
    """
    Six layers, each with an explicit mask, stretch mode, colormap and honest
    provenance string. `mask` is what alpha is built from AND what the stretch
    is fitted over -- one mask, so the picture and the numbers cannot disagree.
    """
    valid = src["valid"]
    dense = np.ones_like(valid, dtype=bool)
    return [
        {"id": "hillshade", "label": "Surface Relief", "data": hillshade, "mask": dense,
         "stretch": "linear", "colormap": "grayscale", "opaque_alpha": 255,
         "provenance": "measured-topography",
         "sources": ["native/dem_native_synthetic.tif"],
         "detail": "Horn hillshade, sun 30 deg altitude / 315 deg azimuth; " + DEM_NOTE},

        {"id": "dem_elevation", "label": "Elevation (DEM)", "data": src["dem"], "mask": dense,
         "stretch": "linear", "colormap": "viridis", "opaque_alpha": 255,
         "provenance": "measured-topography",
         "sources": ["native/dem_native_synthetic.tif"],
         "detail": f"Elevation in metres — {DEM_PROV['elevation_datum']} " + DEM_NOTE},

        {"id": "hazard_map", "label": "Terrain Hazards", "data": terrain["hazard"], "mask": dense,
         "stretch": "linear", "colormap": "magma", "opaque_alpha": 255,
         "provenance": "measured-topography",
         "sources": ["native/dem_native_synthetic.tif"],
         "detail": "(0.50*clip(slope/20 deg) + 0.30*clip(roughness/50 m)) / 0.80 — the "
                   "SAME app/modules/module_d_terrain.compute_hazard_score that produces "
                   "the hazard figure in the stat panel, so the picture and the number "
                   "have one definition. 20 deg is MAX_TRAVERSABLE_SLOPE_DEG, the rover "
                   "tilt limit; the boulder term is weighted to zero because there is no "
                   "OHRC product for this frame, so hazard is slope + roughness, "
                   "renormalised. magma replaces the old JET colormap whose non-monotonic "
                   "lightness invented false hazard edges. "
                   f"Slope is a {DEM_PROV['native_metres_per_pixel']:g} m-post quantity, "
                   "so the roughness divisor is a display scaling, not a threshold "
                   "validated against this terrain. " + DEM_NOTE},

        {"id": "illumination", "label": "Shadowed Areas", "data": illumination, "mask": dense,
         "stretch": "linear", "colormap": "inferno", "opaque_alpha": 255,
         "provenance": "modelled-from-measured-topography",
         "sources": ["native/dem_native_synthetic.tif"],
         "detail": "hillshade * normalised elevation ^1.2. NOT a solar-geometry PSR product "
                   "-- no true cold traps are computed in this build, and this is a shading "
                   "heuristic rather than an illumination measurement. The topography under "
                   "it is real: " + DEM_NOTE},

        {"id": "cpr_heatmap", "label": "Radar Signals (CPR)", "data": src["cpr"], "mask": valid,
         "stretch": "log", "colormap": "turbo", "opaque_alpha": 235,
         "provenance": "measured-radar",
         "sources": ["native/cpr_native.tif", "native/valid_native.tif"],
         "detail": "Circular Polarisation Ratio, sigma_sc / sigma_oc, from the calibrated "
                   "Chandrayaan-2 DFSAR sri products. Alpha and the stretch both follow the "
                   "amplitude mask (15.64% of the frame, 8.75 km ribbon), NOT ISRO's wider "
                   "sri_ma swath mask (35.63%, 19.25 km): 56.11% of that swath carries "
                   "literal integer zero amplitude, and cpr there would be a fabricated 0.0. "
                   "The swath is drawn as an outline instead -- see footprint.swath."},

        {"id": "dop_heatmap", "label": "Degree of Polarisation", "data": src["dop"], "mask": valid,
         "stretch": "log", "colormap": "cividis", "opaque_alpha": 235,
         "provenance": "measured-radar",
         "sources": ["native/dop_native.tif", "native/valid_native.tif"],
         "detail": "Degree of polarisation, |S1| / S0, from the same calibrated products, "
                   "on the same amplitude mask as cpr_heatmap."},
    ]

# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------

def render_layer(spec: dict, out_dir: Path, show_histograms: bool) -> dict:
    name, data, mask = spec["id"], spec["data"], spec["mask"]
    print("\n" + "=" * 78)
    print(f"LAYER  {name}   [{spec['provenance']}]")
    print("=" * 78)

    st = fit_stretch(data, mask, spec["stretch"])
    print(f"  stretch      {describe_stretch(st)}")
    print(f"  fitted over  {st['valid_pixels']:,} px "
          f"({100.0 * st['valid_pixels'] / data.size:.2f}% of the frame)")

    if show_histograms:
        print("\n  BEFORE -- raw values over the pixels the stretch was fitted on")
        print(histogram_table(name, data, mask))

    u8 = (apply_stretch(data, st) * 255.0).round().astype(np.uint8)

    if show_histograms:
        print("\n  AFTER -- what the 8-bit image actually contains")
        print(u8_distribution(name, u8, mask))

    rgb = colorize(u8, spec["colormap"])
    alpha = np.where(mask, np.uint8(spec["opaque_alpha"]), np.uint8(0))
    rgba = np.dstack([rgb, alpha])
    del u8

    t0 = time.time()
    full_path, full_bytes = save_rgba(out_dir / f"{name}.webp", rgba)
    prev_path, prev_bytes = save_rgba(out_dir / f"{name}.preview.webp",
                                      make_preview(rgb, alpha, PREVIEW_WIDTH))
    dt = time.time() - t0
    del rgb, alpha, rgba

    h, w = data.shape
    ph = max(1, int(round(h * PREVIEW_WIDTH / float(w))))
    print(f"\n  wrote        {full_path.name}  {w}x{h}  {full_bytes / 1024:,.0f} KiB")
    print(f"               {prev_path.name}  {PREVIEW_WIDTH}x{ph}  {prev_bytes / 1024:,.0f} KiB   "
          f"({dt:.1f} s)")

    vmin, vmax = stretch_range(st)
    covers_frame = bool(mask.all())
    return {
        "id": name,
        "label": spec["label"],
        "file": full_path.name,
        "preview": prev_path.name,
        "width": int(w),
        "height": int(h),
        "bytes": int(full_bytes),
        "preview_bytes": int(prev_bytes),
        "preview_width": PREVIEW_WIDTH,
        "preview_height": int(ph),
        "colormap": spec["colormap"],
        "stretch": {
            "mode": st["mode"],
            "expression": describe_stretch(st),
            "fitted_over_pixels": st["valid_pixels"],
            "fitted_over_fraction": round(st["valid_pixels"] / float(data.size), 6),
        },
        "vmin": round(vmin, 8),
        "vmax": round(vmax, 8),
        "alpha_opaque": spec["opaque_alpha"],
        "transparent_where": ("nowhere -- this layer covers the whole frame"
                              if covers_frame
                              else "no DFSAR amplitude (native/valid_native.tif == 0)"),
        "provenance": spec["provenance"],
        "source_rasters": spec["sources"],
        "description": spec["detail"],
    }

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    global PREVIEW_WIDTH
    ap = argparse.ArgumentParser(
        description="Render one lossless image per map layer into "
                    "frontend/public/layers/, replacing the tile pyramid.")
    ap.add_argument("--out", type=Path, default=OUT_DIR, help=f"output dir (default {OUT_DIR})")
    ap.add_argument("--preview-width", type=int, default=PREVIEW_WIDTH)
    ap.add_argument("--no-histograms", action="store_true",
                    help="skip the before/after evidence tables")
    ap.add_argument("--only", nargs="*", default=None, help="render only these layer ids")
    ap.add_argument("--craters", nargs="*", default=["faustini"],
                    help="craters whose analysis JSON to regenerate alongside the imagery "
                         "(default faustini)")
    ap.add_argument("--no-analysis", action="store_true",
                    help="skip regenerating public/analysis/<crater>.json — only do this if you "
                         "are certain the numbers still describe these exact images")
    args = ap.parse_args()

    PREVIEW_WIDTH = int(args.preview_width)

    t_start = time.time()
    print("=" * 78)
    print("RENDER SINGLE-IMAGE MAP LAYERS  (no pyramid, no tiles, no per-tile stretch)")
    print("=" * 78)

    src = load_inputs()
    lines, samples = src["valid"].shape
    valid = src["valid"]
    dense = np.ones_like(valid, dtype=bool)

    spacing, spacing_src = resolve_spacing()
    height_units = CRS_WIDTH_UNITS * lines / float(samples)
    metres_per_unit = samples * spacing[1] / CRS_WIDTH_UNITS

    print(f"\nnative grid    {lines} lines x {samples} samples = "
          f"{lines * samples / 1e6:.1f} MP")
    print(f"ground spacing {spacing[0]} m/line x {spacing[1]} m/sample")
    print(f"  source       {spacing_src}")
    print(f"extent         {lines * spacing[0] / 1000:.2f} km across-track x "
          f"{samples * spacing[1] / 1000:.2f} km along-track")
    print(f"Leaflet extent {CRS_WIDTH_UNITS:.0f} x {height_units:.4f} CRS units "
          f"({metres_per_unit:.3f} m per unit)")
    print(f"native zoom    {math.log2(samples / CRS_WIDTH_UNITS):.4f} "
          "(where 1 screen px == 1 image px)")

    valid_frac = float(valid.mean())
    footprint = src["footprint"]
    fp_frac = float(footprint.mean())
    ring, thick, cols = footprint_ring_normalised(valid)
    sw_ring, sw_thick, sw_cols = footprint_ring_normalised(footprint)
    px_km2 = spacing[0] * spacing[1] / 1e6

    print(f"\n--- two masks (see process_real_sar_pipeline.py docstring) ---")
    print(f"  swath footprint  {src['footprint_source']}")
    print(f"                   {int(footprint.sum()):>11,d} px  {fp_frac * 100:6.2f} %  "
          f"{footprint.sum() * px_km2:8.1f} km2")
    print(f"    ribbon         median {np.median(sw_thick):.0f} px = "
          f"{np.median(sw_thick) * spacing[0] / 1000:.2f} km "
          f"(p10 {np.percentile(sw_thick, 10):.0f}, p90 {np.percentile(sw_thick, 90):.0f})"
          "   vs nominal isda:swath 19.65 km")
    print(f"  amplitude        (LH>0) & (LV>0)")
    print(f"                   {int(valid.sum()):>11,d} px  {valid_frac * 100:6.2f} %  "
          f"{valid.sum() * px_km2:8.1f} km2")
    print(f"    ribbon         median {np.median(thick):.0f} px = "
          f"{np.median(thick) * spacing[0] / 1000:.2f} km "
          f"(p10 {np.percentile(thick, 10):.0f}, p90 {np.percentile(thick, 90):.0f})")
    print(f"  amplitude / footprint = "
          f"{valid.sum() / max(footprint.sum(), 1) * 100:.2f} % returned signal")
    print(f"  {(1 - valid_frac) * 100:.2f}% of the frame becomes transparent on the "
          "radar layers -- alpha follows amplitude, never the wider swath, because "
          "cpr/dop are 0.0 outside it and 0.0 there would be fabricated")
    print(f"  rings            swath {len(sw_ring)} vertices / amplitude {len(ring)} "
          f"vertices, every {cols[1] - cols[0] if len(cols) > 1 else 0} samples")

    m2 = m2_before_after(src["dem"], spacing, dense)
    terrain = m2["terrain"]

    hazard_table, hazard_delta = hazard_formula_before_after(
        terrain["slope_deg"], terrain["roughness_m"], dense)
    print(hazard_table)

    hillshade = compute_hillshade(src["dem"], spacing)
    illumination = np.clip(
        hillshade * ((src["dem"] - src["dem"].min()) / (np.ptp(src["dem"]) + 1e-6)) ** 1.2,
        0.0, 1.0).astype(np.float32)

    specs = build_layers(src, terrain, hillshade, illumination)
    if args.only:
        specs = [s for s in specs if s["id"] in set(args.only)]
        print(f"\n(--only) rendering {[s['id'] for s in specs]}")

    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    entries = [render_layer(s, out_dir, not args.no_histograms) for s in specs]

    manifest = {
        "schema": "lunar-ice/layers-manifest/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator": "backend/scripts/render_layers.py",
        "replaces": "backend/scripts/generate_tiles.py + backend/tiles/faustini/** "
                    "(tile pyramid: ~331 tiles/layer, per-tile normalisation, visible seams)",
        "product_id": f"{PRODUCT_STEM}_d_sri_xx_cp_xx_d18",
        "instrument": "Chandrayaan-2 DFSAR (L-band, hybrid circular polarimetry)",
        "observation_date": "2020-08-08T20:11:54.198Z",
        "native": {
            "lines": int(lines),
            "samples": int(samples),
            "megapixels": round(lines * samples / 1e6, 3),
            "metres_per_pixel": {"line": spacing[0], "sample": spacing[1]},
            "metres_per_pixel_source": spacing_src,
            "extent_km": {"across_track": round(lines * spacing[0] / 1000, 3),
                          "along_track": round(samples * spacing[1] / 1000, 3)},
        },
        # Everything the frontend needs to place the images. The map reads these
        # instead of hardcoding bounds -- the old code carried BOUND_H / BOUND_W
        # literals that had to be edited by hand whenever the raster changed.
        "crs": {
            "type": "L.CRS.Simple",
            "width_units": CRS_WIDTH_UNITS,
            "height_units": round(height_units, 6),
            "bounds": [[0.0, 0.0], [round(height_units, 6), CRS_WIDTH_UNITS]],
            "metres_per_unit": round(metres_per_unit, 6),
            "native_zoom": round(math.log2(samples / CRS_WIDTH_UNITS), 6),
            "note": "bounds are [[south, west], [north, east]] for L.imageOverlay. "
                    "The raster fills the whole extent, so image row 0 is at north "
                    "= height_units and the last row is at south = 0.",
        },
        "footprint": {
            # ---- amplitude ribbon: unchanged keys, unchanged meaning ----
            # alpha on the radar layers and every stretch follow THIS mask.
            "valid_fraction": round(valid_frac, 6),
            "padding_fraction": round(1.0 - valid_frac, 6),
            "area_km2": round(float(valid.sum() * px_km2), 2),
            "ribbon_thickness_px": {"median": int(np.median(thick)),
                                    "p10": int(np.percentile(thick, 10)),
                                    "p90": int(np.percentile(thick, 90))},
            "ribbon_thickness_km": {"median": round(float(np.median(thick)) * spacing[0] / 1000, 3),
                                    "mean": round(float(thick.mean()) * spacing[0] / 1000, 3)},
            "ring_unit_coords": ring,
            "ring_note": "[fy_from_top, fx], both 0..1 of the raster. "
                         "lat = height_units * (1 - fy), lng = width_units * fx.",
            # ---- ISRO's swath footprint: the beam's pointed coverage ----
            "swath": {
                "source": src["footprint_source"],
                "fraction": round(fp_frac, 6),
                "area_km2": round(float(footprint.sum() * px_km2), 2),
                "ribbon_thickness_px": {"median": int(np.median(sw_thick)),
                                        "p10": int(np.percentile(sw_thick, 10)),
                                        "p90": int(np.percentile(sw_thick, 90))},
                "ribbon_thickness_km": {
                    "median": round(float(np.median(sw_thick)) * spacing[0] / 1000, 3),
                    "mean": round(float(sw_thick.mean()) * spacing[0] / 1000, 3)},
                "nominal_swath_km": 19.65,
                "ring_unit_coords": sw_ring,
                "amplitude_fraction_of_swath": round(
                    float(valid.sum() / max(footprint.sum(), 1)), 6),
                "note": "ISRO's own sri_ma mask, byte-identical to inc>0 (IoU 100.00 %) "
                        "and corroborated by the geolocation grid (333,614 / 937,296 "
                        "non-fill nodes = 35.59 %). This is where the beam was POINTED. "
                        "It is drawn as an outline only -- no radar colour is painted "
                        "inside it beyond the amplitude ribbon, because 56.11 % of it "
                        "carries literal integer zero amplitude.",
            },
            "measured_by": "backend/scripts/render_layers.py :: footprint_ring_normalised "
                           "(same trace as print_footprint_polygon.py); mask evidence in "
                           "backend/scripts/diagnose_valid_mask.py",
            "evidence": "The narrow ribbon is the delivered data, not a processing loss "
                        "and not a threshold chosen here. Tested three ways: (1) lh>0, "
                        "lv>0, their AND and their OR all measure 15.64 % -- the AND "
                        "discards 4 px of 2,337,090, so it is not the cause; (2) ISRO's "
                        "sri_ma mask does say 35.63 %, but 2,987,459 px (56.11 % of it) "
                        "hold integer zero amplitude; (3) the ground-range gri product "
                        "spans 786 x 25 m = 19,650 m, exactly isda:swath, and its "
                        "amplitude is still a single contiguous 8.80 km run per line with "
                        "zero interior holes on 265/265 sampled lines. Areas close both "
                        "ways: amplitude 1501.2 km2 (gri) vs 1460.7 km2 (sri) = +2.77 %; "
                        "footprint 3239.8 km2 vs 3327.8 km2 = -2.65 %. Cropping cannot "
                        "fix it either: the bounding box of a diagonal ribbon is "
                        "1783 x 6606 and still only 19.84 % valid.",
        },
        "geodetic_frame": load_geodetic_frame(),
        "m2_gradient_spacing": m2["summary"],
        "hazard_single_source": hazard_delta,
        "colormaps_note": "COLORMAP_JET is not used anywhere. Its lightness is "
                          "non-monotonic, which manufactures edges in smooth data; on a "
                          "hazard map that reads as a cliff that is not there.",
        "layers": entries,
    }

    manifest_path = out_dir / "layers.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print("\n" + "=" * 78)
    print("PAYLOAD  (one request per layer; the frontend CDN serves these, not Render)")
    print("=" * 78)
    print(f"  {'layer':16s} {'full KiB':>10s} {'preview KiB':>12s}  colormap    provenance")
    tot = prev_tot = 0
    for e in entries:
        tot += e["bytes"]
        prev_tot += e["preview_bytes"]
        print(f"  {e['id']:16s} {e['bytes'] / 1024:10,.0f} {e['preview_bytes'] / 1024:12,.0f}"
              f"  {e['colormap']:10s}  {e['provenance']}")
    print(f"  {'TOTAL':16s} {tot / 1024:10,.0f} {prev_tot / 1024:12,.0f}"
          f"   = {tot / 1048576:.2f} MiB all layers, "
          f"{prev_tot / 1024:,.0f} KiB for first paint")
    print(f"\nmanifest  {manifest_path}  ({manifest_path.stat().st_size / 1024:.1f} KiB)")
    print(f"done in {time.time() - t_start:.1f} s")
    print("\nREAL:      cpr_heatmap, dop_heatmap  (calibrated DFSAR, alpha = measured footprint)")
    print(f"REAL:      hillshade, dem_elevation, hazard_map  "
          f"({DEM_PROV['provenance']})")
    print(f"MODELLED:  illumination  (shading heuristic over the real DEM, not a "
          f"solar-geometry PSR product)")
    print(f"CAVEAT:    terrain layers carry no relief finer than "
          f"{DEM_PROV['native_metres_per_pixel']:g} m, the LOLA native post spacing.")

    # ------------------------------------------------------------------
    # The numbers ship with the pictures. One command regenerates both, so
    # the imagery and the headline verdict can never again describe
    # different data — which is exactly what happened when the map showed
    # the measured swath while the card showed a seeded DEMO run.
    # ------------------------------------------------------------------
    if args.no_analysis:
        print("\n!! --no-analysis: public/analysis/*.json was NOT regenerated. The verdict "
              "card may now describe different data than these images.")
    else:
        from build_analysis import emit as emit_analysis
        print("\n" + "=" * 78)
        print("PRECOMPUTED ANALYSIS  (same rasters, same run — the numbers behind the images)")
        print("=" * 78)
        for crater in args.craters:
            emit_analysis(crater)


if __name__ == "__main__":
    main()






