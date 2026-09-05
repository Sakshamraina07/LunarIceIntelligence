"""
MODULE E: Multi-Criteria Landing-Site Selection.
PRD Compliance: Generates multiple candidate landing locations along accessible rim plateaus,
evaluates safety, solar illumination and traverse distance to candidate ice targets.

The five positions are HARDCODED GRID OFFSETS scored after the fact; no search
runs here. That is stated in every site's provenance block and in its rationale,
and PRD Phase 3 replaces it with a per-pixel search over the native frame.

There is no "scientific value" term any more. The field of that name held a
decreasing function of the traverse distance and nothing else, and it was then
blended into the composite score beside the distance penalty it duplicated.
"""

import numpy as np
from typing import List, Dict, Any, Tuple, Optional, TYPE_CHECKING
from app.core.config import settings
from app.core.schemas import CandidateLandingSite, CraterInfo
from app.core.provenance import create_provenance

if TYPE_CHECKING:  # import only for type checkers — keeps app.modules free of an ingestion import at runtime
    from app.ingestion.sar_geometry import SarFrame

# Mean lunar radius (m), IAU. One degree of latitude on a sphere of this radius.
_M_PER_DEG_LAT = np.pi * 1737400.0 / 180.0


def select_landing_candidates(
    crater_info: CraterInfo,
    dem: np.ndarray,
    slope_deg: np.ndarray,
    roughness: np.ndarray,
    hazard: np.ndarray,
    illumination: np.ndarray,
    scientific_mask: np.ndarray,
    spacing_m: Tuple[float, float],
    frame: Optional["SarFrame"] = None,
    grid_max: float = 100.0,
    w_safety: Optional[float] = None,
    w_illum: Optional[float] = None,
    w_sci: Optional[float] = None,
    w_dist: Optional[float] = None,
    *,
    data_mode: str,
) -> Tuple[List[CandidateLandingSite], CandidateLandingSite]:
    """
    Identifies and ranks candidate landing sites outside dangerous inner slopes.

    `spacing_m` is (metres_per_line, metres_per_sample) for this grid, so a
    distance in cells becomes a distance in metres per axis rather than through
    one shared scalar.

    `frame`, when supplied, is the SarFrame the grid was resampled from; site
    lat/lon then comes from `frame.grid_to_latlon` (the real south-polar
    stereographic inverse). Without a frame the fallback is an explicit
    spherical approximation about the crater centre — still per-axis, with the
    longitude degree shrunk by cos(lat). The code this replaces divided both
    axes by the same 30370.0 m/deg, which is only correct for latitude and, at
    -89 deg, understated the longitude offset by a factor of about 57.
    """
    ws = w_safety if w_safety is not None else settings.WEIGHT_LANDING_SAFETY
    wi = w_illum if w_illum is not None else settings.WEIGHT_LANDING_ILLUM
    wsc = w_sci if w_sci is not None else settings.WEIGHT_LANDING_SCIENCE
    wd = w_dist if w_dist is not None else settings.WEIGHT_LANDING_DISTANCE

    sy, sx = spacing_m

    # Every site carries this. Without it a hardcoded grid offset is
    # structurally indistinguishable from a searched one in the payload.
    site_provenance = create_provenance(
        dataset_name=f"{crater_info.id.upper()}_LANDING_CANDIDATES",
        algorithm=("HARDCODED GRID OFFSETS, scored after the fact — not a search. Five fixed "
                   "(row, col) positions are evaluated over a 3x3 window and ranked by "
                   "safety/illumination/distance. Phase 3 replaces this with a per-pixel search."),
        parameters={
            "n_candidates": 5,
            "offsets_are_hardcoded": True,
            "search_performed": False,
            "sampling_window_cells": "3x3",
            "weights_applied": {
                "WEIGHT_LANDING_SAFETY": float(ws),
                "WEIGHT_LANDING_ILLUM": float(wi),
                "WEIGHT_LANDING_DISTANCE": float(wd),
            },
            "weight_not_applied": {
                "WEIGHT_LANDING_SCIENCE": float(wsc),
                "why": ("the term it weighted was a restatement of the distance term already "
                        "subtracted, so applying it double-counted distance"),
            },
            "latlon_source": "sar_geometry inverse polar stereographic" if frame is not None
                             else "spherical approximation about the crater centre",
            "spacing_m": [float(sy), float(sx)],
        },
        data_mode=data_mode,
    )

    # Locate centroid of primary ice candidate deposit
    candidate_y, candidate_x = np.where(scientific_mask)
    if len(candidate_x) > 0:
        target_x = int(np.mean(candidate_x))
        target_y = int(np.mean(candidate_y))
    else:
        # Fallback to crater center
        target_x = dem.shape[1] // 2
        target_y = dem.shape[0] // 2

    # Candidate exploration landing zones (located on elevated, illuminated rim ridges)
    # 4 distinct candidate landing sectors around the perimeter
    candidate_offsets = [
        ("Alpha Ridge (North)", 18, 50),
        ("Beta Plateau (South-East)", 82, 75),
        ("Gamma Bench (South-West)", 78, 25),
        ("Delta Spur (West)", 50, 15),
        ("Epsilon Crest (East)", 48, 85)
    ]

    candidates: List[CandidateLandingSite] = []

    # Maximum possible distance across grid in km, measured per axis
    max_diag_km = float(np.hypot(dem.shape[0] * sy, dem.shape[1] * sx) / 1000.0)

    for idx, (name, gy, gx) in enumerate(candidate_offsets):
        # 3x3 local sampling window
        y_min, y_max = max(0, gy - 1), min(dem.shape[0], gy + 2)
        x_min, x_max = max(0, gx - 1), min(dem.shape[1], gx + 2)

        local_slope = float(np.mean(slope_deg[y_min:y_max, x_min:x_max]))
        local_rough = float(np.mean(roughness[y_min:y_max, x_min:x_max]))
        local_hazard = float(np.mean(hazard[y_min:y_max, x_min:x_max]))
        local_illum = float(np.mean(illumination[y_min:y_max, x_min:x_max]))

        dist_km = float(np.hypot((gx - target_x) * sx, (gy - target_y) * sy) / 1000.0)

        # Distance penalty normalized (0 to 1)
        dist_penalty = min(1.0, dist_km / max_diag_km)

        # RENAMED from `sci_value` / `scientific_value`, and REMOVED from the
        # composite score. It is a decreasing function of dist_km and of nothing
        # else, so it was never a science term: the score subtracted the distance
        # penalty at wd and then added the SAME distance back, inverted, at wsc.
        # 20 % of the ranking was the distance term counted a second time. It is
        # still reported per site, because proximity to the anomaly centroid is a
        # real thing to know -- it is just not independent evidence.
        proximity_index = float(max(0.1, 1.0 - (dist_km / (max_diag_km * 0.7))))

        # Landing Safety (inversely proportional to hazard and slope)
        safety_score = max(0.0, 1.0 - local_hazard)

        # Composite Landing Score (0 - 100), over the three INDEPENDENT terms.
        # Score = ws * safety + wi * illum - wd * dist_penalty
        #
        # WEIGHT_LANDING_SCIENCE (wsc) is deliberately not applied and not in
        # the denominator: the term it weighted was the distance term already
        # present at wd. Including it double-counted distance at 20 % of the
        # ranking. The weight returns in Phase 3, when the site search gives it
        # something measured to weigh.
        raw_score = (
            ws * safety_score +
            wi * local_illum -
            wd * dist_penalty
        )
        total_weight = ws + wi + wd
        composite_score = float(np.clip((raw_score / total_weight) * 100.0, 0.0, 100.0))

        # Site lat/lon. Exact when the SAR frame is available (inverse polar
        # stereographic); otherwise a per-axis spherical offset from the crater
        # centre, with the longitude degree shrunk by cos(lat).
        if frame is not None:
            site_lat, site_lon = frame.grid_to_latlon(float(gx), float(gy), grid_max=grid_max)
            site_lat = float(site_lat)
            site_lon = float(site_lon)
        else:
            north_m = (gy - dem.shape[0] // 2) * sy
            east_m = (gx - dem.shape[1] // 2) * sx
            delta_lat = north_m / _M_PER_DEG_LAT
            site_lat = crater_info.latitude_deg + delta_lat
            cos_lat = max(np.cos(np.radians(site_lat)), 1e-6)
            site_lon = crater_info.longitude_deg + east_m / (_M_PER_DEG_LAT * cos_lat)
            site_lat = float(site_lat)
            site_lon = float(((site_lon + 180.0) % 360.0) - 180.0)

        rationale = []
        if local_slope < 8.0:
            rationale.append("Gentle touchdown slope (< 8°)")
        else:
            rationale.append(f"Moderate touchdown slope ({local_slope:.1f}°)")

        if local_illum > 0.60:
            rationale.append("Abundant solar illumination for lander battery/solar recharging")
        else:
            rationale.append("Moderate solar illumination window")

        if dist_km < 10.0:
            rationale.append(f"Direct proximity ({dist_km:.1f} km) to target cold-trap deposit")
        else:
            rationale.append(f"Extended traverse distance ({dist_km:.1f} km) to target")

        rationale.append(
            f"Proximity index {proximity_index:.2f} is a restatement of the {dist_km:.1f} km "
            f"distance above, not independent science content. It is REPORTED but NOT SCORED "
            f"(WEIGHT_LANDING_SCIENCE = {wsc:g} is not applied), because the composite already "
            f"subtracts that distance."
        )
        rationale.append(
            "This site is a HARDCODED GRID OFFSET, scored after the fact, not the result of a "
            "search. Phase 3 replaces these five with the argmax of a six-criterion per-pixel "
            "search over the native frame."
        )

        candidates.append(CandidateLandingSite(
            site_id=f"site_{idx + 1}",
            name=name,
            grid_x=gx,
            grid_y=gy,
            lat_deg=round(site_lat, 4),
            lon_deg=round(site_lon, 4),
            slope_deg=round(local_slope, 2),
            roughness=round(local_rough, 2),
            hazard_score=round(local_hazard, 3),
            illumination_fraction=round(local_illum, 3),
            distance_to_target_km=round(dist_km, 2),
            distance_proximity_index=round(proximity_index, 3),
            composite_landing_score=round(composite_score, 1),
            rank=0,
            is_recommended=False,
            selection_rationale=rationale,
            data_mode=data_mode,
            provenance=site_provenance,
        ))

    # Rank candidates by composite score descending
    candidates.sort(key=lambda s: s.composite_landing_score, reverse=True)
    for rank_idx, site in enumerate(candidates, start=1):
        site.rank = rank_idx

    # Recommended site is Rank 1
    candidates[0].is_recommended = True
    recommended_site = candidates[0]

    return candidates, recommended_site
