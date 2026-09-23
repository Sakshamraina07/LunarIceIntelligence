"""
dop_sampling_bias.py -- the sample DOP at finite N, and what the joint screen selects.

    python backend/scripts/dop_sampling_bias.py            # both artifacts
    python backend/scripts/dop_sampling_bias.py --trials-a 400000 --trials-b 100000

WHY
---
Section III-E calls the 1.50 % of cells with sample DOP < 0.13 a SCREEN
FREQUENCY, not a terrain fraction, because the sample DOP is biased upward at
finite N (Santalla del Rio et al. 2006). It quotes one number for that: for an
unpolarized population under equal-weight Gaussian looks the squared sample
DOP follows Beta(3/2, N - 1), so at N = 14 only 7 % of cells read below 0.13
where the population DOP is zero. That figure is a closed form; this script
checks it by simulation and writes both, so the manuscript's "7 %" points at a
run and not at an assertion (docs/dop_sampling_bias.json).

Review item M6 asks for the curves behind it: across population DOP, population
CPR and N, how often the sample DOP reads below 0.13, how often the sample CPR
reads above 1 and above the one-sided 95 % critical value, and how often both
conditions of the joint screen hold together (docs/joint_calibration.json).

THE GENERATIVE MODEL
--------------------
A population is a 2 x 2 circular-basis covariance: SC and OC powers
a = CPR/(1 + CPR), b = 1/(1 + CPR) (so S0 = 1), and cross term |c| = gamma_c
sqrt(ab), where gamma_c is the circular FIELD coherence. For one covariance
DOP^2 = q^2 + gamma_c^2 (1 - q^2), q = (CPR - 1)/(CPR + 1), so a (DOP, CPR)
pair is realizable only if DOP >= |q|. Pairs that are not are recorded as
invalid and NOT simulated -- the review's instruction, and the reason the grid
is ragged: CPR 0.7 needs DOP >= 0.176.

N looks are drawn as independent, equal-weight, circular complex Gaussian
2-vectors with that covariance; the sample covariance is their mean; from it
the sample CPR R = a_hat / b_hat and the sample DOP
m_hat = sqrt((a_hat - b_hat)^2 + 4 |c_hat|^2) / (a_hat + b_hat).
Speckle only: no texture, no spatial correlation, integer N.

Every rate carries its binomial Monte Carlo standard error; seeds are fixed and
recorded. Nothing here is a property of the DFSAR data -- it is the model the
screen frequencies must be read through.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.stats import beta as Beta
from scipy.stats import f as Fdist

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT_A = BASE_DIR / "docs" / "dop_sampling_bias.json"
OUT_B = BASE_DIR / "docs" / "joint_calibration.json"

DOP_THRESHOLD = 0.13
CPR_THRESHOLD = 1.0
LOOKS = (5, 14, 21, 38)
SEED_A = 20260923
SEED_B = 20260924
POP_DOP = (0.0, 0.05, 0.10, 0.13, 0.2, 0.3)
POP_CPR = (0.7, 1.0, 1.1, 1.2, 1.299)
CHUNK = 25000

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def gamma_c_for(dop: float, cpr: float) -> float | None:
    """The circular field coherence a (DOP, CPR) population requires, or None
    if no covariance realizes the pair."""
    q = (cpr - 1.0) / (cpr + 1.0)
    if dop < abs(q) - 1e-12:
        return None
    return float(np.sqrt(max(dop * dop - q * q, 0.0) / (1.0 - q * q)))


def simulate(rng, n_looks: int, trials: int, cpr: float, gamma: float):
    """Sample CPR and sample DOP for `trials` cells of `n_looks` looks."""
    a, b = cpr / (1 + cpr), 1 / (1 + cpr)
    r_all, m_all = [], []
    done = 0
    while done < trials:
        n = min(CHUNK, trials - done)
        w1 = (rng.standard_normal((n, n_looks)) + 1j * rng.standard_normal((n, n_looks))) / np.sqrt(2)
        w2 = (rng.standard_normal((n, n_looks)) + 1j * rng.standard_normal((n, n_looks))) / np.sqrt(2)
        z1 = np.sqrt(a) * w1
        z2 = np.sqrt(b) * (gamma * w1 + np.sqrt(1 - gamma * gamma) * w2)
        ah = (np.abs(z1) ** 2).mean(axis=1)
        bh = (np.abs(z2) ** 2).mean(axis=1)
        ch = (z1 * np.conj(z2)).mean(axis=1)
        r_all.append(ah / bh)
        m_all.append(np.sqrt((ah - bh) ** 2 + 4 * np.abs(ch) ** 2) / (ah + bh))
        done += n
    return np.concatenate(r_all), np.concatenate(m_all)


def rate(x: np.ndarray) -> dict:
    p = float(x.mean())
    return {"percent": 100 * p, "mc_se_percent": 100 * float(np.sqrt(p * (1 - p) / x.size))}


def part_a(trials: int) -> dict:
    rng = np.random.default_rng(SEED_A)
    rows = []
    print(f"  A. unpolarized population (DOP 0, CPR 1), {trials:,} trials per N")
    for n in LOOKS:
        _, m = simulate(rng, n, trials, 1.0, 0.0)
        sim = rate(m < DOP_THRESHOLD)
        closed = 100 * float(Beta.cdf(DOP_THRESHOLD ** 2, 1.5, n - 1))
        # distributional check beyond the one quantile: KS distance of m^2
        # against Beta(3/2, N-1)
        m2 = np.sort(m * m)
        ecdf = np.arange(1, m2.size + 1) / m2.size
        ks = float(np.max(np.abs(ecdf - Beta.cdf(m2, 1.5, n - 1))))
        z = (sim["percent"] - closed) / sim["mc_se_percent"]
        rows.append({"N": n, "simulated": sim, "beta_closed_form_percent": closed,
                     "z_simulated_vs_closed": z, "ks_distance_m2_vs_beta": ks,
                     "median_sample_dop": float(np.median(m))})
        print(f"    N = {n:>2}: simulated {sim['percent']:.3f} +/- {sim['mc_se_percent']:.3f} %"
              f"   Beta(3/2, N-1) {closed:.3f} %   z {z:+.2f}   KS {ks:.4f}"
              f"   median m_hat {np.median(m):.3f}")
    return {"rows": rows}


def part_b(trials: int) -> dict:
    rng = np.random.default_rng(SEED_B)
    cells, invalid = [], []
    print(f"\n  B. grid: population DOP x CPR x N, {trials:,} trials per valid cell")
    for dop in POP_DOP:
        for cpr in POP_CPR:
            g = gamma_c_for(dop, cpr)
            q = (cpr - 1) / (cpr + 1)
            if g is None:
                invalid.append({"pop_dop": dop, "pop_cpr": cpr, "min_dop": abs(q)})
                continue
            for n in LOOKS:
                crit = float(Fdist.ppf(0.95, 2 * n, 2 * n))
                r, m = simulate(rng, n, trials, cpr, g)
                low = m < DOP_THRESHOLD
                gt1 = r > CPR_THRESHOLD
                gtc = r > crit
                cells.append({
                    "pop_dop": dop, "pop_cpr": cpr, "gamma_c": g, "N": n,
                    "crit_95": crit,
                    "p_dop_below": rate(low), "p_cpr_gt_1": rate(gt1),
                    "p_cpr_gt_crit": rate(gtc),
                    "p_joint_selection": rate(low & gt1),
                    "p_joint_and_significant": rate(low & gtc),
                    "median_sample_dop": float(np.median(m)),
                    "median_sample_cpr": float(np.median(r))})
            print(f"    DOP {dop:.2f} CPR {cpr:.3f}  gamma_c {g:.4f}: "
                  + "  ".join(f"N{c['N']} joint {c['p_joint_selection']['percent']:.2f}%"
                              for c in cells[-len(LOOKS):]))
    sig = sum(c["p_joint_and_significant"]["percent"] > 0 for c in cells)
    print(f"    cells in which a jointly selected cell exceeded the critical value: {sig}")
    return {"cells": cells, "invalid_pairs": invalid,
            "joint_and_significant_nonzero_cells": sig}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials-a", type=int, default=400_000)
    ap.add_argument("--trials-b", type=int, default=100_000)
    args = ap.parse_args()
    if args.trials_a < 400_000 or args.trials_b < 100_000:
        print("  refusing: the review asks for >= 4e5 (A) and >= 1e5 (B) trials")
        return 1

    print("=" * 78)
    print("DOP SAMPLING BIAS AND JOINT-SCREEN CALIBRATION")
    print("=" * 78)
    a = part_a(args.trials_a)
    common = {
        "generator": "backend/scripts/dop_sampling_bias.py",
        "model": ("N independent equal-weight circular complex Gaussian looks of a "
                  "2x2 circular-basis covariance; sample covariance = mean over "
                  "looks; R = a_hat/b_hat, m_hat = sqrt((a_hat-b_hat)^2 + "
                  "4|c_hat|^2)/(a_hat+b_hat). Speckle only."),
        "dop_threshold": DOP_THRESHOLD, "cpr_threshold": CPR_THRESHOLD,
        "reference": "Santalla del Rio et al., IEEE TAP 54(7), 2006 (santalla2006)"}
    at14 = next(r for r in a["rows"] if r["N"] == 14)
    OUT_A.write_text(json.dumps({
        "schema": "lunar-ice/dop-sampling-bias/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(), **common,
        "seed": SEED_A, "trials_per_N": args.trials_a,
        "question": ("P(m_hat < 0.13 | population DOP = 0) -- how often an "
                     "unpolarized population reads as passing the DOP gate"),
        "closed_form": "m_hat^2 ~ Beta(3/2, N - 1)",
        "manuscript_figure": {"N": 14,
                              "closed_form_percent": at14["beta_closed_form_percent"],
                              "simulated_percent": at14["simulated"]["percent"],
                              "printed": "7 %"},
        **a, "run_info": run_info()}, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT_A.relative_to(BASE_DIR)}")

    b = part_b(args.trials_b)
    OUT_B.write_text(json.dumps({
        "schema": "lunar-ice/joint-calibration/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(), **common,
        "review_item": "M6",
        "seed": SEED_B, "trials_per_cell": args.trials_b,
        "grid": {"pop_dop": POP_DOP, "pop_cpr": POP_CPR, "N": LOOKS},
        "validity": "a (DOP, CPR) pair is simulated only if DOP >= |q|, q = (CPR-1)/(CPR+1)",
        "columns": {
            "p_dop_below": "P(m_hat < 0.13)",
            "p_cpr_gt_1": "P(R > 1)",
            "p_cpr_gt_crit": "P(R > crit_95), crit_95 the one-sided 95 % point of F(2N, 2N)",
            "p_joint_selection": "P(m_hat < 0.13 AND R > 1) -- the joint screen",
            "p_joint_and_significant": ("P(m_hat < 0.13 AND R > crit_95); zero by the "
                                        "sample identity m_hat >= |1-R|/(1+R) whenever "
                                        "crit_95 > 1.2989, i.e. N < 80")},
        **b, "run_info": run_info()}, indent=2), encoding="utf-8")
    print(f"  wrote {OUT_B.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
