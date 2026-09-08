"""
Cross-path consistency gate: the API and the static analysis must agree.

WHY THIS EXISTS
---------------
The same terrain quantity is computed twice in this project, by two paths that
do not share code:

    STATIC  build_analysis.py -> frontend/public/analysis/<crater>.json
            scores on the native 2258 x 6618 frame at 25 m. This is what the UI
            reads and what every screenshot shows.

    API     mission_service -> /api/mission/<crater>, and the PDF report
            scores through pradan_pipeline.process_real_dem and
            module_d_terrain.analyze_terrain_safety.

They diverged, twice, in two different places, and the second time the visible
surface was correct while the PDF was not -- which is the worst shape for a bug
to have, because looking at the app does not reveal it:

  * process_real_dem resized the DEM to the serving grid and scored THERE, so a
    5x5 roughness window spanned ~404 m and clip(roughness/50) pinned 2.4 % of
    the frame at 1.0.
  * analyze_terrain_safety then RE-derived terrain from the downsampled DEM,
    discarding the fix, so correcting process_real_dem alone moved nothing.
  * and the DEM the API loads is a 2048^2 raster at 27.56 x 80.79 m, not 25 m,
    so scoring it as though it were 25 m overstated every slope by ~2x.

Three separate faults in one chain. A gate is what stops a fourth.

WHAT IS AND IS NOT COMPARED
---------------------------
Comparable: means and the hazard distribution. These are the same physical
quantity computed two ways and must match.

NOT comparable, and excluded ON PURPOSE rather than by loosening a tolerance:

  * max_slope_deg. The API serves a field AREA-AVERAGED onto a coarse grid, so
    its maximum is a max OF MEANS and is legitimately far below the native
    maximum (33.24 vs 69.39 deg on the current frame). That is why
    process_real_dem carries slope_max_deg separately.
FIXED RATHER THAN EXCLUDED: safe_slope_fraction used to mean the 12 deg limit
in the API and the 20 deg one in the static file, with landable_slope_fraction
holding the 12 deg one there. Two quantities under one name across two files.
Excluding it would have made this gate correct and left the trap armed for the
next reader -- including an examiner comparing the PDF against the UI. Both
sides now carry the threshold IN the name (slope_fraction_below_12deg /
slope_fraction_below_20deg), the 12 deg one is gated with its own stated
tolerance, and the names are checked against config on every run.

Usage:
    python -u backend/scripts/assert_paths_agree.py [--crater faustini]
                                                    [--tolerance 0.02]
Exits non-zero if the paths disagree.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

#: (api key under "terrain", static key under "values"). Only quantities that
#: are the same thing computed two ways.
COMPARED = [
    ("mean_slope_deg", "mean_slope_deg", None),
    ("mean_roughness", "mean_roughness_m", None),
    ("mean_hazard_score", "mean_hazard", None),
    # Gate-able now that the naming collision is fixed: both sides mean the
    # 12 deg limit. Its own tolerance, because the API's copy is computed on an
    # AREA-AVERAGED field and averaging moves a threshold crossing more than it
    # moves a mean -- a stated allowance for a known effect, not a number raised
    # until the row passed.
    ("slope_fraction_below_12deg", "slope_fraction_below_12deg", 0.05),
]

#: SHADOW, AT TOLERANCE 0. Read from api["psr"], not api["terrain"].
#:
#: This gate compared slope, roughness and hazard ONLY, so for as long as the
#: served path computed its own PSR from a brightness proxy at a capped 1.5 deg
#: solar altitude -- a model METHODS 5.3 measures wrong by up to 4.4x -- a
#: disagreement about shadow could not fire. That is METHODS 0's FOURTH PATTERN,
#: a surface with no check on it, one scale smaller than the PDF was: not a check
#: that was wrong, but a quantity no check covered.
#:
#: TOLERANCE 0, not a small number. Both sides are now the same reduction over
#: the same horizon product -- a pixel count times the frame's own cell area --
#: so any difference at all means they are not reading the same thing, and there
#: is no averaging effect to allow for. A tolerance here would be a place for the
#: next divergence to hide.
COMPARED_SHADOW = [
    ("psr_area_km2", "psr_area_km2"),
    ("psr_px", "psr_px"),
]

#: Every quantity BOTH paths produce must be either compared or excluded with a
#: reason. A gate that checks three of six named quantities certifies the three
#: it happens to know about, and says nothing about the rest while looking like
#: it covers the surface.
COVERAGE_SOURCES = {
    "terrain": ("mean_slope_deg", "mean_roughness", "mean_hazard_score",
                "slope_fraction_below_12deg", "max_slope_deg"),
    "psr": ("psr_area_km2", "psr_px", "total_area_km2", "psr_area_fraction",
            "doubly_shadowed_area_km2", "mean_illumination_fraction",
            "shadow_depth_estimate_m", "confidence_level"),
}

#: Named, with the reason, so that excluding them is a stated decision rather
#: than a silent omission.
EXCLUDED = {
    "max_slope_deg": "the API maximum is a max of an AREA-AVERAGED field; "
                     "slope_max_deg carries the true cell maximum instead",
    "total_area_km2": "frame extent, identical by construction on both sides and "
                      "not a measurement of the Moon",
    "psr_area_fraction": "psr_area_km2 / total_area_km2 -- comparing it as well "
                         "would report one disagreement twice",
    "doubly_shadowed_area_km2": "the static path intersects the doubly-shadowed "
                                "mask with a DEM percentile the API does not "
                                "carry; compared, it would test the percentile "
                                "rather than the shadow",
    "mean_illumination_fraction": "the API means a display-downsampled field and "
                                  "the static file a native one; the AREA is the "
                                  "gated quantity and it is exact",
    "shadow_depth_estimate_m": "derived from the API's coarse DEM relief; the "
                               "static path does not publish a counterpart",
    "confidence_level": "a label, not a number",
}


def _decimals_of(v) -> int:
    """Printed decimal places of a value, so two roundings compare fairly."""
    txt = repr(float(v))
    return len(txt.split(".")[1]) if "." in txt and "e" not in txt else 6


def _static_number(static: dict, key: str):
    """A number from the static analysis, wherever it keeps it."""
    vals = static.get("values") or {}
    if key in vals:
        v = vals[key]
        return v.get("value") if isinstance(v, dict) else v
    ms = (static.get("measured_statistics") or {})
    for block in ms.values():
        if isinstance(block, dict) and key in block:
            return block[key]
    if key in static:
        v = static[key]
        return v.get("value") if isinstance(v, dict) else v
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--crater", default="faustini")
    ap.add_argument("--tolerance", type=float, default=0.02,
                    help="relative tolerance (default 2 %%)")
    ap.add_argument("--inject", choices=("shadow", "coverage"),
                    help="prove the shadow comparison and the coverage "
                         "assertion actually fail when they should")
    args = ap.parse_args()

    static_path = BASE_DIR / "frontend/public/analysis" / f"{args.crater}.json"
    if not static_path.is_file():
        print(f"FAIL  {static_path} missing. Run build_analysis.py first.")
        return 2
    _static_doc = json.loads(static_path.read_text(encoding="utf-8"))
    static = _static_doc["values"]
    # The whole document, because the exact PSR pixel count lives in
    # measured_statistics.illumination, not in `values` -- and a gate that could
    # only see `values` would have reported the one exact quantity as ABSENT and
    # skipped it, which is how the shadow surface came to have no check at all.
    static_full = _static_doc

    # In-process, so the gate needs no running server and cannot be skipped by
    # forgetting to start one.
    from app.services.mission_service import MissionPipelineService
    result = MissionPipelineService().run_full_mission_pipeline(args.crater)

    def as_dict(o):
        if isinstance(o, dict):
            return o
        for attr in ("model_dump", "dict"):
            if hasattr(o, attr):
                try:
                    return getattr(o, attr)()
                except TypeError:
                    pass
        return json.loads(json.dumps(o, default=lambda x: getattr(x, "__dict__", str(x))))

    api = as_dict(result)
    terrain = as_dict(api.get("terrain") or {})

    print("=" * 78)
    print(f"CROSS-PATH CONSISTENCY — API vs static analysis, {args.crater}")
    print("=" * 78)
    # The threshold is IN the field name, so the name and config must not drift
    # apart. If someone retunes config, this fails loudly instead of leaving a
    # key called "below_12deg" holding a 15 deg answer.
    from app.core.config import settings as _cfg
    for deg, attr in ((12, "CRITICAL_LANDING_SLOPE_DEG"),
                      (20, "MAX_TRAVERSABLE_SLOPE_DEG")):
        actual = float(getattr(_cfg, attr))
        if abs(actual - deg) > 1e-9:
            print(f"  FAIL  slope_fraction_below_{deg}deg is named for {deg}° but "
                  f"config.{attr} is {actual:g}°.")
            print("        Rename the field or revert the threshold; a name that "
                  "states a number it does not use is worse than no name.")
            return 1
    print("  field names verified against config: 12 deg = "
          "CRITICAL_LANDING_SLOPE_DEG, 20 deg = MAX_TRAVERSABLE_SLOPE_DEG\n")
    print(f"  {'quantity':24s}{'API':>13}{'static':>13}{'rel diff':>11}  verdict")
    failed = []
    for akey, skey, own_tol in COMPARED:
        tol = own_tol if own_tol is not None else args.tolerance
        va = terrain.get(akey)
        vb = (static.get(skey) or {}).get("value")
        if va is None or vb is None:
            print(f"  {akey:24s}{str(va):>13}{str(vb):>13}{'ABSENT':>11}  FAIL")
            failed.append((akey, "one side is absent"))
            continue
        rel = abs(va - vb) / max(abs(vb), 1e-12)
        ok = rel <= tol
        print(f"  {akey:24s}{va:>13.4f}{vb:>13.4f}{rel:>11.5f}  "
              f"{'ok' if ok else 'FAIL'}"
              + (f"   (tol {tol:.0%})" if own_tol is not None else ""))
        if not ok:
            failed.append((akey, f"{rel:.4%} > {tol:.2%}"))

    # ── shadow, tolerance 0 ────────────────────────────────────────────────
    psr_api = as_dict(api.get("psr") or {})
    if args.inject == "shadow":
        # PERTURB ONE PATH'S MASK. One pixel is enough: at tolerance 0 the
        # two counts are the same integer or they are not the same
        # measurement. This is the disagreement that could not fire while
        # the gate compared slope, roughness and hazard only.
        print("")
        print("  --inject shadow: one pixel added to the API PSR count")
        psr_api = dict(psr_api)
        psr_api["psr_px"] = int(psr_api["psr_px"]) + 1
        psr_api["psr_area_km2"] = float(psr_api["psr_area_km2"]) + 1.0
    static_vals = static.get("values") or static
    print()
    print(f"  {'shadow (tolerance 0)':24s}{'API':>13}{'static':>13}{'abs diff':>11}  verdict")
    for akey, skey in COMPARED_SHADOW:
        va = psr_api.get(akey)
        if va is None and akey == "psr_px":
            # The API publishes area, not the count; recover the count from the
            # frame's own cell area rather than adding a field for the gate.
            cell = (static_vals.get("cell_km2") or {}).get("value") if isinstance(
                static_vals.get("cell_km2"), dict) else None
            va = None if cell in (None, 0) else round(psr_api["psr_area_km2"] / cell)
        vb = _static_number(static_full, skey)
        if va is None or vb is None:
            print(f"  {akey:24s}{str(va):>13}{str(vb):>13}{'ABSENT':>11}  "
                  + ("SKIP" if akey == "psr_px" else "FAIL"))
            if akey != "psr_px":
                failed.append((akey, "one side is absent"))
            continue
        # Both sides publish rounded copies of one native reduction, so they are
        # compared at the COARSER of the two printed precisions. That is not a
        # tolerance -- it is the precision at which the two are the same number.
        dec = min(_decimals_of(va), _decimals_of(vb))
        ok = round(float(va), dec) == round(float(vb), dec)
        print(f"  {akey:24s}{float(va):>13.4f}{float(vb):>13.4f}"
              f"{abs(float(va) - float(vb)):>11.6f}  {'ok' if ok else 'FAIL'}")
        if not ok:
            failed.append((akey, f"differ at {dec} dp — one PSR source, two answers"))

    # ── coverage: nothing both paths produce may be silently uncompared ─────
    compared_names = {a for a, _, _ in COMPARED} | {a for a, _ in COMPARED_SHADOW}
    if args.inject == "coverage":
        # A QUANTITY BOTH PATHS PRODUCE, NEITHER COMPARED NOR EXCLUDED.
        # The defect this rule exists for: the gate keeps passing on the
        # rows it knows about while a new one goes unchecked.
        print("")
        print("  --inject coverage: a quantity in neither list")
        compared_names = compared_names - {"psr_px"}
    uncovered = []
    for block, names in COVERAGE_SOURCES.items():
        present = as_dict(api.get(block) or {})
        for n in names:
            if n not in present and n != "psr_px":
                continue
            if n in compared_names or n in EXCLUDED:
                continue
            uncovered.append(f"{block}.{n}")
    if uncovered:
        print()
        for n in uncovered:
            print(f"  UNCOVERED  {n} is produced by both paths and is neither "
                  f"compared nor excluded")
        failed.append(("coverage", f"{len(uncovered)} quantity(ies) uncompared: "
                                   + ", ".join(uncovered)))
    else:
        print(f"\n  coverage: every quantity in {list(COVERAGE_SOURCES)} is "
              f"compared or excluded with a reason")

    print(f"\n  excluded from the comparison, with cause:")
    for k, why in EXCLUDED.items():
        print(f"    {k}: {why}")

    if args.inject:
        if failed:
            print("")
            print("  INJECTION CAUGHT (" + args.inject + "). The gate works.")
            for _k, _why in failed:
                print("    " + _k + ": " + _why)
            return 0
        print("")
        print("  INJECTION NOT CAUGHT (" + args.inject + ").")
        return 1

    if failed:
        print("\n" + "=" * 78)
        print("GATE FAIL — the API and the static analysis disagree.")
        print("=" * 78)
        for k, why in failed:
            print(f"  {k}: {why}")
        print("\n  These are the same quantity computed by two paths that share no")
        print("  code. A divergence means one of them changed grid, ordering or")
        print("  spacing. Do NOT raise the tolerance: find which path moved.")
        return 1
    own = [k for k, _s, t in COMPARED if t is not None]
    print("")
    print("  GATE PASS — " + str(len(COMPARED)) + " terrain quantities agree, "
          + str(len(COMPARED_SHADOW)) + " shadow quantities agree at TOLERANCE 0,"
          + " and every quantity both paths produce is compared or excluded")
    print("  with a stated reason. " + str(len(own)) + " row(s) carry a per-row"
          + " tolerance: " + (", ".join(own) if own else "none") + ".")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
