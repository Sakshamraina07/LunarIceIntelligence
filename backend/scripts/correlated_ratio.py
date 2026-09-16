"""
correlated_ratio.py -- what channel coherence does to the noise exceedance rate.

    python backend/scripts/correlated_ratio.py [--trials N]

WHY
---
Every noise exceedance rate in this work is computed from F(2N, 2N), which assumes
the same-sense and opposite-sense intensities are INDEPENDENT. They are not: the
two circular channels are formed from the same illumination of the same ground,
and METHODS 7.10 bounds their correlation at |rho|^2 >= 0.3052 from Putrevu et
al.'s own published dispersion.

Correlation between numerator and denominator narrows a ratio's distribution, so
every F-based rate is an UPPER BOUND rather than an estimate. That sentence is
load-bearing and is asserted throughout; this measures how much it is worth.

At N = 14 and a true CPR of 0.7, drawing correlated circular-Gaussian channels
directly (Lee et al. 1994's model) gives:

    |rho| = 0     17.58 %     the independent case, which F reproduces
    |rho| = 0.5   14.14 %
    |rho| = 0.8    6.27 %
    |rho| = 0.9    1.92 %
    |rho| = 0.98   0.00 %

The bound is not nearly tight. At the coherence this swath actually shows the
F-based rate overstates the exceedance by more than an order of
magnitude, and saying "upper bound" without saying that invites a reader to treat
17.79 % as an estimate.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.stats import f as Fdist

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "correlated_ratio.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

SEED = 7
N_LOOKS = 14
TRUE_CPR = 0.7
#: THE REFERENCE'S LOOP ORDER, KEPT EXACTLY. A Monte Carlo result depends on the
#: order the generator is consumed in, so iterating a different set of rho values
#: -- or a different set of look counts -- gives a different stream and a
#: different answer within noise. The reference sweeps N over (13, 14) and rho
#: over six values; both are reproduced here and the N = 14 rows are the ones
#: reported. Shortening the loop would silently re-derive rather than port.
N_SWEEP = (13, 14)
RHO_SWEEP = (0.0, 0.5, 0.8, 0.9, 0.9822, 0.999)
RHOS = [0.0, 0.5, 0.8, 0.9, 0.98]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=1_500_000)
    args = ap.parse_args()

    rng = np.random.default_rng(SEED)
    thr = 1.0 / TRUE_CPR
    fp_f = float((1.0 - Fdist.cdf(thr, 2 * N_LOOKS, 2 * N_LOOKS)) * 100.0)

    print("=" * 78)
    print(f"CORRELATED RATIO — P(CPR_hat > 1 | true CPR {TRUE_CPR}) vs coherence")
    print("=" * 78)
    print(f"  N = {N_LOOKS}, seed {SEED}, {args.trials:,} trials per row")
    print(f"  F(2N,2N) analytic, independent channels: {fp_f:.2f} %")
    print()
    print(f"  {'|rho|':>7}{'FP %':>9}{'vs F':>9}")

    all_rows = {}
    for n_l in N_SWEEP:
        for rho in RHO_SWEEP:
            # Two correlated circular-Gaussian channels: w carries coherence rho
            # with z1, so E[z1 w*] = rho. This is the model, not an
            # approximation to it; the intensities are sums of |.|^2 over N.
            z1 = (rng.normal(size=(args.trials, n_l))
                  + 1j * rng.normal(size=(args.trials, n_l))) / np.sqrt(2)
            z2 = (rng.normal(size=(args.trials, n_l))
                  + 1j * rng.normal(size=(args.trials, n_l))) / np.sqrt(2)
            w = rho * z1 + np.sqrt(1.0 - rho ** 2) * z2
            i1 = (np.abs(z1) ** 2).sum(1)
            i2 = (np.abs(w) ** 2).sum(1)
            fp = float(100.0 * np.mean(i1 / i2 > thr))
            all_rows[(n_l, rho)] = fp
            del z1, z2, w, i1, i2

    rows = []
    for rho in RHOS:
        # the reported rows are N = 14; 0.98 is reported for the 0.9822 draw,
        # which is this swath's own measured coherence (METHODS 7.9.3)
        key = 0.9822 if abs(rho - 0.98) < 1e-9 else rho
        fp = all_rows[(N_LOOKS, key)]
        ratio = fp / fp_f if fp_f else float("nan")
        print(f"  {rho:>7.2f}{fp:>9.2f}{ratio:>9.3f}")
        rows.append({"rho": rho, "drawn_at_rho": key,
                     "fp_percent": fp, "ratio_to_F": ratio})

    print()
    print("  The F-based rate is an UPPER BOUND and it is not a tight one: at")
    print("  high coherence it overstates the exceedance by more than an")
    print("  order of magnitude.")

    OUT.write_text(json.dumps({
        "schema": "lunar-ice/correlated-ratio/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/correlated_ratio.py",
        "seed": SEED,
        "trials_per_row": args.trials,
        "n_looks": N_LOOKS,
        "true_cpr": TRUE_CPR,
        "fp_percent_F_independent": fp_f,
        "model": ("Lee et al. 1994: two correlated circular-Gaussian channels, "
                  "w = rho z1 + sqrt(1-rho^2) z2, intensities summed over N looks"),
        "rows": rows,
        "note": ("F(2N,2N) assumes independent numerator and denominator. The "
                 "channels are correlated, so every F-based rate in this work is "
                 "an upper bound; these rows measure by how much."),
    }, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
