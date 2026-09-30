"""
gap_v20_frame.py -- the frame-level parts of the v20 gap pass: the noise
control reconciled (G-B), geometry covariates (G-D), the kernel sweep (G-E) and
the F2 CPR distribution (G-F), on both passes of the complex product.

    python backend/scripts/gap_v20_frame.py [--workers N] [--max-lines N]

Writes docs/kernel_sweep.json (G-E, G-F), merges `v20_reconciliation` into
docs/snr_control.json (G-B) and `v20_gap.per_disc_geometry` /
`v20_gap.geometry_frame` into docs/crater_level_real.json (G-D). Draws nothing
(seed: none); every rate is a count with a Wilson interval.

G-B  NOISE CONTROL RECONCILIATION
---------------------------------
A referee found 285 198 cells dropped for non-positive corrected power and
32 188 corrected cells with DOP > 1, yet only 11 167 cells with min SNR < 0 dB.

The arithmetic reconciles. The 285 198 are 11 167 cells whose corrected
diagonal is not positive (11 159 of them in partial windows) plus 274 031
cells whose corrected matrix has |S3| >= S0, that is |<E_H E_V*>|^2 >
(C_HH - n_H)(C_VV - n_V), which is not a positive semidefinite covariance;
32 188 more such cells pass the S0 test and read DOP > 1. Subtracting noise
from the diagonal alone leaves the cross term untouched, so any cell whose
observed coherence exceeds sqrt((1 - n_H/C_HH)(1 - n_V/C_VV)) becomes
unphysical. At the nominal noise that is 5.4 % of the matched cells, against
0.5 % of the cells at SNR > 10 dB where the correction is negligible.

That excess is not sampling noise. The radiometric scales were:
  (i)  SNR denominator: the label's nes0_coeff_0 of the channel, used as given
       (a sigma0-type number, no sin(theta) applied);
  (ii) subtracted noise: the same number, subtracted from C_HH and C_VV of
       the calibrated coherency, which is sigma0-scale WITH the label's scalar
       sin(theta) (l = DN^2 sin(theta) / (K G^2)); identical in form to (i).
So the two agree with each other; the question is whether the label's number
is in the scale of the calibrated intensity. Readings tested (each against
the coherence bound above):
  R1  nes0 is sigma0 as labelled: noise = nes0 (nominal).
  R2  nes0 is sigma0 at the LOCAL incidence of the geometry file:
      noise = nes0 sin(20 deg) / sin(theta_local(j)).
  R3  nes0 is beta0: noise in the calibrated (sigma0) scale = nes0 sin(20 deg).
The fraction of cells violating the coherence bound is scanned against a
noise scale alpha (noise = alpha nes0) for both bands.

The corrected variants then fix three defects of the v18a run:
  * the noise is scaled by the window's valid-sample fraction f (zero SLC
    samples are no-data; they enter the 21-line mean and the boxcar as zeros,
    so the averaged power is f (S + n), not S + n);
  * a cell whose corrected matrix is not positive semidefinite is PROJECTED
    (|C_HV| reduced to sqrt(C_HH' C_VV'), coherence 1, DOP 1) and kept, rather
    than dropped; it cannot fire (DOP = 1) and is left out of the N-hat
    windows; a cell whose corrected diagonal is not positive holds no signal
    above the noise and is dropped;
  * the floors use SNR = C / (f n).

G-D  GEOMETRY. Per disc: the median slant-range sample (the SLC column), the
     slant range and the incidence angle interpolated from the bundle's
     geometry file (Slant_Range, Incidence_Angle of the tie-point grid), and
     the LOLA local incidence: cos(theta_local) = (cos(theta_i) - sin(theta_i)
     (p u_x + q u_y)) / sqrt(1 + p^2 + q^2), theta_i the geometry file's
     incidence, (p, q) the LDEM_80S_20M gradient over +-2 posts (80 m) in the
     polar-stereographic map axes, u the horizontal unit vector towards the
     sensor, -d(x, y)/d(sample) of the tie-point grid. Selection rate by
     slant-range decile over the frame.

G-E  KERNEL SWEEP. The log-ratio N, the frame joint and IUT counts and the
     selected cells' local look count at 5 x 5, 7 x 7 and 9 x 9 boxcars
     applied after the 21-sample azimuth mean.

G-F  F2 CPR DISTRIBUTION. The F2 disc's 663 signal cells: maximum sample CPR,
     cells above 1.3, fraction above 1, at every kernel.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_erosion

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runinfo import run_info  # noqa: E402
import stokes_from_slc as SFS  # noqa: E402
import enl_logratio as L  # noqa: E402
import decision_rule as DR  # noqa: E402
import f2_complex_product as FCP  # noqa: E402
import snr_control as SC  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT_SNR = BASE_DIR / "docs" / "snr_control.json"
OUT_CLR = BASE_DIR / "docs" / "crater_level_real.json"
OUT_KERNEL = BASE_DIR / "docs" / "kernel_sweep.json"
KERNELS = (5, 7, 9)
N_EDGE = 79.6166
BAND_EDGE = 1.13 / 0.87
DOP_T = 0.13
ALPHAS = (1.0, 0.75, 0.5, None, 0.25, 0.1)       # None: sin(theta_label)
DEM_HALF = 2                                     # gradient over +-2 posts = 80 m

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


# ---------------------------------------------------------------- reading
def read_pass(pid, max_lines=0):
    """The calibrated coherency of build_coherency (azimuth mean only, no
    boxcar) plus, per channel, the fraction of the 21 lines that hold a
    non-zero sample. Identical arithmetic to stokes_from_slc.build_coherency;
    reproduced by the gate against the v18a counts."""
    SFS.configure(pid)
    lab = SFS.label_fields()
    k_lin = 10.0 ** (lab["calibration_constant_db"] / 10.0)
    g_lh, g_lv = lab["gain_imbalance"]["LH"], lab["gain_imbalance"]["LV"]
    sin_t = float(np.sin(np.deg2rad(lab["incidence_angle_deg"])))
    eh, ev = SFS.open_slc("lh"), SFS.open_slc("lv")
    AL = SFS.AZIMUTH_LOOKS
    n_lines = max_lines or SFS.LINES
    n_out = n_lines // AL
    hh = np.empty((n_out, SFS.SAMPLES)); vv = np.empty_like(hh)
    hv = np.empty((n_out, SFS.SAMPLES), dtype=np.complex128)
    fh = np.empty((n_out, SFS.SAMPLES), dtype=np.float32); fv = np.empty_like(fh)
    CH = 512
    for s in range(0, n_out, CH):
        e = min(s + CH, n_out)
        a = np.asarray(eh[s * AL:e * AL], dtype=np.complex128).reshape(e - s, AL, SFS.SAMPLES)
        b = np.asarray(ev[s * AL:e * AL], dtype=np.complex128).reshape(e - s, AL, SFS.SAMPLES)
        pa, pb = np.abs(a) ** 2, np.abs(b) ** 2
        hh[s:e], vv[s:e] = pa.mean(axis=1), pb.mean(axis=1)
        hv[s:e] = (a * np.conj(b)).mean(axis=1)
        fh[s:e], fv[s:e] = (pa > 0).mean(axis=1), (pb > 0).mean(axis=1)
        del a, b, pa, pb
    scale = sin_t / k_lin
    hh *= scale / g_lh ** 2
    vv *= scale / g_lv ** 2
    hv *= scale / (g_lh * g_lv)
    src = (SFS.RAW / f"{SFS.STEM}_d_sli_xx_cp_xx_d18.xml").read_text(encoding="utf-8", errors="replace")
    c0 = [float(v) for v in re.findall(r"<isda:nes0_coeff_0>([^<]+)<", src)]
    c1 = [float(v) for v in re.findall(r"<isda:nes0_coeff_1>([^<]+)<", src)]
    return {"hh": hh, "vv": vv, "hv": hv, "fh": fh, "fv": fv, "c0": c0, "c1": c1, "sin_t": sin_t,
            "theta_deg": lab["incidence_angle_deg"], "AL": AL, "shape": hh.shape}


def boxed(R, b):
    hh, vv = SFS.boxcar2d(R["hh"], b), SFS.boxcar2d(R["vv"], b)
    hv = SFS.boxcar2d(R["hv"].real, b) + 1j * SFS.boxcar2d(R["hv"].imag, b)
    return hh, vv, hv


def geometry_xy(R, pid, psr):
    """Cell positions and PSR membership, as snr_control.load does."""
    spec, g, tx, ty = FCP.tie_grid(pid)
    rows, cols = R["shape"]
    AL = R["AL"]
    li = AL * np.arange(rows) + (AL - 1) / 2.0
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
    return {"x": xc, "y": yc, "psr": in_psr, "spec": spec, "grid": g, "tx": tx, "ty": ty}


class LDEM:
    """LDEM_80S_20M read in place (int16 memmap); heights above the 1737.4 km
    sphere = DN * 0.5 m. Gradients at cell positions by nearest post."""

    def __init__(self):
        spec = importlib.util.spec_from_file_location("_ingest_lola", BASE_DIR / "backend" / "scripts" /
                                                      "ingest_lola_polar_dem.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        lola = BASE_DIR / "data" / "pradan" / "lola"
        self.g = mod.LolaGrid(mod.read_label(lola / "LDEM_80S_20M.LBL"), lola / "LDEM_80S_20M.IMG")
        conv = mod.solve_convention(self.g)
        self.g.base = conv["best"]["base"]
        self.mm = np.memmap(lola / "LDEM_80S_20M.IMG", dtype=self.g.dtype, mode="r",
                            offset=self.g.data_offset_bytes, shape=(self.g.lines, self.g.samples))
        self.base = {"zero_based": 0.0, "half_pixel": 0.5, "one_based": 1.0}[self.g.base]

    def pq(self, x, y):
        """dz/dx, dz/dy (m/m) at map positions (x, y); NaN off the array or at a fill value."""
        g = self.g
        l = np.rint(g.lpo - y / g.scale_m - self.base).astype(np.int64)
        s = np.rint(g.spo + x / g.scale_m - self.base).astype(np.int64)
        h = DEM_HALF
        ok = (l >= h) & (l < g.lines - h) & (s >= h) & (s < g.samples - h)
        p = np.full(x.shape, np.nan); q = np.full(x.shape, np.nan)
        li, si = l[ok], s[ok]
        zE, zW = self.mm[li, si + h].astype(np.float64), self.mm[li, si - h].astype(np.float64)
        zN, zS = self.mm[li - h, si].astype(np.float64), self.mm[li + h, si].astype(np.float64)
        bad = np.abs(np.stack([zE, zW, zN, zS])).max(axis=0) > 30000      # fill values (int16 DN)
        d = 2.0 * h * g.scale_m * g.scaling_factor ** -1                    # DN units -> metres below
        p[ok] = np.where(bad, np.nan, (zE - zW) / d)
        q[ok] = np.where(bad, np.nan, (zN - zS) / d)
        return p, q


# ---------------------------------------------------------------- evaluation
def evaluate2(hh, vv, hv, use_extra, qtab, exclude_from_windows=None, with_iut=True):
    """snr_control.evaluate, with cells that may be left out of the N-hat
    windows (projected cells carry an invalid estimate of ln R)."""
    ok, lr, dop, coh, gam, s0 = SC.stokes_fields(hh, vv, hv)
    if use_extra is not None:
        ok = ok & use_extra
        lr = np.where(ok, lr, np.nan)
    R = np.exp(lr)
    rule = ok & (dop < DOP_T) & (R > 1.0)
    out = {"ok": ok, "R": R, "dop": dop, "coh": coh, "gam": gam, "rule": rule, "s0": s0, "lr": lr}
    if with_iut:
        w_ok = ok if exclude_from_windows is None else (ok & ~exclude_from_windows)
        nh, _ = L.local_n(lr, w_ok)
        fin = ok & np.isfinite(nh)
        iut = np.zeros_like(ok)
        iut[fin] = (R[fin] > DR.crit(nh[fin])) & (dop[fin] < DR.q05_at(nh[fin], qtab))
        out["nh"], out["iut"] = nh, iut
    return out


def corrected(hh, vv, hv, nH, nV, fH, fV):
    """Noise-corrected coherency with valid-fraction-aware noise and PSD
    projection. Returns (h, v, x, pos, projected)."""
    hc, vc = hh - fH * nH, vv - fV * nV
    pos = (hc > 0) & (vc > 0)
    hcp, vcp = np.where(pos, hc, 1.0), np.where(pos, vc, 1.0)
    bound = np.sqrt(hcp * vcp)
    amp = np.abs(hv)
    proj = pos & (amp > bound)
    x = np.where(proj, hv * (bound / np.where(amp > 0, amp, 1.0)), hv)
    return np.where(pos, hc, 0.0), np.where(pos, vc, 0.0), x, pos, proj


def legacy_corrected(hh, vv, hv, nH, nV):
    """The v18a variant exactly: subtract, drop cells with a non-positive
    corrected diagonal, leave the cross term."""
    hc, vc = hh - nH, vv - nV
    pos = (hc > 0) & (vc > 0)
    return np.where(pos, hc, 0.0), np.where(pos, vc, 0.0), hv, pos


def record(E, base_ok, extra=None):
    okm = E["ok"]
    rec = {"cells_matched": int(okm.sum()),
           "joint": int(E["rule"].sum()),
           "joint_fraction": float(E["rule"].sum() / max(okm.sum(), 1)),
           "dop_below_0p13": int((okm & (E["dop"] < DOP_T)).sum()),
           "dop_below_fraction": float((okm & (E["dop"] < DOP_T)).sum() / max(okm.sum(), 1)),
           "unphysical_dop_gt_1": int((okm & (E["dop"] > 1.0 + 1e-9)).sum()),
           "iut": int(E["iut"].sum()) if E.get("iut") is not None else None,
           "dropped_relative_to_base": int(base_ok.sum() - okm.sum())}
    if extra:
        rec.update(extra)
    return rec


def disc_counts(E, discs):
    rl = E["rule"].ravel()
    iu = E["iut"].ravel() if E.get("iut") is not None else np.zeros(rl.size, bool)
    return ([int(rl[d["cells"]].sum()) for d in discs], [int(iu[d["cells"]].sum()) for d in discs])


def disc_rates(counts, disc_rows):
    out = {}
    for pid in ("20200808", "20200305", "all"):
        for cls in ("outside", "inside", "mixed"):
            idx = [i for i, d in enumerate(disc_rows) if d["class"] == cls and (pid == "all" or d["pass"] == pid)]
            a = np.array([counts[i] for i in idx])
            n = len(idx)
            out[f"{pid}_{cls}"] = {"discs": n, "ge1": SC.rate_block(int((a >= 1).sum()), n) if n else None,
                                   "ge5": SC.rate_block(int((a >= 5).sum()), n) if n else None,
                                   "mean": float(a.mean()) if n else None}
    return out


def f2_cpr_block(E, f2mask, sel_mask=None):
    """G-F: the distribution of sample CPR over F2's signal cells."""
    R = E["R"][f2mask]
    fin = np.isfinite(R)
    Rf = R[fin]
    sel = E["rule"][f2mask]
    rs = E["R"][f2mask][sel]
    return {"cells": int(f2mask.sum()), "cells_with_defined_cpr": int(fin.sum()),
            "max_cpr": float(Rf.max()) if Rf.size else None,
            "n_cpr_above_1p3": int((Rf > 1.3).sum()),
            "n_cpr_above_band_edge_1p2989": int((Rf > BAND_EDGE).sum()),
            "fraction_cpr_above_1": float((Rf > 1.0).mean()) if Rf.size else None,
            "median_cpr": float(np.median(Rf)) if Rf.size else None,
            "p95_cpr": float(np.percentile(Rf, 95)) if Rf.size else None,
            "joint_rule_selects": int(sel.sum()),
            "max_cpr_among_selected": float(rs.max()) if rs.size else None,
            "min_cpr_among_selected": float(rs.min()) if rs.size else None,
            "selected_with_cpr_above_band_edge": int((rs > BAND_EDGE).sum())}


def n_blocks(E, s0, m):
    blocks = SFS.low_cv_tiles(s0, m, 64, percentile=10)
    k = 64
    lr, ok = E["lr"], E["ok"]
    bn = []
    for r0, c0, _cv in blocks:
        w, u = lr[r0:r0 + k, c0:c0 + k], ok[r0:r0 + k, c0:c0 + k]
        bn.append(float(L.n_from_var(w[u].var(ddof=1))))
    return {"blocks": len(bn), "N_logratio": L.describe(bn)}


def selected_n(E):
    """enl_logratio.product's local N at the selected cells: every selected
    cell is left out of every window."""
    ok, sel = E["ok"], E["rule"]
    use = ok & ~sel
    nloc, cnt = L.local_n(E["lr"], use)
    n_sel = nloc[sel]
    fin = np.isfinite(n_sel)
    crit = L.crit95(np.where(fin, n_sel, 1.0))
    sig = fin & (E["R"][sel] > crit)
    n_all = nloc[use]
    return {"selected": int(sel.sum()), "selected_local_N": L.describe(n_sel),
            "n_selected_with_local_N_ge_79p6": int((n_sel[fin] >= N_EDGE).sum()),
            "n_selected_with_R_above_crit_at_local_N": int(sig.sum()),
            "frame_local_N_median_nonselected": float(np.nanmedian(n_all)),
            "frame_local_N_iqr_nonselected": [float(np.nanpercentile(n_all, 25)), float(np.nanpercentile(n_all, 75))]}


# ---------------------------------------------------------------- main
def main() -> int:
    import validate_psr_vs_lola as V
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-lines", type=int, default=0, help="smoke test: SLC lines per pass; writes nothing")
    args = ap.parse_args()
    t0 = time.time()
    dr = json.loads((BASE_DIR / "docs" / "decision_rule.json").read_text(encoding="utf-8"))
    qtab = {int(k): v for k, v in dr["dop_quantile_table"]["q05"].items()}
    foot = json.loads(FCP.FOOT.read_text(encoding="utf-8"))["target"]
    x0, y0 = FCP.stereo(foot["lat_deg"], foot["lon_deg"])
    psr = V.load_pds("LPSR_75S_120M_201608")
    clr = json.loads(OUT_CLR.read_text(encoding="utf-8"))
    n_target = clr["discs"]["signal_cells_per_disc"]
    dem = LDEM()
    print("=" * 78); print("v20 gap pass: noise reconciliation, geometry, kernel sweep, F2 CPR"); print("=" * 78)

    NOISE = ["nc_R1", "nc_R1_linear", "nc_R3", "nc_R3_linear"]
    FLOORS = ["floor3_R1", "floor6_R1", "floor3_R3", "floor6_R3"]
    variants = ["base", "legacy_v18a_noise_corrected"] + NOISE + FLOORS
    frame = {v: {} for v in variants}
    f2v = {v: None for v in variants}
    disc_rows, vcounts, viut = [], {v: [] for v in variants}, {v: [] for v in variants}
    decomposition, alpha_scan, kernel, f2cpr, deciles, snr_stats = {}, {}, {}, {}, {}, {}
    geo_rows, geo_frame = [], {}

    for pid in ("20200808", "20200305"):
        R = read_pass(pid, args.max_lines)
        rows, cols = R["shape"]
        sin_l = R["sin_t"]
        c0, c1 = R["c0"], R["c1"]
        G = geometry_xy(R, pid, psr)
        jj = np.broadcast_to(np.arange(cols, dtype=np.float64)[None, :], (rows, cols))
        hh, vv, hv = boxed(R, 5)
        fH, fV = SFS.boxcar2d(R["fh"].astype(np.float64), 5), SFS.boxcar2d(R["fv"].astype(np.float64), 5)
        raw_both = (R["hh"] > 0) & (R["vv"] > 0)
        full = binary_erosion(raw_both, np.ones((5, 5), dtype=bool))
        del raw_both
        base = evaluate2(hh, vv, hv, None, qtab)
        base_ok = base["ok"]
        signal = base_ok & (hh > c0[0]) & (vv > c0[1])
        discs = SC.tile({"x": G["x"], "y": G["y"]}, signal, n_target, FCP.DISC_R_M)
        f2mask = signal & (np.hypot(G["x"] - x0, G["y"] - y0) <= FCP.DISC_R_M)
        print(f"  {pid}: base joint {int(base['rule'].sum()):,}, IUT {int(base['iut'].sum())}, "
              f"{len(discs)} discs, F2 {int(f2mask.sum())} cells / {int((f2mask & base['rule']).sum())} selected", flush=True)
        d_off = len(disc_rows)
        for d in discs:
            pf = float(G["psr"].ravel()[d["cells"]].mean())
            disc_rows.append({"pass": pid, "class": "outside" if pf == 0.0 else ("inside" if pf == 1.0 else "mixed"),
                              "cx": d["cx"], "cy": d["cy"]})

        def run_variant(name, E, extra=None):
            frame[name][pid] = record(E, base_ok, extra)
            if pid == "20200808":
                f2v[name] = {"cells": int(f2mask.sum()), "cells_retained": int((f2mask & E["ok"]).sum()),
                             "published_rule_selects": int((f2mask & E["rule"]).sum()),
                             "iut_selects": int((f2mask & E["iut"]).sum()) if E.get("iut") is not None else None}
            a, b_ = disc_counts(E, discs)
            vcounts[name] += a
            viut[name] += b_

        run_variant("base", base)
        # ---- G-B: decomposition and the alpha scan (pass-level, both bands' worth in one place)
        nH, nV = c0[0], c0[1]
        hc, vc = hh - nH, vv - nV
        pos = (hc > 0) & (vc > 0)
        s0c = np.where(pos, hc + vc, 1.0)
        viol = pos & (np.abs(hv) ** 2 > hc * vc)
        s3c = -2.0 * hv.imag
        lost_s0 = pos & (np.abs(s3c) >= s0c)
        snr_nom = 10 * np.log10(np.maximum(np.minimum(hh / (fH * nH + 1e-300), vv / (fV * nV + 1e-300)), 1e-30))
        snr_raw = 10 * np.log10(np.maximum(np.minimum(hh / nH, vv / nV), 1e-30))
        decomposition[pid] = {
            "matched_cells": int(base_ok.sum()),
            "corrected_diagonal_not_positive": int((base_ok & ~pos).sum()),
            "of_which_partial_window": int((base_ok & ~pos & ~full).sum()),
            "corrected_matrix_not_psd_in_S0_test_(|S3|>=S0)": int((base_ok & lost_s0).sum()),
            "corrected_matrix_not_psd_total_(|C_HV|^2>C_HH'C_VV')": int((base_ok & viol).sum()),
            "not_psd_but_passing_S0_test_(DOP>1_retained)": int((base_ok & viol & ~lost_s0).sum()),
            "total_dropped_by_the_v18a_variant": int((base_ok & ~pos).sum() + (base_ok & lost_s0).sum()),
            "min_snr_below_0_dB_(unnormalised)": int((base_ok & (snr_raw < 0)).sum()),
            "median_observed_coherence_of_not_psd_cells": float(np.median(
                (np.abs(hv) / np.sqrt(np.maximum(hh * vv, 1e-300)))[base_ok & viol])) if (base_ok & viol).any() else None,
            "median_observed_coherence_frame": float(np.median(
                (np.abs(hv) / np.sqrt(np.maximum(hh * vv, 1e-300)))[base_ok])),
            "violation_fraction_by_nominal_snr_bin": {}}
        for lo, hi, lab in SC.SNR_BINS:
            b_ = base_ok & (snr_raw >= lo) & (snr_raw < hi)
            decomposition[pid]["violation_fraction_by_nominal_snr_bin"][lab] = {
                "cells": int(b_.sum()), "not_psd_or_nonpositive": int((b_ & (viol | ~pos)).sum()),
                "fraction": float((b_ & (viol | ~pos)).sum() / max(b_.sum(), 1))}
        baseline = decomposition[pid]["violation_fraction_by_nominal_snr_bin"]["> 10 dB"]["fraction"]
        # incidence for the R2 reading
        inc_full = FCP.interp(G["grid"][..., 3], *np.meshgrid(R["AL"] * np.arange(rows) + (R["AL"] - 1) / 2.0,
                                                               np.arange(cols), indexing="ij"), G["spec"])
        alpha_r2 = sin_l / np.sin(np.deg2rad(inc_full))
        scan = []
        for a in ALPHAS:
            al = sin_l if a is None else a
            h_, v_ = hh - al * nH, vv - al * nV
            p_ = (h_ > 0) & (v_ > 0)
            bad = base_ok & (~p_ | (np.abs(hv) ** 2 > h_ * v_))
            scan.append({"alpha": float(al), "label": "sin(theta_label) = beta0 reading R3" if a is None else "",
                         "violating_cells": int(bad.sum()), "fraction": float(bad.sum() / base_ok.sum())})
        h_, v_ = hh - alpha_r2 * nH, vv - alpha_r2 * nV
        p_ = (h_ > 0) & (v_ > 0)
        bad = base_ok & (~p_ | (np.abs(hv) ** 2 > h_ * v_))
        scan.append({"alpha": "sin(20)/sin(theta_local(j))", "label": "sigma0 at local incidence, reading R2",
                     "alpha_range": [float(alpha_r2.min()), float(alpha_r2.max())],
                     "violating_cells": int(bad.sum()), "fraction": float(bad.sum() / base_ok.sum())})
        alpha_scan[pid] = {"baseline_violation_fraction_at_snr_gt_10dB_nominal": baseline, "scan": scan}
        del hc, vc, viol, lost_s0, s3c, s0c, inc_full, alpha_r2, h_, v_, p_, bad, pos

        # ---- SNR relative statistics under each reading
        rule = base["rule"]
        snr_stats[pid] = {
            "reading_R1_nominal": {"selected_median_db": float(np.median(snr_raw[rule])),
                                   "all_matched_median_db": float(np.median(snr_raw[base_ok])),
                                   "selected_median_db_valid_fraction_normalised": float(np.median(snr_nom[rule])),
                                   "all_matched_median_db_valid_fraction_normalised": float(np.median(snr_nom[base_ok]))},
            "reading_R3_beta0": {"selected_median_db": float(np.median(snr_raw[rule]) - 10 * np.log10(sin_l)),
                                 "all_matched_median_db": float(np.median(snr_raw[base_ok]) - 10 * np.log10(sin_l)),
                                 "note": "a constant shift of -10 log10(sin theta_label) = +4.66 dB; the difference is unchanged"}}

        # ---- corrected variants (constant and linear noise; readings R1 and R3)
        for name, scale_, lin in (("nc_R1", 1.0, False), ("nc_R1_linear", 1.0, True),
                                  ("nc_R3", sin_l, False), ("nc_R3_linear", sin_l, True)):
            nh_ = scale_ * ((c0[0] + c1[0] * jj) if lin else c0[0])
            nv_ = scale_ * ((c0[1] + c1[1] * jj) if lin else c0[1])
            h_, v_, x_, pos_, proj_ = corrected(hh, vv, hv, nh_, nv_, fH, fV)
            E = evaluate2(h_, v_, x_, pos_, qtab, exclude_from_windows=proj_)
            run_variant(name, E, {"projected_non_psd": int((proj_ & base_ok).sum()),
                                  "dropped_corrected_diagonal_not_positive": int((base_ok & ~pos_).sum()),
                                  "noise_scale_alpha": float(scale_),
                                  "noise_model": "nes0_coeff_0 + nes0_coeff_1 j" if lin else "nes0_coeff_0"})
            del h_, v_, x_, pos_, proj_, E
            print(f"    {name}: joint {frame[name][pid]['joint']:,}  "
                  f"(base {frame['base'][pid]['joint']:,}); projected {frame[name][pid]['projected_non_psd']:,}", flush=True)
        # legacy v18a variant, for the gate
        h_, v_, x_, pos_ = legacy_corrected(hh, vv, hv, c0[0], c0[1])
        E = evaluate2(h_, v_, x_, pos_, qtab)
        run_variant("legacy_v18a_noise_corrected", E)
        del h_, v_, x_, pos_, E
        # floors: SNR with the valid-fraction normalisation, readings R1 and R3
        for name, fl, al in (("floor3_R1", 3.0, 1.0), ("floor6_R1", 6.0, 1.0),
                             ("floor3_R3", 3.0, sin_l), ("floor6_R3", 6.0, sin_l)):
            snr = 10 * np.log10(np.maximum(np.minimum(hh / (fH * al * c0[0] + 1e-300),
                                                      vv / (fV * al * c0[1] + 1e-300)), 1e-30))
            E = evaluate2(hh, vv, hv, snr >= fl, qtab)
            run_variant(name, E)
            del E, snr
        # ---- G-D
        allc = np.concatenate([d["cells"] for d in discs])
        ii_, jj_ = np.divmod(allc, cols)
        LIc = R["AL"] * ii_ + (R["AL"] - 1) / 2.0
        SIc = jj_.astype(float)
        spec, g = G["spec"], G["grid"]
        rng_c = FCP.interp(g[..., 2], LIc, SIc, spec)
        inc_c = FCP.interp(g[..., 3], LIc, SIc, spec)
        dxs = np.gradient(G["tx"], axis=1) / spec["interval_pix"]
        dys = np.gradient(G["ty"], axis=1) / spec["interval_pix"]
        ux = -FCP.interp(dxs, LIc, SIc, spec)
        uy = -FCP.interp(dys, LIc, SIc, spec)
        nrm = np.hypot(ux, uy)
        ux, uy = ux / nrm, uy / nrm
        xs, ys = G["x"].ravel()[allc], G["y"].ravel()[allc]
        p, q = dem.pq(xs, ys)
        th = np.deg2rad(inc_c)
        loc = np.rad2deg(np.arccos(np.clip((np.cos(th) - np.sin(th) * (p * ux + q * uy)) /
                                           np.sqrt(1 + p * p + q * q), -1, 1)))
        slope = np.rad2deg(np.arctan(np.hypot(p, q)))
        off = 0
        for k_, d in enumerate(discs):
            n_ = d["cells"].size
            sl = slice(off, off + n_)
            off += n_
            geo_rows.append({"id": d_off + k_, "pass": pid,
                             "median_slant_range_sample": float(np.median(jj_[sl])),
                             "median_slant_range_m": float(np.median(rng_c[sl])),
                             "median_incidence_geometry_deg": float(np.median(inc_c[sl])),
                             "median_lola_local_incidence_deg": float(np.nanmedian(loc[sl])),
                             "median_lola_slope_deg": float(np.nanmedian(slope[sl])),
                             "cells_with_dem": int(np.isfinite(loc[sl]).sum())})
        del allc, ii_, jj_, LIc, SIc, rng_c, inc_c, ux, uy, xs, ys, p, q, th, loc, slope
        # slant-range deciles over the frame (joint rule, base)
        jm = np.broadcast_to(np.arange(cols)[None, :], (rows, cols))[base_ok]
        edges = np.unique(np.percentile(jm, np.linspace(0, 100, 11)))
        dec = []
        for lo, hi in zip(edges[:-1], edges[1:]):
            last = hi == edges[-1]
            m_ = base_ok & (jj >= lo) & ((jj <= hi) if last else (jj < hi))
            k_, n_ = int((m_ & base["rule"]).sum()), int(m_.sum())
            dec.append({"sample_from": float(lo), "sample_to": float(hi), "cells": n_, "selected": k_,
                        "rate": k_ / n_ if n_ else None, "wilson95": SC.wilson(k_, n_) if n_ else None,
                        "median_min_snr_db": float(np.median(snr_nom[m_])),
                        "iut": int((m_ & base["iut"]).sum())})
        deciles[pid] = dec
        del jm, snr_nom, snr_raw, jj
        # ---- G-E / G-F: the kernel sweep
        kernel[pid], f2cpr[pid] = {}, {}
        for b in KERNELS:
            if b == 5:
                Eb, hb, vb = base, hh, vv
            else:
                hb, vb, xb = boxed(R, b)
                Eb = evaluate2(hb, vb, xb, None, qtab)
                del xb
            mb = (hb > 0) & (vb > 0) & ((hb + vb) > 0)
            rec = {"matched_cells": int(Eb["ok"].sum()), "joint": int(Eb["rule"].sum()),
                   "joint_fraction": float(Eb["rule"].sum() / Eb["ok"].sum()),
                   "dop_below_0p13": int((Eb["ok"] & (Eb["dop"] < DOP_T)).sum()),
                   "iut": int(Eb["iut"].sum()),
                   "n_hat_ge_79p6_anywhere": int((Eb["ok"] & np.isfinite(Eb["nh"]) & (Eb["nh"] >= N_EDGE)).sum())}
            rec.update(selected_n(Eb))
            rec["blocks_64x64"] = n_blocks(Eb, Eb["s0"], mb)
            rec["selected_with_iut_n_hat_ge_79p6"] = int((Eb["rule"] & np.isfinite(Eb["nh"]) & (Eb["nh"] >= N_EDGE)).sum())
            kernel[pid][f"{b}x{b}"] = rec
            if pid == "20200808":
                blk = {"cells_f2_fixed_b5_signal_set": f2_cpr_block(Eb, f2mask)}
                own = Eb["ok"] & (hb > c0[0]) & (vb > c0[1]) & (np.hypot(G["x"] - x0, G["y"] - y0) <= FCP.DISC_R_M)
                blk["cells_f2_own_signal_set"] = f2_cpr_block(Eb, own)
                f2cpr[pid][f"{b}x{b}"] = blk
            print(f"    kernel {b}x{b}: joint {rec['joint']:,}, IUT {rec['iut']}, selected local N median "
                  f"{rec['selected_local_N'].get('median', float('nan')):.1f}, >=79.6: "
                  f"{rec['n_selected_with_local_N_ge_79p6']}, blocks N median "
                  f"{rec['blocks_64x64']['N_logratio'].get('median', float('nan')):.2f}", flush=True)
            if b != 5:
                del Eb, hb, vb
        del hh, vv, hv, fH, fV, base, R, G, full
        import gc
        gc.collect()

    if args.max_lines:
        print("  smoke test: nothing written")
        return 0
    # ---- gates: the published counts are reproduced
    prev = sorted((d["pass"], d["rule"]) for d in clr["per_disc_v18"])
    now = sorted((dr_["pass"], c) for dr_, c in zip(disc_rows, vcounts["base"]))
    reproduces = (prev == now) and len(disc_rows) == clr["discs"]["count"]
    legacy_ok = (frame["legacy_v18a_noise_corrected"]["20200808"]["joint"] == 23784
                 and f2v["legacy_v18a_noise_corrected"]["published_rule_selects"] == 48)
    blocks_ok = kernel["20200808"]["5x5"]["blocks_64x64"]["blocks"] == 109
    print(f"  base discs reproduce crater_level_real: {reproduces}; v18a noise-corrected reproduced: {legacy_ok}; "
          f"109 blocks: {blocks_ok}", flush=True)

    # ---- disc rates per variant
    vdisc = {v: disc_rates(vcounts[v], disc_rows) for v in variants}
    viut_d = {v: disc_rates(viut[v], disc_rows) for v in ("base", "nc_R1", "nc_R3", "floor3_R1", "floor6_R1")}

    # ---- the flags (G-B)
    f2_base = f2v["base"]["published_rule_selects"]
    flags = {}
    for v in NOISE + FLOORS:
        chg = (f2v[v]["published_rule_selects"] - f2_base) / f2_base
        dd = {}
        for k in ("20200808_outside", "20200808_inside", "all_outside", "all_inside"):
            a, b = vdisc["base"][k]["ge1"]["rate"], vdisc[v][k]["ge1"]["rate"]
            dd[k] = 100 * (b - a)
        flags[v] = {"f2_selections": f2v[v]["published_rule_selects"], "f2_relative_change": chg,
                    "f2_changes_by_more_than_20_percent": bool(abs(chg) > 0.20),
                    "disc_rate_change_points": dd,
                    "sunlit_or_psr_rate_changes_by_more_than_2_points": bool(max(abs(x) for x in dd.values()) > 2.0)}

    scales = {
        "snr_denominator": ("the channel's label nes0_coeff_0 (LH 7.038e-4, LV 6.065e-4; -31.5 / -32.2 dB), used as "
                            "given: sigma0-type, no sin(theta) applied; the calibrated intensity it divides is "
                            "l = DN^2 sin(theta_label) / (K G^2), i.e. sigma0-scale with the label's scalar "
                            "sin(theta) = 0.342"),
        "subtracted_noise": "the same number, subtracted from C_HH and C_VV of that calibrated coherency",
        "consistent_with_each_other": True,
        "consistent_with_the_data": ("NO at face value (reading R1): the corrected matrix is not positive semidefinite "
                                     "in the fraction of cells reported in alpha_scan, far above the fraction at SNR > "
                                     "10 dB where the correction is negligible; the excess vanishes at alpha <= about 0.5"),
    }
    snr = json.loads(OUT_SNR.read_text(encoding="utf-8"))
    recon = {
        "schema": "lunar-ice/snr-reconciliation/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/gap_v20_frame.py", "seed": None,
        "seed_note": "draws nothing; every rate is a count with a Wilson interval",
        "radiometric_scales": scales,
        "readings": {"R1": "nes0 is sigma0 as labelled; noise in the calibrated scale = nes0 (alpha = 1)",
                     "R2": "nes0 is sigma0 at the local incidence of the geometry file; alpha = sin(20 deg) / sin(theta_local(j))",
                     "R3": "nes0 is beta0; noise in the calibrated (sigma0) scale = nes0 sin(20 deg), alpha = 0.342"},
        "decomposition_of_the_v18a_drops": decomposition,
        "alpha_scan": alpha_scan,
        "snr_relative_statistics": snr_stats,
        "fixes": ["noise scaled by the window's valid-sample fraction", "non-PSD cells projected and kept (left out of the "
                  "N-hat windows) instead of dropped", "floors on SNR = C / (f n)"],
        "variants_frame": frame, "variants_f2": f2v, "variants_disc_rates": vdisc, "variants_iut_disc_rates": viut_d,
        "flags": flags, "gates": {"base_discs_reproduce_crater_level_real": bool(reproduces),
                                  "v18a_noise_corrected_reproduced": bool(legacy_ok), "blocks_109": bool(blocks_ok)},
        "run_info": {**run_info(), "wall_s": round(time.time() - t0, 1)}}
    snr["v20_reconciliation"] = recon
    OUT_SNR.write_text(json.dumps(snr, indent=2, default=float), encoding="utf-8")

    OUT_KERNEL.write_text(json.dumps({
        "schema": "lunar-ice/kernel-sweep/1", "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/gap_v20_frame.py", "seed": None, "seed_note": "draws nothing",
        "definition": "boxcar k x k applied after the 21-sample azimuth mean (5 is the published kernel)",
        "kernels": [f"{b}x{b}" for b in KERNELS], "n_edge": N_EDGE, "band_edge": BAND_EDGE,
        "kernel_sweep": kernel, "f2_cpr_distribution": f2cpr,
        "reproduces_published_5x5": {"blocks_109": bool(blocks_ok), "joint_pass1": kernel["20200808"]["5x5"]["joint"]},
        "run_info": {**run_info(), "wall_s": round(time.time() - t0, 1)}}, indent=2, default=float), encoding="utf-8")

    clr = json.loads(OUT_CLR.read_text(encoding="utf-8"))
    v20 = clr.get("v20_gap", {})
    v20["per_disc_geometry"] = geo_rows
    v20["per_disc_geometry_source"] = {
        "generator": "backend/scripts/gap_v20_frame.py",
        "slant_range_sample": "the SLC column of each of the disc's cells (median)",
        "slant_range_and_incidence_geometry": "bundle geometry file (Slant_Range, Incidence_Angle), tie-point grid "
                                              "interpolated to the cell",
        "lola_local_incidence": "LDEM_80S_20M gradient over +-2 posts (80 m), look vector from the geometry file; see the "
                                "module docstring"}
    v20["geometry_frame"] = {"selection_rate_by_slant_range_decile": deciles}
    clr["v20_gap"] = v20
    OUT_CLR.write_text(json.dumps(clr, indent=2, default=float), encoding="utf-8")
    print(f"  wrote {OUT_KERNEL.name}, merged v20_reconciliation and geometry ({time.time() - t0:.0f} s)")
    return 0 if (reproduces and legacy_ok and blocks_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
