"""
Unit tests for Rover Path Planning and Energy Model.
Tests A* vs Dijkstra, impassable cliff avoidance, and energy consumption model.
"""

import pytest
import numpy as np
from app.modules.module_f_rover import plan_rover_path, compute_step_energy_wh


def test_energy_step_model():
    # Downhill on smooth illuminated terrain
    e_down = compute_step_energy_wh(dist_m=50.0, slope_deg=-5.0, roughness=2.0, illumination=1.0)
    # Steep uphill on rough shadow terrain
    e_up = compute_step_energy_wh(dist_m=50.0, slope_deg=15.0, roughness=25.0, illumination=0.0)

    assert e_up > e_down
    assert e_down > 0.0


def test_rover_path_reachability():
    # Create simple 20x20 flat test environment
    size = 20
    dem = np.zeros((size, size))
    slope = np.full((size, size), 5.0)
    hazard = np.full((size, size), 0.1)
    illumination = np.ones((size, size))
    scientific_mask = np.zeros((size, size), dtype=bool)
    scientific_mask[15, 15] = True
    ml_likelihood = np.zeros((size, size))
    ml_likelihood[15, 15] = 0.9

    start_xy = (2, 2)
    target_xy = (15, 15)

    # Test A*
    res_astar = plan_rover_path(
        dem=dem,
        slope_deg=slope,
        hazard=hazard,
        illumination=illumination,
        scientific_mask=scientific_mask,
        ml_likelihood=ml_likelihood,
        start_xy=start_xy,
        target_xy=target_xy,
        strategy="Science-Aware",
        algorithm="A*",
        pixel_scale_m=100.0
    )

    assert res_astar.path_found is True
    assert len(res_astar.waypoints) > 0
    assert res_astar.waypoints[0].x == start_xy[0] and res_astar.waypoints[0].y == start_xy[1]
    assert res_astar.waypoints[-1].x == target_xy[0] and res_astar.waypoints[-1].y == target_xy[1]


def test_impassable_cliff_barrier_failure():
    size = 20
    dem = np.zeros((size, size))
    # Vertical impassable barrier at column x=10 with slope 30 deg (> 22 deg limit)
    slope = np.zeros((size, size))
    slope[:, 10] = 30.0
    hazard = np.zeros((size, size))
    illumination = np.ones((size, size))
    scientific_mask = np.zeros((size, size), dtype=bool)
    ml_likelihood = np.zeros((size, size))

    start_xy = (2, 5)
    target_xy = (18, 5)

    res = plan_rover_path(
        dem=dem,
        slope_deg=slope,
        hazard=hazard,
        illumination=illumination,
        scientific_mask=scientific_mask,
        ml_likelihood=ml_likelihood,
        start_xy=start_xy,
        target_xy=target_xy,
        strategy="Shortest",
        algorithm="A*",
        pixel_scale_m=100.0
    )

    # PRD Rule: Never fabricate a path when terrain is impassable!
    assert res.path_found is False
    assert "NO FEASIBLE PATH FOUND" in res.failure_reason
