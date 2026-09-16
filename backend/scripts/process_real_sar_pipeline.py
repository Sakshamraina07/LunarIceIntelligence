"""
STAGE 2 & 3 -- Chandrayaan-2 DFSAR calibration and map/analysis product build.

What is REAL in here
--------------------
  * The LH / LV amplitudes and the incidence-angle raster are the calibrated
    ISRO L2-SELENOREF (`sri`) products, read straight from the PDS4 bundle.
  * The radiometric calibration constant and both channel gain imbalances are
    now READ FROM THE PDS4 LABEL instead of being hardcoded.
  * The SWATH FOOTPRINT is now ISRO's own `sri_ma` mask product, not a threshold
    invented here. See the mask model below.
  * Sigma0, the 5x5 multi-look, the Stokes pair (S0, S1), sigma_sc / sigma_oc,
    CPR and DOP are computed from those numbers. That maths is unchanged from
    the previous revision on purpose.
  * Georeferencing is the closed-form south-polar-stereographic transform
    carried in the product's own GeoTIFF GeoKeys (see app/ingestion/sar_geometry).

TWO MASKS, NOT ONE -- measured by backend/scripts/diagnose_valid_mask.py
------------------------------------------------------------------------
A single `valid` mask was conflating "where the beam was pointed" with "where
signal came back". Those differ by a factor of 2.3 in this product:

  footprint  ISRO sri `ma` > 0    5,324,545 px  35.63 %  ribbon p50 19.25 km
             Byte-identical to `inc > 0` (IoU 100.00 %) and corroborated by the
             geolocation grid (333,614 / 937,296 non-fill nodes = 35.59 %).
             Closes to 2.7 % against the label's isda:swath = 19,650 m.

  amplitude  (lh > 0) & (lv > 0)  2,337,086 px  15.64 %  ribbon p50  8.75 km
             Fully contained in the footprint (0 px outside).

The gap is 2,987,459 px -- 19.99 % of the frame, 56.11 % of ISRO's own mask --
where ISRO flags the pixel as imaged and the amplitude rasters hold literal
integer zero. That is a property of the DELIVERED DATA, not of the geocoding:
the ground-range `gri` product is 786 samples x 25 m = 19,650 m across, exactly
the nominal swath, and its amplitude is still only a single contiguous
8.80 km-wide run per line (zero interior holes on 265/265 sampled lines). The
areas close both ways: amplitude 1501.2 km2 (gri) vs 1460.7 km2 (sri), +2.77 %;
footprint 3239.8 km2 vs 3327.8 km2, -2.65 %.

So `footprint` drives geometry, the swath outline and the honest coverage
statement, while `amplitude` drives alpha and EVERY stretch and statistic.
cpr/dop are `np.where(s0 > 0, ..., 0.0)`, so widening the statistical mask to
`ma > 0` would write a fabricated 0.0 over a fifth of the map.

What is still SYNTHETIC in here
-------------------------------
  * Nothing in the rasters. THE DEM IS NOW REAL: `*_dem.tif` / `*_lola_dem.tif`
    carry LOLA polar topography, resampled onto this frame by
    backend/scripts/ingest_lola_polar_dem.py, which reproduces the LOLA
    product's own DERIVED_MINIMUM / DERIVED_MAXIMUM from raw bytes before it
    writes anything. The analytic-placeholder DEM that used to be built here
    from Gaussians and sinusoids is deleted, with no fallback: if the LOLA frame
    is absent this pipeline stops rather than substituting a plausible surface.
  * The number that matters for every terrain quantity is the LOLA product's
    NATIVE post spacing -- read from ldem_frame_25m.provenance.json, 20 m for
    LDEM_80S_20M -- not the 25 m grid it is resampled onto. Slope, roughness
    and hazard here are native-post quantities. They
    are labelled with the spacing they were differenced at, and the sidecar
    `data/pradan/lola/ldem_frame_25m.provenance.json` states both numbers.
  * `native/dem_native.tif` keeps its filename for backend
    compatibility only. Its contents are measured; see `product_provenance`.


Outputs
-------
  data/pradan/native/   full-resolution 2258 x 6618 products -> tile pyramid
  data/pradan/dfsar/    analysis-grid products (existing filenames, unchanged
                        shape) -> consumed by app/services/mission_service.py
  data/pradan/dem/      analysis-grid DEM, LOLA-derived (existing filenames)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import tifffile

BASE_DIR = Path(__file__).resolve().parents[2]        # -> repository root
BACKEND_DIR = Path(__file__).resolve().parents[1]     # -> backend/
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ingestion.sar_geometry import (  # noqa: E402
    load_geolocation_grid,
    parse_calibration,
    parse_geolocation_grid_spec,
    read_geotiff_frame,
    validate_against_grid,
)

DATA_DIR = BASE_DIR / "data" / "pradan"
RAW_DIR = DATA_DIR / "raw" / "data" / "calibrated" / "20200808"
GEOM_DIR = DATA_DIR / "raw" / "geometry" / "calibrated" / "20200808"

OUT_NATIVE_DIR = DATA_DIR / "native"
OUT_DFSAR_DIR = DATA_DIR / "dfsar"
OUT_DEM_DIR = DATA_DIR / "dem"
OUT_OHRC_DIR = DATA_DIR / "ohrc"

# Measured topography on this exact frame, written by ingest_lola_polar_dem.py.
LOLA_FRAME_DEM = DATA_DIR / "lola" / "ldem_frame_25m.tif"
LOLA_FRAME_SIDECAR = DATA_DIR / "lola" / "ldem_frame_25m.provenance.json"

PRODUCT_STEM = "ch2_sar_ncxl_20200808t201154198"
MULTILOOK_KERNEL = 5

# The analysis grid the existing backend already reads. mission_service.py loads
# these files at a fixed square shape, so it is deliberately left alone here:
# changing it is a separate, larger change than this phase.
DEFAULT_ANALYSIS_SIZE = 2048


def _save(path: Path, arr: np.ndarray) -> None:
    """Write a GeoTIFF, using zlib if this tifffile build supports it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        tifffile.imwrite(str(path), arr, compression="zlib")
    except Exception:
        tifffile.imwrite(str(path), arr)


def _percentiles(a: np.ndarray, qs=(0, 1, 5, 25, 50, 75, 95, 99, 100)) -> dict:
    return {f"p{q}": round(float(np.percentile(a, q)), 6) for q in qs}


def _stat_block(name: str, arr: np.ndarray, mask: np.ndarray) -> dict:
    sub = arr[mask]
    if sub.size == 0:
        return {"name": name, "valid_pixels": 0}
    return {
        "name": name,
        "valid_pixels": int(sub.size),
        "min": round(float(sub.min()), 6),
        "max": round(float(sub.max()), 6),
        "mean": round(float(sub.mean()), 6),
        "median": round(float(np.median(sub)), 6),
        "std": round(float(sub.std()), 6),
        "percentiles_over_valid": _percentiles(sub),
    }


def _ribbon(mask: np.ndarray, px_m: float, step: int = 32, min_run: int = 8) -> dict:
    """Per-column vertical extent of a mask, in native lines and km."""
    runs = []
    for c in range(0, mask.shape[1], step):
        idx = np.flatnonzero(mask[:, c])
        if idx.size >= min_run:
            runs.append(idx.size)
    a = np.asarray(runs, np.float64)
    if a.size == 0:
        return {"columns_scored": 0}
    return {
        "columns_scored": int(a.size),
        "p10_px": round(float(np.percentile(a, 10)), 1),
        "p50_px": round(float(np.percentile(a, 50)), 1),
        "p90_px": round(float(np.percentile(a, 90)), 1),
        "p50_km": round(float(np.percentile(a, 50)) * px_m / 1000.0, 3),
        "mean_km": round(float(a.mean()) * px_m / 1000.0, 3),
    }


def _terrain_table(dem: np.ndarray, grid_px_m: float,
                   native_px_m: float | None,
                   title: str = "", sample_px_m: float | None = None) -> str:
    """Slope / roughness / hazard distribution of a DEM, labelled with its posts.

    Uses app/modules/module_d_terrain.py rather than re-deriving the maths, so
    these are the numbers the app itself computes. Boulder risk is passed as zero
    because there is no OHRC product for this frame; hazard here is therefore the
    slope+roughness part only, and is labelled as such.

    grid_px_m is the spacing of axis 0 (lines) of the array being differenced;
    sample_px_m is the spacing of axis 1 (samples), defaulting to grid_px_m when
    the grid is square-posted. native_px_m is the spacing the elevation was
    actually measured at. When grid and native differ, slope is a native_px_m
    quantity on a grid_px_m raster: the finer grid adds no relief, so the same
    terrain differenced at 25 m posts reads shallower than it would at 80 m
    posts. Both numbers are printed for exactly that reason.

    Anisotropy is now HANDLED rather than merely labelled: compute_terrain_metrics
    takes (metres_per_line, metres_per_sample) and hands them to np.gradient
    per axis. Previously it took one scalar applied to both axes, so on the
    square analysis grid (a 2.93:1 swath squashed into a square) every slope in
    this table was inflated on the across-sample axis by that ratio. The table
    now reports the terrain, not an upper bound on it.
    """
    from app.modules.module_d_terrain import (  # noqa: PLC0415
        compute_hazard_score, compute_terrain_metrics)

    spacing = (float(grid_px_m), float(sample_px_m if sample_px_m else grid_px_m))
    slope, _aspect, rough = compute_terrain_metrics(dem, spacing)
    hazard = compute_hazard_score(slope, rough, np.zeros_like(dem, np.float32))

    qs = (1, 5, 25, 50, 75, 90, 95, 99, 100)
    posts = (f"differenced at {grid_px_m:g} m grid posts"
             + (f"; elevation measured at {native_px_m:g} m posts"
                if native_px_m and native_px_m != grid_px_m else ""))
    head = f"{title}, " if title else ""
    out = [f"\n  --- {head}slope / roughness / hazard, {posts} ---"]
    if sample_px_m and abs(sample_px_m - grid_px_m) > 0.01:
        ratio = sample_px_m / grid_px_m
        out.append(
            f"  ANISOTROPIC GRID, HANDLED — {grid_px_m:.4g} m per line, "
            f"{sample_px_m:.4g} m per sample ({ratio:.2f}:1).\n"
            f"          np.gradient receives both spacings, so the across-sample\n"
            f"          gradient is no longer overstated by {ratio:.2f}x. These are "
            f"terrain slopes,\n"
            f"          not an upper bound. Hazard is slope+roughness only "
            f"(no OHRC boulder product).")
    for name, arr, unit in (("slope", slope, "deg"), ("roughness", rough, "m"),
                            ("hazard", hazard, "0-1")):
        pct = " ".join(f"p{q}={float(np.percentile(arr, q)):8.3f}" for q in qs)
        out.append(f"  {name:9s} [{unit:3s}] {pct}")
    out.append(f"  slope > 15 deg: {float((slope > 15.0).mean()) * 100:6.3f} %"
               f"   > 20 deg: {float((slope > 20.0).mean()) * 100:6.3f} %"
               f"   > 25 deg: {float((slope > 25.0).mean()) * 100:6.3f} %")
    out.append(f"  hazard > 0.5  : {float((hazard > 0.5).mean()) * 100:6.3f} %"
               f"   > 0.7  : {float((hazard > 0.7).mean()) * 100:6.3f} %"
               "   (slope+roughness only; no OHRC boulder term for this frame)")
    return "\n".join(out)


def load_lola_frame_dem(shape) -> tuple[np.ndarray, dict]:
    """Measured LOLA topography on this exact frame, or a hard stop.

    Written by backend/scripts/ingest_lola_polar_dem.py, which reproduces the
    product's own DERIVED_MINIMUM / DERIVED_MAXIMUM from raw bytes before it
    writes anything, and refuses to write at all if any output pixel would be
    NaN. There is deliberately no synthetic fallback here: a fallback is exactly
    how analytic placeholder topography survived four revisions of this pipeline
    while the filenames said `_lola_`. If the frame is missing, this stops.
    """
    if not LOLA_FRAME_DEM.is_file():
        raise SystemExit(
            f"\nFATAL: {LOLA_FRAME_DEM} not found.\n"
            "Elevation must come from LOLA. Run:\n"
            "    python backend/scripts/ingest_lola_polar_dem.py\n"
            "Nothing is written. There is no placeholder DEM to fall back to any\n"
            "more, on purpose — a plausible surface in the slot where a\n"
            "measurement belongs is the worst outcome available."
        )
    if not LOLA_FRAME_SIDECAR.is_file():
        raise SystemExit(
            f"\nFATAL: {LOLA_FRAME_DEM.name} exists but {LOLA_FRAME_SIDECAR.name}\n"
            "does not, so its provenance cannot be stated. Re-run the ingest."
        )

    dem = np.asarray(tifffile.imread(str(LOLA_FRAME_DEM)), dtype=np.float32)
    prov = json.loads(LOLA_FRAME_SIDECAR.read_text())

    if dem.shape != tuple(shape):
        raise SystemExit(
            f"\nFATAL: LOLA frame is {dem.shape}, DFSAR frame is {tuple(shape)}.\n"
            "These must be the same grid — the ingest reads its target shape from\n"
            "metadata_real.json, so a mismatch means one of the two was rebuilt\n"
            "without the other. Re-run the ingest. Nothing written."
        )
    if not np.isfinite(dem).all():
        n = int((~np.isfinite(dem)).sum())
        raise SystemExit(
            f"\nFATAL: {n:,} non-finite pixels in the LOLA frame. The ingest's own\n"
            "check 3.3 forbids this, so this file did not come from a clean run.\n"
            "Nothing written."
        )
    return dem, prov


def _boxcar(a: np.ndarray) -> np.ndarray:
    k = np.ones((MULTILOOK_KERNEL, MULTILOOK_KERNEL), np.float32) / float(MULTILOOK_KERNEL ** 2)
    return cv2.filter2D(a, -1, k)


def process_real_data(analysis_size: int = DEFAULT_ANALYSIS_SIZE,
                      write_native: bool = True,
                      write_analysis: bool = True) -> dict:
    print("=" * 78)
    print("STAGE 2 & 3 -- PROCESSING REAL CHANDRAYAAN-2 DFSAR DATA")
    print("=" * 78)

    lh_path = RAW_DIR / f"{PRODUCT_STEM}_d_sri_xx_cp_lh_d18.tif"
    lv_path = RAW_DIR / f"{PRODUCT_STEM}_d_sri_xx_cp_lv_d18.tif"
    in_path = RAW_DIR / f"{PRODUCT_STEM}_d_sri_in_cp_xx_d18.tif"
    label_path = RAW_DIR / f"{PRODUCT_STEM}_d_sri_xx_cp_xx_d18.xml"

    for p in (lh_path, lv_path, in_path, label_path):
        if not p.exists():
            raise FileNotFoundError(f"required PDS4 input missing: {p}")

    # --- 1. georeferencing + calibration, both read from the product ------
    frame = read_geotiff_frame(lh_path, label_path)
    cal = parse_calibration(label_path)
    grid_spec = grid = grid_check = None
    geom_xml = GEOM_DIR / f"{PRODUCT_STEM}_g_xxx_xx_cp_xx_d18.xml"
    grid_csv = GEOM_DIR / f"{PRODUCT_STEM}_g_sri_xx_cp_xx_d18.csv"
    if geom_xml.exists() and grid_csv.exists():
        grid_spec = parse_geolocation_grid_spec(geom_xml, "sri")
        grid = load_geolocation_grid(grid_csv, grid_spec)
        grid_check = validate_against_grid(frame, grid, grid_spec)

    print(f"\nGeoreferencing  {frame.projection}  R={frame.radius_m:.0f} m  k0={frame.scale_factor}")
    print(f"  native grid   {frame.shape[0]} lines x {frame.shape[1]} samples "
          f"@ {frame.pixel_size_m[1]} m x {frame.pixel_size_m[0]} m")
    print(f"  extent        {frame.shape[0] * frame.pixel_size_m[1] / 1000:.2f} km across-track "
          f"x {frame.shape[1] * frame.pixel_size_m[0] / 1000:.2f} km along-track")
    print(f"  max projection scale error {frame.stereographic_scale_error() * 100:.4f} %")
    if grid_check:
        print(f"  ISRO geolocation grid agreement: line rms "
              f"{grid_check['line_residual_px']['rms']} px / sample rms "
              f"{grid_check['sample_residual_px']['rms']} px -> {grid_check['verdict']}")

    K_db = cal["calibration_constant_db"]
    K_lin = 10.0 ** (K_db / 10.0)
    G_lh = cal["channels"]["LH"]["gain_imbalance"]
    G_lv = cal["channels"]["LV"]["gain_imbalance"]
    print(f"\nCalibration (from {cal['source']}): K={K_db} dB  G_LH={G_lh}  G_LV={G_lv}")

    # --- 2. load the calibrated rasters at native resolution --------------
    print("\nLoading raw SRI GeoTIFF arrays at native resolution...")
    lh = tifffile.imread(str(lh_path)).astype(np.float32)
    lv = tifffile.imread(str(lv_path)).astype(np.float32)
    inc = tifffile.imread(str(in_path)).astype(np.float32)
    print(f"  arrays {lh.shape} / {lv.shape} / {inc.shape}")
    if lh.shape != frame.shape:
        raise ValueError(f"array shape {lh.shape} disagrees with GeoTIFF frame {frame.shape}")

    # --- 2b. the two masks ------------------------------------------------
    # footprint: ISRO's own `sri_ma` mask product -- the swath the beam was
    # pointed at. Preferred over any threshold invented here. Falls back to the
    # incidence raster, which measures byte-identical (IoU 100.00 %).
    isro_mask_path = RAW_DIR / f"{PRODUCT_STEM}_d_sri_ma_cp_xx_d18.tif"
    if isro_mask_path.exists():
        ma = tifffile.imread(str(isro_mask_path))
        footprint = ma > 0
        footprint_source = f"ISRO {isro_mask_path.name} > 0"
        ma_values = {int(v): int(c) for v, c in zip(*np.unique(ma, return_counts=True))}
        del ma
    else:
        footprint = inc > 0
        footprint_source = "incidence raster > 0 (ISRO sri_ma product absent)"
        ma_values = None

    inc_footprint = inc > 0
    footprint_iou = float((footprint & inc_footprint).sum()
                          / max((footprint | inc_footprint).sum(), 1))

    # amplitude: pixels that actually recorded return. This is what every
    # stretch, statistic and alpha channel must be fitted over -- cpr/dop are
    # np.where(s0 > 0, ..., 0.0), so a wider statistical mask fabricates zeros.
    amplitude = (lh > 0) & (lv > 0)
    valid = amplitude          # name kept: downstream code and filenames use it

    px_area_km2 = (frame.pixel_size_m[0] * frame.pixel_size_m[1]) / 1e6
    print(f"\n--- swath footprint vs delivered amplitude ---")
    print(f"  footprint  {footprint_source}")
    print(f"             {footprint.sum():>11,d} px  {footprint.mean() * 100:6.2f} %  "
          f"{footprint.sum() * px_area_km2:8.1f} km2")
    print(f"  amplitude  (LH>0) & (LV>0)")
    print(f"             {amplitude.sum():>11,d} px  {amplitude.mean() * 100:6.2f} %  "
          f"{amplitude.sum() * px_area_km2:8.1f} km2")
    print(f"  amplitude / footprint = {amplitude.sum() / max(footprint.sum(), 1) * 100:.2f} % "
          "of the pointed swath returned signal")
    print(f"  IoU(footprint, inc>0) = {footprint_iou * 100:.2f} %  "
          "(two independent ISRO sources)")
    outside = int((amplitude & ~footprint).sum())
    print(f"  amplitude outside the footprint: {outside:,} px "
          f"({'contained, as expected' if outside == 0 else 'UNEXPECTED -- investigate'})")
    gap = int((footprint & ~amplitude).sum())
    print(f"  flagged imaged but amplitude == 0: {gap:,} px "
          f"({gap / max(footprint.sum(), 1) * 100:.2f} % of the footprint) "
          "-> left transparent, NOT filled with 0.0")
    if ma_values:
        print(f"  sri_ma distinct values: {ma_values}  (ISRO documents no semantics "
              "for 16 vs 128 in the label)")

    rows = np.flatnonzero(amplitude.any(axis=1))
    cols = np.flatnonzero(amplitude.any(axis=0))
    print(f"  amplitude bounding box: lines [{rows[0]}:{rows[-1]}], samples [{cols[0]}:{cols[-1]}]"
          f"  ({rows[-1] - rows[0]} x {cols[-1] - cols[0]})")
    frows = np.flatnonzero(footprint.any(axis=1))
    fcols = np.flatnonzero(footprint.any(axis=0))
    print(f"  footprint bounding box: lines [{frows[0]}:{frows[-1]}], samples [{fcols[0]}:{fcols[-1]}]"
          f"  ({frows[-1] - frows[0]} x {fcols[-1] - fcols[0]})")

    nominal_swath_m = None
    try:
        nominal_swath_m = float(frame.label.get("swath_m") or frame.label.get("swath") or 0) or None
    except (TypeError, ValueError):
        nominal_swath_m = None
    if nominal_swath_m is None:
        nominal_swath_m = 19650.0       # isda:swath, gri label

    ribbon_amp = _ribbon(amplitude, frame.pixel_size_m[1])
    ribbon_fp = _ribbon(footprint, frame.pixel_size_m[1])
    print(f"\n  ribbon thickness (nominal swath {nominal_swath_m / 1000:.2f} km)")
    print(f"    footprint  p50 {ribbon_fp['p50_px']:6.0f} px = {ribbon_fp['p50_km']:6.2f} km  "
          f"mean {ribbon_fp['mean_km']:6.2f} km  -> closes to "
          f"{abs(ribbon_fp['mean_km'] * 1000 / nominal_swath_m * 100 - 100):.1f} %")
    print(f"    amplitude  p50 {ribbon_amp['p50_px']:6.0f} px = {ribbon_amp['p50_km']:6.2f} km  "
          f"mean {ribbon_amp['mean_km']:6.2f} km")



    # --- 3. radiometric calibration: DN -> sigma0 (unchanged maths) -------
    sin_inc = np.sin(np.deg2rad(inc))
    del inc
    sigma0_lh = (lh ** 2 * sin_inc) / (K_lin * (G_lh ** 2))
    sigma0_lv = (lv ** 2 * sin_inc) / (K_lin * (G_lv ** 2))
    del lh, lv, sin_inc

    # --- 4. 5x5 boxcar multi-look, Stokes pair, CPR, DOP -----------------
    lh_smooth = _boxcar(sigma0_lh)
    lv_smooth = _boxcar(sigma0_lv)
    del sigma0_lh, sigma0_lv

    s0 = lh_smooth + lv_smooth
    s1 = lh_smooth - lv_smooth
    sqrt_lh = np.sqrt(np.maximum(lh_smooth, 0))
    sqrt_lv = np.sqrt(np.maximum(lv_smooth, 0))
    del lh_smooth, lv_smooth

    sigma_sc = 0.5 * (sqrt_lh - sqrt_lv) ** 2
    sigma_oc = 0.5 * (sqrt_lh + sqrt_lv) ** 2
    del sqrt_lh, sqrt_lv

    eps = 1e-8
    cpr = np.where(s0 > 0, sigma_sc / (sigma_oc + eps), 0.0).astype(np.float32)
    dop = np.clip(np.where(s0 > 0, np.abs(s1) / (s0 + eps), 0.0), 0.0, 1.0).astype(np.float32)
    del sigma_oc, s1

    print("\n--- Real Chandrayaan-2 radar metrics, native grid, over valid pixels only ---")
    stat_blocks = [_stat_block("cpr", cpr, valid), _stat_block("dop", dop, valid),
                   _stat_block("s0", s0, valid), _stat_block("sigma_sc", sigma_sc, valid)]
    for b in stat_blocks:
        if b["valid_pixels"]:
            print(f"  {b['name']:9s} min={b['min']:.6g}  max={b['max']:.6g}  "
                  f"mean={b['mean']:.6g}  median={b['median']:.6g}  p99={b['percentiles_over_valid']['p99']:.6g}")

    # --- 5. measured LOLA topography at native resolution -----------------
    print("\n[MEASURED] loading LOLA polar topography for this frame")
    dem_native, dem_prov = load_lola_frame_dem(frame.shape)
    dem_native_mpp = float(dem_prov.get("native_metres_per_pixel", 0.0)) or None
    print(f"  {LOLA_FRAME_DEM.name}  {dem_prov['provenance']}")
    print(f"  elevation {dem_native.min():.1f} .. {dem_native.max():.1f} m "
          f"(mean {dem_native.mean():.1f}); {dem_prov['elevation_datum']}")
    if dem_native_mpp:
        print(f"  native post spacing {dem_native_mpp:g} m, resampled onto this "
              f"{frame.pixel_size_m[0]:g} m grid "
              f"({dem_prov['resample_ratio']:g}x). Terrain quantities below are "
              f"{dem_native_mpp:g} m quantities.")
    print(_terrain_table(dem_native, frame.pixel_size_m[1], dem_native_mpp,
                         title="NATIVE FRAME (quote these)",
                         sample_px_m=frame.pixel_size_m[0]))

    # --- 6. native-resolution products, consumed by generate_tiles.py -----
    if write_native:
        OUT_NATIVE_DIR.mkdir(parents=True, exist_ok=True)
        print(f"\nWriting native {frame.shape[0]}x{frame.shape[1]} products to {OUT_NATIVE_DIR}")
        for name, arr in (("cpr_native.tif", cpr), ("dop_native.tif", dop),
                          ("s0_native.tif", s0), ("sigma_sc_native.tif", sigma_sc),
                          ("dem_native.tif", dem_native)):
            _save(OUT_NATIVE_DIR / name, arr)
            print(f"  {name}")
        _save(OUT_NATIVE_DIR / "valid_native.tif", valid.astype(np.uint8) * 255)
        print("  valid_native.tif      (amplitude mask: 255 = LH>0 & LV>0)")
        _save(OUT_NATIVE_DIR / "footprint_native.tif", footprint.astype(np.uint8) * 255)
        print("  footprint_native.tif  (ISRO swath mask: 255 = sri_ma > 0)")

    # --- 7. analysis-grid products, existing filenames and shape ----------
    # mission_service.py reads these at a fixed square shape, so the grid is
    # left exactly as the backend already expects. The honest per-axis ground
    # spacing for this grid is recorded in the metadata below.
    analysis = {}
    if write_analysis:
        tgt = (int(analysis_size), int(analysis_size))
        print(f"\nResampling to the existing analysis grid {tgt[0]}x{tgt[1]} "
              "(shape kept for backend compatibility)")
        def _rs(a):
            return cv2.resize(a, (tgt[1], tgt[0]), interpolation=cv2.INTER_AREA)
        analysis = {"cpr": _rs(cpr), "dop": _rs(dop), "s0": _rs(s0),
                    "sigma_sc": _rs(sigma_sc), "dem": _rs(dem_native),
                    "valid": _rs(valid.astype(np.float32)) > 0.5,
                    "footprint": _rs(footprint.astype(np.float32)) > 0.5}

        OUT_DFSAR_DIR.mkdir(parents=True, exist_ok=True)
        OUT_DEM_DIR.mkdir(parents=True, exist_ok=True)
        OUT_OHRC_DIR.mkdir(parents=True, exist_ok=True)

        # NOTE: `s3_real.tif` / `*_dfsar_s3.tif` hold sigma_sc, NOT Stokes S3.
        # The filenames are kept because the backend already reads them.
        for name, arr in (("cpr_real.tif", analysis["cpr"]),
                          ("dop_real.tif", analysis["dop"]),
                          ("s0_real.tif", analysis["s0"]),
                          ("s3_real.tif", analysis["sigma_sc"]),
                          ("ch2_sar_cpr.tif", analysis["cpr"]),
                          ("ch2_sar_dop.tif", analysis["dop"]),
                          ("faustini_dfsar_s0.tif", analysis["s0"]),
                          ("faustini_dfsar_s3.tif", analysis["sigma_sc"]),
                          ("shackleton_dfsar_s0.tif", analysis["s0"]),
                          ("shackleton_dfsar_s3.tif", analysis["sigma_sc"])):
            _save(OUT_DFSAR_DIR / name, arr)
        _save(OUT_DFSAR_DIR / "valid_real.tif", analysis["valid"].astype(np.uint8) * 255)
        _save(OUT_DFSAR_DIR / "footprint_real.tif", analysis["footprint"].astype(np.uint8) * 255)

        for name in ("real_dem.tif", "ch2_sar_dem.tif",
                     "faustini_lola_dem.tif", "shackleton_lola_dem.tif"):
            _save(OUT_DEM_DIR / name, analysis["dem"])
        print(f"  wrote 12 files to {OUT_DFSAR_DIR.name}/ and 4 to {OUT_DEM_DIR.name}/")

        # The analysis grid is what mission_service.py actually differences, so its
        # own distribution is reported too. It is a square resample of a 2.93:1
        # swath, so its two axes have different ground spacing; BOTH are passed
        # through to np.gradient now, and the ratio is still recorded in
        # analysis_grid below so the asymmetry stays visible in the metadata.
        a_line_mpp = frame.shape[0] * frame.pixel_size_m[1] / float(analysis_size)
        a_sample_mpp = frame.shape[1] * frame.pixel_size_m[0] / float(analysis_size)
        print(_terrain_table(analysis["dem"], a_line_mpp, dem_native_mpp,
                             title=("ANALYSIS GRID — DIAGNOSTIC ONLY, DO NOT QUOTE. "
                                    "Roughness here uses a 5x5 window on 80.79 m samples, "
                                    "so it spans ~404 m and measures REGIONAL RELIEF, not "
                                    "25 m roughness. clip(roughness/50) pins 2.39 % of it "
                                    "at 1.0, which is why nothing is scored on this grid: "
                                    "pradan_pipeline scores at 25 m and area-averages the "
                                    "bounded field down. Quote the NATIVE table above"),
                             sample_px_m=a_sample_mpp))

    # --- 8. metadata: real frame in, hardcoded bounding box out -----------
    lines, samples = frame.shape
    mpp_line, mpp_sample = frame.metres_per_pixel()
    meta = {
        "product_id": f"{PRODUCT_STEM}_d_sri_xx_cp_xx_d18",
        "instrument": "Chandrayaan-2 DFSAR (L-band, hybrid circular polarimetry)",
        "observation_date": "2020-08-08T20:11:54.198Z",
        "processing_level": frame.label.get("product_type", "L2-SELENOREF"),
        "imaging_mode": frame.label.get("imaging_mode", ""),
        "frequency_band": frame.label.get("frequency_band", ""),
        "look_direction": frame.label.get("look_direction", ""),
        "orbit": frame.label.get("imaging_orbit_number", ""),
        "native_grid": {"lines": lines, "samples": samples,
                        "metres_per_pixel": {"line": mpp_line, "sample": mpp_sample}},
        "geodetic_frame": frame.geodetic_frame(
            valid_mask=valid, grid_spec=grid_spec, grid_validation=grid_check,
            incidence_range_deg=None,
        ),
        "calibration": cal,
        "multilook": {"kernel": f"{MULTILOOK_KERNEL}x{MULTILOOK_KERNEL} boxcar",
                      "note": "unchanged from the previous revision"},
        "masks": {
            "model": "two masks -- footprint (where the beam pointed) and "
                     "amplitude (where signal returned). A single mask was "
                     "conflating them; they differ by a factor of 2.28 here.",
            "footprint": {
                "source": footprint_source,
                "pixels": int(footprint.sum()),
                "fraction_of_frame": round(float(footprint.mean()), 6),
                "area_km2": round(float(footprint.sum() * px_area_km2), 2),
                "ribbon": ribbon_fp,
                "nominal_swath_m": nominal_swath_m,
                "ribbon_vs_nominal_pct_error": round(
                    abs(ribbon_fp["mean_km"] * 1000 / nominal_swath_m * 100 - 100), 2),
                "iou_with_incidence_gt_zero": round(footprint_iou, 6),
                "corroboration": [
                    "sri_ma > 0 and incidence > 0 are byte-identical (IoU 100.00 %)",
                    "geolocation grid: 333,614 / 937,296 nodes non-fill = 35.59 %",
                    "gri frame is 786 samples x 25.0 m = 19,650 m across-track, "
                    "exactly isda:swath",
                ],
                "used_for": ["swath outline / footprint ring", "void scrim",
                             "coverage statement in the UI"],
            },
            "amplitude": {
                "source": "(LH > 0) & (LV > 0) on the sri amplitude rasters",
                "pixels": int(amplitude.sum()),
                "fraction_of_frame": round(float(amplitude.mean()), 6),
                "area_km2": round(float(amplitude.sum() * px_area_km2), 2),
                "ribbon": ribbon_amp,
                "fraction_of_footprint": round(
                    float(amplitude.sum() / max(footprint.sum(), 1)), 6),
                "pixels_outside_footprint": outside,
                "used_for": ["alpha on the radar layers",
                             "every contrast stretch", "every statistic"],
            },
            "gap": {
                "pixels": gap,
                "fraction_of_frame": round(gap / float(amplitude.size), 6),
                "fraction_of_footprint": round(gap / float(max(footprint.sum(), 1)), 6),
                "explanation": (
                    "ISRO flags these pixels as imaged; the amplitude rasters hold "
                    "literal integer zero there. This is a property of the delivered "
                    "data, not of the geocoding: the ground-range gri product spans "
                    "the full 19,650 m swath yet its amplitude is a single contiguous "
                    "8.80 km run per line with zero interior holes on 265/265 sampled "
                    "lines. Areas close both ways -- amplitude 1501.2 km2 (gri) vs "
                    "1460.7 km2 (sri) = +2.77 %; footprint 3239.8 km2 vs 3327.8 km2 "
                    "= -2.65 %."
                ),
                "handling": (
                    "Left transparent. cpr/dop are np.where(s0 > 0, ..., 0.0), so "
                    "including these pixels in the statistical mask would write a "
                    "fabricated 0.0 over a fifth of the frame."
                ),
                "isro_ma_values_in_gap": ma_values,
                "measured_by": "backend/scripts/diagnose_valid_mask.py",
            },
        },
        "statistics_native_over_valid": {b["name"]: b for b in stat_blocks},
    }
    # kept for continuity with the previous metadata revision
    meta["geodetic_frame"]["isro_sri_ma_nonzero_fraction"] = round(float(footprint.mean()), 6)

    if write_analysis:
        a_lines = a_samples = int(analysis_size)
        meta["analysis_grid"] = {
            "lines": a_lines,
            "samples": a_samples,
            "metres_per_pixel": {
                "line": round(lines * frame.pixel_size_m[1] / a_lines, 4),
                "sample": round(samples * frame.pixel_size_m[0] / a_samples, 4),
            },
            "spacing_resolved": (
                "app/services/mission_service.py now derives the per-axis spacing from "
                "the frame itself (SarFrame.metres_per_pixel) and passes it as "
                "spacing_m=(metres_per_line, metres_per_sample) to every science module. "
                "The former hardcoded pixel_scale_m=250.0 — which matched neither axis — "
                "is gone. The tile pyramid still uses the native grid."
            ),
        }

    meta["product_provenance"] = {
        "real_measured": [
            "native/cpr_native.tif", "native/dop_native.tif", "native/s0_native.tif",
            "native/sigma_sc_native.tif", "native/valid_native.tif",
            "native/footprint_native.tif",
            "dfsar/cpr_real.tif", "dfsar/dop_real.tif", "dfsar/s0_real.tif",
            "dfsar/s3_real.tif", "dfsar/valid_real.tif", "dfsar/footprint_real.tif",
            "dfsar/ch2_sar_cpr.tif", "dfsar/ch2_sar_dop.tif",
            "dfsar/faustini_dfsar_s0.tif", "dfsar/faustini_dfsar_s3.tif",
            "dfsar/shackleton_dfsar_s0.tif", "dfsar/shackleton_dfsar_s3.tif",
            "native/dem_native.tif",
            "dem/real_dem.tif", "dem/ch2_sar_dem.tif",
            "dem/faustini_lola_dem.tif", "dem/shackleton_lola_dem.tif",
        ],
        "synthetic_placeholder": [],
        "elevation": {
            "provenance": dem_prov["provenance"],
            "source": str(LOLA_FRAME_DEM.relative_to(BASE_DIR)).replace("\\", "/"),
            "sidecar": str(LOLA_FRAME_SIDECAR.relative_to(BASE_DIR)).replace("\\", "/"),
            "native_metres_per_pixel": dem_prov.get("native_metres_per_pixel"),
            "grid_metres_per_pixel": dem_prov.get("output_metres_per_pixel"),
            "resample_ratio": dem_prov.get("resample_ratio"),
            "elevation_datum": dem_prov.get("elevation_datum"),
            "lineage": dem_prov.get("lineage"),
            "derived_layer_caveat": (
                "Hillshade, slope, roughness, hazard and illumination are derived "
                f"from elevation measured at "
                f"{dem_prov.get('native_metres_per_pixel')} m posts and resampled "
                f"to {dem_prov.get('output_metres_per_pixel')} m. They are "
                f"{dem_prov.get('native_metres_per_pixel')} m quantities carried on "
                "a finer grid, not measurements at the finer spacing: the upsample "
                "adds no relief. Any slope threshold quoted in the UI must name the "
                "post spacing it was computed at, and thresholds fitted against the "
                "previous analytic surface do not transfer."
            ),
            "not_verified": (
                "Whether LOLA's +y axis means the same ground direction as DFSAR's "
                "+y is asserted from both labels agreeing on the projection, not "
                "independently measured; a third elevation source would be needed. "
                "See axis_convention_assumption in the sidecar."
            ),
        },
        "filename_caveats": [
            "native/dem_native.tif is LOLA-derived despite its name; the "
            "renamed from dem_native_synthetic.tif in Phase 6.",
            "dem/*_lola_dem.tif now genuinely contain LOLA data. Before this "
            "revision the same filenames held analytic placeholder topography.",
            "'s3' in s3_real.tif / *_dfsar_s3.tif is sigma_sc (same-sense circular "
            "backscatter), not Stokes parameter S3.",
        ],
        "naming_caveat": (
            "'s3' in s3_real.tif / *_dfsar_s3.tif is sigma_sc (same-sense circular "
            "backscatter), not Stokes parameter S3."
        ),
    }

    OUT_DFSAR_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DFSAR_DIR / "metadata_real.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\nProcessing complete. Metadata -> {OUT_DFSAR_DIR / 'metadata_real.json'}")
    print(f"  REAL:      CPR, DOP, S0, sigma_sc, georeferencing")
    print(f"  MASKS:     footprint {footprint.mean() * 100:.2f} % (ISRO sri_ma) / "
          f"amplitude {amplitude.mean() * 100:.2f} % (LH>0 & LV>0)")
    print(f"  ELEVATION: {dem_prov['provenance']}")
    print("  SYNTHETIC: nothing. The analytic placeholder DEM is gone and has no")
    print("             fallback; terrain layers are LOLA-derived at "
          f"{dem_prov.get('native_metres_per_pixel')} m native posts.")
    return meta


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Calibrate the Chandrayaan-2 DFSAR sri products and build map "
                    "and analysis rasters. Native resolution is the default; any "
                    "downsampling must be asked for explicitly."
    )
    ap.add_argument("--analysis-size", type=int, default=DEFAULT_ANALYSIS_SIZE,
                    help=f"square analysis grid the existing backend reads "
                         f"(default {DEFAULT_ANALYSIS_SIZE}; this is the shape already on disk)")
    ap.add_argument("--no-native", action="store_true",
                    help="skip the full-resolution products used by the tile builder")
    ap.add_argument("--no-analysis", action="store_true",
                    help="skip the analysis-grid products read by mission_service.py")
    args = ap.parse_args()

    process_real_data(analysis_size=args.analysis_size,
                      write_native=not args.no_native,
                      write_analysis=not args.no_analysis)


if __name__ == "__main__":
    main()
