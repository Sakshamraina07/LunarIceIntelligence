"""
Look at the ground under each Phase 3 site, and say whether it is featureless.

The latitude test (roughness_vs_latitude.py) asks a question about the FRAME.
This asks it about the five pixels that were actually chosen: what does the
terrain look like around each one, is it smooth in a way real ground is smooth,
and does it sit in a band where interpolated smoothness is over-represented.

Three things per site:
  * local statistics in a 1 km box -- slope, roughness, elevation range;
  * the LOCAL RANK of the site's roughness within that box, because a site that
    is the smoothest thing for a kilometre around is a different claim from one
    that sits in uniformly smooth ground;
  * PLANARITY. Fit a plane to the 1 km box and report the RMS residual. A real
    crater floor has metres of micro-relief about its mean plane. Terrain
    interpolated between distant laser tracks is close to exactly planar,
    because a plane is roughly what the interpolator drew. This is the test that
    separates "genuinely flat" from "no data here".

Usage:
    python -u backend/scripts/inspect_sites.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import tifffile
from scipy.ndimage import uniform_filter

BASE_DIR = Path(__file__).resolve().parents[2]
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

NATIVE = BASE_DIR / "data/pradan/native"
BOX = 40          # +/- 40 px at 25 m = a 2 km box


def plane_rms(z: np.ndarray) -> float:
    """RMS residual after removing the best-fit plane."""
    ny, nx = z.shape
    yy, xx = np.mgrid[0:ny, 0:nx]
    A = np.column_stack([xx.ravel(), yy.ravel(), np.ones(z.size)])
    coef, *_ = np.linalg.lstsq(A, z.ravel(), rcond=None)
    return float(np.sqrt((((A @ coef) - z.ravel()) ** 2).mean()))


def main() -> int:
    sites = json.loads((BASE_DIR / "docs/landing_sites.json").read_text(encoding="utf-8"))
    dem = np.asarray(tifffile.imread(str(NATIVE / "dem_native.tif")), dtype=np.float64)
    dy, dx = np.gradient(dem, 25.0, 25.0)
    slope = np.degrees(np.arctan(np.hypot(dx, dy)))
    m = uniform_filter(dem, size=5)
    rough = np.sqrt(np.maximum(0.0, uniform_filter(dem ** 2, size=5) - m * m))

    print("=" * 78)
    print("THE GROUND UNDER EACH SITE — is it flat, or is it empty?")
    print("=" * 78)
    print(f"  frame medians: slope {np.median(slope):.3f} deg, "
          f"roughness {np.median(rough):.3f} m, "
          f"plane-fit RMS over a random 2 km box is the reference below\n")

    # A reference distribution of plane-fit RMS, from boxes sampled at random
    # across the frame, so "1.4 m" has something to be compared against.
    rng = np.random.default_rng(20200808)
    ref = []
    for _ in range(200):
        r0 = int(rng.integers(BOX, dem.shape[0] - BOX))
        c0 = int(rng.integers(BOX, dem.shape[1] - BOX))
        ref.append(plane_rms(dem[r0 - BOX:r0 + BOX, c0 - BOX:c0 + BOX]))
    ref = np.array(ref)
    print(f"  reference plane-fit RMS over 200 random 2 km boxes: "
          f"p05 {np.percentile(ref, 5):.2f} m  p50 {np.percentile(ref, 50):.2f} m  "
          f"p95 {np.percentile(ref, 95):.2f} m\n")

    print(f"  {'#':>2}{'lat':>10}{'slope':>8}{'rough':>8}"
          f"{'box rough p50':>15}{'local rank':>12}{'plane RMS':>11}{'vs ref p05':>12}")
    out = []
    for s in sites["sites"]:
        li, sa = s["grid"]["line"], s["grid"]["sample"]
        r0, r1 = max(0, li - BOX), min(dem.shape[0], li + BOX)
        c0, c1 = max(0, sa - BOX), min(dem.shape[1], sa + BOX)
        box = dem[r0:r1, c0:c1]
        br = rough[r0:r1, c0:c1]
        prms = plane_rms(box)
        rank = float((br < rough[li, sa]).mean())
        rec = {"rank": s["rank"], "lat": s["lat_deg"], "lon": s["lon_deg"],
               "slope_deg": float(slope[li, sa]), "roughness_m": float(rough[li, sa]),
               "box_rough_p50": float(np.median(br)),
               "local_rank_pct": rank * 100.0,
               "plane_rms_m": prms,
               "plane_rms_vs_ref_p05": prms / float(np.percentile(ref, 5))}
        out.append(rec)
        print(f"  {s['rank']:>2}{s['lat_deg']:>10.4f}{rec['slope_deg']:>8.3f}"
              f"{rec['roughness_m']:>8.3f}{rec['box_rough_p50']:>15.3f}"
              f"{rank * 100:>11.1f}%{prms:>11.2f}{rec['plane_rms_vs_ref_p05']:>12.2f}")

    print("\n  local rank = fraction of the 2 km box smoother than the site itself.")
    print("  A site at ~0 % is the smoothest thing for a kilometre around;")
    print("  a site in uniformly smooth ground would sit mid-range.\n")

    worst = min(r["plane_rms_m"] for r in out)
    print("=" * 78)
    print("VERDICT")
    print("=" * 78)
    if worst < 0.5 * float(np.percentile(ref, 5)):
        print(f"  The flattest site's 2 km box fits a plane to {worst:.2f} m RMS,")
        print(f"  far below the 5th percentile of random boxes "
              f"({np.percentile(ref, 5):.2f} m). Terrain that is that close to a")
        print("  plane over 2 km is what an interpolator draws between distant")
        print("  tracks, not what a crater floor looks like. TREAT AS SUSPECT.")
    else:
        print(f"  The flattest site's 2 km box fits a plane to {worst:.2f} m RMS")
        print(f"  against a random-box p05 of {np.percentile(ref, 5):.2f} m. These")
        print("  sites are smooth, but they carry micro-relief about their mean")
        print("  plane in the same way ordinary ground does -- they are not the")
        print("  featureless planes an interpolation gap would produce.")
    (BASE_DIR / "docs/site_inspection.json").write_text(json.dumps({
        "reference_plane_rms_p05": float(np.percentile(ref, 5)),
        "reference_plane_rms_p50": float(np.percentile(ref, 50)),
        "box_km": BOX * 2 * 25 / 1000.0, "sites": out}, indent=2), encoding="utf-8")
    print("\n  wrote docs/site_inspection.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
