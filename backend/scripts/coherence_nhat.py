"""
coherence_nhat.py -- a coherence-aware look count from Var(ln R), validated,
then used in the held-out test of the decision model. (v20 gap pass, G-G)

    python backend/scripts/coherence_nhat.py                 # validation -> docs/coherence_nhat.json
    python backend/scripts/tail_calibration_ci.py --logratio-model-coherence   # held-out test, merged

WHY
---
The paper says circular-channel coherence biases the log-ratio N-hat high and
that the decision model over-rejects (6.38 % at nominal 5 %; 84 of 109 blocks
above nominal against 48.7 expected). enl_logratio inverts
Var(ln R) = 2 psi_1(N), which holds for INDEPENDENT channels. For N-look
complex Wishart channels with squared coherence kappa = |gamma|^2 the
log-ratio variance is smaller (the Kibble bivariate-gamma expansion; the
Laguerre coefficient of ln x is -1/k):

    Var(ln R) = 2 psi_1(N) - 2 sum_{k>=1} kappa^k (k-1)! / (k (N)_k),

(N)_k the Pochhammer symbol; at N = 1 the sum is Li_2(kappa). The estimator
solves this for N given the measured kappa. The ratio's law is
    f(r) = Gamma(2N)/Gamma(N)^2 (1-kappa)^N r^(N-1) (1+r) /
           ((1+r)^2 - 4 kappa r)^(N+1/2)              (Lee et al. 1994),
which replaces F(2N, 2N) in the test when kappa > 0 (they coincide at 0).

kappa is estimated per training half from the cells' squared circular
coherence g2 = (S1^2 + S2^2)/(S0^2 - S3^2) = |C_SC,OC|^2 / (C_SC C_OC):
E[g2] = kappa + (1 - kappa)^2 / N to leading order, so kappa solves
mean(g2) = kappa + (1 - kappa)^2 / N-hat, iterated with N-hat.

VALIDATION
  (1) the series against Monte Carlo of correlated complex-Gaussian pairs;
  (2) the ratio's density integrates to one and has the series' variance;
  (3) the rows of enl_logratio.validation (N = 5, 14, 21, 38, 80, 120, texture
      off and gamma shape 8, the product's lags, 31 x 31 windows, 10 scenes)
      re-simulated with added cross-channel coherence, kappa in {0, 0.05, 0.15,
      0.30}: median bias of N-hat, standard against coherence-aware, with the
      standard error of the median.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.special import gammaln, polygamma
from scipy.optimize import brentq

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "coherence_nhat.json"
SEED = 20260930 + 7
VAL_N = (5, 14, 21, 38, 80, 120)
KAPPAS = (0.0, 0.05, 0.15, 0.30)
WINDOW = 31
SCENES = 10
SHAPE = (256, 256)
KMAX = 80


def _series(n, kappa):
    k = np.arange(1, KMAX + 1)
    lt = k * np.log(max(kappa, 1e-300)) + gammaln(k) + gammaln(n) - np.log(k) - gammaln(n + k)
    return float(np.exp(lt).sum()) if kappa > 0 else 0.0


def var_lnr(n, kappa):
    """Var(ln R) of N-look complex channels with squared coherence kappa."""
    return float(2.0 * polygamma(1, n)) - 2.0 * _series(n, kappa)


def n_from_var(v, kappa):
    """N solving var_lnr(N, kappa) = v (NaN where v <= 0); kappa = 0 gives
    enl_logratio.n_from_var."""
    if not np.isfinite(v) or v <= 0:
        return float("nan")
    lo, hi = 0.05, 1e5
    f = lambda n: var_lnr(n, kappa) - v  # noqa: E731
    if f(lo) < 0:
        return lo
    if f(hi) > 0:
        return float("inf")
    return float(brentq(f, lo, hi, xtol=1e-9, rtol=1e-10))


def kappa_from_g2(m, n):
    """kappa solving m = kappa + (1 - kappa)^2 / n, clipped to [0, 0.98]."""
    a, b, c = 1.0 / n, 1.0 - 2.0 / n, 1.0 / n - m
    disc = b * b - 4 * a * c
    if disc < 0:
        return 0.0
    k = (-b + np.sqrt(disc)) / (2 * a)
    return float(min(max(k, 0.0), 0.98))


def nhat_aware(v, g2_mean, iters=4):
    """(N-hat, kappa-hat): the coherence-aware estimate from the variance of
    ln R and the mean squared coherence of the same cells."""
    n = n_from_var(v, 0.0)
    kap = 0.0
    for _ in range(iters):
        kap = kappa_from_g2(g2_mean, n)
        n = n_from_var(v, kap)
    return n, kap


# ---- the ratio's law ---------------------------------------------------------
_LG = np.linspace(-9.0, 9.0, 6001)


def _logpdf(lr, n, kappa):
    r = np.exp(lr)
    return (gammaln(2 * n) - 2 * gammaln(n) + n * np.log(1 - kappa) + (n - 1) * lr + np.log1p(r)
            - (n + 0.5) * np.log((1 + r) ** 2 - 4 * kappa * r))


def ratio_cdf_table(n, kappa):
    """CDF of ln R on the grid _LG (density of ln R = r f(r))."""
    dens = np.exp(_logpdf(_LG, n, kappa) + _LG)
    cdf = np.concatenate([[0.0], np.cumsum(0.5 * (dens[1:] + dens[:-1]) * np.diff(_LG))])
    return cdf


def ratio_quantile(q, n, kappa):
    """q-quantile of R (scalar or array q) for N looks and coherence kappa."""
    if kappa <= 0:
        from scipy.stats import f as Fd
        return Fd.ppf(q, 2 * n, 2 * n)
    cdf = ratio_cdf_table(n, kappa)
    cdf = cdf / cdf[-1]
    return np.exp(np.interp(q, cdf, _LG))


def ratio_quantiles(qs, n, kappa):
    """Several quantiles of R at once (one CDF table)."""
    if kappa <= 0:
        from scipy.stats import f as Fd
        return [float(Fd.ppf(q, 2 * n, 2 * n)) for q in qs]
    cdf = ratio_cdf_table(n, kappa)
    cdf = cdf / cdf[-1]
    return [float(np.exp(np.interp(q, cdf, _LG))) for q in qs]


def validate_formula(rng) -> dict:
    rows = []
    for n in (1, 5, 14, 40):
        for kappa in (0.0, 0.1, 0.3, 0.6):
            g = np.sqrt(kappa)
            T = 400_000
            a = rng.standard_normal((T, n)) + 1j * rng.standard_normal((T, n))
            b = rng.standard_normal((T, n)) + 1j * rng.standard_normal((T, n))
            s = g * a + np.sqrt(1 - kappa) * b
            lr = np.log((np.abs(s) ** 2).mean(axis=1) / (np.abs(a) ** 2).mean(axis=1))
            dens = np.exp(_logpdf(_LG, n, kappa) + _LG)
            mass = float(np.trapezoid(dens, _LG))
            sd = float(lr.std(ddof=1))
            se = float(lr.var(ddof=1) * np.sqrt(2.0 / (T - 1)))            # SE of the variance (normal theory)
            cdf = ratio_cdf_table(n, kappa)
            mc_q95 = float(np.quantile(np.exp(lr), 0.95))
            rows.append({"N": n, "kappa": kappa, "draws": T, "series_var": var_lnr(n, kappa),
                         "mc_var": float(lr.var(ddof=1)), "mc_var_se": se,
                         "z": float((lr.var(ddof=1) - var_lnr(n, kappa)) / se),
                         "density_mass": mass,
                         "q95_density": float(ratio_quantile(0.95, n, kappa)), "q95_mc": mc_q95})
    return {"rows": rows,
            "max_abs_z_N_ge_5": float(max(abs(r["z"]) for r in rows if r["N"] >= 5)),
            "note_N1": "the normal-theory SE of a variance is invalid at N = 1 (ln R is heavy-tailed); excluded from the z summary",
            "max_abs_z": float(max(abs(r["z"]) for r in rows)),
            "max_density_mass_error": float(max(abs(r["density_mass"] - 1) for r in rows))}


def validate_windows(rng_seed) -> dict:
    """The rows of enl_logratio.validation, with cross-channel coherence."""
    import f2_maximum as F2M
    import enl_logratio as L
    enl = json.loads((BASE_DIR / "docs" / "enl.json").read_text(encoding="utf-8"))
    lags = (enl["lag_correlation"]["LH"]["azimuth_lines"][0], enl["lag_correlation"]["LH"]["range_samples"][0])
    rho = (float(np.sqrt(lags[0])), float(np.sqrt(lags[1])))
    rng = np.random.default_rng(rng_seed)
    rows = []
    for kappa in KAPPAS:
        g = np.sqrt(kappa)
        for n in VAL_N:
            for tex in ("off", "shape 8"):
                std, awr, kap_hat = [], [], []
                sub = np.random.default_rng(rng.integers(1 << 62))
                for _ in range(SCENES):
                    sc = np.zeros(SHAPE, dtype=complex); oc = np.zeros(SHAPE, dtype=complex)
                    i1 = np.zeros(SHAPE); i2 = np.zeros(SHAPE); xx = np.zeros(SHAPE, dtype=complex)
                    for _l in range(n):
                        wo = F2M.ar1_stationary(sub, SHAPE, *rho, 1)[0]
                        ws = F2M.ar1_stationary(sub, SHAPE, *rho, 1)[0]
                        z1 = g * wo + np.sqrt(1 - kappa) * ws
                        i1 += np.abs(z1) ** 2; i2 += np.abs(wo) ** 2; xx += z1 * np.conj(wo)
                    i1 /= n; i2 /= n; xx /= n
                    if tex != "off":
                        t = sub.gamma(8.0, 1.0 / 8.0, SHAPE)
                        i1, i2, xx = i1 * t, i2 * t, xx * t
                    lr = np.log(i1 / i2)
                    g2 = np.abs(xx) ** 2 / (i1 * i2)
                    H, W = lr.shape
                    for r0 in range(0, H - WINDOW + 1, WINDOW):
                        for c0 in range(0, W - WINDOW + 1, WINDOW):
                            w = lr[r0:r0 + WINDOW, c0:c0 + WINDOW]
                            v = float(w.var(ddof=1))
                            std.append(float(L.n_from_var(v)))
                            nh, kh = nhat_aware(v, float(g2[r0:r0 + WINDOW, c0:c0 + WINDOW].mean()))
                            awr.append(nh); kap_hat.append(kh)
                std, awr, kap_hat = np.array(std), np.array(awr), np.array(kap_hat)
                fin = np.isfinite(awr)

                def stat(x):
                    x = x[np.isfinite(x)]
                    return {"median": float(np.median(x)), "relative_bias_median": float(np.median(x) / n - 1),
                            "relative_bias_median_se": float(1.2533 * x.std(ddof=1) / np.sqrt(x.size) / n),
                            "iqr": [float(np.percentile(x, 25)), float(np.percentile(x, 75))]}
                rows.append({"true_N": n, "kappa": kappa, "texture": tex, "windows": int(std.size),
                             "standard": stat(std), "coherence_aware": stat(awr[fin]),
                             "kappa_hat_median": float(np.median(kap_hat))})
                print(f"    kappa {kappa:.2f} N {n:>3} {tex:<7}: standard bias "
                      f"{100 * rows[-1]['standard']['relative_bias_median']:+5.1f} %, aware "
                      f"{100 * rows[-1]['coherence_aware']['relative_bias_median']:+5.1f} % "
                      f"(kappa-hat {rows[-1]['kappa_hat_median']:.3f})", flush=True)
    return {"lags_intensity": list(lags), "window": WINDOW, "scenes_per_config": SCENES,
            "scene_shape": list(SHAPE), "seed": rng_seed,
            "model": "per look: SC = g wo + sqrt(1-kappa) ws, OC = wo, independent AR(1) complex fields at the "
                     "product's lags; N looks averaged per cell; texture (gamma, shape 8) common to both channels",
            "rows": rows}


def main() -> int:
    t0 = __import__("time").time()
    rng = np.random.default_rng(SEED)
    print("  formula check", flush=True)
    f = validate_formula(rng)
    print(f"    max |z| (N >= 5) {f['max_abs_z_N_ge_5']:.2f}; density mass error {f['max_density_mass_error']:.1e}", flush=True)
    print("  window rows", flush=True)
    w = validate_windows(SEED + 1)
    OUT.write_text(json.dumps({
        "schema": "lunar-ice/coherence-nhat/1", "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/coherence_nhat.py", "seed": SEED, "seed_windows": SEED + 1,
        "estimator": "N solving 2 psi_1(N) - 2 sum_k kappa^k (k-1)!/(k (N)_k) = Var(ln R), kappa from the mean "
                     "squared circular coherence: mean(g2) = kappa + (1-kappa)^2/N",
        "formula_check": f, "window_validation": w,
        "run_info": {**run_info(), "wall_s": round(__import__("time").time() - t0, 1)}}, indent=2, default=float),
        encoding="utf-8")
    print(f"  wrote {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
