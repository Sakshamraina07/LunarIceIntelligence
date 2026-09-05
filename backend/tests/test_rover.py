"""
Unit tests for Rover Path Planning and Energy Model.
Tests A* vs Dijkstra, impassable cliff avoidance, and energy consumption model.
"""

import pytest
import numpy as np
from app.core.config import settings
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
    roughness = np.full((size, size), 2.0)
    hazard = np.full((size, size), 0.1)
    illumination = np.ones((size, size))
    scientific_mask = np.zeros((size, size), dtype=bool)
    scientific_mask[15, 15] = True

    start_xy = (2, 2)
    target_xy = (15, 15)

    # Test A*
    res_astar = plan_rover_path(
        dem=dem,
        slope_deg=slope,
        roughness=roughness,
        hazard=hazard,
        illumination=illumination,
        scientific_mask=scientific_mask,
        start_xy=start_xy,
        target_xy=target_xy,
        strategy="Science-Aware",
        algorithm="A*",
        data_mode="DEMO",
        spacing_m=(100.0, 100.0)
    )

    assert res_astar.path_found is True
    assert len(res_astar.waypoints) > 0
    assert res_astar.waypoints[0].x == start_xy[0] and res_astar.waypoints[0].y == start_xy[1]
    assert res_astar.waypoints[-1].x == target_xy[0] and res_astar.waypoints[-1].y == target_xy[1]


def test_anisotropic_spacing_changes_reported_distance():
    """A step across samples must cost its own spacing, not the line spacing.

    On a grid whose samples are 4x wider than its lines, a purely horizontal
    traverse has to report 4x the distance of the same traverse run vertically.
    The old scalar pixel_scale_m made both report the same number.
    """
    size = 12
    flat = dict(
        dem=np.zeros((size, size)),
        slope_deg=np.zeros((size, size)),
        roughness=np.zeros((size, size)),
        hazard=np.zeros((size, size)),
        illumination=np.ones((size, size)),
        scientific_mask=np.zeros((size, size), dtype=bool),
        strategy="Shortest",
        algorithm="A*",
        data_mode="DEMO",
        spacing_m=(100.0, 400.0),
    )

    horizontal = plan_rover_path(start_xy=(1, 5), target_xy=(9, 5), **flat)
    vertical = plan_rover_path(start_xy=(5, 1), target_xy=(5, 9), **flat)

    assert horizontal.path_found and vertical.path_found
    # 8 samples * 400 m = 3.2 km across; 8 lines * 100 m = 0.8 km down
    assert horizontal.total_distance_km == pytest.approx(3.2, abs=0.01)
    assert vertical.total_distance_km == pytest.approx(0.8, abs=0.01)


def test_impassable_cliff_barrier_failure():
    size = 20
    dem = np.zeros((size, size))
    # Vertical impassable barrier at column x=10, slope 30 deg — above
    # settings.MAX_TRAVERSABLE_SLOPE_DEG (20 deg), which the planner now reads
    # instead of its own 22.0 default.
    slope = np.zeros((size, size))
    slope[:, 10] = 30.0
    roughness = np.zeros((size, size))
    hazard = np.zeros((size, size))
    illumination = np.ones((size, size))
    scientific_mask = np.zeros((size, size), dtype=bool)

    start_xy = (2, 5)
    target_xy = (18, 5)

    res = plan_rover_path(
        dem=dem,
        slope_deg=slope,
        roughness=roughness,
        hazard=hazard,
        illumination=illumination,
        scientific_mask=scientific_mask,
        start_xy=start_xy,
        target_xy=target_xy,
        strategy="Shortest",
        algorithm="A*",
        data_mode="DEMO",
        spacing_m=(100.0, 100.0)
    )

    # PRD Rule: Never fabricate a path when terrain is impassable!
    assert res.path_found is False
    assert "NO FEASIBLE PATH" in res.failure_reason
    # The reason must name the limit that was actually applied, and it must be
    # the configured one. The module used to carry its own 22.0 default while
    # config.py declared 20.0.
    assert str(settings.MAX_TRAVERSABLE_SLOPE_DEG).rstrip('0').rstrip('.') in res.failure_reason
    # Optimality is not claimed: only Dijkstra is implemented.
    assert res.algorithm_used == "Dijkstra"
