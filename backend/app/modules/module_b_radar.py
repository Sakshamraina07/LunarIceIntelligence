"""
MODULE B: DFSAR Polarimetric Radar Analysis.
PRD Compliance: Calculates Circular Polarization Ratio (CPR) and Degree of Polarization (DOP).
Applies configurable scientific screening (CPR > CPR_THRESHOLD and DOP < DOP_THRESHOLD).
Adheres strictly to scientific terminology: 'Radar signature consistent with potential ice-bearing region'.
"""

import numpy as np
from typing import Dict, Any, Tuple, Optional
from app.core.config import settings
from app.core.schemas import RadarAnalysisResult
from app.core.provenance import create_provenance


def compute_cpr_from_sigma(sigma_sc: np.ndarray, sigma_oc: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """
    Computes CPR = sigma_sc / sigma_oc.
    Handles division by zero safely using epsilon thresholding.
    """
    safe_oc = np.maximum(sigma_oc, eps)
    cpr = sigma_sc / safe_oc
    return np.clip(cpr, 0.0, 10.0).astype(np.float32)


def compute_cpr_from_stokes(s0: np.ndarray, s3: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """
    Computes CPR from Stokes parameters S0 and S3:
    CPR = sigma_sc / sigma_oc = (S0 - S3) / (S0 + S3).
    """
    numerator = np.maximum(s0 - s3, 0.0)
    denominator = np.maximum(s0 + s3, eps)
    cpr = numerator / denominator
    return np.clip(cpr, 0.0, 10.0).astype(np.float32)


def compute_dop_from_stokes(
    s0: np.ndarray,
    s1: np.ndarray,
    s2: np.ndarray,
    s3: np.ndarray,
    eps: float = 1e-6
) -> np.ndarray:
    """
    Computes Degree of Polarization (DOP) from Stokes vector:
    DOP = sqrt(s1^2 + s2^2 + s3^2) / S0.
    """
    polarized_power = np.sqrt(s1**2 + s2**2 + s3**2)
    safe_s0 = np.maximum(s0, eps)
    dop = polarized_power / safe_s0
    return np.clip(dop, 0.0, 1.0).astype(np.float32)


def classify_radar_polarimetry(
    cpr_val: float,
    dop_val: float,
    cpr_th: float = 1.0,
    dop_th: float = 0.13
) -> str:
    """
    Classifies polarimetric radar signature per stated physical criteria:
    - CPR > 1.0 and DOP < 0.13: Radar signature consistent with potential ice (CBOE volume scattering)
    - CPR > 1.0 and DOP >= 0.13: Surface roughness anomaly (Rocks/boulders, unlikely ice)
    - CPR <= 1.0 and DOP < 0.13: Diffuse volume scattering (Fine regolith)
    - CPR <= 1.0 and DOP >= 0.13: Low/No ice signature (Typical dry regolith)
    """
    if cpr_val > cpr_th and dop_val < dop_th:
        return "Radar signature consistent with potential ice"
    elif cpr_val > cpr_th and dop_val >= dop_th:
        return "Surface roughness anomaly (Unlikely ice)"
    elif cpr_val <= cpr_th and dop_val < dop_th:
        return "Diffuse volume scattering"
    else:
        return "Low/No ice signature (Typical dry regolith)"


def analyze_dfsar_radar(
    crater_id: str,
    cpr: np.ndarray,
    dop: np.ndarray,
    spacing_m: Tuple[float, float],
    cpr_threshold: Optional[float] = None,
    dop_threshold: Optional[float] = None,
    *,
    data_mode: str,
) -> Tuple[RadarAnalysisResult, Dict[str, np.ndarray]]:
    """
    Executes polarimetric screening according to configurable thresholds.

    `spacing_m` is (metres_per_line, metres_per_sample) for the grid `cpr`/`dop`
    are on. Every area in km² below is cells x sy x sx; the old scalar
    `pixel_scale_m=250.0` squared one number and so reported the anomalous area
    of a square grid that does not exist.
    """
    cpr_th = cpr_threshold if cpr_threshold is not None else settings.CPR_THRESHOLD
    dop_th = dop_threshold if dop_threshold is not None else settings.DOP_THRESHOLD

    sy, sx = spacing_m
    cell_area_km2 = (sy / 1000.0) * (sx / 1000.0)
    total_cells = cpr.size

    # Scientific Radar Anomaly Mask: High CPR (> 1.0) and Low DOP (< 0.13)
    # Reflects coherent backscatter opposition effect (CBOE) and volume depolarization
    radar_mask = (cpr > cpr_th) & (dop < dop_th)

    anomalous_cells = int(np.sum(radar_mask))
    anomalous_area_km2 = float(anomalous_cells * cell_area_km2)
    pass_fraction = float(anomalous_cells / total_cells)

    provenance = create_provenance(
        dataset_name=f"{crater_id.upper()}_DFSAR_POL",
        algorithm="Polarimetric Stokes Decomposition (CPR + DOP Screening)",
        parameters={
            "cpr_threshold": cpr_th,
            "dop_threshold": dop_th,
            "spacing_m": [float(sy), float(sx)]
        },
        data_mode=data_mode
    )

    interpretation = (
        f"Detected {anomalous_area_km2:.2f} km² with CPR > {cpr_th:.2f} and DOP < {dop_th:.2f}. "
        "Radar signature consistent with potential ice-bearing volume scattering."
    )

    mean_cpr_val = round(float(np.mean(cpr)), 3)
    max_cpr_val = round(float(np.max(cpr)), 3)
    mean_dop_val = round(float(np.mean(dop)), 3)
    min_dop_val = round(float(np.min(dop)), 3)

    regional_class = classify_radar_polarimetry(mean_cpr_val, mean_dop_val, cpr_th, dop_th)
    anomaly_class = classify_radar_polarimetry(max_cpr_val, min_dop_val, cpr_th, dop_th)
    
    data_source = "Real DFSAR/OHRC (PRADAN)" if data_mode == "REAL" else "Simulated placeholder — pending real data"

    result = RadarAnalysisResult(
        crater_id=crater_id,
        mean_cpr=mean_cpr_val,
        max_cpr=max_cpr_val,
        mean_dop=mean_dop_val,
        min_dop=min_dop_val,
        cpr_threshold_used=cpr_th,
        dop_threshold_used=dop_th,
        radar_anomalous_area_km2=round(anomalous_area_km2, 2),
        screening_pass_fraction=round(pass_fraction, 4),
        scientific_interpretation=interpretation,
        regional_classification=regional_class,
        anomaly_classification=anomaly_class,
        classification_label="Low/No ice signature" if mean_cpr_val <= cpr_th or mean_dop_val >= dop_th else "Consistent with potential ice",
        data_source_tag=data_source,
        provenance=provenance
    )

    rasters = {
        "cpr": cpr,
        "dop": dop,
        "radar_mask": radar_mask
    }

    return result, rasters
