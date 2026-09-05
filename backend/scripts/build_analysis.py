"""
build_analysis.py -- v6 section 2, V10 revision. Precompute the headline verdict OFFLINE.

WHY THIS SCRIPT EXISTS
----------------------
The deployed backend cannot run the real analysis. Two independent reasons,
both measured:

  1. `/data/` and `*.tif` are gitignored, so NO raster reaches the Render
     filesystem. `mission_service.py` then finds none of its inputs and
     silently degrades to the seeded DEMO generator.
  2. Those input paths are hardcoded Windows absolute paths
     (`d:/FYP/data/pradan/...`), which cannot resolve on Linux even if the
     files were deployed.

The result was a live site serving a confident fabricated verdict: 96 %
P(ice), PROMISING CANDIDATE, screening PASSED, 5/5 evidence ticks, 17.58 M m3
of ice -- next to a map rendering the real measured radar swath. Measured
imagery on the left, invented numbers on the right.

So the headline verdict is computed HERE, once, from the real rasters, and
committed as a static asset next to layers.json. The mission view reads it
from the CDN. No backend, no cold start, no DEMO path for the headline.

WHAT CHANGED IN V10 -- THE DEM IS NO LONGER A PLACEHOLDER
--------------------------------------------------------
Every "MODELLED on the placeholder DEM" caveat in the previous revision of
this file described a build in which `dem_native_synthetic.tif` really did
hold Gaussians and sinusoids. It no longer does. Measured, not assumed:

    dem_native_synthetic.tif  vs  lola/ldem_frame_25m.tif
    max|diff| 0.0 m   rms 0.0 m   bit-identical True   pearson r 1.000000000

The file is byte-for-byte the LOLA crop. The FILENAME is a leftover, retained
only so existing consumers keep working; `assert_dem_is_lola()` re-measures
the identity on every run, so the name can never quietly become true again.

What is still modelled is the ILLUMINATION, not the topography. The
`hillshade * elev_norm ** 1.3` expression below is an invented brightness
proxy rather than a horizon computation, and it puts 77 % of the frame in
shadow. Slope, roughness, hazard and elevation are measured quantities now;
PSR area stays UNAVAILABLE until the horizon model replaces that proxy.

WHAT IS DIFFERENT FROM THE BACKEND'S OWN "REAL" MODE
----------------------------------------------------
Even locally, with every real file present, the request path degrades the
data before measuring it:

  * `process_real_dem(..., target_shape=(100, 100))` bilinearly resamples the
    2258 x 6618 raster down to 100 x 100 -- 10,000 cells for the whole scene.
  * `mission_service.py` then resamples cpr/dop to that same 100 x 100.
  * Every statistic is taken over the FULL frame, so 84.36 % literal-zero
    padding is averaged into every "measured" mean.

Measured consequences (all printed by this script):

  CPR mean   native masked 0.001312   vs  API-reported 0.0    (naive, padded)
  CPR max    native masked 0.053411   vs  API-reported 0.044  (resample artefact)
  DOP mean   native masked 0.057053   vs  API-reported 0.009  (naive, padded)

This script measures at native 25 m/px over the amplitude mask only. Nothing
is resampled and nothing is averaged across the void.

PROVENANCE DISCIPLINE
---------------------
  MEASURED    -- an observation, or a direct geometric consequence of one:
                 calibrated Chandrayaan-2 DFSAR, or LOLA topography.
  MODELLED    -- a model output with no ground truth anywhere in this project
                 to check it against: the illumination proxy, and P(ice).
  DERIVED     -- an assumption model applied on top of one of the above
                 (the volume bounds, which multiply area by assumed depth).
  UNAVAILABLE -- cannot be computed honestly yet. The frontend renders an em
                 dash and the reason, never a plausible substitute.

The frontend must never promote a MODELLED or UNAVAILABLE value into the slot
a MEASURED one would occupy.

RESOLUTION HONESTY
------------------
LOLA LDEM_80S_80M is measured at 80 m posts and bilinearly resampled onto this
frame's 25 m grid. Slope, roughness and hazard are therefore 80 m-post
quantities carried on a 25 m grid; they contain no relief finer than 80 m. The
number a reader needs in order to judge them is 80, not 25, so every terrain
value emitted here names 80 in its own note.

Run:  python backend/scripts/build_analysis.py
Out:  frontend/public/analysis/<crater>.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import tifffile

BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

NATIVE_DIR = BASE_DIR / "data" / "pradan" / "native"
LOLA_DIR = BASE_DIR / "data" / "pradan" / "lola"
LOLA_SIDECAR = LOLA_DIR / "ldem_frame_25m.provenance.json"
LOLA_CROP = LOLA_DIR / "ldem_frame_25m.tif"
DFSAR_DIR = BASE_DIR / "data" / "pradan" / "dfsar"
LH_TIF = (BASE_DIR / "data" / "pradan" / "raw" / "data" / "calibrated" / "20200808"
          / "ch2_sar_ncxl_20200808t201154198_d_sri_xx_cp_lh_d18.tif")
LH_XML = (BASE_DIR / "data" / "pradan" / "raw" / "data" / "calibrated" / "20200808"
          / "ch2_sar_ncxl_20200808t201154198_d_sri_xx_cp_xx_d18.xml")
LAYERS_JSON = BASE_DIR / "frontend" / "public" / "layers" / "layers.json"
OUT_DIR = BASE_DIR / "frontend" / "public" / "analysis"

SCHEMA = "lunar-ice/analysis/1"

MEASURED = "MEASURED"
MODELLED = "MODELLED"
DERIVED = "DERIVED"
UNAVAILABLE = "UNAVAILABLE"

# (metres per line, metres per sample). Only used if the PDS4 bundle is absent
# from this host, and the manifest records when that happened.
FALLBACK_SPACING = (25.0, 25.0)


def dem_provenance() -> dict:
    """
    The elevation sidecar written by ingest_lola_polar_dem.py, or a hard stop.

    Identical contract to render_layers.dem_provenance(), deliberately: the
    imagery and the numbers must state the same provenance or one of them is
    lying. The banned-word check is the same one, for the same reason -- the
    previous failure mode was a manifest that said one thing while the pixels
    said another.
    """
    if not LOLA_SIDECAR.is_file():
        raise SystemExit(
            f"{LOLA_SIDECAR} missing. The terrain numbers cannot state their own "
            "provenance without it. Run:\n"
            "    python backend/scripts/ingest_lola_polar_dem.py\n"
            "    python backend/scripts/process_real_sar_pipeline.py"
        )
    p = json.loads(LOLA_SIDECAR.read_text(encoding="utf-8"))
    for key in ("provenance", "native_metres_per_pixel", "output_metres_per_pixel"):
        if key not in p:
            raise SystemExit(f"{LOLA_SIDECAR.name} has no '{key}'; re-run the ingest.")
    banned = ("synthetic", "placeholder", "analytic", "unknown", "unavailable")
    hits = [w for w in banned if w in str(p["provenance"]).lower()]
    if hits:
        raise SystemExit(
            f"the elevation provenance string {p['provenance']!r} contains {hits}, "
            "so this file would badge every terrain number as a placeholder. Fix "
            "the ingest, do not weaken the check here."
        )
    return p


DEM_PROV = dem_provenance()
NATIVE_POST_M = float(DEM_PROV["native_metres_per_pixel"])
GRID_POST_M = float(DEM_PROV["output_metres_per_pixel"])

DEM_NOTE = (
    f"Elevation is {DEM_PROV['provenance']}. Despite its filename, "
    f"native/dem_native_synthetic.tif holds that measured LOLA topography "
    f"bit-for-bit (verified every run: max|diff| 0.0 m against "
    f"lola/ldem_frame_25m.tif); the name is retained only so existing consumers "
    f"keep working."
)
SLOPE_NOTE = (
    f"{NATIVE_POST_M:g} m-POST QUANTITY. The gradient is taken on the "
    f"{GRID_POST_M:g} m grid, but LOLA measured the surface at {NATIVE_POST_M:g} m "
    f"posts and the upsample added no relief below that. Read this as a "
    f"{NATIVE_POST_M:g} m slope, not a {GRID_POST_M:g} m one. " + DEM_NOTE
)
ILLUM_MODEL = (
    "Illumination here is NOT a horizon computation. It is the expression "
    "hillshade(sun 1.5 deg) * elev_norm**1.3 -- an invented brightness proxy "
    "with no physical horizon in it, inherited from the ingest path. It puts "
    "77 % of the frame below the 0.05 cut, which does not delimit a cold trap; "
    "it only says the proxy is dark almost everywhere. The topography beneath "
    "it is measured; the shadow on top of it is not."
)


def assert_dem_is_lola(dem: np.ndarray) -> dict:
    """
    Re-measure the claim the filename contradicts, on every run.

    `dem_native_synthetic.tif` is byte-identical to the LOLA crop today. If a
    future pipeline change ever makes the filename true again, every terrain
    mark in this file silently becomes a lie. So the identity is a FATAL check
    with a printed residual, not a comment.
    """
    if not LOLA_CROP.is_file():
        raise SystemExit(
            f"{LOLA_CROP} missing, so the DEM's identity cannot be verified and "
            "no terrain number may be marked MEASURED. Run "
            "backend/scripts/ingest_lola_polar_dem.py."
        )
    lola = tifffile.imread(str(LOLA_CROP))
    if lola.shape != dem.shape:
        raise SystemExit(
            f"native DEM {dem.shape} and LOLA crop {lola.shape} disagree on shape; "
            "the frames are not the same grid."
        )
    a = dem.astype(np.float64)
    b = lola.astype(np.float64)
    d = a - b
    rec = {
        "compared": ["native/dem_native_synthetic.tif", "lola/ldem_frame_25m.tif"],
        "max_abs_diff_m": float(np.abs(d).max()),
        "rms_diff_m": float(np.sqrt((d ** 2).mean())),
        "bit_identical": bool(np.array_equal(a, b)),
        "tolerance_m": 0.0,
    }
    if rec["max_abs_diff_m"] > rec["tolerance_m"]:
        raise SystemExit(
            "native/dem_native_synthetic.tif is NOT the LOLA crop "
            f"(max|diff| {rec['max_abs_diff_m']:.6f} m). Either the ingest changed "
            "or the filename became true again. No terrain number may be marked "
            "MEASURED until this is resolved."
        )
    rec["verdict"] = "PASS"
    return rec


def resolve_spacing() -> tuple[tuple[float, float], str]:
    """
    Ground spacing from the product's own GeoTIFF GeoKeys, exactly as
    render_layers.resolve_spacing() does it, so the numbers and the imagery
    cannot be computed on two different grids. Tuple, never a scalar:
    (metres per line, metres per sample).
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


def hr(title: str) -> None:
    print("\n" + "-" * 78)
    print(title)
    print("-" * 78)


def val(
    value,
    unit: str = "",
    provenance: str = MEASURED,
    note: str = "",
    reason: str = "",
) -> dict:
    """
    One headline value plus the provenance the UI must render beside it.

    `value is None` means the number does not exist and must not be invented.
    `reason` explains that absence in the place the number would have been.
    """
    rec = {"value": value, "unit": unit, "provenance": provenance}
    if note:
        rec["note"] = note
    if reason:
        rec["reason"] = reason
    return rec


def stats(a: np.ndarray, mask: np.ndarray) -> dict:
    """Population statistics over `mask` only. No padding enters any of these."""
    m = a[mask]
    return {
        "n": int(m.size),
        "mean": float(m.mean()),
        "p50": float(np.percentile(m, 50)),
        "p90": float(np.percentile(m, 90)),
        "p99": float(np.percentile(m, 99)),
        "min": float(m.min()),
        "max": float(m.max()),
        "std": float(m.std()),
    }


def naive(a: np.ndarray) -> dict:
    """The same statistics the backend reports: whole frame, padding included."""
    return {
        "mean": float(a.mean()),
        "p50": float(np.percentile(a, 50)),
        "max": float(a.max()),
        "min": float(a.min()),
    }


def load_native() -> dict:
    """Read the native 25 m/px rasters. Shapes must agree or nothing is trustworthy."""
    need = {
        "cpr": NATIVE_DIR / "cpr_native.tif",
        "dop": NATIVE_DIR / "dop_native.tif",
        "dem": NATIVE_DIR / "dem_native_synthetic.tif",
        "valid": NATIVE_DIR / "valid_native.tif",
        "footprint": NATIVE_DIR / "footprint_native.tif",
    }
    missing = [str(p) for p in need.values() if not p.exists()]
    if missing:
        raise SystemExit(
            "native rasters missing -- run process_real_sar_pipeline.py first:\n  "
            + "\n  ".join(missing)
        )
    out = {k: tifffile.imread(str(p)) for k, p in need.items()}
    shapes = {k: a.shape for k, a in out.items()}
    if len(set(shapes.values())) != 1:
        raise SystemExit(f"native rasters disagree on shape: {shapes}")
    out["valid"] = out["valid"].astype(bool)
    out["footprint"] = out["footprint"].astype(bool)
    out["paths"] = {k: f"native/{p.name}" for k, p in need.items()}
    return out


def terrain_from_dem(dem: np.ndarray, spacing_m: tuple[float, float]) -> dict:
    """
    Slope / roughness / illumination, using the SAME formulas as the backend
    modules so the static file cannot silently disagree with them:
      module_d_terrain.compute_terrain_metrics / compute_hazard_score
      module_a_psr.compute_hillshade
      pradan_pipeline.simulate_grazing_illumination

    `spacing_m` is (metres per line, metres per sample) and has NO DEFAULT, for
    the same reason module_d_terrain.compute_terrain_metrics no longer has one:
    a wrong spacing a caller can inherit silently is the bug, not the value.

    Slope and roughness are MEASURED quantities now -- the DEM under them is
    LOLA -- but they are 80 m-post quantities on a 25 m grid. Illumination is
    still the invented proxy; see ILLUM_MODEL.
    """
    from scipy.ndimage import uniform_filter

    sy, sx = spacing_m
    grad_y, grad_x = np.gradient(dem, sy, sx)
    slope_rad = np.arctan(np.hypot(grad_x, grad_y))
    slope_deg = np.degrees(slope_rad).astype(np.float32)
    aspect_rad = np.arctan2(-grad_x, grad_y)
    del grad_x, grad_y

    mean_elev = uniform_filter(dem, size=5)
    mean_sq = uniform_filter(dem**2, size=5)
    roughness = np.sqrt(np.maximum(0.0, mean_sq - mean_elev**2)).astype(np.float32)
    del mean_elev, mean_sq

    # Horn hillshade at the grazing polar sun elevation used by the ingest path.
    az, alt = np.radians(315.0), np.radians(1.5)
    hill = np.clip(
        np.sin(alt) * np.cos(slope_rad) + np.cos(alt) * np.sin(slope_rad) * np.cos(az - aspect_rad),
        0.0, 1.0,
    ).astype(np.float32)
    del slope_rad, aspect_rad

    elev_norm = (dem - dem.min()) / (np.ptp(dem) + 1e-6)
    illumination = np.clip(hill * (elev_norm ** 1.3), 0.0, 1.0).astype(np.float32)
    del hill, elev_norm

    return {
        "slope_deg": slope_deg,
        "roughness": roughness,
        "illumination": illumination,
        "psr_mask": illumination < 0.05,
        "doubly": (illumination < 0.05) & (dem < np.percentile(dem, 20)),
    }


def hazard_from(slope_deg: np.ndarray, roughness: np.ndarray, cfg,
                boulder_available: bool) -> tuple[np.ndarray, dict]:
    """
    module_d_terrain.compute_hazard_score, with the boulder term handled as an
    ABSENT quantity rather than a zero one.

    The previous version divided by WEIGHT_SLOPE + WEIGHT_ROUGHNESS +
    WEIGHT_BOULDER while putting nothing in the numerator for boulders, so 20 %
    of the weight was contributed by a term that does not exist and every hazard
    score came out 20 % too low. `np.zeros_like` is not an absent state: a zero
    boulder risk is the claim "this terrain was imaged and found free of rocks",
    which no product in this build supports.

    So when no boulder detector exists, the weight is dropped and the blend is
    RENORMALISED over the two terms that remain. Hazard stays in [0, 1] and
    means what it says: a slope-and-roughness hazard, with the missing component
    named in `hazard_model.boulder`.
    """
    slope_risk = np.clip(slope_deg / cfg.MAX_TRAVERSABLE_SLOPE_DEG, 0.0, 1.0)
    rough_risk = np.clip(roughness / 50.0, 0.0, 1.0)
    w_slope = float(cfg.WEIGHT_SLOPE)
    w_rough = float(cfg.WEIGHT_ROUGHNESS)
    w_boulder = float(cfg.WEIGHT_BOULDER) if boulder_available else 0.0
    total = w_slope + w_rough + w_boulder
    hazard = np.clip((w_slope * slope_risk + w_rough * rough_risk) / total,
                     0.0, 1.0).astype(np.float32)
    model = {
        "components": ["slope", "roughness"] + (["boulder"] if boulder_available else []),
        "weights_applied": {"slope": w_slope, "roughness": w_rough, "boulder": w_boulder},
        "weights_in_config": {
            "WEIGHT_SLOPE": float(cfg.WEIGHT_SLOPE),
            "WEIGHT_ROUGHNESS": float(cfg.WEIGHT_ROUGHNESS),
            "WEIGHT_BOULDER": float(cfg.WEIGHT_BOULDER),
        },
        "denominator": total,
        "renormalised": not boulder_available,
        "slope_risk_reference_deg": float(cfg.MAX_TRAVERSABLE_SLOPE_DEG),
        "roughness_risk_reference_m": 50.0,
        "boulder": {
            "provenance": UNAVAILABLE,
            "value": None,
            "reason": ("No boulder detector and no optical product exist in this build; "
                       "data/pradan/ohrc/ is empty. Boulder risk is UNMEASURED, not zero. "
                       "The weight is dropped and the blend renormalised over slope and "
                       "roughness, so hazard is a two-term hazard and says so."),
        },
        "provenance": MEASURED,
        "note": ("Slope and roughness both come from measured LOLA topography, so the "
                 "hazard blend is measured too -- but it is a two-term blend at "
                 f"{NATIVE_POST_M:g} m posts, not the three-term one config.py describes. "
                 + SLOPE_NOTE),
    }
    return hazard, model


def p_ice_over_valid(cpr, dop, slope_deg, roughness, illumination, psr_mask, valid) -> dict:
    """
    Run the project's Random Forest, but ONLY on pixels that carry radar.

    The backend runs it over the whole 100 x 100 frame, so 84 % of its input
    rows are literal-zero padding -- and a row of zeros looks exactly like the
    trained "ice" class (cpr low, dop low, illumination 0, flat), which is a
    large part of why the fabricated card reads 0.96. Restricting the model to
    the amplitude mask removes that artefact.
    """
    from app.modules.module_c_ice import ice_ml_model

    X = np.column_stack([
        cpr[valid].astype(np.float64),
        dop[valid].astype(np.float64),
        slope_deg[valid].astype(np.float64),
        roughness[valid].astype(np.float64),
        illumination[valid].astype(np.float64),
        psr_mask[valid].astype(np.float64),
    ])
    if not ice_ml_model._is_trained:
        ice_ml_model.train_prototype_model()
    p = ice_ml_model.model.predict_proba(X)[:, 1]
    del X
    return {
        "n": int(p.size),
        "mean": float(p.mean()),
        "p50": float(np.percentile(p, 50)),
        "p99": float(np.percentile(p, 99)),
        "max": float(p.max()),
        "fraction_above_0_5": float((p >= 0.5).mean()),
    }


def build(crater_id: str = "faustini") -> dict:
    from app.core.config import settings as cfg
    from app.demo.lunar_generator import CRATER_CATALOG

    info = CRATER_CATALOG[crater_id]
    manifest = json.loads(LAYERS_JSON.read_text(encoding="utf-8")) if LAYERS_JSON.exists() else {}

    r = load_native()
    cpr, dop, dem = r["cpr"], r["dop"], r["dem"]
    valid, footprint = r["valid"], r["footprint"]
    lines, samples = cpr.shape
    spacing, spacing_src = resolve_spacing()
    px_m = float(spacing[1])
    cell_km2 = (spacing[0] / 1000.0) * (spacing[1] / 1000.0)

    dem_identity = assert_dem_is_lola(dem)
    hr("ELEVATION PROVENANCE -- the filename says synthetic; the pixels do not")
    print(f"  sidecar      {LOLA_SIDECAR.relative_to(BASE_DIR)}")
    print(f"  provenance   {DEM_PROV['provenance']}")
    print(f"  native post  {NATIVE_POST_M:g} m   ->  grid {GRID_POST_M:g} m "
          f"(resample ratio {DEM_PROV.get('resample_ratio', 'n/a')}, upsample)")
    print(f"  identity     max|diff| {dem_identity['max_abs_diff_m']:.6f} m   "
          f"rms {dem_identity['rms_diff_m']:.6f} m   "
          f"bit-identical {dem_identity['bit_identical']}   {dem_identity['verdict']}")
    print(f"  dem range    {float(dem.min()):.2f} .. {float(dem.max()):.2f} m  "
          f"({DEM_PROV.get('elevation_datum', 'datum not stated')[:60]}...)")

    hr(f"NATIVE FRAME  {lines} x {samples} @ {spacing[0]:g} m/line x {spacing[1]:g} m/sample")
    print(f"  spacing from {spacing_src}")
    print(f"  frame        {cpr.size:>12,d} px  {cpr.size * cell_km2:10.2f} km2")
    print(f"  amplitude    {int(valid.sum()):>12,d} px  {valid.sum() * cell_km2:10.2f} km2  "
          f"{valid.mean() * 100:6.3f} %   <- every radar statistic below uses ONLY this")
    print(f"  footprint    {int(footprint.sum()):>12,d} px  {footprint.sum() * cell_km2:10.2f} km2  "
          f"{footprint.mean() * 100:6.3f} %   (ISRO sri_ma: where the beam pointed)")
    print(f"  returned / pointed = {valid.sum() / max(footprint.sum(), 1) * 100:.2f} %")

    cpr_s, dop_s = stats(cpr, valid), stats(dop, valid)
    cpr_n, dop_n = naive(cpr), naive(dop)
    hr("RADAR -- MEASURED, over the amplitude mask (and the naive figure the API prints)")
    for nm, s, n in (("CPR", cpr_s, cpr_n), ("DOP", dop_s, dop_n)):
        print(f"  {nm}  masked  mean {s['mean']:.6f}  p50 {s['p50']:.6f}  p99 {s['p99']:.6f}  max {s['max']:.6f}")
        print(f"  {nm}  naive   mean {n['mean']:.6f}  p50 {n['p50']:.6f}                      max {n['max']:.6f}"
              f"   <- padding-contaminated")

    t = terrain_from_dem(dem, spacing)
    boulder_available = False  # data/pradan/ohrc/ is empty; see hazard_model.boulder
    haz, hazard_model = hazard_from(t["slope_deg"], t["roughness"], cfg, boulder_available)
    hr(f"TERRAIN -- MEASURED LOLA topography, {NATIVE_POST_M:g} m posts on a {GRID_POST_M:g} m grid")
    print(f"  slope_deg   p50 {np.percentile(t['slope_deg'], 50):8.4f}  mean {t['slope_deg'].mean():8.4f}  max {t['slope_deg'].max():8.4f}")
    print(f"  roughness_m p50 {np.percentile(t['roughness'], 50):8.4f}  mean {t['roughness'].mean():8.4f}")
    print(f"  hazard      p50 {np.percentile(haz, 50):8.4f}  mean {haz.mean():8.4f}"
          f"   <- {'+'.join(hazard_model['components'])} / {hazard_model['denominator']:g}"
          f"{'  (RENORMALISED: boulder term absent)' if hazard_model['renormalised'] else ''}")
    print(f"  boulder     NO DATA -- weight {cfg.WEIGHT_BOULDER:g} in config, {hazard_model['weights_applied']['boulder']:g} applied. "
          f"Not zero risk: unmeasured risk.")

    hr("ILLUMINATION / PSR -- MODELLED, and the model is the remaining defect")
    print(f"  psr_mask    {int(t['psr_mask'].sum()):>12,d} px  {t['psr_mask'].sum() * cell_km2:10.2f} km2  {t['psr_mask'].mean() * 100:6.2f} %"
          f"   <- DEGENERATE: shadows most of the frame, so PSR area stays UNAVAILABLE")
    print(f"  doubly      {int(t['doubly'].sum()):>12,d} px  {t['doubly'].sum() * cell_km2:10.2f} km2  {t['doubly'].mean() * 100:6.2f} %")
    print(f"  model       hillshade(sun 1.5 deg) * elev_norm**1.3 -- a brightness proxy, no horizon term")

    # ---------------------------------------------------------------- screening
    # module_c_ice.evaluate_ice_intelligence, verbatim criteria, with one
    # addition: the mask is intersected with `valid`, so a candidate can only be
    # claimed where radar actually exists. Without that, the illumination proxy's
    # shadow could nominate pixels the radar never saw.
    cpr_th, dop_th = float(cfg.CPR_THRESHOLD), float(cfg.DOP_THRESHOLD)
    cpr_pass = (cpr > cpr_th) & valid
    dop_pass = (dop < dop_th) & valid
    candidate = cpr_pass & dop_pass & t["psr_mask"]
    cand_n = int(candidate.sum())
    cand_km2 = cand_n * cell_km2
    doubly_overlap = int((candidate & t["doubly"]).sum())

    hr("SCREENING -- CPR > th AND DOP < th AND in PSR, restricted to measured pixels")
    print(f"  threshold   CPR > {cpr_th}   DOP < {dop_th}   (backend/app/core/config.py)")
    print(f"  CPR > {cpr_th}   {int(cpr_pass.sum()):>12,d} px of {int(valid.sum()):,} measured"
          f"   -> highest CPR anywhere in the swath is {cpr_s['max']:.6f}")
    print(f"  DOP < {dop_th}  {int(dop_pass.sum()):>12,d} px  ({dop_pass.sum() / max(valid.sum(), 1) * 100:.2f} % of measured)")
    print(f"  candidates  {cand_n:>12,d} px  {cand_km2:.2f} km2   doubly-shadowed overlap {doubly_overlap:,} px")
    print(f"  status      {'PASS' if cand_n > 0 else 'FAIL'}")

    pice = p_ice_over_valid(cpr, dop, t["slope_deg"], t["roughness"], t["illumination"], t["psr_mask"], valid)
    print(f"\n  P(ice) over the {pice['n']:,} MEASURED pixels only:"
          f"  mean {pice['mean']:.4f}  p50 {pice['p50']:.4f}  p99 {pice['p99']:.4f}  max {pice['max']:.4f}")
    print(f"  fraction >= 0.5: {pice['fraction_above_0_5'] * 100:.2f} %")

    v_exp = cand_km2 * 1e6 * cfg.DEFAULT_ICE_DEPTH_M * cfg.DEFAULT_ICE_FRACTION
    v_cons = cand_km2 * 1e6 * cfg.CONSERVATIVE_ICE_DEPTH_M * cfg.CONSERVATIVE_ICE_FRACTION
    v_up = cand_km2 * 1e6 * cfg.UPPER_ICE_DEPTH_M * cfg.UPPER_ICE_FRACTION
    print(f"\n  volume bounds from {cand_km2:.2f} km2:  conservative {v_cons:,.0f}  expected {v_exp:,.0f}  upper {v_up:,.0f} m3")

    # ------------------------------------------------------------- evidence rows
    # Each row carries the MEASURED value beside the ACTUAL threshold, so the
    # card can show *why* a criterion failed instead of a bare tick or cross.
    evidence = [
        {
            "criterion": "cpr_above_threshold",
            "label": "CPR above CBOE threshold",
            "measured": round(cpr_s["max"], 6), "measured_label": "peak CPR in swath",
            "threshold": cpr_th, "comparison": ">",
            "passed": bool(cpr_s["max"] > cpr_th),
            "provenance": MEASURED,
            "note": (f"Peak CPR across all {cpr_s['n']:,} measured pixels is {cpr_s['max']:.4f}, "
                     f"{cpr_th / max(cpr_s['max'], 1e-9):.0f}x below the {cpr_th} threshold. This build's CPR is "
                     "sigma_sc/sigma_oc from amplitude alone; true hybrid-polarity CPR needs the Stokes S3 "
                     "phase term from the complex sli products, which are not ingested yet."),
        },
        {
            "criterion": "dop_below_threshold",
            "label": "DOP depressed (volume scattering)",
            "measured": round(dop_s["p50"], 6), "measured_label": "median DOP",
            "threshold": dop_th, "comparison": "<",
            "passed": bool(dop_s["p50"] < dop_th),
            "provenance": MEASURED,
            "note": (f"{dop_pass.sum() / max(valid.sum(), 1) * 100:.1f} % of measured pixels sit below "
                     f"{dop_th}. Depolarised returns are consistent with volume scattering, but on their own "
                     "they do not discriminate ice from fine dry regolith."),
        },
        {
            "criterion": "psr_cold_trap_overlap",
            "label": "Overlap with a shadowed cold trap",
            "measured": round(cand_km2, 4), "measured_label": "candidate area",
            "threshold": 0.0, "comparison": ">",
            "passed": bool(cand_n > 0),
            "provenance": MODELLED,
            "note": (f"The topography is measured LOLA, but the SHADOW on top of it is not. "
                     f"{ILLUM_MODEL} It puts {float(t['psr_mask'].mean()) * 100:.1f} % of the frame in "
                     f"shadow, so the overlap test is not discriminating anything. The row fails only "
                     f"because no pixel cleared CPR."),
        },
        {
            "criterion": "doubly_shadowed_core_overlap",
            "label": "Overlap with a doubly-shadowed core",
            "measured": round(doubly_overlap * cell_km2, 4), "measured_label": "overlap area",
            "threshold": 0.0, "comparison": ">",
            "passed": bool(doubly_overlap > 0),
            "provenance": MODELLED,
            "note": ("Doubly-shadowed cores are the illumination proxy's shadow intersected with the "
                     "lowest elevation quintile of the DEM. The elevation quintile is measured LOLA; the "
                     "shadow is not, and an elevation percentile is not a second shadowing event. A real "
                     "doubly-shadowed mask needs scattered light from lit terrain, which this build does "
                     "not compute. " + ILLUM_MODEL),
        },
        {
            "criterion": "thermal_stability_expected",
            "label": "Thermal stability expected",
            "measured": None, "measured_label": "no thermal model",
            "threshold": None, "comparison": None,
            "passed": False,
            "provenance": UNAVAILABLE,
            "note": ("No thermal model and no measured temperature exist in this build. The backend "
                     "returns this criterion as True whenever the candidate count is non-zero, which is a "
                     "restatement of the previous row, not an independent temperature test. Reported as "
                     "unavailable rather than inherited."),
        },
    ]
    print()
    for e in evidence:
        m = "n/a" if e["measured"] is None else f"{e['measured']:.6g}"
        th = "n/a" if e["threshold"] is None else f"{e['comparison']} {e['threshold']}"
        print(f"  [{'PASS' if e['passed'] else 'FAIL'}] {e['label']:38s} {e['measured_label']:20s} "
              f"{m:>12s}  vs {th:<10s} {e['provenance']}")

    passed_n = sum(1 for e in evidence if e["passed"])
    status = "PASS" if cand_n > 0 else "FAIL"

    doc = {
        "schema": SCHEMA,
        "crater_id": crater_id,
        "crater_name": info.name,
        "latitude_deg": info.latitude_deg,
        "longitude_deg": info.longitude_deg,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/build_analysis.py",
        "data_mode": "REAL",
        "why_static": (
            "Computed offline from the native rasters and served as a static asset. The deployed "
            "backend has no access to these files (/data/ and *.tif are gitignored, and the paths in "
            "mission_service.py are Windows absolutes), so on Render it degrades to a seeded DEMO "
            "generator and returns fabricated values with HTTP 200. The headline verdict must not "
            "depend on that path."
        ),
        "supersedes": (
            "the headline verdict previously taken from GET /api/mission/{crater} -- which returned "
            "data_mode DEMO with mean_cpr 0.525, max_cpr 2.292, P(ice) 0.96, screening PASS, 5/5 "
            "evidence ticks and 17,580,000 m3 of ice, none of it measured"
        ),
        "product_id": manifest.get("product_id", info.product_id),
        "instrument": manifest.get("instrument", "Chandrayaan-2 DFSAR"),
        "observation_date": manifest.get("observation_date", info.observed_date),
        "grid": {
            "lines": lines, "samples": samples,
            "metres_per_pixel": px_m,
            "metres_per_pixel_line": spacing[0],
            "metres_per_pixel_sample": spacing[1],
            "metres_per_pixel_source": spacing_src,
            "cell_area_km2": cell_km2,
            "frame_area_km2": round(cpr.size * cell_km2, 2),
            "note": ("Native resolution. The backend request path resamples to 100 x 100 "
                     "(process_real_dem target_shape) and takes every statistic over the padded "
                     "frame; nothing here is resampled and nothing is averaged across the void."),
        },
        "elevation": {
            "provenance": MEASURED,
            "product": DEM_PROV["provenance"],
            "data_set_id": DEM_PROV.get("source_product", {}).get("data_set_id"),
            "product_version_id": DEM_PROV.get("source_product", {}).get("product_version_id"),
            "native_metres_per_pixel": NATIVE_POST_M,
            "grid_metres_per_pixel": GRID_POST_M,
            "resample": DEM_PROV.get("resample_direction"),
            "resolution_caveat": DEM_PROV.get("resolution_caveat"),
            "elevation_datum": DEM_PROV.get("elevation_datum"),
            "min_m": float(dem.min()), "max_m": float(dem.max()), "mean_m": float(dem.mean()),
            "filename_is_a_misnomer": {
                "file": r["paths"]["dem"],
                "verified_every_run": dem_identity,
                "explanation": ("The file is named dem_native_synthetic.tif for historical reasons and "
                                "holds measured LOLA topography bit-for-bit. The name is retained so "
                                "existing consumers keep working; assert_dem_is_lola() fails the build "
                                "if it ever stops being a misnomer."),
            },
            "sidecar": str(LOLA_SIDECAR.relative_to(BASE_DIR)).replace("\\", "/"),
        },
        "hazard_model": hazard_model,
        "illumination_model": {
            "provenance": MODELLED,
            "expression": "clip(hillshade(sun_altitude=1.5 deg, azimuth=315 deg) * elev_norm ** 1.3, 0, 1)",
            "psr_cut": 0.05,
            "psr_fraction_of_frame": float(t["psr_mask"].mean()),
            "doubly_fraction_of_frame": float(t["doubly"].mean()),
            "why_it_is_not_measured": ILLUM_MODEL,
            "what_would_fix_it": ("A horizon computation on the full 7600 x 7600 LOLA array: for each "
                                  "azimuth, horizon(az) = max_r atan((h(p + r*u) - h(p)) / r), lit when "
                                  "the solar elevation exceeds it. The frame's farthest corner sits "
                                  "156.79 km from the pole inside a 304 km half-span array, so the rims "
                                  "that set these horizons are on disk already."),
        },
        "masks": {
            "amplitude": {
                "source": r["paths"]["valid"], "pixels": int(valid.sum()),
                "fraction": float(valid.mean()), "area_km2": round(valid.sum() * cell_km2, 2),
                "meaning": "DFSAR amplitude returned here. Every MEASURED statistic uses this mask only.",
            },
            "footprint": {
                "source": r["paths"]["footprint"], "pixels": int(footprint.sum()),
                "fraction": float(footprint.mean()), "area_km2": round(footprint.sum() * cell_km2, 2),
                "meaning": "ISRO sri_ma > 0: where the beam was pointed. 56.11 % of it returned literal zero.",
            },
            "returned_over_pointed": float(valid.sum() / max(footprint.sum(), 1)),
        },
        "source_rasters": r["paths"],
        "thresholds": {
            "cpr_threshold": cpr_th, "dop_threshold": dop_th,
            "source": "backend/app/core/config.py (CPR_THRESHOLD, DOP_THRESHOLD)",
            "unchanged": True,
            "note": ("Not retuned. Lowering CPR_THRESHOLD until this scene passes would manufacture a "
                     "detection out of an incomplete product."),
        },
        "provenance_legend": {
            MEASURED: ("An observation, or a direct geometric consequence of one: calibrated "
                       "Chandrayaan-2 DFSAR radar, or LOLA topography."),
            MODELLED: ("A model output with no ground truth in this project to check it against: the "
                       "illumination proxy, and the Random Forest P(ice)."),
            DERIVED: "An assumption model applied on top of a measured or modelled quantity.",
            UNAVAILABLE: "Cannot be computed honestly in this build. Render an em dash and the reason.",
        },
    }

    doc["verdict"] = {
        "screening_status": status,
        "criteria_passed": passed_n,
        "criteria_total": len(evidence),
        "label": "No radar ice signature in this swath" if status == "FAIL"
                 else "Radar signature consistent with potential ice",
        "sublabel": (f"{cand_km2:.2f} km² passed CPR > {cpr_th:.2f} and DOP < {dop_th:.2f} "
                     f"within modelled shadow"),
        "confidence": "Low",
        "headline": val(round(cand_km2, 2), "km²", MEASURED,
                        note="Area whose measured radar passes both polarimetric criteria inside shadow."),
        "null_result_caveat": (
            "This is a NULL RESULT on an incomplete measurement, not evidence against ice. Peak CPR in "
            f"the swath is {cpr_s['max']:.4f} against a {cpr_th:.2f} threshold — the product cannot "
            "reach it, because this build derives CPR from amplitude alone. The Stokes S3 phase term from "
            "the complex sli products is required before this scene can be screened at all."
        ),
    }

    doc["values"] = {
        "cpr_mean": val(round(cpr_s["mean"], 6), "", MEASURED,
                        note=f"Mean over {cpr_s['n']:,} pixels carrying amplitude. The API reports "
                             f"{cpr_n['mean']:.6f} by averaging across the void as well."),
        "cpr_max": val(round(cpr_s["max"], 6), "", MEASURED),
        "cpr_p50": val(round(cpr_s["p50"], 6), "", MEASURED),
        "dop_mean": val(round(dop_s["mean"], 6), "", MEASURED,
                        note=f"Mean over the amplitude mask. The API reports {dop_n['mean']:.6f}."),
        "dop_min": val(round(dop_s["min"], 6), "", MEASURED,
                       note="Minimum over measured pixels only; the API's 0.0 is padding."),
        "dop_p50": val(round(dop_s["p50"], 6), "", MEASURED),
        "psr_area_km2": val(None, "km²", UNAVAILABLE,
                            reason=(f"The topography is measured now, but the shadow on top of it is not. "
                                    f"{ILLUM_MODEL} It puts {float(t['psr_mask'].mean()) * 100:.1f} % of "
                                    f"the frame below the 0.05 cut — "
                                    f"{float(t['psr_mask'].sum()) * cell_km2:,.0f} km² of a "
                                    f"{cpr.size * cell_km2:,.0f} km² scene. A PSR area is withheld until "
                                    f"the horizon computation replaces the proxy; a number from this "
                                    f"model would describe the expression, not the Moon.")),
        "mean_slope_deg": val(round(float(t["slope_deg"].mean()), 4), "°", MEASURED, note=SLOPE_NOTE),
        "max_slope_deg": val(round(float(t["slope_deg"].max()), 4), "°", MEASURED, note=SLOPE_NOTE),
        "p_ice_max": val(round(pice["max"], 4), "", MODELLED,
                         note=(f"Random Forest peak over the {pice['n']:,} measured pixels. This can never "
                               f"be MEASURED: there is no ground-truth ice label anywhere in this project, "
                               f"so nothing exists to validate it against, and MODELLED is its honest "
                               f"ceiling. It also disagrees with the physics screening — it puts "
                               f"{pice['fraction_above_0_5'] * 100:.1f} % of the swath at P >= 0.5 while "
                               f"peak CPR is {cpr_th / max(cpr_s['max'], 1e-9):.0f}x below threshold. Its "
                               f"ice class was trained on CPR 1.05-2.5, a range this amplitude-only "
                               f"product cannot reach, and one of its six features (illumination) is the "
                               f"invented proxy. The number describes the model, not the ground.")),
        "p_ice_mean": val(round(pice["mean"], 4), "", MODELLED),
        "candidate_area_km2": val(round(cand_km2, 2), "km²", MEASURED),
        "expected_volume_m3": val(round(v_exp, 0), "m³", DERIVED,
                                  note=f"candidate area x {cfg.DEFAULT_ICE_DEPTH_M} m depth x "
                                       f"{cfg.DEFAULT_ICE_FRACTION} pore fraction. Zero area gives zero "
                                       "volume; the assumptions are untested either way."),
        "conservative_volume_m3": val(round(v_cons, 0), "m³", DERIVED),
        "upper_volume_m3": val(round(v_up, 0), "m³", DERIVED),
        "rover_traverse_km": val(None, "km", UNAVAILABLE,
                                 reason="Traverse planning is not wired to this file yet. The cost surface "
                                        "would now be measured LOLA slope and hazard, but the target still "
                                        "comes from a hardcoded grid centre and no Dijkstra solve runs "
                                        "here, so a distance would be an unfinished code path, not a "
                                        "result."),
        "landing_site": val(None, "", UNAVAILABLE,
                            reason="The backend's five sites are hardcoded grid offsets (Alpha 18,50 / "
                                   "Beta 82,75 / Gamma 78,25 / Delta 50,15 / Epsilon 48,85), asserted "
                                   "rather than searched, and their lat/lon comes from a flat 30.37 km per "
                                   "degree constant that is wrong by ~57x in longitude at this latitude. "
                                   "Withheld until the site search runs."),
    }
    doc["evidence"] = evidence
    doc["measured_statistics"] = {
        "cpr": {"masked": cpr_s, "naive_frame": cpr_n},
        "dop": {"masked": dop_s, "naive_frame": dop_n},
        "p_ice_over_measured": pice,
        "terrain_measured": {
            "post_spacing_m": NATIVE_POST_M,
            "grid_spacing_m": list(spacing),
            "label": f"computed at {NATIVE_POST_M:g} m LOLA posts, carried on a {GRID_POST_M:g} m grid",
            "slope_deg": {"mean": float(t["slope_deg"].mean()), "p50": float(np.percentile(t["slope_deg"], 50)),
                          "p90": float(np.percentile(t["slope_deg"], 90)),
                          "p99": float(np.percentile(t["slope_deg"], 99)),
                          "max": float(t["slope_deg"].max())},
            "roughness_m": {"mean": float(t["roughness"].mean()), "p50": float(np.percentile(t["roughness"], 50)),
                            "p90": float(np.percentile(t["roughness"], 90)),
                            "p99": float(np.percentile(t["roughness"], 99))},
            "hazard": {"mean": float(haz.mean()), "p50": float(np.percentile(haz, 50)),
                       "p90": float(np.percentile(haz, 90)), "p99": float(np.percentile(haz, 99))},
            "dem_min_m": float(dem.min()), "dem_max_m": float(dem.max()),
        },
        "illumination_modelled": {
            "psr_px": int(t["psr_mask"].sum()), "doubly_px": int(t["doubly"].sum()),
            "psr_fraction": float(t["psr_mask"].mean()), "doubly_fraction": float(t["doubly"].mean()),
        },
        "screening": {
            "cpr_pass_px": int(cpr_pass.sum()), "dop_pass_px": int(dop_pass.sum()),
            "candidate_px": cand_n, "candidate_area_km2": cand_km2,
            "doubly_overlap_px": doubly_overlap,
        },
    }
    doc["notes"] = [
        "Every number in this file is reproducible by re-running the generator; nothing is hand-entered.",
        "MEASURED statistics are taken over the amplitude mask at native 25 m/px. The API's equivalents "
        "average across the never-observed void and are therefore lower by construction.",
        f"The DEM is measured LOLA topography ({DEM_PROV['provenance']}), verified bit-identical to "
        f"lola/ldem_frame_25m.tif on every run, so elevation, slope, roughness and hazard are MEASURED. "
        f"They are {NATIVE_POST_M:g} m-post quantities on a {GRID_POST_M:g} m grid and are labelled with "
        f"the {NATIVE_POST_M:g} m spacing they were computed at, not the grid they are carried on.",
        "Illumination, PSR and the doubly-shadowed mask are the one remaining invented model here: a "
        "brightness proxy with no horizon term. They stay MODELLED, and PSR area stays UNAVAILABLE.",
        "Boulder risk is NO DATA, not zero. The hazard blend drops its weight and renormalises over slope "
        "and roughness, so hazard is a two-term hazard in [0, 1] and hazard_model says so.",
        "P(ice) can never be MEASURED in this project: there are no ground-truth ice labels to validate it "
        "against. MODELLED is its ceiling.",
        "The screening threshold was NOT retuned to make this scene pass.",
        "A FAIL here is a null result on an incomplete product, not evidence against ice.",
    ]
    return doc


def emit(crater_id: str) -> Path:
    doc = build(crater_id)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{crater_id}.json"
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")

    hr("EMITTED")
    print(f"  {out}")
    print(f"  {out.stat().st_size:,} bytes")
    v = doc["values"]
    print("\n  the headline cells, each with the mark the UI must render:")
    for k in ("cpr_mean", "cpr_max", "dop_mean", "dop_p50", "psr_area_km2", "mean_slope_deg",
              "max_slope_deg", "p_ice_max", "candidate_area_km2", "expected_volume_m3",
              "rover_traverse_km", "landing_site"):
        rec = v[k]
        shown = ("—  (" + rec["provenance"] + ")" if rec["value"] is None
                 else f"{rec['value']:<14g} {rec['provenance']}")
        print(f"    {k:22s} {shown}")
    print(f"\n  verdict  {doc['verdict']['screening_status']}  "
          f"{doc['verdict']['criteria_passed']}/{doc['verdict']['criteria_total']} criteria  "
          f"\"{doc['verdict']['label']}\"")
    return out


def main() -> int:
    craters = sys.argv[1:] or ["faustini"]
    for c in craters:
        emit(c)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

