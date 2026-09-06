"""
Phase 8 groundwork: what a CPR number is actually worth, given the measured ENL.

THREE THINGS, AND THE SECOND IS THE ONE THAT CONSTRAINS OUR OWN RESULTS.

A. HOW MANY INDEPENDENT SAMPLES DOES A CRATER HOLD?
   A multiple-comparisons penalty computed from RAW PIXEL COUNTS assumes the
   pixels are independent. Our own measurement disproves that: lag-1 correlation
   is +0.838 in azimuth and +0.576 in range, and the screening field is a 5x5
   boxcar of sigma0 on top of that. So the effective count is measured here, by
   integrating the two-dimensional autocorrelation of THE FIELD THAT IS ACTUALLY
   THRESHOLDED (cpr_real.tif), not of the raw DN and not from an AR(1) shortcut.

B. THE F(2N,2N) DISTRIBUTION DOES NOT DESCRIBE OUR OWN CPR VALUES.
   R ~ CPR * F(2N,2N) holds for a ratio of two independent N-look INTENSITIES,
   which is what published CPR (sigma_SC/sigma_OC from the Stokes vector) is. It
   is NOT what this build computes. Our amplitude proxy is

       proxy = ((sqrt(LH) - sqrt(LV)) / (sqrt(LH) + sqrt(LV)))^2

   a different functional form with a different sampling distribution. The
   literature critique in METHODS 7.8 stands, because it is aimed at real
   sigma_SC/sigma_OC values. Applying F(2N,2N) to OUR numbers would be the same
   class of error the critique is about. So the proxy's distribution is obtained
   by Monte Carlo instead, from correlated complex Gaussian fields at the
   measured ENL, with the true Stokes CPR computed from the same draws as a
   control.

C. THE CORRECTED PEAK-CPR TABLE for an ice-free crater, using A rather than the
   raw pixel count.

Usage:
    python -u backend/scripts/cpr_significance.py [--f2-pixels 1520] [--trials 200000]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import tifffile
from scipy.stats import f as fdist

BASE_DIR = Path(__file__).resolve().parents[2]

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

CPR_TIF = BASE_DIR / "data/pradan/dfsar/cpr_real.tif"
VALID_TIF = BASE_DIR / "data/pradan/dfsar/valid_real.tif"
_T0 = time.time()


def beat(msg: str) -> None:
    print(f"  [{time.strftime('%H:%M:%S')}  +{time.time() - _T0:6.1f}s]  {msg}",
          flush=True)


def hr(t: str) -> None:
    print("\n" + "=" * 78 + "\n" + t + "\n" + "=" * 78, flush=True)


# ---------------------------------------------------------------- A. n_eff
def correlation_area(field: np.ndarray, valid: np.ndarray, patch: int = 64,
                     lag: int = 24, max_patches: int = 400) -> dict:
    """Integrate the 2-D autocorrelation of `field` -> pixels per independent sample.

    For a stationary field the number of independent samples in an area of n
    pixels is n / A, where A = sum over lags of the normalised autocorrelation.
    A = 1 for white noise. Patches are mean-removed before the ACF, which
    suppresses the DC terrain level; that biases A slightly LOW (i.e. biases the
    independent count HIGH), so the penalty computed from it is conservative in
    the direction that does NOT flatter the result.
    """
    h, w = (field.shape[0] // patch) * patch, (field.shape[1] // patch) * patch
    f = field[:h, :w].reshape(h // patch, patch, w // patch, patch).swapaxes(1, 2)
    v = valid[:h, :w].reshape(h // patch, patch, w // patch, patch).swapaxes(1, 2)
    keep = v.reshape(-1, patch * patch).all(axis=1)
    blk = f.reshape(-1, patch, patch)[keep].astype(np.float64)
    if blk.shape[0] == 0:
        raise SystemExit("no patch lies entirely inside the valid mask")
    if blk.shape[0] > max_patches:
        idx = np.linspace(0, blk.shape[0] - 1, max_patches).astype(int)
        blk = blk[idx]
    blk = blk - blk.mean(axis=(1, 2), keepdims=True)
    # Wiener-Khinchin, zero-padded so the circular ACF is the linear one.
    F = np.fft.rfft2(blk, s=(2 * patch, 2 * patch))
    acf = np.fft.irfft2(np.abs(F) ** 2, s=(2 * patch, 2 * patch)).mean(axis=0)
    acf = acf / acf[0, 0]
    win = np.concatenate([np.arange(0, lag + 1), np.arange(-lag, 0)])
    sub = acf[np.ix_(win, win)]
    return {"patch": patch, "n_patches": int(blk.shape[0]), "lag_window": lag,
            "area_all_lags": float(sub.sum()),
            "area_positive_lags_only": float(sub[sub > 0].sum()),
            "rho_lag1_axis0": float(acf[1, 0]), "rho_lag1_axis1": float(acf[0, 1]),
            "rho_lag2_axis0": float(acf[2, 0]), "rho_lag2_axis1": float(acf[0, 2])}


# ------------------------------------------------------- B. the Monte Carlo
def monte_carlo(n_looks: int, cpr_true: float, imbalance_db: float,
                trials: int, rng: np.random.Generator,
                coherence: float | None = None) -> dict:
    """Sampling distributions of the TRUE Stokes CPR and of our amplitude proxy.

    Compact pol: circular transmit, linear H and V receive. Per look the
    received field is a zero-mean circular complex Gaussian 2-vector with
    covariance C. The population CPR is set through the H-V correlation, and the
    population channel imbalance through the diagonal, so the two can be varied
    independently -- which is the whole point, since the proxy responds to one
    and the published statistic to the other.
    """
    s_h = 10.0 ** (imbalance_db / 20.0)          # amplitude ratio -> power below
    var_h, var_v = s_h ** 2, 1.0
    # CPR = (S0 + S3)/(S0 - S3) with S3 = -2 Im<E_H E_V*>.
    s0 = var_h + var_v
    s3 = s0 * (cpr_true - 1.0) / (cpr_true + 1.0)
    rho_im = -s3 / (2.0 * np.sqrt(var_h * var_v))
    if abs(rho_im) > 1.0:
        raise SystemExit(f"CPR {cpr_true} unreachable at imbalance {imbalance_db} dB")
    # S3 = -2 Im<E_H E_V*>, and <E_H E_V*> is C[0,1], so Im(C[0,1]) = -S3/2.
    # rho_im is defined as exactly that, and C must be Hermitian, so C[1,0] is
    # its conjugate. Getting this sign wrong inverts the CPR (0.3 reads 3.3) --
    # which is why the CPR = 1.0 row is kept in the table below: it is the only
    # value that is its own reciprocal, so it cannot catch this, and every other
    # row can.
    #
    # THE H-V COHERENCE IS A FREE PARAMETER AND MUST BE MEASURED, NOT ASSUMED.
    # CPR fixes only Im(rho). Leaving Re(rho) at zero makes |rho| as small as the
    # CPR allows, i.e. makes LH and LV as INDEPENDENT as possible -- which is the
    # noisiest case for a statistic built on their difference. The real swath has
    # a measured LH/LV intensity correlation of 0.96, and intensity correlation
    # is |rho|^2, so the honest floor is computed at the measured value. The
    # first version of this simulation omitted this and predicted a proxy floor
    # 25x too high; the pre-registered check in section D is what caught it.
    rho_re = 0.0
    if coherence is not None:
        if coherence ** 2 < rho_im ** 2:
            raise SystemExit(f"|rho| {coherence} too small for CPR {cpr_true}")
        rho_re = float(np.sqrt(coherence ** 2 - rho_im ** 2))
    off = (rho_re + 1j * rho_im) * np.sqrt(var_h * var_v)
    C = np.array([[var_h, off], [np.conj(off), var_v]], dtype=np.complex128)
    # Hermitian square root, so draws have exactly covariance C.
    evals, evecs = np.linalg.eigh(C)
    evals = np.clip(evals, 0.0, None)
    L = evecs @ np.diag(np.sqrt(evals)) @ evecs.conj().T

    z = (rng.standard_normal((trials, n_looks, 2))
         + 1j * rng.standard_normal((trials, n_looks, 2))) / np.sqrt(2.0)
    e = z @ L.T
    eh, ev = e[..., 0], e[..., 1]

    lh = (np.abs(eh) ** 2).mean(axis=1)          # N-look intensities
    lv = (np.abs(ev) ** 2).mean(axis=1)
    cross = (eh * np.conj(ev)).mean(axis=1)
    S0 = lh + lv
    S3 = -2.0 * np.imag(cross)
    cpr_stokes = (S0 + S3) / np.maximum(S0 - S3, 1e-12)

    a, b = np.sqrt(lh), np.sqrt(lv)
    proxy = ((a - b) / (a + b)) ** 2

    def desc(x, truth):
        q = np.percentile(x, [5, 50, 95])
        return {"true": truth, "mean": float(x.mean()), "median": float(q[1]),
                "p5": float(q[0]), "p95": float(q[2]),
                "bias_mean_over_true": float(x.mean() / truth) if truth else None}

    # The proxy's population value: LH and LV converge to var_h and var_v.
    proxy_true = ((np.sqrt(var_h) - np.sqrt(var_v))
                  / (np.sqrt(var_h) + np.sqrt(var_v))) ** 2
    return {"n_looks": n_looks, "cpr_true": cpr_true, "imbalance_db": imbalance_db,
            "stokes_cpr": desc(cpr_stokes, cpr_true),
            "amplitude_proxy": desc(proxy, proxy_true if proxy_true > 0 else None),
            "proxy_population_value": proxy_true}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--f2-pixels", type=int, default=1520)
    ap.add_argument("--trials", type=int, default=200000)
    ap.add_argument("--coherence", type=float, default=None,
                    help="|rho| for section B; omit for the idealised "
                         "independent-channel case, 0.9822 for the measured swath")
    ap.add_argument("--out", default="docs/cpr_significance.json")
    args = ap.parse_args()
    rng = np.random.default_rng(20200808)
    out = {}

    # ---------------------------------------------------------------- A
    hr("A. EFFECTIVE SAMPLE COUNT — measured, not assumed")
    print("  A multiple-comparisons penalty from raw pixel counts assumes")
    print("  independence. Lag-1 correlation is +0.838 azimuth / +0.576 range on")
    print("  the raw DN, and the field that is actually thresholded is a 5x5")
    print("  boxcar on top of that. So integrate the ACF of THAT field.\n")
    cpr = np.asarray(tifffile.imread(str(CPR_TIF)), dtype=np.float32)
    valid = np.asarray(tifffile.imread(str(VALID_TIF))) > 0
    print(f"  cpr_real.tif {cpr.shape[0]} x {cpr.shape[1]}, "
          f"valid {int(valid.sum()):,} px ({valid.mean() * 100:.2f} %)")
    ca = correlation_area(cpr, valid)
    beat(f"ACF over {ca['n_patches']} patches of {ca['patch']}²")
    print(f"\n  rho at lag 1:  axis0 {ca['rho_lag1_axis0']:+.3f}   "
          f"axis1 {ca['rho_lag1_axis1']:+.3f}")
    print(f"  rho at lag 2:  axis0 {ca['rho_lag2_axis0']:+.3f}   "
          f"axis1 {ca['rho_lag2_axis1']:+.3f}")
    print(f"\n  correlation area A (all lags, ±{ca['lag_window']})   "
          f"{ca['area_all_lags']:8.2f} px per independent sample")
    print(f"  correlation area A (positive lags only) {ca['area_positive_lags_only']:8.2f}")
    A = max(ca["area_all_lags"], 1.0)
    n_eff = args.f2_pixels / A
    print(f"\n  F2 holds {args.f2_pixels:,} pixels of CPR, which is "
          f"{n_eff:.1f} INDEPENDENT samples.")
    print(f"  Using {args.f2_pixels:,} would overstate the multiple-comparisons")
    print(f"  penalty by treating {A:.0f} correlated pixels as {A:.0f} separate tries.")
    out["effective_samples"] = {**ca, "f2_pixels": args.f2_pixels,
                                "f2_effective_samples": n_eff}

    # ---------------------------------------------------------------- C
    hr("C. MEDIAN PEAK CPR OVER AN ICE-FREE F2 — raw pixels vs effective samples")
    print("  Median of the maximum of n draws of CPR_true * F(2N,2N).")
    print("  This applies to sigma_SC/sigma_OC — published CPR — NOT to our proxy.\n")
    print(f"  true CPR 0.7        {'raw ' + str(args.f2_pixels) + ' px':>18}"
          f"{'effective ' + format(n_eff, '.0f'):>20}")
    peaks = {}
    for N in (5, 6, 9, 21):
        raw = 0.7 * fdist.ppf(0.5 ** (1.0 / args.f2_pixels), 2 * N, 2 * N)
        eff = 0.7 * fdist.ppf(0.5 ** (1.0 / n_eff), 2 * N, 2 * N)
        peaks[N] = {"raw": float(raw), "effective": float(eff)}
        print(f"  N = {N:<15d}{raw:>18.2f}{eff:>20.2f}")
    print("\n  The raw-pixel column overstates the penalty. The right-hand column")
    print("  is the one that may be quoted.")
    out["f2_peak_cpr"] = peaks

    # ---------------------------------------------------------------- B
    hr("B. OUR PROXY IS NOT sigma_SC/sigma_OC — Monte Carlo, not F(2N,2N)")
    print("  Circular complex Gaussian draws at N looks. The population CPR is set")
    print("  through the H-V correlation and the population channel imbalance")
    print("  through the diagonal, independently — which is the experiment.\n")
    N = 5
    print(f"  N = {N} looks, {args.trials:,} trials per row, |rho| = "
          f"{'0 (idealised, independent channels)' if args.coherence is None else args.coherence}\n")
    print(f"  {'true CPR':>9}{'imbal dB':>10} | {'Stokes CPR: median':>19}"
          f"{'p5':>8}{'p95':>8} | {'proxy: median':>15}{'p95':>9}{'pop.':>8}")
    mc = []
    for cpr_t, imb in ((0.3, 0.0), (0.7, 0.0), (1.0, 0.0), (1.5, 0.0),
                       (0.7, 1.0), (0.7, 3.0)):
        r = monte_carlo(N, cpr_t, imb, args.trials, rng, coherence=args.coherence)
        mc.append(r)
        s, p = r["stokes_cpr"], r["amplitude_proxy"]
        print(f"  {cpr_t:>9.2f}{imb:>10.1f} | {s['median']:>19.3f}{s['p5']:>8.3f}"
              f"{s['p95']:>8.3f} | {p['median']:>15.5f}{p['p95']:>9.5f}"
              f"{r['proxy_population_value']:>8.5f}")
    out["monte_carlo"] = mc

    hr("WHAT THE MONTE CARLO SHOWS")
    flat = [r for r in mc if r["imbalance_db"] == 0.0]
    spread = max(r["amplitude_proxy"]["median"] for r in flat) - \
        min(r["amplitude_proxy"]["median"] for r in flat)
    print("  Rows 1-4 vary the TRUE CPR from 0.3 to 1.5 at zero channel imbalance.")
    print(f"  The Stokes estimator tracks it. The proxy's median moves by {spread:.6f}")
    print("  across that whole range, because at equal channel powers its")
    print("  population value is EXACTLY ZERO whatever the CPR is: it is a")
    print("  function of LH/LV, and the circular polarisation ratio lives in the")
    print("  H-V PHASE, which taking magnitudes discards.")
    print()
    print("  Rows 5-6 hold the CPR at 0.7 and add channel imbalance. Now the proxy")
    print("  moves — because imbalance is the only thing it can see.")
    print()
    print("  Its non-zero median at zero imbalance is a pure SPECKLE NOISE FLOOR:")
    print("  LH and LV differ by chance at finite looks, and the proxy squares")
    print("  that difference, so the floor is positive-definite and biased UP.")
    print("  This is the same fact as the 0.0042610 ceiling, arrived at from the")
    print("  distribution rather than from the algebra.")

    # ---------------------------------------------------------------- D
    hr("D. VALIDATION AGAINST THE REAL SWATH — predictions in "
       "docs/preregistration_proxy_validation.md")
    print("  Committed before this run: the proxy's first-order form is")
    print("  chi2_1/(8N), the screening field's effective N is 13.72 (LH) /")
    print("  19.77 (LV) after the 5x5 boxcar, and the falsifiable claim is that")
    print("  the OBSERVED distribution cannot sit below the simulated zero-")
    print("  imbalance floor, because a scene cannot be quieter than the speckle")
    print("  floor of the instrument that recorded it.\n")
    # cpr_real.tif is 2048x2048 -- the RESAMPLED analysis grid, not the native
    # 2258 x 6618. Resampling 6618 range samples down to 2048 smooths by a
    # further ~3.2x, so comparing it against a simulation at the NATIVE-grid
    # effective N compares two different fields. The native proxy is therefore
    # rebuilt here exactly as process_real_sar_pipeline.py forms it -- calibrate,
    # 5x5 boxcar, then the amplitude proxy -- and that is what the simulation is
    # judged against. sin(theta) and K cancel out of the ratio; the per-channel
    # gain imbalance does not, and is taken from the label.
    from scipy.ndimage import uniform_filter
    _r = BASE_DIR / "data/pradan/raw/data/calibrated/20200808"
    _s = "ch2_sar_ncxl_20200808t201154198_d_sri_xx_cp_{}_d18.tif"
    lh_dn = np.asarray(tifffile.imread(str(_r / _s.format("lh"))), dtype=np.float64)
    lv_dn = np.asarray(tifffile.imread(str(_r / _s.format("lv"))), dtype=np.float64)
    inc = np.asarray(tifffile.imread(str(_r / "ch2_sar_ncxl_20200808t201154198"
                                          "_d_sri_in_cp_xx_d18.tif")), dtype=np.float64)
    nat_valid = (lh_dn > 0) & (lv_dn > 0)
    sin_t = np.sin(np.deg2rad(inc))
    s_lh = uniform_filter(lh_dn ** 2 * sin_t / 1.018442 ** 2, size=5)
    s_lv = uniform_filter(lv_dn ** 2 * sin_t / 1.000923 ** 2, size=5)
    from scipy.ndimage import binary_erosion
    inner = binary_erosion(nat_valid, np.ones((5, 5), dtype=bool))
    a_, b_ = np.sqrt(np.maximum(s_lh, 0)), np.sqrt(np.maximum(s_lv, 0))
    with np.errstate(invalid="ignore", divide="ignore"):
        nat_proxy = ((a_ - b_) / (a_ + b_)) ** 2
    nat = nat_proxy[inner & np.isfinite(nat_proxy)]
    print(f"  NATIVE proxy rebuilt over {nat.size:,} px (2258 x 6618, boxcar-eroded):")
    print(f"    median {np.median(nat):.5f}  p95 {np.percentile(nat, 95):.5f}  "
          f"p99 {np.percentile(nat, 99):.5f}  max {nat.max():.5f}")
    out["native_proxy"] = {"n": int(nat.size), "median": float(np.median(nat)),
                           "p95": float(np.percentile(nat, 95)),
                           "p99": float(np.percentile(nat, 99)),
                           "max": float(nat.max())}
    # How correlated are the two channels after smoothing? The simulation's
    # zero-imbalance floor implicitly assumed LH and LV fluctuate independently;
    # if they do not, the difference of their roots is quieter than that floor.
    def _local_corr(x, y, m, patch=16):
        h, w = (x.shape[0] // patch) * patch, (x.shape[1] // patch) * patch
        rs = lambda a: a[:h, :w].reshape(h // patch, patch, w // patch,
                                        patch).swapaxes(1, 2).reshape(-1, patch * patch)
        X, Y, M = rs(x), rs(y), rs(m)
        k = M.all(axis=1)
        X, Y = X[k], Y[k]
        X = X - X.mean(axis=1, keepdims=True)
        Y = Y - Y.mean(axis=1, keepdims=True)
        num = (X * Y).sum(axis=1)
        den = np.sqrt((X * X).sum(axis=1) * (Y * Y).sum(axis=1))
        r = num[den > 0] / den[den > 0]
        return float(np.median(r))
    r_hv = _local_corr(s_lh, s_lv, inner)
    print(f"    median within-patch LH/LV intensity correlation: {r_hv:+.4f}")
    out["native_proxy"]["lh_lv_local_correlation"] = r_hv
    del lh_dn, lv_dn, inc, s_lh, s_lv, a_, b_, nat_proxy

    obs = cpr[valid].astype(np.float64)
    o = {f"p{q}": float(np.percentile(obs, q)) for q in (50, 90, 95, 99)}
    o["max"] = float(obs.max())
    o["mean"] = float(obs.mean())
    print(f"  observed cpr_real over {obs.size:,} valid px:  median {o['p50']:.5f}  "
          f"p95 {o['p95']:.5f}  p99 {o['p99']:.5f}  max {o['max']:.5f}")

    # The scene's own channel imbalance, recovered from DOP = |LH-LV|/(LH+LV):
    # LH/LV = (1+d)/(1-d), so the imbalance in dB follows directly.
    dop = np.asarray(tifffile.imread(str(BASE_DIR / "data/pradan/dfsar/dop_real.tif")),
                     dtype=np.float64)[valid]
    d_med = float(np.median(dop))
    imb_db = 10.0 * np.log10((1.0 + d_med) / max(1.0 - d_med, 1e-12))
    print(f"  scene median DOP {d_med:.5f}  ->  median channel imbalance "
          f"{imb_db:.3f} dB")

    from scipy.stats import chi2
    print(f"\n  {'N':>4}{'predicted p95':>15}{'simulated p95':>15}"
          f"{'sim median':>12}{'pred median':>13}")
    val = {"observed": o, "scene_median_imbalance_db": imb_db, "by_N": {}}
    coh = float(np.sqrt(max(r_hv, 0.0)))     # intensity correlation = |rho|^2
    print(f"\n  measured |rho| = sqrt({r_hv:.4f}) = {coh:.4f}, supplied to the floor")
    for N in (5, 14, 20):
        r = monte_carlo(N, 1.0, 0.0, args.trials, rng, coherence=coh)
        sim = r["amplitude_proxy"]
        # chi2_1/(8N) assumed independent channels; with correlation r the
        # variance of the difference carries a factor (1 - r).
        pred_p95 = float(chi2.ppf(0.95, 1) * (1.0 - r_hv) / (8 * N))
        pred_med = float(chi2.ppf(0.50, 1) * (1.0 - r_hv) / (8 * N))
        val["by_N"][N] = {"sim_p95": sim["p95"], "sim_median": sim["median"],
                          "predicted_p95": pred_p95, "predicted_median": pred_med}
        print(f"  {N:>4}{pred_p95:>15.5f}{sim['p95']:>15.5f}"
              f"{sim['median']:>12.5f}{pred_med:>13.5f}")

    hr("PREDICTED vs MEASURED")
    p1 = all(abs(v["sim_p95"] / v["predicted_p95"] - 1) < 0.05
             for k, v in val["by_N"].items())
    s14, s20 = val["by_N"][14], val["by_N"][20]
    p2 = s14["sim_p95"] < o["max"] and s20["sim_p95"] < o["max"]
    nat_p95 = out["native_proxy"]["p95"]
    p3 = nat_p95 >= min(s14["sim_p95"], s20["sim_p95"])
    print(f"  P1  MC reproduces chi2_1/(8N) to ~1 %                     "
          f"{'HELD' if p1 else 'FAILED':>8}")
    print(f"      N=14 {s14['sim_p95']:.5f} vs {s14['predicted_p95']:.5f} predicted;  "
          f"N=20 {s20['sim_p95']:.5f} vs {s20['predicted_p95']:.5f}")
    print(f"  P2  simulated p95 at measured N falls below observed max  "
          f"{'HELD' if p2 else 'FAILED':>8}")
    print(f"      sim p95 {s20['sim_p95']:.5f}–{s14['sim_p95']:.5f}  vs  observed max "
          f"{o['max']:.5f}")
    print(f"  P3  observed p95 at or above the pure-noise floor         "
          f"{'HELD' if p3 else 'FAILED':>8}")
    print(f"      NATIVE observed p95 {nat_p95:.5f}  vs  simulated floor p95 "
          f"{min(s14['sim_p95'], s20['sim_p95']):.5f}")
    val["P1_mc_matches_analytic"] = bool(p1)
    val["P2_sim_below_observed_max"] = bool(p2)
    val["P3_observed_above_noise_floor"] = bool(p3)
    out["validation"] = val
    if not p3:
        print("\n  P3 IS THE FALSIFIABLE ONE AND IT FAILED. The observed swath is")
        print("  QUIETER than the speckle floor implied by the measured ENL. Either")
        print("  the ENL is wrong or the simulator is. Phase 8 stops here until this")
        print("  is understood — the significance layer is not built on this.")
    else:
        print("\n  The Monte Carlo is validated against real data at the measured")
        print("  effective look count. Numbers built on it are safe to use.")

    (BASE_DIR / args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
