"""
emit_sweep_grid.py -- the sensitivity sweep, precomputed, so stage 09 needs no host.

    python -u backend/scripts/emit_sweep_grid.py [--crater faustini]

WHY THIS EXISTS
---------------
Stage 09's four sliders re-queried `/api/mission/{crater}`, which re-runs the
pipeline and therefore needs the 9 GB of Chandrayaan-2 and LOLA products. No
deployed host has them, so on the live site the sliders did nothing. Everything
else on that stage -- both sweep tables -- was already static and rendered fine.

This emits the joint screen as a MEASURED grid, so the sliders read a file and
the stage stops depending on a host at all. It is the same move the verdict, the
rasters, the searched sites, the Phase 4 traverse and the criteria probe already
made.

THE AXIS RANGE IS SET FROM THE DATA, NOT FROM THE PUBLISHED THRESHOLD
--------------------------------------------------------------------
A CPR axis centred on the published criterion (CPR > 1.00) is a column of zeros.
The peak CPR anywhere in this swath is 0.0534, and among pixels that satisfy
DOP < 0.13 it is 0.0042610574 -- so no threshold within a factor of 235 of the
published one admits a single pixel. Shipping that as a slider would be a
vacuous criterion behind a control surface: a widget whose output never moves
looks broken, and it is exactly what the NON-DISCRIMINATING gate exists to
catch.

So the CPR axis is built to span the range where the count ACTUALLY CHANGES --
which means running far below the published criterion -- and the published value
is carried on the axis, marked, so the degenerate point is visible rather than
cropped out. The factor is reported as a single number, because it is the result:

    THE PUBLISHED CPR THRESHOLD MUST FALL 234.68x BEFORE ONE PIXEL PASSES.

That measured crossing, 0.0042610574, sits on the algebraic ceiling METHODS 1
derives independently -- tanh^2(artanh(0.13)/2) = 0.0042610829, agreeing to 6
parts in a million. The emptiness is not a search that came up short; it is a
property of forming CPR from amplitude alone, and the data confirms the algebra
rather than being described by it.

WHAT IS MEASURED AND WHAT IS NOT
--------------------------------
Every cell of `counts` is a pixel count over the native arrays -- MEASURED. Area
is that count times the frame's own cell area -- MEASURED. Volume is NOT in this
file: it is area x assumed depth x assumed pore fraction, both untested
assumptions, so it stays DERIVED and is computed where it is displayed, beside
its own mark.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

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

OUT = BASE_DIR / "frontend" / "public" / "analysis" / "sweep_grid.json"
MEASURED = "MEASURED"


def cpr_axis(cv: np.ndarray, crossing: float, published: float) -> tuple[list[float], str]:
    """
    The CPR axis, spanning where the count changes -- which is not where the
    published criterion sits.

    Geometric from a decade below the crossing up to just above it, because the
    interesting structure is all in [0, 0.0043] and a linear axis would put
    fourteen of fifteen samples in a region where nothing happens. The published
    value and the crossing itself are unioned in so neither can be cropped out
    by a change to the spacing.
    """
    lo = crossing / 100.0
    grid = list(np.geomspace(lo, crossing * 1.6, 22))
    grid += [0.0, crossing, float(cv.max()), published]
    grid = sorted({round(float(g), 10) for g in grid})
    why = (f"geometric over [{lo:.3e}, {crossing * 1.6:.3e}] -- a decade below the measured "
           f"crossing to just above it -- unioned with 0, the crossing itself "
           f"({crossing:.10f}), the swath's peak CPR ({float(cv.max()):.10f}) and the "
           f"published criterion ({published:g}). Derived from the measured field, NOT "
           f"from config: a grid centred on the published value is a column of zeros.")
    return grid, why


def dop_axis(dv: np.ndarray, published: float) -> tuple[list[float], str]:
    """The DOP axis, spanning the measured range of the field itself."""
    lo, hi = float(dv.min()), float(dv.max())
    grid = list(np.linspace(lo, hi, 18)) + [published, lo, hi]
    grid = sorted({round(float(g), 10) for g in grid})
    why = (f"linear over the MEASURED DOP range [{lo:.6f}, {hi:.6f}] of the valid-amplitude "
           f"field, unioned with the published criterion ({published:g}). The endpoints are "
           f"the field's own extrema, not config constants.")
    return grid, why


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--crater", default="faustini")
    args = ap.parse_args()

    from build_analysis import load_native, resolve_spacing
    from app.core.config import settings as cfg

    print("=" * 78)
    print("EMIT SWEEP GRID -- the joint screen, measured at every threshold pair")
    print("=" * 78)

    r = load_native()
    cpr, dop, valid = r["cpr"], r["dop"], r["valid"]
    spacing, spacing_src = resolve_spacing()
    cell_km2 = (spacing[0] / 1000.0) * (spacing[1] / 1000.0)
    cpr_pub, dop_pub = float(cfg.CPR_THRESHOLD), float(cfg.DOP_THRESHOLD)

    cv, dv = cpr[valid], dop[valid]
    print(f"  valid amplitude   {cv.size:,} px @ {cell_km2:.6f} km2  "
          f"({cv.size * cell_km2:.2f} km2)")
    print(f"  spacing from      {spacing_src}")

    # -- THE CROSSING, measured -------------------------------------------
    # The count is >= 1 for threshold t exactly when t < max(CPR | DOP < dop_pub).
    # So this single number IS the answer to "how far must the threshold fall".
    dop_ok = dv < dop_pub
    crossing = float(cv[dop_ok].max())
    ceiling = float(np.tanh(np.arctanh(dop_pub) / 2.0) ** 2)
    factor = cpr_pub / crossing
    print(f"\n  DOP < {dop_pub:g}         {int(dop_ok.sum()):,} px "
          f"({dop_ok.mean() * 100:.3f} % of valid)")
    print(f"  crossing          max CPR among those = {crossing:.10f}   MEASURED")
    print(f"  algebraic ceiling tanh^2(artanh({dop_pub:g})/2) = {ceiling:.10f}   "
          f"(METHODS 1, independent)")
    print(f"  agreement         {abs(crossing - ceiling):.3e} absolute, "
          f"{abs(crossing - ceiling) / ceiling:.3e} relative")
    print(f"  FACTOR            the published CPR threshold must fall "
          f"{factor:.2f}x before one pixel passes")

    cgrid, cwhy = cpr_axis(cv, crossing, cpr_pub)
    dgrid, dwhy = dop_axis(dv, dop_pub)
    print(f"\n  cpr axis          {len(cgrid)} values, "
          f"{cgrid[0]:.3e} .. {cgrid[-1]:g}")
    print(f"  dop axis          {len(dgrid)} values, {dgrid[0]:.6f} .. {dgrid[-1]:.6f}")

    # -- the grid, exact ---------------------------------------------------
    # For each CPR threshold, the DOP-passing counts for EVERY dop threshold at
    # once, by binary search into the sorted DOP values of the surviving pixels.
    # Exact, not binned: searchsorted(..., 'left') counts strictly-less-than,
    # which is the criterion. A 2-D histogram would have quantised the answer to
    # its bin edges and called it a measurement.
    counts = []
    dgrid_arr = np.asarray(dgrid, dtype=np.float64)
    for t in cgrid:
        surviving = np.sort(dv[cv > t])
        counts.append(np.searchsorted(surviving, dgrid_arr, side="left").astype(int).tolist())

    flat = [n for row in counts for n in row]
    nonzero = sum(1 for n in flat if n > 0)
    print(f"  grid              {len(cgrid)} x {len(dgrid)} = {len(flat):,} cells, "
          f"{nonzero:,} non-zero ({nonzero / len(flat) * 100:.1f} %)")

    i_pub = cgrid.index(round(cpr_pub, 10))
    j_pub = dgrid.index(round(dop_pub, 10))
    published_px = counts[i_pub][j_pub]
    print(f"  published point   CPR > {cpr_pub:g}, DOP < {dop_pub:g}  ->  "
          f"{published_px:,} px = {published_px * cell_km2:.4f} km2")

    doc = {
        "schema": "lunar-ice/sweep-grid/1",
        "crater_id": args.crater,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "computed_by": "backend/scripts/emit_sweep_grid.py",
        "source": {
            "cpr": "data/pradan/native/cpr_native.tif",
            "dop": "data/pradan/native/dop_native.tif",
            "mask": "valid amplitude (the same mask every radar statistic uses)",
            "spacing_source": spacing_src,
        },
        "cell_km2": cell_km2,
        "valid_px": int(cv.size),
        "published_operating_point": {
            "cpr_threshold": cpr_pub, "dop_threshold": dop_pub,
            "cpr_index": i_pub, "dop_index": j_pub,
            "candidate_px": int(published_px),
            "candidate_area_km2": round(published_px * cell_km2, 6),
            "provenance": MEASURED,
        },
        "crossing": {
            "cpr_value": crossing,
            "provenance": MEASURED,
            "definition": ("the largest CPR among pixels satisfying the published DOP "
                           "criterion; the candidate count is non-zero for a CPR "
                           "threshold t exactly when t < this value"),
            "factor_below_published": factor,
            "algebraic_ceiling": ceiling,
            "algebraic_ceiling_provenance": "DERIVED",
            "algebraic_ceiling_source": "tanh^2(artanh(DOP_THRESHOLD)/2), METHODS section 1",
            "absolute_agreement": abs(crossing - ceiling),
            "relative_agreement": abs(crossing - ceiling) / ceiling,
            "statement": (f"The published CPR threshold must fall {factor:.2f}x - from "
                          f"{cpr_pub:g} to {crossing:.7f} - before a single pixel passes "
                          f"the joint screen. That measured crossing sits on the algebraic "
                          f"ceiling tanh^2(artanh({dop_pub:g})/2) = {ceiling:.7f}, agreeing to "
                          f"{abs(crossing - ceiling) / ceiling:.1e}, so the emptiness is a "
                          f"property of forming CPR from amplitude alone and not a search "
                          f"that came up short."),
        },
        "cpr_axis": {"values": cgrid, "grid_source": cwhy, "provenance": MEASURED},
        "dop_axis": {"values": dgrid, "grid_source": dwhy, "provenance": MEASURED},
        "counts": counts,
        "counts_provenance": MEASURED,
        "counts_note": ("counts[i][j] is the number of valid-amplitude pixels with "
                        "CPR > cpr_axis[i] AND DOP < dop_axis[j]. Multiply by cell_km2 for "
                        "area. Volume is deliberately ABSENT: it is area x assumed depth x "
                        "assumed pore fraction, and both assumptions are untested, so it is "
                        "DERIVED and is computed where it is shown, beside its own mark."),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}  ({OUT.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
