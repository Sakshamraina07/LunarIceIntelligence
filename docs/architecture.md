# System Architecture: Lunar Ice Intelligence v2.0

## High-Level Pipeline

The Lunar Ice Intelligence & Mission Planning System integrates lunar remote sensing, radar polarimetry, machine learning, and multi-objective path planning into an explainable 7-module pipeline:

```text
                 LUNAR DATA INGESTION
          (DFSAR, OHRC, LOLA / DEM Rasters)
          [REAL MODE / DETERMINISTIC DEMO MODE]
                          │
                          ▼
             ┌─────────────────────────┐
             │ A. PSR / CRATER MAPPING │
             └────────────┬────────────┘
                          │
                          ▼
             ┌─────────────────────────┐
             │ B. RADAR ANALYSIS       │
             │ CPR + DOP Polarimetry   │
             └────────────┬────────────┘
                          │
                          ▼
             ┌─────────────────────────┐
             │ C. ICE INTELLIGENCE     │
             │ Scientific + ML Model   │
             └────────────┬────────────┘
                          │
               ┌──────────┴──────────┐
               ▼                     ▼
     ┌──────────────────┐   ┌────────────────────┐
     │ D. TERRAIN       │   │ E. LANDING SITE    │
     │ SAFETY           │──►│ SELECTION          │
     └──────────────────┘   └─────────┬──────────┘
                                       │
                                       ▼
                          ┌──────────────────────┐
                          │ F. ROVER PLANNING    │
                          │ A* + Dijkstra        │
                          │ Science-Aware Route  │
                          └──────────┬───────────┘
                                     │
                                     ▼
                          ┌──────────────────────┐
                          │ G. ICE VOLUME +      │
                          │ MISSION REPORT (PDF) │
                          └──────────────────────┘
```

## Backend Modular Architecture (`backend/app/`)
- **`core/config.py`**: Centralized configuration of thresholds (CPR > 1.0, DOP < 0.13), weights, and rover parameters.
- **`core/schemas.py`**: Strict Pydantic contracts and data provenance models.
- **`demo/lunar_generator.py`**: Deterministic synthetic South Polar lunar craters (Shackleton, Shoemaker, Faustini) based on fixed random seed (42).
- **`modules/module_a_psr.py`**: Grazing solar illumination ray-tracing and distinction between primary PSRs and doubly-shadowed cold-traps.
- **`modules/module_b_radar.py`**: DFSAR Stokes polarimetric decomposition calculating Circular Polarization Ratio (CPR) and Degree of Polarization (DOP).
- **`modules/module_c_ice.py`**: Scientific dual-threshold screening mask and explainable Random Forest ML Ice Likelihood estimator ($P \in [0, 1]$).
- **`modules/module_d_terrain.py`**: Multi-factor terrain hazard index combining surface slope, roughness, and boulder risk.
- **`modules/module_e_landing.py`**: Algorithmic multi-criteria ranking of landing candidates based on touchdown safety, solar array illumination, target proximity, and scientific vantage.
- **`modules/module_f_rover.py`**: 8-connected grid graph traversal comparing Shortest, Safest, and Science-Aware strategies using A* and Dijkstra algorithms with a simplified engineering energy model.
- **`modules/module_g_volume.py`**: 3-tier ice-equivalent volume range estimation and parameter sensitivity analysis.
- **`modules/experiments_runner.py`**: Automated evaluation suite for Experiments 1 through 5 and progressive ablation studies.
- **`services/pdf_generator.py`**: ReportLab mission decision PDF report generator.
- **`api/api_router.py`**: REST endpoints powering the client interface.

## Frontend Architecture (`frontend/src/`)
- **`components/Map/GISMapViewer.tsx`**: High-performance HTML5 Canvas GIS viewer with multi-raster layer switching, interactive crosshair coordinate telemetry, landing site pins, and rover trajectories.
- **`components/Workflow/MissionStepper.tsx`**: 12-step guided mission sequence.
- **`components/Views/WorkflowViews.tsx`**: Specialized step-by-step telemetry cards, ranked landing tables, trajectory comparison matrices, sensitivity sliders, and report downloads.
