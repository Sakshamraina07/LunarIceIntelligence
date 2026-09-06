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
this file described a build in which the native DEM really did hold Gaussians
and sinusoids. It no longer does. Measured, not assumed:

    dem_native.tif  vs  lola/ldem_frame_25m.tif
    max|diff| 0.0 m   rms 0.0 m   bit-identical True   pearson r 1.000000000

The file was called dem_native_synthetic.tif until Phase 6. It was renamed
because a filename asserting "synthetic" over a real measurement is the same
defect class as a plausible placeholder standing in for one -- and this
project had already caught that twice, in shackleton_lola_dem.tif holding
Faustini's bytes and *_ohrc_pan.tif holding a hillshade. The identity check
below is unchanged and still fatal. The rest of this note is retained
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

# ── console encoding ────────────────────────────────────────────────────────
# The Windows console is cp1252 by default, and a single unencodable character
# in a progress line raises UnicodeEncodeError and kills a 30-minute run at
# minute 28. Reconfiguring here rather than relying on PYTHONIOENCODING means it
# cannot be forgotten by whoever launches the script. errors="replace" because a
# diagnostic print must never be the thing that fails a computation.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

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
    f"native/dem_native.tif holds that measured LOLA topography "
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
#: Filled from the horizon product's own sidecar when it is present, so the
#: wording can never describe a run that did not happen. The fallback is the
#: honest absent state, not the deleted proxy.
ILLUM_MODEL = (
    "No horizon product has been computed for this build, so illumination and PSR are "
    "UNAVAILABLE. They are NOT filled from the brightness proxy this project used to carry "
    "(hillshade(sun 1.5 deg) * elev_norm**1.3), which had no horizon term in it and darkened "
    "77 % of the frame. Run: python backend/scripts/compute_horizon.py"
)

MASK_NOTE = (
    "Over the amplitude mask at native 25 m/px. The request path resamples to "
    "100 x 100 and averages across the never-observed void, which moves CPR mean "
    "by 5.5x and destroys the DOP median outright."
)

# One reason string per withheld quantity, written once and referenced, so the
# UI cannot end up showing two different explanations for the same absence.
PSR_ABSENT_REASON = (
    "The topography is measured, but no shadow has been computed on top of it. " + ILLUM_MODEL
)

P_ICE_ABSENT_REASON = (
    "WITHDRAWN, not missing. The Random Forest behind this figure was fitted to np.random.uniform "
    "labels with a fixed seed, and its ice class was defined as CPR 1.05-2.5 -- a range this "
    "amplitude-only product cannot reach at all, since the swath's peak CPR is 0.0534. Every "
    "probability it produced was an extrapolation from fabricated examples, and one of its six "
    "features was the illumination proxy. It is unwired, not retrained: better synthetic labels are "
    "still synthetic. Step 4 now reports the criteria screen, which is measured."
)

DOUBLY_ABSENT_REASON = (
    "A doubly-shadowed core is terrain that is never directly lit AND receives no scattered light "
    "from lit terrain. The second term is the missing one: pass 2 of compute_horizon.py "
    "(--doubly) tests whether the crest bounding each view direction is itself in shadow, and it "
    "has not been run. Reported absent rather than substituted with the single-shadow mask, which "
    "would silently answer a different question."
)

LANDING_ABSENT_REASON = (
    "The five sites are hardcoded grid offsets (18,50 / 82,75 / 78,25 / 50,15 / 48,85), asserted and "
    "then scored, not searched -- and their lat/lon came from a flat 30.37 km per degree constant that "
    "is wrong by about 57x in longitude at this latitude. Withheld until the Phase 3 per-pixel search "
    "over the native frame runs."
)

ROVER_ABSENT_REASON = (
    "No traverse is planned from this file. The cost surface would be measured LOLA slope and hazard, "
    "but the target is still a hardcoded grid centre and no Dijkstra solve runs here, so a distance or "
    "an energy figure would be an unfinished code path rather than a result. Phase 4."
)


def assert_dem_is_lola(dem: np.ndarray) -> dict:
    """
    Re-measure the DEM's identity against the LOLA crop, on every run.

    `dem_native.tif` must be byte-identical to `lola/ldem_frame_25m.tif`. If a
    future pipeline change ever makes it something else -- a placeholder, a
    smoothed copy, a different product -- every terrain mark in this file
    silently becomes a lie. So the identity is a FATAL check with a printed
    residual, not a comment, and its tolerance is 0.0 and stays 0.0.

    Regenerating the reference is NOT editing anything here: it is running the
    ingest and then process_real_sar_pipeline.py, which reads ldem_frame_25m.tif
    and writes dem_native.tif. A gate that gets relaxed the first time it is
    inconvenient stops being a gate.
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
        "compared": ["native/dem_native.tif", "lola/ldem_frame_25m.tif"],
        "max_abs_diff_m": float(np.abs(d).max()),
        "rms_diff_m": float(np.sqrt((d ** 2).mean())),
        "bit_identical": bool(np.array_equal(a, b)),
        "tolerance_m": 0.0,
    }
    if rec["max_abs_diff_m"] > rec["tolerance_m"]:
        raise SystemExit(
            "native/dem_native.tif is NOT the LOLA crop "
            f"(max|diff| {rec['max_abs_diff_m']:.6f} m). Either the ingest changed "
            "or the two files were regenerated out of step. No terrain number may be marked "
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
        "dem": NATIVE_DIR / "dem_native.tif",
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
    Slope and roughness ONLY, using the SAME formulas as the backend modules so
    the static file cannot silently disagree with them:
      module_d_terrain.compute_terrain_metrics / compute_hazard_score

    Illumination is NOT computed here any more -- see the note below and
    backend/scripts/compute_horizon.py.

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

    # THE BRIGHTNESS PROXY IS GONE. It was:
    #     hillshade(sun 1.5 deg) * elev_norm**1.3   < 0.05
    # an invented expression with no horizon term in it, which darkened 77.18 %
    # of the frame and therefore told you about the expression rather than about
    # the Moon. Its "doubly shadowed" companion was that shadow intersected with
    # the lowest elevation quintile of the DEM -- an elevation percentile, which
    # is not a shadowing event at all.
    #
    # Illumination now comes from a horizon computation over the FULL LOLA polar
    # array (backend/scripts/compute_horizon.py), because at the pole the horizon
    # is set by rim crests tens of kilometres outside this frame. This function
    # computes terrain only.
    del slope_rad, aspect_rad

    return {
        "slope_deg": slope_deg,
        "roughness": roughness,
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


def threshold_grid(measured: np.ndarray, configured: float, span: tuple[float, float],
                   steps: int = 9) -> list[float]:
    """
    The thresholds a sweep is evaluated at. STATED, not adaptive.

    Two things have to be visible at once, and a single linear ramp shows
    neither: where the data actually lives, and where the configured threshold
    sits relative to it. So the grid is the union of

      * the measured distribution's own percentiles (p50, p90, p99, p99.9, max),
      * a fixed linear ramp across `span`,
      * the configured threshold itself, always, so the sweep can never be read
        without seeing the operating point.

    This is a sensitivity study, not a search for a threshold that passes. Rule 4
    stands: nothing here is fed back into config.py.
    """
    qs = [float(np.percentile(measured, q)) for q in (50.0, 90.0, 99.0, 99.9)]
    ramp = list(np.linspace(span[0], span[1], steps))
    grid = sorted({round(float(x), 6) for x in (qs + ramp + [float(measured.max()), configured])})
    return [x for x in grid if x >= 0.0]


def sweep_threshold(cpr, dop, valid, *, axis: str, grid: list[float],
                    cpr_th: float, dop_th: float, cell_km2: float,
                    depth_m: float, fraction: float) -> list[dict]:
    """
    Re-threshold the native arrays and count. Nothing is modelled here.

    `area_km2` is MEASURED: a pixel count times the frame's own cell area. The
    volume column is DERIVED from it by the stated depth and pore fraction, and
    is only ever as good as those two assumptions.

    The other axis is held at its configured value, so a row answers "what would
    the candidate area be if THIS threshold moved and nothing else did".
    """
    rows = []
    for th in grid:
        if axis == "cpr_threshold":
            m = (cpr > th) & (dop < dop_th) & valid
        elif axis == "dop_threshold":
            m = (cpr > cpr_th) & (dop < th) & valid
        else:
            raise ValueError(f"sweep_threshold does not sweep {axis!r}")
        n = int(m.sum())
        area = n * cell_km2
        rows.append({
            "threshold": th,
            "is_configured_value": bool(abs(th - (cpr_th if axis == "cpr_threshold" else dop_th)) < 1e-12),
            "candidate_px": n,
            "candidate_area_km2": round(area, 6),
            "candidate_area_provenance": MEASURED,
            "volume_m3": round(area * 1e6 * depth_m * fraction, 3),
            "volume_provenance": DERIVED,
        })
    return rows


def sweep_assumption(area_km2: float, *, axis: str, grid: list[float],
                     depth_m: float, fraction: float) -> list[dict]:
    """
    Depth and pore-fraction sweeps. The candidate AREA does not move on these
    axes -- only the assumption multiplying it does -- so the area column is
    constant and the volume column is linear in the swept value.

    `volume_m3_per_km2` is carried as well. When the candidate area is a measured
    zero the volume column is all zeros and says nothing; the per-km2 rate still
    shows the assumption's actual sensitivity, and is labelled as a rate rather
    than as a result.
    """
    rows = []
    for x in grid:
        d = x if axis == "assumed_depth_m" else depth_m
        f = x if axis == "ice_fraction" else fraction
        rate = 1e6 * d * f
        rows.append({
            "threshold": x,
            "is_configured_value": bool(abs(x - (depth_m if axis == "assumed_depth_m" else fraction)) < 1e-12),
            "candidate_area_km2": round(area_km2, 6),
            "candidate_area_provenance": MEASURED,
            "volume_m3": round(area_km2 * rate, 3),
            "volume_m3_per_km2": round(rate, 3),
            "volume_provenance": DERIVED,
        })
    return rows


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

    # ------------------------------------------------------- illumination
    # Absent unless the horizon product exists. There is deliberately no
    # fallback: substituting the deleted proxy here would put a modelled
    # quantity back into a slot the UI marks as measured.
    illum_frame = None
    illum_meta = None
    try:
        from app.ingestion.horizon_frame import load_horizon
        hp = load_horizon(LOLA_DIR)
        frame_geom = None
        try:
            from app.ingestion.sar_geometry import read_geotiff_frame
            frame_geom = read_geotiff_frame(LH_TIF, LH_XML)
        except Exception as exc:
            print(f"  ! horizon found but the SAR frame is unreadable ({exc}); "
                  f"illumination stays UNAVAILABLE")
        if frame_geom is not None:
            illum_frame = hp.to_frame(frame_geom, cpr.shape)
            illum_meta = hp.meta
    except FileNotFoundError as exc:
        print(f"  ! {exc}")

    # One summary of the illumination state, derived once. Every value, every
    # evidence row and every note below reads from THIS, so the file cannot say
    # illumination is available in one place and absent in another.
    if illum_frame is not None:
        ifrac = illum_frame["illumination_fraction"]
        psr_m = illum_frame["psr_mask"]
        finite_i = np.isfinite(ifrac)
        ILLUM = {
            "available": True,
            "fraction": ifrac,
            "psr": psr_m,
            "psr_px": int(psr_m.sum()),
            "psr_km2": float(psr_m.sum() * cell_km2),
            "psr_fraction_of_frame": float(psr_m.mean()),
            "mean_fraction": float(np.nanmean(ifrac)),
            "n_nan": int((~finite_i).sum()),
            "doubly": illum_frame.get("doubly_shadowed"),
            "svf": illum_frame["sky_view_factor"],
            "native_m": illum_frame["native_metres_per_pixel"],
            "effective_m": illum_frame["effective_metres_per_pixel"],
            "decimation": illum_frame["decimation_factor"],
            "meta": illum_meta,
        }
        ILLUM["note"] = (
            f"Horizon computation over the full {illum_meta['array_shape'][0]}x"
            f"{illum_meta['array_shape'][1]} LOLA polar array at "
            f"{ILLUM['effective_m']:g} m ({ILLUM['native_m']:g} m posts decimated "
            f"{ILLUM['decimation']}x), swept over {illum_meta['azimuths']} azimuths. The solar "
            f"elevation is computed PER PIXEL from its own latitude and the subsolar band is "
            f"integrated in closed form; it reaches "
            f"{illum_meta['elevation_range_deg'][1]:.2f} deg at this frame's outer edge, not a "
            f"flat 1.54 deg. "
            f"{illum_meta['sun_state_model']} "
            f"READ THIS AS A {ILLUM['effective_m']:g} m QUANTITY however it is displayed: "
            f"resampling it onto the {GRID_POST_M:g} m grid adds no shadow detail."
        )
    else:
        ILLUM = {"available": False, "note": ILLUM_MODEL, "psr": None, "doubly": None}

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

    if ILLUM["available"]:
        m = ILLUM["meta"]
        hr(f"ILLUMINATION / PSR -- horizon computation at {ILLUM['effective_m']:g} m")
        print(f"  source      {m['source_product']}  {m['array_shape'][0]}x{m['array_shape'][1]} "
              f"@ {ILLUM['effective_m']:g} m ({ILLUM['native_m']:g} m posts, {ILLUM['decimation']}x block mean)")
        print(f"  sweep       {m['azimuths']} azimuths; subsolar band "
              f"{m.get('subsolar_latitude_range_deg', ['?', '?'])} deg integrated in closed form")
        print(f"  elevation   computed PER PIXEL from its own latitude: "
              f"{m.get('solar_elevation_formula', 'n/a')}")
        # The frame's OWN maximum, from the frame's own latitude bounds. The
        # sidecar's figure is over the whole polar array (outer corner -75.9 deg,
        # 15.64 deg) and quoting it here would attach an array-wide number to a
        # frame-wide statement — the same domain error as an unlabelled area.
        _frame_lat = -84.833408
        _frame_el = 1.54 + (90.0 - abs(_frame_lat))
        # The polar array's own figure, derived from the grid the sidecar records
        # rather than read from a key older sidecars do not carry. Exact, not a
        # fallback estimate: the corner latitude is a closed form of the shape
        # and the spacing.
        _n = ILLUM["meta"]["array_shape"][0]
        _rho = (( _n - 1) / 2.0) * (2 ** 0.5) * ILLUM["effective_m"]
        _arr_lat = np.degrees(2.0 * np.arctan(_rho / (2.0 * 1737400.0)) - np.pi / 2.0)
        _arr_el = 1.54 + (90.0 - abs(_arr_lat))
        print(f"              reaches {_frame_el:.2f} deg at THIS FRAME's outer edge "
              f"({_frame_lat:.4f} deg), and {_arr_el:.2f} deg at the polar array's "
              f"({_arr_lat:.2f} deg) — NOT a flat 1.54 deg, which bounds the subsolar "
              f"latitude, not the elevation")
        print(f"  illum frac  mean {ILLUM['mean_fraction']:.4f}  "
              f"p25 {np.nanpercentile(ILLUM['fraction'], 25):.4f}  "
              f"p50 {np.nanpercentile(ILLUM['fraction'], 50):.4f}  "
              f"p75 {np.nanpercentile(ILLUM['fraction'], 75):.4f}  "
              f"max {np.nanmax(ILLUM['fraction']):.4f}")
        print(f"  PSR         {ILLUM['psr_px']:>12,d} px  {ILLUM['psr_km2']:10.2f} km2  "
              f"{ILLUM['psr_fraction_of_frame'] * 100:6.3f} % of the frame")
        if ILLUM["doubly"] is not None:
            db = ILLUM["doubly"]
            print(f"  doubly      {int(db.sum()):>12,d} px  {db.sum() * cell_km2:10.2f} km2  "
                  f"({db.sum() / max(ILLUM['psr_px'], 1) * 100:.2f} % of the PSR)")
        else:
            print(f"  doubly      ABSENT -- pass 2 (--doubly) not run; the scattered-light term "
                  f"is the missing one")
        print(f"  resolution  {ILLUM['effective_m']:g} m shadow mask carried on a {GRID_POST_M:g} m grid "
              f"(ratio {ILLUM['effective_m'] / GRID_POST_M:.1f}x) -- labelled, not upgraded")
    else:
        hr("ILLUMINATION / PSR -- UNAVAILABLE, and not substituted")
        print(f"  {ILLUM['note']}")

    # ---------------------------------------------------------------- screening
    # THE CRITERIA SCREEN, and nothing else. Two measured polarimetric tests
    # inside the amplitude mask:
    #
    #     candidate = (cpr > CPR_THRESHOLD) & (dop < DOP_THRESHOLD) & valid
    #
    # v1.0 of this file intersected that with `t["psr_mask"]`, the illumination
    # PROXY's shadow. That made the headline area a partly-modelled quantity
    # wearing a MEASURED mark: the proxy darkens 77 % of the frame, so it was
    # not discriminating a cold trap, it was only multiplying by a large mask.
    # The shadow terms are now criteria of their own and both read UNAVAILABLE
    # until the Phase 2 horizon computation exists. The headline is a measured
    # zero, which is a result.
    cpr_th, dop_th = float(cfg.CPR_THRESHOLD), float(cfg.DOP_THRESHOLD)
    cpr_pass = (cpr > cpr_th) & valid
    dop_pass = (dop < dop_th) & valid
    candidate = cpr_pass & dop_pass
    cand_n = int(candidate.sum())
    cand_km2 = cand_n * cell_km2
    valid_n = int(valid.sum())
    cpr_pass_frac = float(cpr_pass.sum()) / max(valid_n, 1)
    dop_pass_frac = float(dop_pass.sum()) / max(valid_n, 1)
    screen_frac = float(cand_n) / max(valid_n, 1)

    hr("SCREENING -- CPR > th AND DOP < th, over the amplitude mask only")
    print(f"  threshold   CPR > {cpr_th}   DOP < {dop_th}   (backend/app/core/config.py, NOT retuned)")
    print(f"  CPR > {cpr_th}   {int(cpr_pass.sum()):>12,d} px of {valid_n:,} measured  "
          f"({cpr_pass_frac * 100:6.3f} %)   -> highest CPR in the swath is {cpr_s['max']:.6f}")
    print(f"  DOP < {dop_th}  {int(dop_pass.sum()):>12,d} px of {valid_n:,} measured  "
          f"({dop_pass_frac * 100:6.3f} %)")
    print(f"  candidates  {cand_n:>12,d} px  {cand_km2:.4f} km2  "
          f"({screen_frac * 100:6.3f} % of the measured swath)")
    print(f"  status      {'PASS' if cand_n > 0 else 'FAIL'}"
          f"   <- a MEASURED zero: no pixel clears CPR, so the AND cannot be non-empty")
    print("  the shadow terms are no longer inside this mask; they are criteria 3 and 4 "
          "and both read UNAVAILABLE until Phase 2.")

    # ------------------------------------------------------------ volume tiers
    # Each tier carries the two assumptions that produced it AS DATA, so the UI
    # never hardcodes "2 m / 5 %" in a caption that can drift away from config.
    tier_spec = [
        ("conservative", cfg.CONSERVATIVE_ICE_DEPTH_M, cfg.CONSERVATIVE_ICE_FRACTION),
        ("expected", cfg.DEFAULT_ICE_DEPTH_M, cfg.DEFAULT_ICE_FRACTION),
        ("upper", cfg.UPPER_ICE_DEPTH_M, cfg.UPPER_ICE_FRACTION),
    ]
    volume_tiers = []
    for name, depth, frac in tier_spec:
        volume_tiers.append({
            "tier": name,
            "assumed_depth_m": float(depth),
            "assumed_pore_fraction": float(frac),
            "volume_m3": round(cand_km2 * 1e6 * float(depth) * float(frac), 3),
            "volume_m3_per_km2": round(1e6 * float(depth) * float(frac), 3),
            "provenance": DERIVED,
            "source": "backend/app/core/config.py",
            "note": (f"candidate area x {depth:g} m assumed depth x {frac:g} assumed pore fraction. "
                     "Both assumptions are untested in this build; neither is a measurement."),
        })
    v_cons, v_exp, v_up = (tv["volume_m3"] for tv in volume_tiers)
    print(f"\n  volume tiers from {cand_km2:.4f} km2 (each DERIVED, assumptions carried as data):")
    for tv in volume_tiers:
        print(f"    {tv['tier']:13s} depth {tv['assumed_depth_m']:5.1f} m  "
              f"fraction {tv['assumed_pore_fraction']:.2f}"
              f"  -> {tv['volume_m3']:>14,.0f} m3   ({tv['volume_m3_per_km2']:,.0f} m3 per km2)")

    # -------------------------------------------------------------- 1B sweeps
    # Previously module_g_volume.run_sensitivity_sweep, which computed nothing:
    # scale = max(0.2, 1.0 - (val - 1.0) * 0.8), a constant best_landing_site_id,
    # and rover columns that were straight-line functions of the swept value.
    # This is the real thing -- re-threshold the native arrays and count.
    cpr_grid = threshold_grid(cpr[valid], cpr_th, (0.0, 1.2))
    dop_grid = threshold_grid(dop[valid], dop_th, (0.0, 0.5))
    depth_grid = [0.5, 1.0, 2.0, 5.0, 10.0, 20.0]
    frac_grid = [0.01, 0.05, 0.10, 0.15, 0.20, 0.30]
    sensitivity = {
        "cpr_threshold": {
            "parameter": "cpr_threshold", "unit": "", "baseline": cpr_th,
            "grid_source": ("measured CPR percentiles (p50/p90/p99/p99.9/max), union a 0.0-1.2 linear "
                            "ramp, union the configured threshold"),
            "held_constant": {"dop_threshold": dop_th},
            "rows": sweep_threshold(cpr, dop, valid, axis="cpr_threshold", grid=cpr_grid,
                                    cpr_th=cpr_th, dop_th=dop_th, cell_km2=cell_km2,
                                    depth_m=float(cfg.DEFAULT_ICE_DEPTH_M),
                                    fraction=float(cfg.DEFAULT_ICE_FRACTION)),
        },
        "dop_threshold": {
            "parameter": "dop_threshold", "unit": "", "baseline": dop_th,
            "grid_source": ("measured DOP percentiles (p50/p90/p99/p99.9/max), union a 0.0-0.5 linear "
                            "ramp, union the configured threshold"),
            "held_constant": {"cpr_threshold": cpr_th},
            "rows": sweep_threshold(cpr, dop, valid, axis="dop_threshold", grid=dop_grid,
                                    cpr_th=cpr_th, dop_th=dop_th, cell_km2=cell_km2,
                                    depth_m=float(cfg.DEFAULT_ICE_DEPTH_M),
                                    fraction=float(cfg.DEFAULT_ICE_FRACTION)),
        },
        "assumed_depth_m": {
            "parameter": "assumed_depth_m", "unit": "m",
            "baseline": float(cfg.DEFAULT_ICE_DEPTH_M),
            "grid_source": "stated grid; the candidate AREA does not move on this axis",
            "held_constant": {"ice_fraction": float(cfg.DEFAULT_ICE_FRACTION),
                              "cpr_threshold": cpr_th, "dop_threshold": dop_th},
            "rows": sweep_assumption(cand_km2, axis="assumed_depth_m", grid=depth_grid,
                                     depth_m=float(cfg.DEFAULT_ICE_DEPTH_M),
                                     fraction=float(cfg.DEFAULT_ICE_FRACTION)),
        },
        "ice_fraction": {
            "parameter": "ice_fraction", "unit": "",
            "baseline": float(cfg.DEFAULT_ICE_FRACTION),
            "grid_source": "stated grid; the candidate AREA does not move on this axis",
            "held_constant": {"assumed_depth_m": float(cfg.DEFAULT_ICE_DEPTH_M),
                              "cpr_threshold": cpr_th, "dop_threshold": dop_th},
            "rows": sweep_assumption(cand_km2, axis="ice_fraction", grid=frac_grid,
                                     depth_m=float(cfg.DEFAULT_ICE_DEPTH_M),
                                     fraction=float(cfg.DEFAULT_ICE_FRACTION)),
        },
        "provenance": MEASURED,
        "computed_by": "backend/scripts/build_analysis.py (sweep_threshold / sweep_assumption)",
        "withheld_columns": {
            "rover_distance_km": ("Phase 4. No traverse is planned from this file, so a distance column "
                                  "would be an unfinished code path, not a result."),
            "rover_energy_wh": "Phase 4, same reason.",
            "best_landing_site_id": ("Phase 3. The sites are still hardcoded grid offsets, so the winner "
                                     "cannot move with a threshold and a column saying so would be noise."),
        },
        "note": ("candidate_area_km2 is a pixel count times the frame's own cell area, so it is MEASURED "
                 "at every row. volume_m3 is DERIVED from it by the assumed depth and pore fraction. The "
                 "CPR axis is degenerate at the configured operating point: the swath's peak CPR is "
                 f"{cpr_s['max']:.6f}, so every threshold at or above it returns exactly zero pixels. "
                 "That flat line is the measurement, not a defect in the sweep."),
    }

    hr("SENSITIVITY -- 1B, computed by re-thresholding the native arrays")
    for axis in ("cpr_threshold", "dop_threshold"):
        blk = sensitivity[axis]
        nz = [row for row in blk["rows"] if row["candidate_px"] > 0]
        print(f"  {axis:16s} {len(blk['rows']):2d} rows, baseline {blk['baseline']:g}, "
              f"{len(nz)} row(s) with a non-zero candidate count")
        for row in blk["rows"]:
            flag = "  <- configured" if row["is_configured_value"] else ""
            print(f"      th {row['threshold']:<10.6g} {row['candidate_px']:>10,d} px  "
                  f"{row['candidate_area_km2']:>12.4f} km2{flag}")

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
            # A TICK IMPLIES EVIDENCE, AND THIS ONE CARRIES NONE.
            #
            # METHODS 7.9.2 establishes by Monte Carlo that the amplitude proxy is
            # a CHANNEL-IMBALANCE estimator with exactly zero sensitivity to the
            # circular polarisation ratio. This row is the same algebra seen from
            # the other side: DOP_amp = |tanh(x/2)| with x = ln(LH/LV), so
            # balanced channels -- the normal case over regolith -- drive it to
            # zero whatever the surface is made of. It passes because the
            # instrument's two receive channels agree, not because anything about
            # this terrain is depolarising.
            #
            # So it gets a third state. Rendering it as the one green tick beside
            # four crosses would make the least informative row on the card the
            # first number a reviewer reads.
            "informative": False,
            "uninformative_reason": (
                f"Satisfied by {dop_pass.sum() / max(valid.sum(), 1) * 100:.1f} % of measured pixels "
                f"because the amplitude proxy collapses when the two receive channels are "
                f"balanced, which is the ordinary case over regolith. It is not evidence of "
                f"volume scattering, and it would read the same over bare rock."),
            "provenance": MEASURED,
            "note": (f"{dop_pass.sum() / max(valid.sum(), 1) * 100:.1f} % of measured pixels sit below "
                     f"{dop_th}. PASSES FOR A REASON THAT IS NOT ABOUT ICE: this build's DOP is "
                     f"|tanh(x/2)| with x = ln(LH/LV), so it measures channel imbalance, and balanced "
                     f"channels are what regolith normally gives. Depolarised returns are consistent "
                     "with volume scattering, but on their own they do not discriminate ice from fine "
                     "dry regolith -- and this proxy does not measure depolarisation in the first "
                     "place. See METHODS 7.9.2."),
        },
        ({
            "criterion": "psr_cold_trap_overlap",
            "label": "Overlap with a shadowed cold trap",
            "measured": round(float((candidate & ILLUM["psr"]).sum()) * cell_km2, 4),
            "measured_label": "candidate area inside PSR",
            "threshold": 0.0, "comparison": ">",
            "passed": bool((candidate & ILLUM["psr"]).sum() > 0),
            "provenance": MEASURED,
            "note": (f"TESTABLE NOW. The frame holds {ILLUM['psr_km2']:,.1f} km² of permanently "
                     f"shadowed terrain ({ILLUM['psr_fraction_of_frame'] * 100:.2f} % of it), from a "
                     f"horizon computation rather than a brightness proxy. This row fails because the "
                     f"CANDIDATE set is empty — no pixel clears CPR — not because there is nowhere "
                     f"cold to look. The two are different findings and this build can now tell them "
                     f"apart. {ILLUM['note']}"),
        } if ILLUM["available"] else {
            "criterion": "psr_cold_trap_overlap",
            "label": "Overlap with a shadowed cold trap",
            "measured": None, "measured_label": "no horizon computation",
            "threshold": None, "comparison": None,
            "passed": False,
            "provenance": UNAVAILABLE,
            "note": "WITHHELD, not failed. " + ILLUM["note"],
        }),
        ({
            "criterion": "doubly_shadowed_core_overlap",
            "label": "Overlap with a doubly-shadowed core",
            "measured": round(float((candidate & ILLUM["doubly"]).sum()) * cell_km2, 4),
            "measured_label": "candidate area inside a doubly-shadowed core",
            "threshold": 0.0, "comparison": ">",
            "passed": bool((candidate & ILLUM["doubly"]).sum() > 0),
            "provenance": DERIVED,
            "note": (f"{float(ILLUM['doubly'].sum()) * cell_km2:,.2f} km² of this frame is never "
                     f"directly lit AND has no sunlit crest bounding its view in any swept azimuth. "
                     + (ILLUM["meta"].get("doubly_shadowed") or {}).get("approximation", "")
                     + " Fails here because the candidate set is empty, not because no such terrain "
                     "exists."),
        } if (ILLUM["available"] and ILLUM["doubly"] is not None) else {
            "criterion": "doubly_shadowed_core_overlap",
            "label": "Overlap with a doubly-shadowed core",
            "measured": None, "measured_label": "no scattered-light term",
            "threshold": None, "comparison": None,
            "passed": False,
            "provenance": UNAVAILABLE,
            "note": "WITHHELD, not failed. " + DOUBLY_ABSENT_REASON,
        }),
        ({
            "criterion": "thermal_stability_expected",
            "label": "Thermal stability expected",
            "measured": 110.0, "measured_label": "inferred ceiling in PSR",
            "threshold": 110.0, "comparison": "<",
            "passed": bool((candidate & ILLUM["psr"]).sum() > 0),
            "provenance": DERIVED,
            "note": ("INFERRED FROM ILLUMINATION, NOT FROM MEASURED TEMPERATURE. A surface lit in "
                     "none of the sampled sun states receives no direct solar input, and the "
                     "water-ice stability limit over geological time is about 110 K. No Diviner or "
                     "other thermal product is on disk; the 110 K figure is an assumed threshold "
                     "from the literature. This row follows the PSR-overlap row exactly — it is an "
                     "inference from the same mask, not an independent temperature test, and it is "
                     "marked DERIVED for that reason."),
        } if ILLUM["available"] else {
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
        }),
    ]
    print()
    for e in evidence:
        m = "n/a" if e["measured"] is None else f"{e['measured']:.6g}"
        th = "n/a" if e["threshold"] is None else f"{e['comparison']} {e['threshold']}"
        verdict_word = ("PASS" if e["passed"]
                        else "HELD" if e["provenance"] == UNAVAILABLE
                        else "FAIL")
        print(f"  [{verdict_word}] {e['label']:38s} {e['measured_label']:24s} "
              f"{m:>12s}  vs {th:<10s} {e['provenance']}")

    passed_n = sum(1 for e in evidence if e["passed"])
    # A criterion that passes for a reason unrelated to the question is not
    # evidence, and counting it as though it were is how "1/5" becomes the first
    # number a reviewer reads. Informative passes are counted separately.
    informative_pass_n = sum(1 for e in evidence
                             if e["passed"] and e.get("informative", True))
    uninformative = [e for e in evidence
                     if e["passed"] and not e.get("informative", True)]
    evaluable = [e for e in evidence if e["provenance"] != UNAVAILABLE]
    withheld_n = len(evidence) - len(evaluable)
    status = "PASS" if cand_n > 0 else "FAIL"
    print(f"\n  {passed_n} passed / {len(evaluable)} evaluable / {withheld_n} withheld "
          f"of {len(evidence)} named criteria")

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
            "dem_identity": {
                "file": r["paths"]["dem"],
                "verified_every_run": dem_identity,
                "explanation": ("Holds measured LOLA topography bit-for-bit, verified against "
                                "lola/ldem_frame_25m.tif at tolerance 0.0 on every run by "
                                "assert_dem_is_lola(). Called dem_native_synthetic.tif until "
                                "Phase 6; renamed because a filename asserting 'synthetic' over "
                                "a real measurement is a provenance defect, not a cosmetic one."),
            },
            "sidecar": str(LOLA_SIDECAR.relative_to(BASE_DIR)).replace("\\", "/"),
        },
        "hazard_model": hazard_model,
        "illumination_model": ({
            "provenance": MEASURED,
            "method": ("horizon computation: for each azimuth, "
                       "horizon(az) = max over r of atan((h(p + r*u) - h(p)) / r), "
                       "lit when the solar elevation exceeds it"),
            "algorithm": ILLUM["meta"]["horizon_algorithm"],
            "source_product": ILLUM["meta"]["source_product"],
            "array_shape": ILLUM["meta"]["array_shape"],
            "computed_over": ("the FULL LOLA polar array, not the frame -- at the pole the horizon "
                              "is set by rim crests tens of kilometres outside this 165 x 56 km "
                              "frame, and a horizon computed only inside it would invent sunlight "
                              "that real terrain blocks"),
            "native_metres_per_pixel": ILLUM["native_m"],
            "decimation_factor": ILLUM["decimation"],
            "effective_metres_per_pixel": ILLUM["effective_m"],
            "decimation_method": ILLUM["meta"]["decimation_method"],
            "azimuths": ILLUM["meta"]["azimuths"],
            "subsolar_band_integration": ILLUM["meta"].get("subsolar_band_integration"),
            "subsolar_latitude_range_deg": ILLUM["meta"].get("subsolar_latitude_range_deg"),
            "solar_elevation_formula": ILLUM["meta"].get("solar_elevation_formula"),
            "max_solar_elevation_deg": ILLUM["meta"]["elevation_range_deg"][1],
            "why_not_a_flat_cap": (
                "1.54 deg is the Moon's obliquity, which bounds the SUBSOLAR LATITUDE, not the "
                "solar elevation seen from a site. Max elevation at latitude phi is "
                "1.54 + (90 - |phi|): 1.54 deg at the pole but 6.71 deg at this frame's outer "
                "edge (-84.833408). A flat 1.54 deg cap inflated this array's PSR from 26,900 "
                "to 65,398 km2 and would not have looked wrong."
            ),
            "sun_state_model": ILLUM["meta"]["sun_state_model"],
            "psr_definition": "illumination_fraction == 0, i.e. lit in no sampled sun state",
            "psr_fraction_of_frame": ILLUM["psr_fraction_of_frame"],
            "doubly_shadowed": ILLUM["meta"].get("doubly_shadowed"),
            "resolution_caveat": ILLUM["meta"]["resolution_caveat"],
            "replaces": ("clip(hillshade(sun_altitude=1.5 deg, azimuth=315 deg) * elev_norm ** 1.3, "
                         "0, 1) < 0.05 -- an invented brightness proxy with no horizon term, which "
                         "darkened 77.18 % of the frame"),
        } if ILLUM["available"] else {
            "provenance": UNAVAILABLE,
            "reason": ILLUM["note"],
        }),
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
            # Carried so the UI reads its slope limits from config too. These
            # were typed into StepPanel as literals -- "Slope <= 12 deg" printed
            # beside a 20 deg traversability cutoff, two different numbers for
            # two different purposes rendered as if they were one.
            "max_traversable_slope_deg": float(cfg.MAX_TRAVERSABLE_SLOPE_DEG),
            "critical_landing_slope_deg": float(cfg.CRITICAL_LANDING_SLOPE_DEG),
            "source": ("backend/app/core/config.py (CPR_THRESHOLD, DOP_THRESHOLD, "
                       "MAX_TRAVERSABLE_SLOPE_DEG, CRITICAL_LANDING_SLOPE_DEG)"),
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
        "criteria_evaluable": len(evaluable),
        "criteria_withheld": withheld_n,
        "criteria_informative_passed": informative_pass_n,
        "criteria_uninformative_passed": len(uninformative),
        "criteria_uninformative": [
            {"label": e["label"], "reason": e["uninformative_reason"]} for e in uninformative],
        "criteria_note": (f"{informative_pass_n} of {len(evaluable)} evaluable criteria passed "
                          f"INFORMATIVELY. {len(uninformative)} further passed for a reason unrelated "
                          f"to ice and is shown as such rather than as a tick: "
                          + " ".join(e["uninformative_reason"] for e in uninformative) + " "
                          + f"The other {withheld_n} are WITHHELD, not failed: two shadow terms "
                          f"awaiting the Phase 2 horizon computation, and thermal stability, for which "
                          f"no product and no model exist here. A withheld criterion is not evidence "
                          f"against ice."),
        "label": "No radar ice signature in this swath" if status == "FAIL"
                 else "Radar signature consistent with potential ice",
        "sublabel": (f"{cand_km2:.2f} km² of the {valid_n * cell_km2:,.0f} km² measured swath passed "
                     f"CPR > {cpr_th:.2f} and DOP < {dop_th:.2f}"),
        "confidence": "Low",
        "headline": val(round(cand_km2, 2), "km²", MEASURED,
                        note=("Area whose measured radar passes both polarimetric criteria, inside the "
                              "amplitude mask. No shadow term is in this mask: the illumination proxy was "
                              "removed from it, and the horizon computation that would replace it is "
                              "Phase 2.")),
        "null_result_caveat": (
            "This is a NULL RESULT on an incomplete measurement, not evidence against ice. Peak CPR in "
            f"the swath is {cpr_s['max']:.4f} against a {cpr_th:.2f} threshold — the product cannot "
            "reach it, because this build derives CPR from amplitude alone. The Stokes S3 phase term from "
            "the complex sli products is required before this scene can be screened at all."
        ),
    }

    # Every figure the twelve steps render, each an AnalysisValue. A step that
    # cannot be computed honestly yet emits UNAVAILABLE with the reason, and the
    # UI prints an em dash plus that reason. Nothing here is a placeholder.
    doc["values"] = {
        # -- step 2 · shadow & PSR --------------------------------------------
        # All three withheld. The proxy's 77 % is a property of the expression,
        # not of the Moon, and must not be carried forward as a shadow fraction.
        "psr_area_km2": (
            val(round(ILLUM["psr_km2"], 3), "km²", MEASURED, note=(
                f"Terrain lit in NO sun state, over all {ILLUM['meta']['azimuths']} azimuths "
                f"and the whole subsolar band. {ILLUM['note']}"))
            if ILLUM["available"] else val(None, "km²", UNAVAILABLE, reason=PSR_ABSENT_REASON)),

        "psr_fraction_of_frame": (
            val(round(ILLUM["psr_fraction_of_frame"], 6), "", MEASURED, note=ILLUM["note"])
            if ILLUM["available"] else val(None, "", UNAVAILABLE, reason=PSR_ABSENT_REASON)),

        "doubly_shadowed_area_km2": (
            val(round(float(ILLUM["doubly"].sum()) * cell_km2, 3), "km²", DERIVED, note=(
                (ILLUM["meta"].get("doubly_shadowed") or {}).get("definition", "") + " — " +
                (ILLUM["meta"].get("doubly_shadowed") or {}).get("approximation", "")))
            if (ILLUM["available"] and ILLUM["doubly"] is not None)
            else val(None, "km²", UNAVAILABLE, reason=(
                (ILLUM["meta"].get("doubly_shadowed") or {}).get("reason", DOUBLY_ABSENT_REASON)
                if ILLUM["available"] else DOUBLY_ABSENT_REASON))),

        "mean_illumination_fraction": (
            val(round(ILLUM["mean_fraction"], 6), "", MEASURED, note=(
                "The fraction of SAMPLED SUN STATES in which a point is lit, averaged over the "
                "frame — a geometric visibility fraction, not a time-weighted duty cycle. "
                + ILLUM["note"]))
            if ILLUM["available"] else val(None, "", UNAVAILABLE, reason=(
                "There is no illumination fraction in this build. " + ILLUM["note"]))),

        "thermal_stability_k": (
            val(110.0, "K", DERIVED, note=(
                f"INFERRED FROM ILLUMINATION, NOT FROM MEASURED TEMPERATURE. No thermal product is "
                f"on disk and no thermal model runs here. A surface lit in none of the sampled sun "
                f"states has no direct solar input, and the water-ice stability limit over "
                f"geological time is about 110 K; the {ILLUM['psr_km2']:,.1f} km² of PSR in this "
                f"frame is therefore inferred to sit below it. The 110 K figure is an assumed "
                f"threshold from the literature, not something measured here. If a Diviner product "
                f"is ever ingested this becomes MEASURED and nothing else changes."))
            if ILLUM["available"] else val(None, "K", UNAVAILABLE, reason=(
                "No thermal product is on disk, and with no illumination computation there is not "
                "even an inference to make. " + ILLUM["note"]))),

        # -- step 3 · DFSAR radar, masked native statistics ---------------------
        "cpr_mean": val(round(cpr_s["mean"], 6), "", MEASURED,
                        note=f"Mean over the {cpr_s['n']:,} pixels carrying amplitude. The request path "
                             f"reports {cpr_n['mean']:.6f} by averaging across the never-observed void."),
        "cpr_p50": val(round(cpr_s["p50"], 6), "", MEASURED, note=MASK_NOTE),
        "cpr_p90": val(round(cpr_s["p90"], 6), "", MEASURED, note=MASK_NOTE),
        "cpr_p99": val(round(cpr_s["p99"], 6), "", MEASURED, note=MASK_NOTE),
        "cpr_max": val(round(cpr_s["max"], 6), "", MEASURED, note=MASK_NOTE),
        "cpr_std": val(round(cpr_s["std"], 6), "", MEASURED, note=MASK_NOTE),
        "dop_mean": val(round(dop_s["mean"], 6), "", MEASURED,
                        note=f"Mean over the amplitude mask. The request path reports {dop_n['mean']:.6f}."),
        "dop_min": val(round(dop_s["min"], 6), "", MEASURED,
                       note="Minimum over measured pixels only; the request path's 0.0 is padding."),
        "dop_p50": val(round(dop_s["p50"], 6), "", MEASURED, note=MASK_NOTE),
        "dop_p90": val(round(dop_s["p90"], 6), "", MEASURED, note=MASK_NOTE),
        "dop_p99": val(round(dop_s["p99"], 6), "", MEASURED, note=MASK_NOTE),
        "dop_max": val(round(dop_s["max"], 6), "", MEASURED, note=MASK_NOTE),
        "measured_area_km2": val(round(valid_n * cell_km2, 2), "km²", MEASURED,
                                 note="Amplitude mask area: where DFSAR actually returned signal. Every "
                                      "MEASURED radar statistic on this page is taken over this and "
                                      "nothing else."),
        "pointed_area_km2": val(round(int(footprint.sum()) * cell_km2, 2), "km²", MEASURED,
                                note="ISRO sri_ma > 0: where the beam was pointed. The difference from "
                                     "the measured area is swath that was pointed at and returned "
                                     "literal zero."),

        # -- step 4 · ice criteria screen (not a probability) ------------------
        "cpr_pass_fraction": val(round(cpr_pass_frac, 8), "", MEASURED,
                                 note=f"Fraction of the measured swath with CPR > {cpr_th:g}."),
        "dop_pass_fraction": val(round(dop_pass_frac, 8), "", MEASURED,
                                 note=f"Fraction of the measured swath with DOP < {dop_th:g}."),
        "screening_pass_fraction": val(round(screen_frac, 8), "", MEASURED,
                                       note="Fraction of the MEASURED SWATH passing both criteria — not "
                                            "of the frame. The frame is 84 % never-observed padding and "
                                            "a fraction over it would be meaningless."),
        "candidate_area_km2": val(round(cand_km2, 4), "km²", MEASURED,
                                  note="Pixel count passing both criteria, times the frame's own cell "
                                       "area. A measured zero here is a result, not a gap."),
        "criteria_passed": val(passed_n, "", MEASURED,
                               note=f"Of {len(evidence)} named criteria: "
                                    + ", ".join(f"{e['label']} = "
                                                + ("PASS" if e["passed"] else
                                                   "WITHHELD" if e["provenance"] == UNAVAILABLE else "FAIL")
                                                for e in evidence)),
        "p_ice_max": val(None, "", UNAVAILABLE, reason=P_ICE_ABSENT_REASON),
        "p_ice_mean": val(None, "", UNAVAILABLE, reason=P_ICE_ABSENT_REASON),

        # -- step 5 · terrain, all from measured LOLA --------------------------
        "mean_slope_deg": val(round(float(t["slope_deg"].mean()), 4), "°", MEASURED, note=SLOPE_NOTE),
        "slope_p50_deg": val(round(float(np.percentile(t["slope_deg"], 50)), 4), "°", MEASURED, note=SLOPE_NOTE),
        "slope_p90_deg": val(round(float(np.percentile(t["slope_deg"], 90)), 4), "°", MEASURED, note=SLOPE_NOTE),
        "slope_p99_deg": val(round(float(np.percentile(t["slope_deg"], 99)), 4), "°", MEASURED, note=SLOPE_NOTE),
        "max_slope_deg": val(round(float(t["slope_deg"].max()), 4), "°", MEASURED, note=SLOPE_NOTE),
        "slope_fraction_below_20deg": val(round(float((t["slope_deg"] <= cfg.MAX_TRAVERSABLE_SLOPE_DEG).mean()), 6),
                                   "", MEASURED,
                                   note=f"Fraction of the frame at or below MAX_TRAVERSABLE_SLOPE_DEG = "
                                        f"{cfg.MAX_TRAVERSABLE_SLOPE_DEG:g}°, read from config.py. " + SLOPE_NOTE),
        "slope_fraction_below_12deg": val(round(float((t["slope_deg"] <= cfg.CRITICAL_LANDING_SLOPE_DEG).mean()), 6),
                                       "", MEASURED,
                                       note=f"Fraction at or below CRITICAL_LANDING_SLOPE_DEG = "
                                            f"{cfg.CRITICAL_LANDING_SLOPE_DEG:g}°. " + SLOPE_NOTE),
        "mean_roughness_m": val(round(float(t["roughness"].mean()), 4), "m", MEASURED, note=SLOPE_NOTE),
        "roughness_p50_m": val(round(float(np.percentile(t["roughness"], 50)), 4), "m", MEASURED, note=SLOPE_NOTE),
        "roughness_p90_m": val(round(float(np.percentile(t["roughness"], 90)), 4), "m", MEASURED, note=SLOPE_NOTE),
        "roughness_p99_m": val(round(float(np.percentile(t["roughness"], 99)), 4), "m", MEASURED, note=SLOPE_NOTE),
        "mean_hazard": val(round(float(haz.mean()), 6), "", MEASURED, note=hazard_model["note"]),
        "hazard_p50": val(round(float(np.percentile(haz, 50)), 6), "", MEASURED, note=hazard_model["note"]),
        "hazard_p90": val(round(float(np.percentile(haz, 90)), 6), "", MEASURED, note=hazard_model["note"]),
        "hazard_p99": val(round(float(np.percentile(haz, 99)), 6), "", MEASURED, note=hazard_model["note"]),
        "critical_hazard_fraction": val(round(float((haz > 0.70).mean()), 6), "", MEASURED,
                                        note="Fraction of the frame above a 0.70 composite hazard. The "
                                             "0.70 cut is a display convention stated here, not a "
                                             "measured property; the hazard field under it is measured."),
        "boulder_risk": val(None, "", UNAVAILABLE, reason=hazard_model["boulder"]["reason"]),
        "min_elevation_m": val(round(float(dem.min()), 2), "m", MEASURED, note=DEM_NOTE),
        "max_elevation_m": val(round(float(dem.max()), 2), "m", MEASURED, note=DEM_NOTE),

        # -- step 6 · landing sites (Phase 3) -----------------------------------
        "landing_site": val(None, "", UNAVAILABLE, reason=LANDING_ABSENT_REASON),
        "landing_site_score": val(None, "", UNAVAILABLE, reason=LANDING_ABSENT_REASON),
        "landing_sites_evaluated": val(None, "", UNAVAILABLE, reason=LANDING_ABSENT_REASON),

        # -- step 7 · rover traverse (Phase 4) ----------------------------------
        "rover_traverse_km": val(None, "km", UNAVAILABLE, reason=ROVER_ABSENT_REASON),
        "rover_energy_wh": val(None, "Wh", UNAVAILABLE, reason=ROVER_ABSENT_REASON),
        "rover_mean_hazard": val(None, "", UNAVAILABLE, reason=ROVER_ABSENT_REASON),

        # -- step 8 · volume, DERIVED, assumptions carried in volume_tiers ------
        "conservative_volume_m3": val(round(v_cons, 0), "m³", DERIVED, note=volume_tiers[0]["note"]),
        "expected_volume_m3": val(round(v_exp, 0), "m³", DERIVED, note=volume_tiers[1]["note"]),
        "upper_volume_m3": val(round(v_up, 0), "m³", DERIVED, note=volume_tiers[2]["note"]),

        # -- step 10 · ablation (Phase 4) ---------------------------------------
        "ablation_runs": val(None, "", UNAVAILABLE, reason=(
            "A real ablation reruns the planner with each hazard weight zeroed in turn and reports the "
            "measured deltas in distance, mean hazard and max slope. It needs the Phase 4 planner. The "
            "previous experiments_runner.py returned four hand-written experiments with no computation "
            "behind them, three of them stamped is_synthetic_evaluation=False; it was deleted in "
            "Phase 0.")),
    }
    # ------------------------------------------------- the CPR/DOP identity
    # Emitted as DATA, not prose, so emit_provenance.py can assert on it and so
    # the UI can state the reason the screen is empty rather than just showing a
    # zero. See docs/METHODS.md for the derivation.
    #
    # This build forms both quantities from the same two smoothed amplitudes:
    #     cpr = ((sqrt(lh) - sqrt(lv)) / (sqrt(lh) + sqrt(lv)))^2 = tanh^2(x/4)
    #     dop = |lh - lv| / (lh + lv)                             = |tanh(x/2)|
    # with x = ln(lh/lv). They are two reparameterisations of ONE channel ratio,
    # so cpr is a strictly increasing function of dop and the conjunction
    # "cpr > a AND dop < b" is empty for every a above the ceiling below.
    ceiling = float(np.tanh(2.0 * np.arctanh(dop_th) / 4.0) ** 2) if dop_th < 1.0 else 1.0
    with np.errstate(divide="ignore", invalid="ignore"):
        d_ok = dop[valid].astype(np.float64)
        m = d_ok < 1.0
        predicted = np.tanh(np.arctanh(np.clip(d_ok[m], 0.0, 1.0 - 1e-12)) / 2.0) ** 2
        residual = predicted - cpr[valid].astype(np.float64)[m]
    identity = {
        "applies_when": "cpr_source == 'amplitude-only'",
        "cpr_source": "amplitude-only",
        "cpr_expression": "((sqrt(lh) - sqrt(lv)) / (sqrt(lh) + sqrt(lv)))**2",
        "dop_expression": "|lh - lv| / (lh + lv)",
        "single_variable": "x = ln(lh / lv)",
        "cpr_of_x": "tanh(x/4)**2",
        "dop_of_x": "|tanh(x/2)|",
        "cpr_from_dop": "tanh(artanh(dop) / 2)**2",
        "degrees_of_freedom": 1,
        "dop_threshold": dop_th,
        "implied_cpr_ceiling": ceiling,
        "verified_over_pixels": int(m.sum()),
        "max_abs_residual": float(np.abs(residual).max()),
        "rms_residual": float(np.sqrt((residual ** 2).mean())),
        "pearson_r": float(np.corrcoef(predicted, cpr[valid].astype(np.float64)[m])[0, 1]),
        "max_cpr_where_dop_passes": float(cpr[valid][dop[valid] < dop_th].max())
        if int((dop[valid] < dop_th).sum()) else None,
        "screen_is_empty_by_construction": bool(cpr_th > ceiling),
        "threshold_over_ceiling_ratio": float(cpr_th / ceiling) if ceiling > 0 else None,
        "consequence": (
            f"No pixel with DOP < {dop_th:g} can exhibit CPR > {ceiling:.7f}, whatever the terrain "
            f"and whatever the instrument. The configured CPR_THRESHOLD of {cpr_th:g} is "
            f"{cpr_th / ceiling:.0f}x above that ceiling, so this screen is LOGICALLY EMPTY, not "
            "merely unsatisfied. A candidate area of exactly 0.0 is the only arithmetically "
            "possible answer, and a non-zero value here would be a bug rather than a detection."
        ),
        "what_fixes_it": (
            "The true Stokes forms are built from DIFFERENT combinations of the four Stokes "
            "parameters -- CPR = (S0 - S3)/(S0 + S3) and DOP = sqrt(S1^2 + S2^2 + S3^2)/S0 -- so "
            "they are genuinely independent and their conjunction selects a real population. The "
            "amplitude proxy's defect is not that it is small: it collapses two independent "
            "physical observables onto one degree of freedom. Phase 5b."
        ),
    }
    doc["cpr_dop_identity"] = identity

    hr("CPR/DOP IDENTITY -- the screen is empty by construction, not by measurement")
    print(f"  cpr = tanh^2(x/4), dop = |tanh(x/2)|, x = ln(lh/lv)  ->  ONE degree of freedom")
    print(f"  cpr = tanh^2(artanh(dop)/2)  verified over {identity['verified_over_pixels']:,} px:")
    print(f"      max|residual| {identity['max_abs_residual']:.3e}   "
          f"rms {identity['rms_residual']:.3e}   pearson r {identity['pearson_r']:.12f}")
    print(f"  DOP < {dop_th:g}  =>  CPR < {ceiling:.7f}"
          f"   (observed max where DOP passes: {identity['max_cpr_where_dop_passes']:.7f})")
    print(f"  CPR_THRESHOLD {cpr_th:g} is {cpr_th / ceiling:.0f}x the ceiling"
          f"  ->  screen empty by construction: {identity['screen_is_empty_by_construction']}")

    doc["evidence"] = evidence
    doc["volume_tiers"] = volume_tiers
    doc["sensitivity"] = sensitivity

    # What each of the twelve steps can honestly show today. The UI reads this
    # to decide whether a step renders figures or renders its own absence; it is
    # not allowed to infer that from whether a value happens to be null.
    doc["steps"] = [
        {"n": 1, "key": "site", "title": "Target Selection", "status": "COMPLETE",
         "basis": "Crater catalogue plus the frame's own georeferencing."},
        ({"n": 2, "key": "psr", "title": "Shadow & PSR", "status": "COMPLETE",
          "basis": ILLUM["note"]}
         if ILLUM["available"] else
         {"n": 2, "key": "psr", "title": "Shadow & PSR", "status": "UNAVAILABLE",
          "basis": PSR_ABSENT_REASON}),
        {"n": 3, "key": "radar", "title": "DFSAR Radar", "status": "COMPLETE",
         "basis": "Masked native statistics from the calibrated L2 amplitude products."},
        {"n": 4, "key": "ice", "title": "Ice Criteria Screen", "status": "COMPLETE",
         "basis": ("Five named criteria. Two are measured and evaluated; three are withheld "
                   "(two shadow terms, one thermal) and say so.")},
        {"n": 5, "key": "terrain", "title": "Terrain Hazards", "status": "COMPLETE",
         "basis": "Slope, roughness and hazard from measured LOLA topography."},
        {"n": 6, "key": "landing", "title": "Landing Sites", "status": "UNAVAILABLE",
         "basis": LANDING_ABSENT_REASON},
        {"n": 7, "key": "rover", "title": "Rover Traverse", "status": "UNAVAILABLE",
         "basis": ROVER_ABSENT_REASON},
        {"n": 8, "key": "volume", "title": "Volume Estimate", "status": "COMPLETE",
         "basis": "Three DERIVED tiers over the measured candidate area, each carrying its own "
                  "assumed depth and pore fraction as data."},
        {"n": 9, "key": "sweep", "title": "Sensitivity Studio", "status": "COMPLETE",
         "basis": "Real sweeps computed by re-thresholding the native arrays."},
        {"n": 10, "key": "research", "title": "Ablation", "status": "UNAVAILABLE",
         "basis": ("A real ablation needs the Phase 4 planner to rerun with each hazard weight "
                   "zeroed. The previous four hand-written experiments were deleted in Phase 0.")},
        {"n": 11, "key": "defense", "title": "Viva Rationale", "status": "COMPLETE",
         "basis": "Reads the evidence rows and the provenance legend in this file."},
        {"n": 12, "key": "provenance", "title": "Provenance", "status": "COMPLETE",
         "basis": "Source rasters, masks, thresholds and the generator that produced this file."},
    ]
    doc["measured_statistics"] = {
        "cpr": {"masked": cpr_s, "naive_frame": cpr_n},
        "dop": {"masked": dop_s, "naive_frame": dop_n},
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
        "illumination": ({
            "psr_px": ILLUM["psr_px"],
            "psr_area_km2": ILLUM["psr_km2"],
            "psr_fraction_of_frame": ILLUM["psr_fraction_of_frame"],
            "illumination_fraction": {
                "mean": ILLUM["mean_fraction"],
                "p25": float(np.nanpercentile(ILLUM["fraction"], 25)),
                "p50": float(np.nanpercentile(ILLUM["fraction"], 50)),
                "p75": float(np.nanpercentile(ILLUM["fraction"], 75)),
                "p99": float(np.nanpercentile(ILLUM["fraction"], 99)),
                "max": float(np.nanmax(ILLUM["fraction"])),
            },
            "sky_view_factor": {
                "p50": float(np.nanpercentile(ILLUM["svf"], 50)),
                "min": float(np.nanmin(ILLUM["svf"])),
            },
            "doubly_shadowed_px": (int(ILLUM["doubly"].sum())
                                   if ILLUM["doubly"] is not None else None),
            "pixels_without_horizon_coverage": ILLUM["n_nan"],
            "effective_metres_per_pixel": ILLUM["effective_m"],
        } if ILLUM["available"] else {"available": False, "reason": ILLUM["note"]}),
        "screening": {
            "measured_px": valid_n,
            "cpr_pass_px": int(cpr_pass.sum()), "cpr_pass_fraction_of_measured": cpr_pass_frac,
            "dop_pass_px": int(dop_pass.sum()), "dop_pass_fraction_of_measured": dop_pass_frac,
            "candidate_px": cand_n, "candidate_area_km2": cand_km2,
            "screening_pass_fraction_of_measured": screen_frac,
            "mask_definition": "(cpr > CPR_THRESHOLD) & (dop < DOP_THRESHOLD) & amplitude_mask",
            "shadow_term_removed": ("v1.0 also intersected the illumination proxy's shadow mask. Removed: "
                                    "it darkens 77 % of the frame, so it discriminated nothing while "
                                    "making a MEASURED-marked area partly modelled."),
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
        "P(ice) is WITHDRAWN, not downgraded. Its Random Forest was fitted to np.random.uniform labels "
        "whose ice class (CPR 1.05-2.5) lies entirely outside this product's achievable range, so every "
        "prediction was an extrapolation from fabricated examples. Step 4 reports the measured criteria "
        "screen instead.",
        "The candidate mask is (CPR > threshold) AND (DOP < threshold) AND amplitude mask. The "
        "illumination proxy's shadow was removed from it: darkening 77 % of the frame discriminates "
        "nothing, and its presence made a MEASURED-marked area partly modelled.",
        "The sensitivity sweeps are computed by re-thresholding the native arrays, not by scaling a "
        "baseline. Every area column is a pixel count; every volume column is that area times a stated "
        "depth and pore fraction.",
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
    for k in ("cpr_mean", "cpr_max", "dop_mean", "dop_p50", "measured_area_km2",
              "screening_pass_fraction", "candidate_area_km2", "criteria_passed",
              "mean_slope_deg", "max_slope_deg", "mean_hazard", "expected_volume_m3",
              "psr_area_km2", "mean_illumination_fraction", "p_ice_max",
              "landing_site", "rover_traverse_km", "ablation_runs"):
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

