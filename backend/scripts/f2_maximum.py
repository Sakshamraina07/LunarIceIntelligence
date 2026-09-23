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

A SECOND GENERATIVE MODEL (third review, M13, 2026-09-23)
-----------------------------------------------------------
Correlated F draws put the correlation on the CPR field directly. The reviewer
asks for the field the CPR is actually formed from: correlated COMPLEX
circular-Gaussian looks in each circular channel, averaged to intensities,
passed through the production 5 x 5 boxcar -- with the zero-fill outside the
amplitude mask that the production boxcar sees -- and only then divided. So
`complex_field` below:

  * draws L equal-weight looks per channel, each a separable AR(1) complex
    field whose intensity lag-one correlations are the DELIVERED product's
    (enl.json::lag_correlation.LH), as enl_benchmark.speckle_field does;
  * sets both channels to zero outside F2's amplitude mask, boxcars each,
    and forms CPR = c * box(SC) / box(OC) over the 260 amplitude pixels;
  * chooses L from {5, 6} by which puts the boxcar'd field's patch-mode ENL
    nearer the measured 13.72 on a large calibration field, and records both;
  * reports, per trial: the maximum over the 260 pixels, the suprathreshold
    area above 1.00 and above the one-sided 95 % critical value, and the
    largest 4-connected cluster above the critical value; and the crater-level
    FAMILY-WISE error P(max > crit) at true CPR 1.00 (the test's null) and 0.7.

The correlated-F rows are kept for comparison and gain the same area, cluster
and family-wise figures, computed from the same draws.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import tifffile
from scipy.ndimage import label as cc_label, uniform_filter
from scipy.optimize import minimize_scalar
from scipy.signal import lfilter
from scipy.stats import f as Fdist, gamma as Gamma, norm

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402

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
#: M13 complex-field null
SEED_COMPLEX = 20260926
ENL_JSON = BASE_DIR / "docs" / "enl.json"
OPERATING_N = 13.72
BOXCAR = 5
BURN = 64
LOOK_CHOICES = (2, 3, 4, 5, 6)
CAL_FIELDS = 3

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


def crit95(n: float) -> float:
    return float(Fdist.ppf(0.95, 2 * n, 2 * n))


def spatial_stats(fields: np.ndarray, mask: np.ndarray, crit: float) -> dict:
    """Per-trial maximum, suprathreshold areas and largest 4-connected cluster
    above crit, over the pixels of `mask`, for a (trials, H, W) CPR stack."""
    t = fields.shape[0]
    vals = fields[:, mask]
    mx = vals.max(axis=1)
    area1 = (vals > THRESHOLD).sum(axis=1)
    areac = (vals > crit).sum(axis=1)
    clus = np.zeros(t, dtype=np.int64)
    for k in range(t):
        lab, n = cc_label((fields[k] > crit) & mask)
        if n:
            clus[k] = np.bincount(lab.ravel())[1:].max()
    return {"max": mx, "area_gt_1": area1, "area_gt_crit": areac, "largest_cluster": clus}


def describe(st: dict, crit: float) -> dict:
    mx = st["max"]
    fwe = float((mx > crit).mean())
    return {"crit_95": crit,
            "max": {"median": float(np.median(mx)), "p95": float(np.percentile(mx, 95))},
            "fwe_p_max_gt_crit": fwe,
            "fwe_se": float(np.sqrt(fwe * (1 - fwe) / mx.size)),
            "area_gt_1": {"mean": float(st["area_gt_1"].mean()),
                          "se": float(st["area_gt_1"].std(ddof=1) / np.sqrt(mx.size)),
                          "p95": float(np.percentile(st["area_gt_1"], 95))},
            "area_gt_crit": {"mean": float(st["area_gt_crit"].mean()),
                             "se": float(st["area_gt_crit"].std(ddof=1) / np.sqrt(mx.size)),
                             "p95": float(np.percentile(st["area_gt_crit"], 95))},
            "largest_cluster_gt_crit": {
                "mean": float(st["largest_cluster"].mean()),
                "p95": float(np.percentile(st["largest_cluster"], 95)),
                "p_at_least_5px": float((st["largest_cluster"] >= 5).mean()),
                "max": int(st["largest_cluster"].max())},
            "n_trials": int(mx.size)}


def complex_looks(rng, n_looks: int, shape, rho_f_az: float, rho_f_rg: float,
                  batch: int) -> np.ndarray:
    """(batch, H, W) mean over n_looks of |AR(1) complex field|^2, unit mean."""
    H, W = shape
    acc = np.zeros((batch, H, W))
    for _ in range(n_looks):
        w = (rng.standard_normal((batch, H + BURN, W + BURN))
             + 1j * rng.standard_normal((batch, H + BURN, W + BURN))) / np.sqrt(2.0)
        x = lfilter([np.sqrt(1 - rho_f_az ** 2)], [1.0, -rho_f_az], w, axis=1)
        x = lfilter([np.sqrt(1 - rho_f_rg ** 2)], [1.0, -rho_f_rg], x, axis=2)
        acc += np.abs(x[:, BURN:, BURN:]) ** 2
    return acc / n_looks


def calibrate_looks(rng, rho_f_az, rho_f_rg) -> dict:
    """Which L puts the boxcar'd field's patch-mode ENL nearest 13.72, measured
    with the production estimator, mean of CAL_FIELDS 1024 x 512 fields per L.

    WHY THE BOXCAR'D ENL AND NOT THE RAW ONE. CPR is formed after the boxcar,
    so the operating point of the tail is the smoothed field's ENL. A separable
    AR(1) field matched at lag one cannot reproduce BOTH the product's raw ENL
    (5.83) and its boxcar'd ENL (13.72): its boxcar gain is about 4 against the
    product's 2.35 (the product's residual terrain structure survives the
    boxcar; pure speckle does not). The first version offered only L = 5, 6,
    whose boxcar'd ENLs are 21-24 -- a null at the wrong operating point, which
    lowered every maximum. It is matched here where the CPR is formed, and the
    raw-ENL mismatch is recorded beside it."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "measure_enl", Path(__file__).resolve().parent / "measure_enl.py")
    ME = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ME)
    out = {}
    for L in LOOK_CHOICES:
        raws, boxes = [], []
        for _ in range(CAL_FIELDS):
            i = complex_looks(rng, L, (1024, 512), rho_f_az, rho_f_rg, 1)[0]
            ones = np.ones_like(i, dtype=bool)
            raws.append(ME.mode_of(ME.patch_ratios(i, ones, 16)))
            boxes.append(ME.mode_of(ME.patch_ratios(uniform_filter(i, BOXCAR), ones, 16)))
        out[str(L)] = {"raw_mode_enl": float(np.mean(raws)), "boxcar_mode_enl": float(np.mean(boxes)),
                       "boxcar_mode_enl_fields": [float(b) for b in boxes],
                       "boxcar_gain": float(np.mean(boxes) / np.mean(raws))}
    out["chosen"] = int(min(LOOK_CHOICES, key=lambda L: abs(out[str(L)]["boxcar_mode_enl"]
                                                          - OPERATING_N)))
    out["target"] = OPERATING_N
    out["matched_on"] = "the boxcar'd field's patch-mode ENL (where CPR is formed)"
    out["product_for_comparison"] = {"raw_mode_enl": 5.83, "boxcar_mode_enl": 13.72,
                                     "boxcar_gain": 2.35}
    out["first_version"] = ("offered L = 5, 6 only; boxcar'd ENL 21-24, a null at "
                            "the wrong operating point; superseded 2026-09-23")
    return out


def complex_field(box_amp: np.ndarray, trials: int) -> dict:
    """M13: the spatial null from correlated complex circular fields."""
    rng = np.random.default_rng(SEED_COMPLEX)
    lc = json.loads(ENL_JSON.read_text(encoding="utf-8"))["lag_correlation"]["LH"]
    rho_i = (float(lc["azimuth_lines"][0]), float(lc["range_samples"][0]))
    rho_f = (np.sqrt(rho_i[0]), np.sqrt(rho_i[1]))
    cal = calibrate_looks(rng, *rho_f)
    L = cal["chosen"]
    crit = crit95(OPERATING_N)
    H, W = box_amp.shape
    out = {"model": ("L equal-weight looks per circular channel, each a separable "
                     "AR(1) circular complex Gaussian field; intensity lag-one "
                     "correlations = the delivered LH product's; channels "
                     "independent (the independent-channel null); both set to "
                     "zero outside F2's amplitude mask, 5x5 boxcar, then "
                     "CPR = c box(SC) / box(OC)"),
           "intensity_lag1_target": {"azimuth": rho_i[0], "range": rho_i[1]},
           "look_calibration": cal, "looks": L, "operating_N": OPERATING_N,
           "crit_95": crit, "seed": SEED_COMPLEX, "trials": trials,
           "box_shape": [H, W], "amplitude_pixels": int(box_amp.sum())}
    batch = 100
    for c in (1.0, TRUE_CPR):
        stacks = []
        for _ in range(0, trials, batch):
            sc = complex_looks(rng, L, (H, W), *rho_f, batch) * c
            oc = complex_looks(rng, L, (H, W), *rho_f, batch)
            sc[:, ~box_amp] = 0.0
            oc[:, ~box_amp] = 0.0
            bs = uniform_filter(sc, size=(1, BOXCAR, BOXCAR), mode="constant")
            bo = uniform_filter(oc, size=(1, BOXCAR, BOXCAR), mode="constant")
            with np.errstate(divide="ignore", invalid="ignore"):
                cpr = np.where(bo > 0, bs / bo, 0.0)
            stacks.append(cpr)
        st = spatial_stats(np.concatenate(stacks), box_amp, crit)
        d = describe(st, crit)
        out[f"true_cpr_{c:g}".replace(".", "p")] = d
        print(f"  complex field, L = {L}, true CPR {c}: max median {d['max']['median']:.3f} "
              f"p95 {d['max']['p95']:.3f}; FWE P(max > {crit:.3f}) = {d['fwe_p_max_gt_crit']:.4f} "
              f"+/- {d['fwe_se']:.4f}; area > crit {d['area_gt_crit']['mean']:.2f}; "
              f"largest cluster p95 {d['largest_cluster_gt_crit']['p95']:.0f} px", flush=True)
    return out


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
        crit_n = crit95(N)
        sp = {"max": [], "area_gt_1": [], "area_gt_crit": [], "largest_cluster": []}
        B = 1000
        for _ in range(0, args.trials, B):
            zx = (L @ rng.standard_normal((n_disc, B))).T
            zy = (L @ rng.standard_normal((n_disc, B))).T
            cpr = TRUE_CPR * gamma_field(N, zx) / gamma_field(N, zy)
            mx_amp.append(cpr[:, amp_idx].max(axis=1))
            mx_disc.append(cpr.max(axis=1))
            cnt.append((cpr[:, amp_idx] > THRESHOLD).sum(axis=1))
            # the same draws laid back on the disc's box, for area and cluster
            box = np.zeros((cpr.shape[0],) + disc.shape)
            box[:, disc] = cpr
            s_ = spatial_stats(box, amp, crit_n)
            for k_ in sp:
                sp[k_].append(s_[k_])
        mx_amp, mx_disc, cnt = map(np.concatenate, (mx_amp, mx_disc, cnt))
        sp = {k_: np.concatenate(v_) for k_, v_ in sp.items()}
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

        spd = describe(sp, crit_n)
        r = {"n_looks": N,
             "correlated_max_over_amplitude_pixels": {
                 **summarise(mx_amp, rng),
                 # crater-level family-wise error at this N's own critical value
                 "crit_95": crit_n,
                 "p_exceeds_crit": spd["fwe_p_max_gt_crit"],
                 "p_exceeds_crit_se": spd["fwe_se"]},
             "correlated_spatial": spd,
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

    print("\n  M13 — the complex-field null over the same 260 pixels")
    cf = complex_field(amp, args.trials)

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
        "complex_field": cf,
        "run_info": run_info(),
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
