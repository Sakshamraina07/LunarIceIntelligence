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
    spacing_m: Tuple[float, float]
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Computes slope (degrees), aspect (degrees), and terrain roughness.

    `spacing_m` is (metres_per_line, metres_per_sample): the ground spacing of
    axis 0 (rows/lines) and axis 1 (columns/samples) of `dem`. There is NO
    default on purpose. The old `pixel_scale_m=250.0` was a single scalar handed
    to np.gradient for both axes; on this frame the true posts are (25, 25) on
    the native grid and (564.5, 1654.5) on the live 100x100 grid, so a scalar was
    wrong on at least one axis and silently rescaled every slope. Forcing the
    caller to pass the tuple its own array implies is the fix. np.gradient takes
    the axis-0 spacing first, which is why the order is (sy, sx).
    """
    sy, sx = spacing_m
    grad_y, grad_x = np.gradient(dem, sy, sx)
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
    boulder_risk: Optional[np.ndarray],
    w_slope: Optional[float] = None,
    w_roughness: Optional[float] = None,
    w_boulder: Optional[float] = None
) -> np.ndarray:
    """
    Normalised terrain hazard score in [0, 1].

    `boulder_risk` may be None, and None is NOT a zeros array. No optical
    product exists for this frame, so a zeros array would assert "imaged and
    found free of rocks" for every cell. When it is None the boulder term is
    dropped and the blend is RENORMALISED over the terms that remain, so the
    score still spans [0, 1] and means a slope-and-roughness hazard.

    Passing a boulder raster while forcing `w_boulder=0.0` gives the same
    renormalisation, which is how mission_service already called it.
    """
    w1 = w_slope if w_slope is not None else settings.WEIGHT_SLOPE
    w2 = w_roughness if w_roughness is not None else settings.WEIGHT_ROUGHNESS
    w3 = w_boulder if w_boulder is not None else settings.WEIGHT_BOULDER

    if boulder_risk is None:
        w3 = 0.0

    # Critical traversability limit for a small lunar rover is ~20 degrees.
    slope_risk = np.clip(slope_deg / settings.MAX_TRAVERSABLE_SLOPE_DEG, 0.0, 1.0)
    # Roughness risk, normalised against a 50 m local height variance.
    roughness_risk = np.clip(roughness / 50.0, 0.0, 1.0)

    total_weight = w1 + w2 + w3
    if total_weight <= 0.0:
        raise ValueError(
            "compute_hazard_score: every weight is zero, so there is no hazard model left to "
            "evaluate. Refusing to divide by zero and return a plausible-looking array."
        )

    numerator = w1 * slope_risk + w2 * roughness_risk
    if w3 > 0.0:
        if boulder_risk is None:
            raise ValueError(
                "compute_hazard_score: w_boulder > 0 but boulder_risk is None. A boulder weight "
                "cannot be applied to a term that was never measured."
            )
        numerator = numerator + w3 * np.clip(boulder_risk, 0.0, 1.0)

    hazard = numerator / total_weight
    return np.clip(hazard, 0.0, 1.0).astype(np.float32)


def analyze_terrain_safety(
    crater_id: str,
    dem: np.ndarray,
    boulder_risk: Optional[np.ndarray],
    spacing_m: Tuple[float, float],
    w_slope: Optional[float] = None,
    w_roughness: Optional[float] = None,
    w_boulder: Optional[float] = None,
    *,
    data_mode: str,
    prescored: Optional[Dict[str, np.ndarray]] = None,
) -> Tuple[TerrainAnalysisResult, Dict[str, np.ndarray]]:
    """
    Performs terrain safety analysis, classifying safe vs critical hazard zones.

    `spacing_m` is (metres_per_line, metres_per_sample); see compute_terrain_metrics.
    This module is the single source of the hazard definition — render_layers.py
    and build_analysis.py both use compute_hazard_score so the rendered picture
    and the reported number cannot drift apart.
    """
    # PRESCORED WINS, AND THAT IS THE WHOLE POINT.
    #
    # Recomputing terrain from `dem` scores it on whatever grid `dem` is served
    # on. For the 100x100 serving grid that is ~565 x 1654 m cells, so the 5x5
    # roughness window spans kilometres and measures REGIONAL RELIEF -- it read
    # 268.48 m mean roughness where the native frame reads 6.87 m, and hazard
    # 0.635 against 0.373. clip(roughness/50) is pinned at 1.0 throughout, so
    # slope stops contributing at all.
    #
    # pradan_pipeline.process_real_dem already scores at 25 m and area-averages
    # the bounded fields down. Recomputing here threw that away, which is why
    # fixing process_real_dem alone did not move a single API number. When the
    # caller supplies prescored rasters they are USED, not re-derived.
    if prescored and all(k in prescored for k in ("slope_deg", "roughness", "hazard")):
        slope_deg = prescored["slope_deg"]
        roughness = prescored["roughness"]
        aspect_deg = prescored.get("aspect_deg", np.zeros_like(slope_deg))
        hazard = prescored["hazard"]
    else:
        slope_deg, aspect_deg, roughness = compute_terrain_metrics(dem, spacing_m)
        hazard = compute_hazard_score(slope_deg, roughness, boulder_risk,
                                      w_slope, w_roughness, w_boulder)

    cell_area_km2 = (spacing_m[0] / 1000.0) * (spacing_m[1] / 1000.0)
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
