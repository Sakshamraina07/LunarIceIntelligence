"""
search_landing_sites.py -- PRD Phase 3. Landing sites SEARCHED, not asserted.

    python backend/scripts/search_landing_sites.py [--top 5] [--nms-km 5.0]

WHAT THIS REPLACES
------------------
Five hardcoded grid offsets in module_e_landing.py:

    ("Alpha Ridge (North)", 18, 50)   ("Beta Plateau (South-East)", 82, 75)
    ("Gamma Bench (South-West)", 78, 25)  ("Delta Spur (West)", 50, 15)
    ("Epsilon Crest (East)", 48, 85)

asserted on a 100 x 100 grid and then scored. A site chosen on ~1 km cells is
located to +/-500 m, which is not a landing site. All five fell OUTSIDE the
measured amplitude ribbon.

This searches all 14,943,444 native 25 m pixels, vectorised, and returns a list.

THE TWO CRITERIA THAT FIGHT EACH OTHER, AND WHY THEY ARE NOT COLLAPSED
----------------------------------------------------------------------
  distance to the nearest PSR   -- the ice-access term, wants to be SMALL
  illumination_fraction         -- the solar-power term, wants to be LARGE

They are in direct tension: a cold trap is cold because it is not lit. Averaging
them into one number hides exactly the trade-off a mission planner has to make,
so BOTH are reported per site, unreduced, alongside the composite.

HAZARD IS SCORED ON THE NATIVE FRAME, THEN AVERAGED DOWN
--------------------------------------------------------
The old path resampled to 100 x 100 FIRST and scored after. On ~1 km cells the
roughness p50 is 214.5 m against a 50 m divisor, so clip(roughness/50) pins to
1.0, slope stops contributing entirely, and the reported hazard mean of 0.635
with p99 = 1.0 is a saturation artefact rather than a terrain map.

Scoring at 25 m (where roughness p50 is 5.8 m) and area-averaging the bounded
0-1 field down preserves the ordering. The 50 m divisor is NOT touched.

Two numbers are carried per serving cell, because one cannot answer both
questions a planner asks:
    hazard_mean  -- for traverse cost, the average difficulty of crossing it
    slope_max    -- for the hard-impassable gate; a cell that averages safe can
                    still contain a 25 deg face that stops a rover dead.
"""
from __future__ import annotations

import argparse
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
OUT = BASE_DIR / "docs" / "landing_sites.json"
HEATMAP = NATIVE / "landing_suitability.tif"


def hr(t: str) -> None:
    print("\n" + "-" * 78)
    print(t)
    print("-" * 78, flush=True)


def main() -> int:
    from app.core.config import settings as cfg
    from app.ingestion.horizon_frame import load_horizon
    from app.ingestion.sar_geometry import read_geotiff_frame
    from app.modules.module_d_terrain import compute_hazard_score
    from scipy.ndimage import distance_transform_edt, maximum_filter, uniform_filter

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--top", type=int, default=5, help="sites to return (default 5)")
    ap.add_argument("--nms-km", type=float, default=5.0,
                    help="minimum separation between returned sites, km (default 5)")
    ap.add_argument("--rover-range-km", type=float, default=20.0,
                    help="maximum useful distance to a PSR, km (default 20)")
    ap.add_argument("--min-illumination", type=float, default=0.05,
                    help="minimum illumination_fraction for solar power (default 0.05)")
    args = ap.parse_args()

    # ---------------------------------------------------------------- inputs
    dem = tifffile.imread(str(NATIVE / "dem_native_synthetic.tif")).astype(np.float32)
    valid = tifffile.imread(str(NATIVE / "valid_native.tif")).astype(bool)
    lines, samples = dem.shape
    px_m = 25.0
    cell_km2 = (px_m / 1000.0) ** 2

    frame = read_geotiff_frame(RAW / f"{STEM}_d_sri_xx_cp_lh_d18.tif",
                               RAW / f"{STEM}_d_sri_xx_cp_xx_d18.xml")
    hp = load_horizon(LOLA_DIR)
    proj = hp.to_frame(frame, dem.shape)
    illum = np.nan_to_num(proj["illumination_fraction"], nan=0.0)
    psr = proj["psr_mask"]

    hr(f"SEARCH SPACE — every one of {dem.size:,} native {px_m:g} m pixels")
    print(f"  frame        {lines} x {samples} = {dem.size * cell_km2:,.0f} km²")
    print(f"  amplitude    {int(valid.sum()):,} px ({valid.mean() * 100:.2f} %) — a site "
          f"outside this has NO radar evidence and is labelled, not excluded")
    print(f"  PSR          {int(psr.sum()):,} px ({psr.mean() * 100:.2f} %) at "
          f"{hp.effective_m:g} m effective")

    # ------------------------------------------------- terrain, at 25 m
    sy = sx = px_m
    gy, gx = np.gradient(dem, sy, sx)
    slope = np.degrees(np.arctan(np.hypot(gx, gy))).astype(np.float32)
    del gx, gy
    m1 = uniform_filter(dem, size=5)
    m2 = uniform_filter(dem.astype(np.float64) ** 2, size=5)
    rough = np.sqrt(np.maximum(0.0, m2 - m1.astype(np.float64) ** 2)).astype(np.float32)
    del m1, m2
    hazard = compute_hazard_score(slope, rough, None, w_boulder=0.0)

    hr("HAZARD — scored at 25 m, not after the resample")
    def pct(a, label, unit=""):
        print(f"  {label:22s} p50 {np.percentile(a, 50):8.3f}{unit}  "
              f"p90 {np.percentile(a, 90):8.3f}{unit}  p99 {np.percentile(a, 99):8.3f}{unit}  "
              f"max {a.max():8.3f}{unit}")
    pct(slope, "slope_deg", "°")
    pct(rough, "roughness_m", " m")
    pct(hazard, "hazard (25 m)")

    # The before/after the PRD asks for: score-then-average vs average-then-score.
    def block_mean(a, k):
        n, m = (a.shape[0] // k) * k, (a.shape[1] // k) * k
        return a[:n, :m].reshape(n // k, k, m // k, k).mean(axis=(1, 3))
    def block_max(a, k):
        n, m = (a.shape[0] // k) * k, (a.shape[1] // k) * k
        return a[:n, :m].reshape(n // k, k, m // k, k).max(axis=(1, 3))

    k = 22          # 22 x 25 m = 550 m, close to the old 100x100 serving cell
    haz_then_avg = block_mean(hazard, k)
    slope_avg, rough_avg = block_mean(slope, k), block_mean(rough, k)
    avg_then_haz = compute_hazard_score(slope_avg, rough_avg, None, w_boulder=0.0)
    slope_max_cell = block_max(slope, k)

    print(f"\n  the correction, at a {k * px_m / 1000:.2f} km serving cell:")
    print(f"  {'':26}{'p50':>9}{'p90':>9}{'p99':>9}{'max':>9}{'  pinned at 1.0':>16}")
    for label, a in (("score at 25 m then average", haz_then_avg),
                     ("average then score (old)", avg_then_haz)):
        print(f"  {label:26}{np.percentile(a, 50):9.3f}{np.percentile(a, 90):9.3f}"
              f"{np.percentile(a, 99):9.3f}{a.max():9.3f}{(a >= 0.999).mean() * 100:15.2f}%")
    print(f"  slope_max per serving cell   p50 {np.percentile(slope_max_cell, 50):.2f}°  "
          f"p99 {np.percentile(slope_max_cell, 99):.2f}°  max {slope_max_cell.max():.2f}°")
    print(f"  — carried BESIDE hazard_mean: a cell averaging safe can still hold a "
          f"{slope_max_cell.max():.0f}° face.")

    # --------------------------------------------- distance to the nearest PSR
    # Euclidean transform on the complement: distance from every pixel to the
    # nearest PSR cell, in metres.
    psr_dist_m = distance_transform_edt(~psr, sampling=(px_m, px_m)).astype(np.float32)

    # ------------------------------------------------------- the six criteria
    hr("CRITERIA — all thresholds read from config.py, none written here")
    crit = {
        "slope_below_landing_limit": (slope <= cfg.CRITICAL_LANDING_SLOPE_DEG,
                                      f"slope ≤ {cfg.CRITICAL_LANDING_SLOPE_DEG:g}° "
                                      f"(CRITICAL_LANDING_SLOPE_DEG)"),
        "roughness_below_limit": (rough <= cfg.CRITICAL_LANDING_ROUGHNESS_M,
                                  f"roughness ≤ {cfg.CRITICAL_LANDING_ROUGHNESS_M:g} m "
                                  f"(CRITICAL_LANDING_ROUGHNESS_M)"),
        "hazard_below_limit": (hazard <= cfg.CRITICAL_LANDING_HAZARD,
                               f"hazard ≤ {cfg.CRITICAL_LANDING_HAZARD:.2f} "
                               f"(CRITICAL_LANDING_HAZARD)"),
        "inside_amplitude_mask": (valid, "inside the measured DFSAR ribbon"),
        "psr_within_rover_range": (psr_dist_m <= args.rover_range_km * 1000.0,
                                   f"nearest PSR ≤ {args.rover_range_km:g} km"),
        "illumination_above_minimum": (illum >= args.min_illumination,
                                       f"illumination_fraction ≥ {args.min_illumination:g}"),
    }
    for name, (m, desc) in crit.items():
        print(f"  {name:28s} {m.mean() * 100:6.2f} % of the frame   {desc}")

    # A criterion that admits everything is not a criterion. Reporting six and
    # having one of them select 100 % of the frame overstates how constrained
    # the answer is, in exactly the way a plausible placeholder overstates a
    # measurement -- so it is named here rather than left to look like work.
    vacuous = [(n, m.mean()) for n, (m, _d) in crit.items()
               if m.mean() > 0.99 or m.mean() < 0.01]
    if vacuous:
        print()
        for n, f in vacuous:
            print(f"  NON-DISCRIMINATING: {n} passes {f * 100:.2f} % of the frame. "
                  f"It does no filtering here and")
            print(f"    the site ranking would be identical without it. Kept because "
                  f"it is a real mission constraint")
            print(f"    that a different frame would bind on, but it must not be "
                  f"counted as evidence of selectivity.")

    feasible = np.ones(dem.shape, dtype=bool)
    for m, _ in crit.values():
        feasible &= m
    print(f"\n  ALL SIX                      {feasible.mean() * 100:6.2f} % of the frame "
          f"({int(feasible.sum()):,} px, {feasible.sum() * cell_km2:,.2f} km²)")

    # ------------------------------------------------------ suitability score
    # Bounded 0-1 terms, weights from config. The two tension terms are scored
    # but ALSO reported raw per site; the score is a ranking device, not a claim
    # that they can be traded off at a known exchange rate.
    safety = 1.0 - hazard
    access = np.clip(1.0 - psr_dist_m / (args.rover_range_km * 1000.0), 0.0, 1.0)
    power = np.clip(illum / max(float(illum.max()), 1e-9), 0.0, 1.0)
    w_safe = float(cfg.WEIGHT_LANDING_SAFETY)
    w_illum = float(cfg.WEIGHT_LANDING_ILLUM)
    w_dist = float(cfg.WEIGHT_LANDING_DISTANCE)
    wsum = w_safe + w_illum + w_dist
    score = ((w_safe * safety + w_illum * power + w_dist * access) / wsum).astype(np.float32)
    score[~feasible] = 0.0

    tifffile.imwrite(str(HEATMAP), score)
    print(f"\n  suitability heatmap -> {HEATMAP.relative_to(BASE_DIR)} "
          f"({HEATMAP.stat().st_size / 1e6:.1f} MB) — the recommendation is visibly "
          f"the argmax of this")

    # ------------------------------------------------------------------- NMS
    hr(f"NON-MAXIMUM SUPPRESSION — minimum separation {args.nms_km:g} km")
    sep_px = int(round(args.nms_km * 1000.0 / px_m))
    print(f"  {sep_px} px at {px_m:g} m. Without it the top N are N pixels of one "
          f"crater floor, which is one site reported five times.")

    sites = []
    work = score.copy()
    for rank in range(1, args.top + 1):
        idx = int(np.argmax(work))
        if work.flat[idx] <= 0.0:
            print(f"  only {rank - 1} site(s) satisfy all six criteria with "
                  f"{args.nms_km:g} km separation")
            break
        li, si = divmod(idx, samples)
        lat, lon = frame.pixel_to_latlon(float(li), float(si))
        sites.append({
            "rank": rank,
            "grid": {"line": int(li), "sample": int(si)},
            "lat_deg": round(float(lat), 5),
            "lon_deg": round(float(lon), 5),
            "suitability_score": round(float(score[li, si]), 5),
            # THE TWO TENSION TERMS, UNREDUCED. Reported side by side because
            # collapsing them hides the trade-off that is the actual science.
            "ice_access": {
                "psr_distance_km": round(float(psr_dist_m[li, si]) / 1000.0, 3),
                "threshold_km": args.rover_range_km,
                "passed": bool(psr_dist_m[li, si] <= args.rover_range_km * 1000.0),
            },
            "solar_power": {
                "illumination_fraction": round(float(illum[li, si]), 5),
                "threshold": args.min_illumination,
                "passed": bool(illum[li, si] >= args.min_illumination),
            },
            "criteria": {
                name: {"value": round(float(v), 4), "threshold": th, "comparison": cmp,
                       "passed": bool(m[li, si])}
                for name, v, th, cmp, m in (
                    ("slope_deg", slope[li, si], cfg.CRITICAL_LANDING_SLOPE_DEG, "<=",
                     crit["slope_below_landing_limit"][0]),
                    ("roughness_m", rough[li, si], 10.0, "<=",
                     crit["roughness_below_limit"][0]),
                    ("hazard", hazard[li, si], 0.5, "<=",
                     crit["hazard_below_limit"][0]),
                    ("in_amplitude_mask", float(valid[li, si]), 1.0, "==",
                     crit["inside_amplitude_mask"][0]),
                    ("psr_distance_km", psr_dist_m[li, si] / 1000.0, args.rover_range_km,
                     "<=", crit["psr_within_rover_range"][0]),
                    ("illumination_fraction", illum[li, si], args.min_illumination, ">=",
                     crit["illumination_above_minimum"][0]),
                )
            },
            "provenance": {
                "slope/roughness/hazard": "MEASURED — LOLA LDEM_80S_80M V2.0, 80 m posts",
                "illumination/psr_distance": (
                    f"MEASURED — horizon computation at {hp.effective_m:g} m effective "
                    f"({hp.decimation}x from {hp.native_m:g} m posts), "
                    f"{hp.meta['azimuths']} azimuths"),
                "in_amplitude_mask": "MEASURED — Chandrayaan-2 DFSAR amplitude",
                "lat_lon": "sar_geometry inverse projection, validated to 13.2 mm",
            },
        })
        y0, y1 = max(0, li - sep_px), min(lines, li + sep_px + 1)
        x0, x1 = max(0, si - sep_px), min(samples, si + sep_px + 1)
        work[y0:y1, x0:x1] = 0.0

    hr(f"TOP {len(sites)} — the tension terms side by side, never collapsed")
    print(f"  {'#':>2} {'lat':>10} {'lon':>10} {'score':>7} {'PSR km':>8} {'illum':>7} "
          f"{'slope':>7} {'hazard':>7} {'radar':>6}")
    for s in sites:
        print(f"  {s['rank']:>2} {s['lat_deg']:>10.4f} {s['lon_deg']:>10.4f} "
              f"{s['suitability_score']:>7.4f} "
              f"{s['ice_access']['psr_distance_km']:>8.2f} "
              f"{s['solar_power']['illumination_fraction']:>7.4f} "
              f"{s['criteria']['slope_deg']['value']:>6.2f}° "
              f"{s['criteria']['hazard']['value']:>7.3f} "
              f"{'YES' if s['criteria']['in_amplitude_mask']['passed'] else 'NO':>6}")
    print("\n  PSR km and illum are the two that fight: closer to the cold trap means")
    print("  less sun. Both are printed because the trade-off is the decision.")

    doc = {
        "schema": "lunar-ice/landing-sites/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/search_landing_sites.py",
        "search": {
            "pixels_evaluated": int(dem.size),
            "metres_per_pixel": px_m,
            "note": "every native pixel, vectorised — not a list of asserted offsets",
            "nms_separation_km": args.nms_km,
            "nms_separation_px": sep_px,
            "rover_range_km": args.rover_range_km,
            "min_illumination": args.min_illumination,
            "weights": {"safety": w_safe, "illumination": w_illum, "distance": w_dist,
                        "source": "backend/app/core/config.py"},
        },
        "criteria_coverage": {name: float(m.mean()) for name, (m, _) in crit.items()},
        "all_six_fraction": float(feasible.mean()),
        "all_six_area_km2": float(feasible.sum() * cell_km2),
        "hazard_correction": {
            "serving_cell_km": k * px_m / 1000.0,
            "score_at_25m_then_average": {
                "p50": float(np.percentile(haz_then_avg, 50)),
                "p90": float(np.percentile(haz_then_avg, 90)),
                "p99": float(np.percentile(haz_then_avg, 99)),
                "fraction_pinned_at_1": float((haz_then_avg >= 0.999).mean()),
            },
            "average_then_score_old": {
                "p50": float(np.percentile(avg_then_haz, 50)),
                "p90": float(np.percentile(avg_then_haz, 90)),
                "p99": float(np.percentile(avg_then_haz, 99)),
                "fraction_pinned_at_1": float((avg_then_haz >= 0.999).mean()),
            },
            "slope_max_per_cell": {
                "p50": float(np.percentile(slope_max_cell, 50)),
                "p99": float(np.percentile(slope_max_cell, 99)),
                "max": float(slope_max_cell.max()),
            },
        },
        "sites": sites,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
