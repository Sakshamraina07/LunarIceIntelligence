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
    data_mode: str = "DEMO"
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


def run_sensitivity_sweep(
    parameter_name: str,
    base_candidate_area_km2: float,
    sweep_values: Optional[List[float]] = None
) -> SensitivityAnalysisResult:
    """
    Simulates parameter sensitivity sweeps for PRD Section 20.
    """
    if parameter_name == "cpr_threshold":
        baseline = settings.CPR_THRESHOLD
        values = sweep_values or [0.7, 0.85, 1.0, 1.15, 1.3, 1.5]
        summary = "Higher CPR threshold restricts screening to pure CBOE cores, reducing total candidate area."
    elif parameter_name == "dop_threshold":
        baseline = settings.DOP_THRESHOLD
        values = sweep_values or [0.08, 0.10, 0.13, 0.16, 0.20]
        summary = "Higher DOP threshold permits less depolarized terrain, expanding the candidate area."
    elif parameter_name == "assumed_depth_m":
        baseline = settings.DEFAULT_ICE_DEPTH_M
        values = sweep_values or [1.0, 3.0, 5.0, 8.0, 12.0]
        summary = "Ice volume scales linearly with assumed deposit depth."
    else:  # ice_fraction
        baseline = settings.DEFAULT_ICE_FRACTION
        values = sweep_values or [0.05, 0.10, 0.15, 0.20, 0.30]
        summary = "Ice volume scales linearly with regolith pore ice volumetric fraction."

    points: List[SensitivityPoint] = []
    for val in values:
        if parameter_name == "cpr_threshold":
            scale = max(0.2, 1.0 - (val - 1.0) * 0.8)
            area = base_candidate_area_km2 * scale
            vol = area * 1e6 * settings.DEFAULT_ICE_DEPTH_M * settings.DEFAULT_ICE_FRACTION
        elif parameter_name == "dop_threshold":
            scale = max(0.3, 1.0 + (val - 0.13) * 3.0)
            area = base_candidate_area_km2 * scale
            vol = area * 1e6 * settings.DEFAULT_ICE_DEPTH_M * settings.DEFAULT_ICE_FRACTION
        elif parameter_name == "assumed_depth_m":
            area = base_candidate_area_km2
            vol = area * 1e6 * val * settings.DEFAULT_ICE_FRACTION
        else:
            area = base_candidate_area_km2
            vol = area * 1e6 * settings.DEFAULT_ICE_DEPTH_M * val

        points.append(SensitivityPoint(
            parameter_name=parameter_name,
            parameter_value=round(val, 3),
            candidate_ice_area_km2=round(area, 2),
            expected_volume_m3=round(vol, 0),
            best_landing_site_id="site_1",
            rover_distance_km=round(11.2 + (val * 0.1), 2),
            rover_energy_wh=round(145.0 + (val * 2.5), 1)
        ))

    return SensitivityAnalysisResult(
        parameter_tested=parameter_name,
        baseline_value=baseline,
        sweep_values=values,
        results=points,
        sensitivity_summary=summary
    )
