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

    # Data Mode: 'DEMO' or 'REAL'
    DATA_MODE: str = "DEMO"
    RANDOM_SEED: int = 42

    # Henry Labs AI Copilot Settings
    HENRY_LABS_API_KEY: str = os.getenv("HENRY_LABS_API_KEY", "")
    HENRY_LABS_BASE_URL: str = os.getenv("HENRY_LABS_BASE_URL", "https://api.heurist.ai/v1")
    HENRY_LABS_MODEL: str = os.getenv("HENRY_LABS_MODEL", "mistralai/mixtral-8x7b-instruct")

    # Scientific Radar Screening Thresholds (Baseline PRD criteria)
    # CPR: Circular Polarization Ratio (Same-sense to Opposite-sense)
    # DOP: Degree of Polarization (Polarimetric purity of Stokes vector)
    CPR_THRESHOLD: float = 1.00
    DOP_THRESHOLD: float = 0.13

    # Terrain Hazard Scoring Weights (Must sum to 1.0)
    WEIGHT_SLOPE: float = 0.50
    WEIGHT_ROUGHNESS: float = 0.30
    WEIGHT_BOULDER: float = 0.20

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
