"""
f2_maximum.py -- P5. The maximum CPR over crater F2's ACTUAL amplitude mask,
with the CPR field drawn as CORRELATED F variates.

    python backend/scripts/f2_maximum.py [--trials 10000]

The paper's F2 figures are the expected maximum of independent F(2N, 2N)
draws over 1521 disc pixels, or over 24.7 effective samples. Neither is the
crater as measured: 260 of the 1521 disc pixels returned amplitude, and
neighbouring pixels are correlated (lag-one 0.884 azimuth, 0.509 range on the
CPR field, cpr_significance.json::effective_samples). So:

  1. the F2 disc and its amplitude mask are built exactly as
     check_f2_footprint.py builds them (validated forward projection, 44 px
     disc at 25 m);
  2. an exponential and a Gaussian correlogram are fitted per axis to the
     measured lag-1 and lag-2 correlations; the better fit is used, both are
     recorded; the 2-D correlation is the separable product;
  3. the CPR field over the disc is 0.7 * X / Y with X, Y independent
     Gamma(N, 1/N) fields sharing that spatial correlation (Gaussian copula:
     Cholesky of the disc correlation matrix, Phi, Gamma quantile);
  4. per trial: the maximum over the amplitude pixels and over the full disc,
     and the count of amplitude pixels above 1.00.

At N = 5 and N = 13.72, true CPR 0.7, with the independent-sample figures
(25, 260, 1521 samples) computed by the same code for comparison, and the
paper's f2_peak_cpr rows quoted verbatim beside them.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import tifffile
from scipy.optimize import minimize_scalar
from scipy.stats import gamma as Gamma, norm

BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
RAW = BASE_DIR / "data" / "pradan" / "raw" / "data" / "calibrated" / "20200808"
NATIVE = BASE_DIR / "data" / "pradan" / "native"
STEM = "ch2_sar_ncxl_20200808t201154198"
OUT = BASE_DIR / "docs" / "f2_maximum.json"
SIG = BASE_DIR / "docs" / "cpr_significance.json"
FOOT = BASE_DIR / "docs" / "f2_footprint.json"

SEED = 7
TRUE_CPR = 0.7
THRESHOLD = 1.0
N_VALUES = (5.0, 13.72)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def fit_correlogram(r1: float, r2: float) -> dict:
    """Least squares over lags 1 and 2 for rho(d) = exp(-d/l) and exp(-d^2/l^2)."""
    out = {}
    for name, fn in (("exponential", lambda d, l: np.exp(-d / l)),
                     ("gaussian", lambda d, l: np.exp(-(d / l) ** 2))):
        res = minimize_scalar(lambda l: (fn(1, l) - r1) ** 2 + (fn(2, l) - r2) ** 2,
                              bounds=(0.05, 50.0), method="bounded")
        out[name] = {"length_px": float(res.x), "sse": float(res.fun),
                     "fitted_lag1": float(fn(1, res.x)), "fitted_lag2": float(fn(2, res.x))}
    out["chosen"] = min(("exponential", "gaussian"), key=lambda k: out[k]["sse"])
    return out


def rho_fn(fit: dict):
    kind, l = fit["chosen"], fit[fit["chosen"]]["length_px"]
    if kind == "exponential":
        return lambda d: np.exp(-np.abs(d) / l)
    return lambda d: np.exp(-(d / l) ** 2)


def summarise(x: np.ndarray, rng) -> dict:
    """median, p95, P(> threshold) with bootstrap / binomial SE."""
    b = np.array([np.percentile(x[rng.integers(0, x.size, x.size)], [50, 95]) for _ in range(200)])
    p = float((x > THRESHOLD).mean())
    return {"median": float(np.median(x)), "median_se": float(b[:, 0].std(ddof=1)),
            "p95": float(np.percentile(x, 95)), "p95_se": float(b[:, 1].std(ddof=1)),
            "p_exceeds_threshold": p,
            "p_exceeds_se": float(np.sqrt(p * (1 - p) / x.size)), "n_trials": int(x.size)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=10_000)
    args = ap.parse_args()
    rng = np.random.default_rng(SEED)
    from app.ingestion.sar_geometry import read_geotiff_frame

    foot = json.loads(FOOT.read_text(encoding="utf-8"))
    F2 = foot["target"]
    frame = read_geotiff_frame(RAW / f"{STEM}_d_sri_xx_cp_lh_d18.tif",
                               RAW / f"{STEM}_d_sri_xx_cp_xx_d18.xml")
    lines, samples = frame.shape
    x, y = frame.latlon_to_xy(F2["lat_deg"], F2["lon_deg"])
    line, sample = (float(v) for v in frame.xy_to_pixel(x, y))
    valid = tifffile.imread(str(NATIVE / "valid_native.tif")).astype(bool)
    li, si = int(round(line)), int(round(sample))
    r_px = F2["diameter_km"] * 1000.0 / 2.0 / 25.0
    y0, y1 = max(0, int(li - r_px) - 1), min(lines, int(li + r_px) + 2)
    x0, x1 = max(0, int(si - r_px) - 1), min(samples, int(si + r_px) + 2)
    yy, xx = np.mgrid[y0:y1, x0:x1]
    disc = ((yy - line) ** 2 + (xx - sample) ** 2) <= r_px ** 2
    amp = valid[y0:y1, x0:x1] & disc
    n_disc, n_amp = int(disc.sum()), int(amp.sum())
    assert n_disc == foot["disc_pixels"], (n_disc, foot["disc_pixels"])

    sig = json.loads(SIG.read_text(encoding="utf-8"))["effective_samples"]
    fit_az = fit_correlogram(sig["rho_lag1_axis0"], sig["rho_lag2_axis0"])
    fit_rg = fit_correlogram(sig["rho_lag1_axis1"], sig["rho_lag2_axis1"])
    f_az, f_rg = rho_fn(fit_az), rho_fn(fit_rg)

    print("=" * 78)
    print("F2 MAXIMUM on the actual amplitude mask, correlated F field")
    print("=" * 78)
    print(f"  disc {n_disc} px, amplitude {n_amp} px ({100 * n_amp / n_disc:.1f} %)")
    print(f"  correlogram az: {fit_az['chosen']} l = {fit_az[fit_az['chosen']]['length_px']:.3f} px "
          f"(exp sse {fit_az['exponential']['sse']:.2e}, gauss sse {fit_az['gaussian']['sse']:.2e})")
    print(f"  correlogram rg: {fit_rg['chosen']} l = {fit_rg[fit_rg['chosen']]['length_px']:.3f} px "
          f"(exp sse {fit_rg['exponential']['sse']:.2e}, gauss sse {fit_rg['gaussian']['sse']:.2e})")

    # correlation matrix over the disc pixels (separable), Cholesky
    py, px = yy[disc].astype(float), xx[disc].astype(float)
    C = f_az(py[:, None] - py[None, :]) * f_rg(px[:, None] - px[None, :])
    L = np.linalg.cholesky(C + 1e-9 * np.eye(n_disc))
    amp_idx = amp[disc]
    print(f"  Cholesky of {n_disc}x{n_disc}: ok;  {args.trials:,} trials, seed {SEED}")

    def gamma_field(n_looks, z):
        return Gamma.ppf(norm.cdf(z), n_looks, scale=1.0 / n_looks)

    results = {}
    for N in N_VALUES:
        # correlated field over the disc, in batches
        mx_amp, mx_disc, cnt = [], [], []
        B = 1000
        for _ in range(0, args.trials, B):
            zx = (L @ rng.standard_normal((n_disc, B))).T
            zy = (L @ rng.standard_normal((n_disc, B))).T
            cpr = TRUE_CPR * gamma_field(N, zx) / gamma_field(N, zy)
            mx_amp.append(cpr[:, amp_idx].max(axis=1))
            mx_disc.append(cpr.max(axis=1))
            cnt.append((cpr[:, amp_idx] > THRESHOLD).sum(axis=1))
        mx_amp, mx_disc, cnt = map(np.concatenate, (mx_amp, mx_disc, cnt))
        # achieved lag-1 correlation of the simulated CPR field (check on the copula)
        zx = (L @ rng.standard_normal((n_disc, 2000))).T
        zy = (L @ rng.standard_normal((n_disc, 2000))).T
        c = TRUE_CPR * gamma_field(N, zx) / gamma_field(N, zy)
        pairs = [(i, j) for i in range(n_disc) for j in range(i + 1, n_disc)
                 if py[i] == py[j] and abs(px[i] - px[j]) == 1]
        i_, j_ = np.array(pairs).T
        ach_rg = float(np.corrcoef(c[:, i_].ravel(), c[:, j_].ravel())[0, 1])
        pairs = [(i, j) for i in range(n_disc) for j in range(i + 1, n_disc)
                 if px[i] == px[j] and abs(py[i] - py[j]) == 1]
        i_, j_ = np.array(pairs).T
        ach_az = float(np.corrcoef(c[:, i_].ravel(), c[:, j_].ravel())[0, 1])

        # independent references, same code, same true CPR
        ind = {}
        for n_s in (25, n_amp, n_disc):
            z = rng.standard_normal((args.trials, n_s))
            w = rng.standard_normal((args.trials, n_s))
            ind[str(n_s)] = summarise((TRUE_CPR * gamma_field(N, z) / gamma_field(N, w)).max(axis=1), rng)
        # and at true CPR 1.0 over the disc, the paper's f2_peak_cpr convention
        z = rng.standard_normal((args.trials, n_disc)); w = rng.standard_normal((args.trials, n_disc))
        ind_cpr1_disc = summarise((gamma_field(N, z) / gamma_field(N, w)).max(axis=1), rng)

        r = {"n_looks": N,
             "correlated_max_over_amplitude_pixels": summarise(mx_amp, rng),
             "correlated_max_over_full_disc": summarise(mx_disc, rng),
             "exceedance_count_over_amplitude_pixels": {
                 "mean": float(cnt.mean()), "se": float(cnt.std(ddof=1) / np.sqrt(cnt.size)),
                 "p_at_least_one": float((cnt >= 1).mean()),
                 "p95": float(np.percentile(cnt, 95)), "max": int(cnt.max())},
             "achieved_lag1_of_simulated_cpr": {"azimuth": ach_az, "range": ach_rg},
             "independent_max_true_cpr_0p7": ind,
             "independent_max_true_cpr_1p0_over_disc": ind_cpr1_disc}
        # keyed "N5", "N13p72": the audit addresses artifacts by dotted path
        results[f"N{N:g}".replace(".", "p")] = r
        a, d = r["correlated_max_over_amplitude_pixels"], r["correlated_max_over_full_disc"]
        print(f"\n  N = {N:g}")
        print(f"    correlated, {n_amp} amplitude px: max median {a['median']:.3f} ± {a['median_se']:.3f}  "
              f"p95 {a['p95']:.3f}  P(max>1) {a['p_exceeds_threshold']:.4f} ± {a['p_exceeds_se']:.4f}")
        print(f"    correlated, {n_disc} disc px:     max median {d['median']:.3f}  p95 {d['p95']:.3f}  "
              f"P(max>1) {d['p_exceeds_threshold']:.4f}")
        print(f"    count > 1 over amplitude px: mean {cnt.mean():.3f} ± {cnt.std(ddof=1) / np.sqrt(cnt.size):.3f}, "
              f"P(>=1) {(cnt >= 1).mean():.4f}")
        for k, v in ind.items():
            print(f"    independent {k:>5} px:         max median {v['median']:.3f}  p95 {v['p95']:.3f}  "
                  f"P(max>1) {v['p_exceeds_threshold']:.4f}")
        print(f"    independent {n_disc} px at true CPR 1.0: max median {ind_cpr1_disc['median']:.3f}")
        print(f"    achieved lag-1 of the simulated CPR field: az {ach_az:.3f}  rg {ach_rg:.3f}")

    paper = json.loads(SIG.read_text(encoding="utf-8"))["f2_peak_cpr"]
    OUT.write_text(json.dumps({
        "schema": "lunar-ice/f2-maximum/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/f2_maximum.py",
        "seed": SEED, "trials": args.trials, "true_cpr": TRUE_CPR, "threshold": THRESHOLD,
        "disc": {"centre_line": line, "centre_sample": sample, "radius_px": r_px,
                 "pixels": n_disc, "amplitude_pixels": n_amp,
                 "built_as": "check_f2_footprint.py: validated forward projection, "
                             "disc of radius 22 px at 25 m, amplitude = valid_native.tif"},
        "correlation": {"measured": {k: sig[k] for k in ("rho_lag1_axis0", "rho_lag2_axis0",
                                                          "rho_lag1_axis1", "rho_lag2_axis1")},
                        "measured_from": "docs/cpr_significance.json::effective_samples "
                                         "(CPR field, 64-px patches)",
                        "fit_azimuth": fit_az, "fit_range": fit_rg,
                        "model": "separable product of the chosen per-axis correlograms; "
                                 "Gaussian copula on Gamma(N, 1/N) for X and Y independently; "
                                 "CPR = 0.7 X / Y"},
        "results": results,
        "paper_f2_peak_cpr_verbatim": paper,
        "paper_convention": "f2_peak_cpr is the expected maximum of independent F(2N,2N) "
                            "draws at TRUE CPR 0.7 over 1520 pixels (raw) or 24.7 effective "
                            "samples: its N = 5 rows, 7.38 and 2.52, are reproduced here by "
                            "independent_max_true_cpr_0p7 at 1521 and 25 samples (7.377, "
                            "2.528). independent_max_true_cpr_1p0_over_disc is the same "
                            "quantity at true CPR 1 and is NOT the paper's convention",
    }, indent=2, default=float), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
