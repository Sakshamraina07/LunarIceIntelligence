"""
snr_control.py -- thermal noise, the discs compared fairly, and transmit
non-ideality, on both passes of the complex product. (v18a referee reports:
N1, N2, N7c; also writes the per-cell cache N3 reads)

    python backend/scripts/snr_control.py [--workers 8]

WHY
---
Receiver noise is unpolarized: added to a weak cell it pushes the sample CPR
toward 1 and the sample DOP toward 0, where the published rule selects. So:

N1  Per-cell SNR. SNR_X = (boxcar'd calibrated intensity of channel X) /
    NESZ_X. NESZ model (primary): the label's nes0_coeff_0 per channel,
    constant over the swath -- the -31.5 dB the manuscript quotes. The label
    also carries nes0_coeff_1 with no stated independent variable; as a
    sensitivity, NESZ_X(j) = coeff_0 + coeff_1 j, j the SLC range-sample
    index (the only variable of the SLC that keeps it positive over the
    swath). Selection rates are tabulated by min(SNR_H, SNR_V) in bins
    < 0, 0-3, 3-6, 6-10, > 10 dB crossed with window completeness (full 5 x 5
    window of non-zero samples in both channels, or partial), for the whole
    frame, F2's 663 signal cells and the discs by class and pass. Then:
      * NOISE-CORRECTED: C_HH - n_H and C_VV - n_V on the averaged (boxcar'd)
        covariance, C_HV untouched (noise is independent between channels
        and zero-mean in the cross product); a cell whose corrected power is
        not positive in either channel is dropped. The Stokes vector, R,
        the sample DOP and N_hat (31 x 31, Var ln R) are re-formed from it.
      * SNR FLOORS 3 dB and 6 dB: cells whose min SNR is below the floor are
        excluded from the rule, the IUT and N_hat's window.
    Each variant reports frame fractions, F2's selections and disc rates.
N2  The discs of crater_level_real, compared fairly: per-pass x class tables;
    coherence-stratified rates and the Mantel-Haenszel odds ratio of
    shadowed against sunlit discs; a logistic regression of "fires" on disc
    median coherence, ln N_hat, pass, class and median min-SNR; the per-disc
    mixture simulation for every class (per-disc probabilities kept); the
    discs' pairwise overlap; and 5 x 5-lattice block-bootstrap intervals.
N7c Transmit ellipticity. A transmitted wave of axial ratio AR is the
    intended circular state plus the opposite sense at amplitude
    eps = (AR_lin - 1)/(AR_lin + 1), AR_lin = 10^(AR_dB/20). To first order
    this couples the received circular channels: z' = D z,
    D = [[1, eps e^{i phi}], [eps e^{i phi}, 1]] in (SC, OC), with the phase
    phi unknown and swept over 0, 90, 180, 270 deg; C' = D C D^H. Axial
    ratios: the DFSAR L-band hybrid-pol specification 0.4 dB (Bhiravarasu et
    al. 2021, Table 1), 0.5 and 1 dB.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_erosion, uniform_filter
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runinfo import run_info  # noqa: E402
import stokes_from_slc as SFS  # noqa: E402
import enl_logratio as L  # noqa: E402
import decision_rule as DR  # noqa: E402
import f2_complex_product as FCP  # noqa: E402
import f2_maximum as F2M  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT_N1 = BASE_DIR / "docs" / "snr_control.json"
OUT_N2 = BASE_DIR / "docs" / "crater_level_real.json"
OUT_N7 = BASE_DIR / "docs" / "slc_chain.json"
CACHE_N3 = BASE_DIR / "data" / "derived" / "v18" / "cells_by_disc.npz"
GRID_JSON = BASE_DIR / "docs" / "complex_grid_correlation.json"
SEED_MIX = 20261010
DOP_T = 0.13
SNR_BINS = [(-np.inf, 0.0, "< 0 dB"), (0.0, 3.0, "0-3 dB"), (3.0, 6.0, "3-6 dB"),
            (6.0, 10.0, "6-10 dB"), (10.0, np.inf, "> 10 dB")]
COH_BINS = [(-1.0, 0.4, "< 0.4"), (0.4, 0.5, "0.4-0.5"), (0.5, 0.6, "0.5-0.6"), (0.6, 2.0, ">= 0.6")]
AR_DB = (0.4, 0.5, 1.0)
PHIS = (0.0, 90.0, 180.0, 270.0)
PER_DISC = 40
BOOT_B = 2000

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


# ---------------------------------------------------------------- loading
def load(pid, psr, max_lines=0):
    SFS.configure(pid)
    src = (SFS.RAW / f"{SFS.STEM}_d_sli_xx_cp_xx_d18.xml").read_text(encoding="utf-8", errors="replace")
    c0 = [float(v) for v in re.findall(r"<isda:nes0_coeff_0>([^<]+)<", src)]
    c1 = [float(v) for v in re.findall(r"<isda:nes0_coeff_1>([^<]+)<", src)]
    hh, vv, hv, info = SFS.build_coherency(max_lines, smooth=False)
    raw_both = (hh > 0) & (vv > 0)
    full = binary_erosion(raw_both, np.ones((5, 5), dtype=bool))
    hh, vv = SFS.boxcar2d(hh), SFS.boxcar2d(vv)
    hv = SFS.boxcar2d(hv.real) + 1j * SFS.boxcar2d(hv.imag)
    spec, g, tx, ty = FCP.tie_grid(pid)
    rows, cols = hh.shape
    li = SFS.AZIMUTH_LOOKS * np.arange(rows) + (SFS.AZIMUTH_LOOKS - 1) / 2.0
    LI, SI = np.meshgrid(li, np.arange(cols), indexing="ij")
    xc = FCP.interp(tx, LI, SI, spec).astype(np.float64)
    yc = FCP.interp(ty, LI, SI, spec).astype(np.float64)
    del LI, SI
    gpsr, apsr = psr
    base = {"zero_based": 0.0, "half_pixel": 0.5, "one_based": 1.0}[gpsr.base]
    pl = np.rint(gpsr.lpo - yc / gpsr.scale_m - base).astype(np.int64)
    ps = np.rint(gpsr.spo + xc / gpsr.scale_m - base).astype(np.int64)
    inb = (pl >= 0) & (pl < apsr.shape[0]) & (ps >= 0) & (ps < apsr.shape[1])
    in_psr = np.zeros(xc.shape, dtype=bool)
    in_psr[inb] = apsr[pl[inb], ps[inb]] > 0.5
    j = np.broadcast_to(np.arange(cols, dtype=np.float64)[None, :], hh.shape)
    return {"pass": pid, "hh": hh, "vv": vv, "hv": hv, "full": full, "raw_both": raw_both,
            "x": xc, "y": yc, "psr": in_psr, "c0": c0, "c1": c1, "j": j, "shape": (rows, cols),
            "azimuth_looks": SFS.AZIMUTH_LOOKS}


def nesz(P, model):
    if model == "constant":
        return P["c0"][0], P["c0"][1]
    return P["c0"][0] + P["c1"][0] * P["j"], P["c0"][1] + P["c1"][1] * P["j"]


def stokes_fields(hh, vv, hv):
    s0, s1, s2, s3 = hh + vv, hh - vv, 2.0 * hv.real, -2.0 * hv.imag      # physical sign
    m = (hh > 0) & (vv > 0) & (s0 > 0)
    sc, oc = 0.5 * (s0 - s3), 0.5 * (s0 + s3)
    ok = m & (sc > 0) & (oc > 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        lr = np.where(ok, np.log(np.where(ok, sc, 1.0) / np.where(ok, oc, 1.0)), np.nan)
        dop = np.where(m, np.sqrt(s1 ** 2 + s2 ** 2 + s3 ** 2) / np.where(m, s0, 1.0), np.nan)
        coh = np.where(m, np.abs(hv) / np.sqrt(np.maximum(hh * vv, 1e-300)), np.nan)
        gam = np.where(m, np.sqrt(s1 ** 2 + s2 ** 2) / np.sqrt(np.maximum(s0 ** 2 - s3 ** 2, 1e-300)), np.nan)
    return ok, lr, dop, coh, gam, s0


def evaluate(hh, vv, hv, use_extra, qtab, with_iut=True):
    ok, lr, dop, coh, gam, s0 = stokes_fields(hh, vv, hv)
    if use_extra is not None:
        ok = ok & use_extra
        lr = np.where(ok, lr, np.nan)
    R = np.exp(lr)
    rule = ok & (dop < DOP_T) & (R > 1.0)
    out = {"ok": ok, "R": R, "dop": dop, "coh": coh, "gam": gam, "rule": rule, "s0": s0}
    if with_iut:
        nh, _ = L.local_n(lr, ok)
        fin = ok & np.isfinite(nh)
        iut = np.zeros_like(ok)
        iut[fin] = (R[fin] > DR.crit(nh[fin])) & (dop[fin] < DR.q05_at(nh[fin], qtab))
        out["nh"], out["iut"] = nh, iut
    return out


def ellipticity(hh, vv, hv, eps, phi_deg):
    """C' = D C D^H in the circular basis (SC, OC); back to hh, vv, hv."""
    s0, s1, s2, s3 = hh + vv, hh - vv, 2.0 * hv.real, -2.0 * hv.imag
    sc, oc = 0.5 * (s0 - s3), 0.5 * (s0 + s3)
    x = 0.5 * (s1 + 1j * s2)                      # <z_SC z_OC*>, |x|^2 = (S1^2 + S2^2)/4
    e = eps * np.exp(1j * np.deg2rad(phi_deg))
    # D = [[1, e], [e, 1]]: C' = D C D^H
    sc2 = sc + np.abs(e) ** 2 * oc + 2 * (np.conj(e) * x).real
    oc2 = oc + np.abs(e) ** 2 * sc + 2 * (e * x).real
    x2 = x + e * oc + np.conj(e) * sc + np.abs(e) ** 2 * np.conj(x)
    s0n, s3n = sc2 + oc2, oc2 - sc2
    s1n, s2n = 2 * x2.real, 2 * x2.imag
    hh2, vv2 = 0.5 * (s0n + s1n), 0.5 * (s0n - s1n)
    hv2 = 0.5 * s2n - 0.5j * s3n                    # s3 = -2 Im hv  ->  Im hv = -s3/2
    return hh2, vv2, hv2


def compact(var_out, frame, f2, pid, f2mask):
    """Record each not-yet-recorded variant's frame and F2 figures, then keep
    only the boolean masks the discs need (the full fields of 17 variants
    would not fit in memory)."""
    for v, E in var_out.items():
        if pid in frame[v]:
            continue
        okm = E["ok"]
        rec = {"cells_matched": int(okm.sum()), "joint": int(E["rule"].sum()),
               "joint_fraction": float(E["rule"].sum() / max(okm.sum(), 1)),
               "iut": int(E["iut"].sum()) if E.get("iut") is not None else None}
        if "dop" in E:
            rec.update({"dop_below_0p13": int((okm & (E["dop"] < DOP_T)).sum()),
                        "dop_below_fraction": float((okm & (E["dop"] < DOP_T)).sum() / max(okm.sum(), 1)),
                        "unphysical_dop_gt_1": int((okm & (E["dop"] > 1.0)).sum())})
        frame[v][pid] = rec
        if pid == "20200808":
            f2[v] = {"cells": int(f2mask.sum()), "cells_retained": int((f2mask & okm).sum()),
                     "published_rule_selects": int((f2mask & E["rule"]).sum()),
                     "iut_selects": int((f2mask & E["iut"]).sum()) if E.get("iut") is not None else None}
        if v != "base":
            var_out[v] = {"ok": E["ok"], "rule": E["rule"], "iut": E.get("iut")}


# ---------------------------------------------------------------- discs
def tile(P, signal, n_target, radius):
    idx = np.flatnonzero(signal.ravel())
    x, y = P["x"].ravel()[idx], P["y"].ravel()[idx]
    pitch = 2 * radius
    cx, cy = np.rint(x / pitch).astype(np.int64), np.rint(y / pitch).astype(np.int64)
    d = np.hypot(x - cx * pitch, y - cy * pitch)
    keep = d <= radius
    idx, cx, cy, d = idx[keep], cx[keep], cy[keep], d[keep]
    key = (cx - cx.min()) * (cy.max() - cy.min() + 1) + (cy - cy.min())
    order = np.lexsort((d, key))
    idx, key, cx, cy = idx[order], key[order], cx[order], cy[order]
    start = np.r_[0, np.flatnonzero(np.diff(key)) + 1]
    size = np.diff(np.r_[start, key.size])
    discs = []
    for s, n in zip(start, size):
        if n < n_target:
            continue
        discs.append({"cells": idx[s:s + n_target], "cx": int(cx[s]), "cy": int(cy[s])})
    return discs


def pct(a, q):
    a = np.asarray(a)
    return dict(zip(map(str, q), np.percentile(a, q).tolist())) if a.size else None


def wilson(k, n):
    return FCP.wilson(k, n)


def rate_block(k, n):
    return {"k": int(k), "n": int(n), "rate": (k / n) if n else None, "wilson95": wilson(k, n)}


# ---------------------------------------------------------------- statistics
def mantel_haenszel(strata):
    """strata: list of (a, b, c, d) = exposed fires / not, unexposed fires / not.
    OR_MH with its Robins-Breslow-Greenland interval (two-sided, level 0.95)."""
    num = den = 0.0
    P_R = P_S_Q = Q_S = R_sum = S_sum = 0.0
    for a, b, c, d in strata:
        n = a + b + c + d
        if n == 0:
            continue
        R, S = a * d / n, b * c / n
        Pp, Q = (a + d) / n, (b + c) / n
        num += R; den += S
        P_R += Pp * R; P_S_Q += Pp * S + Q * R; Q_S += Q * S
    if den == 0 or num == 0:
        return {"or": None}
    orr = num / den
    var = P_R / (2 * num ** 2) + P_S_Q / (2 * num * den) + Q_S / (2 * den ** 2)
    se = np.sqrt(var)
    return {"or": orr, "ci95": [float(orr * np.exp(-1.96 * se)), float(orr * np.exp(1.96 * se))],
            "se_log_or": float(se)}


def logistic(X, y, names):
    """IRLS; coefficients, SEs from the inverse Fisher information."""
    b = np.zeros(X.shape[1])
    for _ in range(100):
        eta = X @ b
        p = 1 / (1 + np.exp(-eta))
        W = p * (1 - p)
        H = X.T @ (X * W[:, None])
        g = X.T @ (y - p)
        step = np.linalg.solve(H + 1e-10 * np.eye(len(b)), g)
        b = b + step
        if np.max(np.abs(step)) < 1e-10:
            break
    p = 1 / (1 + np.exp(-(X @ b)))
    H = X.T @ (X * (p * (1 - p))[:, None])
    cov = np.linalg.inv(H)
    se = np.sqrt(np.diag(cov))
    ll = float(np.sum(y * np.log(np.clip(p, 1e-300, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-300, 1))))
    return {"coefficients": {n: {"estimate": float(v), "se": float(s), "z": float(v / s),
                                 "p_two_sided": float(2 * norm.sf(abs(v / s)))}
                             for n, v, s in zip(names, b, se)},
            "n": int(len(y)), "events": int(y.sum()), "log_likelihood": ll}


# ---------------------------------------------------------------- mixture
def _mixture_worker(args):
    seed, mask, discs, per_disc, rsc, roc = args
    rng = np.random.default_rng(seed)
    H, W = mask.shape
    M = 4 + 15

    def field(Lk, batch, cpr, gam):
        a, b = cpr / (1 + cpr), 1 / (1 + cpr)
        sc = np.zeros((batch, H + 2 * M, W + 2 * M)); oc = np.zeros_like(sc)
        x = np.zeros_like(sc, dtype=complex)
        for _ in range(Lk):
            wo = F2M.ar1_stationary(rng, (H + 2 * M, W + 2 * M), *roc, batch)
            ws = F2M.ar1_stationary(rng, (H + 2 * M, W + 2 * M), *rsc, batch)
            zo = np.sqrt(b) * wo
            zs = np.sqrt(a) * (gam * wo + np.sqrt(1 - gam * gam) * ws)
            sc += np.abs(zs) ** 2; oc += np.abs(zo) ** 2; x += zs * np.conj(zo)
        f = lambda v: uniform_filter(v, size=(1, 5, 5), mode="reflect")  # noqa: E731
        return f(sc / Lk), f(oc / Lk), f(x.real / Lk) + 1j * f(x.imag / Lk)

    cal = {}
    for Lk in range(1, 25):
        bs, bo, _ = field(Lk, 8, 1.0, 0.0)
        cal[Lk] = float(L.n_from_var(np.var(np.log(bs / bo)[:, M:-M, M:-M], ddof=1)))
    ks = np.array(sorted(cal)); ns = np.array([cal[k] for k in ks])
    out = []
    for d in discs:
        Lk = int(ks[np.argmin(np.abs(ns - d["median_N_hat"]))])
        bs, bo, bx = field(Lk, per_disc, d["median_cpr"], min(d["median_gamma_c"], 0.999))
        r = (bs / bo)[:, M:-M, M:-M][:, mask]
        m = (np.sqrt((bs - bo) ** 2 + 4 * np.abs(bx) ** 2) / (bs + bo))[:, M:-M, M:-M][:, mask]
        k = ((m < DOP_T) & (r > 1.0)).sum(axis=1)
        out.append((d["id"], float((k >= 1).mean()), float((k >= 5).mean()), Lk))
    return out


# ---------------------------------------------------------------- main
def main() -> int:
    import validate_psr_vs_lola as V
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--max-lines", type=int, default=0, help="smoke test: SLC lines per pass; writes nothing")
    args = ap.parse_args()
    t0 = time.time()
    dr = json.loads((BASE_DIR / "docs" / "decision_rule.json").read_text(encoding="utf-8"))
    qtab = {int(k): v for k, v in dr["dop_quantile_table"]["q05"].items()}
    foot = json.loads(FCP.FOOT.read_text(encoding="utf-8"))["target"]
    x0, y0 = FCP.stereo(foot["lat_deg"], foot["lon_deg"])
    psr = V.load_pds("LPSR_75S_120M_201608")
    prev = json.loads(OUT_N2.read_text(encoding="utf-8"))
    n_target = prev["discs"]["signal_cells_per_disc"]
    print("=" * 78); print("N1 / N2 / N7c — SNR, discs, transmit ellipticity"); print("=" * 78)

    variants = ["base", "noise_corrected", "noise_corrected_linear_nesz", "floor_3dB", "floor_6dB"] + \
               [f"ellipticity_{a:g}dB_phi{int(p)}" for a in AR_DB for p in PHIS]
    frame = {v: {} for v in variants}
    f2 = {v: None for v in variants}
    disc_rows = []                       # one per disc, baseline + per-variant counts
    snr_tables, sel_snr = {}, {}
    cache = {k: [] for k in ("disc", "cpr", "gam", "nh", "s0", "cls", "pass")}
    layout = None
    for pid in ("20200808", "20200305"):
        P = load(pid, psr, args.max_lines)
        hh, vv, hv = P["hh"], P["vv"], P["hv"]
        nH, nV = nesz(P, "constant")
        snr_h = 10 * np.log10(np.maximum(hh / nH, 1e-30))
        snr_v = 10 * np.log10(np.maximum(vv / nV, 1e-30))
        min_snr = np.minimum(snr_h, snr_v)
        base = evaluate(hh, vv, hv, None, qtab)
        signal = base["ok"] & (hh > P["c0"][0]) & (vv > P["c0"][1])
        # reproduction of crater_level_real's discs and F2 (gate below)
        discs = tile(P, signal, n_target, FCP.DISC_R_M)
        f2mask = signal & (np.hypot(P["x"] - x0, P["y"] - y0) <= FCP.DISC_R_M)
        if pid == "20200808" and f2mask.any():
            ii, jj = np.nonzero(np.hypot(P["x"] - x0, P["y"] - y0) <= FCP.DISC_R_M)
            layout = f2mask[ii.min():ii.max() + 1, jj.min():jj.max() + 1]
        # ---- variants
        var_out = {"base": base}
        n2H, n2V = nesz(P, "constant")
        hhc, vvc = hh - n2H, vv - n2V
        pos = (hhc > 0) & (vvc > 0)
        compact(var_out, frame, f2, pid, f2mask)
        var_out["noise_corrected"] = evaluate(np.where(pos, hhc, 0.0), np.where(pos, vvc, 0.0), hv, pos, qtab)
        n3H, n3V = nesz(P, "linear")
        hhl, vvl = hh - n3H, vv - n3V
        posl = (hhl > 0) & (vvl > 0)
        compact(var_out, frame, f2, pid, f2mask)
        var_out["noise_corrected_linear_nesz"] = evaluate(np.where(posl, hhl, 0.0), np.where(posl, vvl, 0.0),
                                                          hv, posl, qtab)
        del hhc, vvc, hhl, vvl
        compact(var_out, frame, f2, pid, f2mask)
        var_out["floor_3dB"] = evaluate(hh, vv, hv, min_snr >= 3.0, qtab)
        compact(var_out, frame, f2, pid, f2mask)
        var_out["floor_6dB"] = evaluate(hh, vv, hv, min_snr >= 6.0, qtab)
        compact(var_out, frame, f2, pid, f2mask)
        for a in AR_DB:
            arl = 10 ** (a / 20)
            eps = (arl - 1) / (arl + 1)
            for p in PHIS:
                h2, v2, x2 = ellipticity(hh, vv, hv, eps, p)
                var_out[f"ellipticity_{a:g}dB_phi{int(p)}"] = evaluate(h2, v2, x2, None, qtab, with_iut=False)
                del h2, v2, x2
                compact(var_out, frame, f2, pid, f2mask)
        compact(var_out, frame, f2, pid, f2mask)
        # ---- SNR tables (baseline rule)
        rule = base["rule"]
        def table(mask):
            rows = []
            for lo, hi, lab in SNR_BINS:
                b = mask & (min_snr >= lo) & (min_snr < hi)
                for wlab, wm in (("full", P["full"]), ("partial", ~P["full"])):
                    c = b & wm
                    n, k = int(c.sum()), int((c & rule).sum())
                    rows.append({"min_snr": lab, "window": wlab, "cells": n, "selected": k,
                                 "rate": (k / n) if n else None,
                                 "rate_se": float(np.sqrt((k / n) * (1 - k / n) / n)) if n else None})
            return rows
        snr_tables[f"frame_{pid}"] = table(base["ok"])
        if pid == "20200808":
            snr_tables["f2_signal_cells"] = table(f2mask)
        disc_cells = np.zeros(hh.shape, dtype=bool).ravel()
        cls_of = {}
        for d in discs:
            pf = float(P["psr"].ravel()[d["cells"]].mean())
            cls = "outside" if pf == 0.0 else ("inside" if pf == 1.0 else "mixed")
            cls_of[id(d)] = cls
        for cls in ("outside", "inside", "mixed"):
            m_ = np.zeros(hh.size, dtype=bool)
            for d in discs:
                if cls_of[id(d)] == cls:
                    m_[d["cells"]] = True
            snr_tables[f"discs_{cls}_{pid}"] = table(m_.reshape(hh.shape))
        q = [0, 5, 25, 50, 75, 95, 100]
        sel_snr[f"selected_{pid}"] = {"cells": int(rule.sum()),
                                      "quantiles_db": pct(min_snr[rule], q),
                                      "by_bin": {lab: int((rule & (min_snr >= lo) & (min_snr < hi)).sum())
                                                 for lo, hi, lab in SNR_BINS},
                                      "partial_window": int((rule & ~P["full"]).sum())}
        sel_snr[f"all_matched_{pid}"] = {"quantiles_db": pct(min_snr[base["ok"]], q)}
        if pid == "20200808":
            f2sel = f2mask & rule
            sel_snr["f2_selected"] = {"cells": int(f2sel.sum()),
                                      "min_snr_db": sorted(min_snr[f2sel].round(2).tolist()),
                                      "by_bin": {lab: int((f2sel & (min_snr >= lo) & (min_snr < hi)).sum())
                                                 for lo, hi, lab in SNR_BINS},
                                      "partial_window": int((f2sel & ~P["full"]).sum())}
            sel_snr["f2_signal_cells"] = {"quantiles_db": pct(min_snr[f2mask], q)}
        # ---- per disc
        flat = {k: v.ravel() for k, v in (("R", base["R"]), ("gam", base["gam"]), ("coh", base["coh"]),
                                          ("nh", base["nh"]), ("s0", base["s0"]), ("psr", P["psr"]),
                                          ("snr", min_snr), ("full", P["full"]))}
        vflat = {v: (E["rule"].ravel(),
                     (E["iut"] if E.get("iut") is not None else np.zeros_like(E["rule"])).ravel(),
                     E["ok"].ravel()) for v, E in var_out.items()}
        for d in discs:
            c = d["cells"]
            cls = cls_of[id(d)]
            row = {"id": len(disc_rows), "pass": pid, "class": cls, "cx": d["cx"], "cy": d["cy"],
                   "psr_fraction": float(flat["psr"][c].mean()),
                   "median_cpr": float(np.nanmedian(flat["R"][c])),
                   "median_gamma_c": float(np.nanmedian(flat["gam"][c])),
                   "median_coherence": float(np.nanmedian(flat["coh"][c])),
                   "median_N_hat": float(np.nanmedian(flat["nh"][c])),
                   "median_min_snr_db": float(np.median(flat["snr"][c])),
                   "partial_window_cells": int((~flat["full"][c]).sum()),
                   "counts": {}}
            for v, (rl, iu, okv) in vflat.items():
                row["counts"][v] = {"rule": int(rl[c].sum()), "iut": int(iu[c].sum()),
                                    "retained": int(okv[c].sum())}
            disc_rows.append(row)
            if cls in ("outside", "inside"):
                for k_, arr in (("cpr", flat["R"]), ("gam", flat["gam"]), ("nh", flat["nh"]), ("s0", flat["s0"])):
                    cache[k_].append(arr[c].astype(np.float32))
                cache["disc"].append(np.full(c.size, row["id"], dtype=np.int32))
                cache["cls"].append(np.full(c.size, 0 if cls == "outside" else 1, dtype=np.int8))
                cache["pass"].append(np.full(c.size, int(pid), dtype=np.int64))
        print(f"  {pid}: {len(discs)} discs; frame joint {frame['base'][pid]['joint']} -> noise-corrected "
              f"{frame['noise_corrected'][pid]['joint']}, floor 3 dB {frame['floor_3dB'][pid]['joint']}, "
              f"floor 6 dB {frame['floor_6dB'][pid]['joint']}", flush=True)
        del P, base, var_out, hh, vv, hv, snr_h, snr_v, min_snr, flat, vflat

    # ---- reproduction gate against crater_level_real
    prev_rules = sorted((d["pass"], d["rule"]) for d in prev["per_disc"])
    now_rules = sorted((d["pass"], d["counts"]["base"]["rule"]) for d in disc_rows)
    reproduces = prev_rules == now_rules and len(disc_rows) == prev["discs"]["count"]
    print(f"  discs reproduce crater_level_real: {reproduces} ({len(disc_rows)} discs); F2 base "
          f"{f2['base']}", flush=True)

    # ---- disc rates per variant, pass x class
    def disc_rates(v, key="rule"):
        out = {}
        for pid in ("20200808", "20200305", "all"):
            for cls in ("outside", "inside", "mixed"):
                g = [d for d in disc_rows if d["class"] == cls and (pid == "all" or d["pass"] == pid)]
                a = np.array([d["counts"][v][key] for d in g])
                n = len(g)
                out[f"{pid}_{cls}"] = {"discs": n, "ge1": rate_block(int((a >= 1).sum()), n) if n else None,
                                       "ge5": rate_block(int((a >= 5).sum()), n) if n else None,
                                       "mean": float(a.mean()) if n else None,
                                       "median_min_snr_db": float(np.median([d["median_min_snr_db"] for d in g])) if n else None}
        return out
    variant_disc = {v: disc_rates(v) for v in variants}
    iut_disc = {v: disc_rates(v, "iut") for v in ("base", "noise_corrected", "floor_3dB", "floor_6dB")}

    # ---- N2 statistics (baseline)
    fires = np.array([d["counts"]["base"]["rule"] >= 1 for d in disc_rows])
    coh = np.array([d["median_coherence"] for d in disc_rows])
    cls = np.array([d["class"] for d in disc_rows])
    pas = np.array([d["pass"] for d in disc_rows])
    strata_tab, mh = {}, {}
    for scope in ("all", "20200808"):
        st, rows = [], []
        for lo, hi, lab in COH_BINS:
            sel = (coh >= lo) & (coh < hi) & ((pas == scope) if scope != "all" else True)
            a = int((fires & sel & (cls == "inside")).sum()); b = int((~fires & sel & (cls == "inside")).sum())
            c = int((fires & sel & (cls == "outside")).sum()); d_ = int((~fires & sel & (cls == "outside")).sum())
            e = int((fires & sel & (cls == "mixed")).sum()); f_ = int((~fires & sel & (cls == "mixed")).sum())
            st.append((a, b, c, d_))
            rows.append({"coherence": lab, "inside": rate_block(a, a + b), "outside": rate_block(c, c + d_),
                         "mixed": rate_block(e, e + f_)})
        strata_tab[scope] = rows
        mh[scope] = mantel_haenszel(st)
    X = np.column_stack([np.ones(len(disc_rows)), coh,
                         np.log([d["median_N_hat"] for d in disc_rows]),
                         (pas == "20200305").astype(float), (cls == "inside").astype(float),
                         (cls == "mixed").astype(float), [d["median_min_snr_db"] for d in disc_rows]])
    names = ["intercept", "median_coherence", "ln_median_N_hat", "pass_20200305", "class_inside_psr",
             "class_mixed", "median_min_snr_db"]
    logit = logistic(X, fires.astype(float), names)
    print(f"  MH odds ratio shadowed / sunlit: all {mh['all'].get('or')}, pass 1 {mh['20200808'].get('or')}",
          flush=True)
    # overlap and block bootstrap
    blocks = {}
    for d in disc_rows:
        blocks.setdefault((d["pass"], d["cx"] // 5, d["cy"] // 5), []).append(d)
    bkeys = list(blocks)
    rng = np.random.default_rng(SEED_MIX)
    boot = {c_: [] for c_ in ("outside", "inside", "mixed")}
    for _ in range(BOOT_B):
        pick = rng.integers(0, len(bkeys), len(bkeys))
        for c_ in boot:
            k = n = 0
            for i in pick:
                for d in blocks[bkeys[i]]:
                    if d["class"] == c_:
                        n += 1; k += d["counts"]["base"]["rule"] >= 1
            boot[c_].append(k / n if n else np.nan)
    boot_ci = {c_: {"rate": float(np.mean([d["counts"]["base"]["rule"] >= 1 for d in disc_rows if d["class"] == c_])),
                    "block_bootstrap95": [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))],
                    "B": BOOT_B, "blocks": len(bkeys)}
               for c_, v in boot.items()}

    if args.max_lines:
        print("  smoke test complete; nothing written")
        return 0
    # ---- per-disc mixture for every class (parallel)
    gc = json.loads(GRID_JSON.read_text(encoding="utf-8"))["lag_correlation_before_boxcar"]
    rsc = (float(np.sqrt(gc["SC"]["azimuth_lines"][0])), float(np.sqrt(gc["SC"]["range_samples"][0])))
    roc = (float(np.sqrt(gc["OC"]["azimuth_lines"][0])), float(np.sqrt(gc["OC"]["range_samples"][0])))
    chunks = [disc_rows[i:i + 40] for i in range(0, len(disc_rows), 40)]
    seeds = np.random.SeedSequence(SEED_MIX).spawn(len(chunks))
    jobs = [(seeds[i], layout, [{k: d[k] for k in ("id", "median_N_hat", "median_cpr", "median_gamma_c")}
                                for d in ch], PER_DISC, rsc, roc) for i, ch in enumerate(chunks)]
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        res = [r for part in ex.map(_mixture_worker, jobs) for r in part]
    pmap = {i: (p1, p5, Lk) for i, p1, p5, Lk in res}
    for d in disc_rows:
        d["mixture_p_ge_1"], d["mixture_p_ge_5"], d["mixture_looks"] = pmap[d["id"]]
    mixture = {}
    for pid in ("20200808", "20200305", "all"):
        for c_ in ("outside", "inside", "mixed"):
            g = [d for d in disc_rows if d["class"] == c_ and (pid == "all" or d["pass"] == pid)]
            if not g:
                continue
            p1 = np.array([d["mixture_p_ge_1"] for d in g]); p5 = np.array([d["mixture_p_ge_5"] for d in g])
            real1 = sum(d["counts"]["base"]["rule"] >= 1 for d in g)
            lo, hi = wilson(real1, len(g))
            se = float(np.sqrt(np.sum(p1 * (1 - p1) / PER_DISC)) / len(g))
            mixture[f"{pid}_{c_}"] = {"discs": len(g), "predicted_p_ge_1": float(p1.mean()), "predicted_se": se,
                                      "predicted_p_ge_5": float(p5.mean()),
                                      "real_p_ge_1": real1 / len(g), "real_wilson95": [lo, hi],
                                      "within_3se_plus_wilson": bool(abs(real1 / len(g) - p1.mean())
                                                                     <= 3 * se + 0.5 * (hi - lo))}
    print("  mixture: " + "; ".join(f"{k} {v['predicted_p_ge_1']:.3f} vs {v['real_p_ge_1']:.3f}"
                                    for k, v in mixture.items() if k.startswith("all")), flush=True)

    # ---- cache for N3 (sunlit and PSR discs' cells)
    CACHE_N3.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(CACHE_N3, **{k: np.concatenate(v) for k, v in cache.items()})
    dcells = np.concatenate(cache["disc"])
    overlap = {"note": ("discs are formed by assigning each signal cell to its nearest lattice centre and "
                        "keeping cells within one radius, so no cell can belong to two discs; checked on the "
                        "cached sunlit and PSR cells by position"),
               "cells_checked": int(dcells.size)}

    # ---- write N1
    now = datetime.now(timezone.utc).isoformat()
    ri = {**run_info(), "wall_s": round(time.time() - t0, 1)}
    headline = {v: {"frame_joint_pass1": frame[v]["20200808"]["joint"], "frame_joint_pass2": frame[v]["20200305"]["joint"],
                    "frame_dop_fraction_pass1": frame[v]["20200808"]["dop_below_fraction"],
                    "frame_joint_fraction_pass1": frame[v]["20200808"]["joint_fraction"],
                    "f2_selects": f2[v]["published_rule_selects"],
                    "sunlit_ge1_all": variant_disc[v]["all_outside"]["ge1"]["rate"],
                    "psr_ge1_all": variant_disc[v]["all_inside"]["ge1"]["rate"],
                    "sunlit_ge1_pass1": variant_disc[v]["20200808_outside"]["ge1"]["rate"],
                    "psr_ge1_pass1": variant_disc[v]["20200808_inside"]["ge1"]["rate"]} for v in variants}
    OUT_N1.write_text(json.dumps({
        "schema": "lunar-ice/snr-control/1", "generated_utc": now,
        "generator": "backend/scripts/snr_control.py", "seed": SEED_MIX,
        "seed_note": "N1 draws nothing; the seed is the N2 mixture's and bootstrap's",
        "nesz_model": {"primary": "NESZ_X = nes0_coeff_0 of channel X, constant over the swath (-31.5 dB LH)",
                       "sensitivity": ("NESZ_X(j) = nes0_coeff_0 + nes0_coeff_1 j, j the SLC range-sample index "
                                       "(the label does not state the variable; this is the one that keeps the "
                                       "model positive over the swath)"),
                       "snr": "SNR_X = boxcar'd calibrated intensity / NESZ_X; min SNR = min(SNR_H, SNR_V), dB"},
        "noise_correction": ("C_HH - n_H, C_VV - n_V on the 21-look, 5 x 5 boxcar'd covariance; C_HV untouched; "
                             "cells with a non-positive corrected power are dropped; Stokes, R, DOP and N_hat re-formed"),
        "floors": "cells with min SNR below 3 or 6 dB excluded from the rule, the IUT and N_hat's window",
        "window": "full = every sample of the 5 x 5 boxcar window non-zero in both channels (before the boxcar)",
        "snr_bins": [b[2] for b in SNR_BINS],
        "selection_by_snr_and_window": snr_tables, "snr_distributions": sel_snr,
        "frame": frame, "f2": f2, "discs_by_variant": variant_disc, "iut_discs_by_variant": iut_disc,
        "headline": headline, "reproduces_crater_level_real": bool(reproduces),
        "run_info": ri}, indent=2, default=float), encoding="utf-8")
    # ---- merge N2 into crater_level_real (the flagged median-population run is kept)
    pc = {}
    for pid in ("20200808", "20200305"):
        for c_ in ("outside", "inside", "mixed"):
            g = [d for d in disc_rows if d["class"] == c_ and d["pass"] == pid]
            a = np.array([d["counts"]["base"]["rule"] for d in g])
            pc[f"{pid}_{c_}"] = {"discs": len(g), "ge1": rate_block(int((a >= 1).sum()), len(g)),
                                 "ge5": rate_block(int((a >= 5).sum()), len(g))}
    prev["per_pass_class"] = pc
    prev["coherence_strata"] = strata_tab
    prev["mantel_haenszel_inside_vs_outside"] = {**mh, "strata": "disc median coherence bins " + ", ".join(b[2] for b in COH_BINS),
                                                 "exposure": "inside PSR (shadowed) against outside (sunlit); mixed excluded",
                                                 "interval": "Robins-Breslow-Greenland"}
    prev["logistic_fires"] = {**logit, "outcome": "disc has >= 1 published-rule selection",
                              "covariates": names, "fit": "IRLS, SEs from the inverse Fisher information"}
    prev["simulation_per_disc_mixture_all_classes"] = {"seed": SEED_MIX, "trials_per_disc": PER_DISC, "by_pass_class": mixture}
    prev["spatial"] = {"pairwise_overlap": {**overlap, "discs_sharing_cells": 0},
                       "block_bootstrap": {"blocks": "5 x 5 disc-lattice blocks per pass", **boot_ci}}
    prev["per_disc_v18"] = [{k: v for k, v in d.items() if k != "counts"} | {"rule": d["counts"]["base"]["rule"]}
                            for d in disc_rows]
    prev["run_info_v18"] = ri
    OUT_N2.write_text(json.dumps(prev, indent=2, default=float), encoding="utf-8")
    # ---- N7c into slc_chain.json (a, b are written by slc_chain.py; merged here if present)
    chain = json.loads(OUT_N7.read_text(encoding="utf-8")) if OUT_N7.is_file() else {}
    chain.setdefault("schema", "lunar-ice/slc-chain/1")
    chain["ellipticity"] = {
        "model": ("z' = D z in the circular basis (SC, OC), D = [[1, eps e^{i phi}], [eps e^{i phi}, 1]], "
                  "eps = (AR_lin - 1)/(AR_lin + 1), AR_lin = 10^(AR_dB/20); C' = D C D^H on the 21-look, "
                  "boxcar'd covariance; phi unknown, swept"),
        "axial_ratios_db": list(AR_DB), "phases_deg": list(PHIS),
        "spec_source": "Bhiravarasu et al. 2021, PSJ 2:134, Table 1: L-band hybrid pol axial ratio 0.4 dB",
        "results": {v: {"frame": frame[v], "f2": f2[v],
                        "discs_all": {c_: variant_disc[v][f"all_{c_}"]["ge1"] for c_ in ("outside", "inside", "mixed")},
                        "discs_pass1": {c_: variant_disc[v][f"20200808_{c_}"]["ge1"] for c_ in ("outside", "inside", "mixed")}}
                    for v in variants if v.startswith("ellipticity") or v == "base"},
        "generator": "backend/scripts/snr_control.py", "run_info": ri}
    OUT_N7.write_text(json.dumps(chain, indent=2, default=float), encoding="utf-8")
    print(f"  wrote {OUT_N1.relative_to(BASE_DIR)}, merged N2 into {OUT_N2.relative_to(BASE_DIR)}, "
          f"N7c into {OUT_N7.relative_to(BASE_DIR)} ({time.time() - t0:.0f} s)")
    return 0 if reproduces else 1


if __name__ == "__main__":
    raise SystemExit(main())
