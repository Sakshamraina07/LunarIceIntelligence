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


def simulate_cells(rng, qtab) -> dict:
    pops = D.curve_populations()
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
            for variant in ["oracle"] + [f"plugin_W{w}" for w in WINDOWS]:
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
    out = {"pass": pass_id, "cells_evaluated": int(valid.sum()),
           "local_N_hat": L.describe(n_),
           "cpr_test_rejects": int(a_.sum()), "dop_test_rejects": int(b_.sum()),
           "iut_selects": int((a_ & b_).sum()),
           "iut_selects_fraction": float((a_ & b_).mean()),
           "sinha_rule_selects": int(sinha.sum())}
    print(f"  pass {pass_id}: IUT selects {out['iut_selects']:,} of {out['cells_evaluated']:,} "
          f"(CPR test {out['cpr_test_rejects']:,}, DOP test {out['dop_test_rejects']:,}; "
          f"Sinha rule {out['sinha_rule_selects']:,})", flush=True)
    return out


def main() -> int:
    rng = np.random.default_rng(SEED)
    print("=" * 78)
    print("TASK 3 — a calibrated replacement rule")
    print("=" * 78)
    qtab = q05_table(rng)
    print(f"  q05 at DOP 0.13: N 14 -> {q05_at(14, qtab):.4f}, N 38 -> {q05_at(38, qtab):.4f}, "
          f"N 100 -> {q05_at(100, qtab):.4f}", flush=True)
    rows = simulate_cells(rng, qtab)
    summ = summarize(rows)
    for k, v in summ.items():
        o = v["oracle"]
        print(f"  {k}: IUT size {o['iut_size_percent']:.2f} %  power {max(o['iut_power_percent'].values()):.2f} %  "
              f"| plug-in W16 size {v['plugin_W16']['iut_size_percent']:.2f} %  CPR-test size "
              f"{v['plugin_W16']['cpr_test_size_percent']:.2f} % (oracle {o['cpr_test_size_percent']:.2f} %)")
    prod = {p: apply_to_product(p, qtab) for p in ("20200808", "20200305")}
    OUT.write_text(json.dumps({
        "schema": "lunar-ice/decision-rule/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/decision_rule.py",
        "seed": SEED, "alpha": ALPHA, "N_eval": list(N_EVAL),
        "test_cells_per_population": TEST_CELLS, "window_pool": POOL,
        "windows": {"960": "31 x 31 of independent cells",
                    "16": "31 x 31 at the product's 61.42 px per independent sample"},
        "dop_quantile_table": {"at_population_dop": 0.13, "arm": "A", "trials_per_N": Q_TRIALS,
                               "q05": {str(k): v for k, v in qtab.items()}},
        "arms": "as joint_power_curve.json (A speckle, B per-look texture 8, C correlated looks)",
        "summary": summ, "rows": rows, "product": prod,
        "run_info": run_info()}, indent=2, default=float), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
