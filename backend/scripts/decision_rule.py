"""
decision_rule.py -- a calibrated replacement for the joint rule. (council work
order, Task 3; simulation, then applied to the complex product)

    python backend/scripts/decision_rule.py

THE RULE
--------
(a) CPR test. Reject CPR <= 1 when R > F^-1_0.95(2 N_hat, 2 N_hat), N_hat
    estimated from Var(ln R) on a 31 x 31 window (enl_logratio.py's
    estimator, N_SC = N_OC = N_hat). Its size is inflated or deflated by
    plugging in an estimate; that is what is measured.
(b) DOP test. Reject population DOP >= 0.13 when the sample DOP is below the
    5 % quantile of its sampling law at population DOP 0.13 and the look
    count. For a 2 x 2 Wishart the law of the sample DOP depends on the
    population only through its DOP (the eigenvalue ratio), so one quantile
    curve q05(N), simulated at DOP 0.13 under arm A and interpolated in log N,
    serves every population. At DOP 0 the law is Beta(3/2, N-1) for m_hat^2.
(c) Joint test. Intersection-union: select a cell only if BOTH reject. Its
    size is at most the larger of the two component sizes over the null
    region {CPR <= 1} union {DOP >= 0.13}.

HOW THE PLUG-IN IS SIMULATED
----------------------------
Cells are drawn from dop_sampling_bias.simulate_arm (the arms of Task 1). A
window of W cells from the SAME population gives N_hat. W = 960 is a 31 x 31
window of independent cells; W = 16 is what a 31 x 31 window holds on the
product, whose CPR field carries one independent sample per 61.42 pixels
(cpr_significance.json::effective_samples). Windows are drawn from a pool of
the population's cells; the tested cell is drawn separately. The "oracle"
columns use the true nominal N instead of N_hat.

FINAL PASS (B1, B5)
-------------------
61.42 px is the DELIVERED grid's correlation area; the 31 x 31 window is
applied on the COMPLEX grid, so W = 16 mixes grids. complex_grid.py measures A
on the complex grid (Stokes CPR, 109 homogeneous blocks); W_complex = 961 / A
(median) is added as a third plug-in variant, "plugin_Wcomplex", its N_hat
drawn from a SEPARATE generator (seed SEED_WCOMPLEX) so every existing row
reproduces draw for draw. apply_to_product adds the maximum and 99th
percentile of N_hat, and the counts of cells with N_hat >= 79.6, 218 and 254,
over all cells and over the cells the published rule selects. `iut_onset`
records where (crit - 1)/(crit + 1) first falls below q05(N) on the table's
grid.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.stats import f as Fdist

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402
import dop_sampling_bias as D  # noqa: E402
import enl_logratio as L  # noqa: E402
import stokes_from_slc as SFS  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "decision_rule.json"
SEED = 20261002
N_EVAL = (14, 38, 100)
TEST_CELLS = 20_000
POOL = 40_000
WINDOWS = (960, 16)
SEED_WCOMPLEX = 20261007
GRID_JSON = BASE_DIR / "docs" / "complex_grid_correlation.json"
N_THRESHOLDS = (79.6166, 218.0, 254.0)
Q_GRID = tuple(int(x) for x in np.unique(np.round(np.geomspace(2, 400, 36))))
Q_TRIALS = 200_000
ALPHA = 0.05

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def rate(x) -> dict:
    x = np.asarray(x, dtype=bool)
    p = float(x.mean())
    return {"percent": 100 * p, "mc_se_percent": 100 * float(np.sqrt(p * (1 - p) / x.size))}


def q05_table(rng) -> dict:
    """5 % quantile of the sample DOP at population DOP 0.13, arm A."""
    g = D.gamma_c_for(0.13, 1.0)
    out = {}
    for n in Q_GRID:
        _, m = D.simulate(rng, n, Q_TRIALS, 1.0, g)
        out[n] = float(np.quantile(m, ALPHA))
    return out


def q05_at(n, table) -> np.ndarray:
    ns = np.array(sorted(table))
    qs = np.array([table[k] for k in ns])
    n = np.clip(np.asarray(n, dtype=float), ns[0], ns[-1])
    return np.interp(np.log(n), np.log(ns), qs)


def crit(n):
    return Fdist.ppf(1 - ALPHA, 2 * np.asarray(n, dtype=float), 2 * np.asarray(n, dtype=float))


def plugin_n(rng, lr_pool: np.ndarray, w: int, cells: int) -> np.ndarray:
    out = np.empty(cells)
    step = max(1, int(2e7 // w))
    for i in range(0, cells, step):
        k = min(step, cells - i)
        idx = rng.integers(0, lr_pool.size, (k, w))
        out[i:i + k] = L.n_from_var(lr_pool[idx].var(axis=1, ddof=1))
    return out


def w_complex() -> int:
    return int(json.loads(GRID_JSON.read_text(encoding="utf-8"))["window_31x31"]["W_used"])


def iut_onset(qtab) -> dict:
    """Where the IUT first has a rejection region on the q05 grid: the sample
    identity needs (crit - 1)/(crit + 1) < q05(N)."""
    ns = sorted(qtab)
    edge = {n: float((crit(n) - 1) / (crit(n) + 1)) for n in ns}
    opens = [n for n in ns if edge[n] < qtab[n]]
    first = opens[0] if opens else None
    last_closed = max(n for n in ns if n < first) if first else None
    return {"last_N_without_region": last_closed, "first_N_with_region": first,
            "edge_at": {str(n): edge[n] for n in ns}, "q05_at": {str(n): qtab[n] for n in ns},
            "rule": "(crit95(N) - 1)/(crit95(N) + 1) < q05(N) at population DOP 0.13"}


def simulate_cells(rng, qtab) -> dict:
    pops = D.curve_populations()
    rng_w = np.random.default_rng(SEED_WCOMPLEX)
    wc = w_complex()
    res = {}
    for arm in ("A", "B", "C"):
        rows = []
        for n in N_EVAL:
            chol = D.arm_c_factor(n)[0] if arm == "C" else None
            c_or, q_or = float(crit(n)), float(q05_at(n, qtab))
            for label, cpr, dop, kind in pops:
                g = D.gamma_c_for(dop, cpr)
                r, m = D.simulate_arm(rng, arm, n, TEST_CELLS, cpr, g, chol)
                rp, _ = D.simulate_arm(rng, arm, n, POOL, cpr, g, chol)
                lrp = np.log(rp)
                row = {"arm": arm, "N": n, "population": label, "kind": kind,
                       "pop_cpr": cpr, "pop_dop": dop,
                       "null_cpr": cpr <= 1.0, "null_dop": dop >= 0.13 - 1e-12,
                       "oracle": {"cpr_test": rate(r > c_or), "dop_test": rate(m < q_or),
                                  "joint_iut": rate((r > c_or) & (m < q_or))}}
                for w in WINDOWS:
                    nh = plugin_n(rng, lrp, w, TEST_CELLS)
                    a_ = r > crit(nh)
                    b_ = m < q05_at(nh, qtab)
                    row[f"plugin_W{w}"] = {"N_hat_median": float(np.nanmedian(nh)),
                                           "N_hat_iqr": [float(np.nanpercentile(nh, 25)),
                                                         float(np.nanpercentile(nh, 75))],
                                           "cpr_test": rate(a_), "dop_test": rate(b_),
                                           "joint_iut": rate(a_ & b_),
                                           "sinha_joint": rate((m < 0.13) & (r > 1.0))}
                nh = plugin_n(rng_w, lrp, wc, TEST_CELLS)
                a_ = r > crit(nh)
                b_ = m < q05_at(nh, qtab)
                row["plugin_Wcomplex"] = {"W": wc, "N_hat_median": float(np.nanmedian(nh)),
                                          "N_hat_iqr": [float(np.nanpercentile(nh, 25)),
                                                        float(np.nanpercentile(nh, 75))],
                                          "cpr_test": rate(a_), "dop_test": rate(b_),
                                          "joint_iut": rate(a_ & b_),
                                          "sinha_joint": rate((m < 0.13) & (r > 1.0))}
                rows.append(row)
            print(f"  arm {arm} N {n:>3}: done", flush=True)
        res[arm] = rows
    return res


def summarize(rows) -> dict:
    out = {}
    for arm in ("A", "B", "C"):
        for n in N_EVAL:
            rs = [r for r in rows[arm] if r["N"] == n]
            blk = {}
            for variant in ["oracle"] + [f"plugin_W{w}" for w in WINDOWS] + ["plugin_Wcomplex"]:
                cpr_null = [r for r in rs if r["null_cpr"]]
                dop_null = [r for r in rs if r["null_dop"]]
                iut_null = [r for r in rs if r["null_cpr"] or r["null_dop"]]
                alt = [r for r in rs if not r["null_cpr"] and not r["null_dop"]]
                pick = lambda lst, test: max(lst, key=lambda r: r[variant][test]["percent"])  # noqa: E731
                a_sz, b_sz, j_sz = pick(cpr_null, "cpr_test"), pick(dop_null, "dop_test"), pick(iut_null, "joint_iut")
                blk[variant] = {
                    "cpr_test_size_percent": a_sz[variant]["cpr_test"]["percent"],
                    "cpr_test_size_at": a_sz["population"],
                    "dop_test_size_percent": b_sz[variant]["dop_test"]["percent"],
                    "dop_test_size_at": b_sz["population"],
                    "dop_test_power_at_dop0_percent": next(
                        r[variant]["dop_test"]["percent"] for r in rs if r["population"].endswith("DOP 0.00")),
                    "iut_size_percent": j_sz[variant]["joint_iut"]["percent"],
                    "iut_size_mc_se_percent": j_sz[variant]["joint_iut"]["mc_se_percent"],
                    "iut_size_at": j_sz["population"],
                    "iut_power_percent": {r["population"]: r[variant]["joint_iut"]["percent"] for r in alt}}
            out[f"{arm}_N{n}"] = blk
    return out


def apply_to_product(pass_id: str, qtab) -> dict:
    SFS.configure(pass_id)
    hh, vv, hv, _ = SFS.build_coherency(0)
    s0, s1 = hh + vv, hh - vv
    s2, s3 = 2.0 * hv.real, -2.0 * hv.imag
    m = (hh > 0) & (vv > 0) & (s0 > 0)
    del hh, vv, hv
    sc, oc = 0.5 * (s0 - s3), 0.5 * (s0 + s3)
    ok = m & (sc > 0) & (oc > 0)
    lr = np.where(ok, np.log(np.where(ok, sc, 1.0) / np.where(ok, oc, 1.0)), np.nan)
    mh = np.where(m, np.sqrt(s1 ** 2 + s2 ** 2 + s3 ** 2) / np.where(m, s0, 1.0), np.nan)
    del s0, s1, s2, s3, sc, oc
    nh, cnt = L.local_n(lr, ok)
    valid = ok & np.isfinite(nh)
    r = np.exp(lr[valid])
    n_ = nh[valid]
    m_ = mh[valid]
    a_ = r > crit(n_)
    b_ = m_ < q05_at(n_, qtab)
    sinha = (m_ < 0.13) & (r > 1.0)
    ns = n_[sinha]
    counts = {f"n_ge_{t:g}".replace(".", "p"): int((n_ >= t).sum()) for t in N_THRESHOLDS}
    counts_sel = {f"n_ge_{t:g}".replace(".", "p"): int((ns >= t).sum()) for t in N_THRESHOLDS}
    out = {"pass": pass_id, "cells_evaluated": int(valid.sum()),
           "local_N_hat": {**L.describe(n_), "max": float(n_.max()),
                           "p99": float(np.percentile(n_, 99))},
           "local_N_hat_counts": counts,
           "published_rule_cells": {"cells": int(sinha.sum()), "local_N_hat_counts": counts_sel,
                                    "local_N_hat_p99": float(np.percentile(ns, 99)) if ns.size else None,
                                    "local_N_hat_max": float(ns.max()) if ns.size else None,
                                    "local_N_hat_median": float(np.median(ns)) if ns.size else None},
           "any_N_hat_ge_218": bool(counts["n_ge_218"] > 0),
           "any_N_hat_ge_254": bool(counts["n_ge_254"] > 0),
           "cpr_test_rejects": int(a_.sum()), "dop_test_rejects": int(b_.sum()),
           "cpr_test_rejects_fraction": float(a_.mean()),
           "dop_test_rejects_fraction": float(b_.mean()),
           "both_tests_reject": int((a_ & b_).sum()),
           "iut_selects": int((a_ & b_).sum()),
           "iut_selects_fraction": float((a_ & b_).mean()),
           "sinha_rule_selects": int(sinha.sum())}
    print(f"  pass {pass_id}: IUT selects {out['iut_selects']:,} of {out['cells_evaluated']:,} "
          f"(CPR test {out['cpr_test_rejects']:,}, DOP test {out['dop_test_rejects']:,}; "
          f"Sinha rule {out['sinha_rule_selects']:,})", flush=True)
    print(f"    N_hat max {out['local_N_hat']['max']:.1f}, p99 {out['local_N_hat']['p99']:.1f}; "
          f"counts >= 79.6 / 218 / 254: {list(counts.values())}; among the published rule's "
          f"cells {list(counts_sel.values())} (p99 {out['published_rule_cells']['local_N_hat_p99']}, "
          f"max {out['published_rule_cells']['local_N_hat_max']})", flush=True)
    if out["any_N_hat_ge_218"]:
        print(f"    CELLS WITH N_HAT >= 218 ON PASS {pass_id}: {counts['n_ge_218']}", flush=True)
    return out


def main() -> int:
    rng = np.random.default_rng(SEED)
    print("=" * 78)
    print("TASK 3 — a calibrated replacement rule")
    print("=" * 78)
    qtab = q05_table(rng)
    print(f"  q05 at DOP 0.13: N 14 -> {q05_at(14, qtab):.4f}, N 38 -> {q05_at(38, qtab):.4f}, "
          f"N 100 -> {q05_at(100, qtab):.4f}", flush=True)
    onset = iut_onset(qtab)
    print(f"  IUT onset on the q05 grid: between N = {onset['last_N_without_region']} and "
          f"{onset['first_N_with_region']}", flush=True)
    rows = simulate_cells(rng, qtab)
    summ = summarize(rows)
    for k, v in summ.items():
        o = v["oracle"]
        print(f"  {k}: IUT size {o['iut_size_percent']:.2f} %  power {max(o['iut_power_percent'].values()):.2f} %  "
              f"| plug-in W16 size {v['plugin_W16']['iut_size_percent']:.2f} %  CPR-test size "
              f"{v['plugin_W16']['cpr_test_size_percent']:.2f} % (oracle {o['cpr_test_size_percent']:.2f} %) "
              f"| W{w_complex()} (complex grid) CPR {v['plugin_Wcomplex']['cpr_test_size_percent']:.2f} % "
              f"IUT {v['plugin_Wcomplex']['iut_size_percent']:.3f} %")
    prod = {p: apply_to_product(p, qtab) for p in ("20200808", "20200305")}
    OUT.write_text(json.dumps({
        "schema": "lunar-ice/decision-rule/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/decision_rule.py",
        "seed": SEED, "alpha": ALPHA, "N_eval": list(N_EVAL),
        "test_cells_per_population": TEST_CELLS, "window_pool": POOL,
        "windows": {"960": "31 x 31 of independent cells",
                    "16": "31 x 31 at the product's 61.42 px per independent sample",
                    "complex": {"W": w_complex(),
                                "basis": ("961 / A, A the median correlation area of the Stokes "
                                          "CPR on the complex grid "
                                          "(complex_grid_correlation.json)"),
                                "seed": SEED_WCOMPLEX}},
        "iut_onset": onset,
        "dop_quantile_table": {"at_population_dop": 0.13, "arm": "A", "trials_per_N": Q_TRIALS,
                               "q05": {str(k): v for k, v in qtab.items()}},
        "arms": "as joint_power_curve.json (A speckle, B per-look texture 8, C correlated looks)",
        "summary": summ, "rows": rows, "product": prod,
        "run_info": run_info()}, indent=2, default=float), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
