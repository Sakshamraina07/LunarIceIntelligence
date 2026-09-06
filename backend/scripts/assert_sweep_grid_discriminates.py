"""
assert_sweep_grid_discriminates.py -- G17. A slider whose output never moves.

    python backend/scripts/assert_sweep_grid_discriminates.py [--inject WHICH]

WHY
---
Stage 09's sliders read `analysis/sweep_grid.json` instead of re-querying a host
that does not hold the rasters. That removes a dependency, and it introduces a
new way to be wrong: a grid whose cells are all the same number is a control
surface over a criterion that does not discriminate. It looks like a working
widget and it is a vacuous claim -- the exact failure the NON-DISCRIMINATING
gate was written for elsewhere in this project, arriving here in a new shape.

A CPR axis spanning the PUBLISHED criterion would be precisely that. Nothing in
this swath comes within a factor of 235 of CPR > 1.00, so a slider over
[0.6, 1.6] reads 0.00 km2 at every position. The axis is therefore built from
the measured field, and this gate asserts that it still is -- because "derived
from the data" is a property that survives exactly as long as nobody edits the
emitter.

WHAT IT ASSERTS
---------------
  1. AGREEMENT   the grid's value at the published operating point equals the
                 candidate area in the analysis artifact the UI reads. Two files
                 describing one measurement must agree, or one of them is wrong.
  2. MEASURED    the axis endpoints come from the field's own extrema, not from
                 config constants; and the published value is ON the axis, so
                 the degenerate point is visible rather than cropped out.
  3. MOVES       the grid is not constant, and specifically not constant along
                 EACH axis in turn -- a grid that varies with CPR alone would
                 pass a naive "not constant" check with a dead DOP slider.
  4. CROSSING    the reported factor is arithmetically consistent with the
                 reported crossing and the published threshold, and the crossing
                 is where the counts actually change in the grid.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
for _d in (str(BACKEND_DIR), str(Path(__file__).resolve().parent)):
    if _d not in sys.path:
        sys.path.insert(0, _d)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

ANALYSIS = BASE_DIR / "frontend" / "public" / "analysis"
INJECTIONS = ("disagree", "constant", "cpronly", "publishedaxis", "configaxis", "factor")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--crater", default="faustini")
    ap.add_argument("--inject", choices=INJECTIONS,
                    help="prove the gate fails when the grid stops discriminating")
    args = ap.parse_args()

    from app.core.config import settings as cfg

    print("=" * 78)
    print("G17 - the precomputed sweep discriminates, and agrees with the analysis")
    print("=" * 78)

    grid_path = ANALYSIS / "sweep_grid.json"
    if not grid_path.is_file():
        print(f"  GATE FAIL - {grid_path} is absent. Run emit_sweep_grid.py.")
        return 1
    g = json.loads(grid_path.read_text(encoding="utf-8"))
    doc = json.loads((ANALYSIS / f"{args.crater}.json").read_text(encoding="utf-8"))

    # -- the injections, each one a defect this gate claims to catch ---------
    if args.inject == "disagree":
        print("  --inject disagree: the grid claims area the analysis does not\n")
        g["published_operating_point"]["candidate_area_km2"] = 8.75
    elif args.inject == "constant":
        print("  --inject constant: every cell the same number\n")
        g["counts"] = [[0] * len(row) for row in g["counts"]]
    elif args.inject == "cpronly":
        print("  --inject cpronly: the DOP slider is dead, the CPR one is not\n")
        g["counts"] = [[i] * len(row) for i, row in enumerate(g["counts"])]
    elif args.inject == "publishedaxis":
        print("  --inject publishedaxis: the published value cropped off the axis\n")
        keep = [i for i, v in enumerate(g["cpr_axis"]["values"])
                if abs(v - float(cfg.CPR_THRESHOLD)) > 1e-12]
        g["cpr_axis"]["values"] = [g["cpr_axis"]["values"][i] for i in keep]
        g["counts"] = [g["counts"][i] for i in keep]
    elif args.inject == "configaxis":
        print("  --inject configaxis: the axis re-centred on the published threshold\n")
        g["cpr_axis"]["values"] = [round(0.6 + 0.05 * k, 4) for k in range(21)]
        g["cpr_axis"]["grid_source"] = "linear 0.6..1.6 around the configured threshold"
        g["counts"] = [[0] * len(g["dop_axis"]["values"]) for _ in range(21)]
    elif args.inject == "factor":
        print("  --inject factor: the headline factor no longer follows from the crossing\n")
        g["crossing"]["factor_below_published"] = 3.0

    bad: list[str] = []
    cprs = g["cpr_axis"]["values"]
    dops = g["dop_axis"]["values"]
    counts = g["counts"]
    cpr_pub, dop_pub = float(cfg.CPR_THRESHOLD), float(cfg.DOP_THRESHOLD)

    # -- 1. AGREEMENT -------------------------------------------------------
    # `values.candidate_area_km2` is the AnalysisValue the UI's verdict card
    # renders; `measured_statistics.screening` is the same number as a bare
    # float. Both are checked, because two copies in one file is exactly the
    # shape that drifts, and this gate is cheap enough to read both.
    analysis_area = ((doc.get("values") or {}).get("candidate_area_km2") or {}).get("value")
    stats_area = ((doc.get("measured_statistics") or {}).get("screening")
                  or {}).get("candidate_area_km2")
    if (analysis_area is not None and stats_area is not None
            and abs(float(analysis_area) - float(stats_area)) > 1e-9):
        bad.append(f"{args.crater}.json disagrees with itself: values.candidate_area_km2 "
                   f"= {analysis_area}, measured_statistics.screening = {stats_area}")
    pop = g["published_operating_point"]
    if analysis_area is None:
        bad.append("the analysis artifact carries no candidate area to agree with")
    elif abs(float(pop["candidate_area_km2"]) - float(analysis_area)) > 1e-9:
        bad.append(f"the grid says {pop['candidate_area_km2']} km2 at the published "
                   f"operating point; {args.crater}.json says {analysis_area} km2. "
                   f"Two files, one measurement, two answers.")
    else:
        print(f"  agreement       grid and {args.crater}.json both say "
              f"{float(analysis_area):.4f} km2 at CPR > {cpr_pub:g}, DOP < {dop_pub:g}")

    # -- 2. MEASURED axes ---------------------------------------------------
    if not any(abs(v - cpr_pub) < 1e-12 for v in cprs):
        bad.append(f"the published CPR threshold {cpr_pub:g} is not on the axis, so the "
                   f"degenerate point has been cropped out rather than shown")
    if not any(abs(v - dop_pub) < 1e-12 for v in dops):
        bad.append(f"the published DOP threshold {dop_pub:g} is not on the axis")
    # An axis whose span is set by the published threshold rather than the data
    # is the defect this gate exists for: its minimum would sit near the
    # criterion instead of orders of magnitude below the measured crossing.
    crossing = float(g["crossing"]["cpr_value"])
    positive = [v for v in cprs if v > 0]
    if positive and min(positive) > crossing:
        bad.append(f"the CPR axis starts at {min(positive):.6g}, above the measured crossing "
                   f"{crossing:.6g} - it is set from the published threshold, not from the "
                   f"data, and every cell on it is necessarily empty")
    else:
        print(f"  measured axes   CPR spans {min(positive):.3e} .. {max(cprs):g} "
              f"(crossing {crossing:.7f}); published values present on both axes")

    # -- 3. IT MOVES --------------------------------------------------------
    flat = [n for row in counts for n in row]
    if len(set(flat)) <= 1:
        bad.append(f"every one of the {len(flat)} cells reads {flat[0] if flat else 'nothing'} - "
                   f"the grid does not discriminate, and a slider over it is a "
                   f"vacuous criterion behind a control surface")
    else:
        # ...and it must move on BOTH axes. A grid varying with CPR alone passes
        # a naive "not constant" check with a dead DOP slider, which is exactly
        # the shape the old published-range sweep had.
        moves_cpr = any(len({counts[i][j] for i in range(len(cprs))}) > 1
                        for j in range(len(dops)))
        moves_dop = any(len(set(counts[i])) > 1 for i in range(len(cprs)))
        if not moves_cpr:
            bad.append("no column varies with the CPR threshold - the CPR slider is dead")
        if not moves_dop:
            bad.append("no row varies with the DOP threshold - the DOP slider is dead")
        if moves_cpr and moves_dop:
            nz = sum(1 for n in flat if n > 0)
            print(f"  it moves        {len(set(flat)):,} distinct values over {len(flat):,} cells, "
                  f"{nz:,} non-zero; varies on BOTH axes")

    # -- 4. the CROSSING is arithmetic, not assertion -----------------------
    factor = float(g["crossing"]["factor_below_published"])
    if abs(factor - cpr_pub / crossing) > 1e-6 * max(1.0, factor):
        bad.append(f"the stated factor {factor:.4f} is not {cpr_pub:g}/{crossing:.10f} "
                   f"= {cpr_pub / crossing:.4f}")
    else:
        # and it must be where the grid's counts actually die
        above = [counts[i][g["published_operating_point"]["dop_index"]]
                 for i, v in enumerate(cprs) if v >= crossing]
        below = [counts[i][g["published_operating_point"]["dop_index"]]
                 for i, v in enumerate(cprs) if 0 < v < crossing]
        if any(n > 0 for n in above):
            bad.append("cells at or above the stated crossing still count pixels, so the "
                       "crossing is not where the answer changes")
        elif below and not any(n > 0 for n in below):
            bad.append("no cell below the stated crossing counts a pixel either, so the "
                       "crossing is not a crossing")
        else:
            print(f"  crossing        {cpr_pub:g} / {crossing:.10f} = {factor:.2f}x, and the "
                  f"counts die exactly there")

    print()
    if args.inject:
        if bad:
            print(f"  INJECTION CAUGHT ({args.inject}). The gate works.")
            for b in bad:
                print(f"    {b}")
            return 0
        print(f"  INJECTION NOT CAUGHT ({args.inject}). The gate does not do what it says.")
        return 1

    if bad:
        print("  GATE FAIL")
        for b in bad:
            print(f"    - {b}")
        return 1
    print("  GATE PASS - the precomputed sweep discriminates on both axes, its axes")
    print("  are built from the measured field, and it agrees with the analysis")
    print("  artifact at the published operating point.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
