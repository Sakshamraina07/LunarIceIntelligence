"""
Mission Service: End-to-end scientific pipeline orchestrator.
Executes the full pipeline:
Crater Selection -> PSR Mapping -> Radar Analysis -> Ice Intelligence ->
Terrain Safety -> Landing Ranking -> Multi-Strategy Rover Planning -> Volume Estimation.

FIXED (this version):
  - Previously, `is_real` was determined ONLY by the global data_mode toggle
    (`data_mode == "REAL"`). This meant selecting a crater that genuinely has
    real Chandrayaan-2 data (e.g. Faustini, which has `is_real_data=True` in
    the catalog) would STILL silently generate fully synthetic demo data if
    the user hadn't also flipped the separate "Toggle Mode" button to REAL.
    The result looked identical to real data but was entirely fake — this
    was the root cause of "it still looks simulated even after picking the
    real crater."
  - Now, real data is used whenever EITHER the global toggle is set to REAL,
    OR the selected crater is flagged as having real data in the catalog.
    The actual data source used (`effective_data_mode`) is reported back in
    the payload, so the frontend badge always reflects what was ACTUALLY
    loaded, not just what the toggle happened to say.
"""

import cv2
import base64
import numpy as np
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.core.schemas import MissionState, CraterInfo
from app.demo.lunar_generator import CRATER_CATALOG, demo_generator
from app.modules.module_a_psr import analyze_psr
from app.modules.module_b_radar import analyze_dfsar_radar
from app.modules.module_c_ice import evaluate_ice_intelligence
from app.modules.module_d_terrain import analyze_terrain_safety
from app.modules.module_e_landing import select_landing_candidates
from app.modules.module_f_rover import plan_rover_path
from app.modules.module_g_volume import estimate_ice_volume
from app.core.provenance import create_provenance


def array_to_base64_png(arr: np.ndarray, colormap: Optional[int] = None) -> str:
    """
    Encodes 2D numpy raster to a web-optimized Base64 PNG image.
    """
    # Normalize to 0 - 255
    arr_min = float(np.min(arr))
    arr_max = float(np.max(arr))
    if arr_max > arr_min:
        norm = ((arr - arr_min) / (arr_max - arr_min) * 255.0).astype(np.uint8)
    else:
        norm = np.zeros_like(arr, dtype=np.uint8)

    if colormap is not None:
        colored = cv2.applyColorMap(norm, colormap)
    else:
        colored = cv2.cvtColor(norm, cv2.COLOR_GRAY2BGR)

    success, buffer = cv2.imencode('.png', colored)
    if not success:
        return ""
    return f"data:image/png;base64,{base64.b64encode(buffer).decode('utf-8')}"


class MissionPipelineService:
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get_available_craters(self) -> Dict[str, CraterInfo]:
        return CRATER_CATALOG

    def run_full_mission_pipeline(
        self,
        crater_id: str = "shackleton",
        data_mode: str = "DEMO",
        cpr_threshold: Optional[float] = None,
        dop_threshold: Optional[float] = None,
        ice_depth_m: Optional[float] = None,
        ice_fraction: Optional[float] = None,
        rover_algorithm: str = "A*"
    ) -> Dict[str, Any]:
        """
        Executes the entire end-to-end mission workflow and returns structured results
        along with base64 visual raster layers for the dashboard.
        """
        crater_info = CRATER_CATALOG.get(crater_id, CRATER_CATALOG["shackleton"])

        # ------------------------------------------------------------------
        # FIXED: is_real is no longer decided by the global toggle alone.
        # A crater explicitly flagged as having real data (is_real_data=True
        # in the catalog, e.g. Faustini) ALWAYS loads its real files,
        # regardless of the DEMO/REAL toggle state. The toggle still lets a
        # user force REAL-mode ingestion attempts on other craters (which
        # will fall back to generated sample files if no real disk data
        # exists for them yet — see create_sample_georeferenced_pradan_data).
        # ------------------------------------------------------------------
        crater_has_real_data = bool(getattr(crater_info, "is_real_data", False))
        is_real = (data_mode == "REAL") or crater_has_real_data
        # Robustness: a crater may be flagged real, but the raw raster files are
        # only present on the local workstation (the 9GB SAR set is not deployed).
        # If none of the real inputs exist on THIS host, transparently downgrade to
        # the DEMO generator instead of failing — the UI already labels this DEMO.
        _real_inputs_present = (
            Path(f"d:/FYP/data/pradan/dem/{crater_id}_lola_dem.tif").exists()
            or Path("d:/FYP/data/pradan/dem/real_dem.tif").exists()
            or (
                Path("d:/FYP/data/pradan/dfsar/cpr_real.tif").exists()
                and Path("d:/FYP/data/pradan/dfsar/dop_real.tif").exists()
            )
        )
        if is_real and not _real_inputs_present:
            is_real = False
        effective_data_mode = "REAL" if is_real else "DEMO"

        # Cache key includes the EFFECTIVE mode so a stale DEMO-mode cache
        # entry for a real-data crater can never be returned by mistake.
        cache_key = f"{crater_id}_{effective_data_mode}_{cpr_threshold}_{dop_threshold}_{ice_depth_m}_{ice_fraction}_{rover_algorithm}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Step 1: Environment Ingestion (Demo generator or Real PRADAN Ingestion Pipeline)
        cpr_real_path = Path("d:/FYP/data/pradan/dfsar/cpr_real.tif")
        dop_real_path = Path("d:/FYP/data/pradan/dfsar/dop_real.tif")
        dem_pradan_path = Path(f"d:/FYP/data/pradan/dem/{crater_id}_lola_dem.tif")
        if not dem_pradan_path.exists():
            dem_pradan_path = Path("d:/FYP/data/pradan/dem/real_dem.tif")

        dfsar_s0_path = Path(f"d:/FYP/data/pradan/dfsar/{crater_id}_dfsar_s0.tif")
        dfsar_s3_path = Path(f"d:/FYP/data/pradan/dfsar/{crater_id}_dfsar_s3.tif")
        ohrc_path = Path(f"d:/FYP/data/pradan/ohrc/{crater_id}_ohrc_pan.tif")

        # Track whether we actually managed to load real files on disk —
        # this can differ from `is_real` if the real files are missing,
        # in which case we transparently fall back to demo data and say so.
        actually_loaded_real = False

        if is_real:
            from app.ingestion.pradan_pipeline import (
                ensure_pradan_directories,
                read_raster_file,
                create_sample_georeferenced_pradan_data,
                process_real_dem,
                process_real_dfsar_stokes,
                extract_boulders_from_ohrc
            )
            ensure_pradan_directories()

            real_dem_available = dem_pradan_path.exists() or Path("d:/FYP/data/pradan/dem/real_dem.tif").exists()
            real_radar_available = cpr_real_path.exists() and dop_real_path.exists()

            if real_dem_available or real_radar_available:
                actually_loaded_real = True

            if not actually_loaded_real:
                raise ValueError(f"Real data not yet ingested for {crater_info.name} — coming soon.")

            # Proceed if we have real data

            dem_dict = process_real_dem(str(dem_pradan_path), pixel_scale_m=250.0)
            dem = dem_dict["dem"]
            pixel_scale_m = 250.0
            illumination = dem_dict["illumination"]
            psr_mask = dem_dict["psr_mask"]
            doubly_shadowed_mask = dem_dict["doubly_shadowed"]
            hillshade = dem_dict["hillshade"]

            if real_radar_available:
                cpr = read_raster_file(str(cpr_real_path))
                dop = read_raster_file(str(dop_real_path))
                if cpr.shape != dem.shape:
                    cpr = cv2.resize(cpr, (dem.shape[1], dem.shape[0]), interpolation=cv2.INTER_LINEAR)
                if dop.shape != dem.shape:
                    dop = cv2.resize(dop, (dem.shape[1], dem.shape[0]), interpolation=cv2.INTER_LINEAR)
            else:
                stokes_dict = process_real_dfsar_stokes(str(dfsar_s0_path), s3_path=str(dfsar_s3_path))
                cpr = stokes_dict["cpr"]
                dop = stokes_dict["dop"]

            boulder_risk = extract_boulders_from_ohrc(str(ohrc_path)) if ohrc_path.exists() else np.zeros_like(dem, dtype=np.float32)
        else:
            env = demo_generator.generate_crater_environment(crater_id)
            dem = env["dem"]
            pixel_scale_m = env["pixel_scale_m"]
            illumination = env["illumination"]
            psr_mask = env["psr_mask"]
            doubly_shadowed_mask = env["doubly_shadowed_mask"]
            cpr = env["cpr"]
            dop = env["dop"]
            boulder_risk = env["boulder_risk"]

        # If we requested real mode but genuinely had no real files at all
        # (neither DEM nor radar), be honest about it downstream: this run
        # is effectively still demo-quality data, even though `is_real` was
        # true. This prevents the UI from ever labeling pure fallback data
        # as "REAL DATA".
        if is_real and not actually_loaded_real:
            effective_data_mode = "DEMO"

        # Step 2: Module A - PSR & Doubly Shadowed Mapping
        psr_res, psr_rasters = analyze_psr(
            crater_id=crater_id,
            dem=dem,
            illumination=illumination,
            psr_mask=psr_mask,
            doubly_shadowed_mask=doubly_shadowed_mask,
            pixel_scale_m=pixel_scale_m,
            data_mode=effective_data_mode
        )

        # Step 3: Module B - DFSAR Radar Polarimetry (CPR & DOP)
        radar_res, radar_rasters = analyze_dfsar_radar(
            crater_id=crater_id,
            cpr=cpr,
            dop=dop,
            pixel_scale_m=pixel_scale_m,
            cpr_threshold=cpr_threshold,
            dop_threshold=dop_threshold,
            data_mode=effective_data_mode
        )

        if effective_data_mode == "REAL" and getattr(crater_info, "product_id", None):
            radar_res.data_source_tag = f"REAL DATA — Chandrayaan-2 SAR, Product ID: {crater_info.product_id}, Observed: {crater_info.observed_date}"
        else:
            radar_res.data_source_tag = "Simulated placeholder — pending real data"

        # Step 4: Module D - Terrain Safety & Hazard Scoring
        terrain_res, terrain_rasters = analyze_terrain_safety(
            crater_id=crater_id,
            dem=dem,
            boulder_risk=boulder_risk,
            pixel_scale_m=pixel_scale_m,
            data_mode=effective_data_mode
        )

        # Step 5: Module C - Ice Intelligence (Scientific Screening + ML)
        ice_res, ice_rasters = evaluate_ice_intelligence(
            crater_id=crater_id,
            cpr=cpr,
            dop=dop,
            slope_deg=terrain_rasters["slope_deg"],
            roughness=terrain_rasters["roughness"],
            illumination=illumination,
            psr_mask=psr_mask,
            doubly_shadowed_mask=doubly_shadowed_mask,
            pixel_scale_m=pixel_scale_m,
            cpr_threshold=cpr_threshold,
            dop_threshold=dop_threshold,
            data_mode=effective_data_mode
        )

        # Step 6: Module E - Landing Site Selection
        landing_sites, recommended_site = select_landing_candidates(
            crater_info=crater_info,
            dem=dem,
            slope_deg=terrain_rasters["slope_deg"],
            roughness=terrain_rasters["roughness"],
            hazard=terrain_rasters["hazard"],
            illumination=illumination,
            scientific_mask=ice_rasters["scientific_candidate_mask"],
            pixel_scale_m=pixel_scale_m
        )

        # Step 7: Target centroid for rover traverse (ensure target cell is traversable)
        cand_y, cand_x = np.where(ice_rasters["scientific_candidate_mask"])
        if len(cand_x) > 0:
            safe_cand = terrain_rasters["slope_deg"][cand_y, cand_x] < 15.0
            if np.any(safe_cand):
                valid_x = cand_x[safe_cand]
                valid_y = cand_y[safe_cand]
                cx, cy = np.mean(cand_x), np.mean(cand_y)
                dists = (valid_x - cx)**2 + (valid_y - cy)**2
                best_idx = int(np.argmin(dists))
                target_xy = (int(valid_x[best_idx]), int(valid_y[best_idx]))
            else:
                target_xy = (int(cand_x[0]), int(cand_y[0]))
        else:
            target_xy = (dem.shape[1] // 2, dem.shape[0] // 2)

        start_xy = (recommended_site.grid_x, recommended_site.grid_y)

        # Step 8: Module F - Multi-Strategy Rover Path Planning
        # Shortest
        route_shortest = plan_rover_path(
            dem=dem,
            slope_deg=terrain_rasters["slope_deg"],
            hazard=terrain_rasters["hazard"],
            illumination=illumination,
            scientific_mask=ice_rasters["scientific_candidate_mask"],
            ml_likelihood=ice_rasters["ml_likelihood"],
            start_xy=start_xy,
            target_xy=target_xy,
            strategy="Shortest",
            algorithm=rover_algorithm,
            pixel_scale_m=pixel_scale_m
        )

        # Safest
        route_safest = plan_rover_path(
            dem=dem,
            slope_deg=terrain_rasters["slope_deg"],
            hazard=terrain_rasters["hazard"],
            illumination=illumination,
            scientific_mask=ice_rasters["scientific_candidate_mask"],
            ml_likelihood=ice_rasters["ml_likelihood"],
            start_xy=start_xy,
            target_xy=target_xy,
            strategy="Safest",
            algorithm=rover_algorithm,
            pixel_scale_m=pixel_scale_m
        )

        # Science-Aware
        route_science = plan_rover_path(
            dem=dem,
            slope_deg=terrain_rasters["slope_deg"],
            hazard=terrain_rasters["hazard"],
            illumination=illumination,
            scientific_mask=ice_rasters["scientific_candidate_mask"],
            ml_likelihood=ice_rasters["ml_likelihood"],
            start_xy=start_xy,
            target_xy=target_xy,
            strategy="Science-Aware",
            algorithm=rover_algorithm,
            pixel_scale_m=pixel_scale_m
        )

        rover_routes = {
            "Shortest": route_shortest,
            "Safest": route_safest,
            "Science-Aware": route_science
        }

        # Step 9: Module G - Ice-Equivalent Volume Estimation
        volume_res = estimate_ice_volume(
            candidate_area_km2=ice_res.scientific_candidate_area_km2,
            crater_id=crater_id,
            depth_expected_m=ice_depth_m,
            fraction_expected=ice_fraction,
            data_mode=effective_data_mode
        )

        # Step 10: Generate Base64 Visual Layers for GIS Dashboard
        raster_layers = {
            "hillshade": array_to_base64_png(psr_rasters["hillshade"]),
            "dem_elevation": array_to_base64_png(dem, cv2.COLORMAP_VIRIDIS),
            "illumination": array_to_base64_png(illumination, cv2.COLORMAP_HOT),
            "psr_mask": array_to_base64_png(psr_mask.astype(float), cv2.COLORMAP_BONE),
            "cpr_heatmap": array_to_base64_png(cpr, cv2.COLORMAP_TURBO),
            "dop_heatmap": array_to_base64_png(dop, cv2.COLORMAP_CIVIDIS),
            "ml_likelihood": array_to_base64_png(ice_rasters["ml_likelihood"], cv2.COLORMAP_MAGMA),
            "hazard_map": array_to_base64_png(terrain_rasters["hazard"], cv2.COLORMAP_JET)
        }

        payload = {
            "selected_crater": crater_info,
            # Report the EFFECTIVE mode (what was actually loaded), not the
            # raw requested/toggle mode — this is what the frontend badge
            # should trust.
            "data_mode": effective_data_mode,
            "psr": psr_res,
            "radar": radar_res,
            "ice": ice_res,
            "terrain": terrain_res,
            "landing_sites": landing_sites,
            "recommended_landing_site": recommended_site,
            "rover_routes": rover_routes,
            "volume": volume_res,
            "raster_layers": raster_layers,
            "grid_dimensions": {"width": dem.shape[1], "height": dem.shape[0], "pixel_scale_m": pixel_scale_m},
            "target_coordinates": {"x": target_xy[0], "y": target_xy[1]},
            "generated_at": datetime.now(timezone.utc).isoformat()
        }

        self._cache[cache_key] = payload
        return payload


mission_orchestrator = MissionPipelineService()