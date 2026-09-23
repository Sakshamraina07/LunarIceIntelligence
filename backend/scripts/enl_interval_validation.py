"""
enl_interval_validation.py -- does any interval on the ENL cover it? (review M8)

    python backend/scripts/enl_interval_validation.py [--workers 4]

WHY
---
The manuscript labels every ENL range "precision, not confidence", because on
the benchmark's synthetic correlated speckle the nominally 95 % row-block
bootstrap covers the true ENL 12-26 % of the time. The reviewer asks for an
interval procedure WITH demonstrated coverage, or the measurement that none of
the candidates has it. Two are tried here, on the benchmark's own scenes
(enl_benchmark.py's speckle_field: 1024 x 512, the product's intensity lag-one
correlations, N independent looks, optional K texture), at the production
estimator (mode of per-patch mean^2/var, measure_enl.py):

  2-D BLOCK BOOTSTRAP. The patch grid is tiled into non-overlapping blocks of
  64 x 64 px -- at least three intensity correlation lengths in BOTH axes
  (lengths -1/ln(rho_1): 5.7 px azimuth, 1.8 px range, from the product's
  lag-one 0.838 / 0.576) -- and whole blocks are resampled. Reported as the
  percentile interval and as the basic (bias-reflected) interval.

  PARAMETRIC, under the fitted correlated-speckle model. The estimator's
  sampling distribution is simulated at each N of a grid (texture-free, the
  product's lags), and the interval is its Neyman inversion: every N whose
  central 95 % (90 %) band contains the observed estimate. The basic parametric
  bootstrap at the observed estimate is reported beside it. The lag nuisance
  parameters are held at their generating values rather than re-fitted per
  scene -- a small advantage to this method, stated rather than hidden.

Configurations: N = 5, 14, 21, 38; texture off and on (order 8); patches 16 and
32 px. Coverage is the fraction of independent test scenes whose interval
contains the true N, at nominal 90 % and 95 %, each with its binomial Monte
Carlo standard error. Seeds are spawned from one recorded root.
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "enl_interval_validation.json"
ENL_JSON = BASE_DIR / "docs" / "enl.json"

ROOT_SEED = 20260925
N_TRUE = (5, 14, 21, 38)
TEXTURE = (float("inf"), 8.0)
PATCHES = (16, 32)
ROWS, COLS = 1024, 512
BLOCK_PX = 64
S_TEST = 150
B_BLOCK = 200
GRID_N = (2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 17, 21, 25, 30, 38, 46, 55, 65)
R_GRID = 200
LEVELS = (0.90, 0.95)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def _lags() -> tuple[float, float]:
    """The product's LH intensity lag-one correlations, as the benchmark reads them."""
    d = json.loads(ENL_JSON.read_text(encoding="utf-8"))
    lc = d["lag_correlation"]["LH"]
    return float(lc["azimuth_lines"][0]), float(lc["range_samples"][0])


def _scene(seed: int, n: int, nu: float, rho_i):
    import enl_benchmark as EB
    rng = np.random.default_rng(seed)
    return EB.speckle_field(rng, n, ROWS, COLS, np.sqrt(rho_i[0]), np.sqrt(rho_i[1]), nu), rng


def _mode(v: np.ndarray) -> float:
    import enl_benchmark as EB
    v = v[np.isfinite(v) & (v > 0)]
    return EB.mode_of(v)


def block_boot_2d(grid: np.ndarray, b: int, B: int, rng) -> np.ndarray:
    """Resample non-overlapping b x b blocks of the patch grid, pool, take the mode."""
    R, C = grid.shape[0] // b * b, grid.shape[1] // b * b
    blocks = grid[:R, :C].reshape(R // b, b, C // b, b).swapaxes(1, 2).reshape(-1, b * b)
    nb = blocks.shape[0]
    out = np.empty(B)
    for k in range(B):
        out[k] = _mode(blocks[rng.integers(0, nb, nb)].ravel())
    return out


def test_task(args):
    """One test scene: the estimate and its block-bootstrap distribution, per patch."""
    import bootstrap_enl as BE
    seed, n, nu, rho_i = args
    i, rng = _scene(seed, n, nu, rho_i)
    ones = np.ones_like(i, dtype=bool)
    res = {}
    for p in PATCHES:
        g = BE.ratio_grid(i, ones, p)
        est = _mode(g.ravel())
        bb = block_boot_2d(g, max(BLOCK_PX // p, 1), B_BLOCK, rng)
        res[p] = {"est": est, "boot_q": np.percentile(bb, [2.5, 5, 50, 95, 97.5]).tolist(),
                  "n_patches": int(np.isfinite(g).sum())}
    return res


def grid_task(args):
    """One texture-free scene at a grid N: the estimate per patch size."""
    import bootstrap_enl as BE
    seed, n, rho_i = args
    i, _ = _scene(seed, n, float("inf"), rho_i)
    ones = np.ones_like(i, dtype=bool)
    return {p: _mode(BE.ratio_grid(i, ones, p).ravel()) for p in PATCHES}


def neyman(est: float, table: dict, alpha: float) -> list:
    """Every N whose central (1 - alpha) band of the simulated estimator contains
    est. Quantile curves are made monotone in N and interpolated in log N."""
    ns = np.array(sorted(table))
    lo_q = np.maximum.accumulate(np.array([np.quantile(table[n], alpha / 2) for n in ns]))
    hi_q = np.maximum.accumulate(np.array([np.quantile(table[n], 1 - alpha / 2) for n in ns]))
    ln = np.log(ns)
    # lower end: smallest N with hi_q(N) >= est; upper end: largest N with lo_q(N) <= est
    lower = float(np.exp(np.interp(est, hi_q, ln))) if est > hi_q[0] else float(ns[0])
    upper = float(np.exp(np.interp(est, lo_q, ln))) if est < lo_q[-1] else float("inf")
    return [lower, upper]


def param_basic(est: float, table: dict, alpha: float) -> list:
    """Basic parametric bootstrap at the estimate: quantiles of the simulated
    estimator at N = est (interpolated in log N), reflected about est."""
    ns = np.array(sorted(table))
    ln = np.log(ns)
    q_lo = np.interp(np.log(est), ln, [np.quantile(table[n], alpha / 2) for n in ns])
    q_hi = np.interp(np.log(est), ln, [np.quantile(table[n], 1 - alpha / 2) for n in ns])
    return [2 * est - q_hi, 2 * est - q_lo]


def main() -> int:
    from runinfo import run_info
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    rho_i = _lags()
    root = np.random.SeedSequence(ROOT_SEED)
    s_grid, s_test = root.spawn(2)

    print("=" * 78)
    print("ENL INTERVAL VALIDATION (M8) — coverage of two interval procedures")
    print("=" * 78)
    print(f"  scenes {ROWS} x {COLS}; lags az {rho_i[0]:.3f} rg {rho_i[1]:.3f}; block "
          f"{BLOCK_PX} px; B = {B_BLOCK}; {S_TEST} test scenes per configuration; "
          f"grid {len(GRID_N)} N x {R_GRID}; root seed {ROOT_SEED}", flush=True)

    grid_jobs = [(int(ss.generate_state(1)[0]), n, rho_i)
                 for n, ss_n in zip(GRID_N, s_grid.spawn(len(GRID_N)))
                 for ss in ss_n.spawn(R_GRID)]
    test_cfg = [(n, nu) for n in N_TRUE for nu in TEXTURE]
    test_jobs = [(int(ss.generate_state(1)[0]), n, nu, rho_i)
                 for (n, nu), ss_c in zip(test_cfg, s_test.spawn(len(test_cfg)))
                 for ss in ss_c.spawn(S_TEST)]

    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        grid_out = list(ex.map(grid_task, grid_jobs, chunksize=4))
        print(f"  grid done: {len(grid_out)} scenes", flush=True)
        test_out = list(ex.map(test_task, test_jobs, chunksize=2))
        print(f"  test scenes done: {len(test_out)}", flush=True)

    tables = {p: {} for p in PATCHES}
    for (seed, n, _), r in zip(grid_jobs, grid_out):
        for p in PATCHES:
            tables[p].setdefault(n, []).append(r[p])
    tables = {p: {n: np.array(v) for n, v in t.items()} for p, t in tables.items()}

    rows = []
    for (n, nu) in test_cfg:
        res = [r for (s, nn, uu, _), r in zip(test_jobs, test_out) if nn == n and uu == nu]
        for p in PATCHES:
            est = np.array([r[p]["est"] for r in res])
            bq = np.array([r[p]["boot_q"] for r in res])
            cov = {}
            for lev in LEVELS:
                a = 1 - lev
                qi = (0, 4) if lev == 0.95 else (1, 3)
                pct = [(q[qi[0]], q[qi[1]]) for q in bq]
                basic = [(2 * e - q[qi[1]], 2 * e - q[qi[0]]) for e, q in zip(est, bq)]
                ney = [neyman(e, tables[p], a) for e in est]
                pb = [param_basic(e, tables[p], a) for e in est]
                for name, iv in (("block2d_percentile", pct), ("block2d_basic", basic),
                                 ("parametric_neyman", ney), ("parametric_basic", pb)):
                    hit = np.array([lo <= n <= hi for lo, hi in iv])
                    c = float(hit.mean())
                    widths = np.array([hi - lo for lo, hi in iv if np.isfinite(hi)])
                    cov.setdefault(name, {})[f"{int(100 * lev)}"] = {
                        "coverage": c, "mc_se": float(np.sqrt(c * (1 - c) / hit.size)),
                        "median_width": float(np.median(widths)) if widths.size else None}
            row = {"true_N": n, "texture": "off" if not np.isfinite(nu) else f"order {nu:g}",
                   "patch_px": p, "scenes": int(est.size),
                   "n_patches": res[0][p]["n_patches"],
                   "block_patches": max(BLOCK_PX // p, 1),
                   "estimate_median": float(np.median(est)),
                   "relative_bias_median": float(np.median(est) / n - 1),
                   "coverage": cov}
            rows.append(row)
            c95 = {k: v["95"]["coverage"] for k, v in cov.items()}
            print(f"  N {n:>2} tex {row['texture']:<8} p {p}: est {np.median(est):6.2f}  "
                  + "  ".join(f"{k} {100 * v:5.1f}%" for k, v in c95.items()), flush=True)

    def summary(tex):
        out = {}
        for name in ("block2d_percentile", "block2d_basic", "parametric_neyman", "parametric_basic"):
            for lev in ("90", "95"):
                v = [r["coverage"][name][lev]["coverage"] for r in rows if r["texture"] == tex]
                out.setdefault(name, {})[lev] = {"min": min(v), "max": max(v),
                                                 "median": float(np.median(v))}
        return out

    OUT.write_text(json.dumps({
        "schema": "lunar-ice/enl-interval-validation/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/enl_interval_validation.py",
        "review_item": "M8",
        "estimator": "mode of per-patch mean^2/var (measure_enl.mode_of, 120 log bins)",
        "scenes": {"rows": ROWS, "cols": COLS, "generator": "enl_benchmark.speckle_field",
                   "intensity_lag1_target": {"azimuth": rho_i[0], "range": rho_i[1]},
                   "texture_on": "K texture, Gamma(8, 1/8) per cell"},
        "block_bootstrap_2d": {
            "block_px": BLOCK_PX, "B": B_BLOCK,
            "correlation_lengths_px": {"azimuth": float(-1 / np.log(rho_i[0])),
                                       "range": float(-1 / np.log(rho_i[1]))},
            "rule": "block >= 3 x the correlation length in both axes",
            "intervals": {"percentile": "[q_a/2, q_1-a/2] of the bootstrap modes",
                          "basic": "[2 est - q_1-a/2, 2 est - q_a/2]"}},
        "parametric": {
            "model": "texture-free correlated speckle at the product's lags",
            "grid_N": list(GRID_N), "replicates_per_N": R_GRID,
            "nuisance": "lags held at their generating values, not re-fitted per scene",
            "intervals": {"neyman": "every N whose central band contains the estimate",
                          "basic": "quantiles at N = est, reflected about est"}},
        "seed_root": ROOT_SEED, "test_scenes_per_configuration": S_TEST,
        "levels": list(LEVELS), "rows": rows,
        "summary_texture_off": summary("off"), "summary_texture_on": summary("order 8"),
        "run_info": run_info()}, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
