"""
stokes_from_slc.py -- P1. The Stokes vector, formed from the single-look complex.

    python backend/scripts/stokes_from_slc.py [--max-lines N]

WHY THIS IS THE DECISIVE EXPERIMENT
-----------------------------------
Everything this project says about the amplitude-only CPR rests on an algebraic
claim proved from the delivered amplitude rasters -- proved about the product,
using the product. The single-look complex from the SAME PASS retains the H-V
cross-product, so the amplitude proxy and the genuine Stokes quantities can be
computed FROM THE SAME SAMPLES and compared.

WHAT THE FIRST VERSION GOT WRONG, AND WHAT IT OVERSTATED
--------------------------------------------------------
Two errors, both corrected here and both recorded because each looked like a
result:

  3b tested the wrong band. Eq. (1) of the paper follows from Cauchy-Schwarz:
  |S3| <= 2|<E_H E_V*>| <= 2 sqrt(l_H l_V), so the Stokes CPR lies in [c, 1/c]
  with c = ((sqrt l_H - sqrt l_V)/(sqrt l_H + sqrt l_V))^2 -- which is CPR_a
  itself. The first version tested the COUPLING band [(1-DOP_a)/(1+DOP_a), ...]
  instead, saw 80 % violations, and explained the wrong formula's failure as
  algebra. The true band is invariant to any phase rotation, because rotation
  moves magnitude between S2 and S3 and cannot increase |<E_H E_V*>|.
  Expected: exactly zero.

  "A factor of 22 on a convention" treated a binary sign as a continuous
  unknown. CPR = (S0-S3)/(S0+S3) with S3 = +/-2 Im<E_H E_V*> admits ONE binary
  choice: which circular combination is called same-sense. That is 0 deg or
  180 deg, and the two readings are reciprocals. The 90/270 rows are what you
  get by mistaking S2 for S3; 45/135/225/315 are mixtures. None is an admissible
  reading. The physical sign is the one under which single-bounce reflection --
  which reverses handedness -- gives CPR < 1; a frame-wide median of 4.7 would
  make the lunar south pole double-bounce everywhere, against every published
  map. So the sign is fixed by the DEFINITION of CPR plus the observation of
  which circular component dominates, and is stated as a convention with its
  reasoning, not as an ambiguity.

WHAT THE PHASE MEASUREMENT ACTUALLY SAYS
----------------------------------------
For circular transmit and linear receive, single-bounce puts E_H and E_V in
quadrature: arg<E_H E_V*> = +/-90 deg exactly, in a calibrated system. A
circular mean of -88.33 deg with resultant 0.946 over 5.88 M cells says the
terrain is overwhelmingly single-bounce AND the inter-channel phase is within
1.67 deg of quadrature. Whatever fraction of that is instrument residual, its
effect on |S3| is cos(1.67 deg) = 0.99958 -- 0.04 %. The data BOUND the phase
calibration error; they do not reveal a failure of it.

WHAT IS COMPUTED ON WHICH GRID
------------------------------
The SLC is slant-range / azimuth-time, 355,768 x 759; the delivered `sri` is
selenoreferenced onto a 25 m UPS grid, 2,258 x 6,618. Every comparison that can
be made without geocoding is made on the SLC grid, from one coherency matrix.
Only 3a compares against the delivered rasters, and only distributionally.

CALIBRATION, IN THE ORDER APPLIED (process_real_sar_pipeline.py:407-411)
    sigma0_X = |E_X|^2 * sin(theta) / (K_lin * G_X^2)
sin(theta) and K are common and cancel in every ratio; G_X is per-channel and
does not. K is the SLI label's 80.000000, not the SRI label's 70.308868.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.stats import f as Fdist

BASE_DIR = Path(__file__).resolve().parents[2]
RAW = BASE_DIR / "data/pradan/raw/data/calibrated/20200808"
STEM = "ch2_sar_ncxl_20200808t201154198"
OUT = BASE_DIR / "docs" / "stokes_from_slc.json"

LINES, SAMPLES, OFFSET = 355768, 759, 5725302
AZIMUTH_LOOKS = 21
BOXCAR = 5
DOP_THRESHOLD = 0.13
CPR_THRESHOLD = 1.0
#: Sec. V-C's homogeneous windows: k x k, non-overlapping, the `top` lowest
#: CV of S0 -- the criterion cpr_dispersion.py applies on the delivered grid.
WINDOW = 15
TOP_WINDOWS = 20
BLOCK = 64
BLOCK_CV_PERCENTILE = 10
SEED = 7

_T0 = time.time()
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def beat(msg: str) -> None:
    print(f"  [{time.strftime('%H:%M:%S')}  +{time.time() - _T0:7.1f}s]  {msg}",
          flush=True)


def hr(t: str) -> None:
    print("\n" + "=" * 78 + "\n" + t + "\n" + "=" * 78, flush=True)


def label_fields() -> dict:
    """K, the per-channel gains and the phase fields, READ from the sli label."""
    src = (RAW / f"{STEM}_d_sli_xx_cp_xx_d18.xml").read_text(
        encoding="utf-8", errors="replace")

    def one(tag):
        m = re.search(r"<isda:" + tag + r"[^>]*>([^<]+)<", src)
        return None if m is None else m.group(1).strip()

    gains = re.findall(r"<isda:polarization>(\w+)</isda:polarization>.*?"
                       r"<isda:gain_imbalance>([^<]+)<", src, re.S)
    phases = re.findall(r"<isda:polarization>(\w+)</isda:polarization>.*?"
                        r"<isda:phase_orthogonality>([^<]+)<", src, re.S)
    return {
        "calibration_constant_db": float(one("calibration_constant")),
        "incidence_angle_deg": float(one("incidence_angle")),
        "gain_imbalance": {k: float(v) for k, v in gains},
        "phase_orthogonality": {k: float(v) for k, v in phases},
        "azimuth_looks_declared": int(float(one("azimuth_looks"))),
    }


def open_slc(ch: str) -> np.memmap:
    p = RAW / f"{STEM}_d_sli_xx_cp_{ch}_d18.tif"
    size = p.stat().st_size
    need = OFFSET + LINES * SAMPLES * 8
    if size != need:
        raise SystemExit(f"{p.name}: {size} bytes, geometry implies {need}. "
                         f"Refusing to memmap an unconfirmed raster.")
    return np.memmap(p, dtype=np.complex64, mode="r",
                     offset=OFFSET, shape=(LINES, SAMPLES))


def boxcar2d(a: np.ndarray, k: int = BOXCAR) -> np.ndarray:
    """Separable running mean, identical in effect to the pipeline's 5x5."""
    pad = k // 2
    b = np.pad(a, ((pad, pad), (pad, pad)), mode="edge")
    c = np.cumsum(b, axis=0)
    c = np.vstack([c[k - 1:k, :], c[k:, :] - c[:-k, :]]) / k
    d = np.cumsum(c, axis=1)
    d = np.hstack([d[:, k - 1:k], d[:, k:] - d[:, :-k]]) / k
    return d


def enl_moment(x: np.ndarray, mask: np.ndarray, patch: int = 16) -> dict:
    """Median of per-patch mean^2/var over patches wholly inside the mask."""
    h, w = x.shape
    ph, pw = h // patch * patch, w // patch * patch
    blocks = x[:ph, :pw].reshape(ph // patch, patch, pw // patch, patch)
    blocks = blocks.swapaxes(1, 2).reshape(-1, patch * patch)
    mblk = mask[:ph, :pw].reshape(ph // patch, patch, pw // patch, patch)
    mblk = mblk.swapaxes(1, 2).reshape(-1, patch * patch)
    blocks = blocks[mblk.all(axis=1)]
    if blocks.shape[0] < 30:
        return {"n_patches": int(blocks.shape[0]), "enl": None}
    m = blocks.mean(axis=1)
    v = blocks.var(axis=1, ddof=1)
    r = m ** 2 / np.where(v > 0, v, np.nan)
    r = r[np.isfinite(r)]
    return {"n_patches": int(r.size), "enl": float(np.median(r)),
            "enl_se": float(1.253 * r.std(ddof=1) / np.sqrt(r.size)),
            "p5": float(np.percentile(r, 5)), "p95": float(np.percentile(r, 95)),
            "patch": patch}


def cpr_from(s0, s3, mask):
    """(S0-S3)/(S0+S3), NaN wherever the denominator is not positive."""
    ok = mask & ((s0 + s3) > 0)
    return np.where(ok, (s0 - s3) / np.where(ok, s0 + s3, 1.0), np.nan)


def tile(a, k):
    """Non-overlapping k x k tiles as rows; also the tile-grid width."""
    h, w = a.shape
    ph, pw = h // k * k, w // k * k
    t = a[:ph, :pw].reshape(ph // k, k, pw // k, k).swapaxes(1, 2)
    return t.reshape(-1, k * k), pw // k


def low_cv_tiles(s0, mask, k, *, top=None, percentile=None):
    """Tiles wholly inside the mask, ranked by CV of S0. Either the `top`
    lowest, or every tile below the given percentile of CV."""
    S, nbw = tile(s0, k)
    M, _ = tile(mask, k)
    idx = np.flatnonzero(M.all(axis=1))
    mu = S[idx].mean(axis=1)
    sd = S[idx].std(axis=1, ddof=1)
    cv = np.where(mu > 0, sd / mu, np.inf)
    if top is not None:
        pick = np.argsort(cv)[:top]
    else:
        pick = np.flatnonzero(cv < np.percentile(cv, percentile))
    return [(int(idx[p] // nbw) * k, int(idx[p] % nbw) * k, float(cv[p])) for p in pick]


def window_stats(r0, c0, k, sc, oc, cpr, dop, coh, mask):
    """3e, inside one homogeneous window -- speckle-only by construction:
    the empirical Stokes-CPR tail about the window's own median, against
    F(2 N_SC, 2 N_OC) at the window's own moment ENLs."""
    sl = (slice(r0, r0 + k), slice(c0, c0 + k))
    m = mask[sl]
    x, y = sc[sl][m], oc[sl][m]
    c_ = cpr[sl][m]
    c_ = c_[np.isfinite(c_)]
    n_sc = float(x.mean() ** 2 / x.var(ddof=1)) if x.size > 2 else float("nan")
    n_oc = float(y.mean() ** 2 / y.var(ddof=1)) if y.size > 2 else float("nan")
    xc, yc = x - x.mean(), y - y.mean()
    corr = float(abs((xc * yc).mean()) / np.sqrt((xc ** 2).mean() * (yc ** 2).mean()))
    med = float(np.median(c_))
    rel = c_ / med
    out = {"row": r0, "col": c0, "n": int(c_.size), "n_sc": n_sc, "n_oc": n_oc,
           "corr_sc_oc": corr, "cpr_median": med,
           "emp_p95_over_median": float(np.percentile(rel, 95)),
           "emp_p99_over_median": float(np.percentile(rel, 99)),
           "emp_p_gt1": float((c_ > CPR_THRESHOLD).mean()),
           "dop_below_frac": float((dop[sl][m] < DOP_THRESHOLD).mean()),
           "coherence_median": float(np.median(coh[sl][m]))}
    if np.isfinite(n_sc) and np.isfinite(n_oc) and n_sc > 1 and n_oc > 1:
        d1, d2 = 2 * n_sc, 2 * n_oc
        fmed = Fdist.ppf(0.5, d1, d2)
        out["f_p95_over_median"] = float(Fdist.ppf(0.95, d1, d2) / fmed)
        out["f_p99_over_median"] = float(Fdist.ppf(0.99, d1, d2) / fmed)
        # P(CPR_hat > 1 | true CPR = window median), under F
        out["f_p_gt1"] = float(1.0 - Fdist.cdf(fmed / med, d1, d2)) if med > 0 else None
        out["ratio_p95"] = out["emp_p95_over_median"] / out["f_p95_over_median"]
        out["ratio_p99"] = out["emp_p99_over_median"] / out["f_p99_over_median"]
    return out


def summarise(group, label):
    r95 = [g["ratio_p95"] for g in group if "ratio_p95" in g]
    r99 = [g["ratio_p99"] for g in group if "ratio_p99" in g]
    cc = [g["corr_sc_oc"] for g in group]
    p1 = [g["emp_p_gt1"] for g in group]
    print(f"  {label}: {len(group)} windows")
    if not group:
        return {"n_windows": 0}
    if r95:
        print(f"    empirical/F p95-over-median  median {np.median(r95):.3f}  "
              f"range [{min(r95):.3f}, {max(r95):.3f}]")
        print(f"    empirical/F p99-over-median  median {np.median(r99):.3f}  "
              f"range [{min(r99):.3f}, {max(r99):.3f}]")
    print(f"    |corr(SC,OC)| per window     median {np.median(cc):.3f}  "
          f"range [{min(cc):.3f}, {max(cc):.3f}]")
    print(f"    N_SC median {np.median([g['n_sc'] for g in group]):.2f}   "
          f"N_OC median {np.median([g['n_oc'] for g in group]):.2f}   "
          f"P(CPR>1) median {np.median(p1):.4f}")
    return {"n_windows": len(group),
            "ratio_p95_median": float(np.median(r95)) if r95 else None,
            "ratio_p95_range": [min(r95), max(r95)] if r95 else None,
            "ratio_p99_median": float(np.median(r99)) if r99 else None,
            "ratio_p99_range": [min(r99), max(r99)] if r99 else None,
            "corr_median": float(np.median(cc)), "corr_range": [min(cc), max(cc)],
            "n_sc_median": float(np.median([g["n_sc"] for g in group])),
            "n_oc_median": float(np.median([g["n_oc"] for g in group])),
            "p_gt1_median": float(np.median(p1)),
            "cpr_median_range": [min(g["cpr_median"] for g in group),
                                 max(g["cpr_median"] for g in group)]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-lines", type=int, default=0,
                    help="SLC lines to process (default: the whole swath)")
    args = ap.parse_args()

    lab = label_fields()
    k_lin = 10.0 ** (lab["calibration_constant_db"] / 10.0)
    g_lh, g_lv = lab["gain_imbalance"]["LH"], lab["gain_imbalance"]["LV"]
    sin_t = float(np.sin(np.deg2rad(lab["incidence_angle_deg"])))

    hr("P1 — STOKES VECTOR FROM THE SINGLE-LOOK COMPLEX (amended after adjudication)")
    print(f"  K = {lab['calibration_constant_db']:g} dB (sli label)   "
          f"G_LH {g_lh:.6f}  G_LV {g_lv:.6f}   sin(theta) {sin_t:.6f}")

    eh, ev = open_slc("lh"), open_slc("lv")
    n_lines = args.max_lines or LINES
    n_out = n_lines // AZIMUTH_LOOKS
    hh = np.empty((n_out, SAMPLES)); vv = np.empty((n_out, SAMPLES))
    hv = np.empty((n_out, SAMPLES), dtype=np.complex128)
    CHUNK = 512
    for start in range(0, n_out, CHUNK):
        stop = min(start + CHUNK, n_out)
        a = np.asarray(eh[start * AZIMUTH_LOOKS:stop * AZIMUTH_LOOKS], dtype=np.complex128)
        b = np.asarray(ev[start * AZIMUTH_LOOKS:stop * AZIMUTH_LOOKS], dtype=np.complex128)
        rows = stop - start
        a = a.reshape(rows, AZIMUTH_LOOKS, SAMPLES)
        b = b.reshape(rows, AZIMUTH_LOOKS, SAMPLES)
        hh[start:stop] = (np.abs(a) ** 2).mean(axis=1)
        vv[start:stop] = (np.abs(b) ** 2).mean(axis=1)
        hv[start:stop] = (a * np.conj(b)).mean(axis=1)
        del a, b
    beat(f"coherency matrix: {n_out:,} x {SAMPLES} cells, {AZIMUTH_LOOKS} azimuth looks")

    scale = sin_t / k_lin
    hh *= scale / g_lh ** 2
    vv *= scale / g_lv ** 2
    hv *= scale / (g_lh * g_lv)
    # THE SAME 5x5 BOXCAR ON ALL THREE COHERENCY ELEMENTS. Stokes components
    # are linear in the coherency matrix, so boxcar-then-derive equals the
    # pipeline's smoothing; boxcar-on-the-ratio would not, and is a way 3b
    # could silently fail.
    hh, vv = boxcar2d(hh), boxcar2d(vv)
    hv = boxcar2d(hv.real) + 1j * boxcar2d(hv.imag)

    s0, s1 = hh + vv, hh - vv
    s2, s3 = 2.0 * hv.real, 2.0 * hv.imag     # 0 deg reading: S3 = +2 Im<E_H E_V*>
    m = (hh > 0) & (vv > 0) & (s0 > 0)
    n_m = int(m.sum())
    beat(f"matched mask: {n_m:,} cells")

    eps = 1e-300
    dop_s = np.where(m, np.sqrt(s1 ** 2 + s2 ** 2 + s3 ** 2) / (s0 + eps), np.nan)
    coh = np.where(m, np.abs(hv) / np.sqrt(np.maximum(hh * vv, eps)), np.nan)
    sq_h, sq_v = np.sqrt(np.maximum(hh, 0)), np.sqrt(np.maximum(vv, 0))
    cpr_a = np.where(m, ((sq_h - sq_v) / (sq_h + sq_v + eps)) ** 2, np.nan)
    dop_a = np.where(m, np.abs(s1) / (s0 + eps), np.nan)

    # The two ADMISSIBLE readings: the sign of S3.
    cpr_0, cpr_180 = cpr_from(s0, s3, m), cpr_from(s0, -s3, m)
    med_0, med_180 = float(np.nanmedian(cpr_0)), float(np.nanmedian(cpr_180))
    physical_deg = 0 if med_0 < 1.0 else 180
    cpr_p = cpr_0 if physical_deg == 0 else cpr_180
    s3_p = s3 if physical_deg == 0 else -s3
    sc_p, oc_p = 0.5 * (s0 - s3_p), 0.5 * (s0 + s3_p)

    res: dict = {}

    # ---- 3b, AMENDED: Eq. (1)'s band, at both signs ------------------------
    hr("3b — Stokes CPR inside [c, 1/c], c = CPR_a from the SAME l_H, l_V")
    c = cpr_a[m]
    lo_b, hi_b = c, 1.0 / np.maximum(c, eps)
    for deg, arr in ((0, cpr_0), (180, cpr_180)):
        v = arr[m]
        ok = np.isfinite(v)
        outside = (v[ok] < lo_b[ok] * (1 - 1e-12)) | (v[ok] > hi_b[ok] * (1 + 1e-12))
        frac = float(outside.mean())
        exc = 0.0
        if outside.any():
            below = np.maximum(lo_b[ok] / np.maximum(v[ok], eps), 1.0)
            above = np.maximum(v[ok] / np.maximum(hi_b[ok], eps), 1.0)
            exc = float(np.maximum(below, above)[outside].max() - 1.0)
        print(f"  {deg:>3} deg: violation fraction {frac:.6f}   "
              f"max relative excursion {exc:.3e}   (n = {int(ok.sum()):,})")
        res[f"t3b_{deg}"] = {"violation_fraction": frac,
                             "max_relative_excursion": exc, "n": int(ok.sum()),
                             "tolerance": 1e-12}
    res["t3b_band"] = ("[c, 1/c], c = ((sqrt l_H - sqrt l_V)/(sqrt l_H + sqrt l_V))^2 "
                       "= CPR_a; follows from |S3| <= 2 sqrt(l_H l_V) (Cauchy-Schwarz) "
                       "and is invariant to any phase rotation")

    # ---- the sign, and the phase evidence -----------------------------------
    hr("THE SIGN OF S3 — the one binary convention, and the phase evidence")
    ph = np.angle(hv[m])
    resultant = complex(np.mean(np.exp(1j * ph)))
    mean_deg = float(np.degrees(np.angle(resultant)))
    resid_deg = abs(abs(mean_deg) - 90.0)
    cos_resid = float(np.cos(np.deg2rad(resid_deg)))
    print(f"  median Stokes CPR   0 deg: {med_0:.4f}    180 deg: {med_180:.4f}   "
          f"(product {med_0 * med_180:.4f}: reciprocal readings)")
    print(f"  PHYSICAL SIGN = {physical_deg} deg  (the reading with median < 1: "
          f"single bounce reverses handedness)")
    print(f"  arg<E_H E_V*>  circular mean {mean_deg:+.2f} deg   R = {abs(resultant):.4f}")
    print(f"  residual from quadrature {resid_deg:.2f} deg  ->  cos = {cos_resid:.5f}  "
          f"({100 * (1 - cos_resid):.3f} % on |S3|)")
    diag = []
    for deg in (45, 90, 135, 270, 315):
        r = hv * np.exp(1j * np.deg2rad(deg))
        diag.append({"rotation_deg": deg,
                     "median_cpr": float(np.nanmedian(cpr_from(s0, 2.0 * r.imag, m))),
                     "admissible": False})
        del r
    res["sign"] = {
        "admissible_readings": {"0_deg": med_0, "180_deg": med_180},
        "reciprocal_product": med_0 * med_180,
        "physical_sign_deg": physical_deg,
        "physical_median_cpr": float(np.nanmedian(cpr_p)),
        "reasoning": ("CPR = (S0-S3)/(S0+S3) with S3 = +/-2 Im<E_H E_V*> admits one "
                      "binary choice: which circular combination is same-sense. "
                      "CPR is defined so that single-bounce reflection, which "
                      "reverses handedness, gives CPR < 1. A frame-wide median of "
                      f"{max(med_0, med_180):.2f} would make the south pole "
                      "double-bounce everywhere against every published map; the "
                      f"reading with median {min(med_0, med_180):.4f} is physical."),
        "phase_evidence": {
            "circular_mean_deg": mean_deg, "resultant_length": float(abs(resultant)),
            "residual_from_quadrature_deg": resid_deg,
            "cos_residual": cos_resid,
            "effect_on_S3_percent": float(100 * (1 - cos_resid)),
            "reading": ("single bounce under circular transmit / linear receive puts "
                        "E_H and E_V in quadrature; the phase clusters there, so the "
                        "terrain is overwhelmingly single-bounce and the residual "
                        "phase-calibration error is BOUNDED by the data at < 2 deg. "
                        "This is calibration evidence, not an ambiguity.")},
        "label_phase_orthogonality": lab["phase_orthogonality"],
        "diagnostic_rotations_not_admissible": {
            "why": "90/270 mistake S2 for S3; 45/135/315 mix them. Not readings.",
            "rows": diag},
    }

    # ---- rotation-invariant results -----------------------------------------
    hr("ROTATION-INVARIANT MEASUREMENTS — hold regardless of the sign")
    wins = low_cv_tiles(s0, m, WINDOW, top=TOP_WINDOWS)
    coh_m = coh[m]
    dop_below = m & (dop_s < DOP_THRESHOLD)
    n_below = int(dop_below.sum())
    frac_below = n_below / n_m
    per_win_coh = [float(np.median(coh[r:r + WINDOW, c_:c_ + WINDOW])) for r, c_, _ in wins]
    per_win_dop = [float((dop_s[r:r + WINDOW, c_:c_ + WINDOW] < DOP_THRESHOLD).mean())
                   for r, c_, _ in wins]
    print(f"  (a) coherence |<E_H E_V*>|/sqrt(l_H l_V): median {np.median(coh_m):.4f}  "
          f"IQR [{np.percentile(coh_m, 25):.4f}, {np.percentile(coh_m, 75):.4f}]")
    print(f"      over {len(wins)} homogeneous {WINDOW}x{WINDOW} windows: median "
          f"{np.median(per_win_coh):.4f}, range [{min(per_win_coh):.4f}, {max(per_win_coh):.4f}]")
    se_below = float(np.sqrt(frac_below * (1 - frac_below) / n_m))
    print(f"  (b) Stokes DOP < {DOP_THRESHOLD}: {n_below:,} of {n_m:,} = "
          f"{100 * frac_below:.4f} %  (binomial SE {100 * se_below:.4f} pp)")
    print(f"      per window: median {100 * np.median(per_win_dop):.2f} %, "
          f"range [{100 * min(per_win_dop):.2f}, {100 * max(per_win_dop):.2f}] %")
    lo_c = (1 - DOP_THRESHOLD) / (1 + DOP_THRESHOLD)
    hi_c = (1 + DOP_THRESHOLD) / (1 - DOP_THRESHOLD)
    v_b = cpr_p[dop_below]
    v_b = v_b[np.isfinite(v_b)]
    out_band = float(((v_b <= lo_c) | (v_b >= hi_c)).mean())
    print(f"  (c) 3f: of those {n_below:,} cells, fraction outside "
          f"({lo_c:.4f}, {hi_c:.4f}): {out_band:.6f}")
    excl_a = m & (dop_a >= DOP_THRESHOLD)
    also = float((dop_s[excl_a] >= DOP_THRESHOLD).mean())
    print(f"  3c  DOP_a >= {DOP_THRESHOLD} on {100 * excl_a.sum() / n_m:.4f} % of cells; "
          f"of those Stokes DOP >= {DOP_THRESHOLD}: {100 * also:.4f} %")
    res["invariant"] = {
        "coherence": {"median": float(np.median(coh_m)),
                      "iqr": [float(np.percentile(coh_m, 25)), float(np.percentile(coh_m, 75))],
                      "per_window_median": per_win_coh},
        "dop_below_threshold": {"n": n_below, "of": n_m, "fraction": frac_below,
                                "binomial_se": se_below,
                                "per_window_fraction": per_win_dop},
        "t3f_coupling_band": {"n": int(v_b.size), "fraction_outside": out_band,
                              "band": [lo_c, hi_c]},
        "t3c": {"fraction_dop_a_ge": float(excl_a.sum() / n_m),
                "of_those_stokes_dop_ge": also},
        "windows": [{"row": r, "col": c_, "cv_s0": cv} for r, c_, cv in wins],
        "window_selection": (f"{TOP_WINDOWS} non-overlapping {WINDOW}x{WINDOW} windows "
                             "wholly inside the mask, lowest CV of S0 on the SLC grid "
                             "-- the criterion of cpr_dispersion.py, Sec. V-C"),
    }

    # ---- the measured joint rate, at the physical sign -----------------------
    hr("MEASURED JOINT RATE — CPR > 1 among Stokes DOP < 0.13, physical sign")
    j = float((v_b > CPR_THRESHOLD).mean())
    j_se = float(np.sqrt(j * (1 - j) / v_b.size))
    n_both = int((v_b > CPR_THRESHOLD).sum())
    ju = n_both / n_m
    ju_se = float(np.sqrt(ju * (1 - ju) / n_m))
    print(f"  conditional  P(CPR > 1 | DOP < {DOP_THRESHOLD}) = {100 * j:.4f} % +/- "
          f"{100 * j_se:.4f} pp   over {v_b.size:,} cells")
    print(f"  unconditional P(CPR > 1 AND DOP < {DOP_THRESHOLD}) = {100 * ju:.4f} % +/- "
          f"{100 * ju_se:.4f} pp   ({n_both:,} of {n_m:,})")
    print("  These are measured over THIS terrain; the DOP < 0.13 cells are, by the")
    print("  coupling identity, cells whose CPR already lies in (0.77, 1.30). Neither")
    print("  is the simulated joint false-positive rate at a 0.7 background (P7).")
    res["joint_measured"] = {
        "conditional": {"fraction": j, "binomial_se": j_se, "n": int(v_b.size),
                        "definition": "P(CPR_S > 1 | DOP_S < 0.13)"},
        "unconditional": {"fraction": ju, "binomial_se": ju_se, "n_both": n_both,
                          "of": n_m, "definition": "P(CPR_S > 1 AND DOP_S < 0.13)"},
        "sign_deg": physical_deg,
        "not_comparable_to": "joint_criterion.py simulates a 0.7 background; this "
                             "is the rate on the terrain actually observed"}

    # ---- 3d at both signs ----------------------------------------------------
    hr("3d — circular ENLs and |corr(SC, OC)|, both signs")
    for deg, s3v in ((0, s3), (180, -s3)):
        sc_, oc_ = 0.5 * (s0 - s3v), 0.5 * (s0 + s3v)
        e_sc = enl_moment(np.where(m, sc_, np.nan), m)
        e_oc = enl_moment(np.where(m, oc_, np.nan), m)
        x, y = sc_[m], oc_[m]
        xc, yc = x - x.mean(), y - y.mean()
        g = float(abs((xc * yc).mean()) / np.sqrt((xc ** 2).mean() * (yc ** 2).mean()))
        tag = "   <- physical" if deg == physical_deg else ""
        print(f"  {deg:>3} deg: N_SC {e_sc['enl']:.2f} +/- {e_sc['enl_se']:.2f}   "
              f"N_OC {e_oc['enl']:.2f} +/- {e_oc['enl_se']:.2f}   |corr| {g:.4f}{tag}")
        res[f"t3d_{deg}"] = {"enl_sc": e_sc, "enl_oc": e_oc, "corr_sc_oc": g,
                             "physical": deg == physical_deg}
        del sc_, oc_, x, y, xc, yc

    # ---- 3e REDESIGNED: speckle-only, within homogeneous windows -------------
    hr("3e — within-window tail vs F(2N_SC, 2N_OC), at each sign")
    blocks = low_cv_tiles(s0, m, BLOCK, percentile=BLOCK_CV_PERCENTILE)
    res["t3e"] = {"design": ("empirical Stokes CPR about each window's median vs "
                             "F(2N_SC, 2N_OC) at the window's own moment ENLs; "
                             "ratio > 1 = heavier tail than F (residual texture), "
                             "< 1 = narrower (channel correlation). Whole-frame "
                             "quantiles were the first version's error: they "
                             "include terrain."),
                  "blocks_64x64": {"cv_percentile": BLOCK_CV_PERCENTILE,
                                   "n_selected": len(blocks)}}
    for deg in (0, 180):
        s3v = s3 if deg == 0 else -s3
        sc_, oc_ = 0.5 * (s0 - s3v), 0.5 * (s0 + s3v)
        cprv = cpr_0 if deg == 0 else cpr_180
        tag = "   <- physical" if deg == physical_deg else ""
        print(f"  --- {deg} deg{tag}")
        ws = [window_stats(r, c_, WINDOW, sc_, oc_, cprv, dop_s, coh, m) for r, c_, _ in wins]
        bs = [window_stats(r, c_, BLOCK, sc_, oc_, cprv, dop_s, coh, m) for r, c_, _ in blocks]
        res["t3e"][f"{deg}_deg"] = {
            "windows_15x15_summary": summarise(ws, f"{WINDOW}x{WINDOW} homogeneous"),
            "blocks_64x64_summary": summarise(bs, f"{BLOCK}x{BLOCK} low-CV"),
            "windows_15x15": ws, "blocks_64x64": bs,
            "physical": deg == physical_deg}
        del sc_, oc_

    # ---- 3a at matched ENL, units stated ------------------------------------
    hr("3a — delivered vs SLC-formed amplitude ratio, AT MATCHED ENL")
    try:
        import tifffile
        d_lh = tifffile.imread(str(RAW / f"{STEM}_d_sri_xx_cp_lh_d18.tif")).astype(np.float64)
        d_lv = tifffile.imread(str(RAW / f"{STEM}_d_sri_xx_cp_lv_d18.tif")).astype(np.float64)
        dv = (d_lh > 0) & (d_lv > 0)
        # Delivered DN are AMPLITUDE (METHODS 7.2); intensity = DN^2. The
        # pipeline boxcars intensity, so the matched-ENL row boxcars DN^2 and
        # takes the square root of the ratio -- the same sqrt(l_H/l_V) formed on
        # the SLC side after 21 looks + the same 5x5 boxcar.
        bl_h = boxcar2d(np.where(dv, d_lh ** 2, 0.0))
        bl_v = boxcar2d(np.where(dv, d_lv ** 2, 0.0))
        r_del_raw = d_lh[dv] / d_lv[dv]
        r_del_bx = np.sqrt(bl_h[dv] / np.maximum(bl_v[dv], eps))
        r_slc = (sq_h / (sq_v + eps))[m]
        qs = [5, 25, 50, 75, 95]
        rows = {"delivered_raw_DN_ratio": np.percentile(r_del_raw, qs).tolist(),
                "delivered_boxcar5_sqrt_DN2_ratio": np.percentile(r_del_bx, qs).tolist(),
                "slc_21look_boxcar5_sqrt_ratio": np.percentile(r_slc, qs).tolist()}
        iqr = {k_: v_[3] - v_[1] for k_, v_ in rows.items()}
        print(f"  quantiles {qs} of the LH/LV AMPLITUDE ratio")
        for k_, v_ in rows.items():
            print(f"    {k_:<36} {[round(x, 4) for x in v_]}   IQR {iqr[k_]:.4f}")
        print("  delivered DN are AMPLITUDE (METHODS 7.2); the raw row is DN/DN at the")
        print("  delivered ENL (~5.8), the matched row is sqrt(boxcar5(DN^2)/boxcar5(DN^2))")
        print("  at ENL ~13.7, against the SLC's 21-look + boxcar5 field.")
        res["t3a"] = {"status": "partial - distributional, at matched ENL; no per-cell "
                                "slope or r^2 without geocoding",
                      "delivered_units": "DN are amplitude; intensity = DN^2",
                      "quantiles": qs, **rows, "iqr": iqr,
                      "blocker": "slant-range vs selenoreferenced grid; per-cell "
                                 "regression needs a geocoding step whose own error "
                                 "would dominate the residual"}
        del d_lh, d_lv, bl_h, bl_v
    except Exception as exc:  # noqa: BLE001
        print(f"  BLOCKED: {exc}")
        res["t3a"] = {"status": "blocked", "reason": str(exc)}

    OUT.write_text(json.dumps({
        "schema": "lunar-ice/stokes-from-slc/2",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/stokes_from_slc.py",
        "seed": SEED,
        "slc": {"lines": LINES, "samples": SAMPLES, "offset": OFFSET,
                "lines_processed": n_lines, "azimuth_looks": AZIMUTH_LOOKS,
                "boxcar": BOXCAR, "output_cells": [n_out, SAMPLES], "matched_cells": n_m},
        "calibration": {"equation": "sigma0_X = |E_X|^2 sin(theta) / (K_lin G_X^2)",
                        "order": ["|E|^2", "x sin(theta)", "/ K_lin", "/ G_X^2"],
                        "K_db": lab["calibration_constant_db"], "G_LH": g_lh, "G_LV": g_lv,
                        "sin_theta": sin_t,
                        "boxcar_applied_to": "all three coherency elements, before Stokes"},
        "sign_convention": (f"S3 = {'+' if physical_deg == 0 else '-'}2 Im<E_H E_V*> "
                            "(physical reading); SC = (S0-S3)/2, OC = (S0+S3)/2; "
                            "the other sign gives CPR -> 1/CPR"),
        "results": res,
    }, indent=2, default=float), encoding="utf-8")
    beat(f"wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
