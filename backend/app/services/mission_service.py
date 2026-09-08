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
import json
import base64
import numpy as np
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.core.schemas import MissionState, CraterInfo
from app.core.exceptions import UnknownCraterError
from app.demo.lunar_generator import CRATER_CATALOG, demo_generator_enabled
from app.ingestion.real_data_gate import (
    PRADAN_ROOT,
    RealDataStatus,
    assert_no_shared_real_rasters,
    real_data_status,
)
from app.modules.module_a_psr import analyze_psr
from app.modules.module_b_radar import analyze_dfsar_radar
from app.modules.module_c_screen import screen_ice_criteria
from app.modules.module_d_terrain import analyze_terrain_safety
from app.modules.module_e_landing import select_landing_candidates
from app.modules.module_f_rover import plan_rover_path
from app.modules.module_g_volume import estimate_ice_volume
from app.core.provenance import create_provenance


class HorizonPSRUnavailable(RuntimeError):
    """This host cannot say where the shadow is, and will not guess.

    The same shape as ReportArtifactsMissing (G16): absence REFUSES, it does not
    degrade. A served host without the horizon product could substitute the
    brightness proxy this replaced and produce a plausible PSR mask -- which is
    precisely the np.zeros_like mistake the whole project is built against, and
    is what happened here for as long as the proxy existed.
    """


def _read_horizon_psr(frame, shape=None):
    """The horizon-derived PSR, projected onto this frame -- or a refusal.

    ONE PSR SOURCE. build_analysis.py reads `load_horizon(...).to_frame(...)` for
    the verdict; the PDF renders what that produced; this reads the same product
    through the same call. Nothing here recomputes shadow, so there is no second
    implementation to drift.

    Returns (illumination_fraction, psr_mask, doubly_shadowed, summary) at the
    frame's NATIVE resolution, with the summary carrying the authoritative
    areas.
    """
    from app.ingestion.horizon_frame import load_horizon

    lola_dir = PRADAN_ROOT / "lola"
    try:
        hp = load_horizon(lola_dir)
    except FileNotFoundError as exc:
        raise HorizonPSRUnavailable(
            f"No horizon product on this host ({exc}). Permanent shadow is a "
            f"horizon computation over the full LOLA polar array (METHODS 5); "
            f"without it this host cannot say where the shadow is. It does not "
            f"substitute a brightness proxy -- METHODS 5.1 deleted those, and "
            f"METHODS 5.3 measures the capped-elevation model wrong by up to "
            f"4.4x. Run: python backend/scripts/compute_horizon.py"
        ) from exc

    if frame is None:
        raise HorizonPSRUnavailable(
            "The SAR frame geometry is unreadable, so the horizon product cannot "
            "be projected onto it. A mask placed without geometry would be in the "
            "wrong place, which is worse than an absent one."
        )

    # PROJECT AT THE FRAME'S NATIVE SHAPE, NOT THE DISPLAY GRID.
    #
    # to_frame builds `rows = arange(lines)` and feeds them to
    # frame.pixel_to_xy, so `shape` is FRAME PIXEL INDICES, not an arbitrary
    # output grid. Passing the API's 100x100 sampled a 100x100-pixel CORNER of a
    # 2258x6618 frame -- about 2.5 km of it -- and reported 8704.56 km2 of
    # shadow against the analysis artifact's 2043.22, with a mean illumination
    # of exactly 0.0. The refusal path was right and the projection was wrong,
    # which is the more dangerous half to get wrong because it answers.
    native_shape = tuple(int(v) for v in frame.shape)
    projected = hp.to_frame(frame, native_shape)
    illum = projected["illumination_fraction"]
    psr = projected["psr_mask"]
    dbl = projected.get("doubly_shadowed")

    # The area reduction is build_analysis.py's, line for line: a pixel count
    # times the frame's own cell area, at NATIVE resolution. It is not a second
    # implementation of shadow -- shadow was read above -- and computing it at
    # the display grid instead would quantise a measured area to 564 x 1654 m
    # cells and then call it the same number.
    sy, sx = float(frame.pixel_size_m[1]), float(frame.pixel_size_m[0])
    cell_km2 = (sy / 1000.0) * (sx / 1000.0)
    finite = np.isfinite(illum)
    summary = {
        "psr_px": int(psr.sum()),
        "psr_km2": float(psr.sum() * cell_km2),
        "total_px": int(psr.size),
        "total_km2": float(psr.size * cell_km2),
        "psr_fraction": float(psr.mean()),
        "mean_illumination_fraction": float(np.nanmean(illum)) if finite.any() else None,
        "doubly_px": int(dbl.sum()) if dbl is not None else None,
        "doubly_km2": float(dbl.sum() * cell_km2) if dbl is not None else None,
        "native_shape": native_shape,
        "cell_km2": cell_km2,
        "source": "horizon product via load_horizon().to_frame() — the same "
                  "product and the same call build_analysis.py reads",
    }
    return illum, psr, dbl, summary


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

        # BEFORE the eligibility gate, deliberately. An id that is not in the
        # catalogue is not an un-ingested crater -- answering NOT_INGESTED for
        # it asserts that such a crater exists and merely lacks a product, which
        # is a claim about the Moon rather than about this repository. Unknown
        # is unknown, and the API turns this into a 404.
        if crater_info is None:
            raise UnknownCraterError(crater_id, sorted(CRATER_CATALOG))

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

        dfsar_s0_path = PRADAN_ROOT / "dfsar" / f"{crater_id}_dfsar_s0.tif"
        dfsar_s3_path = PRADAN_ROOT / "dfsar" / f"{crater_id}_dfsar_s3.tif"
        ohrc_path = PRADAN_ROOT / "ohrc" / f"{crater_id}_ohrc_pan.tif"

        if is_real:
            from app.ingestion.pradan_pipeline import (
                ensure_pradan_directories,
                read_raster_file,
                process_real_dem,
                process_real_dfsar_stokes,
                extract_boulders_from_ohrc
            )
            ensure_pradan_directories()

            # There is no `real_radar_available` flag any more. It was assigned a
            # literal True, which made the `else:` branch beneath it -- the one
            # that would have derived CPR and DOP from the Stokes products --
            # unreachable code that nonetheless read as a working alternative
            # path. Reaching this line means the gate found all three rasters,
            # so "real but nothing loaded" is not a state that can occur. The
            # Stokes derivation returns in Phase 5, wired to the complex sli
            # products rather than to a dead branch.

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
                    meta_path = PRADAN_ROOT / "dfsar" / "metadata_real.json"
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
                # FATAL, not a caveat. This used to fall back to (250.0, 250.0)
                # and carry on, so the run still published areas in km2, volumes
                # in m3 and a traverse in km -- every one of them a placeholder
                # squared -- with nothing but a string in `grid_dimensions` to
                # say so. A number that is not calibrated must not be computed
                # at all, let alone served. The crater degrades to NOT_INGESTED,
                # which is the honest state: its georeferencing is unreadable.
                return self._not_ingested_payload(
                    crater_id, crater_info,
                    status.with_failure(
                        "SPACING_UNRESOLVED",
                        "Ground spacing could not be resolved. Neither the DEM's GeoTIFF tags nor "
                        "dfsar/metadata_real.json supplied a frame, so there is no metres-per-pixel "
                        "for this product. Every area, distance and slope would be uncalibrated, so "
                        "none is computed. Re-run backend/scripts/process_real_sar_pipeline.py to "
                        "regenerate dfsar/metadata_real.json.",
                    ),
                    data_mode,
                )

            # SCORE ON THE NATIVE FRAME WHEN IT IS AVAILABLE.
            #
            # data/pradan/dem/*_lola_dem.tif is a 2048^2 raster: 27.56 m per line
            # but 80.79 m per sample, so a 5x5 roughness window on it spans ~404 m
            # and measures regional relief. native/dem_native.tif is the same
            # extent at its true 2258 x 6618 / 25 m posts. Terrain is scored there
            # and the bounded fields are area-averaged onto the serving grid, so
            # the API and the static analysis compute the same quantity.
            # FROM THE GATE, never constructed here. real_data_gate is the
            # pipeline's only file resolver, and reading a path it did not
            # resolve is the exact hole this restores.
            _native_dem = status.inputs.get("dem_native")
            if _native_dem and Path(_native_dem).is_file():
                # READ, NOT TYPED. A literal 25.0 here would be the fourth
                # spacing constant in this project to go stale behind a rename;
                # the ingest already records what grid it wrote onto.
                _side = PRADAN_ROOT / "lola" / "ldem_frame_25m.provenance.json"
                try:
                    _px = float(json.loads(_side.read_text(encoding="utf-8"))
                                ["output_metres_per_pixel"])
                except (OSError, ValueError, KeyError, TypeError):
                    _px = float(frame.pixel_size_m[0]) if frame is not None else 25.0
                _terrain_src, _src_spacing = str(_native_dem), (_px, _px)
            else:
                # No silent 25 m: derive the file's real spacing from the frame.
                _terrain_src = str(dem_pradan_path)
                _probe = read_raster_file(_terrain_src)
                _src_spacing = (frame.shape[0] * frame.pixel_size_m[1] / _probe.shape[0],
                                frame.shape[1] * frame.pixel_size_m[0] / _probe.shape[1])                     if frame is not None else (25.0, 25.0)
            dem_dict = process_real_dem(_terrain_src, spacing_m=spacing_tuple,
                                        source_spacing_m=_src_spacing)
            dem = dem_dict["dem"]
            spacing_m = dem_dict["spacing_m"]
            hillshade = dem_dict["hillshade"]

            # ONE PSR SOURCE, READ AND NOT RECOMPUTED.
            #
            # This used to take `illumination`, `psr_mask` and `doubly_shadowed`
            # straight from process_real_dem, which derived them from a BRIGHTNESS
            # THRESHOLD on a hillshade at a capped 1.5 deg solar altitude. METHODS
            # 5.3 measures that model wrong by up to 4.4x -- solar elevation at
            # latitude phi reaches 1.54 + (90 - |phi|), which is 6.71 deg at this
            # frame's edge -- and METHODS 5.1 had already deleted both brightness
            # proxies from every other path. This one survived because it sits
            # behind an API nobody reads.
            #
            # It is not adapted, it is REPLACED. An adapter is how the two paths
            # drifted in the PDF (METHODS 0, third pattern): a second
            # implementation of a transform that already exists agrees with the
            # first until it does not. The horizon product IS the PSR source --
            # the same one build_analysis reads for the verdict, the same one the
            # report renders -- and this reads it or it refuses.
            (illum_native, psr_native, dbl_native,
             psr_summary) = _read_horizon_psr(frame, None)

            # The masks are DOWNSAMPLED FOR DISPLAY ONLY, nearest-neighbour,
            # never bilinear -- an interpolated boolean invents half-shadowed
            # pixels (METHODS 5.10). Every NUMBER comes from `psr_summary`, which
            # was reduced at native resolution, so nothing a reader sees is a
            # statistic of a resampled mask.
            _th, _tw = dem.shape
            illumination = cv2.resize(np.nan_to_num(illum_native, nan=0.0),
                                      (_tw, _th), interpolation=cv2.INTER_AREA)
            psr_mask = cv2.resize(psr_native.astype(np.uint8), (_tw, _th),
                                  interpolation=cv2.INTER_NEAREST).astype(bool)
            doubly_shadowed_mask = (
                cv2.resize(dbl_native.astype(np.uint8), (_tw, _th),
                           interpolation=cv2.INTER_NEAREST).astype(bool)
                if dbl_native is not None else np.zeros_like(psr_mask))

            cpr = read_raster_file(str(cpr_real_path))
            dop = read_raster_file(str(dop_real_path))
            if cpr.shape != dem.shape:
                cpr = cv2.resize(cpr, (dem.shape[1], dem.shape[0]), interpolation=cv2.INTER_LINEAR)
            if dop.shape != dem.shape:
                dop = cv2.resize(dop, (dem.shape[1], dem.shape[0]), interpolation=cv2.INTER_LINEAR)

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
                # `None`, not `np.zeros_like(dem)`. The zeros array was passed
                # downstream where it was indistinguishable from a measured
                # boulder-free surface; every consumer already branches on
                # `boulder_available`, so there is nothing for it to be.
                boulder_risk = None
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
            psr_summary = None  # generated grid; nothing authoritative to read
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
            data_mode=effective_data_mode,
            # REAL runs hand it the native-resolution reduction so the served
            # numbers are the analysis artifact's numbers, not statistics of a
            # display-sized mask. DEMO passes None and analyze_psr computes from
            # the generated grid, which is the only thing there is there.
            authoritative=psr_summary,
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
            data_mode=effective_data_mode,
            # Scored at 25 m and area-averaged onto this grid by
            # process_real_dem. Passing them stops this module re-deriving
            # terrain from a DEM that has already been downsampled.
            prescored={k: dem_dict[k] for k in
                       ("slope_deg", "aspect_deg", "roughness", "hazard")
                       if k in dem_dict},
        )

        # Step 5: Module C - the measured CRITERIA SCREEN.
        #
        # Was evaluate_ice_intelligence(), which also returned a Random Forest
        # P(ice). That classifier is unwired: it was fitted to np.random.uniform
        # labels whose positive class (CPR 1.05-2.5) lies outside this product's
        # achievable range, so every probability was an extrapolation from
        # fabricated examples. See module_c_ice.py's header.
        #
        # The psr_mask term is gone from the candidate mask too. It came from
        # the illumination proxy, which darkens 77 % of the frame, so ANDing it
        # in discriminated nothing while making a measured area partly modelled.
        ice_res, ice_rasters = screen_ice_criteria(
            crater_id=crater_id,
            cpr=cpr,
            dop=dop,
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
            grid_max=float(dem.shape[1]),
            data_mode=effective_data_mode
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
            start_xy=start_xy,
            target_xy=target_xy,
            spacing_m=spacing_m,
            data_mode=effective_data_mode,
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
            start_xy=start_xy,
            target_xy=target_xy,
            spacing_m=spacing_m,
            data_mode=effective_data_mode,
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
            start_xy=start_xy,
            target_xy=target_xy,
            spacing_m=spacing_m,
            data_mode=effective_data_mode,
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