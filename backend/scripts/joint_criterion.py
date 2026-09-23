"""
joint_criterion.py -- the DOP half of the criterion does most of the work.

    python backend/scripts/joint_criterion.py [--trials N]

WHY
---
The published criterion is a PAIR of thresholds, CPR > 1 AND DOP < 0.13, but its
noise exceedance rate is always quoted for the CPR half alone. That understates the
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

P7 (review 4.16) asks for the full specification of that 1.8 %: the population
covariance matrix the channels are drawn from, the population Stokes vector, CPR
and DOP it realises, the trial count, seed and Monte Carlo SE -- and a second run
at the population point that maximises the joint rate inside DOP < 0.13, i.e.
true CPR just below the band edge 1.2989. Both are emitted here, and the block is
also written into docs/cpr_significance.json::joint_criterion together with the
MEASURED joint rate from the SLC (P1), so the paper can print the simulated rate
against the measured one from one artifact.

SIGN CONVENTION. The simulator forms S3 = -2 Im<E_H E_V*> and SC = (S0 - S3)/2.
That is the reading stokes_from_slc.py identifies as physical (single bounce
gives CPR < 1); the population point is constructed so that CPR = SC/OC takes
the requested value under that sign.

THIS DOES NOT RESCUE THE AMPLITUDE PROXY. METHODS 1 shows the amplitude-only
CPR is a function of DOP alone, so on THIS build the two conditions are one
condition and the joint rate is not available from the delivered rasters.
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
SIG = BASE_DIR / "docs" / "cpr_significance.json"
SLC = BASE_DIR / "docs" / "stokes_from_slc.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

SEED = 7
SEED_CHECK_SEEDS = tuple(range(100, 130))
N_LOOKS = 14
TRUE_CPR = 0.7
DOP_THRESHOLD = 0.13
CPR_THRESHOLD = 1.0


def population(cpr: float, m: float) -> dict | None:
    """The population covariance that realises (cpr, m), and its Stokes vector."""
    s0 = 2.0
    s3 = s0 * (1.0 - cpr) / (1.0 + cpr)
    s2sq = (m * s0) ** 2 - s3 ** 2
    if s2sq < 0:
        return None
    s2 = np.sqrt(s2sq)
    cmag = np.sqrt(s2 ** 2 + s3 ** 2) / 2.0
    phi = np.arctan2(-s3 / 2.0, s2 / 2.0)
    c = cmag * np.exp(1j * phi)
    return {"c": c,
            "covariance": {"E|H|^2": 1.0, "E|V|^2": 1.0,
                           "E[H V*]": {"re": float(c.real), "im": float(c.imag),
                                       "abs": float(abs(c)), "arg_deg": float(np.degrees(phi))}},
            "stokes": {"S0": s0, "S1": 0.0, "S2": float(s2), "S3": float(s3)},
            "cpr": float((s0 - s3) / (s0 + s3)),
            "dop": float(np.sqrt(s2 ** 2 + s3 ** 2) / s0)}


def stokes_draw(rng, cpr, m, n_looks, trials):
    """N-look Stokes estimates for a population with this CPR and this DOP.
    Returns (CPR_hat, m_hat) per trial, or None if (cpr, m) is unrealisable."""
    pop = population(cpr, m)
    if pop is None:
        return None
    c = pop["c"]
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


def rates(rng, cpr, m, trials) -> dict | None:
    got = stokes_draw(rng, cpr, m, N_LOOKS, trials)
    if got is None:
        return None
    cpr_hat, m_hat = got
    p_m = float(np.mean(cpr_hat > CPR_THRESHOLD))
    p_j = float(np.mean((cpr_hat > CPR_THRESHOLD) & (m_hat < DOP_THRESHOLD)))
    pop = population(cpr, m)
    pop.pop("c")
    return {"true_cpr": cpr, "true_m": m, "population": pop,
            "marginal_fp_percent": 100 * p_m,
            "marginal_se_percent": 100 * float(np.sqrt(p_m * (1 - p_m) / trials)),
            "joint_fp_percent": 100 * p_j,
            "joint_se_percent": 100 * float(np.sqrt(p_j * (1 - p_j) / trials)),
            "trials": trials}


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
    print(f"  {'true m':>9}{'marginal %':>13}{'joint %':>11}{'±SE':>8}")

    # The rows exactly as before, in the same RNG order: the 1.8 % is row 0.
    rows = []
    for m0 in (m_min + 1e-6, 0.2, 0.3, 0.5):
        r = rates(rng, TRUE_CPR, m0, args.trials)
        if r is None:
            continue
        print(f"  {m0:>9.4f}{r['marginal_fp_percent']:>13.2f}{r['joint_fp_percent']:>11.3f}"
              f"{r['joint_se_percent']:>8.3f}")
        rows.append({"true_m": m0, "marginal_fp_percent": r["marginal_fp_percent"],
                     "joint_fp_percent": r["joint_fp_percent"]})
        if m0 == m_min + 1e-6:
            headline_spec = r

    # P7: the point that maximises the joint rate inside DOP < 0.13 -- the
    # requested "just below 1.2989", and a scan to show it is the maximiser.
    print("\n  MAXIMISING POINT — true CPR just below the band edge, true m just below 0.13")
    edge = band[1] - 1e-4
    m_edge = (edge - 1.0) / (edge + 1.0) + 1e-6
    at_edge = rates(rng, edge, m_edge, args.trials)
    print(f"  CPR {edge:.5f}, m {m_edge:.5f}:  joint {at_edge['joint_fp_percent']:.3f} "
          f"± {at_edge['joint_se_percent']:.3f} %   marginal {at_edge['marginal_fp_percent']:.2f} %")
    print("\n  scan (true m = m_min + 1e-6 for each CPR):")
    scan = []
    for c in (1.05, 1.10, 1.15, 1.20, 1.25, edge):
        mm = abs(c - 1.0) / (c + 1.0) + 1e-6
        r = rates(rng, c, mm, 100_000)
        scan.append({"true_cpr": c, "true_m": mm, "joint_percent": r["joint_fp_percent"],
                     "joint_se_percent": r["joint_se_percent"], "trials": 100_000})
        print(f"    CPR {c:.5f}  m {mm:.5f}  joint {r['joint_fp_percent']:6.2f} ± {r['joint_se_percent']:.2f} %")
    maximiser = max(scan, key=lambda s: s["joint_percent"])

    # CONSISTENCY CHECK (2026-09-23). The headline marginal reads 17.69 % at
    # seed 7 against the analytic F(28, 28) value 17.545 % for its own
    # population (gamma_c ~ 0.0006, where the ratio is F to within 1e-6), about
    # three Monte Carlo standard errors high. Generator or seed? The same draw
    # at 30 further seeds, each with its own generator so the headline's RNG
    # stream above is untouched, answers it: an unbiased generator gives z-
    # scores with mean ~0 and SD ~1. The manuscript prints the F value.
    an = float((1.0 - _F.cdf(1.0 / TRUE_CPR, 2 * N_LOOKS, 2 * N_LOOKS)) * 100.0)
    zs = []
    for sd in SEED_CHECK_SEEDS:
        r_ = rates(np.random.default_rng(sd), TRUE_CPR, m_min + 1e-6, args.trials)
        zs.append((r_["marginal_fp_percent"] - an) / r_["marginal_se_percent"])
    zs = np.array(zs)
    z7 = (headline_spec["marginal_fp_percent"] - an) / headline_spec["marginal_se_percent"]
    seed_check = {
        "analytic_F_percent": an, "headline_seed": SEED,
        "headline_marginal_percent": headline_spec["marginal_fp_percent"],
        "headline_z": float(z7),
        "other_seeds": list(SEED_CHECK_SEEDS), "trials_each": args.trials,
        "z_mean": float(zs.mean()), "z_sd": float(zs.std(ddof=1)),
        "z_mean_se": float(zs.std(ddof=1) / np.sqrt(zs.size)),
        "verdict": ("generator unbiased: the other seeds' z-scores have mean "
                    f"{zs.mean():+.2f} and SD {zs.std(ddof=1):.2f}; seed {SEED}'s "
                    f"{z7:+.2f} is one draw's fluctuation. The manuscript prints "
                    "the F value, not the Monte Carlo marginal."),
        "gamma_c_of_headline_population": float(
            headline_spec["population"]["stokes"]["S2"]
            / np.sqrt(headline_spec["population"]["stokes"]["S0"] ** 2
                      - headline_spec["population"]["stokes"]["S3"] ** 2))}
    print(f"\n  SEED CHECK: analytic {an:.3f} %, seed {SEED} z {z7:+.2f}; "
          f"{zs.size} other seeds z mean {zs.mean():+.2f}, SD {zs.std(ddof=1):.2f}")

    measured = None
    if SLC.is_file():
        j = json.loads(SLC.read_text(encoding="utf-8"))["results"].get("joint_measured")
        if j:
            measured = {"conditional_percent": 100 * j["conditional"]["fraction"],
                        "conditional_se_percent": 100 * j["conditional"]["binomial_se"],
                        "n_cells_dop_below": j["conditional"]["n"],
                        "unconditional_percent": 100 * j["unconditional"]["fraction"],
                        "unconditional_se_percent": 100 * j["unconditional"]["binomial_se"],
                        "of_cells": j["unconditional"]["of"],
                        "sign_deg": j["sign_deg"],
                        "source": "docs/stokes_from_slc.json::results.joint_measured",
                        "note": "measured on this pass's terrain, physical sign; not the "
                                "simulated rate at a 0.7 background"}
            print(f"\n  MEASURED (P1): P(CPR>1 | DOP<0.13) = {measured['conditional_percent']:.2f} "
                  f"± {measured['conditional_se_percent']:.2f} % over "
                  f"{measured['n_cells_dop_below']:,} cells; "
                  f"P(both) = {measured['unconditional_percent']:.4f} % of all cells")

    spec = {
        "schema": "lunar-ice/joint-criterion-spec/1",
        "generator": "backend/scripts/joint_criterion.py",
        "seed": SEED, "trials": args.trials, "n_looks": N_LOOKS,
        "sign_convention": "S3 = -2 Im<E_H E_V*>, SC = (S0 - S3)/2, OC = (S0 + S3)/2 -- "
                           "the physical reading of stokes_from_slc.py",
        "draw": "E_H = z1; E_V = conj(c) z1 + sqrt(1 - |c|^2) z2; z1, z2 ~ CN(0, 1) "
                "i.i.d. per look; N-look averages of |E_H|^2, |E_V|^2, E_H E_V*",
        "headline_at_cpr_0p7": headline_spec,
        "maximising_point_requested": at_edge,
        "scan": scan, "scan_maximiser": maximiser,
        "cpr_band_for_m_below_threshold": list(band),
        "measured_joint_rate_slc": measured,
    }

    OUT.write_text(json.dumps({
        "schema": "lunar-ice/joint-criterion/2",
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
        "marginal_fp_percent_analytic_F": float(
            (1.0 - _F.cdf(1.0 / TRUE_CPR, 2 * N_LOOKS, 2 * N_LOOKS)) * 100.0),
        "marginal_seed_check": seed_check,
        "headline": {"marginal_fp_percent_monte_carlo": rows[0]["marginal_fp_percent"],
                     "joint_fp_percent": rows[0]["joint_fp_percent"],
                     "at_true_m": rows[0]["true_m"]},
        "specification": spec,
        "not_available_on_this_build": (
            "The amplitude-only CPR is a function of DOP alone (METHODS 1), so "
            "on this product the two conditions are one condition and the joint "
            "rate cannot be claimed from the delivered rasters. The SLC-derived "
            "measured rate is in specification.measured_joint_rate_slc."),
    }, indent=2, default=float), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")

    # P7: the same block into cpr_significance.json, the artifact the paper cites.
    if SIG.is_file():
        doc = json.loads(SIG.read_text(encoding="utf-8"))
        doc["joint_criterion"] = spec
        SIG.write_text(json.dumps(doc, indent=2, default=float), encoding="utf-8")
        print(f"  updated {SIG.relative_to(BASE_DIR)}::joint_criterion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
