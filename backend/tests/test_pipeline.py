"""
Integration test for complete end-to-end scientific pipeline.
Tests full pipeline on Shackleton, Shoemaker, and Faustini craters.
"""

import pytest
from app.services.mission_service import mission_orchestrator
from app.modules.experiments_runner import run_all_research_experiments


def test_full_mission_pipeline_execution():
    crater_ids = ["shackleton", "shoemaker", "faustini"]

    for cid in crater_ids:
        state = mission_orchestrator.run_full_mission_pipeline(crater_id=cid)

        # Verify all mandatory sections exist
        assert state["selected_crater"].id == cid
        assert state["data_mode"] in ["DEMO", "REAL"]
        assert state["psr"].psr_area_km2 >= 0.0
        assert state["radar"].mean_cpr >= 0.0
        assert state["ice"].scientific_candidate_area_km2 >= 0.0
        assert state["terrain"].safe_slope_fraction > 0.0
        assert len(state["landing_sites"]) >= 3
        assert state["recommended_landing_site"].is_recommended is True

        # Verify rover routes
        routes = state["rover_routes"]
        assert "Shortest" in routes
        assert "Safest" in routes
        assert "Science-Aware" in routes

        sa_route = routes["Science-Aware"]
        assert sa_route.strategy == "Science-Aware"
        if sa_route.path_found:
            assert sa_route.total_distance_km > 0.0
            assert sa_route.total_energy_wh > 0.0

        # Verify volume estimate
        vol = state["volume"]
        assert vol.conservative_volume_m3 <= vol.expected_volume_m3 <= vol.upper_volume_m3
        assert vol.scientific_label == "Estimated Ice-Equivalent Volume"

        # Verify raster layers exist for visualization
        layers = state["raster_layers"]
        for layer_name in ["hillshade", "dem_elevation", "illumination", "psr_mask", "cpr_heatmap", "dop_heatmap", "hazard_map"]:
            assert layer_name in layers
            assert layers[layer_name].startswith("data:image/png;base64,")


def test_experiments_suite_execution():
    results = run_all_research_experiments(crater_id="shackleton")
    assert "experiments" in results
    assert "ablation_study" in results
    assert len(results["experiments"]) == 4
    assert len(results["ablation_study"]) == 6
