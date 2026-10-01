"""
n_sensitivity_region.py -- the region-mean null over the N grid. (v21 work
order, W1E)

    python backend/scripts/n_sensitivity_region.py [--workers 6]

region_mean_null.py simulated Sinha et al.'s statistic (mean DOP over the
pixels with CPR >= 1) at N in {5, 13.72, 39.4, 80, 150}. This runs it over the
full sensitivity grid for the populations CPR 0.7 / DOP 0.176 (the ice-free
operating point), CPR 0.7 / DOP 0.20 and CPR 1.0 / DOP 0 (the unpolarized
population), for regions of 260 and 3647 cells, independent and correlated
cells, using region_mean_null's own functions.

The correlated model has integer looks L; a grid N is mapped to the L whose
single-cell log-ratio N is nearest, and the achieved N is reported, as the
existing artifact does (two grid points can share an L). Results already in
docs/region_mean_null.json are reused where the (population, region size,
L) agree, and the source key is recorded.

Per configuration: the conditional P(mean DOP < 0.13 | the region has a cell
with CPR >= 1), the containing fraction P(region has such a cell), and the
unconditional P(mean DOP < 0.13 and such a cell) = conditional x containing,
with the binomial Monte Carlo SE of the unconditional rate over all trials.
Writes docs/n_sensitivity_region.json (seed 20261031).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402
import region_mean_null as RM  # noqa: E402
import region_design_curve as RDC  # noqa: E402
import f2_maximum as F2M  # noqa: E402
import enl_logratio as L  # noqa: E402
from scipy.ndimage import uniform_filter  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "n_sensitivity_region.json"
SEED = 20261031
GRID = (5.0, 7.0, 10.0, 13.72, 14.5, 17.4, 21.0, 28.0, 34.0, 38.0, 39.4, 45.0, 55.0, 70.0, 75.9, 80.0,
        100.0, 150.0, 218.0)
POPS = (("CPR 1.00 DOP 0", 1.0, 0.0), ("CPR 0.7 DOP 0.176", 0.7, 0.3 / 1.7), ("CPR 0.7 DOP 0.20", 0.7, 0.20))
T_IND = {260: 20_000, 3647: 4_000}
T_COR = {260: 2_000, 3647: 1_000}
LMAX = 120

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def calibrate(size, rsc, roc, seed):
    """Single-cell log-ratio N for L = 1, 2, ... (the null, CPR 1 at zero coherence).

    region_mean_null.correlated estimates it on four realizations of the region's own bounding box
    (about 300 correlated cells each), which leaves the achieved N uncertain by 10-15 % (the
    calibration below reads L8 below L7 on the 260-cell box). Here it is measured once on four
    200 x 200 realizations (about 150 000 cells, a few per cent), the same for both region sizes;
    the artifact's own achieved N is kept beside it."""
    rng = np.random.default_rng(seed)
    H = W = 200
    M = 4
    cal = {}
    Lk = 1
    while Lk <= LMAX:
        sc = np.zeros((4, H + 2 * M, W + 2 * M)); oc = np.zeros_like(sc)
        for _ in range(Lk):
            wo = F2M.ar1_stationary(rng, (H + 2 * M, W + 2 * M), *roc, 4)
            ws = F2M.ar1_stationary(rng, (H + 2 * M, W + 2 * M), *rsc, 4)
            sc += np.abs(np.sqrt(0.5) * ws) ** 2; oc += np.abs(np.sqrt(0.5) * wo) ** 2
        f = lambda v: uniform_filter(v, size=(1, 5, 5), mode="reflect")  # noqa: E731
        bs, bo = f(sc / Lk), f(oc / Lk)
        cal[Lk] = float(L.n_from_var(np.var(np.log(bs / bo)[:, M:-M, M:-M], ddof=1)))
        Lk += 1 if Lk < 10 else 3
    return cal


def correlated_L(args):
    """region_mean_null.correlated with the looks given (no calibration)."""
    seed, cpr, dop, Lc, size, trials, rsc, roc = args
    rng = np.random.default_rng(seed)
    mask = RM.ellipse(size)
    H, W = mask.shape
    M = 4
    g = RDC.NPB.gamma_c(dop, cpr)
    a, b = cpr / (1 + cpr), 1 / (1 + cpr)
    mr = np.full(trials, np.nan); mm = np.full(trials, np.nan); anyc = np.zeros(trials, bool)
    batch = 20
    for i in range(0, trials, batch):
        t = min(batch, trials - i)
        sc = np.zeros((t, H + 2 * M, W + 2 * M)); oc = np.zeros_like(sc); x = np.zeros_like(sc, dtype=complex)
        for _ in range(Lc):
            wo = F2M.ar1_stationary(rng, (H + 2 * M, W + 2 * M), *roc, t)
            ws = F2M.ar1_stationary(rng, (H + 2 * M, W + 2 * M), *rsc, t)
            zo = np.sqrt(b) * wo
            zs = np.sqrt(a) * (g * wo + np.sqrt(1 - g * g) * ws)
            sc += np.abs(zs) ** 2; oc += np.abs(zo) ** 2; x += zs * np.conj(zo)
        f = lambda v: uniform_filter(v, size=(1, 5, 5), mode="reflect")  # noqa: E731
        bs, bo, bx = f(sc / Lc), f(oc / Lc), f(x.real / Lc) + 1j * f(x.imag / Lc)
        r = (bs / bo)[:, M:-M, M:-M][:, mask]
        m = (np.sqrt((bs - bo) ** 2 + 4 * np.abs(bx) ** 2) / (bs + bo))[:, M:-M, M:-M][:, mask]
        sel = r >= 1.0
        cnt = sel.sum(axis=1)
        anyc[i:i + t] = cnt > 0
        with np.errstate(invalid="ignore", divide="ignore"):
            mr[i:i + t] = np.where(cnt > 0, (r * sel).sum(axis=1) / cnt, np.nan)
            mm[i:i + t] = np.where(cnt > 0, (m * sel).sum(axis=1) / cnt, np.nan)
    out = RM.summarize(mr, mm, anyc, trials)
    out["looks_per_channel"] = Lc
    return out


def with_unconditional(x):
    """Add the unconditional rate and its binomial SE to a summarize() dict."""
    if "p_mean_dop_lt_0p13" not in x:
        x.update({"conditional_p": 0.0, "containing_fraction": x["fraction_regions_with_cpr_ge1_cell"],
                  "unconditional_p": 0.0, "unconditional_se": 0.0})
        return x
    frac, p = x["fraction_regions_with_cpr_ge1_cell"], x["p_mean_dop_lt_0p13"]
    # regions_evaluated / trials is the containing fraction; the conditional p is over regions_evaluated
    u = p * x["regions_evaluated"] / x["trials"]
    x.update({"conditional_p": p, "containing_fraction": frac, "unconditional_p": u,
              "unconditional_se": float(np.sqrt(u * (1 - u) / x["trials"]))})
    return x


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    t0 = time.time()
    old = json.loads(RM.OUT.read_text(encoding="utf-8"))
    gc = json.loads((BASE_DIR / "docs" / "complex_grid_correlation.json").read_text(encoding="utf-8"))["lag_correlation_before_boxcar"]
    rsc = (float(np.sqrt(gc["SC"]["azimuth_lines"][0])), float(np.sqrt(gc["SC"]["range_samples"][0])))
    roc = (float(np.sqrt(gc["OC"]["azimuth_lines"][0])), float(np.sqrt(gc["OC"]["range_samples"][0])))
    ss = np.random.SeedSequence(SEED)
    s_cal, s_ind, s_cor = ss.spawn(3)
    print("=" * 78); print("W1E — the region-mean null over the N grid"); print("=" * 78, flush=True)
    cal_big = calibrate(None, rsc, roc, s_cal)
    cals = {sz: cal_big for sz in RM.SIZES}
    print("  calibration (200 x 200, 4 realizations): " + ", ".join(f"L{l}->{n:.1f}" for l, n in list(cal_big.items())[:14]), flush=True)
    lmap = {}
    for sz in RM.SIZES:
        for n in GRID:
            Lc = min(cals[sz], key=lambda l: abs(cals[sz][l] - n))
            lmap[(sz, n)] = Lc
    # independent: every (population, grid N, size)
    ind_keys = [(lab, c, d, n, sz) for lab, c, d in POPS for n in GRID for sz in RM.SIZES]
    ind_seeds = s_ind.spawn(len(ind_keys))
    # correlated: reuse old results where (population, size, L) agree; compute the rest, once per (pop, size, L)
    old_by_L = {}
    for lab, byN in old["results"].items():
        for nk, bysz in byN.items():
            for szk, x in bysz.items():
                c = x["correlated"]
                if "looks_per_channel" in c:
                    old_by_L[(lab, int(szk.replace("cells", "")), c["looks_per_channel"])] = (f"region_mean_null.json::results.{lab}.{nk}.{szk}.correlated", c)
    need = {}
    for lab, c, d in POPS:
        for sz in RM.SIZES:
            for n in GRID:
                Lc = lmap[(sz, n)]
                if (lab, sz, Lc) not in old_by_L:
                    need.setdefault((lab, c, d, sz, Lc), None)
    cor_keys = list(need)
    cor_seeds = s_cor.spawn(len(cor_keys))
    print(f"  {len(ind_keys)} independent runs; {len(cor_keys)} correlated runs to compute, rest reused", flush=True)
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        ind = list(ex.map(RM.independent, [(ind_seeds[i], c, d, n, sz, T_IND[sz]) for i, (lab, c, d, n, sz) in enumerate(ind_keys)]))
        cor = list(ex.map(correlated_L, [(cor_seeds[i], c, d, Lc, sz, T_COR[sz], rsc, roc)
                                         for i, (lab, c, d, sz, Lc) in enumerate(cor_keys)]))
    new_by_L = {(lab, sz, Lc): ("computed here", r) for (lab, c, d, sz, Lc), r in zip(cor_keys, cor)}
    res = {}
    for (lab, c, d, n, sz), a in zip(ind_keys, ind):
        Lc = lmap[(sz, n)]
        src, b = old_by_L.get((lab, sz, Lc)) or new_by_L[(lab, sz, Lc)]
        b = with_unconditional(dict(b))
        if "achieved_log_ratio_N" in b:
            b["achieved_log_ratio_N_in_region_mean_null_json"] = b["achieved_log_ratio_N"]
        b["achieved_log_ratio_N"] = cals[sz][Lc]
        b["achieved_log_ratio_N_calibration_here"] = cals[sz][Lc]
        b["source"] = src
        a = with_unconditional(dict(a))
        res.setdefault(lab, {}).setdefault(f"N{n:g}", {})[f"cells{sz}"] = {"independent": a, "correlated": b}
    # crossings and maxima of the unconditional correlated rate vs the achieved N (per population, size)
    summary = {}
    for lab, c, d in POPS:
        for sz in RM.SIZES:
            pts = []
            for n in GRID:
                b = res[lab][f"N{n:g}"][f"cells{sz}"]["correlated"]
                pts.append((b["achieved_log_ratio_N"], b["unconditional_p"], b["unconditional_se"], n))
            pts = sorted(set(pts))
            xs = np.array([p[0] for p in pts]); ys = np.array([p[1] for p in pts])

            def cross(level):
                for i in range(1, len(xs)):
                    if (ys[i - 1] - level) * (ys[i] - level) < 0:
                        t = (level - ys[i - 1]) / (ys[i] - ys[i - 1])
                        return float(xs[i - 1] + t * (xs[i] - xs[i - 1]))
                return None
            j = int(np.argmax(ys))
            summary[f"{lab} / {sz} cells / correlated"] = {
                "max_unconditional_p": float(ys[j]), "max_unconditional_se": float(pts[j][2]),
                "at_achieved_N": float(xs[j]), "at_grid_N": pts[j][3],
                "first_crosses_5pct_at_achieved_N": cross(0.05), "first_crosses_50pct_at_achieved_N": cross(0.50),
                "rises_with_N_up_to_achieved_N": float(xs[j]), "monotone_rise_over_grid": bool(np.all(np.diff(ys) >= -2 * max(p[2] for p in pts)))}
    OUT.write_text(json.dumps({
        "schema": "lunar-ice/n-sensitivity-region/1", "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/n_sensitivity_region.py", "seed": SEED,
        "statistic": RM.__doc__.split("\n")[2].strip() if False else
        "mean sample DOP over the cells of a region with sample CPR >= 1 (the per-region statistic Sinha et al. report)",
        "populations": [{"label": lab, "cpr": c, "dop": d} for lab, c, d in POPS],
        "N_grid": list(GRID), "region_cells": list(RM.SIZES), "looks_map": {f"{sz}/{n:g}": v for (sz, n), v in lmap.items()},
        "calibration": {str(sz): {str(k): v for k, v in cals[sz].items()} for sz in RM.SIZES},
        "trials": {"independent": {str(k): v for k, v in T_IND.items()}, "correlated": {str(k): v for k, v in T_COR.items()}},
        "results": res, "summary": summary,
        "run_info": {**run_info(), "wall_s": round(time.time() - t0, 1)}}, indent=2, default=float), encoding="utf-8")
    for k, v in summary.items():
        print(f"  {k}: max {100 * v['max_unconditional_p']:.1f} +/- {100 * v['max_unconditional_se']:.1f} % at achieved N {v['at_achieved_N']:.1f}; "
              f"5 % at {v['first_crosses_5pct_at_achieved_N']}, 50 % at {v['first_crosses_50pct_at_achieved_N']}", flush=True)
    print(f"  wrote {OUT.name} ({time.time() - t0:.0f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
