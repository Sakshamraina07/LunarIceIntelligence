"""
Mission Service: End-to-end scientific pipeline orchestrator.
Executes the full pipeline:
Crater Selection -> PSR Mapping -> Radar Analysis -> Ice Intelligence ->
Terrain Safety -> Landing Ranking -> Multi-Strategy Rover Planning -> Volume Estimation.

FIXED (this version):
  - Eligibility for a REAL run is decided by PROVENANCE, not by the filesystem.
    The previous gate asked whether a *filename* existed:

        Path(f"data/pradan/dem/{crater_id}_lola_dem.tif").exists()

    Four DEMs on disk share one digest (sha256 a5e4ed4b...): faustini's crop,
    `real_dem.tif`, `ch2_sar_dem.tif`, and `shackleton_lola_dem.tif`, which is a
    byte copy of faustini's. Under the filename test Shackleton passed as REAL
    and served Faustini's terrain and Faustini's radar swath under a MEASURED
    mark — strictly worse than the old seeded fallback, because the fallback at
    least labelled itself. `real_data_gate.real_data_status()` now requires the
    catalogue to carry `is_real_data=True` AND a PDS4 `product_id`, and
    `assert_no_shared_real_rasters()` runs at construction as a hard failure.
  - A crater that fails the gate gets `_not_ingested_payload()`: HTTP 200, a
    `status` field, and NO numeric fields at all. Not zeros — zeros are a
    measurement claim, and the seeded fallback that used to fill this case
    served `scientific_screening_status: "PASS"` with
    `ml_ice_likelihood_mean: 0.96`, the best-looking numbers in the app.
  - The seeded generator is reachable only when
    `LUNAR_ICE_ALLOW_DEMO_GENERATOR=1`, which `backend/conftest.py` sets and no
    serving path does. `tests/test_pipeline.py` therefore still drives
    shackleton / shoemaker / faustini end to end; a request to the server for an
    un-ingested crater cannot.
"""

import cv2
import base64
import numpy as np
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.core.schemas import MissionState, CraterInfo
from app.demo.lunar_generator import CRATER_CATALOG, demo_generator_enabled
from app.ingestion.real_data_gate import (
    RealDataStatus,
    assert_no_shared_real_rasters,
    real_data_status,
)
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
        # Armed at construction, not per request: a catalogue in which two
        # craters marked REAL resolve to the same bytes must stop the process,
        # not serve one good response and then a mislabelled one. Raises
        # SystemExit, same zero tolerance as build_analysis.assert_dem_is_lola().
        self._raster_identity = assert_no_shared_real_rasters(CRATER_CATALOG)

    def get_available_craters(self) -> Dict[str, CraterInfo]:
        return CRATER_CATALOG

    def _not_ingested_payload(
        self,
        crater_id: str,
        crater_info: Optional[CraterInfo],
        status: RealDataStatus,
        requested_data_mode: str,
    ) -> Dict[str, Any]:
        """The absent state, in a deliberately different SHAPE.

        There is no `psr`, `radar`, `ice`, `terrain`, `landing_sites`,
        `rover_routes`, `volume` or `raster_layers` key here — not those keys
        holding zeros. A zero is a measurement claim ("we looked and found
        none"); a missing key cannot be plotted, summed or averaged by accident,
        and a frontend that reaches for one fails loudly instead of drawing
        `0.00 km2` under a confident heading.

        `selected_crater` survives because crater names, centres and diameters
        are published IAU/USGS facts, not measurements of ours. The API needs
        them to name the crater it is declining to analyse.
        """
        return {
            "status": "NOT_INGESTED",
            "data_mode": "NOT_INGESTED",
            "crater_id": crater_id,
            "selected_crater": crater_info,
            "requested_data_mode": requested_data_mode,
            "gate": status.as_payload(),
            "raster_identity_check": self._raster_identity,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def run_full_mission_pipeline(
        self,
        crater_id: str = "shackleton",
        data_mode: str = "REAL",
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
        crater_info = CRATER_CATALOG.get(crater_id)

        # ------------------------------------------------------------------
        # The gate. Provenance decides, and `data_mode` no longer votes.
        #
        # The old line was `is_real = (data_mode == "REAL") or crater_has_real_data`,
        # which let a query string promote a crater the catalogue does not vouch
        # for; the filename test underneath it then found a raster with the right
        # name and let it through. Both are gone. `real_data_status()` reads
        # `is_real_data` + `product_id` from CRATER_CATALOG, and a crater that
        # fails cannot be argued into a REAL run by any caller.
        # ------------------------------------------------------------------
        status = real_data_status(crater_id, crater_info)

        if not status.eligible and not demo_generator_enabled():
            # The serving path. No numbers, no seeded substitute.
            return self._not_ingested_payload(crater_id, crater_info, status, data_mode)

        if crater_info is None:
            crater_info = CRATER_CATALOG["shackleton"]

        # Past this point `demo_generator_enabled()` is the only way a
        # non-eligible crater can still be running, and that flag is set by
        # backend/conftest.py alone (see app/demo/lunar_generator.py). Under
        # pytest the seeded branch below keeps tests/test_pipeline.py driving
        # shackleton / shoemaker / faustini through modules A-G.
        is_real = status.eligible
        effective_data_mode = "REAL" if is_real else "DEMO"

        # Cache key includes the EFFECTIVE mode so a stale DEMO-mode cache
        # entry for a real-data crater can never be returned by mistake.
        cache_key = f"{crater_id}_{effective_data_mode}_{cpr_threshold}_{dop_threshold}_{ice_depth_m}_{ice_fraction}_{rover_algorithm}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Step 1: Environment ingestion. One resolver, and it is the gate's.
        #
        # `status.inputs` holds the paths real_data_status() already confirmed on
        # disk for THIS crater, so the pipeline cannot reach for a different file
        # than the one that was vetted. The old `if not dem_pradan_path.exists():
        # dem_pradan_path = .../real_dem.tif` fallback is deleted: `real_dem.tif`
        # is one of the four files sharing digest a5e4ed4b..., and substituting it
        # is precisely how a crater ended up served another crater's terrain.
        if is_real:
            dem_pradan_path = Path(status.inputs["dem"])
            cpr_real_path = Path(status.inputs["cpr"])
            dop_real_path = Path(status.inputs["dop"])
        else:
            dem_pradan_path = cpr_real_path = dop_real_path = None

        dfsar_s0_path = Path(f"d:/FYP/data/pradan/dfsar/{crater_id}_dfsar_s0.tif")
        dfsar_s3_path = Path(f"d:/FYP/data/pradan/dfsar/{crater_id}_dfsar_s3.tif")
        ohrc_path = Path(f"d:/FYP/data/pradan/ohrc/{crater_id}_ohrc_pan.tif")

        if is_real:
            from app.ingestion.pradan_pipeline import (
                ensure_pradan_directories,
                read_raster_file,
                process_real_dem,
                process_real_dfsar_stokes,
                extract_boulders_from_ohrc
            )
            ensure_pradan_directories()

            # No availability re-test and no ValueError branch here any more:
            # reaching this line means the gate found all three rasters, so
            # "real but nothing loaded" is not a state that can occur.
            real_radar_available = True

            # Real spacing comes from the frame's own georeferencing, not a
            # constant. Two sources, in order of directness:
            #   1. the DEM's own GeoTIFF tags, if it has any;
            #   2. dfsar/metadata_real.json, whose geodetic_frame block was
            #      written by process_real_sar_pipeline.py straight from the
            #      source product's GeoTIFF tags and PDS4 label.
            # In practice (2) is the one that fires: every raster this project
            # writes goes out through plain tifffile with no geokeys, so (1)
            # raises on all of them. Both paths are wrapped because an
            # unreadable frame must degrade honestly, not 500 the endpoint.
            frame = None
            frame_source = "none"
            try:
                from app.ingestion.sar_geometry import (
                    frame_from_geodetic_metadata,
                    read_geotiff_frame,
                )
                try:
                    frame = read_geotiff_frame(str(dem_pradan_path))
                    frame_source = f"geotiff-tags:{dem_pradan_path.name}"
                except Exception:
                    meta_path = Path("d:/FYP/data/pradan/dfsar/metadata_real.json")
                    if meta_path.exists():
                        frame = frame_from_geodetic_metadata(meta_path)
                        frame_source = "metadata_real.json:geodetic_frame"
            except Exception:
                frame = None
                frame_source = "none"

            if frame is not None:
                # (564.5, 1654.5) m for the 100x100 mission grid: the real frame
                # extent (56.45 x 165.45 km) divided by the target grid, per axis.
                spacing_tuple = frame.metres_per_pixel((100, 100))
                spacing_absent_reason = None
            else:
                # No georeferencing reachable. Do not invent a spacing: say so.
                # The grid is still 100x100 cells, but every km, km2 and slope
                # derived from it is uncalibrated, and the payload says which.
                spacing_tuple = (250.0, 250.0)
                spacing_absent_reason = (
                    "Ground spacing is UNCALIBRATED. Neither the DEM's GeoTIFF "
                    "tags nor dfsar/metadata_real.json could supply the frame, "
                    "so 250 m per axis is a placeholder, not a measurement. "
                    "Every distance, area and slope on this run is therefore "
                    "uncalibrated and must not be quoted."
                )

            dem_dict = process_real_dem(str(dem_pradan_path), spacing_m=spacing_tuple)
            dem = dem_dict["dem"]
            spacing_m = dem_dict["spacing_m"]
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

            # Boulder risk is ABSENT, not zero, when there is no OHRC product.
            #
            # The previous `np.zeros_like(dem)` fallback made "no optical imagery
            # was ever acquired here" indistinguishable from "this terrain was
            # imaged and found to be free of boulders". Those are different
            # facts and the hazard map must be able to say which. Zero is a
            # measurement claim; absence is not. Downstream, boulder_available
            # False means the boulder weight is dropped from the hazard blend
            # rather than silently contributing a perfect score.
            boulder_available = ohrc_path.exists()
            if boulder_available:
                boulder_risk = extract_boulders_from_ohrc(str(ohrc_path))
                boulder_absent_reason = None
            else:
                boulder_risk = np.zeros_like(dem, dtype=np.float32)
                boulder_absent_reason = (
                    f"No OHRC product on disk for {crater_id}. Boulder risk is "
                    "UNMEASURED, not zero: the hazard score below is the "
                    "slope-and-roughness part only, renormalised, and no claim "
                    "is made about rocks at this site."
                )
        else:
            # PYTEST ONLY. Unreachable on a serving path: the gate above already
            # returned _not_ingested_payload() unless LUNAR_ICE_ALLOW_DEMO_GENERATOR=1,
            # and generate_crater_environment() re-checks the same flag itself.
            from app.demo.lunar_generator import demo_generator
            env = demo_generator.generate_crater_environment(crater_id)
            dem = env["dem"]
            # Demo grid is isotropic by construction, so the tuple is the scalar twice.
            spacing_m = (float(env["pixel_scale_m"]), float(env["pixel_scale_m"]))
            frame = None
            frame_source = "demo-generator (isotropic by construction)"
            spacing_absent_reason = None
            illumination = env["illumination"]
            psr_mask = env["psr_mask"]
            doubly_shadowed_mask = env["doubly_shadowed_mask"]
            cpr = env["cpr"]
            dop = env["dop"]
            boulder_risk = env["boulder_risk"]
            boulder_available = True
            boulder_absent_reason = None

        # `effective_data_mode` needs no post-hoc downgrade any more. It was set
        # from `status.eligible` before any file was opened, and the branch above
        # cannot change which of the two ran, so the label and the data source
        # cannot disagree.

        # Step 2: Module A - PSR & Doubly Shadowed Mapping
        psr_res, psr_rasters = analyze_psr(
            crater_id=crater_id,
            dem=dem,
            illumination=illumination,
            psr_mask=psr_mask,
            doubly_shadowed_mask=doubly_shadowed_mask,
            spacing_m=spacing_m,
            data_mode=effective_data_mode
        )

        # Step 3: Module B - DFSAR Radar Polarimetry (CPR & DOP)
        radar_res, radar_rasters = analyze_dfsar_radar(
            crater_id=crater_id,
            cpr=cpr,
            dop=dop,
            spacing_m=spacing_m,
            cpr_threshold=cpr_threshold,
            dop_threshold=dop_threshold,
            data_mode=effective_data_mode
        )

        if effective_data_mode == "REAL" and getattr(crater_info, "product_id", None):
            radar_res.data_source_tag = f"REAL DATA — Chandrayaan-2 SAR, Product ID: {crater_info.product_id}, Observed: {crater_info.observed_date}"
        else:
            radar_res.data_source_tag = "Simulated placeholder — pending real data"

        # Step 4: Module D - Terrain Safety & Hazard Scoring
        # w_boulder=0.0 when there is no OHRC product: compute_hazard_score
        # divides by (w1+w2+w3), so zeroing the weight renormalises the blend
        # over slope and roughness instead of feeding it an unmeasured 0.0 that
        # would read as "no rocks here" and pull every hazard score down.
        terrain_res, terrain_rasters = analyze_terrain_safety(
            crater_id=crater_id,
            dem=dem,
            boulder_risk=boulder_risk,
            spacing_m=spacing_m,
            w_boulder=None if boulder_available else 0.0,
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
            spacing_m=spacing_m,
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
            spacing_m=spacing_m,
            # With a real georeferenced frame, site lat/lon is the exact inverse
            # polar-stereographic transform rather than a flat degrees-per-metre
            # guess applied to both axes.
            frame=frame,
            grid_max=float(dem.shape[1])
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
            roughness=terrain_rasters["roughness"],
            hazard=terrain_rasters["hazard"],
            illumination=illumination,
            scientific_mask=ice_rasters["scientific_candidate_mask"],
            ml_likelihood=ice_rasters["ml_likelihood"],
            start_xy=start_xy,
            target_xy=target_xy,
            spacing_m=spacing_m,
            strategy="Shortest",
            algorithm=rover_algorithm
        )

        # Safest
        route_safest = plan_rover_path(
            dem=dem,
            slope_deg=terrain_rasters["slope_deg"],
            roughness=terrain_rasters["roughness"],
            hazard=terrain_rasters["hazard"],
            illumination=illumination,
            scientific_mask=ice_rasters["scientific_candidate_mask"],
            ml_likelihood=ice_rasters["ml_likelihood"],
            start_xy=start_xy,
            target_xy=target_xy,
            spacing_m=spacing_m,
            strategy="Safest",
            algorithm=rover_algorithm
        )

        # Science-Aware
        route_science = plan_rover_path(
            dem=dem,
            slope_deg=terrain_rasters["slope_deg"],
            roughness=terrain_rasters["roughness"],
            hazard=terrain_rasters["hazard"],
            illumination=illumination,
            scientific_mask=ice_rasters["scientific_candidate_mask"],
            ml_likelihood=ice_rasters["ml_likelihood"],
            start_xy=start_xy,
            target_xy=target_xy,
            spacing_m=spacing_m,
            strategy="Science-Aware",
            algorithm=rover_algorithm
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
            # Discriminator. The absent state uses the same key with
            # "NOT_INGESTED" and omits every numeric section, so a consumer
            # branches on one field rather than probing for missing keys.
            "status": "OK",
            "selected_crater": crater_info,
            # Report the EFFECTIVE mode (what was actually loaded), not the
            # raw requested/toggle mode — this is what the frontend badge
            # should trust.
            "data_mode": effective_data_mode,
            # Why this run was allowed to be REAL, served rather than merely
            # printed, so the claim is auditable from the response itself.
            "gate": {
                "eligible": status.eligible,
                "reason": status.reason,
                "product_id": status.product_id,
                "resolved_inputs": dict(status.inputs),
            },
            "raster_identity_check": self._raster_identity,
            "psr": psr_res,
            "radar": radar_res,
            "ice": ice_res,
            "terrain": terrain_res,
            "landing_sites": landing_sites,
            "recommended_landing_site": recommended_site,
            "rover_routes": rover_routes,
            "volume": volume_res,
            "raster_layers": raster_layers,
            # Spacing is per-axis. `pixel_scale_m` is kept for the older
            # GISMapViewer readout and is the LINE spacing only; anything that
            # needs a real ground distance must use metres_per_line /
            # metres_per_sample, because on the live frame they differ by ~2.9x.
            "grid_dimensions": {
                "width": dem.shape[1],
                "height": dem.shape[0],
                "pixel_scale_m": float(spacing_m[0]),
                "metres_per_line": float(spacing_m[0]),
                "metres_per_sample": float(spacing_m[1]),
                "spacing_is_anisotropic": bool(abs(spacing_m[0] - spacing_m[1]) > 1e-6),
                "spacing_source": frame_source,
                "spacing_absent_reason": spacing_absent_reason
            },
            "target_coordinates": {"x": target_xy[0], "y": target_xy[1]},
            # Absent and zero are different facts. The UI must be able to say
            # "boulder risk was never measured here" rather than implying the
            # terrain was imaged and found clear.
            "boulder_risk_available": boulder_available,
            "boulder_risk_absent_reason": boulder_absent_reason,
            "hazard_components": (
                ["slope", "roughness", "boulder"] if boulder_available
                else ["slope", "roughness"]
            ),
            "generated_at": datetime.now(timezone.utc).isoformat()
        }

        self._cache[cache_key] = payload
        return payload


mission_orchestrator = MissionPipelineService()