"""
complex_grid.py -- three measurements on the complex product's own grid.
(v14 final pass: B4 spectral ceiling, B5 correlation area, and the SC / OC lag
correlations B2(c) needs)

    python backend/scripts/complex_grid.py

B4. THE SPECTRAL CEILING ON N FOR ONE COMPLEX-PRODUCT CELL
    A cell of the complex product is the equal-weight intensity average of
    21 consecutive azimuth samples (build_coherency), then a 5 x 5 boxcar on
    that grid: 105 consecutive azimuth lines by 5 range samples, all equal
    weight. For circular-Gaussian samples with complex covariance C, the
    equal-weight intensity average has ENL (tr C)^2 / tr(C^2) = the
    participation ratio (sum lambda)^2 / sum lambda^2 of C. C is built from the
    window's MEASURED 2-D autocovariance (the inverse FFT of the 2-D power
    spectrum, zero-padded so it is the linear, not circular, ACF, and divided
    by the overlap count), in the nine windows mechanism_spec.py uses, and
    its eigenvalues are taken explicitly (525 x 525). Speckle alone cannot
    carry more looks than this: texture and CPR variation only lower the
    count an estimator reads. 21 x 1 reproduces mechanism_spec's 7.13 as a
    check. LH is the channel mechanism_spec measured; LV and the two circular
    channels (physical sign) are reported beside it.

B5. THE CORRELATION AREA ON THE COMPLEX GRID
    A = 61.42 px was measured on the DELIVERED screening field (the boxcar'd
    amplitude proxy, 25 m grid). decision_rule.py's W16 window applied it to
    31 x 31 windows of the COMPLEX grid. Here A is measured where the window
    is applied: the Stokes CPR (physical sign) after the boxcar, over the 109
    homogeneous 64 x 64 blocks (lowest 10 % CV of S0, the blocks of
    stokes_from_slc.py's tail calibration), with cpr_significance.py's
    estimator (block mean removed, zero-padded Wiener-Khinchin ACF, all lags
    within +/-24 summed). Median and IQR over blocks, and the block-pooled ACF.

B2(c). SC AND OC LAG CORRELATIONS
    measure_enl.lag_correlation (16-px patches, patch mean removed: the
    estimator behind enl.json::lag_correlation.LH) on the SC and OC
    intensities of the complex product BEFORE the boxcar, physical sign.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402
import stokes_from_slc as SFS  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT_CEIL = BASE_DIR / "docs" / "complex_cell_ceiling.json"
OUT_GRID = BASE_DIR / "docs" / "complex_grid_correlation.json"
MECH = BASE_DIR / "docs" / "mechanism_spec.json"
ENL = BASE_DIR / "docs" / "enl.json"
AZ, RG = 21, 5            # azimuth looks, boxcar
WINDOWS, LINES_EACH = 9, 8400
LAG = 24                  # cpr_significance.py's lag window
WINDOW_31 = 31 * 31

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).resolve().parent / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def acf2d(z: np.ndarray, max_az: int, max_rg: int) -> np.ndarray:
    """Linear complex autocovariance r(da, dr), da in [-max_az, max_az],
    dr in [-max_rg, max_rg], normalized to r(0, 0) = 1. Each range bin's
    azimuth mean removed first (as mechanism_spec.pr_from_spectrum)."""
    z = z - z.mean(axis=0)
    H, W = z.shape
    F = np.fft.fft2(z, s=(2 * H, 2 * W))
    a = np.fft.ifft2(np.abs(F) ** 2)
    da = np.r_[0:max_az + 1, -max_az:0]
    dr = np.r_[0:max_rg + 1, -max_rg:0]
    sub = a[np.ix_(da % (2 * H), dr % (2 * W))]
    cnt = (H - np.abs(da))[:, None] * (W - np.abs(dr))[None, :]
    sub = sub / cnt
    sub = sub / sub[0, 0].real
    return np.fft.fftshift(sub)         # centre (max_az, max_rg) = lag 0


def participation(r: np.ndarray, n_az: int, n_rg: int) -> float:
    """(sum lambda)^2 / sum lambda^2 of the (n_az n_rg)^2 covariance of an
    n_az x n_rg block of samples, from the centred ACF r."""
    ca, cr = (r.shape[0] - 1) // 2, (r.shape[1] - 1) // 2
    ia, ir = np.meshgrid(np.arange(n_az), np.arange(n_rg), indexing="ij")
    ia, ir = ia.ravel(), ir.ravel()
    C = r[ca + ia[:, None] - ia[None, :], cr + ir[:, None] - ir[None, :]]
    lam = np.linalg.eigvalsh(0.5 * (C + C.conj().T))
    return float(lam.sum() ** 2 / (lam ** 2).sum())


def ceiling() -> dict:
    CTRL = _load("slc_multilook_control")
    lab = SFS.label_fields()
    g_lh, g_lv = lab["gain_imbalance"]["LH"], lab["gain_imbalance"]["LV"]
    SFS.configure("20200808")
    eh, ev = SFS.open_slc("lh"), SFS.open_slc("lv")
    starts = np.linspace(0, CTRL.LINES - LINES_EACH - 1, WINDOWS).astype(int)
    shapes = {"21x1": (AZ, 1), "105x1": (AZ * RG, 1), "21x5": (AZ, RG), "105x5": (AZ * RG, RG)}
    rows = []
    for wi, s0 in enumerate(starts):
        a = np.array(eh[s0:s0 + LINES_EACH], dtype=np.complex128)
        b = np.array(ev[s0:s0 + LINES_EACH], dtype=np.complex128)
        col = ((np.abs(a) > 0) & (np.abs(b) > 0)).mean(axis=0)
        keep = np.flatnonzero(col > 0.999)
        if keep.size < 64:
            continue
        sl = slice(keep.min(), keep.max() + 1)
        a, b = a[:, sl] / g_lh, b[:, sl] / g_lv
        if float(((np.abs(a) > 0) & (np.abs(b) > 0)).mean()) < 0.98:
            continue
        # circular channels. Physical sign (decision_rule.py): S3 = -2 Im<E_H E_V*>,
        # SC = (S0 - S3)/2 = |E_H + i E_V|^2 / 2, OC = |E_H - i E_V|^2 / 2.
        chans = {"LH": a, "LV": b, "SC": (a + 1j * b) / np.sqrt(2), "OC": (a - 1j * b) / np.sqrt(2)}
        row = {"window": wi, "start_line": int(s0), "range_bins": int(a.shape[1])}
        for ch, z in chans.items():
            r = acf2d(z, AZ * RG, RG)
            row[ch] = {k: participation(r, *v) for k, v in shapes.items()}
            row[ch]["acf_lag1_az_abs"] = float(abs(r[AZ * RG + 1, RG]))
            row[ch]["acf_lag1_rg_abs"] = float(abs(r[AZ * RG, RG + 1]))
        rows.append(row)
        print(f"  window {wi}: 105x5 PR  LH {row['LH']['105x5']:.2f}  LV {row['LV']['105x5']:.2f}  "
              f"SC {row['SC']['105x5']:.2f}  OC {row['OC']['105x5']:.2f}   (21x1 LH "
              f"{row['LH']['21x1']:.2f}, 105x1 {row['LH']['105x1']:.2f}, 21x5 {row['LH']['21x5']:.2f})",
              flush=True)
        del a, b, chans
    summ = {}
    for ch in ("LH", "LV", "SC", "OC"):
        summ[ch] = {k: {"median": float(np.median([r[ch][k] for r in rows])),
                        "range": [float(min(r[ch][k] for r in rows)),
                                  float(max(r[ch][k] for r in rows))]}
                    for k in list(shapes) + ["acf_lag1_az_abs", "acf_lag1_rg_abs"]}
    mech = json.loads(MECH.read_text(encoding="utf-8"))["expected_looks_from_measured_spectrum"]
    return {"rows": rows, "summary": summ, "mechanism_spec_21x1": mech}


def grid_measures() -> dict:
    ME = _load("measure_enl")
    CS = _load("cpr_significance")
    SFS.configure("20200808")
    hh, vv, hv, info = SFS.build_coherency(0, smooth=False)
    s0 = hh + vv
    s3 = -2.0 * hv.imag                      # physical sign, as decision_rule.py
    sc, oc = 0.5 * (s0 - s3), 0.5 * (s0 + s3)
    raw_ok = (hh > 0) & (vv > 0) & (sc > 0) & (oc > 0)
    lags = {"SC": ME.lag_correlation(sc, raw_ok, 16, max_lag=3),
            "OC": ME.lag_correlation(oc, raw_ok, 16, max_lag=3),
            "LH_complex_grid": ME.lag_correlation(hh, raw_ok, 16, max_lag=3)}
    print(f"  lag-1 before the boxcar: SC az {lags['SC']['azimuth_lines'][0]:.4f} rg "
          f"{lags['SC']['range_samples'][0]:.4f} | OC az {lags['OC']['azimuth_lines'][0]:.4f} rg "
          f"{lags['OC']['range_samples'][0]:.4f}", flush=True)
    del sc, oc
    # the CPR field as it is formed: boxcar on the coherency, then the ratio
    hh, vv = SFS.boxcar2d(hh), SFS.boxcar2d(vv)
    hv = SFS.boxcar2d(hv.real) + 1j * SFS.boxcar2d(hv.imag)
    s0 = hh + vv
    s3 = -2.0 * hv.imag
    m = (hh > 0) & (vv > 0) & (s0 > 0)
    cpr = SFS.cpr_from(s0, s3, m)
    blocks = SFS.low_cv_tiles(s0, m, 64, percentile=10)
    areas, acfs = [], []
    for r0, c0, _ in blocks:
        f = cpr[r0:r0 + 64, c0:c0 + 64]
        v = np.isfinite(f)
        ca = CS.correlation_area(np.where(v, f, 0.0), v, patch=64, lag=LAG)
        areas.append(ca["area_all_lags"])
        b = f - np.nanmean(f)
        F = np.fft.rfft2(np.nan_to_num(b), s=(128, 128))
        a_ = np.fft.irfft2(np.abs(F) ** 2, s=(128, 128))
        acfs.append(a_ / a_[0, 0])
    acf = np.mean(acfs, axis=0)
    win = np.r_[0:LAG + 1, -LAG:0]
    pooled = float(acf[np.ix_(win, win)].sum())
    areas = np.array(areas)
    med, q1, q3 = (float(np.percentile(areas, p)) for p in (50, 25, 75))
    print(f"  correlation area of the Stokes CPR on the complex grid: {len(blocks)} blocks, "
          f"median {med:.2f} px (IQR {q1:.2f}-{q3:.2f}), pooled ACF {pooled:.2f}", flush=True)
    enl = json.loads(ENL.read_text(encoding="utf-8"))["lag_correlation"]["LH"]
    return {"blocks": len(blocks), "areas": areas, "median": med, "iqr": [q1, q3],
            "pooled": pooled, "lag1_az": float(acf[1, 0]), "lag1_rg": float(acf[0, 1]),
            "lags": lags, "enl_LH": enl, "info": {"n_out": info["n_out"]}}


def main() -> int:
    t0 = time.time()
    print("=" * 78)
    print("B4 — spectral ceiling on N for one complex-product cell (105 az x 5 rg)")
    print("=" * 78)
    ce = ceiling()
    t_ceil = time.time() - t0
    s = ce["summary"]
    below = s["LH"]["105x5"]["median"] < 79.6166
    for ch in ("LH", "LV", "SC", "OC"):
        print(f"  {ch}: 105x5 median {s[ch]['105x5']['median']:.2f} range "
              f"{s[ch]['105x5']['range'][0]:.2f}-{s[ch]['105x5']['range'][1]:.2f}  "
              f"(21x1 {s[ch]['21x1']['median']:.2f})")
    ceil_max = max(s[ch]["105x5"]["range"][1] for ch in ("LH", "LV", "SC", "OC"))
    OUT_CEIL.write_text(json.dumps({
        "schema": "lunar-ice/complex-cell-ceiling/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/complex_grid.py",
        "seed": None, "seed_note": "no random draws: a spectral computation",
        "definition": ("participation ratio (sum lambda)^2 / sum lambda^2 of the covariance of "
                       "the samples averaged into one complex-product cell: 21 consecutive "
                       "azimuth lines (build_coherency), then a 5 x 5 boxcar on that grid = 105 "
                       "azimuth x 5 range samples, equal weight; covariance from the window's "
                       "measured 2-D autocovariance (linear, overlap-normalized), eigenvalues "
                       "taken explicitly"),
        "windows": {"count": WINDOWS, "lines_each": LINES_EACH,
                    "starts": "numpy.linspace(0, LINES - lines - 1, windows), as mechanism_spec.py",
                    "range_crop": "bins non-zero on > 99.9 % of lines in both channels"},
        "channels": {"LH": "as mechanism_spec.py", "LV": "",
                     "SC": "(E_H/G_H + i E_V/G_V)/sqrt 2, physical sign (S3 = -2 Im<E_H E_V*>)",
                     "OC": "(E_H/G_H - i E_V/G_V)/sqrt 2"},
        "ceiling_105x5": {ch: s[ch]["105x5"] for ch in s},
        "check_21x1_vs_mechanism_spec": {"here_LH_median": s["LH"]["21x1"]["median"],
                                         "mechanism_spec_median": ce["mechanism_spec_21x1"]["median"],
                                         "mechanism_spec_range": ce["mechanism_spec_21x1"]["range"]},
        "summary": s,
        "compare": {"block_log_ratio_N": 39.4, "crit_crossing_N": 79.6166,
                    "ceiling_median_LH": s["LH"]["105x5"]["median"],
                    "ceiling_below_79p6": bool(below),
                    "windows_at_or_above_79p6": {
                        ch: int(sum(r[ch]["105x5"] >= 79.6166 for r in ce["rows"]))
                        for ch in ("LH", "LV", "SC", "OC")},
                    "windows": len(ce["rows"]),
                    "max_over_windows_and_channels": ceil_max,
                    "block_N_over_ceiling": 39.4 / s["LH"]["105x5"]["median"],
                    "verdict": (("THE CEILING IS BELOW 79.6: the median over the nine windows "
                                 f"is {s['LH']['105x5']['median']:.1f} looks (LH); "
                                 f"{sum(r['LH']['105x5'] >= 79.6166 for r in ce['rows'])} of "
                                 f"{len(ce['rows'])} windows reach 79.6. A cell of this product "
                                 "cannot typically carry 79.6 independent looks, so most local "
                                 "N_hat >= 79.6 readings are estimator noise")
                                if below else
                                "the median ceiling is at or above 79.6")},
        "per_window": ce["rows"],
        "run_info": {**run_info(), "wall_s": round(t_ceil, 1)},
    }, indent=2), encoding="utf-8")
    print(f"  wrote {OUT_CEIL.relative_to(BASE_DIR)}", flush=True)

    print("=" * 78)
    print("B5 / B2(c) — correlation area and SC/OC lags on the complex grid")
    print("=" * 78)
    t1 = time.time()
    gm = grid_measures()
    w_new = WINDOW_31 / gm["median"]
    OUT_GRID.write_text(json.dumps({
        "schema": "lunar-ice/complex-grid-correlation/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/complex_grid.py",
        "seed": None, "seed_note": "no random draws",
        "correlation_area": {
            "field": "Stokes CPR, physical sign, after the 5 x 5 boxcar, complex-product grid",
            "blocks": gm["blocks"], "block_px": 64,
            "estimator": ("cpr_significance.correlation_area: block mean removed, zero-padded "
                          f"Wiener-Khinchin ACF, all lags within +/-{LAG} summed"),
            "median_px": gm["median"], "iqr_px": gm["iqr"],
            "pooled_acf_px": gm["pooled"],
            "pooled_lag1": {"azimuth": gm["lag1_az"], "range": gm["lag1_rg"]},
            "per_block_px": [float(a) for a in gm["areas"]],
            "delivered_grid_value_px": 61.42,
            "delivered_grid_source": "cpr_significance.json::effective_samples.area_all_lags "
                                     "(boxcar'd amplitude proxy, 25 m grid)"},
        "window_31x31": {"cells": WINDOW_31,
                         "independent_samples_at_median_A": w_new,
                         "W_used": int(round(w_new)),
                         "previous_W": 16,
                         "previous_basis": "961 / 61.42, the delivered grid's A: mixed grids"},
        "lag_correlation_before_boxcar": {
            "estimator": "measure_enl.lag_correlation, 16-px patches, patch mean removed",
            "sign": "physical: S3 = -2 Im<E_H E_V*>, SC = (S0 - S3)/2",
            "SC": gm["lags"]["SC"], "OC": gm["lags"]["OC"],
            "LH_complex_grid": gm["lags"]["LH_complex_grid"],
            "delivered_LH_enl_json": gm["enl_LH"]},
        "run_info": {**run_info(), "wall_s": round(time.time() - t1, 1)},
    }, indent=2), encoding="utf-8")
    print(f"  W = 961 / {gm['median']:.2f} = {w_new:.1f}", flush=True)
    print(f"  wrote {OUT_GRID.relative_to(BASE_DIR)}  ({time.time() - t0:.0f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
