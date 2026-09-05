"""
Centralized Configuration for Lunar Ice Intelligence and Mission Planning System.
PRD Compliance: No hardcoded thresholds scattered across files. All scientific,
terrain, rover, and volume assumptions are declared here with clear provenance.
"""

import os
from pydantic import BaseModel, Field
from typing import Dict, Any


class Settings(BaseModel):
    PROJECT_NAME: str = "Lunar Ice Intelligence & Traverse Planning System"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api"

    # Requested data mode: 'REAL' or 'DEMO'.
    #
    # REAL is the default because DEMO is no longer a servable state. It is only
    # a request, not an outcome: mission_service decides per crater from
    # real_data_gate.real_data_status(), so a crater with no registered PDS4
    # product answers NOT_INGESTED whatever this says. Defaulting to DEMO meant
    # a caller who omitted the parameter — /report/pdf and /copilot/ask both did —
    # silently asked for seeded data.
    DATA_MODE: str = "REAL"
    RANDOM_SEED: int = 42

    # Henry Labs AI Copilot Settings
    HENRY_LABS_API_KEY: str = os.getenv("HENRY_LABS_API_KEY", "")
    HENRY_LABS_BASE_URL: str = os.getenv("HENRY_LABS_BASE_URL", "https://api.heurist.ai/v1")
    HENRY_LABS_MODEL: str = os.getenv("HENRY_LABS_MODEL", "mistralai/mixtral-8x7b-instruct")

    # Scientific Radar Screening Thresholds.
    #
    # THESE ARE NOT INHERITED MAGIC NUMBERS. They are exactly the published
    # criterion in:
    #
    #     Sinha, R. K. et al. (2026). npj Space Exploration 2:22.
    #     doi:10.1038/s44453-026-00038-9
    #
    # which reports crater F2 inside Faustini (87.39 S, 82.31 E, 1.1 km across)
    # at peak CPR 1.95 with DOP 0.1-0.13 where CPR is elevated, and reads the
    # combination as strong evidence for subsurface ice. CPR > 1.0 with a
    # depressed DOP is the coherent-backscatter opposition effect (CBOE)
    # signature those thresholds are drawn from.
    #
    # ONE DIFFERENCE THAT MATTERS, AND IT IS NOT A DETAIL. Sinha et al. work in
    # FULL POLARIMETRY (HH/HV/VH/VV). This project's DFSAR products are
    # HYBRID / COMPACT POL (`_cp_`, channels LH/LV), for which the correct
    # formulation is the Stokes one,
    #
    #     CPR = (S0 - S3) / (S0 + S3)      DOP = sqrt(S1^2 + S2^2 + S3^2) / S0
    #
    # already implemented in module_b_radar.compute_cpr_from_stokes(). So this
    # project CANNOT replicate their formula and must not claim to; it can state
    # which mode it used and why its derivation is the right one for that mode.
    #
    # Saran et al. (2026, Research Square preprint) dispute the same feature,
    # reporting mean CPR 1.01 +/- 0.3 and DOP 0.32 +/- 0.1, and argue the
    # signature is better explained by roughness. The thresholds below are the
    # criterion under dispute, not a settled fact -- which is exactly why they
    # are cited rather than tuned. See PRD 2 rule 4 and docs/METHODS.md 1.
    CPR_THRESHOLD: float = 1.00
    DOP_THRESHOLD: float = 0.13

    # Terrain Hazard Scoring Weights.
    # These do NOT have to sum to 1.0 — compute_hazard_score divides by their
    # sum, so the score stays in [0, 1] whatever they are.
    # WEIGHT_BOULDER is 0.0 because there is no boulder raster: no boulder
    # detector has been run on this frame, so a boulder term could only be fed
    # a zeros array, and a zeros array is not a measurement — it is a claim that
    # every cell is boulder-free. Weighting it out means the reported hazard is
    # slope + roughness only, which is exactly what the data supports.
    # Restore a non-zero weight the day a real boulder raster exists.
    WEIGHT_SLOPE: float = 0.50
    WEIGHT_ROUGHNESS: float = 0.30
    WEIGHT_BOULDER: float = 0.0

    # Physical Slope Limits for Safe Rover Movement
    MAX_TRAVERSABLE_SLOPE_DEG: float = 20.0
    CRITICAL_LANDING_SLOPE_DEG: float = 12.0

    # Landing Site Selection Criteria Weights
    WEIGHT_LANDING_SAFETY: float = 0.40
    WEIGHT_LANDING_ILLUM: float = 0.25
    WEIGHT_LANDING_SCIENCE: float = 0.20
    WEIGHT_LANDING_DISTANCE: float = 0.15

    # Rover Traverse Cost Weights (Multi-Objective)
    WEIGHT_ROVER_DISTANCE: float = 0.25
    WEIGHT_ROVER_HAZARD: float = 0.40
    WEIGHT_ROVER_ENERGY: float = 0.20
    WEIGHT_ROVER_SCIENCE: float = 0.15

    # Simplified Engineering Energy Model Parameters (Rover Specification)
    ROVER_MASS_KG: float = 30.0  # Pragyan-class exploration micro-rover
    BASE_POWER_W: float = 25.0
    NOMINAL_SPEED_MPS: float = 0.05  # 5 cm/second typical lunar rover speed
    SOLAR_POWER_GAIN_W: float = 50.0  # Peak solar array generation under direct illumination

    # Ice-Equivalent Volume Model Parameters
    DEFAULT_ICE_DEPTH_M: float = 5.0
    CONSERVATIVE_ICE_DEPTH_M: float = 2.0
    UPPER_ICE_DEPTH_M: float = 10.0

    DEFAULT_ICE_FRACTION: float = 0.15
    CONSERVATIVE_ICE_FRACTION: float = 0.05
    UPPER_ICE_FRACTION: float = 0.30

    REGOLITH_BULK_DENSITY_KG_M3: float = 1500.0
    WATER_ICE_DENSITY_KG_M3: float = 930.0


settings = Settings()
