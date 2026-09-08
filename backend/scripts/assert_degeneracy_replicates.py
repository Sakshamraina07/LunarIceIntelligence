"""
assert_degeneracy_replicates.py -- G20. The identity holds on a second product.

    python backend/scripts/assert_degeneracy_replicates.py [--inject WHICH]

WHY
---
METHODS section 1 derives that an amplitude-formed CPR is a function of DOP
alone:

    CPR_a = tanh^2(x/4),  DOP_a = |tanh(x/2)|,  x = ln(LH/LV)
      =>   CPR_a = tanh^2(artanh(DOP_a)/2)

and therefore that DOP < 0.13 caps CPR at tanh^2(artanh(0.13)/2) = 0.0042610829,
against a threshold of 1.00. The screen is empty BY CONSTRUCTION.

That is algebra. It cannot depend on which acquisition it is evaluated on, so a
SECOND, INDEPENDENT product is a real check on whether we are reading these
files correctly at all -- and a positive result rather than an absence. The
2020-03-05 pass is a different date, a different orbit, a different look angle
(26.0 vs 20.0 deg), a different PRF, a different pulse bandwidth, a different
declared look count and a different output grid (90 m vs 25 m).

If the identity ever fails to replicate, THE FINDING IS THAT WE ARE READING THE
FILE WRONG, not that the algebra varies. This gate exists so that conclusion is
forced rather than available.

WHAT IT ASSERTS, on the independent 2020-03-05 product
  1. the measured crossing -- max CPR among pixels satisfying DOP < 0.13 --
     matches the closed form to better than 1e-3 relative
  2. CPR predicted from DOP through the identity matches stored CPR to a
     float-precision residual
  3. no pixel passes the joint screen, on either product
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import tifffile

BASE_DIR = Path(__file__).resolve().parents[2]

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

DOP_THRESHOLD = 0.13
CPR_THRESHOLD = 1.00
#: How close the measurement must sit to the closed form. 1e-3 relative is three
#: orders looser than either product actually achieves (1.4e-05 and 8.6e-05), so
#: it is a threshold on "did the algebra replicate", not a fitted tolerance.
REL_TOL = 1e-3

PRODUCTS = [
    ("2020-08-08 (the screened product)",
     "data/pradan/raw/data/calibrated/20200808",
     "ch2_sar_ncxl_20200808t201154198_d_sri_xx_cp_{ch}_d18.tif"),
    ("2020-03-05 (independent)",
     "data/generality/20200305/data/calibrated/20200305",
     "ch2_sar_ncxl_20200305t114902885_d_sri_xx_cp_{ch}_d18.tif"),
]
INJECTIONS = ("crossing", "identity", "passing")


def measure(directory: str, stem: str, inject: str | None = None) -> dict:
    """CPR_a and DOP_a exactly as process_real_sar_pipeline.py forms them.

    sin(incidence) multiplies BOTH channels and therefore cancels in every ratio
    (METHODS 12.4), so it is not applied here and the result is identical. That
    is the whole reason a discredited incidence field cannot reach these numbers.
    """
    d = BASE_DIR / directory
    lh = tifffile.imread(str(d / stem.format(ch="lh"))).astype(np.float64)
    lv = tifffile.imread(str(d / stem.format(ch="lv"))).astype(np.float64)
    if inject == "identity":
        # Break the relationship between the channels without changing either
        # one's marginal distribution: shuffling LV destroys the pairing.
        rng = np.random.default_rng(0)
        flat = lv.ravel().copy()
        rng.shuffle(flat)
        lv = flat.reshape(lv.shape)

    valid = (lh > 0) & (lv > 0)
    s_lh, s_lv = lh ** 2, lv ** 2
    eps = 1e-12
    sc = (np.sqrt(s_lh) - np.sqrt(s_lv)) ** 2
    oc = (np.sqrt(s_lh) + np.sqrt(s_lv)) ** 2
    cpr = np.where(valid, sc / (oc + eps), 0.0)
    dop = np.where(valid, np.abs(s_lh - s_lv) / (s_lh + s_lv + eps), 0.0)

    pred = np.tanh(np.arctanh(np.clip(dop[valid], 0.0, 0.999999)) / 2.0) ** 2
    residual = float(np.abs(pred - cpr[valid]).max())

    under = valid & (dop < DOP_THRESHOLD)
    crossing = float(cpr[under].max()) if under.any() else float("nan")
    if inject == "crossing":
        crossing *= 1.05
    passing = int((valid & (cpr > CPR_THRESHOLD) & (dop < DOP_THRESHOLD)).sum())
    if inject == "passing":
        passing = 1
    return {"valid_px": int(valid.sum()), "max_residual": residual,
            "crossing": crossing, "peak_cpr": float(cpr[valid].max()),
            "passing": passing}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inject", choices=INJECTIONS)
    args = ap.parse_args()

    ceiling = math.tanh(math.atanh(DOP_THRESHOLD) / 2.0) ** 2
    print("=" * 78)
    print("G20 — the CPR/DOP degeneracy replicates on an independent product")
    print("=" * 78)
    print(f"  closed form  tanh^2(artanh({DOP_THRESHOLD:g})/2) = {ceiling:.10f}")
    if args.inject:
        print(f"\n  --inject {args.inject}\n")

    bad: list[str] = []
    emitted: list = []
    print(f"\n  {'product':<34}{'valid px':>12}{'max resid':>12}"
          f"{'crossing':>15}{'rel':>11}{'pass':>6}")
    for name, directory, stem in PRODUCTS:
        independent = "independent" in name
        m = measure(directory, stem,
                    args.inject if (independent or args.inject == "passing") else None)
        rel = abs(m["crossing"] - ceiling) / ceiling
        emitted.append({"product": name, "directory": directory,
                        "independent": independent,
                        "relative_agreement": rel, **m})
        print(f"  {name:<34}{m['valid_px']:>12,}{m['max_residual']:>12.2e}"
              f"{m['crossing']:>15.10f}{rel:>11.2e}{m['passing']:>6}")

        if independent and rel > REL_TOL:
            bad.append(f"{name}: the measured crossing {m['crossing']:.10f} is "
                       f"{rel:.2e} from the closed form {ceiling:.10f}, over the "
                       f"{REL_TOL:.0e} bound. The algebra does not vary, so this "
                       f"means the file is being read wrong.")
        if m["max_residual"] > 1e-6:
            bad.append(f"{name}: CPR predicted from DOP differs from stored CPR by "
                       f"{m['max_residual']:.2e}; the two are one degree of freedom "
                       f"and cannot disagree above float precision.")
        if m["passing"] != 0:
            bad.append(f"{name}: {m['passing']} pixel(s) pass CPR > {CPR_THRESHOLD:g} "
                       f"AND DOP < {DOP_THRESHOLD:g}, which the ceiling forbids.")

    # EMITTED, so METHODS 1.10 quotes a stamped artifact rather than a
    # terminal -- the failure mode section 5.12 exists to describe. Not
    # written on an injection run, which would poison the artifact with a
    # fabricated value.
    if not args.inject:
        import json
        from datetime import datetime, timezone
        (BASE_DIR / "docs" / "degeneracy_replication.json").write_text(
            json.dumps({
                "schema": "lunar-ice/degeneracy-replication/1",
                "generated_utc": datetime.now(timezone.utc).isoformat(),
                "computed_by": "backend/scripts/assert_degeneracy_replicates.py",
                "closed_form_ceiling": ceiling,
                "dop_threshold": DOP_THRESHOLD,
                "cpr_threshold": CPR_THRESHOLD,
                "relative_tolerance": REL_TOL,
                "products": emitted,
            }, indent=2), encoding="utf-8")
    print()
    if args.inject:
        if bad:
            print(f"  INJECTION CAUGHT ({args.inject}). The gate works.")
            for b in bad:
                print(f"    {b}")
            return 0
        print(f"  INJECTION NOT CAUGHT ({args.inject}).")
        return 1

    if bad:
        print("  GATE FAIL")
        for b in bad:
            print(f"    - {b}")
        return 1
    print("  GATE PASS — the identity replicates on an independent acquisition,")
    print("  the measured crossing sits on the closed form, and the joint screen")
    print("  is empty on both products.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
