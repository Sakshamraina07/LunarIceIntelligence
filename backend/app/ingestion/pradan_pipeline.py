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
from app.demo.lunar_generator import demo_generator
from app.modules.module_d_terrain import compute_terrain_metrics, compute_hazard_score


PRADAN_DATA_DIR = Path("d:/FYP/data/pradan")


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


def simulate_grazing_illumination(
    dem: np.ndarray,
    pixel_scale_m: float = 250.0,
    sun_altitude_deg: float = 1.5
) -> np.ndarray:
    """Computes grazing solar illumination based on Horn gradient and elevation."""
    hill = compute_hillshade(dem, pixel_scale_m=pixel_scale_m, altitude_deg=sun_altitude_deg)
    elev_norm = (dem - np.min(dem)) / (np.ptp(dem) + 1e-6)
    return np.clip(hill * (elev_norm ** 1.3), 0.0, 1.0).astype(np.float32)


def process_real_dem(
    dem_path: str,
    pixel_scale_m: float = 250.0,
    target_shape: Tuple[int, int] = (100, 100)
) -> Dict[str, np.ndarray]:
    """
    Processes real LOLA / TMC-2 DEM:
    Computes georeferenced elevation, Horn hillshade, slope, aspect, and roughness.
    """
    dem_raw = read_raster_file(dem_path)
    if dem_raw.shape != target_shape:
        dem = cv2.resize(dem_raw, (target_shape[1], target_shape[0]), interpolation=cv2.INTER_LINEAR)
    else:
        dem = dem_raw.copy()

    hillshade = compute_hillshade(dem, pixel_scale_m=pixel_scale_m)
    illumination = simulate_grazing_illumination(dem, pixel_scale_m=pixel_scale_m, sun_altitude_deg=1.5)
    psr_mask = (illumination < 0.05)
    doubly_shadowed = psr_mask & (dem < np.percentile(dem, 20))
    slope_deg, aspect_deg, roughness = compute_terrain_metrics(dem, pixel_scale_m=pixel_scale_m)

    return {
        "dem": dem,
        "hillshade": hillshade,
        "psr_mask": psr_mask,
        "doubly_shadowed": doubly_shadowed,
        "illumination": illumination,
        "slope_deg": slope_deg,
        "aspect_deg": aspect_deg,
        "roughness": roughness
    }


def create_sample_georeferenced_pradan_data(crater_id: str = "shackleton") -> Dict[str, str]:
    """
    Generates standardized, georeferenced Chandrayaan-2 sample GeoTIFF/TIFF files
    in d:/FYP/data/pradan/ so the ingestion pipeline can be demonstrated with real disk files.
    """
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

    # Save OHRC Imagery
    ohrc_file = PRADAN_DATA_DIR / "ohrc" / f"{crater_id}_ohrc_pan.tif"
    hill = compute_hillshade(env["dem"])
    ohrc_img = (hill * 255.0).astype(np.uint8)
    cv2.imwrite(str(ohrc_file), ohrc_img)

    return {
        "dem": str(dem_file),
        "s0": str(s0_file),
        "s3": str(s3_file),
        "ohrc": str(ohrc_file)
    }
