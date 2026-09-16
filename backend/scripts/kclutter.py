"""
kclutter.py -- texture cancels in a ratio, unless the two channels do not share it.

    python backend/scripts/kclutter.py [--trials N]

WHY
---
Lunar regolith is not a homogeneous scatterer, so the speckle model underlying
F(2N, 2N) -- Gaussian clutter, no texture -- is an idealisation. The obvious
worry is that real texture inflates the exceedance rate and every figure in
this work is optimistic.

It does not, and the reason is worth stating precisely. If the same-sense and
opposite-sense channels see the SAME patch of ground, they share the same texture
modulation, and a shared multiplicative factor cancels exactly in their ratio.
K-distributed clutter of any order then gives the same tail as the Gaussian case:

    shared texture, any nu:  17.53 %   (F model: 17.54 %)

The rate only moves if the two channels are given INDEPENDENT texture, which
would mean they were looking at different ground:

    independent texture:  27.5 % to 39.5 % across nu = 1.5 to 10

THE SECOND ROW IS NOT A CORRECTION TO APPLY; IT IS A MODEL THAT DOES NOT DESCRIBE
THIS INSTRUMENT. Both channels are formed from one illumination of one footprint.
It is computed because "texture cancels" is a claim, and a claim with an
unmeasured alternative beside it is stronger than a claim on its own.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.stats import f as Fdist

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "kclutter.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

SEED = 7
N_LOOKS = 14
TRUE_CPR = 0.7
#: K-distribution order. Small nu is strongly textured; nu -> infinity is
#: Gaussian. 1e9 stands in for the Gaussian limit.
NU_VALUES = (1.5, 2.0, 5.0, 10.0, 1e9)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=1_000_000)
    args = ap.parse_args()

    rng = np.random.default_rng(SEED)
    fp_f = float((1.0 - Fdist.cdf(1.0 / TRUE_CPR, 2 * N_LOOKS, 2 * N_LOOKS)) * 100.0)

    print("=" * 78)
    print("K-DISTRIBUTED CLUTTER — shared vs independent texture")
    print("=" * 78)
    print(f"  N = {N_LOOKS}, true CPR {TRUE_CPR}, seed {SEED}, "
          f"{args.trials:,} trials per row")
    print(f"  F model, Gaussian clutter: {fp_f:.2f} %")
    print()
    print(f"  {'nu':>10}{'shared %':>12}{'independent %':>16}")

    # The speckle part, drawn once: an N-look intensity is Gamma(N, 1/N).
    g1 = rng.gamma(N_LOOKS, 1.0 / N_LOOKS, args.trials)
    g2 = rng.gamma(N_LOOKS, 1.0 / N_LOOKS, args.trials)

    rows = []
    for nu in NU_VALUES:
        t = rng.gamma(nu, 1.0 / nu, args.trials)
        t_b = rng.gamma(nu, 1.0 / nu, args.trials)
        # SHARED: the same texture multiplies both channels, so it cancels.
        r_shared = (t * g1) / (t * g2)
        # INDEPENDENT: a different texture per channel. Not this instrument.
        r_indep = (t * g1) / (t_b * g2)
        a = float(100.0 * np.mean(TRUE_CPR * r_shared > 1.0))
        b = float(100.0 * np.mean(TRUE_CPR * r_indep > 1.0))
        label = "inf" if nu > 1e8 else f"{nu:g}"
        print(f"  {label:>10}{a:>12.2f}{b:>16.2f}")
        rows.append({"nu": (None if nu > 1e8 else nu), "nu_label": label,
                     "fp_shared_percent": a, "fp_independent_percent": b})
        del t, t_b, r_shared, r_indep

    shared = [r["fp_shared_percent"] for r in rows]
    indep = [r["fp_independent_percent"] for r in rows]
    indep_finite = [r["fp_independent_percent"] for r in rows if r["nu"] is not None]
    # The Monte Carlo standard error of one tail estimate at this trial count,
    # in percentage points, at the F-model tail p: the CLAIM is that shared
    # texture reproduces the F tail to within that error, not to a digit.
    p = fp_f / 100.0
    sigma_mc = 100.0 * math.sqrt(p * (1.0 - p) / args.trials)
    diff_max = max(abs(s - fp_f) for s in shared)
    print()
    print(f"  MC sigma at {args.trials:,} trials: {sigma_mc:.4f} points; "
          f"max |shared - F| = {diff_max:.4f} points ({diff_max / sigma_mc:.2f} sigma)")
    print(f"  shared texture spans {min(shared):.2f}-{max(shared):.2f} % "
          f"against the F model's {fp_f:.2f} % -- it cancels")
    print(f"  independent texture spans {min(indep):.1f}-{max(indep):.1f} %, "
          f"a model that does not describe this instrument")

    OUT.write_text(json.dumps({
        "schema": "lunar-ice/kclutter/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/kclutter.py",
        "seed": SEED,
        "trials_per_row": args.trials,
        "n_looks": N_LOOKS,
        "true_cpr": TRUE_CPR,
        "fp_percent_F_gaussian": fp_f,
        "rows": rows,
        "shared_texture_range": [min(shared), max(shared)],
        "independent_texture_range": [min(indep), max(indep)],
        "independent_texture_range_finite_nu": [min(indep_finite), max(indep_finite)],
        "mc_sigma_points": sigma_mc,
        # The claim compares TWO estimates of the same tail, so the sampling
        # error that matters is that of their difference: sigma * sqrt(2).
        "mc_sigma_of_difference_points": sigma_mc * math.sqrt(2.0),
        "shared_minus_F_max_points": diff_max,
        "claim_gated": ("|fp_shared - fp_F| <= 3 sigma_MC at this trial count for every "
                        "texture order (the manuscript states the identity holds to "
                        "within the simulation's own sampling error), and the "
                        "independent-texture rows span 27-40 % across nu = 1.5..10"),
        "reproducibility": (
            "These are what the reference block produces from a FRESH "
            "default_rng(7). The reference's own printed digits (17.53 / "
            "27.5-39.5) came from a generator already advanced by earlier blocks "
            "of the script it lived in; the manuscript prints none of those "
            "digits and makes a qualitative claim, so the gate asserts the claim "
            "at the recorded trial count rather than any digit."),
        "why_shared_is_the_right_model": (
            "Both circular channels are formed from one illumination of one "
            "footprint, so they share the texture modulation and it cancels in "
            "their ratio. The independent-texture row is computed as the "
            "alternative it is NOT, not as a correction to apply."),
    }, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
