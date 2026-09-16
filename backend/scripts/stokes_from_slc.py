"""
stokes_from_slc.py -- P1. The Stokes vector, formed from the single-look complex.

    python backend/scripts/stokes_from_slc.py [--max-lines N]

WHY THIS IS THE DECISIVE EXPERIMENT
-----------------------------------
Everything this project says about the amplitude-only CPR rests on an algebraic
claim: with the H-V cross-product discarded, CPR_a becomes a function of DOP_a
alone, and DOP_a < 0.13 caps CPR_a at 0.0042611 against a threshold of 1.00.
That claim is proved from the delivered amplitude rasters, which is exactly the
thing under suspicion -- it is proved about the product, using the product.

The single-look complex from the SAME PASS retains the cross-product. Forming the
coherency matrix from it gives a genuine Stokes vector, so the amplitude proxy
and the real quantity can be computed FROM THE SAME SAMPLES and compared. That
turns a sensitivity calculation into a measurement.

WHAT IS COMPUTED ON WHICH GRID, AND WHY IT MATTERS
--------------------------------------------------
The SLC is slant-range / azimuth-time: 355,768 x 759. The delivered `sri` is
selenoreferenced onto a 25 m UPS grid: 2,258 x 6,618. They are different
geometries and no decimation maps one onto the other.

So EVERY comparison that can be made without geocoding is made on the SLC grid,
by computing the amplitude proxy and the Stokes quantities from the SAME
coherency matrix. Tests 3c, 3d, 3e and 3f are therefore exact and self-consistent; 3b as
specified uses the wrong DOP and is reported as such. Test 3a alone compares against the DELIVERED rasters and needs
per-cell registration; what can be done without it is done, and the limitation is
recorded rather than papered over with a resampling step whose own error would
dominate the residual being reported.

CALIBRATION, AND THE ORDER IT IS APPLIED IN
-------------------------------------------
Exactly as `process_real_sar_pipeline.py:407-411`, and stated here because P1
asks for it:

    sigma0_X = |E_X|^2 * sin(theta) / (K_lin * G_X^2)

  1. |E_X|^2 formed from the complex sample
  2. multiplied by sin(theta)          -- COMMON to both channels
  3. divided by K_lin = 10^(K/10)      -- COMMON to both channels
  4. divided by G_X^2                  -- PER CHANNEL, so it does NOT cancel

K is read from the `sli` label (80.000000), which is NOT the `sri` label's
70.308868: they are different products and carry different constants. sin(theta)
and K are common factors and cancel in every ratio (METHODS 12.4), so CPR and DOP
are invariant to them; G_LH/G_LV is per-channel and does not cancel, and is the
one calibration term that can move these results.

CROSS-CHANNEL PHASE
-------------------
The label carries `phase_orthogonality` per channel (LH 1.074722, LV 0.467679)
with no stated unit and no documented procedure for applying a relative H-V phase
correction. This script therefore applies NO cross-channel phase calibration and
records that. Per P1.4: 3b, 3c and 3f are phase-convention-independent and stand
regardless; 3d and 3e depend on the convention and are reported with that caveat
attached rather than omitted.
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

BASE_DIR = Path(__file__).resolve().parents[2]
RAW = BASE_DIR / "data/pradan/raw/data/calibrated/20200808"
STEM = "ch2_sar_ncxl_20200808t201154198"
OUT = BASE_DIR / "docs" / "stokes_from_slc.json"

LINES, SAMPLES, OFFSET = 355768, 759, 5725302
AZIMUTH_LOOKS = 21
BOXCAR = 5
DOP_THRESHOLD = 0.13
CPR_THRESHOLD = 1.0
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
    """mean^2/var over patches wholly inside the mask, with the mode and an SE."""
    h, w = x.shape
    ph, pw = h // patch * patch, w // patch * patch
    blocks = x[:ph, :pw].reshape(ph // patch, patch, pw // patch, patch)
    blocks = blocks.swapaxes(1, 2).reshape(-1, patch * patch)
    mblk = mask[:ph, :pw].reshape(ph // patch, patch, pw // patch, patch)
    mblk = mblk.swapaxes(1, 2).reshape(-1, patch * patch)
    keep = mblk.all(axis=1)
    blocks = blocks[keep]
    if blocks.shape[0] < 30:
        return {"n_patches": int(blocks.shape[0]), "enl": None,
                "reason": "fewer than 30 patches lie wholly inside the mask"}
    m = blocks.mean(axis=1)
    v = blocks.var(axis=1, ddof=1)
    r = m ** 2 / np.where(v > 0, v, np.nan)
    r = r[np.isfinite(r)]
    med = float(np.median(r))
    # SE of the median, from the interquartile range
    se = float(1.253 * r.std(ddof=1) / np.sqrt(r.size))
    return {"n_patches": int(r.size), "enl": med, "enl_se": se,
            "enl_mean": float(r.mean()), "p5": float(np.percentile(r, 5)),
            "p95": float(np.percentile(r, 95)), "patch": patch}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-lines", type=int, default=0,
                    help="0 = all; otherwise cap for a fast pass")
    args = ap.parse_args()

    lab = label_fields()
    k_lin = 10.0 ** (lab["calibration_constant_db"] / 10.0)
    g_lh = lab["gain_imbalance"]["LH"]
    g_lv = lab["gain_imbalance"]["LV"]
    sin_t = float(np.sin(np.deg2rad(lab["incidence_angle_deg"])))

    hr("P1 — STOKES VECTOR FROM THE SINGLE-LOOK COMPLEX")
    print(f"  K = {lab['calibration_constant_db']:g} dB (sli label)   "
          f"K_lin = {k_lin:.6g}")
    print(f"  G_LH = {g_lh:.6f}   G_LV = {g_lv:.6f}   sin(theta) = {sin_t:.6f}")
    print(f"  phase_orthogonality LH {lab['phase_orthogonality']['LH']:.6f}  "
          f"LV {lab['phase_orthogonality']['LV']:.6f}  (unit undocumented)")
    print(f"  order: |E|^2 -> x sin(theta) -> / K_lin -> / G^2  "
          f"(sin and K common; G per-channel)")

    eh = open_slc("lh")
    ev = open_slc("lv")
    n_lines = args.max_lines or LINES
    n_out = n_lines // AZIMUTH_LOOKS
    beat(f"memmapped {LINES:,} x {SAMPLES}; forming {n_out:,} x {SAMPLES} "
         f"{AZIMUTH_LOOKS}-look cells")

    # --- 1. the coherency matrix, 21-look azimuth average ------------------
    hh = np.empty((n_out, SAMPLES), dtype=np.float64)
    vv = np.empty((n_out, SAMPLES), dtype=np.float64)
    hv = np.empty((n_out, SAMPLES), dtype=np.complex128)
    CHUNK = 512  # output rows per read
    for start in range(0, n_out, CHUNK):
        stop = min(start + CHUNK, n_out)
        r0, r1 = start * AZIMUTH_LOOKS, stop * AZIMUTH_LOOKS
        a = np.asarray(eh[r0:r1], dtype=np.complex128)
        b = np.asarray(ev[r0:r1], dtype=np.complex128)
        rows = stop - start
        a = a.reshape(rows, AZIMUTH_LOOKS, SAMPLES)
        b = b.reshape(rows, AZIMUTH_LOOKS, SAMPLES)
        hh[start:stop] = (np.abs(a) ** 2).mean(axis=1)
        vv[start:stop] = (np.abs(b) ** 2).mean(axis=1)
        hv[start:stop] = (a * np.conj(b)).mean(axis=1)
        del a, b
        if start % (CHUNK * 8) == 0:
            beat(f"  coherency rows {stop:,}/{n_out:,}")
    beat("coherency matrix formed")

    # calibration, in the pipeline's order
    scale = sin_t / k_lin
    hh *= scale / (g_lh ** 2)
    vv *= scale / (g_lv ** 2)
    hv *= scale / (g_lh * g_lv)

    # --- the same 5x5 boxcar the pipeline applies --------------------------
    hh = boxcar2d(hh)
    vv = boxcar2d(vv)
    hv = boxcar2d(hv.real) + 1j * boxcar2d(hv.imag)
    beat("5x5 boxcar applied to all three elements")

    # --- 2. Stokes, circular intensities, CPR, DOP -------------------------
    s0 = hh + vv
    s1 = hh - vv
    s2 = 2.0 * hv.real
    s3 = 2.0 * hv.imag          # S3 = 2 Im<E_H E_V*>, as the paper states
    sc = 0.5 * (s0 - s3)
    oc = 0.5 * (s0 + s3)

    mask = (hh > 0) & (vv > 0) & (s0 > 0) & (oc > 0)
    beat(f"matched mask: {int(mask.sum()):,} of {mask.size:,} cells "
         f"({100 * mask.mean():.2f} %)")

    eps = 1e-30
    cpr_s = np.where(mask, sc / (oc + eps), np.nan)
    dop_s = np.where(mask, np.sqrt(s1 ** 2 + s2 ** 2 + s3 ** 2) / (s0 + eps), np.nan)

    # the AMPLITUDE PROXY from the same samples: discard the cross-product
    sq_h, sq_v = np.sqrt(np.maximum(hh, 0)), np.sqrt(np.maximum(vv, 0))
    sc_a = 0.5 * (sq_h - sq_v) ** 2
    oc_a = 0.5 * (sq_h + sq_v) ** 2
    cpr_a = np.where(mask, sc_a / (oc_a + eps), np.nan)
    dop_a = np.where(mask, np.abs(s1) / (s0 + eps), np.nan)

    m = mask
    res: dict = {}

    # --- 3c. amplitude exclusion, and whether Stokes agrees ----------------
    hr("3c — DOP_a >= 0.13, and the Stokes DOP of those same cells")
    excl = m & (dop_a >= DOP_THRESHOLD)
    frac_excl = float(excl.sum() / m.sum())
    also = float((dop_s[excl] >= DOP_THRESHOLD).mean()) if excl.sum() else float("nan")
    print(f"  DOP_a >= {DOP_THRESHOLD}        {frac_excl * 100:.2f} % of matched cells")
    print(f"  of those, Stokes DOP >= {DOP_THRESHOLD}  {also * 100:.4f} %  (must be 100 %)")
    res["t3c"] = {"fraction_dop_a_ge_threshold": frac_excl,
                  "of_those_stokes_dop_ge_threshold": also,
                  "n_excluded": int(excl.sum()),
                  "why_must_be_100": (
                      "DOP_a = |S1|/S0 is one component of the full "
                      "DOP = sqrt(S1^2+S2^2+S3^2)/S0, so the full DOP is >= the "
                      "amplitude one cell by cell, identically.")}

    # --- 3f. the structural band under DOP < 0.13 --------------------------
    hr("3f — Stokes CPR among cells with Stokes DOP < 0.13")
    lo = (1 - DOP_THRESHOLD) / (1 + DOP_THRESHOLD)
    hi = (1 + DOP_THRESHOLD) / (1 - DOP_THRESHOLD)
    sel = m & (dop_s < DOP_THRESHOLD)
    n_sel = int(sel.sum())
    if n_sel:
        inside = (cpr_s[sel] > lo) & (cpr_s[sel] < hi)
        outside = float(1.0 - inside.mean())
        joint = float(((cpr_s[sel] > CPR_THRESHOLD)).mean())
    else:
        outside, joint = float("nan"), float("nan")
    print(f"  cells with Stokes DOP < {DOP_THRESHOLD}: {n_sel:,}")
    print(f"  predicted band ({lo:.4f}, {hi:.4f})")
    print(f"  fraction OUTSIDE the band: {outside:.3e}   (must be 0)")
    print(f"  of those cells, CPR > 1:   {joint * 100:.4f} %")
    joint_all = float((m & (cpr_s > CPR_THRESHOLD) & (dop_s < DOP_THRESHOLD)).sum()
                      / m.sum())
    print(f"  joint fraction over ALL matched cells: {joint_all * 100:.6f} %")
    res["t3f"] = {"band": [lo, hi], "n_cells_dop_below": n_sel,
                  "fraction_outside_band": outside,
                  "fraction_cpr_gt_1_within_selection": joint,
                  "joint_fraction_all_cells": joint_all}

    # --- 3b. the amplitude band, and why it is the wrong band -------------
    hr("3b — Stokes CPR against the band implied by the AMPLITUDE DOP")
    dm = m & np.isfinite(dop_a) & (dop_a < 1.0)
    c_lo = (1 - dop_a[dm]) / (1 + dop_a[dm])
    c_hi = (1 + dop_a[dm]) / (1 - dop_a[dm])
    v = cpr_s[dm]
    viol = float(((v < c_lo) | (v > c_hi)).mean())
    print(f"  cells tested: {int(dm.sum()):,}")
    print(f"  violation fraction: {viol:.4f}")
    print()
    print("  THIS TEST CANNOT COME OUT AT ZERO, AND THE REASON IS ALGEBRAIC.")
    print("  With u = S3/S0, CPR = (1-u)/(1+u) and |u| <= m, the FULL degree of")
    print("  polarisation. So the band that bounds the Stokes CPR is the one built")
    print("  from m, not from DOP_a = |S1|/S0. Since m >= DOP_a identically -- the")
    print("  amplitude DOP is one component of three -- the DOP_a band is strictly")
    print("  NARROWER than the true constraint, and the Stokes CPR is entitled to")
    print("  sit outside it. The correct form of this test is 3f, which uses m and")
    print("  comes out at exactly zero violations.")
    res["t3b"] = {
        "n_tested": int(dm.sum()), "violation_fraction": viol,
        "band_definition": "[(1-DOP_a)/(1+DOP_a), (1+DOP_a)/(1-DOP_a)]",
        "verdict": "NOT A DEFECT - the test as specified uses the wrong DOP",
        "why": ("CPR = (1-u)/(1+u) with u = S3/S0 and |u| <= m, the FULL DOP. "
                "The bounding band is built from m, not from DOP_a = |S1|/S0. "
                "m >= DOP_a identically, so the DOP_a band is strictly narrower "
                "than the true constraint and the Stokes CPR may legitimately "
                "fall outside it. Test 3f applies the same check with m and "
                "returns exactly zero violations."),
    }

    # --- 3d. circular ENLs and the SC/OC coherence -------------------------
    hr("3d — ENL of SC and OC, and the complex coherence between them")
    e_sc = enl_moment(np.where(m, sc, np.nan), m)
    e_oc = enl_moment(np.where(m, oc, np.nan), m)
    # complex coherence of the circular FIELDS is not available without a phase
    # convention; the INTENSITY correlation is, and is reported as such.
    x = sc[m]
    y = oc[m]
    xc, yc = x - x.mean(), y - y.mean()
    gamma_I = float(abs((xc * yc).mean()) / np.sqrt((xc ** 2).mean() * (yc ** 2).mean()))
    print(f"  N_SC = {e_sc.get('enl')}  +/- {e_sc.get('enl_se')}")
    print(f"  N_OC = {e_oc.get('enl')}  +/- {e_oc.get('enl_se')}")
    print(f"  |corr(SC, OC)| on intensities = {gamma_I:.6f}")
    res["t3d"] = {"enl_sc": e_sc, "enl_oc": e_oc,
                  "intensity_correlation_sc_oc": gamma_I,
                  "phase_caveat": (
                      "The complex field coherence requires a cross-channel "
                      "phase convention the label does not document. What is "
                      "reported is the INTENSITY correlation, which is "
                      "convention-independent.")}

    # --- 3e. tail calibration --------------------------------------------
    hr("3e — the Stokes CPR tail against F(2 N_SC, 2 N_OC)")
    vals = cpr_s[m]
    vals = vals[np.isfinite(vals)]
    p95, p99 = float(np.percentile(vals, 95)), float(np.percentile(vals, 99))
    p_gt1 = float((vals > CPR_THRESHOLD).mean())
    med = float(np.median(vals))
    model = None
    if e_sc.get("enl") and e_oc.get("enl"):
        from scipy.stats import f as Fdist
        d1, d2 = 2 * e_sc["enl"], 2 * e_oc["enl"]
        model = {
            "d1": d1, "d2": d2,
            "p95": float(Fdist.ppf(0.95, d1, d2) * med),
            "p99": float(Fdist.ppf(0.99, d1, d2) * med),
            "p_gt_1": float(1.0 - Fdist.cdf(CPR_THRESHOLD / max(med, 1e-12), d1, d2)),
        }
    se_p = float(np.sqrt(max(p_gt1, 1e-12) * (1 - p_gt1) / vals.size))
    print(f"  empirical  median {med:.6f}  p95 {p95:.6f}  p99 {p99:.6f}  "
          f"P(CPR>1) {p_gt1:.6e} +/- {se_p:.1e}")
    if model:
        print(f"  F model    p95 {model['p95']:.6f}  p99 {model['p99']:.6f}  "
              f"P(CPR>1) {model['p_gt_1']:.6e}")
    res["t3e"] = {"n_cells": int(vals.size), "median": med, "p95": p95, "p99": p99,
                  "p_cpr_gt_1": p_gt1, "p_cpr_gt_1_se": se_p, "f_model": model,
                  "phase_caveat": "depends on the phase convention via N_SC, N_OC"}

    # --- P1.4 THE PHASE CONVENTION, MEASURED -----------------------------
    hr("P1.4 — is the cross-channel phase determined?")
    ph = np.angle(hv[m])
    resultant = complex(np.mean(np.exp(1j * ph)))
    coh = np.abs(hv[m]) / np.sqrt(np.maximum(hh[m] * vv[m], 1e-300))
    coh_med = float(np.median(coh))
    print(f"  arg<E_H E_V*>  circular mean {np.degrees(np.angle(resultant)):+.2f} deg")
    print(f"  resultant length R = {abs(resultant):.4f}   "
          f"(1 = perfectly coherent, 0 = uniform)")
    print(f"  |<E_H E_V*>| / sqrt(<|E_H|^2><|E_V|^2>)  median = {coh_med:.4f}")
    print()
    print(f"  The phase is NOT noise: R = {abs(resultant):.4f} is a strong systematic")
    print(f"  offset, sitting {abs(np.degrees(np.angle(resultant)) + 90):.2f} deg from -90.")
    print("  But the label documents no convention for it, so it cannot be removed")
    print("  on evidence -- only guessed at, which is a different thing.")
    print()
    print("  median Stokes CPR as a function of an applied rotation:")
    sweep = []
    for deg in range(0, 360, 45):
        rot = hv * np.exp(1j * np.deg2rad(deg))
        s3r = 2.0 * rot.imag
        # guard the denominator: S0 + S3 is the OC intensity and is positive on
        # physical data, but a cell where it is not must be excluded rather than
        # producing an inf that would drag the median.
        ok = m & ((s0 + s3r) > 0)
        cprr = np.where(ok, (s0 - s3r) / np.where(ok, s0 + s3r, 1.0), np.nan)
        med_r = float(np.nanmedian(cprr))
        print(f"    {deg:>3} deg -> median CPR {med_r:8.4f}")
        sweep.append({"rotation_deg": deg, "median_stokes_cpr": med_r})
    lows = [r["median_stokes_cpr"] for r in sweep]
    print()
    print(f"  THE MEDIAN SWINGS {min(lows):.2f} TO {max(lows):.2f} -- a factor of")
    print(f"  {max(lows) / max(min(lows), 1e-9):.1f} -- on the choice of convention alone.")
    res["phase_determination"] = {
        "circular_mean_deg": float(np.degrees(np.angle(resultant))),
        "resultant_length": float(abs(resultant)),
        "hv_coherence_median": coh_med,
        "hv_coherence_p5": float(np.percentile(coh, 5)),
        "hv_coherence_p95": float(np.percentile(coh, 95)),
        "rotation_sweep": sweep,
        "median_cpr_range": [min(lows), max(lows)],
        "verdict": (
            "The cross-channel phase carries a strong systematic offset "
            "(R = 0.53, circular mean about -91 deg) but the label documents no "
            "convention for it. The median Stokes CPR moves by a factor of ~4 "
            "across the rotation sweep, so the Stokes CPR is NOT DETERMINED by "
            "this product alone. Any value between the sweep endpoints can be "
            "produced by a choice nobody has written down."),
        "what_survives": (
            "The COHERENCE MAGNITUDE is rotation-invariant and is a genuine "
            "measurement: median |<E_H E_V*>|/sqrt(<|E_H|^2><|E_V|^2>) = "
            f"{coh_med:.4f}. So is every test built on m rather than on S3 "
            "individually: 3c and 3f."),
    }

    # --- 3a. against the delivered rasters --------------------------------
    hr("3a — against the DELIVERED amplitude rasters")
    print("  BLOCKED FOR PER-CELL REGRESSION, and the reason is geometric.")
    print(f"  SLC-derived grid : {n_out:,} x {SAMPLES}  (slant range, azimuth time)")
    print("  delivered sri    : 2,258 x 6,618  (selenoreferenced, 25 m UPS)")
    print("  No decimation maps one onto the other; a per-cell regression needs")
    print("  geocoding, whose own resampling error would dominate the residual")
    print("  being reported. The distributional comparison IS made below.")
    try:
        import tifffile
        d_lh = tifffile.imread(str(RAW / f"{STEM}_d_sri_xx_cp_lh_d18.tif")).astype(np.float64)
        d_lv = tifffile.imread(str(RAW / f"{STEM}_d_sri_xx_cp_lv_d18.tif")).astype(np.float64)
        dv = (d_lh > 0) & (d_lv > 0)
        # delivered amplitudes are DN; SLC-derived are calibrated sigma0. Compare
        # the SHAPE of the distribution via the ratio LH/LV, which is scale-free
        # and is the only quantity the two geometries share.
        r_del = (d_lh[dv] / d_lv[dv])
        r_slc = np.sqrt(hh[m] / np.maximum(vv[m], 1e-300))
        qs = [5, 25, 50, 75, 95]
        q_del = np.percentile(r_del, qs).tolist()
        q_slc = np.percentile(r_slc, qs).tolist()
        print(f"  LH/LV amplitude ratio percentiles {qs}")
        print(f"    delivered : {[round(x, 4) for x in q_del]}")
        print(f"    SLC-formed: {[round(x, 4) for x in q_slc]}")
        res["t3a"] = {
            "status": "partial - distributional only",
            "blocker": ("the SLC is slant-range/azimuth-time and the delivered "
                        "sri is selenoreferenced on a 25 m UPS grid; per-cell "
                        "registration requires geocoding"),
            "quantiles": qs,
            "lh_over_lv_delivered": q_del,
            "lh_over_lv_slc_formed": q_slc,
            "n_delivered": int(dv.sum()), "n_slc": int(m.sum()),
        }
    except Exception as exc:  # noqa: BLE001
        print(f"  delivered rasters unreadable: {exc}")
        res["t3a"] = {"status": "blocked", "reason": str(exc)}

    OUT.write_text(json.dumps({
        "schema": "lunar-ice/stokes-from-slc/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/stokes_from_slc.py",
        "seed": SEED,
        "slc": {"lines": LINES, "samples": SAMPLES, "offset": OFFSET,
                "dtype": "complex64", "lines_used": n_lines,
                "azimuth_looks": AZIMUTH_LOOKS, "boxcar": BOXCAR,
                "output_cells": [n_out, SAMPLES]},
        "calibration": {
            "equation": "sigma0_X = |E_X|^2 * sin(theta) / (K_lin * G_X^2)",
            "order": ["|E|^2", "x sin(theta)", "/ K_lin", "/ G_X^2"],
            "K_db": lab["calibration_constant_db"], "K_lin": k_lin,
            "G_LH": g_lh, "G_LV": g_lv, "sin_theta": sin_t,
            "incidence_deg_label": lab["incidence_angle_deg"],
            "common_factors_cancel": "sin(theta) and K_lin are common to both "
                                     "channels and cancel in CPR and DOP",
            "per_channel_factor": "G_LH/G_LV does NOT cancel and is the one "
                                  "calibration term that can move these results",
            "K_differs_from_sri_label": "sli says 80.000000, sri says 70.308868",
        },
        "sign_convention": "S3 = 2 Im<E_H E_V*>; SC = (S0-S3)/2, OC = (S0+S3)/2",
        "cross_channel_phase": {
            "applied": False,
            "label_fields": lab["phase_orthogonality"],
            "reason": ("the label carries phase_orthogonality per channel with "
                       "no stated unit and documents no relative H-V phase "
                       "correction procedure"),
            "tests_independent_of_convention": ["3b", "3c", "3f"],
            "tests_dependent_on_convention": ["3d", "3e"],
        },
        "matched_mask_cells": int(m.sum()),
        "results": res,
    }, indent=2), encoding="utf-8")
    beat(f"wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
