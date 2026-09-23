"""
region_mean_null.py -- the null distribution of the statistic Sinha et al.
actually report. (v18a referee reports, N4)

    python backend/scripts/region_mean_null.py [--workers 6]

Sinha et al. report, per region, the MEAN CPR and MEAN DOP of the pixels with
CPR >= 1 (mean DOP 0.10-0.13 in F2, F3, H3 and S1). Here that pair -- over the
cells of a region whose sample CPR is >= 1, the mean sample CPR and the mean
sample DOP -- is simulated under populations that carry no ice signature:

  * CPR 1.00 at DOP 0 (the unpolarized null boundary);
  * CPR 0.7 at DOP 0.176 (its minimum) and 0.20;
  * the median population of the sunlit discs (crater_level_real.json);

at N in {5, 13.72, 39.4, 80, 150}, for regions of 260 and 3647 cells (the
delivered grid's returned F2 pixels, and F2's full complex-product disc).

Two versions:
  * INDEPENDENT: every cell an exact complex-Wishart draw with N looks
    (Bartlett decomposition, real N) -- the mean's law at the stated N;
  * CORRELATED: L equal-weight looks of exactly stationary AR(1) complex
    fields at the complex product's SC / OC lag-one correlations, 5 x 5
    boxcar, on an elliptical region of the complex grid with the disc's
    aspect (10.0 m azimuth x 23.1 m ground-range cells) scaled to hold the
    stated number of cells; L chosen so the single-cell log-ratio N is nearest
    the stated N, and the achieved N reported.

Reported per configuration: the fraction of regions with any cell at CPR >= 1;
over those, the 5-95 % range of each mean; P(mean DOP < 0.13) and
P(mean DOP < 0.10), with Monte Carlo SEs. Separately, the N at which the
conditional mean DOP of an unpolarized population, E[m_hat | R >= 1], falls to
0.13 and to 0.10 (Bartlett, 10^6 draws per N on a log grid, interpolated in
ln N), beside the unconditional crossings 75.09 and 127.07 of
dop_sampling_bias.json.
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
from scipy.ndimage import uniform_filter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402
import region_design_curve as RDC  # noqa: E402
import f2_maximum as F2M  # noqa: E402
import enl_logratio as L  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "region_mean_null.json"
SEED = 20261011
N_GRID = (5.0, 13.72, 39.4, 80.0, 150.0)
SIZES = (260, 3647)
T_IND = {260: 20_000, 3647: 4_000}
T_COR = {260: 2_000, 3647: 1_000}
CELL_AZ_M, CELL_RG_M = 10.0, 23.1
DOP_T = 0.13


def populations():
    clr = json.loads((BASE_DIR / "docs" / "crater_level_real.json").read_text(encoding="utf-8"))
    so = clr["summary"]["outside"]
    c, g = so["median_cpr_over_discs"], so["median_gamma_c_over_discs"]
    q = (c - 1) / (c + 1)
    d = float(np.sqrt(q * q + g * g * (1 - q * q)))
    return [("CPR 1.00 DOP 0", 1.0, 0.0), ("CPR 0.7 DOP 0.176", 0.7, 0.3 / 1.7),
            ("CPR 0.7 DOP 0.20", 0.7, 0.20), (f"sunlit median (CPR {c:.3f}, DOP {d:.3f})", c, d)]


def ellipse(n):
    """An elliptical cell mask of the disc's aspect holding exactly n cells."""
    ar = CELL_RG_M / CELL_AZ_M               # rows per column of equal ground extent
    for s in np.linspace(3, 80, 3000):
        a, b = s * ar, s                      # semi-axes in rows, columns
        R, C = int(np.ceil(a)) + 1, int(np.ceil(b)) + 1
        yy, xx = np.mgrid[-R:R + 1, -C:C + 1]
        m = (yy / a) ** 2 + (xx / b) ** 2 <= 1.0
        if m.sum() >= n:
            d = (yy / a) ** 2 + (xx / b) ** 2
            idx = np.argsort(d.ravel(), kind="stable")[:n]
            out = np.zeros(m.size, dtype=bool); out[idx] = True
            return out.reshape(m.shape)
    raise ValueError(n)


def summarize(means_r, means_m, any_ge1, trials):
    ok = np.isfinite(means_m)
    k = int(ok.sum())
    out = {"trials": trials, "fraction_regions_with_cpr_ge1_cell": float(np.mean(any_ge1))}
    if k:
        mr, mm = means_r[ok], means_m[ok]
        p13 = float((mm < DOP_T).mean()); p10 = float((mm < 0.10).mean())
        out.update({"mean_cpr_5_95": [float(np.percentile(mr, 5)), float(np.percentile(mr, 95))],
                    "mean_dop_5_95": [float(np.percentile(mm, 5)), float(np.percentile(mm, 95))],
                    "mean_cpr_median": float(np.median(mr)), "mean_dop_median": float(np.median(mm)),
                    "p_mean_dop_lt_0p13": p13, "p_mean_dop_lt_0p13_se": float(np.sqrt(p13 * (1 - p13) / k)),
                    "p_mean_dop_lt_0p10": p10, "p_mean_dop_lt_0p10_se": float(np.sqrt(p10 * (1 - p10) / k)),
                    "regions_evaluated": k})
    return out


def independent(args):
    seed, cpr, dop, n, size, trials = args
    rng = np.random.default_rng(seed)
    ch = RDC.chol_sigma(cpr, dop)
    mr = np.full(trials, np.nan); mm = np.full(trials, np.nan); anyc = np.zeros(trials, bool)
    step = max(1, 2_000_000 // size)
    for i in range(0, trials, step):
        t = min(step, trials - i)
        r, m = RDC.stats(*RDC.bartlett(rng, n, t * size, ch))
        r, m = r.reshape(t, size), m.reshape(t, size)
        sel = r >= 1.0
        cnt = sel.sum(axis=1)
        anyc[i:i + t] = cnt > 0
        with np.errstate(invalid="ignore", divide="ignore"):
            mr[i:i + t] = np.where(cnt > 0, (r * sel).sum(axis=1) / cnt, np.nan)
            mm[i:i + t] = np.where(cnt > 0, (m * sel).sum(axis=1) / cnt, np.nan)
    return summarize(mr, mm, anyc, trials)


def correlated(args):
    seed, cpr, dop, n_target, size, trials, rsc, roc = args
    rng = np.random.default_rng(seed)
    mask = ellipse(size)
    H, W = mask.shape
    M = 4
    g = RDC.NPB.gamma_c(dop, cpr)
    a, b = cpr / (1 + cpr), 1 / (1 + cpr)

    def field(Lk, batch, aa, bb, gg):
        sc = np.zeros((batch, H + 2 * M, W + 2 * M)); oc = np.zeros_like(sc)
        x = np.zeros_like(sc, dtype=complex)
        for _ in range(Lk):
            wo = F2M.ar1_stationary(rng, (H + 2 * M, W + 2 * M), *roc, batch)
            ws = F2M.ar1_stationary(rng, (H + 2 * M, W + 2 * M), *rsc, batch)
            zo = np.sqrt(bb) * wo
            zs = np.sqrt(aa) * (gg * wo + np.sqrt(1 - gg * gg) * ws)
            sc += np.abs(zs) ** 2; oc += np.abs(zo) ** 2; x += zs * np.conj(zo)
        f = lambda v: uniform_filter(v, size=(1, 5, 5), mode="reflect")  # noqa: E731
        return f(sc / Lk), f(oc / Lk), f(x.real / Lk) + 1j * f(x.imag / Lk)

    # looks per channel: single-cell log-ratio N nearest the target (calibrated at the null)
    cal, Lk = {}, 1
    while True:
        bs, bo, _ = field(Lk, 4, 0.5, 0.5, 0.0)
        cal[Lk] = float(L.n_from_var(np.var(np.log(bs / bo)[:, M:-M, M:-M], ddof=1)))
        if cal[Lk] >= n_target or Lk >= 80:
            break
        Lk += 1 if Lk < 10 else 3
    Lc = min(cal, key=lambda k: abs(cal[k] - n_target))
    mr = np.full(trials, np.nan); mm = np.full(trials, np.nan); anyc = np.zeros(trials, bool)
    batch = 20
    for i in range(0, trials, batch):
        t = min(batch, trials - i)
        bs, bo, bx = field(Lc, t, a, b, g)
        r = (bs / bo)[:, M:-M, M:-M][:, mask]
        m = (np.sqrt((bs - bo) ** 2 + 4 * np.abs(bx) ** 2) / (bs + bo))[:, M:-M, M:-M][:, mask]
        sel = r >= 1.0
        cnt = sel.sum(axis=1)
        anyc[i:i + t] = cnt > 0
        with np.errstate(invalid="ignore", divide="ignore"):
            mr[i:i + t] = np.where(cnt > 0, (r * sel).sum(axis=1) / cnt, np.nan)
            mm[i:i + t] = np.where(cnt > 0, (m * sel).sum(axis=1) / cnt, np.nan)
    out = summarize(mr, mm, anyc, trials)
    out.update({"looks_per_channel": Lc, "achieved_log_ratio_N": cal[Lc], "region_mask_cells": int(mask.sum())})
    return out


def conditional_crossings(rng) -> dict:
    ns = np.geomspace(5, 600, 40)
    ch = RDC.chol_sigma(1.0, 0.0)
    cond, unc = [], []
    for n in ns:
        r, m = RDC.stats(*RDC.bartlett(rng, float(n), 1_000_000, ch))
        cond.append(float(m[r >= 1.0].mean())); unc.append(float(m.mean()))

    def cross(vals, level):
        v = np.array(vals)
        i = int(np.argmax(v < level))
        if v[i] >= level or i == 0:
            return None
        t = (level - v[i - 1]) / (v[i] - v[i - 1])
        return float(np.exp(np.log(ns[i - 1]) + t * (np.log(ns[i]) - np.log(ns[i - 1]))))
    dsb = json.loads((BASE_DIR / "docs" / "dop_sampling_bias.json").read_text(encoding="utf-8"))
    mu = dsb["mean_sample_dop_unpolarized"]
    return {"grid_N": ns.tolist(), "conditional_mean_dop": cond, "unconditional_mean_dop": unc,
            "N_conditional_0p13": cross(cond, 0.13), "N_conditional_0p10": cross(cond, 0.10),
            "N_unconditional_0p13_simulated": cross(unc, 0.13), "N_unconditional_0p10_simulated": cross(unc, 0.10),
            "N_unconditional_0p13_closed_form": mu["N_where_mean_is_0p13"],
            "N_unconditional_0p10_closed_form": mu["N_where_mean_is_0p10"],
            "draws_per_N": 1_000_000}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    t0 = time.time()
    pops = populations()
    gc = json.loads((BASE_DIR / "docs" / "complex_grid_correlation.json").read_text(encoding="utf-8"))["lag_correlation_before_boxcar"]
    rsc = (float(np.sqrt(gc["SC"]["azimuth_lines"][0])), float(np.sqrt(gc["SC"]["range_samples"][0])))
    roc = (float(np.sqrt(gc["OC"]["azimuth_lines"][0])), float(np.sqrt(gc["OC"]["range_samples"][0])))
    ss = np.random.SeedSequence(SEED)
    s_cross, s_ind, s_cor = ss.spawn(3)
    keys = [(lab, c, d, n, sz) for lab, c, d in pops for n in N_GRID for sz in SIZES]
    ind_seeds, cor_seeds = s_ind.spawn(len(keys)), s_cor.spawn(len(keys))
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        ind = list(ex.map(independent, [(ind_seeds[i], c, d, n, sz, T_IND[sz]) for i, (lab, c, d, n, sz) in enumerate(keys)]))
        cor = list(ex.map(correlated, [(cor_seeds[i], c, d, n, sz, T_COR[sz], rsc, roc)
                                       for i, (lab, c, d, n, sz) in enumerate(keys)]))
    res = {}
    for (lab, c, d, n, sz), a, b in zip(keys, ind, cor):
        res.setdefault(lab, {}).setdefault(f"N{n:g}", {})[f"cells{sz}"] = {"independent": a, "correlated": b}
        print(f"  {lab:34s} N {n:>6g} {sz:>5} cells: P(mean DOP<0.13) ind "
              f"{a.get('p_mean_dop_lt_0p13', float('nan')):.3f} cor {b.get('p_mean_dop_lt_0p13', float('nan')):.3f}; "
              f"mean DOP 5-95 ind {a.get('mean_dop_5_95')}", flush=True)
    crossings = conditional_crossings(np.random.default_rng(s_cross))
    print(f"  conditional mean DOP of an unpolarized population falls to 0.13 at N = "
          f"{crossings['N_conditional_0p13']}, to 0.10 at {crossings['N_conditional_0p10']}", flush=True)
    lit = json.loads((BASE_DIR / "docs" / "literature_screen.json").read_text(encoding="utf-8"))
    sinha = next(r for r in lit["records"] if r.get("id") == 4)["aggregation_record"]
    OUT.write_text(json.dumps({
        "schema": "lunar-ice/region-mean-null/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/region_mean_null.py", "seed": SEED,
        "statistic": ("over the cells of a region with sample CPR >= 1: the mean sample CPR and the mean "
                      "sample DOP (the per-region pair Sinha et al. report)"),
        "populations": [{"label": lab, "cpr": c, "dop": d} for lab, c, d in pops],
        "N_grid": list(N_GRID), "region_cells": list(SIZES),
        "trials": {"independent": {str(k): v for k, v in T_IND.items()},
                   "correlated": {str(k): v for k, v in T_COR.items()}},
        "correlated_model": {"lags_intensity_SC": [gc["SC"]["azimuth_lines"][0], gc["SC"]["range_samples"][0]],
                             "lags_intensity_OC": [gc["OC"]["azimuth_lines"][0], gc["OC"]["range_samples"][0]],
                             "region": ("ellipse on the complex grid, cell 10.0 m azimuth x 23.1 m ground range, "
                                        "scaled to the stated cell count"), "boxcar": 5},
        "results": res, "conditional_mean_dop_unpolarized": crossings,
        "sinha_reported": {"in_repository": {"mean_dop_range": sinha["average_dop_range"],
                                             "craters": sinha["craters"], "quote": sinha["quote_average_dop"],
                                             "aggregation": sinha["aggregation"]},
                           "not_in_repository": ("the per-region mean CPR values and the per-region mean DOP of "
                                                 "each crater; only the 0.10-0.13 range over the four craters is "
                                                 "recorded, so the comparison is against that range")},
        "run_info": {**run_info(), "wall_s": round(time.time() - t0, 1)}}, indent=2, default=float), encoding="utf-8")
    print(f"  wrote {OUT.relative_to(BASE_DIR)} ({time.time() - t0:.0f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
