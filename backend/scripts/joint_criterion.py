"""
joint_criterion.py -- the DOP half of the criterion does most of the work.

    python backend/scripts/joint_criterion.py [--trials N]

WHY
---
The published criterion is a PAIR of thresholds, CPR > 1 AND DOP < 0.13, but its
false-positive rate is always quoted for the CPR half alone. That understates the
screen and overstates the problem: on a properly formed Stokes vector the two
conditions are not independent, and requiring both is far stricter than requiring
the first.

Drawn from a genuine Stokes vector at N = 14 with a true CPR of 0.7:

    marginal  P(CPR_hat > 1)                   17.5 %
    joint     P(CPR_hat > 1 AND m_hat < 0.13)   1.8 %

A structural fact sits underneath it. For a true CPR of c the degree of
polarisation cannot fall below |1 - c| / (1 + c), which at c = 0.7 is 0.176 --
already above the 0.13 threshold. So the DOP condition is not merely an extra
hurdle; at this background it is one the terrain cannot clear except through
estimator noise, and the joint rate is an order of magnitude below the marginal.

THIS DOES NOT RESCUE THE AMPLITUDE PROXY. It is a statement about what the
criterion would do on a correctly formed Stokes vector, which is what a future
build with the sli products could compute. METHODS 1 shows the amplitude-only
CPR is a function of DOP alone, so on THIS build the two conditions are one
condition and the joint rate is not available.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.stats import f as _F

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "joint_criterion.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

SEED = 7
N_LOOKS = 14
TRUE_CPR = 0.7
DOP_THRESHOLD = 0.13
CPR_THRESHOLD = 1.0


def stokes_draw(rng, cpr, m, n_looks, trials):
    """N-look Stokes estimates for a population with this CPR and this DOP.

    The covariance is built to realise (cpr, m) exactly, then circular-Gaussian
    channels are drawn from it. Returns (CPR_hat, m_hat) per trial.
    """
    s0 = 2.0
    s3 = s0 * (1.0 - cpr) / (1.0 + cpr)
    s2sq = (m * s0) ** 2 - s3 ** 2
    if s2sq < 0:
        return None
    s2 = np.sqrt(s2sq)
    cmag = np.sqrt(s2 ** 2 + s3 ** 2) / 2.0
    phi = np.arctan2(-s3 / 2.0, s2 / 2.0)
    c = cmag * np.exp(1j * phi)

    z1 = (rng.normal(size=(trials, n_looks))
          + 1j * rng.normal(size=(trials, n_looks))) / np.sqrt(2)
    z2 = (rng.normal(size=(trials, n_looks))
          + 1j * rng.normal(size=(trials, n_looks))) / np.sqrt(2)
    eh = z1
    ev = np.conj(c) * z1 + np.sqrt(1.0 - abs(c) ** 2) * z2

    lh = (np.abs(eh) ** 2).mean(1)
    lv = (np.abs(ev) ** 2).mean(1)
    x = (eh * np.conj(ev)).mean(1)
    s0h = lh + lv
    s1h = lh - lv
    s2h = 2.0 * x.real
    s3h = -2.0 * x.imag
    return ((s0h - s3h) / (s0h + s3h),
            np.sqrt(s1h ** 2 + s2h ** 2 + s3h ** 2) / s0h)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=600_000)
    args = ap.parse_args()

    rng = np.random.default_rng(SEED)
    m_min = (1.0 - TRUE_CPR) / (1.0 + TRUE_CPR)
    band = ((1.0 - DOP_THRESHOLD) / (1.0 + DOP_THRESHOLD),
            (1.0 + DOP_THRESHOLD) / (1.0 - DOP_THRESHOLD))

    print("=" * 78)
    print("JOINT CRITERION — CPR > 1 AND DOP < 0.13, on a Stokes vector")
    print("=" * 78)
    print(f"  N = {N_LOOKS}, true CPR {TRUE_CPR}, seed {SEED}, "
          f"{args.trials:,} trials per row")
    print(f"  STRUCTURAL: m >= |1-CPR|/(1+CPR) = {m_min:.4f} at CPR {TRUE_CPR}")
    print(f"  so DOP < {DOP_THRESHOLD} requires a true CPR inside "
          f"({band[0]:.3f}, {band[1]:.3f})")
    print()
    print(f"  {'true m':>9}{'marginal %':>13}{'joint %':>11}")

    rows = []
    for m0 in (m_min + 1e-6, 0.2, 0.3, 0.5):
        got = stokes_draw(rng, TRUE_CPR, m0, N_LOOKS, args.trials)
        if got is None:
            continue
        cpr_hat, m_hat = got
        marginal = float(100.0 * np.mean(cpr_hat > CPR_THRESHOLD))
        joint = float(100.0 * np.mean((cpr_hat > CPR_THRESHOLD)
                                      & (m_hat < DOP_THRESHOLD)))
        print(f"  {m0:>9.4f}{marginal:>13.2f}{joint:>11.3f}")
        rows.append({"true_m": m0, "marginal_fp_percent": marginal,
                     "joint_fp_percent": joint})

    print()
    print("  Requiring both conditions is an order of magnitude stricter than")
    print("  requiring the CPR one. THIS BUILD CANNOT USE THAT: METHODS 1 shows")
    print("  an amplitude-only CPR is a function of DOP alone, so here the two")
    print("  conditions are one condition.")

    OUT.write_text(json.dumps({
        "schema": "lunar-ice/joint-criterion/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/joint_criterion.py",
        "seed": SEED,
        "trials_per_row": args.trials,
        "n_looks": N_LOOKS,
        "true_cpr": TRUE_CPR,
        "dop_threshold": DOP_THRESHOLD,
        "m_min_at_true_cpr": m_min,
        "cpr_band_for_m_below_threshold": list(band),
        "rows": rows,
        # BOTH MARGINALS, because they are different quantities and the
        # manuscript quotes the analytic one. The Monte Carlo marginal is what
        # the Stokes ESTIMATOR does at this m; the analytic marginal is
        # F(2N,2N) for independent channels. They differ by ~0.15 pp, which is
        # about 3 standard errors at this trial count -- not noise, but the
        # estimator's own behaviour. Reporting only one would leave the other
        # unsourced.
        "marginal_fp_percent_analytic_F": float(
            (1.0 - _F.cdf(1.0 / TRUE_CPR, 2 * N_LOOKS, 2 * N_LOOKS)) * 100.0),
        "headline": {"marginal_fp_percent_monte_carlo": rows[0]["marginal_fp_percent"],
                     "joint_fp_percent": rows[0]["joint_fp_percent"],
                     "at_true_m": rows[0]["true_m"]},
        "not_available_on_this_build": (
            "The amplitude-only CPR is a function of DOP alone (METHODS 1), so "
            "on this product the two conditions are one condition and the joint "
            "rate cannot be claimed. It describes what a Stokes-derived build "
            "from the sli products could do."),
    }, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
