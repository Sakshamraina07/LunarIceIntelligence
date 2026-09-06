"""
plan_traverse.py -- PRD Phase 4. Traverse planning between REAL targets.

    python backend/scripts/plan_traverse.py [--planning-m 100] [--compare-m 50]

CONNECTIVITY IS REPORTED BEFORE ANY DISTANCE, AND THAT ORDER IS DELIBERATE
--------------------------------------------------------------------------
A cell is impassable if ANY 25 m face inside it exceeds MAX_TRAVERSABLE_SLOPE_DEG.
That is the conservative rule and it is the right one -- a rover meets the worst
face in a cell, not its average. But slope_max rises fast with cell size: at
0.55 km cells the p50 is already 18.15 deg against a 20 deg limit, so at a coarse
planning resolution a large fraction of cells fail on a single steep face and the
graph can fragment.

IF THAT HAPPENS, "UNREACHABLE" IS REPORTING THE AGGREGATION, NOT THE MOON. It
would look like a finding about Faustini and be a finding about the cell size --
the same shape as the hazard saturation one level up.

So this script reports, before it computes a single route:
    passable cell fraction, at this resolution
    the number of connected components and the size of the largest
    whether all Phase 3 sites fall inside that component
and it repeats those figures at a FINER resolution so a reader can see which
result is terrain and which is quantisation. THE SLOPE LIMIT IS NEVER RELAXED TO
RECONNECT THE GRAPH.

WHAT THE ROVER IS ACTUALLY DRIVING TO
--------------------------------------
Candidate ice area in this frame is 0.00 km2. There is no measured ice target
anywhere, so a traverse "to the ice" would be a route to something this project
did not find. The primary deliverable is instead the route from each site to the
nearest MODELLED COLD TRAP boundary, carrying the same caveat the site records
do: a cold trap at 240 m effective resolution is where ice COULD persist, not
where ice IS, and no radar detection supports it.

The site-to-site matrix is the CAPABILITY result -- it demonstrates the planner
works between arbitrary pairs. The shortest tour over all five is a graph-theory
exercise, not a mission plan: no lander visits five sites, a lander goes to one.
Both are labelled as such.
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import tifffile

BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

NATIVE = BASE_DIR / "data" / "pradan" / "native"
LOLA_DIR = BASE_DIR / "data" / "pradan" / "lola"
RAW = BASE_DIR / "data" / "pradan" / "raw" / "data" / "calibrated" / "20200808"
STEM = "ch2_sar_ncxl_20200808t201154198"
SITES_IN = BASE_DIR / "docs" / "landing_sites.json"
OUT = BASE_DIR / "docs" / "traverse.json"
OUT_UI = BASE_DIR / "frontend" / "public" / "analysis" / "traverse.json"

G_MOON = 1.625          # m/s^2
MU_ROLL = 0.25          # rolling resistance over regolith, dimensionless


def hr(t: str) -> None:
    print("\n" + "-" * 78)
    print(t)
    print("-" * 78, flush=True)


def aggregate(slope, hazard, psr, valid, k: int):
    """Native 25 m -> a k-times coarser planning grid.

    hazard is a BOUNDED 0-1 score and is AREA-AVERAGED down, which is meaningful.
    slope is aggregated by MAX, because a rover meets the worst face in a cell.
    psr and the amplitude mask are aggregated by ANY, so a planning cell counts
    as cold-trap or measured if any of its native pixels is.
    """
    h, w = (slope.shape[0] // k) * k, (slope.shape[1] // k) * k
    rs = lambda a: a[:h, :w].reshape(h // k, k, w // k, k)
    return (rs(slope).max(axis=(1, 3)),
            rs(hazard).mean(axis=(1, 3)),
            rs(psr).any(axis=(1, 3)),
            rs(valid).any(axis=(1, 3)))


def connectivity(passable):
    from scipy.ndimage import label
    lab, n = label(passable, structure=np.ones((3, 3), dtype=int))
    if n == 0:
        return lab, 0, 0, 0
    sizes = np.bincount(lab.ravel())
    sizes[0] = 0
    biggest = int(sizes.argmax())
    return lab, n, biggest, int(sizes[biggest])


def build_graph(passable, hazard, px_m, hazard_weight):
    """8-connected grid over PASSABLE cells only.

    Edge cost is GROUND LENGTH times a hazard multiplier, so a route's cost is a
    distance in metres inflated by how hard the ground is. Length is reported
    separately from cost: a cost is a planning quantity, a length is a claim
    about the Moon.
    """
    from scipy.sparse import coo_matrix
    ny, nx = passable.shape
    idx = -np.ones(passable.shape, dtype=np.int64)
    idx[passable] = np.arange(int(passable.sum()))
    rows, cols, cost, length = [], [], [], []
    for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
        a = passable[max(0, -dy):ny - max(0, dy), max(0, -dx):nx - max(0, dx)]
        b = passable[max(0, dy):ny - max(0, -dy), max(0, dx):nx - max(0, -dx)]
        both = a & b
        if not both.any():
            continue
        ia = idx[max(0, -dy):ny - max(0, dy), max(0, -dx):nx - max(0, dx)][both]
        ib = idx[max(0, dy):ny - max(0, -dy), max(0, dx):nx - max(0, -dx)][both]
        ha = hazard[max(0, -dy):ny - max(0, dy), max(0, -dx):nx - max(0, dx)][both]
        hb = hazard[max(0, dy):ny - max(0, -dy), max(0, dx):nx - max(0, -dx)][both]
        seg = px_m * float(np.hypot(dy, dx))
        c = seg * (1.0 + hazard_weight * 0.5 * (ha + hb))
        rows.append(ia); cols.append(ib); cost.append(c)
        length.append(np.full(ia.shape, seg))
        rows.append(ib); cols.append(ia); cost.append(c)
        length.append(np.full(ia.shape, seg))
    n = int(passable.sum())
    r = np.concatenate(rows); c2 = np.concatenate(cols)
    return (coo_matrix((np.concatenate(cost), (r, c2)), shape=(n, n)).tocsr(),
            coo_matrix((np.concatenate(length), (r, c2)), shape=(n, n)).tocsr(),
            idx)


def walk_back(pred, src, dst):
    path = [dst]
    while path[-1] != src:
        nxt = pred[path[-1]]
        if nxt < 0:
            return None
        path.append(int(nxt))
    return path[::-1]


def main() -> int:
    from app.core.config import settings as cfg
    from app.ingestion.horizon_frame import load_horizon
    from app.ingestion.sar_geometry import read_geotiff_frame
    from app.modules.module_d_terrain import compute_hazard_score
    from scipy.ndimage import uniform_filter
    from scipy.sparse.csgraph import dijkstra

    ap = argparse.ArgumentParser()
    ap.add_argument("--planning-m", type=float, default=100.0)
    ap.add_argument("--compare-m", type=float, default=50.0)
    ap.add_argument("--hazard-weight", type=float, default=2.0)
    args = ap.parse_args()

    sites_doc = json.loads(SITES_IN.read_text(encoding="utf-8"))
    sites = sites_doc["sites"]

    dem = tifffile.imread(str(NATIVE / "dem_native.tif")).astype(np.float32)
    valid = tifffile.imread(str(NATIVE / "valid_native.tif")).astype(bool)
    frame = read_geotiff_frame(RAW / f"{STEM}_d_sri_xx_cp_lh_d18.tif",
                               RAW / f"{STEM}_d_sri_xx_cp_xx_d18.xml")
    hp = load_horizon(LOLA_DIR)
    proj = hp.to_frame(frame, dem.shape)
    psr = proj["psr_mask"]

    px_m = 25.0
    gy, gx = np.gradient(dem, px_m, px_m)
    slope = np.degrees(np.arctan(np.hypot(gx, gy))).astype(np.float32)
    m1 = uniform_filter(dem, size=5)
    rough = np.sqrt(np.maximum(0.0, uniform_filter(dem.astype(np.float64) ** 2, size=5)
                               - m1.astype(np.float64) ** 2)).astype(np.float32)
    hazard = compute_hazard_score(slope, rough, np.zeros_like(dem, np.float32))
    limit = float(cfg.MAX_TRAVERSABLE_SLOPE_DEG)

    # ---------------------------------------------------------- CONNECTIVITY
    hr("CONNECTIVITY FIRST — is the graph even connected, and at what cell size?")
    print(f"  impassable rule: slope_max in a planning cell > "
          f"{limit:g} deg (MAX_TRAVERSABLE_SLOPE_DEG)")
    print(f"  a cell containing ANY impassable 25 m face is impassable — the")
    print(f"  conservative rule, and the reason cell size matters so much here.\n")
    print(f"  {'planning res':>14}{'cells':>12}{'passable':>11}{'components':>12}"
          f"{'largest':>11}{'sites in it':>13}")

    conn = {}
    for res in (args.planning_m, args.compare_m):
        k = max(1, int(round(res / px_m)))
        eff = k * px_m
        smax, hmean, psr_c, valid_c = aggregate(slope, hazard, psr, valid, k)
        passable = smax <= limit
        lab, ncomp, big, bigsz = connectivity(passable)
        inside = 0
        for s in sites:
            li, si = s["grid"]["line"] // k, s["grid"]["sample"] // k
            if 0 <= li < lab.shape[0] and 0 <= si < lab.shape[1] and lab[li, si] == big:
                inside += 1
        conn[eff] = {"k": k, "eff_m": eff, "cells": int(passable.size),
                     "passable_fraction": float(passable.mean()),
                     "components": int(ncomp),
                     "largest_component_cells": bigsz,
                     "largest_component_fraction_of_passable":
                         bigsz / max(int(passable.sum()), 1),
                     "sites_in_largest": inside, "n_sites": len(sites),
                     "_arrays": (smax, hmean, psr_c, valid_c, passable, lab, big)}
        print(f"  {eff:>11.0f} m{passable.size:>12,}{passable.mean() * 100:>10.2f}%"
              f"{ncomp:>12,}{bigsz:>11,}{inside:>9} / {len(sites)}")

    fine = conn[min(conn)]
    coarse = conn[max(conn)]
    print()
    if coarse["sites_in_largest"] < coarse["n_sites"]:
        print(f"  AT {coarse['eff_m']:.0f} m THE GRAPH DOES NOT HOLD ALL THE SITES.")
        print(f"  At {fine['eff_m']:.0f} m it holds "
              f"{fine['sites_in_largest']}/{fine['n_sites']}. Any UNREACHABLE at the")
        print("  coarse resolution would be reporting the CELL SIZE, not the Moon.")
    else:
        print(f"  All {coarse['n_sites']} sites lie in one connected component at both")
        print(f"  resolutions. Passable fraction moves "
              f"{coarse['passable_fraction'] * 100:.2f} % -> "
              f"{fine['passable_fraction'] * 100:.2f} % from "
              f"{coarse['eff_m']:.0f} m to {fine['eff_m']:.0f} m, which is the")
        print("  aggregation effect made visible rather than assumed away.")
    print("\n  THE SLOPE LIMIT IS NOT RELAXED TO RECONNECT ANYTHING.")

    # Plan at the requested resolution.
    use = conn[max(k_ for k_ in conn if abs(k_ - args.planning_m) < 1e-6)] \
        if any(abs(k_ - args.planning_m) < 1e-6 for k_ in conn) else coarse
    smax, hmean, psr_c, valid_c, passable, lab, big = use["_arrays"]
    eff = use["eff_m"]
    for v in conn.values():
        v.pop("_arrays", None)

    hr(f"PLANNING AT {eff:.0f} m — path length is QUANTISED to this")
    print(f"  Every reported length is a multiple of {eff:.0f} m (or {eff * 2 ** 0.5:.1f} m")
    print(f"  diagonally). A route reported as 4,180 m is 4,180 +/- {eff / 2:.0f} m; the")
    print("  planner cannot resolve finer than one cell and does not pretend to.")
    graph, lengraph, idx = build_graph(passable, hmean, eff, args.hazard_weight)
    print(f"  graph: {int(passable.sum()):,} nodes, {graph.nnz:,} directed edges, "
          f"8-connected")
    print(f"  edge cost = ground length x (1 + {args.hazard_weight:g} x mean hazard); "
          f"LENGTH is tracked separately from COST")

    def node_of(site):
        li, si = site["grid"]["line"] // use["k"], site["grid"]["sample"] // use["k"]
        li = min(max(li, 0), passable.shape[0] - 1)
        si = min(max(si, 0), passable.shape[1] - 1)
        return int(idx[li, si]) if passable[li, si] else -1

    nodes = [node_of(s) for s in sites]
    dem_c = dem[:passable.shape[0] * use["k"], :passable.shape[1] * use["k"]] \
        .reshape(passable.shape[0], use["k"], passable.shape[1], use["k"]).mean(axis=(1, 3))

    def latlon(li, si):
        """Planning cell (li, si) -> selenodetic lat/lon at the CELL CENTRE.

        CALLS THE FRAME, DOES NOT RESTATE IT. This function previously
        re-derived the inverse projection by hand and used
        `arctan2(x, -y)` -- the `y_away_lam0` convention of the LOLA polar
        product (ingest_lola_polar_dem.py:272) -- against a DFSAR frame whose
        transform is `arctan2(x, y)` (sar_geometry.py:198). Latitude was
        unaffected, so every check that looked at latitude passed. Longitude
        came out as 180 - lon: site 1 was written at 97.33971 deg where the
        frame, validated against ISRO's 937,296-node geolocation grid to
        13.2 mm, puts it at 82.64773 deg.

        This is METHODS section 0's first pattern in a producer rather than a
        verifier: a second copy of a transform, which agreed with the first
        until it did not. There is now one copy.
        """
        lat, lon = frame.pixel_to_latlon(li * use["k"] + use["k"] / 2,
                                         si * use["k"] + use["k"] / 2)
        return round(float(np.asarray(lat).ravel()[0]), 5),                round(float(np.asarray(lon).ravel()[0]), 5)

    def route(src_node, dst_nodes):
        """Dijkstra from one node to a SET; returns the cheapest reachable one."""
        if src_node < 0:
            return None
        d, pred = dijkstra(graph, indices=src_node, return_predecessors=True)
        best, bestd = -1, np.inf
        for t in dst_nodes:
            if t >= 0 and d[t] < bestd:
                best, bestd = t, d[t]
        if best < 0 or not np.isfinite(bestd):
            return None
        path = walk_back(pred, src_node, best)
        if path is None:
            return None
        rc = np.argwhere(idx >= 0)
        lut = np.zeros((int(passable.sum()), 2), dtype=np.int64)
        lut[idx[passable]] = rc
        cells = [(int(lut[n][0]), int(lut[n][1])) for n in path]
        length_m = sum(eff * float(np.hypot(cells[i + 1][0] - cells[i][0],
                                            cells[i + 1][1] - cells[i][1]))
                       for i in range(len(cells) - 1))
        climb = sum(max(0.0, float(dem_c[cells[i + 1]] - dem_c[cells[i]]))
                    for i in range(len(cells) - 1))
        return {"target_node": best, "cost": float(bestd), "length_m": round(length_m, 1),
                "climb_m": round(climb, 1), "cells": cells,
                "energy_J_per_kg": round(G_MOON * (MU_ROLL * length_m + climb), 1)}

    return _report(args, sites, conn, use, eff, nodes, route, psr_c, passable,
                   idx, latlon, sites_doc, frame)


def _report(args, sites, conn, use, eff, nodes, route, psr_c, passable, idx,
            latlon, sites_doc, frame) -> int:
    # ---------------------------------------------- PRIMARY: site -> cold trap
    hr("PRIMARY DELIVERABLE — each site to its nearest MODELLED cold trap")
    print("  Candidate ice area in this frame is 0.00 km2. There is no measured ice")
    print("  target anywhere here, so this is a route to a MODELLED cold trap from")
    print("  the Phase 2 horizon computation at 240 m effective resolution: where")
    print("  ice COULD persist, not where ice IS. No radar detection supports it.")
    print()
    trap_nodes = [int(idx[li, si]) for li, si in np.argwhere(psr_c & passable)]
    print(f"  {int(psr_c.sum()):,} cold-trap cells, {len(trap_nodes):,} of them passable\n")
    print(f"  {'site':>5}{'length m':>11}{'climb m':>10}{'J/kg':>10}{'cells':>8}  status")
    to_trap = []
    for s, n in zip(sites, nodes):
        r = route(n, trap_nodes) if n >= 0 else None
        if r is None:
            to_trap.append({"rank": s["rank"], "status": "UNREACHABLE",
                            "why": ("the site's planning cell is impassable, or no "
                                    "passable path to any cold-trap cell exists at "
                                    "this planning resolution"),
                            "length_m": None})
            print(f"  {s['rank']:>5}{'—':>11}{'—':>10}{'—':>10}{'—':>8}  UNREACHABLE")
            continue
        ll = [latlon(a, b) for a, b in r["cells"]]
        to_trap.append({
            "rank": s["rank"], "status": "REACHABLE",
            "length_m": r["length_m"], "climb_m": r["climb_m"],
            "energy_J_per_kg": r["energy_J_per_kg"], "provenance_energy": "DERIVED",
            "quantisation_m": eff, "cells": len(r["cells"]),
            "polyline_grid": r["cells"], "polyline_latlon": ll,
            "target": ("nearest MODELLED cold trap boundary (horizon computation, "
                       "240 m effective) — where ice COULD persist, not where ice "
                       "IS. Candidate ice area in this frame is 0.00 km2 and no "
                       "radar detection supports this target."),
        })
        print(f"  {s['rank']:>5}{r['length_m']:>11,.0f}{r['climb_m']:>10.1f}"
              f"{r['energy_J_per_kg']:>10,.0f}{len(r['cells']):>8}  REACHABLE")

    # ---- GATE: the first waypoint IS the site, so it must plot where the site
    # plots. This file wrote longitudes as 180 - lon for five routes and every
    # existing check passed, because they all looked at length, climb and
    # connectivity -- quantities the longitude does not enter. The only thing
    # that would have caught it is comparing the two files that must agree.
    # Tolerance is one planning cell of great-circle distance: the route starts
    # at the CELL CENTRE and the site is a native 25 m pixel inside that cell,
    # so they are not required to be equal, only to be in the same cell.
    for rec, s in zip(to_trap, sites):
        if rec["status"] != "REACHABLE":
            continue
        lat0, lon0 = rec["polyline_latlon"][0]
        d = frame.great_circle_m(s["lat_deg"], s["lon_deg"], lat0, lon0)
        if d > eff * 1.5:
            raise AssertionError(
                f"route {rec['rank']} starts {d:,.0f} m from site {rec['rank']} "
                f"({s['lat_deg']:.5f}, {s['lon_deg']:.5f}) vs "
                f"({lat0:.5f}, {lon0:.5f}) — more than one {eff:g} m planning "
                f"cell. The route polyline and docs/landing_sites.json disagree "
                f"about where the same point is.")
        print(f"        route {rec['rank']} starts {d:6.1f} m from site "
              f"{rec['rank']} (tolerance {eff * 1.5:g} m) — files agree")

    # ------------------------------------------------ CAPABILITY: pairwise
    hr("CAPABILITY RESULT — pairwise site-to-site matrix")
    print("  This demonstrates the planner works between arbitrary pairs. It is not")
    print("  a mission plan.\n")
    n = len(sites)
    mat = [[None] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                mat[i][j] = 0.0
                continue
            r = route(nodes[i], [nodes[j]])
            mat[i][j] = None if r is None else r["length_m"]
    print(f"  {'':>6}" + "".join(f"{s['rank']:>11}" for s in sites))
    for i, s in enumerate(sites):
        cells = "".join(("     UNREACH" if mat[i][j] is None
                         else f"{mat[i][j]:>11,.0f}") for j in range(n))
        print(f"  {s['rank']:>6}{cells}")
    print("\n  UNREACH is an explicit state and never a distance of 0. A zero would")
    print("  read as 'no travel needed', which is the opposite of what it means.")

    # A ROUTE CAN NEVER BE SHORTER THAN THE STRAIGHT LINE. Asserted rather than
    # assumed: a path length shorter than the Euclidean separation would mean the
    # length accumulator or the grid mapping is wrong, and the number would look
    # entirely plausible while being impossible.
    hr("DETOUR RATIO — route length against straight-line separation")
    print("  Ratio 1.0 is a straight run. High ratios are terrain forcing a")
    print("  detour, and they are the part of a traverse result that carries")
    print("  information; the raw length alone does not.\n")
    print(f"  {'pair':>7}{'straight m':>13}{'route m':>12}{'ratio':>8}")
    detour = {}
    worst = 0.0
    for i in range(n):
        for j in range(i + 1, n):
            gi = (sites[i]["grid"]["line"], sites[i]["grid"]["sample"])
            gj = (sites[j]["grid"]["line"], sites[j]["grid"]["sample"])
            straight = 25.0 * float(np.hypot(gi[0] - gj[0], gi[1] - gj[1]))
            r = mat[i][j]
            if r is None:
                print(f"  {sites[i]['rank']}-{sites[j]['rank']:<5}{straight:>13,.0f}"
                      f"{'UNREACH':>12}{'—':>8}")
                continue
            assert r >= straight * 0.999, (
                f"route {sites[i]['rank']}-{sites[j]['rank']} is {r:.0f} m, SHORTER "
                f"than the straight-line separation of {straight:.0f} m. A path "
                f"cannot beat the Euclidean distance; the length accumulator or the "
                f"grid mapping is wrong.")
            ratio = r / max(straight, 1e-9)
            worst = max(worst, ratio)
            detour[f"{sites[i]['rank']}-{sites[j]['rank']}"] = {
                "straight_m": round(straight, 1), "route_m": r,
                "detour_ratio": round(ratio, 2)}
            print(f"  {sites[i]['rank']}-{sites[j]['rank']:<5}{straight:>13,.0f}"
                  f"{r:>12,.0f}{ratio:>8.2f}")
    print(f"\n  every route is at least its straight-line separation — asserted, "
          f"not assumed")
    if worst > 2.5:
        print(f"\n  THE SITES ARE NOT ONE NEIGHBOURHOOD. The worst pair detours "
              f"{worst:.1f}x,")
        print("  which is terrain the rover has to go around rather than through.")
        print("  Ratios near 1.1 and ratios near 5 in the same matrix mean the")
        print("  sites fall into groups separated by impassable ground -- a fact")
        print("  about this frame that a table of raw lengths would not show.")

    # ------------------------------------------------------------- the tour
    hr("SHORTEST TOUR — a graph-theory exercise, NOT a mission plan")
    print("  No lander visits five sites; a lander goes to ONE. This is here to")
    print("  show the planner composes, and it is labelled so nobody reads it as a")
    print("  proposed concept of operations.\n")
    tour = None
    if n <= 8 and all(mat[i][j] is not None for i in range(n) for j in range(n)):
        best, bestlen = None, np.inf
        for perm in itertools.permutations(range(1, n)):
            order = (0,) + perm
            tot = sum(mat[order[i]][order[i + 1]] for i in range(n - 1))
            if tot < bestlen:
                best, bestlen = order, tot
        tour = {"method": ("EXACT — full enumeration of all "
                           f"{np.math.factorial(n - 1) if hasattr(np, 'math') else 24} "
                           "permutations with the first site fixed. Not a heuristic, "
                           "not simulated annealing; for n <= 8 the optimum is "
                           "cheap to prove."),
                "order": [sites[i]["rank"] for i in best],
                "total_length_m": round(float(bestlen), 1),
                "is_a_mission_plan": False,
                "note": ("A capability demonstration. No mission concept in this "
                         "project proposes visiting five landing sites.")}
        print(f"  order {' -> '.join(str(sites[i]['rank']) for i in best)}   "
              f"total {bestlen:,.0f} m")
        print(f"  method: exact enumeration, {n - 1}! permutations, first site fixed")
    else:
        print("  NOT COMPUTED — the matrix contains UNREACHABLE pairs, so no tour")
        print("  over all five exists at this planning resolution.")

    doc = {
        "schema": "traverse/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/plan_traverse.py",
        "planning": {
            "resolution_m": eff,
            "quantisation_note": (f"Every length is a multiple of {eff:.0f} m "
                                  f"(or {eff * 2 ** 0.5:.1f} m diagonally). A route "
                                  f"reported as 4,180 m is 4,180 +/- {eff / 2:.0f} m."),
            "impassable_rule": ("slope_max within a planning cell > "
                                "MAX_TRAVERSABLE_SLOPE_DEG. A cell containing any "
                                "impassable 25 m face is impassable."),
            "hazard_weight": args.hazard_weight,
            "algorithm": "Dijkstra, 8-connected, scipy.sparse.csgraph",
        },
        "connectivity": conn,
        "energy_proxy": {
            "provenance": "DERIVED",
            "formula": "g_moon * (mu_roll * length_m + positive climb_m), per kg",
            "g_moon_m_s2": G_MOON, "mu_roll": MU_ROLL,
            "note": ("Reported PER KILOGRAM so no rover mass is invented. mu_roll is "
                     "an assumed rolling resistance for regolith, not a measurement."),
        },
        "primary_site_to_cold_trap": to_trap,
        "capability_pairwise_matrix_m": mat,
        "capability_detour_ratios": detour,
        "capability_tour": tour,
        "site_source": str(SITES_IN.relative_to(BASE_DIR)).replace("\\", "/"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    OUT_UI.parent.mkdir(parents=True, exist_ok=True)
    OUT_UI.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")
    print(f"  wrote {OUT_UI.relative_to(BASE_DIR)}  (the UI reads this one)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
