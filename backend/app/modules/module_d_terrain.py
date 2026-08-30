"""
MODULE D: Terrain Safety & Hazard Assessment.
PRD Compliance: Computes slope, aspect, terrain roughness (TRI), and composite hazard score:
Hazard = w1 * slope_risk + w2 * roughness_risk + w3 * boulder_risk.
Normalized strictly to [0, 1] with fully configurable weights.
"""

import numpy as np
from typing import Dict, Any, Tuple, Optional
from app.core.config import settings
from app.core.schemas import TerrainAnalysisResult
from app.core.provenance import create_provenance


def compute_terrain_metrics(
    dem: np.ndarray,
    pixel_scale_m: float = 250.0
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Computes slope (degrees), aspect (degrees), and terrain roughness.
    """
    grad_y, grad_x = np.gradient(dem, pixel_scale_m)
    slope_rad = np.arctan(np.sqrt(grad_x**2 + grad_y**2))
    slope_deg = np.degrees(slope_rad).astype(np.float32)

    aspect_rad = np.arctan2(-grad_x, grad_y)
    aspect_deg = (np.degrees(aspect_rad) + 360.0) % 360.0

    from scipy.ndimage import uniform_filter
    mean_elev = uniform_filter(dem, size=5)
    mean_sq_elev = uniform_filter(dem**2, size=5)
    roughness = np.sqrt(np.maximum(0.0, mean_sq_elev - mean_elev**2)).astype(np.float32)

    return slope_deg, aspect_deg, roughness


def compute_hazard_score(
    slope_deg: np.ndarray,
    roughness: np.ndarray,
    boulder_risk: np.ndarray,
    w_slope: Optional[float] = None,
    w_roughness: Optional[float] = None,
    w_boulder: Optional[float] = None
) -> np.ndarray:
    """
    Calculates normalized terrain hazard score in range [0, 1].
    """
    w1 = w_slope if w_slope is not None else settings.WEIGHT_SLOPE
    w2 = w_roughness if w_roughness is not None else settings.WEIGHT_ROUGHNESS
    w3 = w_boulder if w_boulder is not None else settings.WEIGHT_BOULDER

    # Normalize individual components
    # Critical traversability limit for small lunar rover is ~20 degrees
    slope_risk = np.clip(slope_deg / settings.MAX_TRAVERSABLE_SLOPE_DEG, 0.0, 1.0)

    # Roughness risk: Normalized against maximum expected local height variance (e.g. 50m)
    roughness_risk = np.clip(roughness / 50.0, 0.0, 1.0)

    boulder_risk_norm = np.clip(boulder_risk, 0.0, 1.0)

    total_weight = w1 + w2 + w3
    hazard = (w1 * slope_risk + w2 * roughness_risk + w3 * boulder_risk_norm) / total_weight
    return np.clip(hazard, 0.0, 1.0).astype(np.float32)


def analyze_terrain_safety(
    crater_id: str,
    dem: np.ndarray,
    boulder_risk: np.ndarray,
    pixel_scale_m: float = 250.0,
    w_slope: Optional[float] = None,
    w_roughness: Optional[float] = None,
    w_boulder: Optional[float] = None,
    data_mode: str = "DEMO"
) -> Tuple[TerrainAnalysisResult, Dict[str, np.ndarray]]:
    """
    Performs terrain safety analysis, classifying safe vs critical hazard zones.
    """
    slope_deg, aspect_deg, roughness = compute_terrain_metrics(dem, pixel_scale_m)
    hazard = compute_hazard_score(slope_deg, roughness, boulder_risk, w_slope, w_roughness, w_boulder)

    cell_area_km2 = (pixel_scale_m / 1000.0) ** 2
    total_cells = dem.size

    safe_slope_mask = slope_deg <= settings.CRITICAL_LANDING_SLOPE_DEG
    safe_slope_fraction = float(np.sum(safe_slope_mask) / total_cells)

    high_hazard_mask = hazard >= 0.70
    high_hazard_cells = int(np.sum(high_hazard_mask))
    high_hazard_area_km2 = float(high_hazard_cells * cell_area_km2)

    weights_used = {
        "slope_weight": w_slope if w_slope is not None else settings.WEIGHT_SLOPE,
        "roughness_weight": w_roughness if w_roughness is not None else settings.WEIGHT_ROUGHNESS,
        "boulder_weight": w_boulder if w_boulder is not None else settings.WEIGHT_BOULDER
    }

    provenance = create_provenance(
        dataset_name=f"{crater_id.upper()}_TERRAIN",
        algorithm="Multi-Criteria Terrain Gradient & Micro-Relief Hazard Assessment",
        parameters=weights_used,
        data_mode=data_mode
    )

    result = TerrainAnalysisResult(
        crater_id=crater_id,
        mean_slope_deg=round(float(np.mean(slope_deg)), 2),
        max_slope_deg=round(float(np.max(slope_deg)), 2),
        safe_slope_fraction=round(safe_slope_fraction, 4),
        mean_roughness=round(float(np.mean(roughness)), 2),
        mean_hazard_score=round(float(np.mean(hazard)), 3),
        high_hazard_area_km2=round(high_hazard_area_km2, 2),
        weights_used=weights_used,
        provenance=provenance
    )

    rasters = {
        "slope_deg": slope_deg,
        "aspect_deg": aspect_deg,
        "roughness": roughness,
        "hazard": hazard
    }

    return result, rasters
