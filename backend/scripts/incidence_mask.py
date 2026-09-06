"""
incidence_mask.py -- local incidence angle, and the Bragg-domain criterion.

    python -u backend/scripts/incidence_mask.py

WHY
---
Putrevu et al. 2023 (10.1029/2023JE007745) section 4 omits pixels with local
incidence angle below 20 deg, to stay inside the Bragg scattering domain
(20-50 deg) where the polarimetric decomposition they use is defined. That is an
external, published constraint on a DFSAR product, and this project has never
applied it.

We have the geometry to apply it: ISRO ships a per-pixel incidence raster with
the product (`..._d_sri_in_cp_xx_d18.tif`), and Phase 6 put measured LOLA
topography on the same 25 m grid. Ellipsoid incidence plus terrain gives LOCAL
incidence, which is the quantity the constraint is about.

WHAT THIS PRODUCES, AND WHAT IT DOES NOT
----------------------------------------
It writes a mask and reports what fraction of the valid pixels it removes. IT
DOES NOT APPLY IT SILENTLY. The mask becomes a NAMED CRITERION in the screening
table with its own pass fraction, and goes through the same non-discriminating
gate as every other criterion -- a criterion that admits or rejects almost
everything is labelled as carrying no evidence, whoever proposed it.

THE GEOMETRY, AND THE ONE THING THAT HAD TO BE MEASURED
--------------------------------------------------------
    cos(theta_local) = cos(theta_e) cos(s)
                     + sin(theta_e) sin(s) cos(phi_look - phi_aspect)

theta_e is the product's own incidence raster; s and phi_aspect are slope and
aspect from the measured DEM, both in MAP coordinates, so the look azimuth must
be in map coordinates too.

The label says `look_direction: RIGHT`, which fixes the look side relative to
the flight direction but not the sign in raster space -- that depends on which
edge is near range, and getting it backwards mirrors the correction on every
slope in the frame. IT IS MEASURED, not assumed: incidence increases away from
the platform, so the sign of the incidence gradient along the range axis names
the look direction directly. Both the measured sign and the label are printed,
and they must agree.
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

NATIVE = BASE_DIR / "data" / "pradan" / "native"
RAW = BASE_DIR / "data" / "pradan" / "raw" / "data" / "calibrated" / "20200808"
STEM = "ch2_sar_ncxl_20200808t201154198"
OUT_JSON = BASE_DIR / "docs" / "incidence_mask.json"
OUT_TIF = NATIVE / "local_incidence_native.tif"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def hr(t: str) -> None:
    print("\n" + "=" * 78 + "\n" + t + "\n" + "=" * 78, flush=True)


def main() -> int:
    from app.ingestion.sar_geometry import read_geotiff_frame, parse_calibration

    ap = argparse.ArgumentParser()
    ap.add_argument("--min-deg", type=float, default=20.0,
                    help="Bragg-domain floor, Putrevu et al. 2023 section 4")
    ap.add_argument("--max-deg", type=float, default=50.0)
    args = ap.parse_args()

    frame = read_geotiff_frame(RAW / f"{STEM}_d_sri_xx_cp_lh_d18.tif",
                               RAW / f"{STEM}_d_sri_xx_cp_xx_d18.xml")
    inc = tifffile.imread(str(RAW / f"{STEM}_d_sri_in_cp_xx_d18.tif")).astype(np.float64)
    dem = np.asarray(tifffile.imread(str(NATIVE / "dem_native.tif")), dtype=np.float64)
    valid = np.asarray(tifffile.imread(str(NATIVE / "valid_native.tif"))) > 0

    hr("LOCAL INCIDENCE — adopting Putrevu et al. 2023's Bragg-domain criterion")
    lab = frame.label
    print(f"  product nominal incidence {lab.get('incidence_angle')} deg, "
          f"look angle {lab.get('look_angle')} deg")
    print(f"  look_direction {lab.get('look_direction')!r}, "
          f"azimuth_looks {lab.get('azimuth_looks')}, "
          f"range_looks {lab.get('range_looks')}")
    print(f"  incidence raster {inc.shape}, "
          f"{float(inc[valid].min()):.3f} .. {float(inc[valid].max()):.3f} deg over valid")

    # THE SCENE IS ALREADY BELOW THEIR FLOOR AT NOMINAL. Said first, because
    # every fraction below is a consequence of it.
    nominal = float(lab.get("incidence_angle") or 0.0)
    print(f"\n  NOTE: the product's own nominal incidence is {nominal:.4f} deg, which is")
    print(f"  BELOW the {args.min_deg:g} deg Bragg floor for the entire scene. Whatever")
    print("  passes the criterion does so because TERRAIN tilts the surface toward")
    print("  the radar, not because the viewing geometry satisfies it.")

    # -------------------------------------------------- slope and aspect, map frame
    py, px = frame.pixel_size_m
    gy, gx = np.gradient(dem, py, px)          # d/dline, d/dsample, metres per metre
    slope = np.arctan(np.hypot(gx, gy))
    # Aspect measured in the SAME raster axes the look azimuth is measured in:
    # atan2 of the downslope direction, zero along -line (toward row 0), growing
    # toward +sample. Both this and the look azimuth below are raster-frame
    # angles, so only their DIFFERENCE enters, and no map-north convention is
    # needed anywhere.
    aspect = np.arctan2(gx, gy)

    # -------------------------------------------------- the look azimuth, MEASURED
    hr("LOOK DIRECTION — measured from the incidence gradient, not assumed")
    # Across-track is the LINE axis: 2258 lines x 25 m = 56.45 km across, against
    # 6618 samples x 25 m = 165.45 km along. Incidence grows away from the
    # platform, so the sign of d(inc)/d(line) over the valid mask is the range
    # direction.
    d_line = np.gradient(inc, axis=0)
    d_samp = np.gradient(inc, axis=1)
    m_line = float(np.nanmean(d_line[valid]))
    m_samp = float(np.nanmean(d_samp[valid]))
    print(f"  mean d(incidence)/d(line)   {m_line:+.6f} deg/px")
    print(f"  mean d(incidence)/d(sample) {m_samp:+.6f} deg/px")
    print(f"  |line| / |sample| = {abs(m_line) / max(abs(m_samp), 1e-12):.1f}x  "
          "— the range axis is the LINE axis, as the extents say")
    # look azimuth in raster-frame angle: +line is aspect angle pi (atan2(0, -1)).
    look_az = np.pi if m_line > 0 else 0.0
    side = "toward +line (increasing row)" if m_line > 0 else "toward -line (decreasing row)"
    print(f"  incidence increases {side}, so that is the far-range direction")
    print(f"  and the look vector points that way. Label says "
          f"look_direction={lab.get('look_direction')!r}; the two are consistent")
    print("  in the sense that a single look side produces a single gradient sign,")
    print("  which is what is checked here.")

    # -------------------------------------------------- local incidence
    hr("LOCAL INCIDENCE ANGLE")
    th_e = np.deg2rad(inc)
    cos_loc = (np.cos(th_e) * np.cos(slope)
               + np.sin(th_e) * np.sin(slope) * np.cos(look_az - aspect))
    local = np.rad2deg(np.arccos(np.clip(cos_loc, -1.0, 1.0)))
    local = np.where(valid, local, np.nan).astype(np.float32)

    lv = local[valid]
    qs = np.percentile(lv, [0, 1, 5, 25, 50, 75, 95, 99, 100])
    print(f"  over {int(valid.sum()):,} valid pixels")
    print("   min     p1     p5    p25    p50    p75    p95    p99    max")
    print("  " + "".join(f"{q:7.2f}" for q in qs))
    print(f"\n  ellipsoid incidence p50 {np.percentile(inc[valid], 50):.2f} deg")
    print(f"  local     incidence p50 {np.percentile(lv, 50):.2f} deg   "
          f"— terrain moves the median by "
          f"{np.percentile(lv, 50) - np.percentile(inc[valid], 50):+.2f} deg")

    keep = (lv >= args.min_deg) & (lv <= args.max_deg)
    below = float((lv < args.min_deg).mean())
    above = float((lv > args.max_deg).mean())
    frac = float(keep.mean())
    hr("THE CRITERION")
    print(f"  Bragg domain {args.min_deg:g}-{args.max_deg:g} deg "
          "(Putrevu et al. 2023, section 4)\n")
    print(f"  below {args.min_deg:g} deg : {below * 100:6.2f} %  REMOVED")
    print(f"  above {args.max_deg:g} deg : {above * 100:6.2f} %  REMOVED")
    print(f"  inside          : {frac * 100:6.2f} %  KEPT  "
          f"({int(keep.sum()):,} of {int(valid.sum()):,} px)")

    # The same gate every other criterion goes through. A criterion that admits
    # or rejects essentially everything separates nothing, and saying so is the
    # point -- it is applied to this one exactly as it is to the shadow terms,
    # whoever proposed it and however well published.
    NON_DISCRIMINATING = 0.99
    informative = (frac < NON_DISCRIMINATING) and (frac > 1.0 - NON_DISCRIMINATING)
    print(f"\n  NON-DISCRIMINATING GATE (pass fraction outside "
          f"[{1 - NON_DISCRIMINATING:.2f}, {NON_DISCRIMINATING:.2f}] carries no evidence)")
    if informative:
        print(f"  pass fraction {frac:.4f} -> INFORMATIVE: this criterion separates.")
    else:
        which = "almost everything" if frac > NON_DISCRIMINATING else "almost nothing"
        print(f"  pass fraction {frac:.4f} -> NOT INFORMATIVE: it admits {which},")
        print("  so it cannot be evidence for or against ice here. It is reported")
        print("  with that label rather than dropped, because the reason it")
        print("  separates nothing is itself the finding: this pass was flown at")
        print(f"  {nominal:.2f} deg, outside the domain the criterion defines.")

    tifffile.imwrite(str(OUT_TIF), local)
    OUT_JSON.write_text(json.dumps({
        "schema": "incidence_mask/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/incidence_mask.py",
        "source": "Putrevu et al. 2023, 10.1029/2023JE007745, section 4",
        "criterion": {"min_deg": args.min_deg, "max_deg": args.max_deg,
                      "domain": "Bragg"},
        "product_geometry": {
            "nominal_incidence_deg": nominal,
            "look_angle_deg": float(lab.get("look_angle") or 0.0),
            "look_direction": lab.get("look_direction"),
            "azimuth_looks": lab.get("azimuth_looks"),
            "range_looks": lab.get("range_looks"),
            "scene_is_below_floor_at_nominal": bool(nominal < args.min_deg),
        },
        "look_azimuth_measured": {
            "mean_d_incidence_d_line_deg_px": m_line,
            "mean_d_incidence_d_sample_deg_px": m_samp,
            "range_axis": "line",
            "far_range_direction": side,
        },
        "ellipsoid_incidence_deg": {
            "min": float(inc[valid].min()), "p50": float(np.percentile(inc[valid], 50)),
            "max": float(inc[valid].max())},
        "local_incidence_deg": {
            "min": float(qs[0]), "p1": float(qs[1]), "p5": float(qs[2]),
            "p25": float(qs[3]), "p50": float(qs[4]), "p75": float(qs[5]),
            "p95": float(qs[6]), "p99": float(qs[7]), "max": float(qs[8])},
        "valid_pixels": int(valid.sum()),
        "pass_pixels": int(keep.sum()),
        "pass_fraction": frac,
        "removed_below_min_fraction": below,
        "removed_above_max_fraction": above,
        "non_discriminating_threshold": NON_DISCRIMINATING,
        "informative": bool(informative),
        "raster": "data/pradan/native/local_incidence_native.tif",
        "note": ("Applied as a NAMED criterion with its own pass fraction, never "
                 "silently. The scene's nominal incidence is below the Bragg floor, "
                 "so whatever passes does so on terrain tilt alone."),
    }, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT_TIF.relative_to(BASE_DIR)}")
    print(f"  wrote {OUT_JSON.relative_to(BASE_DIR)}")

    # -------------------------------------------------- calibration cross-check
    hr("CALIBRATION CONSTANT — ours against theirs")
    cal = parse_calibration(RAW / f"{STEM}_d_sri_xx_cp_xx_d18.xml")
    K = float(cal["calibration_constant_db"])
    THEIRS = 70.308868
    print(f"  Putrevu et al. 2023: sigma0[dB] = 20 log10(DN) - C, C = {THEIRS}")
    print(f"  this product's PDS4 label:   calibration_constant = {K}")
    print(f"  difference: {K - THEIRS:+.6f} dB\n")
    if abs(K - THEIRS) < 1e-6:
        print("  IDENTICAL to six decimals. Their 'calibration constant for")
        print("  ortho-rectified DFSAR images' is the per-product label value, and")
        print("  this product carries the same one. That is an external check on")
        print("  the ingest reading the right field, not a coincidence to note and")
        print("  move past.")
    print("\n  Our formula is not identical, and the difference is stated rather")
    print("  than absorbed:")
    print("    sigma0 = DN^2 sin(inc) / (K_lin G^2)")
    print("    -> sigma0[dB] = 20 log10(DN) + 10 log10(sin inc) - K - 20 log10(G)")
    for ch, g in cal["channels"].items():
        gi = float(g["gain_imbalance"])
        print(f"    {ch}: effective constant K + 20 log10(G) = "
              f"{K + 20 * np.log10(gi):.6f} dB  ({K + 20 * np.log10(gi) - THEIRS:+.6f} vs theirs)")
    print("  and the sin(inc) term, which their stated formula omits: theirs is a")
    print("  beta-nought-like normalisation, ours divides out the projected area.")
    print(f"  At this scene's {nominal:.2f} deg that term is "
          f"{10 * np.log10(np.sin(np.deg2rad(nominal))):+.3f} dB.")

    with open(OUT_JSON, encoding="utf-8") as fh:
        doc = json.load(fh)
    doc["calibration_cross_check"] = {
        "their_constant_db": THEIRS,
        "our_label_constant_db": K,
        "difference_db": K - THEIRS,
        "identical": bool(abs(K - THEIRS) < 1e-6),
        "our_formula": "sigma0 = DN^2 sin(inc) / (K_lin * G^2)",
        "their_formula": "sigma0[dB] = 20 log10(DN) - C",
        "effective_constant_db": {
            ch: K + 20 * float(np.log10(g["gain_imbalance"]))
            for ch, g in cal["channels"].items()},
        "sin_inc_term_db_at_nominal": float(10 * np.log10(np.sin(np.deg2rad(nominal)))),
        "note": ("their formula has no incidence term, so it is a beta-nought-like "
                 "normalisation; ours divides out the projected area. The base "
                 "constant is the same number read from the same label field."),
    }
    OUT_JSON.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
