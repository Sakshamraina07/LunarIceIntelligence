# Testing & Verification Guide: Lunar Ice Intelligence v2.0

## Automated Test Suite (`backend/tests/`)
Run all automated unit and integration tests via Pytest:
```powershell
cd d:\FYP\backend
python -m pytest -v tests/
```

### Coverage Overview
- **`test_science.py`**:
  - `test_cpr_computation`: Verifies CPR ratio calculations and safe epsilon handling for zero-division.
  - `test_dop_computation`: Verifies Stokes vector purity and strict $[0, 1]$ bounds.
  - `test_hazard_score_bounds`: Verifies monotonic increase with slope/roughness and normalization.
  - `test_ice_volume_estimation_tiers`: Verifies 3-tier calculations and density conversions.
- **`test_rover.py`**:
  - `test_energy_step_model`: Validates simplified energy power consumption on slopes.
  - `test_rover_path_reachability`: Validates A* path finding from start to target.
  - `test_impassable_cliff_barrier_failure`: Validates PRD Section 40 requirement that impassable terrain gracefully returns `NO FEASIBLE PATH FOUND` rather than fabricating paths.
- **`test_pipeline.py`**:
  - `test_full_mission_pipeline_execution`: Runs complete end-to-end mission workflow across Shackleton, Shoemaker, and Faustini craters.
  - `test_experiments_suite_execution`: Runs all 4 research experiments and the 6-step ablation study.

## Frontend Build Verification
```powershell
cd d:\FYP\frontend
npm run build
```
Builds the production client bundle using Vite, validating all TypeScript contracts without errors.
