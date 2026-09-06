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

#: Named, with the reason, so that excluding them is a stated decision rather
#: than a silent omission.
EXCLUDED = {
    "max_slope_deg": "the API maximum is a max of an AREA-AVERAGED field; "
                     "slope_max_deg carries the true cell maximum instead",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--crater", default="faustini")
    ap.add_argument("--tolerance", type=float, default=0.02,
                    help="relative tolerance (default 2 %%)")
    args = ap.parse_args()

    static_path = BASE_DIR / "frontend/public/analysis" / f"{args.crater}.json"
    if not static_path.is_file():
        print(f"FAIL  {static_path} missing. Run build_analysis.py first.")
        return 2
    static = json.loads(static_path.read_text(encoding="utf-8"))["values"]

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

    print(f"\n  excluded from the comparison, with cause:")
    for k, why in EXCLUDED.items():
        print(f"    {k}: {why}")

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
    print(f"\n  GATE PASS — {len(COMPARED)} quantities agree: "
          f"{len(COMPARED) - len(own)} within the default {args.tolerance:.2%}"
          + (f", and {len(own)} within a stated per-row tolerance "
             f"({', '.join(own)})." if own else "."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
