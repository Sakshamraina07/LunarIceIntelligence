"""
MODULE F: Multi-Objective Rover Path Planning & Engineering Energy Model.

ONE search is implemented: uniform-cost (Dijkstra) over an 8-connected grid.
The "A*" mode was removed in PRD Phase 1C -- its heuristic added a distance in
CELLS to a priority measured in composite cost units whose steps are floored at
0.1, so it was not admissible, the search was not guaranteed to return the
cheapest path, and the label asserted an optimality the code did not have. A
caller may still pass algorithm="A*"; it gets Dijkstra and `algorithm_used`
says Dijkstra.

Three strategies over that one search:
1. Shortest Path (Distance minimization)
2. Safest Path (Hazard/slope avoidance)
3. Science-Aware Path (Multi-objective balancing safety, energy, and volatile scientific sampling)
Includes simplified engineering energy model and graceful 'NO FEASIBLE PATH FOUND' handling.
"""

import heapq
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from app.core.config import settings
from app.core.schemas import RoverRouteResult, PathWaypoint
from app.core.provenance import create_provenance


class PriorityQueue:
    def __init__(self):
        self.elements = []

    def empty(self) -> bool:
        return len(self.elements) == 0

    def put(self, item, priority: float):
        heapq.heappush(self.elements, (priority, item))

    def get(self):
        return heapq.heappop(self.elements)[1]


def compute_step_energy_wh(
    dist_m: float,
    slope_deg: float,
    roughness: float,
    illumination: float
) -> float:
    """
    Simplified Engineering Energy Model for Pragyan-class micro-rover (30 kg).
    Labeled: SIMPLIFIED ENGINEERING ESTIMATE.
    Power consumption = Base hotel power + mobility work against slope & rolling resistance
    Net power = Power consumption - Solar generation (when illuminated).
    """
    speed_mps = settings.NOMINAL_SPEED_MPS
    time_sec = dist_m / speed_mps
    time_hr = time_sec / 3600.0

    # Base electrical and instrument hotel load
    p_base_w = settings.BASE_POWER_W

    # Mechanical drive power against gravity and rolling friction
    # Upward slope increases power dramatically; downhill regenerative braking is limited
    slope_rad = np.radians(slope_deg)
    p_climb_w = settings.ROVER_MASS_KG * 1.62 * speed_mps * np.sin(slope_rad)  # Lunar g = 1.62 m/s^2
    p_climb_w = max(-10.0, min(80.0, p_climb_w))

    # Rolling resistance on rough regolith
    p_rough_w = min(25.0, roughness * 0.8)

    total_consumption_w = max(15.0, p_base_w + p_climb_w + p_rough_w)

    # Solar power generation from top deck arrays (50W peak in full sunlight)
    p_solar_w = settings.SOLAR_POWER_GAIN_W * illumination

    net_power_draw_w = max(5.0, total_consumption_w - p_solar_w)
    return net_power_draw_w * time_hr


def plan_rover_path(
    dem: np.ndarray,
    slope_deg: np.ndarray,
    roughness: np.ndarray,
    hazard: np.ndarray,
    illumination: np.ndarray,
    scientific_mask: np.ndarray,
    start_xy: Tuple[int, int],
    target_xy: Tuple[int, int],
    spacing_m: Tuple[float, float],
    strategy: str = "Science-Aware",
    algorithm: str = "Dijkstra",
    max_slope_limit_deg: Optional[float] = None,
    *,
    data_mode: str,
) -> RoverRouteResult:
    """
    Plans traversal path between landing site and candidate ice deposit.
    Supports 8-connectivity grid graph with multi-objective edge weighting.

    `spacing_m` is (metres_per_line, metres_per_sample) — the ground spacing of
    axis 0 (y) and axis 1 (x). There is no default: the old
    `pixel_scale_m=250.0` was neither of the real spacings on any grid in this
    project, and it multiplied both axes alike, so on the live 100x100 mission
    grid (564.5 m per line, 1654.5 m per sample) an eastward step was costed as
    though it were 250 m when it is 1654.5 m.

    `roughness` is now a required raster and is the SAME array the terrain module
    produced. Previously the search fed `dem[ny,nx] - dem[cy,cx]` (a signed
    elevation delta, not a roughness) into the energy model while the telemetry
    pass fed a hardcoded 5.0 — the route was chosen under one model and reported
    under a different one.
    """
    height, width = dem.shape
    start = (start_xy[0], start_xy[1])
    target = (target_xy[0], target_xy[1])
    sy, sx = spacing_m

    # ONE supported search. A caller asking for "A*" gets Dijkstra and is told
    # so in `algorithm_used`, rather than getting a uniform-cost search wearing
    # an A* label. See the comment at the frontier push for why the heuristic
    # that used to be applied there was not admissible.
    algorithm_requested = algorithm
    algorithm = "Dijkstra"

    slope_limit_deg_pre = (max_slope_limit_deg if max_slope_limit_deg is not None
                           else float(settings.MAX_TRAVERSABLE_SLOPE_DEG))
    route_provenance = create_provenance(
        dataset_name=f"ROVER_ROUTE_{strategy.upper().replace('-', '_')}",
        algorithm=("Uniform-cost search (Dijkstra) over an 8-connected grid with a composite "
                   "step cost. Not A*: no admissible heuristic is applied."),
        parameters={
            "strategy": strategy,
            "algorithm_requested": algorithm_requested,
            "algorithm_used": "Dijkstra",
            "a_star_available": False,
            "why_no_a_star": ("the previous heuristic added a distance in CELLS to a priority in "
                              "composite cost units, so it was not admissible and the search was "
                              "not guaranteed optimal"),
            "max_traversable_slope_deg": float(slope_limit_deg_pre),
            "slope_limit_source": ("caller override" if max_slope_limit_deg is not None
                                   else "settings.MAX_TRAVERSABLE_SLOPE_DEG"),
            "spacing_m": [float(sy), float(sx)],
            "cost_scalers": {
                "hazard": 15.0, "energy": 5.0, "science": 8.0,
                "note": ("dimensionless scalers that put the three terms on comparable ranges "
                         "before the configured weights are applied; not measured quantities"),
            },
            "science_term": ("binary membership of the measured criteria mask; the Random Forest "
                             "P(ice) that used to weight it was withdrawn in Phase 1C"),
        },
        data_mode=data_mode,
    )

    # Validate boundaries
    if not (0 <= start[0] < width and 0 <= start[1] < height):
        return RoverRouteResult(
            strategy=strategy,
            algorithm_used=algorithm,
            path_found=False,
            path_length_waypoints=0,
            total_distance_km=0.0,
            estimated_travel_time_hours=0.0,
            total_energy_wh=0.0,
            mean_hazard_encountered=0.0,
            max_slope_encountered_deg=0.0,
            total_scientific_value_collected=0.0,
            waypoints=[],
            avoidance_explanations=[],
            failure_reason=(f"Start coordinates {start} lie outside the {width} x {height} grid."),
            data_mode=data_mode,
            provenance=route_provenance,
        )

    # Impassable barrier mask: Cliffs exceeding rover physical tilt limits
    # settings.MAX_TRAVERSABLE_SLOPE_DEG, not a 22.0 default. The module used to
    # carry its own 22.0 while config.py declared 20.0, so the planner drove over
    # terrain the rest of the app called impassable and the two numbers appeared
    # side by side in the UI.
    slope_limit_deg = slope_limit_deg_pre
    impassable = slope_deg > slope_limit_deg

    # Strategy Cost Weights
    if strategy == "Shortest":
        w_dist = 1.0
        w_hazard = 0.0
        w_energy = 0.0
        w_science = 0.0
    elif strategy == "Safest":
        w_dist = 0.15
        w_hazard = 0.85
        w_energy = 0.0
        w_science = 0.0
    else:  # Science-Aware
        w_dist = settings.WEIGHT_ROVER_DISTANCE
        w_hazard = settings.WEIGHT_ROVER_HAZARD
        w_energy = settings.WEIGHT_ROVER_ENERGY
        w_science = settings.WEIGHT_ROVER_SCIENCE

    # Graph Search Setup
    frontier = PriorityQueue()
    frontier.put(start, 0)
    came_from: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {start: None}
    cost_so_far: Dict[Tuple[int, int], float] = {start: 0.0}

    # 8-connected neighbors (dx, dy)
    neighbors = [
        (1, 0), (-1, 0), (0, 1), (0, -1),
        (1, 1), (-1, 1), (1, -1), (-1, -1)
    ]

    # Cheapest possible step in metres, used to normalise distance cost so that
    # the shortest step still costs 1.0 and the A* cell-distance heuristic stays
    # admissible while the cost itself is measured in real metres.
    min_spacing_m = float(min(sy, sx))

    target_reached = False

    while not frontier.empty():
        current = frontier.get()

        if current == target:
            target_reached = True
            break

        cx, cy = current

        for dx, dy in neighbors:
            nx, ny = cx + dx, cy + dy

            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if impassable[ny, nx]:
                continue

            step_dist_m = float(np.hypot(dx * sx, dy * sy))
            step_slope = float(slope_deg[ny, nx])
            step_hazard = float(hazard[ny, nx])
            step_illum = float(illumination[ny, nx])
            # Was ml_likelihood[ny, nx] -- the withdrawn Random Forest's P(ice).
            # The measured criteria mask is binary, so the science incentive is
            # now "this cell passed both polarimetric criteria" and nothing more.
            step_sci = 1.0 if scientific_mask[ny, nx] else 0.0

            # Simplified energy estimate for this step
            step_energy_wh = compute_step_energy_wh(
                dist_m=step_dist_m,
                slope_deg=step_slope,
                roughness=float(roughness[ny, nx]),
                illumination=step_illum
            )

            # Normalized costs for composite weighting
            dist_cost = step_dist_m / min_spacing_m
            hazard_cost = step_hazard * 15.0
            energy_cost = (step_energy_wh / 0.5) * 5.0
            # Science value serves as an incentive (cost reduction)
            science_benefit = step_sci * 8.0

            step_cost = (
                w_dist * dist_cost +
                w_hazard * hazard_cost +
                w_energy * energy_cost -
                w_science * science_benefit
            )
            # Ensure step cost is strictly positive
            step_cost = max(0.1, step_cost)

            new_cost = cost_so_far[current] + step_cost

            next_node = (nx, ny)
            if next_node not in cost_so_far or new_cost < cost_so_far[next_node]:
                cost_so_far[next_node] = new_cost
                # DIJKSTRA ONLY. The A* branch that stood here added
                # heuristic_euclidean(next, target) -- a distance in CELLS --
                # to a priority measured in composite cost units, where a single
                # step can cost w_hazard * hazard * 15.0 + w_energy * energy * 5.0
                # and is floored at 0.1. The two quantities are not commensurate,
                # so the heuristic was not admissible and the search was not
                # guaranteed to return the cheapest path. Labelling that "A*" is
                # a claim of optimality that was false. A scaled, admissible
                # heuristic arrives with the Phase 4 planner, which drops this
                # hand-rolled search for scipy.sparse.csgraph.dijkstra.
                priority = new_cost
                frontier.put(next_node, priority)
                came_from[next_node] = current

    if not target_reached:
        return RoverRouteResult(
            strategy=strategy,
            algorithm_used=algorithm,
            path_found=False,
            path_length_waypoints=0,
            total_distance_km=0.0,
            estimated_travel_time_hours=0.0,
            total_energy_wh=0.0,
            mean_hazard_encountered=0.0,
            max_slope_encountered_deg=0.0,
            total_scientific_value_collected=0.0,
            waypoints=[],
            avoidance_explanations=[
                f"UNREACHABLE. Every 8-connected route from {start} to {target} crosses cells above "
                f"the {slope_limit_deg:g}° traversability limit "
                f"({int(np.sum(impassable)):,} of {slope_deg.size:,} cells excluded)."
            ],
            failure_reason=(
                f"NO FEASIBLE PATH: no 8-connected sequence of cells at or below "
                f"{slope_limit_deg:g}° (settings.MAX_TRAVERSABLE_SLOPE_DEG) connects the start to "
                f"the target."
            ),
            data_mode=data_mode,
            provenance=route_provenance,
        )

    # Reconstruct path
    curr = target
    path_nodes = []
    while curr is not None:
        path_nodes.append(curr)
        curr = came_from[curr]
    path_nodes.reverse()

    # Calculate cumulative telemetry metrics along path
    waypoints: List[PathWaypoint] = []
    cum_dist_km = 0.0
    cum_energy_wh = 0.0
    hazards = []
    slopes = []
    sci_values = []

    for i, (px, py) in enumerate(path_nodes):
        elev = float(dem[py, px])
        s_deg = float(slope_deg[py, px])
        h_score = float(hazard[py, px])
        illum = float(illumination[py, px])
        sci = 1.0 if scientific_mask[py, px] else 0.0

        if i > 0:
            prev_px, prev_py = path_nodes[i - 1]
            step_m = float(np.hypot((px - prev_px) * sx, (py - prev_py) * sy))
            cum_dist_km += step_m / 1000.0
            # Same energy model, same roughness raster, same spacing as the search
            cum_energy_wh += compute_step_energy_wh(
                dist_m=step_m,
                slope_deg=s_deg,
                roughness=float(roughness[py, px]),
                illumination=illum
            )

        hazards.append(h_score)
        slopes.append(s_deg)
        sci_values.append(sci)

        waypoints.append(PathWaypoint(
            x=px,
            y=py,
            elevation_m=round(elev, 1),
            slope_deg=round(s_deg, 2),
            hazard_score=round(h_score, 3),
            illumination=round(illum, 3),
            science_value=round(sci, 3),
            cumulative_distance_km=round(cum_dist_km, 3),
            cumulative_energy_wh=round(cum_energy_wh, 2)
        ))

    est_time_hrs = (cum_dist_km * 1000.0 / settings.NOMINAL_SPEED_MPS) / 3600.0

    # DERIVED FROM THE PATH THAT WAS ACTUALLY WALKED. The previous version
    # printed one of three fixed paragraphs chosen by `strategy` alone --
    # "traversed wide switchbacks around boulder-strewn debris tongues" was
    # emitted for every Safest route regardless of geometry, in a build with no
    # boulder product at all. Each statement below is a measurement of `path_nodes`
    # or it is not made.
    avoidance_notes = []
    n_impassable = int(np.sum(impassable))
    avoidance_notes.append(
        f"{len(waypoints)} waypoints over {cum_dist_km:.2f} km; mean hazard "
        f"{float(np.mean(hazards)):.3f}, peak slope {float(np.max(slopes)):.2f}°."
    )
    avoidance_notes.append(
        f"{n_impassable:,} of {slope_deg.size:,} cells ({n_impassable / slope_deg.size * 100:.1f} %) "
        f"were excluded as impassable at > {slope_limit_deg:g}° "
        f"(settings.MAX_TRAVERSABLE_SLOPE_DEG)."
    )
    n_sci = int(np.sum([w.science_value > 0.0 for w in waypoints]))
    avoidance_notes.append(
        f"{n_sci} of {len(waypoints)} waypoints fall inside the measured criteria mask."
        if n_sci else
        f"No waypoint falls inside the measured criteria mask; the mask is empty for this frame, so "
        f"the science term contributed nothing to this route and the three strategies differ only in "
        f"their hazard and energy weighting."
    )
    straight_km = float(np.hypot((target[0] - start[0]) * sx, (target[1] - start[1]) * sy) / 1000.0)
    if straight_km > 0:
        avoidance_notes.append(
            f"Path is {cum_dist_km / straight_km:.2f}x the {straight_km:.2f} km straight-line "
            f"distance between start and target."
        )

    return RoverRouteResult(
        strategy=strategy,
        algorithm_used=algorithm,
        path_found=True,
        path_length_waypoints=len(waypoints),
        total_distance_km=round(cum_dist_km, 2),
        estimated_travel_time_hours=round(est_time_hrs, 2),
        total_energy_wh=round(cum_energy_wh, 1),
        mean_hazard_encountered=round(float(np.mean(hazards)), 3),
        max_slope_encountered_deg=round(float(np.max(slopes)), 2),
        total_scientific_value_collected=round(float(np.sum(sci_values)), 2),
        waypoints=waypoints,
        avoidance_explanations=avoidance_notes,
        failure_reason=None,
        data_mode=data_mode,
        provenance=route_provenance,
    )
