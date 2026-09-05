"""
check_f2_footprint.py -- does the published F2 detection fall inside our data?

    python backend/scripts/check_f2_footprint.py

WHY THIS MATTERS MORE THAN ITS SIZE SUGGESTS
--------------------------------------------
Sinha et al. (2026, npj Space Exploration 2:22, doi 10.1038/s44453-026-00038-9)
report crater F2 inside Faustini at 87.39 S, 82.31 E -- about 1.1 km across --
with peak CPR 1.95 and more than 1 over roughly 47 % of its interior, and read it
as strong evidence for subsurface ice. Saran et al. (2026) dispute the same
feature, reporting mean CPR 1.01 +/- 0.3 and attributing it to roughness.

If F2 lies inside this project's measured amplitude ribbon, then our null result
is not a null in a different place -- it is a null AT A PUBLISHED POSITIVE, and
Phase 5b (recovering true Stokes CPR from the complex products) stops being a
theoretical improvement and becomes a direct test against a specific published
claim on a specific 1.1 km crater.

TWO SEPARATE QUESTIONS, ANSWERED SEPARATELY
--------------------------------------------
  1. Is F2 inside the 165 x 56 km FRAME at all?
  2. Is F2 inside the AMPLITUDE RIBBON -- the 15.64 % of the frame where DFSAR
     actually returned signal?

They are not the same question. ISRO pointed the beam at 35.6 % of the frame and
56 % of that returned literal zero. A feature can sit inside the frame and still
have no radar over it, in which case we have nothing to say about it.

The coordinate is transformed by `sar_geometry`'s own forward projection --
the one validated to 13.2 mm against ISRO's 937,296-node geolocation grid -- and
not by hand.
"""
from __future__ import annotations

import json
import sys
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

RAW = BASE_DIR / "data" / "pradan" / "raw" / "data" / "calibrated" / "20200808"
NATIVE = BASE_DIR / "data" / "pradan" / "native"
STEM = "ch2_sar_ncxl_20200808t201154198"
OUT = BASE_DIR / "docs" / "f2_footprint.json"

#: Sinha et al. 2026, npj Space Exploration 2:22, doi 10.1038/s44453-026-00038-9
F2 = {"name": "F2", "lat_deg": -87.39, "lon_deg": 82.31, "diameter_km": 1.1,
      "published_peak_cpr": 1.95, "published_fraction_cpr_gt_1": 0.47}


def main() -> int:
    from app.ingestion.sar_geometry import read_geotiff_frame

    frame = read_geotiff_frame(RAW / f"{STEM}_d_sri_xx_cp_lh_d18.tif",
                               RAW / f"{STEM}_d_sri_xx_cp_xx_d18.xml")
    lines, samples = frame.shape

    print("=" * 78)
    print("  F2 — Sinha et al. 2026, npj Space Exploration 2:22")
    print("=" * 78)
    print(f"  published position   {F2['lat_deg']}°, {F2['lon_deg']}°   "
          f"⌀ {F2['diameter_km']} km")
    print(f"  published CPR        peak {F2['published_peak_cpr']}, "
          f">1 over {F2['published_fraction_cpr_gt_1'] * 100:.0f} % of the interior")
    print(f"  our frame            {lines} x {samples} @ 25 m")

    # Forward projection — the validated one, not arithmetic by hand.
    x, y = frame.latlon_to_xy(F2["lat_deg"], F2["lon_deg"])
    line, sample = frame.xy_to_pixel(x, y)
    line, sample = float(line), float(sample)

    print(f"\n  projected            E {float(x):,.1f} m   N {float(y):,.1f} m")
    print(f"  frame pixel          line {line:,.1f}   sample {sample:,.1f}")

    inside_frame = (0 <= line < lines) and (0 <= sample < samples)
    print(f"\n  QUESTION 1 — inside the frame?   {'YES' if inside_frame else 'NO'}")
    if not inside_frame:
        print(f"    line must be in [0, {lines}) and sample in [0, {samples})")

    result = {
        "target": F2,
        "citation": ("Sinha et al. 2026, npj Space Exploration 2:22, "
                     "doi:10.1038/s44453-026-00038-9"),
        "projection": "app/ingestion/sar_geometry forward transform, validated to 13.2 mm",
        "projected_xy_m": [float(x), float(y)],
        "frame_pixel": {"line": line, "sample": sample},
        "inside_frame": bool(inside_frame),
    }

    if inside_frame:
        valid = tifffile.imread(str(NATIVE / "valid_native.tif")).astype(bool)
        foot = tifffile.imread(str(NATIVE / "footprint_native.tif")).astype(bool)
        li, si = int(round(line)), int(round(sample))

        # The crater is 1.1 km across = 44 px at 25 m. Test the disc, not one pixel:
        # a single-pixel answer at a 1.1 km feature would be luck either way.
        r_px = F2["diameter_km"] * 1000.0 / 2.0 / 25.0
        y0, y1 = max(0, int(li - r_px) - 1), min(lines, int(li + r_px) + 2)
        x0, x1 = max(0, int(si - r_px) - 1), min(samples, int(si + r_px) + 2)
        yy, xx = np.mgrid[y0:y1, x0:x1]
        disc = ((yy - line) ** 2 + (xx - sample) ** 2) <= r_px ** 2
        v = valid[y0:y1, x0:x1][disc]
        f = foot[y0:y1, x0:x1][disc]

        print(f"\n  QUESTION 2 — inside the measured amplitude ribbon?")
        print(f"    F2 disc            {int(disc.sum()):,} px of 25 m "
              f"(radius {r_px:.1f} px = {F2['diameter_km'] / 2:.2f} km)")
        print(f"    centre pixel       amplitude {'YES' if valid[li, si] else 'NO'}   "
              f"ISRO pointed {'YES' if foot[li, si] else 'NO'}")
        print(f"    over the disc      amplitude {v.mean() * 100:6.2f} %   "
              f"ISRO pointed {f.mean() * 100:6.2f} %")
        result["disc_pixels"] = int(disc.sum())
        result["centre_in_amplitude"] = bool(valid[li, si])
        result["centre_in_pointed_swath"] = bool(foot[li, si])
        result["disc_amplitude_fraction"] = float(v.mean())
        result["disc_pointed_fraction"] = float(f.mean())

        # What our radar actually says over the part of F2 it DID measure. A
        # bounded statement about a minority of the crater, labelled as one --
        # but a real measurement at a published detection.
        if v.any():
            cpr = tifffile.imread(str(NATIVE / "cpr_native.tif"))[y0:y1, x0:x1][disc][v]
            dop = tifffile.imread(str(NATIVE / "dop_native.tif"))[y0:y1, x0:x1][disc][v]
            print(f"\n  OUR MEASUREMENT over the {int(v.sum()):,} px of F2 that returned amplitude")
            print(f"    CPR (amplitude-only)  mean {cpr.mean():.6f}  "
                  f"median {float(np.median(cpr)):.6f}  max {cpr.max():.6f}")
            print(f"    DOP                   mean {dop.mean():.6f}  "
                  f"median {float(np.median(dop)):.6f}  min {dop.min():.6f}")
            print(f"    their peak CPR {F2['published_peak_cpr']} is "
                  f"{F2['published_peak_cpr'] / max(float(cpr.max()), 1e-9):.0f}x our maximum")
            print("    THIS IS NOT A CONTRADICTION. Our CPR is the amplitude-only ratio,")
            print("    which docs/METHODS.md §1 proves cannot exceed 0.0042611 wherever")
            print("    DOP < 0.13, and cannot reach 1.95 anywhere by construction. Sinha")
            print("    et al. use full-pol (HH/HV/VH/VV); these products are hybrid/compact")
            print("    pol (LH/LV). The comparison becomes meaningful only after Phase 5b")
            print("    recovers true Stokes CPR = (S0 - S3)/(S0 + S3).")
            result["measured_over_covered_part"] = {
                "pixels": int(v.sum()),
                "fraction_of_crater": float(v.mean()),
                "cpr_amplitude_only": {"mean": float(cpr.mean()),
                                       "median": float(np.median(cpr)),
                                       "max": float(cpr.max())},
                "dop": {"mean": float(dop.mean()), "median": float(np.median(dop)),
                        "min": float(dop.min())},
                "caveat": ("amplitude-only CPR, algebraically capped at 0.0042611 where "
                           "DOP < 0.13 (docs/METHODS.md 1); hybrid/compact pol against their "
                           "full-pol. NOT comparable to their 1.95 until Phase 5b."),
            }

        print("\n" + "-" * 78)
        if v.mean() > 0.5:
            print("  F2 IS COVERED BY OUR MEASURED RADAR.")
            print("  Our null result is therefore a null AT A PUBLISHED POSITIVE, on the")
            print("  same 1.1 km crater two 2026 papers disagree about. Phase 5b becomes a")
            print("  direct test of a specific published claim rather than a general")
            print("  improvement.")
            result["verdict"] = "covered"
        elif f.mean() > 0.5:
            print("  F2 was POINTED AT but returned little or no amplitude.")
            print("  That is itself a finding: the published detection sits in a part of")
            print("  the swath where this product carries no usable signal.")
            result["verdict"] = "pointed_but_no_amplitude"
        else:
            print("  F2 is inside the frame but OUTSIDE the measured ribbon.")
            print("  We can say nothing about it from this product, and must not imply")
            print("  our null contradicts theirs.")
            result["verdict"] = "outside_ribbon"
        print("-" * 78)
    else:
        result["verdict"] = "outside_frame"
        print("\n  F2 lies outside this frame entirely. Our null and their detection are")
        print("  measurements of different ground, and must not be compared.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
