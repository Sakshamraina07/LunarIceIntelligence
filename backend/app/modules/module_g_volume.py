"""
MODULE G: Ice-Equivalent Volume Estimation & Parameter Sensitivity Analysis.
PRD Compliance: Estimates a 3-tier uncertainty range (Conservative, Expected, Upper)
based on: Volume = Ice-bearing Area * Assumed Depth * Ice Fraction.
Always labels as 'Estimated Ice-Equivalent Volume' (never 'Measured').
Includes multi-parameter sensitivity analysis sweeps.
"""

import numpy as np
from typing import Dict, Any, List, Optional
from app.core.config import settings
from app.core.schemas import (
    IceVolumeEstimateResult,
    SensitivityAnalysisResult,
    SensitivityPoint
)
from app.core.provenance import create_provenance


def estimate_ice_volume(
    candidate_area_km2: float,
    crater_id: str = "shackleton",
    depth_conservative_m: Optional[float] = None,
    depth_expected_m: Optional[float] = None,
    depth_upper_m: Optional[float] = None,
    fraction_conservative: Optional[float] = None,
    fraction_expected: Optional[float] = None,
    fraction_upper: Optional[float] = None,
    *,
    data_mode: str,
) -> IceVolumeEstimateResult:
    """
    Computes volumetric and mass estimates for candidate subsurface volatile ice deposits.
    """
    d_cons = depth_conservative_m if depth_conservative_m is not None else settings.CONSERVATIVE_ICE_DEPTH_M
    d_exp = depth_expected_m if depth_expected_m is not None else settings.DEFAULT_ICE_DEPTH_M
    d_up = depth_upper_m if depth_upper_m is not None else settings.UPPER_ICE_DEPTH_M

    f_cons = fraction_conservative if fraction_conservative is not None else settings.CONSERVATIVE_ICE_FRACTION
    f_exp = fraction_expected if fraction_expected is not None else settings.DEFAULT_ICE_FRACTION
    f_up = fraction_upper if fraction_upper is not None else settings.UPPER_ICE_FRACTION

    area_m2 = candidate_area_km2 * 1e6
    rho_ice = settings.WATER_ICE_DENSITY_KG_M3  # ~930 kg/m^3

    # Volumetric ranges (m^3)
    v_cons = area_m2 * d_cons * f_cons
    v_exp = area_m2 * d_exp * f_exp
    v_up = area_m2 * d_up * f_up

    # Mass ranges (metric tons = kg / 1000)
    m_cons = (v_cons * rho_ice) / 1000.0
    m_exp = (v_exp * rho_ice) / 1000.0
    m_up = (v_up * rho_ice) / 1000.0

    provenance = create_provenance(
        dataset_name=f"{crater_id.upper()}_VOLUME",
        algorithm="Volumetric Area-Depth-Porosity Inversion Range Model",
        parameters={
            "candidate_area_km2": candidate_area_km2,
            "depth_range_m": [d_cons, d_exp, d_up],
            "fraction_range": [f_cons, f_exp, f_up],
            "ice_density_kg_m3": rho_ice
        },
        data_mode=data_mode
    )

    return IceVolumeEstimateResult(
        candidate_area_km2=round(candidate_area_km2, 2),
        conservative_volume_m3=round(v_cons, 0),
        conservative_mass_metric_tons=round(m_cons, 0),
        conservative_assumptions={
            "assumed_depth_m": d_cons,
            "ice_volume_fraction": f_cons,
            "description": "Thin regolith veneer with isolated subsurface ice grains."
        },
        expected_volume_m3=round(v_exp, 0),
        expected_mass_metric_tons=round(m_exp, 0),
        expected_assumptions={
            "assumed_depth_m": d_exp,
            "ice_volume_fraction": f_exp,
            "description": "Moderate depth permafrost volatile mixture consistent with LCROSS plume impact constraints."
        },
        upper_volume_m3=round(v_up, 0),
        upper_mass_metric_tons=round(m_up, 0),
        upper_assumptions={
            "assumed_depth_m": d_up,
            "ice_volume_fraction": f_up,
            "description": "Deep cryo-trap with persistent thick ice-cemented regolith lenses."
        },
        scientific_label="Estimated Ice-Equivalent Volume",
        limitation_statement=(
            "Estimated Ice-Equivalent Volume is a computational inference based on remote-sensing radar "
            "anomalies and assumed regolith stratigraphy. It does NOT represent direct in-situ measured ice mass."
        ),
        provenance=provenance
    )


# run_sensitivity_sweep() WAS HERE. Deleted in PRD Phase 1B.
#
# It computed nothing. The whole "sweep" was three closed-form scalings of a
# single baseline number handed in by the caller:
#
#     cpr_threshold:  scale = max(0.2, 1.0 - (val - 1.0) * 0.8)
#     dop_threshold:  scale = max(0.3, 1.0 + (val - 0.13) * 3.0)
#     area = base_candidate_area_km2 * scale
#
# No raster was read, so no threshold was ever actually applied to any data.
# The remaining three columns were worse: best_landing_site_id was the string
# "site_1" at every row, rover_distance_km was 11.2 + val * 0.1 and
# rover_energy_wh was 145.0 + val * 2.5 -- straight lines through the swept
# parameter, presented as a replanned traverse. The endpoint's default
# base_area_km2 was 8.75, a number with no origin anywhere in this project.
#
# The real sweep is computed offline by backend/scripts/build_analysis.py
# (sweep_threshold / sweep_assumption): it re-thresholds the native 25 m/px
# arrays and counts pixels, so every area column is a measurement. It ships in
# frontend/public/analysis/<crater>.json under "sensitivity", and
# GET /api/sensitivity/{param} now serves that table rather than inventing one.
