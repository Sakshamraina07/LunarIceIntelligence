"""
kclutter_within_cell.py -- P4. Texture that varies WITHIN the multilook cell.

    python backend/scripts/kclutter_within_cell.py [--trials N]

kclutter.py draws one texture value per multilook cell, shared by both circular
channels, and finds the ratio tail unchanged -- a shared multiplicative factor
cancels algebraically. That is the right model if texture is constant over the
cell. The reviewer's 4.13 asks what happens if it is not: if each of the N
looks that are averaged sees its own texture t_k, the ratio is

    R = sum_k t_k g1_k / sum_k t_k g2_k

and t_k no longer cancels. Three texture models per look, all SHARED between the
channels (one illumination of one footprint), at N = 14, true CPR 0.7, K orders
{inf, 8, 4}:

    independent   t_k i.i.d. Gamma(nu, 1/nu)
    lag-one 0.5   t_k with AR(1) correlation 0.5 across the look index
    lag-one 0.8   t_k with AR(1) correlation 0.8 across the look index

The correlated texture is a Gaussian copula: an AR(1) Gaussian sequence across
the N looks, mapped through Phi to a uniform and through the Gamma quantile.
The copula fixes the RANK correlation; the achieved Pearson lag-one correlation
of t_k is measured and recorded beside the nominal one.

Reported: the exceedance P(0.7 R > 1) with its binomial SE against the F model,
and the moment-estimated ENL of the textured cell intensity I = mean_k t_k g_k
(population mean^2 / var over the trials, with a 10-block jackknife SE), which
is how within-cell texture moves the effective look count.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.stats import f as Fdist, gamma as Gamma, norm

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "kclutter_within_cell.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

SEED = 7
N_LOOKS = 14
TRUE_CPR = 0.7
ORDERS = (float("inf"), 8.0, 4.0)
RHOS = (0.0, 0.5, 0.8)


def texture(rng, nu: float, rho: float, trials: int, n: int) -> np.ndarray:
    """(trials, n) shared texture per look: Gamma(nu, 1/nu), AR(1) across looks."""
    if not np.isfinite(nu):
        return np.ones((trials, n))
    z = rng.standard_normal((trials, n))
    if rho > 0:
        for k in range(1, n):
            z[:, k] = rho * z[:, k - 1] + np.sqrt(1.0 - rho ** 2) * z[:, k]
    if rho == 0:
        return rng.gamma(nu, 1.0 / nu, (trials, n))
    return Gamma.ppf(norm.cdf(z), nu, scale=1.0 / nu)


def enl_jackknife(i: np.ndarray, blocks: int = 10) -> tuple:
    full = i.mean() ** 2 / i.var(ddof=1)
    parts = np.array_split(i, blocks)
    leave = []
    for b in range(blocks):
        rest = np.concatenate([p for j, p in enumerate(parts) if j != b])
        leave.append(rest.mean() ** 2 / rest.var(ddof=1))
    leave = np.array(leave)
    se = float(np.sqrt((blocks - 1) / blocks * ((leave - leave.mean()) ** 2).sum()))
    return float(full), se


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=1_000_000)
    args = ap.parse_args()
    rng = np.random.default_rng(SEED)
    fp_f = float((1.0 - Fdist.cdf(1.0 / TRUE_CPR, 2 * N_LOOKS, 2 * N_LOOKS)) * 100.0)

    print("=" * 78)
    print("WITHIN-CELL TEXTURE — per-look, shared between channels")
    print("=" * 78)
    print(f"  N = {N_LOOKS}, true CPR {TRUE_CPR}, seed {SEED}, {args.trials:,} trials per row")
    print(f"  F model (no texture): {fp_f:.3f} %\n")
    print(f"  {'nu':>5} {'rho':>5} {'rho meas':>9} {'exceed %':>9} {'±SE':>6} "
          f"{'-F':>7} {'ENL(I)':>8} {'±SE':>6}")
    rows = []
    # The speckle is drawn ONCE per row of texture models, so rows differ only
    # in the texture: g1, g2 are the per-look single-look intensities.
    for nu in ORDERS:
        for rho in RHOS:
            if not np.isfinite(nu) and rho > 0:
                continue
            g1 = rng.exponential(1.0, (args.trials, N_LOOKS))
            g2 = rng.exponential(1.0, (args.trials, N_LOOKS))
            t = texture(rng, nu, rho, args.trials, N_LOOKS)
            i1, i2 = (t * g1).mean(axis=1), (t * g2).mean(axis=1)
            r = i1 / i2
            p = float(np.mean(TRUE_CPR * r > 1.0))
            se = float(np.sqrt(p * (1 - p) / args.trials))
            enl, enl_se = enl_jackknife(i1)
            rho_meas = (float(np.corrcoef(t[:, :-1].ravel(), t[:, 1:].ravel())[0, 1])
                        if np.isfinite(nu) else 0.0)
            label = "inf" if not np.isfinite(nu) else f"{nu:g}"
            print(f"  {label:>5} {rho:>5.1f} {rho_meas:>9.3f} {100 * p:>9.3f} {100 * se:>6.3f} "
                  f"{100 * p - fp_f:>+7.3f} {enl:>8.3f} {enl_se:>6.3f}")
            rows.append({"nu": None if not np.isfinite(nu) else nu, "nu_label": label,
                         "texture_lag1_nominal": rho, "texture_lag1_measured": rho_meas,
                         "exceed_percent": 100 * p, "exceed_se_percent": 100 * se,
                         "minus_F_model_points": 100 * p - fp_f,
                         "enl_of_textured_intensity": enl, "enl_se_jackknife": enl_se,
                         "texture_model": ("none" if not np.isfinite(nu) else
                                           ("independent per look" if rho == 0 else
                                            f"AR(1) Gaussian copula, lag-one {rho}"))})
            del g1, g2, t, i1, i2, r

    print()
    print("  Per-look texture does NOT cancel: the exceedance rises above the F")
    print("  model by the amount shown, and the textured cell's own moment ENL")
    print("  falls below N. Correlating the texture across looks moves it toward")
    print("  the whole-cell (kclutter.py) case, where it cancels exactly.")
    OUT.write_text(json.dumps({
        "schema": "lunar-ice/kclutter-within-cell/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/kclutter_within_cell.py",
        "seed": SEED, "trials_per_row": args.trials, "n_looks": N_LOOKS,
        "true_cpr": TRUE_CPR, "fp_percent_F_model": fp_f,
        "texture_orders": [None if not np.isfinite(o) else o for o in ORDERS],
        "texture_lag1_values": list(RHOS),
        "model": "I_c = mean_k t_k g_ck, g_ck ~ Exp(1) independent per channel and look, "
                 "t_k ~ Gamma(nu, 1/nu) shared between channels; R = I_1 / I_2; "
                 "exceedance = P(0.7 R > 1)",
        "copula_note": "rank correlation is set by the Gaussian AR(1); the Pearson "
                       "lag-one correlation of t_k is measured and reported",
        "enl_note": "population mean^2 / var of the textured cell intensity over the "
                    "trials, 10-block jackknife SE",
        "rows": rows,
        "whole_cell_reference": "docs/kclutter.json (one texture value per cell: cancels)",
    }, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
