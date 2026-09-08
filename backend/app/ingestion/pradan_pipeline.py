"""
CHANDRAYAAN-2 PRADAN DATA INGESTION PIPELINE
Supports ISRO PRADAN PDS4 / GeoTIFF products:
1. DFSAR Polarimetric Stokes parameters (S0, S1, S2, S3)
2. OHRC High-Resolution Panchromatic Imagery (Boulder & micro-hazard detection)
3. LOLA / TMC-2 Digital Elevation Models (DEM) with analytical georeferencing
"""

import os
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from PIL import Image

from app.core.config import settings
from app.modules.module_b_radar import compute_cpr_from_stokes, compute_dop_from_stokes, classify_radar_polarimetry
from app.modules.module_a_psr import compute_hillshade
from scipy.ndimage import maximum_filter

from app.modules.module_d_terrain import compute_terrain_metrics, compute_hazard_score


# Repository root, derived from this file's own location rather than a
# hardcoded drive letter. backend/app/ingestion/ -> parents[3] is the root.
# A Windows absolute here is why every crater reported NOT_INGESTED on the
# Linux deploy host: the path could not resolve, so no raster was ever found.
BASE_DIR = Path(__file__).resolve().parents[3]
PRADAN_DATA_DIR = BASE_DIR / "data" / "pradan"


def ensure_pradan_directories():
    """Ensures input directories exist for PRADAN data ingestion."""
    dirs = [
        PRADAN_DATA_DIR / "dfsar",
        PRADAN_DATA_DIR / "ohrc",
        PRADAN_DATA_DIR / "dem"
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    return dirs


def read_raster_file(file_path: str) -> np.ndarray:
    """
    Reads an image or GeoTIFF file as float32 numpy array.
    Supports GeoTIFF, TIFF, PNG, and NPY.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PRADAN raster file not found: {file_path}")

    if path.suffix.lower() == ".npy":
        arr = np.load(path).astype(np.float32)
    elif path.suffix.lower() in [".tif", ".tiff", ".geotiff"]:
        try:
            import tifffile
            arr = tifffile.imread(path).astype(np.float32)
        except Exception:
            img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
            if img is None:
                pil_img = Image.open(path)
                arr = np.array(pil_img, dtype=np.float32)
            else:
                arr = img.astype(np.float32)
    else:
        # Standard image (PNG/JPG)
        img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise ValueError(f"Unable to decode raster image: {file_path}")
        arr = img.astype(np.float32)

    return arr


def process_real_dfsar_stokes(
    s0_path: str,
    s1_path: Optional[str] = None,
    s2_path: Optional[str] = None,
    s3_path: Optional[str] = None,
    eps: float = 1e-6
) -> Dict[str, np.ndarray]:
    """
    Ingests Chandrayaan-2 DFSAR Stokes parameters and computes CPR and DOP:
    - S0: Total intensity
    - S1: Linear horizontal vs vertical power (Q)
    - S2: Linear +45° vs -45° power (U)
    - S3: Circular right vs left power (V)

    Formulas:
    sigma_oc = 0.5 * (S0 + S3)
    sigma_sc = 0.5 * (S0 - S3)
    CPR = (S0 - S3) / (S0 + S3)
    DOP = sqrt(S1^2 + S2^2 + S3^2) / S0
    """
    s0 = read_raster_file(s0_path)

    # If single multi-channel file provided
    if s0.ndim == 3 and s0.shape[2] >= 4:
        s3 = s0[:, :, 3]
        s2 = s0[:, :, 2]
        s1 = s0[:, :, 1]
        s0 = s0[:, :, 0]
    else:
        s1 = read_raster_file(s1_path) if s1_path else np.zeros_like(s0)
        s2 = read_raster_file(s2_path) if s2_path else np.zeros_like(s0)
        s3 = read_raster_file(s3_path) if s3_path else np.zeros_like(s0)

    # Ensure equal dimensions
    target_shape = s0.shape
    if s1.shape != target_shape:
        s1 = cv2.resize(s1, (target_shape[1], target_shape[0]))
    if s2.shape != target_shape:
        s2 = cv2.resize(s2, (target_shape[1], target_shape[0]))
    if s3.shape != target_shape:
        s3 = cv2.resize(s3, (target_shape[1], target_shape[0]))

    # Physical computations
    cpr = compute_cpr_from_stokes(s0, s3, eps=eps)
    dop = compute_dop_from_stokes(s0, s1, s2, s3, eps=eps)
    sigma_oc = np.maximum(0.5 * (s0 + s3), 0.0)
    sigma_sc = np.maximum(0.5 * (s0 - s3), 0.0)

    return {
        "s0": s0,
        "s1": s1,
        "s2": s2,
        "s3": s3,
        "cpr": cpr,
        "dop": dop,
        "sigma_oc": sigma_oc,
        "sigma_sc": sigma_sc
    }


def extract_boulders_from_ohrc(
    ohrc_path: str,
    target_shape: Tuple[int, int] = (100, 100)
) -> np.ndarray:
    """
    Extracts boulder / micro-hazard distribution from high-resolution OHRC imagery.
    Applies gradient magnitude and morphological top-hat filtering to isolate elevated blocks.
    """
    raw_img = read_raster_file(ohrc_path)
    # Normalize to 0-255 uint8
    norm_img = ((raw_img - np.min(raw_img)) / (np.ptp(raw_img) + 1e-6) * 255.0).astype(np.uint8)

    # Morphological Top-Hat filter to extract small high-contrast boulders
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    top_hat = cv2.morphologyEx(norm_img, cv2.MORPH_TOPHAT, kernel)

    # Edge gradient (Canny edge detection)
    edges = cv2.Canny(norm_img, 50, 150)
    combined_hazard = np.maximum(top_hat.astype(np.float32) / 255.0, edges.astype(np.float32) / 255.0)

    # Downsample / aggregate to target mission grid scale (e.g. 100x100 cells)
    hazard_grid = cv2.resize(combined_hazard, (target_shape[1], target_shape[0]), interpolation=cv2.INTER_AREA)
    return np.clip(hazard_grid, 0.0, 1.0).astype(np.float32)


# simulate_grazing_illumination() WAS HERE, AND sun_altitude_deg WITH IT.
#
# It computed a hillshade at a capped 1.5 deg solar altitude and called the dark
# pixels permanent shadow. METHODS 5.3 measures that model wrong by up to 4.4x --
# solar elevation at latitude phi reaches 1.54 + (90 - |phi|), which is 6.71 deg
# at this frame's outer edge, so treating it as a constant under-illuminates the
# frame. METHODS 5.1 deleted both brightness proxies from every other path when
# the horizon computation replaced them; this one survived only because it sat
# behind an API nobody was reading.
#
# It is DELETED, not adapted. mission_service now reads the horizon product --
# the same one build_analysis reads for the verdict and the report renders --
# through the same load_horizon().to_frame() call, or refuses with
# HorizonPSRUnavailable. One PSR source, read and not recomputed.
#
# sun_altitude_deg is deleted with it and is deliberately NOT recorded in
# assumptions.md: with no consumer it is not an assumption, and declaring it
# would assert the capped-elevation model METHODS 5.3 spends a section refuting.

#: The DFSAR frame's own post spacing, for callers that want the default.
#: NOTHING assumes the file on disk is at this spacing -- see process_real_dem's
#: source_spacing_m, which is required precisely because assuming it was wrong:
#: data/pradan/dem/*_lola_dem.tif is a 2048^2 raster at 27.56 x 80.79 m, and
#: scoring it as though it were 25 m overstated every API slope by ~2x.
NATIVE_POST_M = 25.0


def process_real_dem(
    dem_path: str,
    spacing_m: Tuple[float, float],
    target_shape: Tuple[int, int] = (100, 100),
    source_spacing_m: Optional[Tuple[float, float]] = None,
) -> Dict[str, np.ndarray]:
    """
    Processes real LOLA / TMC-2 DEM:
    Computes georeferenced elevation, Horn hillshade, slope, aspect, and roughness.

    `spacing_m` is (metres_per_line, metres_per_sample) of the OUTPUT grid — the
    resampled `target_shape` grid, not the file on disk. The caller knows the
    frame extent and the target shape, so the caller derives it; the returned
    dict echoes it back under "spacing_m" so downstream code cannot re-guess.
    """
    dem_raw = read_raster_file(dem_path)

    # ---- SCORE NATIVELY, THEN AREA-AVERAGE DOWN ---------------------------
    # THE SATURATION PROBLEM, AND WHY THIS ORDER MATTERS.
    #
    # This function used to resize the DEM to target_shape FIRST and derive
    # slope, roughness and hazard on that grid. For the 2048^2 serving grid the
    # sample spacing is 80.79 m, so the 5x5 roughness window spans ~404 m: it
    # measures REGIONAL RELIEF, a different physical quantity wearing the same
    # name. clip(roughness / 50) then pins to 1.0 and slope stops contributing
    # to hazard at all. Measured on the current frame:
    #
    #     resize-then-score   hazard p50 0.393  p90 0.843  p99 1.000   2.4143 % pinned
    #     score-then-average  hazard p50 0.344  p90 0.709  p99 0.788   0.0000 % pinned
    #     native reference    hazard p50 0.344  p90 0.721  p99 0.788   0.0002 % pinned
    #
    # Hazard is a BOUNDED 0-1 score, so averaging it down is meaningful in a way
    # that averaging a DEM and re-differencing it is not. Score at 25 m, then
    # area-average the bounded field onto whatever grid is being served.
    #
    # slope_max_deg is carried BESIDE hazard_mean because an average hides the
    # thing a lander cares about: a cell that averages safe can still hold a
    # single impassable face.
    # The spacing of the FILE, which is not necessarily 25 m and must not be
    # guessed. When the caller does not say, fall back to the DFSAR post
    # spacing and record what was used so a reader can tell.
    native_spacing = tuple(source_spacing_m) if source_spacing_m else (NATIVE_POST_M,
                                                                      NATIVE_POST_M)
    slope_n, aspect_n, rough_n = compute_terrain_metrics(dem_raw, native_spacing)
    hazard_n = compute_hazard_score(slope_n, rough_n,
                                    np.zeros_like(dem_raw, dtype=np.float32))

    if dem_raw.shape != target_shape:
        th, tw = target_shape
        dem = cv2.resize(dem_raw, (tw, th), interpolation=cv2.INTER_LINEAR)
        # INTER_AREA is the area average; INTER_LINEAR would point-sample and
        # reintroduce exactly the aliasing this ordering exists to avoid.
        hazard = cv2.resize(hazard_n, (tw, th), interpolation=cv2.INTER_AREA)
        slope_deg = cv2.resize(slope_n, (tw, th), interpolation=cv2.INTER_AREA)
        roughness = cv2.resize(rough_n, (tw, th), interpolation=cv2.INTER_AREA)
        aspect_deg = cv2.resize(aspect_n, (tw, th), interpolation=cv2.INTER_NEAREST)
        # Block MAX, not a mean: a maximum filter sized to the serving cell,
        # then nearest-sampled so the value is a real cell maximum rather than
        # an interpolation between two of them.
        by = max(1, int(np.ceil(dem_raw.shape[0] / float(th))))
        bx = max(1, int(np.ceil(dem_raw.shape[1] / float(tw))))
        slope_max = cv2.resize(maximum_filter(slope_n, size=(by, bx)),
                               (tw, th), interpolation=cv2.INTER_NEAREST)
    else:
        dem = dem_raw.copy()
        hazard, slope_deg, roughness = hazard_n, slope_n, rough_n
        aspect_deg, slope_max = aspect_n, slope_n

    hillshade = compute_hillshade(dem, spacing_m)
    # NO ILLUMINATION, NO PSR MASK, NO DOUBLY-SHADOWED TERM FROM HERE.
    # This function reads a DEM and derives terrain. Shadow is a horizon
    # computation over the full LOLA polar array and is read from that product by
    # mission_service; deriving it here as well would be the second
    # implementation that METHODS 0's third pattern is about.

    return {
        "dem": dem,
        "hillshade": hillshade,
        "slope_deg": slope_deg,
        "aspect_deg": aspect_deg,
        "roughness": roughness,
        "hazard": hazard,
        "slope_max_deg": slope_max,
        "spacing_m": spacing_m,
        # Every terrain field above was computed at NATIVE_POST_M and averaged
        # onto this grid. A consumer that reports them as though they were
        # measured at `spacing_m` is overstating the resolution.
        "terrain_scored_at_m": list(native_spacing),
        "terrain_source_shape": list(dem_raw.shape),
        "terrain_order": "scored natively, then area-averaged to the serving grid",
    }


def create_sample_georeferenced_pradan_data(crater_id: str = "shackleton") -> Dict[str, Optional[str]]:
    """
    Writes seeded rasters into data/pradan/ under the same names a real
    ingested product would use. PYTEST / LOCAL DEVELOPMENT ONLY.

    This function is how the ambiguity got onto disk. It names its output
    `{crater_id}_lola_dem.tif`, indistinguishable by filename from an ingested
    LOLA crop, and `shoemaker_lola_dem.tif` (40,176 bytes) is its work. The old
    eligibility test was `Path(f".../{crater_id}_lola_dem.tif").exists()`, so
    every file this wrote promoted a crater to REAL.

    The gate no longer reads the filesystem for provenance
    (app/ingestion/real_data_gate.real_data_status), so these files can no longer
    promote anything. It is still gated: a served host has no business
    manufacturing files that look like products.
    """
    from app.demo.lunar_generator import demo_generator, demo_generator_enabled

    if not demo_generator_enabled():
        raise RuntimeError(
            "Refusing to write sample rasters: this writes seeded data into the "
            "PRADAN data directory under real product filenames. It is a "
            "development fixture only (set LUNAR_ICE_ALLOW_DEMO_GENERATOR=1). "
            "Ingest an actual Chandrayaan-2 DFSAR product instead."
        )

    ensure_pradan_directories()
    env = demo_generator.generate_crater_environment(crater_id)

    # Save DEM GeoTIFF
    dem_file = PRADAN_DATA_DIR / "dem" / f"{crater_id}_lola_dem.tif"
    cv2.imwrite(str(dem_file), env["dem"].astype(np.float32))

    # Save DFSAR Stokes GeoTIFFs
    s0_file = PRADAN_DATA_DIR / "dfsar" / f"{crater_id}_dfsar_s0.tif"
    s3_file = PRADAN_DATA_DIR / "dfsar" / f"{crater_id}_dfsar_s3.tif"
    cpr = env["cpr"]
    # Reconstruct S0 and S3 from CPR: CPR = (S0 - S3)/(S0 + S3) => S3 = S0 * (1 - CPR) / (1 + CPR)
    s0 = np.ones_like(cpr, dtype=np.float32)
    s3 = s0 * (1.0 - cpr) / (1.0 + cpr + 1e-6)
    cv2.imwrite(str(s0_file), s0)
    cv2.imwrite(str(s3_file), s3)

    # NO OHRC PRODUCT IS WRITTEN.
    #
    # This used to write {crater_id}_ohrc_pan.tif as a hillshade of the DEM, then
    # mission_service.py read it back and ran boulder detection over it. That
    # closed a loop with no observation in it: every "boulder" was a shading
    # artefact of the elevation model that produced it, reported as if OHRC had
    # imaged a rock. A hillshade of a DEM is not an optical product.
    #
    # There is no OHRC data for this frame, so the honest output is nothing at
    # all. mission_service.py is .exists()-guarded and now reports boulder risk
    # as ABSENT rather than as zero — those are different facts.

    return {
        "dem": str(dem_file),
        "s0": str(s0_file),
        "s3": str(s3_file),
        "ohrc": None,
        "ohrc_absent_reason": (
            "No OHRC product exists for this frame. The previous build "
            "substituted a hillshade of the DEM here, which made boulder "
            "detection circular; it was removed rather than replaced."
        ),
    }
