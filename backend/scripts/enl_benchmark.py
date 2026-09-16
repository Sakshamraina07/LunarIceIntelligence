"""
enl_benchmark.py -- P2. The ENL estimator, benchmarked on synthetic fields whose
look count is KNOWN, and compared against two other estimators on the SLC.

    python backend/scripts/enl_benchmark.py [--replicates 200] [--B 2000]
                                            [--rows 1024] [--cols 512]

PART A -- SYNTHETIC BENCHMARK (review 4.11)
-------------------------------------------
The estimator on the delivered product is the mode of per-patch mean^2/var over
16 x 16 patches, with a percentile bootstrap over rows of the patch grid. None
of that has been checked against a field whose ENL is known. Here it is: N-look
intensity formed from N independent complex circular-Gaussian looks, each with
separable AR(1) correlation chosen so the INTENSITY lag-one correlation equals
the product's measured +0.838 (azimuth) and +0.576 (range) -- intensity
correlation is the squared field correlation, for any N, when the looks are
independent. Multiplicative texture, K-distributed (Gamma(nu, 1/nu) per cell),
at orders {inf, 8, 4}. Then THE IDENTICAL PIPELINE: measure_enl.patch_ratios,
measure_enl.mode_of, bootstrap_enl.block_boot and simple_boot, imported.

Reported per configuration: bias, RMSE, and the coverage of the 95 % interval,
each with its Monte Carlo standard error over the replicates. No boxcar: the
benchmark is of the raw estimator, the one that reports 5.83 / 5.14.

The AR(1) field matches lag one BY CONSTRUCTION; its lag-two intensity
correlation is rho^2 = 0.702 (az) against the product's 0.565, so the synthetic
field is MORE correlated at longer lags than the product. That direction makes
the benchmark conservative for the interval width and is recorded, not hidden.

PART B -- THREE ESTIMATORS ON THE SLC SPATIAL ARM (review 5.3)
--------------------------------------------------------------
On the 21-look coherency matrix formed from the SLC (no boxcar), over 16 x 16
patches wholly inside the swath:
  moment        mean^2 / var of each channel's intensity   (the project's)
  trace-moment  Anfinsen, Doulgeris & Eltoft (2009), TGRS 47(11):
                L = tr(<C>)^2 / ( <tr(C^2)> - tr(<C>^2) )
  log-cumulant  Anfinsen et al. (2009): var(ln det C) = psi'(L) + psi'(L-1)
                for d = 2, solved for L; and the single-channel var(ln I) = psi'(L)
Each with a block-bootstrap percentile interval over rows of the patch grid.
Point estimate is the MODE over patches, the pipeline's convention; the median
is reported beside it.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.optimize import brentq
from scipy.signal import lfilter
from scipy.special import polygamma

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "enl_benchmark.json"
ENL_JSON = BASE_DIR / "docs" / "enl.json"

SEED = 11
PATCH = 16
ENL_GRID = (4, 6, 8, 12)
TEXTURE_ORDERS = (float("inf"), 8.0, 4.0)
BURN = 64
CHUNK = 512
AZIMUTH_LOOKS = 21

_T0 = time.time()
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def beat(msg: str) -> None:
    print(f"  [{time.strftime('%H:%M:%S')}  +{time.time() - _T0:7.1f}s]  {msg}", flush=True)


def hr(t: str) -> None:
    print("\n" + "=" * 78 + "\n" + t + "\n" + "=" * 78, flush=True)


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        "_" + name, Path(__file__).with_name(name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ME = _load("measure_enl")
BE = _load("bootstrap_enl")
SF = _load("stokes_from_slc")
patch_ratios, mode_of = ME.patch_ratios, ME.mode_of


# ----------------------------------------------------------------------------
# PART A
# ----------------------------------------------------------------------------
def ar1(w: np.ndarray, rho: float, axis: int) -> np.ndarray:
    """x[i] = rho x[i-1] + sqrt(1-rho^2) w[i]: unit variance in steady state."""
    return lfilter([np.sqrt(1.0 - rho ** 2)], [1.0, -rho], w, axis=axis)


def speckle_field(rng, n_looks: int, rows: int, cols: int, rho_az: float,
                  rho_rg: float, nu: float) -> np.ndarray:
    """N-look intensity with the target lag-one intensity correlations, times
    K-distributed texture of order nu (inf = none). Unit mean."""
    R, C = rows + BURN, cols + BURN
    acc = np.zeros((rows, cols))
    for _ in range(n_looks):
        w = (rng.standard_normal((R, C)) + 1j * rng.standard_normal((R, C))) / np.sqrt(2.0)
        x = ar1(ar1(w, rho_az, 0), rho_rg, 1)[BURN:, BURN:]
        acc += np.abs(x) ** 2
    acc /= n_looks
    if np.isfinite(nu):
        acc *= rng.gamma(nu, 1.0 / nu, acc.shape)
    return acc


def lag1(i: np.ndarray, p: int = PATCH) -> dict:
    """Intensity lag-one correlation, patch-mean removed, as measure_enl does."""
    c = ME.lag_correlation(i, np.ones_like(i, dtype=bool), p, max_lag=3)
    return {"azimuth": c["azimuth_lines"], "range": c["range_samples"]}


def part_a(args, rng, rho_i_az, rho_i_rg) -> list:
    rho_f_az, rho_f_rg = np.sqrt(rho_i_az), np.sqrt(rho_i_rg)
    hr("PART A — synthetic benchmark of the estimator at KNOWN ENL")
    print(f"  field {args.rows} x {args.cols}, patch {PATCH}, {args.replicates} replicates "
          f"per configuration, B = {args.B:,}, seed {SEED}")
    print(f"  target intensity lag-1: az {rho_i_az:.3f}, rg {rho_i_rg:.3f}  "
          f"-> field AR(1) rho: az {rho_f_az:.4f}, rg {rho_f_rg:.4f}")
    print(f"\n  {'N':>3} {'nu':>5} {'bias':>8} {'±SE':>6} {'RMSE':>7} "
          f"{'cov.block':>10} {'±SE':>6} {'cov.simple':>11} {'lag1 az':>8} {'lag1 rg':>8}")
    rows = []
    for n in ENL_GRID:
        for nu in TEXTURE_ORDERS:
            est, cov_b, cov_s, l1a, l1r, width_b = [], [], [], [], [], []
            for _ in range(args.replicates):
                i = speckle_field(rng, n, args.rows, args.cols, rho_f_az, rho_f_rg, nu)
                ones = np.ones_like(i, dtype=bool)
                r = patch_ratios(i, ones, PATCH)
                e = mode_of(r)
                est.append(e)
                g = BE.ratio_grid(i, ones, PATCH)
                bb = BE.block_boot(g, args.B, rng)
                sb = BE.simple_boot(r, args.B, rng)
                lo, hi = BE.ci(bb)
                cov_b.append(lo <= n <= hi)
                width_b.append(hi - lo)
                lo, hi = BE.ci(sb)
                cov_s.append(lo <= n <= hi)
                c = lag1(i)
                l1a.append(c["azimuth"][0]); l1r.append(c["range"][0])
            est = np.array(est)
            m = args.replicates
            bias = float(est.mean() - n)
            bias_se = float(est.std(ddof=1) / np.sqrt(m))
            rmse = float(np.sqrt(np.mean((est - n) ** 2)))
            cb, cs = float(np.mean(cov_b)), float(np.mean(cov_s))
            cb_se = float(np.sqrt(cb * (1 - cb) / m))
            cs_se = float(np.sqrt(cs * (1 - cs) / m))
            label = "inf" if not np.isfinite(nu) else f"{nu:g}"
            print(f"  {n:>3} {label:>5} {bias:>+8.3f} {bias_se:>6.3f} {rmse:>7.3f} "
                  f"{cb:>10.3f} {cb_se:>6.3f} {cs:>11.3f} {np.mean(l1a):>8.3f} {np.mean(l1r):>8.3f}",
                  flush=True)
            rows.append({"true_enl": n, "texture_order": (None if not np.isfinite(nu) else nu),
                         "texture_label": label, "replicates": m,
                         "estimate_mean": float(est.mean()), "estimate_sd": float(est.std(ddof=1)),
                         "bias": bias, "bias_se": bias_se, "rmse": rmse,
                         "relative_bias": bias / n,
                         "coverage_block_95": cb, "coverage_block_se": cb_se,
                         "coverage_simple_95": cs, "coverage_simple_se": cs_se,
                         "mean_block_interval_width": float(np.mean(width_b)),
                         "measured_lag1_az": float(np.mean(l1a)),
                         "measured_lag1_rg": float(np.mean(l1r)),
                         "n_patches": int(r.size)})
    return rows


# ----------------------------------------------------------------------------
# PART B
# ----------------------------------------------------------------------------
def coherency_21(eh, ev, scale_h, scale_v, scale_x):
    n_out = SF.LINES // AZIMUTH_LOOKS
    hh = np.empty((n_out, SF.SAMPLES)); vv = np.empty((n_out, SF.SAMPLES))
    hv = np.empty((n_out, SF.SAMPLES), dtype=np.complex128)
    for start in range(0, n_out, CHUNK):
        stop = min(start + CHUNK, n_out)
        a = np.asarray(eh[start * AZIMUTH_LOOKS:stop * AZIMUTH_LOOKS], dtype=np.complex128)
        b = np.asarray(ev[start * AZIMUTH_LOOKS:stop * AZIMUTH_LOOKS], dtype=np.complex128)
        a = a.reshape(stop - start, AZIMUTH_LOOKS, SF.SAMPLES)
        b = b.reshape(stop - start, AZIMUTH_LOOKS, SF.SAMPLES)
        hh[start:stop] = (np.abs(a) ** 2).mean(axis=1) * scale_h
        vv[start:stop] = (np.abs(b) ** 2).mean(axis=1) * scale_v
        hv[start:stop] = (a * np.conj(b)).mean(axis=1) * scale_x
        del a, b
    return hh, vv, hv


def tiles(a, mask, p):
    """(rows, cols, p*p) tiles and the wholly-inside flag per tile."""
    h, w = (a.shape[0] // p) * p, (a.shape[1] // p) * p
    t = a[:h, :w].reshape(h // p, p, w // p, p).swapaxes(1, 2).reshape(h // p, w // p, p * p)
    m = mask[:h, :w].reshape(h // p, p, w // p, p).swapaxes(1, 2).reshape(h // p, w // p, p * p)
    return t, m.all(axis=2)


def solve_logcum(v: float, d: int) -> float:
    """L such that sum_{i<d} psi'(L - i) = v. NaN if v is outside the range."""
    f = lambda L: sum(polygamma(1, L - i) for i in range(d)) - v
    lo, hi = d - 1 + 1e-6, 1e5
    if not np.isfinite(v) or f(lo) < 0 or f(hi) > 0:
        return float("nan")
    return float(brentq(f, lo, hi, xtol=1e-10))


def grid_stats(grid: np.ndarray, B: int, rng) -> dict:
    vals = grid[np.isfinite(grid) & (grid > 0)]
    if vals.size < 30:
        return {"n_patches": int(vals.size), "mode": None}
    bb = BE.block_boot(grid, B, rng)
    return {"n_patches": int(vals.size), "mode": float(mode_of(vals)),
            "median": float(np.median(vals)),
            "p25": float(np.percentile(vals, 25)), "p75": float(np.percentile(vals, 75)),
            "mode_ci_block_95": BE.ci(bb), "mode_bootstrap_sd": float(bb.std(ddof=1)),
            "median_ci_block_95": BE.ci(np.array([
                np.nanmedian(grid[rng.integers(0, grid.shape[0], grid.shape[0])])
                for _ in range(B)]))}


def part_b(args, rng) -> dict:
    hr("PART B — moment, trace-moment and log-cumulant ENL on the SLC spatial arm")
    lab = SF.label_fields()
    k_lin = 10.0 ** (lab["calibration_constant_db"] / 10.0)
    g_lh, g_lv = lab["gain_imbalance"]["LH"], lab["gain_imbalance"]["LV"]
    sin_t = float(np.sin(np.deg2rad(lab["incidence_angle_deg"])))
    sc = sin_t / k_lin
    eh, ev = SF.open_slc("lh"), SF.open_slc("lv")
    hh, vv, hv = coherency_21(eh, ev, sc / g_lh ** 2, sc / g_lv ** 2, sc / (g_lh * g_lv))
    mask = (hh > 0) & (vv > 0)
    beat(f"21-look coherency, no boxcar: {hh.shape[0]:,} x {hh.shape[1]}, "
         f"{int(mask.sum()):,} cells in the swath")

    T_hh, ok = tiles(hh, mask, PATCH)
    T_vv, _ = tiles(vv, mask, PATCH)
    T_hv, _ = tiles(hv, mask, PATCH)
    nan = np.full(ok.shape, np.nan)

    def per_patch(fn):
        out = nan.copy()
        idx = np.argwhere(ok)
        for r, c in idx:
            out[r, c] = fn(T_hh[r, c], T_vv[r, c], T_hv[r, c])
        return out

    def moment(x):
        v = x.var(ddof=1)
        return x.mean() ** 2 / v if v > 0 else np.nan

    def trace_moment(a, b, x):
        tr = a + b
        tr2 = a ** 2 + b ** 2 + 2.0 * np.abs(x) ** 2
        den = tr2.mean() - (a.mean() ** 2 + b.mean() ** 2 + 2.0 * abs(x.mean()) ** 2)
        return tr.mean() ** 2 / den if den > 0 else np.nan

    def logcum2(a, b, x):
        det = a * b - np.abs(x) ** 2
        det = det[det > 0]
        if det.size < 8:
            return np.nan
        return solve_logcum(float(np.var(np.log(det), ddof=1)), 2)

    def logcum1(a):
        a = a[a > 0]
        return solve_logcum(float(np.var(np.log(a), ddof=1)), 1) if a.size >= 8 else np.nan

    beat("per-patch estimators")
    grids = {
        "moment_LH": per_patch(lambda a, b, x: moment(a)),
        "moment_LV": per_patch(lambda a, b, x: moment(b)),
        "trace_moment_2x2": per_patch(trace_moment),
        "log_cumulant_2x2": per_patch(logcum2),
        "log_cumulant_LH": per_patch(lambda a, b, x: logcum1(a)),
        "log_cumulant_LV": per_patch(lambda a, b, x: logcum1(b)),
    }
    res = {}
    print(f"\n  {'estimator':<20} {'n':>6} {'mode':>7} {'block 95 % CI':>18} {'median':>8} {'IQR':>16}")
    for name, g in grids.items():
        beat(f"bootstrap {name}")
        s = grid_stats(g, args.B, rng)
        res[name] = s
        if s.get("mode") is None:
            print(f"  {name:<20} {s['n_patches']:>6}  too few patches")
            continue
        print(f"  {name:<20} {s['n_patches']:>6} {s['mode']:>7.3f} "
              f"[{s['mode_ci_block_95'][0]:>7.3f}, {s['mode_ci_block_95'][1]:>7.3f}] "
              f"{s['median']:>8.3f} [{s['p25']:>6.3f}, {s['p75']:>6.3f}]")
    return {"estimators": res, "patch": PATCH, "grid_rows": int(ok.shape[0]),
            "grid_cols": int(ok.shape[1]), "n_patches_inside": int(ok.sum()),
            "calibration": {"K_db": lab["calibration_constant_db"], "G_LH": g_lh,
                            "G_LV": g_lv, "sin_theta": sin_t,
                            "note": "scale-free for the single-channel estimators; the "
                                    "per-channel gain enters the 2x2 ones"},
            "definitions": {
                "moment": "mean^2 / var(ddof=1) of the channel intensity per patch",
                "trace_moment_2x2": "tr(<C>)^2 / (<tr(C^2)> - tr(<C>^2)), C the per-cell "
                                    "21-look coherency matrix; Anfinsen et al. 2009 "
                                    "(complex Wishart: E[tr C^2] = tr Sigma^2 + tr(Sigma)^2 / L)",
                "log_cumulant_2x2": "var(ln det C) = psi'(L) + psi'(L-1), solved for L",
                "log_cumulant_1": "var(ln I) = psi'(L), solved for L",
                "point": "mode over patches (measure_enl.mode_of), the pipeline's "
                         "convention; median beside it",
                "interval": f"percentile block bootstrap over rows of the {PATCH}x{PATCH} "
                            f"patch grid, B = {args.B}"}}


def speckle_only_summary(rows: list) -> dict:
    """The two sentences the paper makes of Part A, as keys.

    A pure function of the rows, so it can be recomputed from the artifact
    without re-running an 83-minute Monte Carlo (--summarise-only).
    """
    clean = [r for r in rows if r["texture_order"] is None]
    cov = [r["coverage_block_95"] for r in clean]
    rel = [r["relative_bias"] for r in clean]
    return {
        "configurations": [r["true_enl"] for r in clean],
        "coverage_block_95_min": min(cov), "coverage_block_95_max": max(cov),
        "coverage_percent_range": [100 * min(cov), 100 * max(cov)],
        "relative_bias_median": float(np.median(rel)),
        "relative_bias_percent_median": float(100 * np.median(rel)),
        "bias_at_lowest_N": {"N": clean[0]["true_enl"], "bias": clean[0]["bias"]},
        "bias_at_highest_N": {"N": clean[-1]["true_enl"], "bias": clean[-1]["bias"]},
        "reading": ("on pure correlated speckle the mode estimator reads about "
                    "16 % high at every look count tested, and the nominally "
                    "95 % block-bootstrap procedure covers the true ENL 12-26 % "
                    "of the time: the ranges state precision, not confidence"),
        "raw_enl_corrected": ("5.83 / (1 + relative_bias_median) — the delivered "
                              "product's raw ENL read through the measured bias"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summarise-only", action="store_true",
                    help="recompute the summary block from the stored rows and "
                         "rewrite the artifact; runs no Monte Carlo")
    ap.add_argument("--replicates", type=int, default=200)
    ap.add_argument("--B", type=int, default=BE.B_DEFAULT)
    ap.add_argument("--rows", type=int, default=1024)
    ap.add_argument("--cols", type=int, default=512)
    ap.add_argument("--skip-slc", action="store_true")
    args = ap.parse_args()

    if args.summarise_only:
        doc = json.loads(OUT.read_text(encoding="utf-8"))
        s = speckle_only_summary(doc["synthetic"]["rows"])
        doc["synthetic"]["speckle_only_summary"] = s
        s["raw_enl_5p83_corrected"] = 5.83 / (1.0 + s["relative_bias_median"])
        OUT.write_text(json.dumps(doc, indent=2, default=float), encoding="utf-8")
        print(json.dumps(s, indent=2, default=float))
        print(f"\n  rewrote {OUT.relative_to(BASE_DIR)} (summary only; no Monte Carlo run)")
        return 0

    enl = json.loads(ENL_JSON.read_text(encoding="utf-8"))
    rho_i_az = float(enl["lag_correlation"]["LH"]["azimuth_lines"][0])
    rho_i_rg = float(enl["lag_correlation"]["LH"]["range_samples"][0])
    lag_measured = enl["lag_correlation"]["LH"]

    rng = np.random.default_rng(SEED)
    part_b_res = None if args.skip_slc else part_b(args, rng)
    rng_a = np.random.default_rng(SEED + 1)
    rows = part_a(args, rng_a, rho_i_az, rho_i_rg)

    OUT.write_text(json.dumps({
        "schema": "lunar-ice/enl-benchmark/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/enl_benchmark.py",
        "seed_part_b": SEED, "seed_part_a": SEED + 1, "B": args.B,
        "synthetic": {
            "rows": args.rows, "cols": args.cols, "patch": PATCH,
            "replicates_per_config": args.replicates,
            "enl_grid": list(ENL_GRID),
            "texture_orders": [None if not np.isfinite(t) else t for t in TEXTURE_ORDERS],
            "target_intensity_lag1": {"azimuth": rho_i_az, "range": rho_i_rg,
                                      "read_from": "docs/enl.json::lag_correlation.LH"},
            "product_lag_correlations_LH": lag_measured,
            "field_model": "N independent complex circular-Gaussian looks, each separable "
                           "AR(1) with field rho = sqrt(target intensity lag-1); "
                           "intensity = mean |x|^2; texture = Gamma(nu, 1/nu) per cell "
                           "multiplying the N-look intensity; burn-in 64 rows/cols dropped",
            "pipeline": "measure_enl.patch_ratios + mode_of; bootstrap_enl.block_boot / "
                        "simple_boot / ci -- all imported unmodified; no boxcar",
            "caveat_lag2": "AR(1) gives lag-2 intensity correlation rho^2 (0.702 az) against "
                           "the product's 0.565: the synthetic field is more correlated at "
                           "longer lags than the product",
            "rows": rows,
            "speckle_only_summary": speckle_only_summary(rows)},
        "slc_spatial_arm": part_b_res,
    }, indent=2, default=float), encoding="utf-8")
    beat(f"wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
