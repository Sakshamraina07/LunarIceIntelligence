"""
n_sensitivity.py -- every headline of the paper as a function of the look
count N. (v21 work order, W1A, W1C, W1D; the np bound, the regional null and the
real-data override are W1B, W1E, W1F and live in n_sensitivity_np.py,
n_sensitivity_region.py and n_sensitivity_real.py)

    python backend/scripts/n_sensitivity.py [--trials 2000000]

Writes docs/n_sensitivity_core.json (draws: seed 20261021).

The look count N is not identified (label 21; spectrum 7.13 / 12.8; moment ENL
5.83 / 13.72; complex-block moment ENL 14.8 / 25.6; log-ratio 39.4, IQR
28.5-46.0, and 17.4 per cell; ceiling 69.7). This module computes what does not
need data:

A  ANALYTIC. The one-sided 95 % critical value of F(2N, 2N); the CPR edges of
   the DOP < 0.13 band (0.7699 and 1.2989, N-free); the smallest N at which the
   critical value is below 1.2989; the power of a CPR-only test at the band
   edge.
C  SIZE AND POWER of the published joint rule (sample DOP < 0.13 and sample
   CPR > 1) under the complex-Wishart speckle model with N looks (exact Bartlett
   sampling, real N): size = the largest selection rate at CPR 1.00 with
   population DOP 0, 0.05, 0.10, 0.13; power at CPR 1.1, 1.2, 1.25 at the
   minimum admissible DOP (gamma_c = 0, the only DOP a CPR != 1 population can
   have at zero coherence; DOP exactly 0 exists only at CPR 1) and midway
   from there to 0.13. Every rate carries its binomial Monte Carlo SE. The N at
   which the size first exceeds 5, 10 and 20 % is read from a dense scan.
D  REGIONAL TESTS. (i) The IUT's onset: for integer N the smallest at which
   (crit - 1)/(crit + 1) falls below q05(N), the 5 % quantile of the sample DOP
   at population DOP 0.13; the size of the IUT at that N. (ii) The pooled-looks
   requirement for 80 % regional power (region_design_curve.json) and the number
   of independent cells K = ceil(N_eff / N) it is in each N; confirmed at N = 14
   and 39.4 by summing K independent cells and applying the IUT.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.optimize import brentq
from scipy.stats import f as Fd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402
import region_design_curve as RDC  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "n_sensitivity_core.json"
SEED = 20261021
GRID = (5.0, 7.0, 10.0, 13.72, 14.5, 17.4, 21.0, 28.0, 34.0, 38.0, 39.4, 45.0, 55.0, 70.0, 75.9, 80.0,
        100.0, 150.0, 218.0)
EXTRA = (79.6166,)                       # the N at which crit95 = 1.2989 (a stated threshold)
EDGE = 1.13 / 0.87
DOP_T = 0.13
CPRS = (1.1, 1.2, 1.25)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def crit(n):
    return float(Fd.ppf(0.95, 2 * n, 2 * n))


def rate(x):
    x = np.asarray(x, bool)
    p = float(x.mean())
    return {"rate": p, "percent": 100 * p, "mc_se_percent": 100 * float(np.sqrt(p * (1 - p) / x.size)),
            "trials": int(x.size)}


def rule_rate(rng, n, cpr, dop, trials):
    r, m = RDC.stats(*RDC.bartlett(rng, float(n), trials, RDC.chol_sigma(cpr, dop)))
    return rate((m < DOP_T) & (r > 1.0))


def dmin(cpr):
    return abs(cpr - 1.0) / (cpr + 1.0)


def analytic(n):
    c = crit(n)
    return {"crit95": c, "crit95_edge_dop_0p13_cpr_low": (1 - DOP_T) / (1 + DOP_T),
            "cpr_edge_high": EDGE,
            "crit_below_band_edge": bool(c < EDGE),
            "cpr_only_power_at_band_edge_percent": 100 * float(Fd.sf(c / EDGE, 2 * n, 2 * n)),
            "noise_exceedance_of_1_at_true_cpr_0p7_percent": 100 * float(Fd.sf(1 / 0.7, 2 * n, 2 * n)),
            "iut_dop_edge_at_crit": (c - 1) / (c + 1)}


def size_power(rng, n, trials):
    size_pops = {}
    for d in (0.0, 0.05, 0.10, 0.13):
        size_pops[f"CPR 1.00 DOP {d:g}"] = rule_rate(rng, n, 1.0, d, trials)
    smax_key = max(size_pops, key=lambda k: size_pops[k]["rate"])
    out = {"size": {**size_pops[smax_key], "at": smax_key}, "size_populations": size_pops, "power": {}}
    for c in CPRS:
        lo = dmin(c)
        out["power"][f"CPR {c:g} DOP min"] = {**rule_rate(rng, n, c, lo, trials), "dop": lo}
        mid = 0.5 * (lo + DOP_T)
        out["power"][f"CPR {c:g} DOP mid"] = {**rule_rate(rng, n, c, mid, trials), "dop": mid}
    return out


def dense_size_scan(rng, trials):
    ns = np.concatenate([np.arange(3, 30, 1.0), np.arange(30, 120, 2.0)])
    vals = [rule_rate(rng, n, 1.0, 0.0, trials) for n in ns]
    return {"N": ns.tolist(), "size_percent": [v["percent"] for v in vals], "mc_se_percent": [v["mc_se_percent"] for v in vals],
            "population": "CPR 1.00 DOP 0", "trials_per_N": trials}


def first_exceed(ns, vals, ses, level):
    """(N at which the curve first exceeds `level` %, and the N range over which
    +-2 SE straddles it), by linear interpolation of the dense scan."""
    ns, vals, ses = map(np.asarray, (ns, vals, ses))

    def cross(v):
        i = int(np.argmax(v > level))
        if v[i] <= level or i == 0:
            return None
        t = (level - v[i - 1]) / (v[i] - v[i - 1])
        return float(ns[i - 1] + t * (ns[i] - ns[i - 1]))
    return {"level_percent": level, "N_first_exceeds": cross(vals), "N_range_2se": [cross(vals + 2 * ses), cross(vals - 2 * ses)]}


def q05_at(rng, n, draws):
    _, m = RDC.stats(*RDC.bartlett(rng, float(n), draws, RDC.chol_sigma(1.0, 0.13)))
    return float(np.quantile(m, 0.05))


def iut_onset(rng, draws):
    rows = []
    for n in list(range(196, 300, 4)):
        c = crit(n)
        rows.append({"N": n, "edge": (c - 1) / (c + 1), "q05": q05_at(rng, n, draws)})
    first = next((r["N"] for r in rows if r["edge"] < r["q05"]), None)
    # refine to the integer
    fine = []
    if first is not None:
        for n in range(first - 4, first + 1):
            c = crit(n)
            fine.append({"N": n, "edge": (c - 1) / (c + 1), "q05": q05_at(rng, n, 4 * draws)})
    onset = next((r["N"] for r in fine if r["edge"] < r["q05"]), None)
    return {"coarse": rows, "fine": fine, "first_N_with_rejection_region": onset,
            "last_N_without": (onset - 1) if onset else None, "q05_draws_fine": 4 * draws}


def iut_size_at(rng, n, trials=400_000):
    q = q05_at(rng, n, 2_000_000)
    c = crit(n)
    out = {}
    for lab, cpr, dop in (("CPR 1.00 DOP 0", 1.0, 0.0), ("CPR 1.00 DOP 0.13", 1.0, 0.13), ("CPR 1.2989 DOP 0.13", EDGE, 0.13),
                          ("CPR 1.00 DOP 0.065", 1.0, 0.065)):
        r, m = RDC.stats(*RDC.bartlett(rng, float(n), trials, RDC.chol_sigma(cpr, dop)))
        out[lab] = rate((r > c) & (m < q))
    worst = max(out.values(), key=lambda v: v["rate"])
    return {"N": n, "q05": q, "crit95": c, "by_null": out, "size_percent": worst["percent"],
            "size_mc_se_percent": worst["mc_se_percent"]}


def pooled_confirmation(rng, n, cpr, dop, k, trials):
    """K independent cells of N looks pooled; the IUT at N_eff = K N."""
    ch = RDC.chol_sigma(cpr, dop)
    s11 = np.zeros(trials); s22 = np.zeros(trials); s12 = np.zeros(trials, dtype=complex)
    for _ in range(k):
        a, b, c = RDC.bartlett(rng, float(n), trials, ch)
        s11 += a; s22 += b; s12 += c
    r, m = RDC.stats(s11 / k, s22 / k, s12 / k)
    neff = k * n
    qn = q05_at(rng, neff, 2_000_000)
    hit = (r > crit(neff)) & (m < qn)
    return {"K": k, "N": n, "N_eff": neff, "cpr": cpr, "dop": dop, "q05_at_N_eff": qn, **rate(hit)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=2_000_000)
    args = ap.parse_args()
    t0 = time.time()
    ss = np.random.SeedSequence(SEED)
    r_sp, r_scan, r_iut, r_conf = [np.random.default_rng(s) for s in ss.spawn(4)]
    print("=" * 78); print("W1 A, C, D — the results as functions of N"); print("=" * 78, flush=True)
    rows = {}
    for n in sorted(set(GRID + EXTRA)):
        row = {"N": n, "analytic": analytic(n), "rule": size_power(r_sp, n, args.trials)}
        rows[f"{n:g}"] = row
        s = row["rule"]["size"]
        print(f"  N {n:>7g}: crit {row['analytic']['crit95']:.4f}; size {s['percent']:.3f} +/- {s['mc_se_percent']:.3f} %; "
              f"power CPR 1.1 min {row['rule']['power']['CPR 1.1 DOP min']['percent']:.2f} %", flush=True)
    n_edge = float(brentq(lambda n: crit(n) - EDGE, 20, 400, xtol=1e-9))
    scan = dense_size_scan(r_scan, 1_000_000)
    thresholds = {f"{lv}": first_exceed(scan["N"], scan["size_percent"], scan["mc_se_percent"], lv) for lv in (5.0, 10.0, 20.0)}
    for lv, v in thresholds.items():
        print(f"  size first exceeds {lv} % at N = {v['N_first_exceeds']:.2f} (2 SE range {v['N_range_2se']})", flush=True)
    onset = iut_onset(r_iut, 4_000_000)
    print(f"  IUT: first N with a rejection region {onset['first_N_with_rejection_region']}", flush=True)
    iut_at = {}
    for n in (onset["last_N_without"], onset["first_N_with_rejection_region"], 254, 300):
        if n:
            iut_at[str(n)] = iut_size_at(r_iut, int(n))
    rdc = json.loads((BASE_DIR / "docs" / "region_design_curve.json").read_text(encoding="utf-8"))
    req = {}
    for lab, blk in rdc["design"].items():
        neff = blk["iut"]["80pct"]["N"]
        req[lab] = {"iut_80pct_N_eff": neff, "np_bound_80pct_N_eff": blk["np_bound"]["80pct"]["N"],
                    "K_cells_by_N": {f"{n:g}": int(math.ceil(neff / n)) for n in sorted(set(GRID + EXTRA))}}
    conf = [pooled_confirmation(r_conf, 14.0, 1.1, dmin(1.1), int(math.ceil(1396 / 14)), 100_000),
            pooled_confirmation(r_conf, 39.4, 1.1, dmin(1.1), int(math.ceil(1396 / 39.4)), 100_000)]
    for c in conf:
        print(f"  pooled K={c['K']} N={c['N']}: N_eff {c['N_eff']:.1f}, power {c['percent']:.2f} +/- {c['mc_se_percent']:.2f} %", flush=True)
    OUT.write_text(json.dumps({
        "schema": "lunar-ice/n-sensitivity-core/1", "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/n_sensitivity.py", "seed": SEED, "trials_per_population": args.trials,
        "grid": list(sorted(set(GRID + EXTRA))),
        "N_edge_crit_equals_1p2989": n_edge, "band_cpr_edges": [(1 - DOP_T) / (1 + DOP_T), EDGE],
        "rows": rows, "size_scan": scan, "size_first_exceeds": thresholds,
        "iut_onset": onset, "iut_size_at": iut_at, "regional_requirement": req,
        "pooled_confirmation": conf,
        "run_info": {**run_info(), "wall_s": round(time.time() - t0, 1)}}, indent=2, default=float), encoding="utf-8")
    print(f"  wrote {OUT.name} ({time.time() - t0:.0f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
