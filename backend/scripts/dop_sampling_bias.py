"""
dop_sampling_bias.py -- the sample DOP at finite N, and what the joint screen selects.

    python backend/scripts/dop_sampling_bias.py            # both artifacts
    python backend/scripts/dop_sampling_bias.py --trials-a 400000 --trials-b 100000
    python backend/scripts/dop_sampling_bias.py --curve      # joint_power_curve.json

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
from scipy.linalg import toeplitz
from scipy.optimize import brentq
from scipy.special import betaln
from scipy.stats import beta as Beta
from scipy.stats import f as Fdist

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT_A = BASE_DIR / "docs" / "dop_sampling_bias.json"
OUT_B = BASE_DIR / "docs" / "joint_calibration.json"
OUT_C = BASE_DIR / "docs" / "joint_power_curve.json"

# ---- council work order, Task 1: the joint rule as a test across N ---------
SEED_C = 20261001
CURVE_N = (5, 8, 14, 16, 17, 18, 19, 20, 21, 30, 38, 60, 80, 100, 150, 200)
CURVE_TRIALS = 100_000
TEXTURE_SHAPE = 8.0
#: the product's azimuth INTENSITY lag correlations at lags 1-3 (enl.json); the
#: look fields get their square roots. Truncating the field ACF after lag 3 is
#: not a valid covariance (its spectrum goes negative at the Nyquist), so the
#: field ACF is continued geometrically at the measured lag-2-to-3 ratio, which
#: reproduces the intensity ACF's own decay (~0.65 per lag).
LOOK_LAGS_INTENSITY = (0.838, 0.565, 0.363)
N_EDGE = 79.6166

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


def look_acf(n: int) -> np.ndarray:
    """Field correlation between looks k apart (arm C)."""
    r = np.sqrt(np.array(LOOK_LAGS_INTENSITY))
    ratio = r[2] / r[1]
    a = np.empty(n)
    a[0] = 1.0
    for k in range(1, n):
        a[k] = r[k - 1] if k <= 3 else r[2] * ratio ** (k - 3)
    return a


def arm_c_factor(n: int):
    """Cholesky factor of the look correlation, its minimum eigenvalue, and the
    participation ratio (the looks it is worth)."""
    C = toeplitz(look_acf(n))
    ev = np.linalg.eigvalsh(C)
    return np.linalg.cholesky(C), float(ev.min()), float(ev.sum() ** 2 / (ev ** 2).sum())


def simulate_arm(rng, arm: str, n_looks: int, trials: int, cpr: float, gamma: float,
                 chol=None):
    """Sample CPR and sample DOP for `trials` cells of `n_looks` looks.

    arm "A": independent equal-weight looks (the model of simulate());
    arm "B": each look's 2-vector scaled by sqrt(T), T ~ Gamma(8, 1/8) per look,
             common to both channels -- within-cell texture;
    arm "C": looks correlated along the look index with the product's azimuth
             lag correlations (look_acf), the same for both channel processes.
    """
    a, b = cpr / (1 + cpr), 1 / (1 + cpr)
    chunk = max(1000, min(CHUNK, int(4e6 // max(n_looks, 1))))
    r_all, m_all = [], []
    done = 0
    while done < trials:
        n = min(chunk, trials - done)
        w1 = (rng.standard_normal((n, n_looks)) + 1j * rng.standard_normal((n, n_looks))) / np.sqrt(2)
        w2 = (rng.standard_normal((n, n_looks)) + 1j * rng.standard_normal((n, n_looks))) / np.sqrt(2)
        if arm == "C":
            w1, w2 = w1 @ chol.T, w2 @ chol.T
        z1 = np.sqrt(a) * w1
        z2 = np.sqrt(b) * (gamma * w1 + np.sqrt(1 - gamma * gamma) * w2)
        if arm == "B":
            t = np.sqrt(rng.gamma(TEXTURE_SHAPE, 1.0 / TEXTURE_SHAPE, (n, n_looks)))
            z1, z2 = z1 * t, z2 * t
        ah = (np.abs(z1) ** 2).mean(axis=1)
        bh = (np.abs(z2) ** 2).mean(axis=1)
        ch = (z1 * np.conj(z2)).mean(axis=1)
        r_all.append(ah / bh)
        m_all.append(np.sqrt((ah - bh) ** 2 + 4 * np.abs(ch) ** 2) / (ah + bh))
        done += n
    return np.concatenate(r_all), np.concatenate(m_all)


def curve_populations():
    """Task 1's populations: null, in band, ice-free. (label, cpr, dop, kind)"""
    pops = [(f"null CPR 1.00 DOP {d:.2f}", 1.0, d, "null") for d in (0.0, 0.05, 0.10, 0.13)]
    for c in (1.05, 1.1, 1.2, 1.25, 1.299):
        q = abs(c - 1) / (c + 1)
        pops.append((f"band CPR {c} DOP min {q:.4f}", c, q, "band"))
        if q <= DOP_THRESHOLD:
            pops.append((f"band CPR {c} DOP 0.13", c, DOP_THRESHOLD, "band"))
    for c in (0.5, 0.7, 0.9):
        q = abs(c - 1) / (c + 1)
        pops.append((f"ice-free CPR {c} DOP min {q:.4f}", c, q, "ice_free"))
        for d in (0.20, 0.30):
            if d >= q:
                pops.append((f"ice-free CPR {c} DOP {d:.2f}", c, d, "ice_free"))
    return pops


def mean_sample_dop_unpolarized(n: float) -> float:
    """E[m_hat] for an unpolarized population: m_hat^2 ~ Beta(3/2, N-1), so
    E[m_hat] = B(2, N-1) / B(3/2, N-1)."""
    return float(np.exp(betaln(2.0, n - 1.0) - betaln(1.5, n - 1.0)))


def n_where_mean_dop_is(target: float) -> float:
    return float(brentq(lambda n: mean_sample_dop_unpolarized(n) - target, 1.5, 1e6))


def strict_band(cn, band) -> dict:
    keep = {c["population"] for c in cn if c["kind"] == "band" and c["pop_dop"] < DOP_THRESHOLD - 1e-12}
    sb = [b for b in band if b["population"] in keep]
    return {"populations": [b["population"] for b in sb],
            "power_min_percent": min(b["power_percent"] for b in sb),
            "power_max_percent": max(b["power_percent"] for b in sb),
            "max_ratio_to_null_same_dop": max(b["ratio_to_null_same_dop"] for b in sb),
            "max_excess_over_null_same_dop_percent":
                100 * (max(b["ratio_to_null_same_dop"] for b in sb) - 1)}


def curve_summary(cells):
    """Per-N size and in-band rates of one arm. The STRICT band keeps only the
    in-band populations with population DOP < 0.13 (the band's definition):
    'DOP 0.13' and 'CPR 1.299 DOP min 0.1301' sit on or outside its edge."""
    out = []
    for n in CURVE_N:
        cn = [c for c in cells if c["N"] == n]
        nulls = [c for c in cn if c["kind"] == "null"]
        size_c = max(nulls, key=lambda c: c["p_joint"]["percent"])
        nd = np.array([c["pop_dop"] for c in nulls])
        nv = np.array([c["p_joint"]["percent"] for c in nulls])
        band = []
        for c in (c for c in cn if c["kind"] == "band"):
            ref = float(np.interp(c["pop_dop"], nd, nv))
            band.append({"population": c["population"], "power_percent": c["p_joint"]["percent"],
                         "mc_se_percent": c["p_joint"]["mc_se_percent"],
                         "null_at_same_dop_percent": ref,
                         "ratio_to_null_same_dop": c["p_joint"]["percent"] / ref if ref > 0 else None})
        out.append({"N": n, "size_percent": size_c["p_joint"]["percent"],
                    "size_mc_se_percent": size_c["p_joint"]["mc_se_percent"],
                    "size_at": size_c["population"],
                    "power_max_percent": max(b["power_percent"] for b in band),
                    "power_min_percent": min(b["power_percent"] for b in band),
                    "max_ratio_to_null": max(b["ratio_to_null_same_dop"] for b in band
                                             if b["ratio_to_null_same_dop"]),
                    "band": band,
                    "strict_band": strict_band(cn, band),
                    "joint_and_significant_count": sum(c["n_joint_and_significant"] for c in cn)})
    first_size = next((r["N"] for r in out if r["size_percent"] > 5.0), None)
    first_sig = next((r["N"] for r in out if r["joint_and_significant_count"] > 0), None)
    below_edge_zero = all(r["joint_and_significant_count"] == 0 for r in out if r["N"] < N_EDGE)
    first_2se = next((r["N"] for r in out
                      if r["size_percent"] + 2 * r["size_mc_se_percent"] >= 5.0), None)
    return {"by_N": out, "first_N_size_exceeds_5pct": first_size,
            "first_N_size_within_2se_of_5pct": first_2se,
            "first_N_joint_and_significant_nonzero": first_sig,
            "joint_and_significant_zero_for_every_N_below_79p6": below_edge_zero}


def part_c(trials: int) -> dict:
    """The joint rule as a test across N, three arms."""
    rng = np.random.default_rng(SEED_C)
    pops = curve_populations()
    arms = {}
    for arm in ("A", "B", "C"):
        cells = []
        chol_info = {}
        for n in CURVE_N:
            chol = None
            if arm == "C":
                chol, ev_min, pr = arm_c_factor(n)
                chol_info[str(n)] = {"min_eigenvalue": ev_min, "effective_looks": pr}
            crit = float(Fdist.ppf(0.95, 2 * n, 2 * n))
            for label, cpr, dop, kind in pops:
                g = gamma_c_for(dop, cpr)
                r, m = simulate_arm(rng, arm, n, trials, cpr, g, chol)
                low, gt1, gtc = m < DOP_THRESHOLD, r > CPR_THRESHOLD, r > crit
                cells.append({"N": n, "population": label, "kind": kind, "pop_cpr": cpr,
                              "pop_dop": dop, "gamma_c": g, "crit_95": crit,
                              "p_joint": rate(low & gt1), "p_dop_below": rate(low),
                              "p_cpr_gt_1": rate(gt1), "p_cpr_gt_crit": rate(gtc),
                              "p_joint_and_significant": rate(low & gtc),
                              "n_joint_and_significant": int((low & gtc).sum())})
            size = max(c["p_joint"]["percent"] for c in cells if c["N"] == n and c["kind"] == "null")
            print(f"  arm {arm} N {n:>3}: size {size:6.3f} %", flush=True)
        arms[arm] = {"cells": cells, "look_correlation": chol_info or None}

    summ = {arm: curve_summary(v["cells"]) for arm, v in arms.items()}
    a14 = next(r for r in summ["A"]["by_N"] if r["N"] == 14)
    gate = {"arm_A_N14_size_percent": a14["size_percent"], "reference_percent": 3.575,
            "mc_se_percent": a14["size_mc_se_percent"],
            "z": (a14["size_percent"] - 3.575) / a14["size_mc_se_percent"],
            "reproduces": abs(a14["size_percent"] - 3.575) <= 3 * a14["size_mc_se_percent"] * 2 ** 0.5,
            "zero_below_edge_every_arm": all(summ[a]["joint_and_significant_zero_for_every_N_below_79p6"]
                                             for a in summ)}
    gate["verdict"] = "PASS" if gate["reproduces"] and gate["zero_below_edge_every_arm"] else "FAIL"
    return {"arms": arms, "summary": summ, "gate": gate, "populations": [p[0] for p in pops]}


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


def grid_summaries(cells: list) -> dict:
    """The figures Sections III-E and V-A print from this grid, computed here
    so each resolves to one key. Percent throughout."""
    def c(n, cpr, dop):
        return next(x for x in cells if x["N"] == n and abs(x["pop_cpr"] - cpr) < 1e-9
                    and abs(x["pop_dop"] - dop) < 1e-9)

    out = {}
    for n in LOOKS:
        nulls = [x for x in cells if x["N"] == n and x["pop_cpr"] == 1.0
                 and x["pop_dop"] <= DOP_THRESHOLD + 1e-12]
        band = [x for x in cells if x["N"] == n and x["pop_cpr"] in (1.1, 1.2)
                and x["pop_dop"] <= DOP_THRESHOLD + 1e-12]
        ratios = []
        for x in (x for x in cells if x["N"] == n and 1.0 < x["pop_cpr"] < 1.3
                  and x["pop_dop"] <= DOP_THRESHOLD + 1e-12):
            ref = [y for y in nulls if abs(y["pop_dop"] - x["pop_dop"]) < 1e-9]
            if ref:
                ratios.append({"pop_cpr": x["pop_cpr"], "pop_dop": x["pop_dop"],
                               "ratio": x["p_joint_selection"]["percent"]
                                        / ref[0]["p_joint_selection"]["percent"]})
        qual = [x for x in cells if x["N"] == n and x["pop_dop"] <= DOP_THRESHOLD + 1e-12]
        d20 = [x for x in cells if x["N"] == n and abs(x["pop_dop"] - 0.2) < 1e-9]
        d30 = [x for x in cells if x["N"] == n and abs(x["pop_dop"] - 0.3) < 1e-9]
        blk = {
            "size_percent": max(x["p_joint_selection"]["percent"] for x in nulls),
            "null_selection_range_percent": [min(x["p_joint_selection"]["percent"] for x in nulls),
                                             max(x["p_joint_selection"]["percent"] for x in nulls)],
            "band_1p1_1p2_selection_range_percent": [
                min(x["p_joint_selection"]["percent"] for x in band),
                max(x["p_joint_selection"]["percent"] for x in band)],
            "max_band_over_null_same_dop": max(r["ratio"] for r in ratios),
            "max_band_over_null_same_dop_excess_percent": 100 * (max(r["ratio"] for r in ratios) - 1),
            "band_over_null_rows": ratios,
            "dop_gate_pass_qualifying_range_percent": [
                min(x["p_dop_below"]["percent"] for x in qual),
                max(x["p_dop_below"]["percent"] for x in qual)],
            "dop_gate_pass_at_dop_0p20_range_percent": [
                min(x["p_dop_below"]["percent"] for x in d20),
                max(x["p_dop_below"]["percent"] for x in d20)],
            "dop_gate_pass_at_dop_0p30_range_percent": [
                min(x["p_dop_below"]["percent"] for x in d30),
                max(x["p_dop_below"]["percent"] for x in d30)],
            "cpr0p7_joint_at_dop_0p20_percent": c(n, 0.7, 0.2)["p_joint_selection"]["percent"],
            "cpr0p7_joint_at_dop_0p30_percent": c(n, 0.7, 0.3)["p_joint_selection"]["percent"],
            "gate_effect_cpr1p1_dop0p10": {
                "p_cpr_gt_1_percent": c(n, 1.1, 0.1)["p_cpr_gt_1"]["percent"],
                "p_joint_percent": c(n, 1.1, 0.1)["p_joint_selection"]["percent"]}}
        out[f"N{n}"] = blk
    return out


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
    summaries = grid_summaries(cells)
    print(f"    cells in which a jointly selected cell exceeded the critical value: {sig}")
    return {"cells": cells, "invalid_pairs": invalid,
            "joint_and_significant_nonzero_cells": sig, "summaries": summaries}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials-a", type=int, default=400_000)
    ap.add_argument("--trials-b", type=int, default=100_000)
    ap.add_argument("--curve", action="store_true",
                    help="run only Task 1's joint power curve -> joint_power_curve.json")
    ap.add_argument("--strict-summary", action="store_true",
                    help=("recompute joint_power_curve.json's summaries from its stored cells "
                          "(no simulation) -- adds the strict-band keys"))
    args = ap.parse_args()
    if args.strict_summary:
        doc = json.loads(OUT_C.read_text(encoding="utf-8"))
        for arm in ("A", "B", "C"):
            new = curve_summary(doc["arms"][arm]["cells"])
            old = doc["summary"][arm]
            for r0, r1 in zip(old["by_N"], new["by_N"]):
                assert r0["size_percent"] == r1["size_percent"] and r0["band"] == r1["band"], arm
            assert old["first_N_size_exceeds_5pct"] == new["first_N_size_exceeds_5pct"]
            doc["summary"][arm] = new
            for r in new["by_N"]:
                if r["N"] in (14, 38):
                    sb = r["strict_band"]
                    print(f"  arm {arm} N {r['N']}: strict band {sb['power_min_percent']:.3f}-"
                          f"{sb['power_max_percent']:.3f} % (size {r['size_percent']:.3f}); max ratio "
                          f"{sb['max_ratio_to_null_same_dop']:.4f}")
            print(f"  arm {arm}: size first > 5 % at N = {new['first_N_size_exceeds_5pct']}, "
                  f"within 2 SE of 5 % at N = {new['first_N_size_within_2se_of_5pct']}")
        doc["definitions"]["strict_band"] = ("in-band populations with population DOP < 0.13 only "
                                             "(drops 'DOP 0.13' and 'CPR 1.299 DOP min 0.1301')")
        doc["run_info_strict_summary"] = run_info()
        OUT_C.write_text(json.dumps(doc, indent=2, default=float), encoding="utf-8")
        print(f"  rewrote the summaries of {OUT_C.relative_to(BASE_DIR)}")
        return 0
    if args.curve:
        print("=" * 78)
        print("THE JOINT RULE AS A TEST ACROSS N — three arms")
        print("=" * 78)
        c = part_c(CURVE_TRIALS)
        OUT_C.write_text(json.dumps({
            "schema": "lunar-ice/joint-power-curve/1",
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "generator": "backend/scripts/dop_sampling_bias.py --curve",
            "seed": SEED_C, "trials_per_cell": CURVE_TRIALS, "N_grid": list(CURVE_N),
            "rule": "sample DOP < 0.13 AND sample CPR > 1, Stokes formed per cell",
            "arms": {"A": "independent equal-weight circular complex Gaussian looks",
                     "B": f"per-look Gamma({TEXTURE_SHAPE:g}, 1/{TEXTURE_SHAPE:g}) texture common to both channels",
                     "C": ("looks correlated along the look index: field correlation sqrt(0.838, "
                           "0.565, 0.363) at lags 1-3, continued geometrically (ratio "
                           "sqrt(0.363/0.565)); valid for every N (look_correlation.min_eigenvalue)")},
            "definitions": {
                "size": "max over the null cells (CPR 1.00, DOP 0-0.13) of P(joint)",
                "power": "P(joint) at the in-band populations",
                "ratio_to_null_same_dop": "P(joint) in band / P(joint) at CPR 1.00 interpolated to the same DOP",
                "joint_and_significant": "P(joint AND R > crit_95(F(2N, 2N)))"},
            **c, "run_info": run_info()}, indent=2, default=float), encoding="utf-8")
        print(f"\n  gate: {c['gate']}")
        print(f"  wrote {OUT_C.relative_to(BASE_DIR)}")
        return 0 if c["gate"]["verdict"] == "PASS" else 1
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
    a["mean_sample_dop_unpolarized"] = {
        "formula": "E[m_hat] = B(2, N-1) / B(3/2, N-1) for m_hat^2 ~ Beta(3/2, N-1)",
        "N_where_mean_is_0p13": n_where_mean_dop_is(0.13),
        "N_where_mean_is_0p10": n_where_mean_dop_is(0.10),
        "at_N14": mean_sample_dop_unpolarized(14.0)}
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
