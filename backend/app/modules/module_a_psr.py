"""
MODULE A: PSR & Doubly-Shadowed Crater Mapping.
PRD Compliance: Identifies permanently shadowed regions and distinguishes doubly-shadowed
candidate craters from general PSRs. Computes hillshade, illumination fractions, and geometric statistics.
"""

import numpy as np
from typing import Dict, Any, Tuple
from scipy.ndimage import label
from app.core.config import settings
from app.core.schemas import PSRAnalysisResult
from app.core.provenance import create_provenance


def compute_hillshade(
    dem: np.ndarray,
    spacing_m: Tuple[float, float],
    azimuth_deg: float = 315.0,
    altitude_deg: float = 45.0
) -> np.ndarray:
    """
    Standard analytical hillshade model based on Horn (1981) surface gradients.

    `spacing_m` is (metres_per_line, metres_per_sample) — the ground spacing of
    axis 0 and axis 1 of `dem`, in that order, because that is the order
    np.gradient consumes. There is deliberately no default: the old scalar
    `pixel_scale_m=250.0` was applied to both axes at once, which silently
    rescaled the gradient on any anisotropic grid (the live 100x100 mission grid
    is 564.5 m per line by 1654.5 m per sample — a factor of ~2.9 apart).
    """
    sy, sx = spacing_m
    grad_y, grad_x = np.gradient(dem, sy, sx)
    slope_rad = np.arctan(np.sqrt(grad_x**2 + grad_y**2))
    aspect_rad = np.arctan2(-grad_x, grad_y)

    azimuth_rad = np.radians(azimuth_deg)
    altitude_rad = np.radians(altitude_deg)

    shaded = (
        np.sin(altitude_rad) * np.cos(slope_rad) +
        np.cos(altitude_rad) * np.sin(slope_rad) * np.cos(azimuth_rad - aspect_rad)
    )
    return np.clip(shaded, 0.0, 1.0).astype(np.float32)


def analyze_psr(
    crater_id: str,
    dem: np.ndarray,
    illumination: np.ndarray,
    psr_mask: np.ndarray,
    doubly_shadowed_mask: np.ndarray,
    spacing_m: Tuple[float, float],
    *,
    data_mode: str,
) -> Tuple[PSRAnalysisResult, Dict[str, np.ndarray]]:
    """
    Performs illumination & shadow analysis, separating PSR from doubly-shadowed zones.

    `spacing_m` is (metres_per_line, metres_per_sample); see compute_hillshade.
    Cell area is the product of the two, not the square of one of them.
    """
    sy, sx = spacing_m
    cell_area_km2 = (sy / 1000.0) * (sx / 1000.0)
    total_cells = dem.size
    total_area_km2 = total_cells * cell_area_km2

    psr_cells = np.sum(psr_mask)
    psr_area_km2 = float(psr_cells * cell_area_km2)
    psr_area_fraction = float(psr_cells / total_cells)

    doubly_cells = np.sum(doubly_shadowed_mask)
    doubly_shadowed_area_km2 = float(doubly_cells * cell_area_km2)

    mean_illumination = float(np.mean(illumination))

    # Shadow depth estimate: Height difference between surrounding rim crest and deepest shadow floor
    shadow_depth_estimate_m = float(np.max(dem) - np.min(dem[psr_mask])) if psr_cells > 0 else 0.0

    hillshade = compute_hillshade(dem, spacing_m)

    provenance = create_provenance(
        dataset_name=f"{crater_id.upper()}_DEM_LOLA",
        algorithm="Analytical Ray-Tracing & Horn Hillshade with Cold-Trap Partitioning",
        parameters={
            # Report the spacing actually used on each axis, and the hillshade
            # geometry actually used. The previous dict claimed sun_elevation 1.5
            # deg / azimuth 45 deg while compute_hillshade ran at altitude 45 /
            # azimuth 315 — the provenance described a run that never happened.
            "spacing_m": [float(sy), float(sx)],
            "hillshade_altitude_deg": 45.0,
            "hillshade_azimuth_deg": 315.0
        },
        data_mode=data_mode
    )

    result = PSRAnalysisResult(
        crater_id=crater_id,
        total_area_km2=round(total_area_km2, 2),
        psr_area_km2=round(psr_area_km2, 2),
        psr_area_fraction=round(psr_area_fraction, 4),
        doubly_shadowed_area_km2=round(doubly_shadowed_area_km2, 2),
        mean_illumination_fraction=round(mean_illumination, 3),
        shadow_depth_estimate_m=round(shadow_depth_estimate_m, 1),
        confidence_level="High" if psr_area_km2 > 5.0 else "Medium",
        provenance=provenance
    )

    rasters = {
        "hillshade": hillshade,
        "illumination": illumination,
        "psr_mask": psr_mask,
        "doubly_shadowed_mask": doubly_shadowed_mask
    }

    return result, rasters
