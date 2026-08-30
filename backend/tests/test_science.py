"""
Unit tests for Lunar Scientific Computation Modules.
Tests CPR, DOP, Slope, Roughness, Hazard Scoring, and Ice Volume calculation.
"""

import pytest
import numpy as np
from app.modules.module_a_psr import compute_hillshade
from app.modules.module_b_radar import compute_cpr_from_sigma, compute_dop_from_stokes
from app.modules.module_d_terrain import compute_hazard_score
from app.modules.module_g_volume import estimate_ice_volume
from app.core.config import settings


def test_cpr_computation():
    sigma_sc = np.array([1.2, 0.5, 0.0])
    sigma_oc = np.array([0.8, 1.0, 0.0])

    cpr = compute_cpr_from_sigma(sigma_sc, sigma_oc)

    # 1.2 / 0.8 = 1.5
    assert np.isclose(cpr[0], 1.5, atol=1e-3)
    # 0.5 / 1.0 = 0.5
    assert np.isclose(cpr[1], 0.5, atol=1e-3)
    # Zero division handled safely via epsilon
    assert cpr[2] >= 0.0
    assert not np.isnan(cpr).any()


def test_dop_computation():
    s0 = np.array([1.0, 2.0, 0.0])
    s1 = np.array([0.05, 0.2, 0.0])
    s2 = np.array([0.05, 0.2, 0.0])
    s3 = np.array([0.02, 0.1, 0.0])

    dop = compute_dop_from_stokes(s0, s1, s2, s3)

    # Depolarized sample (DOP < 0.13)
    assert dop[0] < 0.13
    assert not np.isnan(dop).any()
    assert (dop >= 0.0).all() and (dop <= 1.0).all()


def test_hazard_score_bounds():
    slope = np.array([5.0, 15.0, 25.0])
    roughness = np.array([10.0, 30.0, 60.0])
    boulders = np.array([0.1, 0.5, 0.9])

    hazard = compute_hazard_score(slope, roughness, boulders)

    assert (hazard >= 0.0).all() and (hazard <= 1.0).all()
    # Monotonic increasing risk
    assert hazard[0] < hazard[1] < hazard[2]


def test_ice_volume_estimation_tiers():
    area_km2 = 10.0
    res = estimate_ice_volume(area_km2, crater_id="shackleton")

    # Volume: Area * Depth * Fraction
    # Conservative: 10e6 * 2m * 0.05 = 1,000,000 m3
    # Expected: 10e6 * 5m * 0.15 = 7,500,000 m3
    # Upper: 10e6 * 10m * 0.30 = 30,000,000 m3
    assert res.conservative_volume_m3 < res.expected_volume_m3 < res.upper_volume_m3
    assert res.conservative_volume_m3 == 1000000.0
    assert res.expected_volume_m3 == 7500000.0
    assert res.upper_volume_m3 == 30000000.0
    assert res.scientific_label == "Estimated Ice-Equivalent Volume"
