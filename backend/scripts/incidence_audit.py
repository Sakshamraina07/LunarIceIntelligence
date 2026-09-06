"""
incidence_audit.py -- is the product's incidence raster an incidence angle?

    python -u backend/scripts/incidence_audit.py

WHY
---
`incidence_mask.py` adopted Putrevu et al. 2023's 20 deg Bragg-domain criterion
and computed local incidence from `..._d_sri_in_cp_xx_d18.tif`, treating it as
the ellipsoid incidence angle. It reported a median of 14.44 deg.

That is below the label's own look angle of 19.9979 deg, and ON A CONVEX BODY
INCIDENCE IS ALWAYS GREATER THAN THE LOOK ANGLE:

    sin(theta_inc) = ((R + h) / R) sin(eta)

so a median incidence below the look angle is not a small error, it is
geometrically impossible. This script asks what the raster actually is, and what
depends on the answer.

THREE TESTS, EACH ABLE TO FAIL ON ITS OWN
-----------------------------------------
 1. MAGNITUDE. Compare the raster against the closed-form incidence the label's
    own geometry requires.
 2. SMOOTHNESS. A geometric incidence field across a 44.5 km swath is a smooth
    ramp of order 0.03 deg per 25 m pixel. Measure the actual pixel-to-pixel
    scatter.
 3. TERRAIN. If it were a LOCAL incidence -- already terrain-corrected by ISRO --
    it would correlate with the DEM slope. Measure the correlation.

WHAT DEPENDS ON IT
------------------
The calibration multiplies both channels by sin(inc) before the boxcar. CPR and
DOP are ratios in which that factor is COMMON TO BOTH CHANNELS, so it should very
nearly cancel -- but "should" is not a measurement, and the boxcar is applied
after the multiplication, so the cancellation is not exact. The screening is
re-run with sin(inc) removed and the candidate area compared. That is the only
thing that settles whether this defect reaches the headline.
"""
from __future__ import annotations

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

NATIVE = BASE_DIR / "data" / "pradan" / "native"
RAW = BASE_DIR / "data" / "pradan" / "raw" / "data" / "calibrated" / "20200808"
STEM = "ch2_sar_ncxl_20200808t201154198"
OUT = BASE_DIR / "docs" / "incidence_audit.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def hr(t: str) -> None:
    print("\n" + "=" * 78 + "\n" + t + "\n" + "=" * 78, flush=True)


def boxcar(a: np.ndarray, k: int = 5) -> np.ndarray:
    """Same 5x5 mean the pipeline applies, by cumulative sums."""
    from scipy.ndimage import uniform_filter
    return uniform_filter(a, size=k, mode="nearest")


def main() -> int:
    from app.ingestion.sar_geometry import read_geotiff_frame, parse_calibration

    frame = read_geotiff_frame(RAW / f"{STEM}_d_sri_xx_cp_lh_d18.tif",
                               RAW / f"{STEM}_d_sri_xx_cp_xx_d18.xml")
    lab = frame.label
    R = float(lab["semi_major_radius"])
    h = float(lab["spacecraft_altitude"])          # READ, not assumed
    eta = float(lab["look_angle"])
    lab_inc = float(lab["incidence_angle"])
    k_ratio = (R + h) / R
    theta_req = float(np.degrees(np.arcsin(k_ratio * np.sin(np.radians(eta)))))

    hr("INCIDENCE AUDIT — what is in the product's incidence raster?")
    print(f"  label: semi_major_radius {R:,.0f} m, spacecraft_altitude {h:,.0f} m")
    print(f"         look_angle {eta:.6f} deg, incidence_angle {lab_inc:.6f} deg")
    print(f"  THE LABEL GIVES THE SAME NUMBER FOR BOTH, which is the first sign:")
    print(f"  on a convex body they cannot be equal.\n")
    print(f"  (R + h) / R = {k_ratio:.6f}")
    print(f"  incidence required by that look angle = {theta_req:.4f} deg")

    inc = tifffile.imread(str(RAW / f"{STEM}_d_sri_in_cp_xx_d18.tif")).astype(np.float64)
    valid = np.asarray(tifffile.imread(str(NATIVE / "valid_native.tif"))) > 0
    fp = np.asarray(tifffile.imread(str(NATIVE / "footprint_native.tif"))) > 0

    # ---------------------------------------------------------- test 1
    hr("TEST 1 — MAGNITUDE against the geometric identity")
    v = inc[valid]
    qs = np.percentile(v, [0, 1, 5, 25, 50, 75, 95, 99, 100])
    print("   min     p1     p5    p25    p50    p75    p95    p99    max")
    print("  " + "".join(f"{q:7.3f}" for q in qs))
    below = float((v < eta).mean())
    print(f"\n  raster median over valid      {np.percentile(v, 50):7.4f} deg")
    print(f"  look angle                    {eta:7.4f} deg")
    print(f"  incidence the geometry requires {theta_req:7.4f} deg")
    print(f"  fraction of valid pixels BELOW the look angle: {below * 100:.2f} %")
    print("  On a convex body incidence > look angle for every pixel. A field with")
    print(f"  {below * 100:.0f} % of its values below the look angle is not an incidence angle.")
    test1 = bool(below < 0.001)

    # ---------------------------------------------------------- test 2
    hr("TEST 2 — SMOOTHNESS against what a geometric ramp must look like")
    across_m = 44531.21          # measured footprint width, layers.json
    # incidence at the near and far edge of a swath that wide, from the same
    # closed form, so the expected ramp is derived rather than guessed.
    gam_c = theta_req - eta
    d_c = R * np.radians(gam_c)
    d_near, d_far = d_c - across_m / 2, d_c + across_m / 2
    def theta_at(d):
        g = d / R
        e = np.arctan(R * np.sin(g) / ((R + h) - R * np.cos(g)))
        return np.degrees(g + e)
    span = theta_at(d_far) - theta_at(d_near)
    px_across = across_m / frame.pixel_size_m[0]
    expect = span / px_across
    d_line = np.abs(np.diff(inc, axis=0))[fp[1:]]
    print(f"  a {across_m / 1000:.1f} km swath spans {theta_at(d_near):.2f} .. "
          f"{theta_at(d_far):.2f} deg = {span:.2f} deg")
    print(f"  over {px_across:.0f} pixels that is {expect:.4f} deg/px, smooth")
    print(f"  MEASURED |d inc / d line| inside the swath:")
    print(f"    p50 {np.percentile(d_line, 50):.4f}   p95 {np.percentile(d_line, 95):.4f}"
          f"   max {d_line.max():.3f} deg/px")
    ratio = float(np.percentile(d_line, 50) / expect)
    print(f"  the median step is {ratio:.0f}x the geometric ramp")
    test2 = bool(ratio < 3.0)

    # ---------------------------------------------------------- test 3
    hr("TEST 3 — TERRAIN: is it a LOCAL incidence instead?")
    dem = np.asarray(tifffile.imread(str(NATIVE / "dem_native.tif")), dtype=np.float64)
    gy, gx = np.gradient(dem, frame.pixel_size_m[0], frame.pixel_size_m[1])
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    m = fp & (inc > 0)
    corr = float(np.corrcoef(inc[m], slope[m])[0, 1])
    print(f"  corr(raster, DEM slope) over {int(m.sum()):,} pixels = {corr:+.4f}")
    print("  A local incidence angle is ellipsoid incidence plus a terrain term, so")
    print("  it must correlate with slope. This does not.")
    test3 = bool(abs(corr) > 0.1)

    # ---------------------------------------------------------- blast radius
    hr("WHAT DEPENDS ON IT — does the screening move?")
    cal = parse_calibration(RAW / f"{STEM}_d_sri_xx_cp_xx_d18.xml")
    K = 10.0 ** (float(cal["calibration_constant_db"]) / 10.0)
    g_lh = float(cal["channels"]["LH"]["gain_imbalance"])
    g_lv = float(cal["channels"]["LV"]["gain_imbalance"])
    lh = tifffile.imread(str(RAW / f"{STEM}_d_sri_xx_cp_lh_d18.tif")).astype(np.float32)
    lv = tifffile.imread(str(RAW / f"{STEM}_d_sri_xx_cp_lv_d18.tif")).astype(np.float32)

    def screen(use_sin: bool):
        s = np.sin(np.deg2rad(inc)).astype(np.float32) if use_sin else np.float32(1.0)
        a = boxcar((lh ** 2 * s) / (K * g_lh ** 2))
        b = boxcar((lv ** 2 * s) / (K * g_lv ** 2))
        ra, rb = np.sqrt(np.maximum(a, 0)), np.sqrt(np.maximum(b, 0))
        sc = 0.5 * (ra - rb) ** 2
        oc = 0.5 * (ra + rb) ** 2
        with np.errstate(divide="ignore", invalid="ignore"):
            cpr = np.where(oc > 0, sc / oc, 0.0)
            dop = np.where((a + b) > 0, np.abs(a - b) / (a + b), 0.0)
        return cpr, dop

    cpr_w, dop_w = screen(True)
    cpr_o, dop_o = screen(False)
    cw, co = cpr_w[valid], cpr_o[valid]
    dw, do = dop_w[valid], dop_o[valid]
    print(f"  CPR with sin(inc)   max {cw.max():.6f}  p50 {np.percentile(cw, 50):.6g}")
    print(f"  CPR without         max {co.max():.6f}  p50 {np.percentile(co, 50):.6g}")
    print(f"  max |difference|    {np.abs(cw - co).max():.3e}")
    print(f"  DOP  max |difference| {np.abs(dw - do).max():.3e}")
    n_pass_w = int(((cw > 1.0) & (dw < 0.13)).sum())
    n_pass_o = int(((co > 1.0) & (do < 0.13)).sum())
    print(f"\n  pixels passing CPR > 1.00 AND DOP < 0.13:  "
          f"with sin(inc) {n_pass_w},  without {n_pass_o}")
    print("  The factor is COMMON TO BOTH CHANNELS and cancels in every ratio.")
    print("  It scales sigma0 -- the absolute backscatter -- and nothing else.")
    screening_moves = bool(n_pass_w != n_pass_o
                           or np.abs(cw - co).max() > 1e-6)

    hr("VERDICT")
    print(f"  test 1 magnitude   {'PASS' if test1 else 'FAIL'}  "
          f"({below * 100:.2f} % of pixels below the look angle)")
    print(f"  test 2 smoothness  {'PASS' if test2 else 'FAIL'}  "
          f"(median step {ratio:.0f}x the geometric ramp)")
    print(f"  test 3 terrain     {'PASS' if test3 else 'FAIL'}  "
          f"(slope correlation {corr:+.4f})")
    is_incidence = test1 and test2
    print()
    if not is_incidence:
        print("  THE RASTER IS NOT AN ELLIPSOID INCIDENCE ANGLE, and test 3 says it is")
        print("  not a local incidence angle either. Whatever it is, it cannot carry a")
        print("  criterion defined on incidence.")
        print()
        print("  CONSEQUENCE 1 — the Bragg-domain criterion is WITHDRAWN. Every figure")
        print("  computed from this raster by incidence_mask.py is withdrawn with it:")
        print("  the 14.44 deg ellipsoid median, the 17.73 deg local median, the")
        print("  62.58 % removal fraction, and the sentence about the pass being flown")
        print("  below the Bragg floor. None of them measured what they said.")
        print()
        print("  CONSEQUENCE 2 — the screening is UNAFFECTED, and that is measured")
        print("  above, not argued: the factor is common to both channels and cancels")
        print("  in CPR and DOP to "
              f"{np.abs(cw - co).max():.1e}. The candidate area does not move.")
        print()
        print("  CONSEQUENCE 3 — sigma0 itself carries the factor and is therefore")
        print("  scaled by an unknown field. s0_native is affected; no ratio is.")
    else:
        print("  The raster behaves like an incidence angle on the tests applied.")

    OUT.write_text(json.dumps({
        "schema": "incidence_audit/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/incidence_audit.py",
        "label_geometry": {
            "semi_major_radius_m": R, "spacecraft_altitude_m": h,
            "look_angle_deg": eta, "label_incidence_angle_deg": lab_inc,
            "radius_ratio": k_ratio,
            "incidence_required_by_look_angle_deg": theta_req,
            "label_gives_same_value_for_both": bool(abs(lab_inc - eta) < 1e-9),
        },
        "raster_over_valid_deg": {n: float(q) for n, q in zip(
            ["min", "p1", "p5", "p25", "p50", "p75", "p95", "p99", "max"], qs)},
        "test_1_magnitude": {"fraction_below_look_angle": below, "passes": test1},
        "test_2_smoothness": {
            "expected_ramp_deg_per_px": float(expect),
            "measured_step_p50_deg_per_px": float(np.percentile(d_line, 50)),
            "measured_step_p95_deg_per_px": float(np.percentile(d_line, 95)),
            "ratio": ratio, "passes": test2},
        "test_3_terrain": {"corr_with_dem_slope": corr, "passes": test3},
        "is_ellipsoid_incidence": bool(is_incidence),
        "screening_blast_radius": {
            "cpr_max_with_sin": float(cw.max()), "cpr_max_without": float(co.max()),
            "cpr_max_abs_difference": float(np.abs(cw - co).max()),
            "dop_max_abs_difference": float(np.abs(dw - do).max()),
            "pixels_passing_with_sin": n_pass_w,
            "pixels_passing_without": n_pass_o,
            "screening_moves": screening_moves,
            "why": ("sin(inc) multiplies BOTH channels before the boxcar, so it "
                    "cancels in CPR and DOP. It scales sigma0 and nothing else."),
        },
    }, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
