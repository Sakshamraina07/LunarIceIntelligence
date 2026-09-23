"""
f2_complex_product.py -- the published rule and the IUT on crater F2 in the
COMPLEX product, and at crater scale over both passes. (v17a referee report,
P2 and P3; also writes the cache Fig. `fig_scene.pdf` is drawn from)

    python backend/scripts/f2_complex_product.py

GEOLOCATION
-----------
Each bundle ships a geolocation tie-point grid for its SLI (geometry/…/
*_g_sli_xx_cp_xx_d18.csv): latitude, longitude, slant range and incidence at
every 32nd line and 32nd sample (isda:sli_grid_* in *_g_xxx_…xml). A
complex-product cell i, j (21 lines, then the 5 x 5 boxcar, build_coherency)
sits at SLC line 21 i + 10, sample j; its ground position is the bilinear
interpolation of the tie points' south-polar-stereographic (x, y) (R 1737.4 km,
lon0 0: the delivered frame's projection). The tie points are
terrain-dependent -- incidence and ground spacing jump at crater walls -- so
the interpolation is checked two ways:
  * HOLD-OUT: every tie point at an odd grid index is predicted from the
    even-index points alone (twice the native spacing: a pessimistic bound),
    and the error is converted to SLC pixels through the local Jacobian;
  * IMAGE CLOSURE: the complex product's own LH intensity, geolocated this
    way, is binned onto the delivered map grid (25 m) around F2 and
    cross-correlated with the delivered LH product; the peak's offset is the
    residual misregistration in metres.

P2. F2's disc is the centre and radius that gave the delivered grid's
1521-px disc (f2_footprint.json: -87.39, 82.31; 22 px x 25 m = 550 m). Cells
with signal: boxcar'd calibrated intensity above the label's NESZ
(nes0_coeff_0) in BOTH channels. The published rule: sample DOP < 0.13 and
R > 1 (physical sign). The IUT: R > F^-1_0.95(2 N_hat, 2 N_hat) and sample DOP
< q05(N_hat), N_hat from Var(ln R) over the 31 x 31 window of matched cells
(decision_rule.py's estimator and table, unchanged).

P3. Both passes are tiled into non-overlapping discs of F2's radius on a
square lattice of pitch 2 R in (x, y); each disc keeps its n_F2 signal cells
nearest the centre (n_F2 = F2's count), discs with fewer are dropped. Discs
are classed by the LOLA PSR mask (LPSR_75S_120M_201608, nearest neighbour)
as outside, inside or mixed. Sunlit polar terrain is where the criterion's
proponents do not claim ice; it is NOT a proven ice-free null (subsurface ice
can be thermally stable outside PSRs), so its rates are a real-data
comparison, not a false-positive rate. The sunlit discs' median population
(CPR, circular coherence gamma_c, log-ratio look count) is then simulated on
F2's own cell layout -- correlated SC / OC fields at the complex product's
lags, the look count matched by the same log-ratio estimator -- and the
simulated crater-level rates compared with the real ones.
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.ndimage import map_coordinates, uniform_filter
from scipy.stats import f as Fdist

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runinfo import run_info  # noqa: E402
import stokes_from_slc as SFS  # noqa: E402
import enl_logratio as L  # noqa: E402
import decision_rule as DR  # noqa: E402
import f2_maximum as F2M  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT_P2 = BASE_DIR / "docs" / "f2_complex_product.json"
OUT_P3 = BASE_DIR / "docs" / "crater_level_real.json"
CACHE = BASE_DIR / "data" / "derived" / "fig_scene" / "fig_scene_cache.npz"
FOOT = BASE_DIR / "docs" / "f2_footprint.json"
GRID_JSON = BASE_DIR / "docs" / "complex_grid_correlation.json"
R_MOON = 1737400.0
DISC_R_M = 22 * 25.0                  # the delivered disc: 22 px at 25 m
SEED = 20261009
SIM_TRIALS = 10_000
DOP_T = 0.13
GEOM = {"20200808": BASE_DIR / "data/pradan/raw/geometry/calibrated/20200808",
        "20200305": BASE_DIR / "data/generality/20200305/geometry/calibrated/20200305"}
SINHA_CRATERS = ("F2", "F3", "H3", "S1")

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def stereo(lat, lon):
    rho = 2 * R_MOON * np.tan(np.pi / 4 + np.deg2rad(lat) / 2)
    t = np.deg2rad(lon)
    return rho * np.sin(t), rho * np.cos(t)


def tie_grid(pass_id):
    stem = PASS_STEM[pass_id]
    xml = (GEOM[pass_id] / f"{stem}_g_xxx_xx_cp_xx_d18.xml").read_text(encoding="utf-8", errors="replace")
    spec = {k: int(re.search(rf"<isda:sli_grid_{k}>(\d+)<", xml).group(1))
            for k in ("no_samples", "no_records", "interval_scan", "interval_pix")}
    g = np.loadtxt(GEOM[pass_id] / f"{stem}_g_sli_xx_cp_xx_d18.csv", delimiter=",", skiprows=1)
    g = g.reshape(spec["no_records"], spec["no_samples"], 4)
    x, y = stereo(g[..., 0], g[..., 1])
    return spec, g, x, y


PASS_STEM = {"20200808": "ch2_sar_ncxl_20200808t201154198",
             "20200305": "ch2_sar_ncxl_20200305t114902885"}


def interp(field, lines, samples, spec):
    return map_coordinates(field, [np.asarray(lines, float) / spec["interval_scan"],
                                   np.asarray(samples, float) / spec["interval_pix"]],
                           order=1, mode="nearest")


def holdout_closure(x, y, spec) -> dict:
    """Odd-index tie points predicted from the even-index lattice; errors in
    metres and, through the local Jacobian, in SLC lines and samples."""
    xe, ye = x[::2, ::2], y[::2, ::2]
    ii, jj = np.meshgrid(np.arange(x.shape[0]), np.arange(x.shape[1]), indexing="ij")
    held = (ii % 2 == 1) | (jj % 2 == 1)
    inside = (ii <= 2 * (xe.shape[0] - 1)) & (jj <= 2 * (xe.shape[1] - 1))
    sel = held & inside
    px = map_coordinates(xe, [ii[sel] / 2.0, jj[sel] / 2.0], order=1)
    py = map_coordinates(ye, [ii[sel] / 2.0, jj[sel] / 2.0], order=1)
    ex, ey = px - x[sel], py - y[sel]
    # local Jacobian d(x, y)/d(line, sample) from the full lattice
    dxl = np.gradient(x, axis=0) / spec["interval_scan"]
    dyl = np.gradient(y, axis=0) / spec["interval_scan"]
    dxs = np.gradient(x, axis=1) / spec["interval_pix"]
    dys = np.gradient(y, axis=1) / spec["interval_pix"]
    a, b, c, d = dxl[sel], dxs[sel], dyl[sel], dys[sel]
    det = a * d - b * c
    ok = np.abs(det) > 1e-9
    dl = np.where(ok, (d * ex - b * ey) / np.where(ok, det, 1), np.nan)
    ds = np.where(ok, (-c * ex + a * ey) / np.where(ok, det, 1), np.nan)
    e = np.hypot(ex, ey)

    def q(v):
        v = v[np.isfinite(v)]
        return {"rms": float(np.sqrt(np.mean(v ** 2))), "median_abs": float(np.median(np.abs(v))),
                "p95_abs": float(np.percentile(np.abs(v), 95))}
    return {"points": int(sel.sum()), "spacing_used": "2 x native (even-index lattice only)",
            "error_m": q(e), "error_lines": q(dl), "error_samples": q(ds),
            "error_complex_rows": q(dl / SFS.AZIMUTH_LOOKS)}


def image_closure(xc, yc, hh, rows, cols) -> dict:
    """Bin the complex product's LH intensity onto the delivered map grid
    around F2 and cross-correlate with the delivered LH DN^2."""
    import tifffile
    from app.ingestion.sar_geometry import read_geotiff_frame
    raw = BASE_DIR / "data/pradan/raw/data/calibrated/20200808"
    stem = PASS_STEM["20200808"]
    frame = read_geotiff_frame(raw / f"{stem}_d_sri_xx_cp_lh_d18.tif", raw / f"{stem}_d_sri_xx_cp_xx_d18.xml")
    dn = tifffile.imread(str(raw / f"{stem}_d_sri_xx_cp_lh_d18.tif")).astype(np.float64)
    foot = json.loads(FOOT.read_text(encoding="utf-8"))
    l0, s0 = foot["frame_pixel"]["line"], foot["frame_pixel"]["sample"]
    half = 160
    ln, sm = frame.xy_to_pixel(xc, yc)
    li, si = np.rint(ln - (l0 - half)).astype(int), np.rint(sm - (s0 - half)).astype(int)
    keep = (li >= 0) & (li < 2 * half) & (si >= 0) & (si < 2 * half) & (hh > 0)
    acc = np.zeros((2 * half, 2 * half)); cnt = np.zeros_like(acc)
    np.add.at(acc, (li[keep], si[keep]), hh[keep]); np.add.at(cnt, (li[keep], si[keep]), 1)
    cp = np.where(cnt > 0, acc / np.maximum(cnt, 1), np.nan)
    L0, S0 = int(round(l0)) - half, int(round(s0)) - half
    ref = dn[L0:L0 + 2 * half, S0:S0 + 2 * half] ** 2
    a = np.log(np.where(np.isfinite(cp) & (cp > 0), cp, np.nan))
    b = np.log(np.where(ref > 0, ref, np.nan))
    best, grid = None, []
    M = 12
    for dy in range(-M, M + 1):
        for dx in range(-M, M + 1):
            aa = a[max(0, dy):2 * half + min(0, dy), max(0, dx):2 * half + min(0, dx)]
            bb = b[max(0, -dy):2 * half + min(0, -dy), max(0, -dx):2 * half + min(0, -dx)]
            v = np.isfinite(aa) & np.isfinite(bb)
            if v.sum() < 500:
                continue
            r = float(np.corrcoef(aa[v], bb[v])[0, 1])
            grid.append((dy, dx, r))
            if best is None or r > best[2]:
                best = (dy, dx, r, int(v.sum()))
    r0 = next((g[2] for g in grid if g[0] == 0 and g[1] == 0), None)
    return {"window_map_px": 2 * half, "map_px_m": 25.0, "search_px": M,
            "peak_offset_px": {"line": best[0], "sample": best[1]},
            "peak_offset_m": 25.0 * float(np.hypot(best[0], best[1])),
            "peak_correlation": best[2], "correlation_at_zero_offset": r0,
            "overlap_px": best[3],
            "quantity": "log LH intensity: complex product (21 looks, no boxcar) binned to 25 m vs delivered DN^2"}


def wilson(k, n, z=1.959964):
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [float(c - h), float(c + h)]


def load_pass(pass_id, qtab, psr):
    """Every per-cell field this script needs, for one pass."""
    SFS.configure(pass_id)
    lab = SFS.label_fields()
    src = (SFS.RAW / f"{SFS.STEM}_d_sli_xx_cp_xx_d18.xml").read_text(encoding="utf-8", errors="replace")
    nes = [float(v) for v in re.findall(r"<isda:nes0_coeff_0>([^<]+)<", src)]
    hh, vv, hv, info = SFS.build_coherency(0, smooth=False)
    raw_both = (hh > 0) & (vv > 0)
    from scipy.ndimage import binary_erosion
    # cells whose whole 5 x 5 boxcar window holds data in both channels: the
    # boxcar spreads values into zero-fill, so edge cells average fewer looks
    full = binary_erosion(raw_both, np.ones((5, 5), dtype=bool))
    hh_raw_lh = hh.astype(np.float32)
    hh, vv = SFS.boxcar2d(hh), SFS.boxcar2d(vv)
    hv = SFS.boxcar2d(hv.real) + 1j * SFS.boxcar2d(hv.imag)
    s0 = hh + vv
    s1, s2, s3 = hh - vv, 2.0 * hv.real, -2.0 * hv.imag       # physical sign
    m = (hh > 0) & (vv > 0) & (s0 > 0)
    sc, oc = 0.5 * (s0 - s3), 0.5 * (s0 + s3)
    ok = m & (sc > 0) & (oc > 0)
    lr = np.where(ok, np.log(np.where(ok, sc, 1.0) / np.where(ok, oc, 1.0)), np.nan)
    R = np.exp(lr).astype(np.float32)
    dop = np.where(m, np.sqrt(s1 ** 2 + s2 ** 2 + s3 ** 2) / np.where(m, s0, 1.0), np.nan).astype(np.float32)
    coh = np.where(m, np.abs(hv) / np.sqrt(np.maximum(hh * vv, 1e-300)), np.nan).astype(np.float32)
    gam = np.where(m, np.sqrt(s1 ** 2 + s2 ** 2) / np.sqrt(np.maximum(s0 ** 2 - s3 ** 2, 1e-300)),
                   np.nan).astype(np.float32)
    signal = ok & (hh > nes[0]) & (vv > nes[1])
    del s0, s1, s2, s3, sc, oc, hv
    nh, _ = L.local_n(lr, ok)
    nh = nh.astype(np.float32)
    rule = ok & (dop < DOP_T) & (R > 1.0)
    fin = ok & np.isfinite(nh)
    iut = np.zeros_like(ok)
    iut[fin] = (R[fin] > DR.crit(nh[fin])) & (dop[fin] < DR.q05_at(nh[fin], qtab))
    spec, g, tx, ty = tie_grid(pass_id)
    rows, cols = hh.shape
    li = SFS.AZIMUTH_LOOKS * np.arange(rows) + (SFS.AZIMUTH_LOOKS - 1) / 2.0
    LI, SI = np.meshgrid(li, np.arange(cols), indexing="ij")
    xc = interp(tx, LI, SI, spec).astype(np.float64)
    yc = interp(ty, LI, SI, spec).astype(np.float64)
    del LI, SI
    gpsr, apsr = psr
    base = {"zero_based": 0.0, "half_pixel": 0.5, "one_based": 1.0}[gpsr.base]
    pl = np.rint(gpsr.lpo - yc / gpsr.scale_m - base).astype(np.int64)
    ps = np.rint(gpsr.spo + xc / gpsr.scale_m - base).astype(np.int64)
    inb = (pl >= 0) & (pl < apsr.shape[0]) & (ps >= 0) & (ps < apsr.shape[1])
    in_psr = np.zeros(xc.shape, dtype=bool)
    in_psr[inb] = apsr[pl[inb], ps[inb]] > 0.5
    return {"pass": pass_id, "spec": spec, "tie": (g, tx, ty), "shape": (rows, cols),
            "x": xc, "y": yc, "ok": ok, "signal": signal, "raw_both": raw_both, "full": full,
            "R": R, "dop": dop, "coh": coh, "gam": gam, "nh": nh, "rule": rule, "iut": iut,
            "psr": in_psr, "hh_raw": hh_raw_lh, "nesz": nes, "azimuth_looks": SFS.AZIMUTH_LOOKS}


def crater_block(P, x0, y0, radius, name):
    d = np.hypot(P["x"] - x0, P["y"] - y0)
    disc = d <= radius
    n = int(disc.sum())
    out = {"name": name, "inside_frame": bool(n > 0), "cells_in_disc": n}
    if not n:
        return out, None
    sig = disc & P["signal"]
    sel = disc & P["signal"] & P["rule"]
    iut = disc & P["signal"] & P["iut"]
    ii, jj = np.nonzero(sel)
    cells = []
    for i, j in zip(ii, jj):
        nh = float(P["nh"][i, j])
        c = float(DR.crit(nh)) if np.isfinite(nh) else None
        cells.append({"row": int(i), "col": int(j), "sample_cpr": float(P["R"][i, j]),
                      "sample_dop": float(P["dop"][i, j]), "local_N_hat": nh, "crit_95_at_N_hat": c,
                      "R_gt_crit": bool(c is not None and P["R"][i, j] > c),
                      "iut_selects": bool(P["iut"][i, j]), "in_psr": bool(P["psr"][i, j]),
                      "full_window": bool(P["full"][i, j])})
    out.update({
        "cells_nonzero_both_channels": int((disc & P["raw_both"]).sum()),
        "cells_matched": int((disc & P["ok"]).sum()),
        "cells_with_signal": int(sig.sum()),
        "signal_definition": "boxcar'd calibrated intensity above the label NESZ (nes0_coeff_0) in both channels",
        "fraction_with_signal": float(sig.sum() / n),
        "fraction_in_psr": float((disc & P["psr"]).sum() / n),
        "published_rule_selects": int(sel.sum()),
        "iut_selects": int(iut.sum()),
        "cells_full_window": int((disc & P["full"]).sum()),
        "published_rule_selects_full_window": int((sel & P["full"]).sum()),
        "iut_selects_full_window": int((iut & P["full"]).sum()),
        "selected_with_R_gt_crit_at_N_hat": int(sum(c["R_gt_crit"] for c in cells)),
        "median_over_signal": {"cpr": float(np.nanmedian(P["R"][sig])) if sig.any() else None,
                               "dop": float(np.nanmedian(P["dop"][sig])) if sig.any() else None,
                               "coherence": float(np.nanmedian(P["coh"][sig])) if sig.any() else None,
                               "N_hat": float(np.nanmedian(P["nh"][sig])) if sig.any() else None},
        "selected_cells": cells})
    return out, sig


def tile_discs(P, n_target, radius):
    """Non-overlapping discs on a square lattice of pitch 2 radius; each keeps
    its n_target signal cells nearest the centre."""
    sig = P["signal"]
    idx = np.flatnonzero(sig.ravel())
    x, y = P["x"].ravel()[idx], P["y"].ravel()[idx]
    pitch = 2 * radius
    cx, cy = np.rint(x / pitch).astype(np.int64), np.rint(y / pitch).astype(np.int64)
    d = np.hypot(x - cx * pitch, y - cy * pitch)
    keep = d <= radius
    idx, cx, cy, d = idx[keep], cx[keep], cy[keep], d[keep]
    key = (cx - cx.min()) * (cy.max() - cy.min() + 1) + (cy - cy.min())
    order = np.lexsort((d, key))
    idx, key, d = idx[order], key[order], d[order]
    start = np.r_[0, np.flatnonzero(np.diff(key)) + 1]
    size = np.diff(np.r_[start, key.size])
    discs = []
    flat = {k: P[k].ravel() for k in ("rule", "iut", "psr", "coh", "R", "gam", "nh", "full")}
    for s, n in zip(start, size):
        if n < n_target:
            continue
        cells = idx[s:s + n_target]
        pf = float(flat["psr"][cells].mean())
        discs.append({"pass": P["pass"], "rule": int(flat["rule"][cells].sum()),
                      "iut": int(flat["iut"][cells].sum()), "psr_fraction": pf,
                      "rule_full_window": int((flat["rule"][cells] & flat["full"][cells]).sum()),
                      "full_window_cells": int(flat["full"][cells].sum()),
                      "class": "outside" if pf == 0.0 else ("inside" if pf == 1.0 else "mixed"),
                      "median_coherence": float(np.nanmedian(flat["coh"][cells])),
                      "median_cpr": float(np.nanmedian(flat["R"][cells])),
                      "median_gamma_c": float(np.nanmedian(flat["gam"][cells])),
                      "median_N_hat": float(np.nanmedian(flat["nh"][cells]))})
    return discs


def summarize_discs(ds):
    out = {}
    for cls in ("outside", "inside", "mixed"):
        g = [d for d in ds if d["class"] == cls]
        n = len(g)
        blk = {"discs": n}
        if n:
            for key in ("rule", "iut", "rule_full_window"):
                a = np.array([d[key] for d in g])
                k1, k5 = int((a >= 1).sum()), int((a >= 5).sum())
                blk[key] = {"p_ge_1": k1 / n, "p_ge_1_wilson95": wilson(k1, n),
                            "p_ge_5": k5 / n, "p_ge_5_wilson95": wilson(k5, n),
                            "mean": float(a.mean()), "mean_se": float(a.std(ddof=1) / np.sqrt(n)) if n > 1 else None}
            for key in ("median_coherence", "median_cpr", "median_gamma_c", "median_N_hat"):
                blk[f"{key}_over_discs"] = float(np.median([d[key] for d in g]))
        out[cls] = blk
    return out


def simulate_sunlit(layout, cpr, gam, n_target, rng, trials) -> dict:
    """The published rule and the IUT on F2's cell layout at the sunlit
    discs' median population, correlated SC / OC fields at the complex
    product's lags; looks per channel matched by the log-ratio estimator."""
    gc = json.loads(GRID_JSON.read_text(encoding="utf-8"))["lag_correlation_before_boxcar"]
    rsc = (np.sqrt(gc["SC"]["azimuth_lines"][0]), np.sqrt(gc["SC"]["range_samples"][0]))
    roc = (np.sqrt(gc["OC"]["azimuth_lines"][0]), np.sqrt(gc["OC"]["range_samples"][0]))
    a, b = cpr / (1 + cpr), 1 / (1 + cpr)
    mask, n_hat_target, qtab = layout["mask"], layout["n_hat"], layout["qtab"]
    H, W = mask.shape
    M = 4 + 15

    def field(Lk, batch):
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

    # looks per channel: the L whose single-cell log-ratio N is nearest the target
    cal = {}
    for Lk in range(2, 41, 2):
        bs, bo, _ = field(Lk, 2)
        cal[Lk] = float(L.n_from_var(np.var(np.log(bs / bo)[:, M:-M, M:-M], ddof=1)))
        if cal[Lk] > 1.5 * n_hat_target:
            break
    Lc = min(cal, key=lambda k: abs(cal[k] - n_hat_target))
    rule_n, iut_n = [], []
    batch = 50
    for _ in range(0, trials, batch):
        bs, bo, bx = field(Lc, batch)
        r = bs / bo
        m = np.sqrt((bs - bo) ** 2 + 4 * np.abs(bx) ** 2) / (bs + bo)
        lr = np.log(r)
        for t in range(batch):
            nh, _ = L.local_n(lr[t], np.ones_like(lr[t], dtype=bool))
            rr, mm, nn = r[t, M:-M, M:-M][mask], m[t, M:-M, M:-M][mask], nh[M:-M, M:-M][mask]
            rule_n.append(int(((mm < DOP_T) & (rr > 1.0)).sum()))
            fin = np.isfinite(nn)
            iut_n.append(int(((rr[fin] > DR.crit(nn[fin])) & (mm[fin] < DR.q05_at(nn[fin], qtab))).sum()))
    out = {"population": {"cpr": cpr, "gamma_c": gam,
                          "dop": float(np.sqrt(((cpr - 1) / (cpr + 1)) ** 2 + gam ** 2 * (1 - ((cpr - 1) / (cpr + 1)) ** 2)))},
           "look_calibration_log_ratio": {str(k): v for k, v in cal.items()},
           "looks_per_channel": Lc, "achieved_log_ratio_N": cal[Lc], "target_N_hat": n_hat_target,
           "cells_tested": int(mask.sum()), "trials": len(rule_n)}
    for key, arr in (("rule", np.array(rule_n)), ("iut", np.array(iut_n))):
        t = arr.size
        p1, p5 = float((arr >= 1).mean()), float((arr >= 5).mean())
        out[key] = {"p_ge_1": p1, "p_ge_1_se": float(np.sqrt(p1 * (1 - p1) / t)),
                    "p_ge_5": p5, "p_ge_5_se": float(np.sqrt(p5 * (1 - p5) / t)),
                    "mean": float(arr.mean()), "mean_se": float(arr.std(ddof=1) / np.sqrt(t))}
    return out


def simulate_disc_mixture(layout, discs, rng, per_disc) -> dict:
    """Each sunlit disc simulated at ITS OWN median population (CPR, gamma_c)
    and look count, on F2's cell layout; the predicted fraction of discs with
    >= 1 (>= 5) selections is the mean of the per-disc probabilities. This
    carries the between-disc heterogeneity the single median population
    cannot."""
    gc = json.loads(GRID_JSON.read_text(encoding="utf-8"))["lag_correlation_before_boxcar"]
    rsc = (np.sqrt(gc["SC"]["azimuth_lines"][0]), np.sqrt(gc["SC"]["range_samples"][0]))
    roc = (np.sqrt(gc["OC"]["azimuth_lines"][0]), np.sqrt(gc["OC"]["range_samples"][0]))
    mask = layout["mask"]
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
    p1, p5 = [], []
    for d in discs:
        Lk = int(ks[np.argmin(np.abs(ns - d["median_N_hat"]))])
        bs, bo, bx = field(Lk, per_disc, d["median_cpr"], min(d["median_gamma_c"], 0.999))
        r = (bs / bo)[:, M:-M, M:-M][:, mask]
        m = (np.sqrt((bs - bo) ** 2 + 4 * np.abs(bx) ** 2) / (bs + bo))[:, M:-M, M:-M][:, mask]
        k = ((m < DOP_T) & (r > 1.0)).sum(axis=1)
        p1.append(float((k >= 1).mean())); p5.append(float((k >= 5).mean()))
    p1, p5 = np.array(p1), np.array(p5)
    n = len(discs)
    return {"discs": n, "trials_per_disc": per_disc,
            "look_calibration_log_ratio": {str(k): v for k, v in cal.items()},
            "predicted_p_ge_1": float(p1.mean()),
            "predicted_p_ge_1_se": float(np.sqrt(np.sum(p1 * (1 - p1) / per_disc)) / n),
            "predicted_p_ge_5": float(p5.mean()),
            "predicted_p_ge_5_se": float(np.sqrt(np.sum(p5 * (1 - p5) / per_disc)) / n),
            "discs_with_predicted_p_ge_1_above_0p5": int((p1 > 0.5).sum())}


def main() -> int:
    import validate_psr_vs_lola as V
    t0 = time.time()
    foot = json.loads(FOOT.read_text(encoding="utf-8"))
    F2 = foot["target"]
    x0, y0 = stereo(F2["lat_deg"], F2["lon_deg"])
    dr = json.loads((BASE_DIR / "docs" / "decision_rule.json").read_text(encoding="utf-8"))
    qtab = {int(k): v for k, v in dr["dop_quantile_table"]["q05"].items()}
    psr = V.load_pds("LPSR_75S_120M_201608")
    print("=" * 78); print("P2 / P3 — the rule on F2 and at crater scale, complex product"); print("=" * 78)

    passes, p2, discs, cache = {}, {}, [], {}
    f2_layout = None
    for pid in ("20200808", "20200305"):
        P = load_pass(pid, qtab, psr)
        g, tx, ty = P["tie"]
        clos = holdout_closure(tx, ty, P["spec"])
        print(f"  {pid}: tie grid {P['spec']}; hold-out closure rms {clos['error_m']['rms']:.1f} m, "
              f"{clos['error_lines']['rms']:.1f} lines, {clos['error_samples']['rms']:.2f} samples", flush=True)
        craters = {}
        f2, f2sig = crater_block(P, x0, y0, DISC_R_M, "F2")
        craters["F2"] = f2
        for nm in SINHA_CRATERS[1:]:
            craters[nm] = {"name": nm, "inside_frame": None,
                           "status": ("coordinates not in the repository; the publisher's page "
                                      "redirects to a sign-in flow, so they were not read. Needs the "
                                      "author to supply centre latitude, longitude and diameter")}
        entry = {"tie_grid": {k: v for k, v in P["spec"].items()},
                 "tie_grid_source": f"{PASS_STEM[pid]}_g_sli_xx_cp_xx_d18.csv",
                 "complex_product_shape": list(P["shape"]), "azimuth_looks": P["azimuth_looks"],
                 "nesz_linear": P["nesz"],
                 "cells_matched": int(P["ok"].sum()), "cells_with_signal": int(P["signal"].sum()),
                 "cells_in_psr": int((P["psr"] & P["ok"]).sum()),
                 "published_rule_selects": int(P["rule"].sum()), "iut_selects": int(P["iut"].sum()),
                 "closure_holdout": clos, "craters": craters}
        if pid == "20200808":
            ic = image_closure(P["x"].ravel(), P["y"].ravel(), P["hh_raw"].ravel(), None, None)
            entry["closure_image"] = ic
            print(f"  image closure near F2: peak offset {ic['peak_offset_px']} map px "
                  f"({ic['peak_offset_m']:.0f} m), r = {ic['peak_correlation']:.3f} "
                  f"(r at zero offset {ic['correlation_at_zero_offset']:.3f})", flush=True)
            if f2sig is not None:
                ii, jj = np.nonzero((np.hypot(P["x"] - x0, P["y"] - y0) <= DISC_R_M))
                sub = f2sig[ii.min():ii.max() + 1, jj.min():jj.max() + 1]
                f2_layout = {"mask": sub, "rows": [int(ii.min()), int(ii.max())],
                             "cols": [int(jj.min()), int(jj.max())]}
            # figure cache: the frame in rotated along-/cross-track map coordinates
            xs, ys = P["x"][P["ok"]], P["y"][P["ok"]]
            cov = np.cov(np.vstack([xs[::97], ys[::97]]))
            ev, evec = np.linalg.eigh(cov)
            ax_ = evec[:, 1]
            th = float(np.arctan2(ax_[1], ax_[0]))
            c_, s_ = np.cos(-th), np.sin(-th)
            u = c_ * P["x"] - s_ * P["y"]; v = s_ * P["x"] + c_ * P["y"]
            B = 100.0
            u0, v0 = np.nanmin(u[P["ok"]]), np.nanmin(v[P["ok"]])
            ui = ((u - u0) / B).astype(np.int64); vi = ((v - v0) / B).astype(np.int64)
            nu, nv = int(ui[P["ok"]].max()) + 1, int(vi[P["ok"]].max()) + 1
            o = P["ok"]
            lcpr = np.log10(P["R"][o].astype(np.float64))
            acc = np.zeros((nv, nu)); cnt = np.zeros((nv, nu)); pacc = np.zeros((nv, nu))
            np.add.at(acc, (vi[o], ui[o]), lcpr); np.add.at(cnt, (vi[o], ui[o]), 1)
            np.add.at(pacc, (vi[o], ui[o]), P["psr"][o].astype(float))
            sel = P["rule"]
            cache = {"log10_cpr": np.where(cnt > 0, acc / np.maximum(cnt, 1), np.nan).astype(np.float32),
                     "psr_frac": np.where(cnt > 0, pacc / np.maximum(cnt, 1), np.nan).astype(np.float32),
                     "bin_m": B, "u0": u0, "v0": v0, "theta": th,
                     "sel_u": u[sel].astype(np.float32), "sel_v": v[sel].astype(np.float32),
                     "f2_u": c_ * x0 - s_ * y0, "f2_v": s_ * x0 + c_ * y0, "f2_r": DISC_R_M,
                     "n_selected": int(sel.sum())}
            # the zoom panel: 25 m bins in a 12 x 8 km window centred on F2
            Z, zb = (12000.0, 8000.0), 25.0
            fu, fv = cache["f2_u"], cache["f2_v"]
            zu0, zv0 = fu - Z[0] / 2, fv - Z[1] / 2
            zo = o & (np.abs(u - fu) < Z[0] / 2) & (np.abs(v - fv) < Z[1] / 2)
            zui = ((u[zo] - zu0) / zb).astype(np.int64); zvi = ((v[zo] - zv0) / zb).astype(np.int64)
            za = np.zeros((int(Z[1] / zb), int(Z[0] / zb))); zc = np.zeros_like(za); zp = np.zeros_like(za)
            np.add.at(za, (zvi, zui), np.log10(P["R"][zo].astype(np.float64)))
            np.add.at(zc, (zvi, zui), 1); np.add.at(zp, (zvi, zui), P["psr"][zo].astype(float))
            zs = sel & (np.abs(u - fu) < Z[0] / 2) & (np.abs(v - fv) < Z[1] / 2)
            cache.update({"zoom_log10_cpr": np.where(zc > 0, za / np.maximum(zc, 1), np.nan).astype(np.float32),
                          "zoom_psr_frac": np.where(zc > 0, zp / np.maximum(zc, 1), np.nan).astype(np.float32),
                          "zoom_u0": zu0, "zoom_v0": zv0, "zoom_bin_m": zb,
                          "zoom_sel_u": u[zs].astype(np.float32), "zoom_sel_v": v[zs].astype(np.float32)})
            f2_layout["n_hat"] = f2["median_over_signal"]["N_hat"]
            f2_layout["qtab"] = qtab
        passes[pid] = entry
        print(f"  {pid} F2: {json.dumps({k: f2.get(k) for k in ('cells_in_disc', 'cells_with_signal', 'fraction_in_psr', 'published_rule_selects', 'iut_selects')})}",
              flush=True)
        passes[pid]["_P"] = P
        del P
    n_f2 = passes["20200808"]["craters"]["F2"]["cells_with_signal"]
    for pid in passes:
        discs += tile_discs(passes[pid]["_P"], n_f2, DISC_R_M)
        del passes[pid]["_P"]
    summ = summarize_discs(discs)
    for cls, b in summ.items():
        if b["discs"]:
            print(f"  discs {cls:8s}: {b['discs']:>4}; rule >=1 {b['rule']['p_ge_1']:.3f} "
                  f"{b['rule']['p_ge_1_wilson95']}, >=5 {b['rule']['p_ge_5']:.3f}, mean {b['rule']['mean']:.2f}; "
                  f"IUT >=1 {b['iut']['p_ge_1']:.3f}", flush=True)

    rng = np.random.default_rng(SEED)
    sim = None
    comparison = None
    if summ["outside"]["discs"] and f2_layout is not None:
        so = summ["outside"]
        f2_layout["n_hat"] = so["median_N_hat_over_discs"]
        sim = simulate_sunlit(f2_layout, so["median_cpr_over_discs"], so["median_gamma_c_over_discs"],
                              n_f2, rng, SIM_TRIALS)
        real = so["rule"]["p_ge_1"]
        lo, hi = so["rule"]["p_ge_1_wilson95"]
        half = 0.5 * (hi - lo)
        s = sim["rule"]
        tol = 3 * s["p_ge_1_se"] + half
        differs = abs(real - s["p_ge_1"]) > tol
        comparison = {"real_sunlit_p_ge_1": real, "real_wilson95": [lo, hi],
                      "simulated_p_ge_1": s["p_ge_1"], "simulated_se": s["p_ge_1_se"],
                      "tolerance": tol, "differs": bool(differs),
                      "flag": ("THE REAL SUNLIT RATE DIFFERS FROM THE SIMULATION BY MORE THAN 3 MC SE PLUS "
                               "THE WILSON HALF-WIDTH" if differs else "within 3 MC SE plus the Wilson half-width")}
        print(f"  sunlit real >=1 {real:.3f} [{lo:.3f}, {hi:.3f}] vs simulated {s['p_ge_1']:.3f} +/- "
              f"{s['p_ge_1_se']:.3f} -> {comparison['flag']}", flush=True)

    mixture = None
    if summ["outside"]["discs"] and f2_layout is not None:
        mixture = simulate_disc_mixture(f2_layout, [d for d in discs if d["class"] == "outside"],
                                        rng, 40)
        so = summ["outside"]["rule"]
        lo, hi = so["p_ge_1_wilson95"]
        tol = 3 * mixture["predicted_p_ge_1_se"] + 0.5 * (hi - lo)
        mixture["real_p_ge_1"] = so["p_ge_1"]
        mixture["differs_beyond_3se_plus_wilson"] = bool(abs(so["p_ge_1"] - mixture["predicted_p_ge_1"]) > tol)
        print(f"  per-disc mixture: predicted >=1 {mixture['predicted_p_ge_1']:.3f} +/- "
              f"{mixture['predicted_p_ge_1_se']:.3f} against real {so['p_ge_1']:.3f}", flush=True)
    now = datetime.now(timezone.utc).isoformat()
    OUT_P2.write_text(json.dumps({
        "schema": "lunar-ice/f2-complex-product/1", "generated_utc": now,
        "generator": "backend/scripts/f2_complex_product.py", "seed": None,
        "seed_note": "P2 draws nothing; P3's simulation seed is in crater_level_real.json",
        "geolocation_found": ("yes: each bundle's geometry/*_g_sli_xx_cp_xx_d18.csv, latitude, longitude, "
                              "slant range and incidence every 32nd line and sample (isda:sli_grid_*)"),
        "geolocation_method": ("bilinear interpolation of the tie points' south-polar-stereographic x, y "
                               "(R 1737.4 km, lon0 0) at each complex-product cell (SLC line 21 i + 10, "
                               "sample j)"),
        "f2": {"lat_deg": F2["lat_deg"], "lon_deg": F2["lon_deg"], "radius_m": DISC_R_M,
               "projected_xy_m": [x0, y0], "source": "f2_footprint.json (the delivered grid's 1521-px disc)"},
        "sinha_craters": list(SINHA_CRATERS),
        "rules": {"published": "sample DOP < 0.13 AND sample CPR > 1 (physical sign)",
                  "iut": "decision_rule.py: R > F^-1_0.95(2 N_hat, 2 N_hat) AND sample DOP < q05(N_hat); "
                         "N_hat from Var(ln R), 31 x 31 matched cells"},
        "passes": passes, "run_info": {**run_info(), "wall_s": round(time.time() - t0, 1)}},
        indent=2, default=float), encoding="utf-8")
    OUT_P3.write_text(json.dumps({
        "schema": "lunar-ice/crater-level-real/1", "generated_utc": now,
        "generator": "backend/scripts/f2_complex_product.py", "seed": SEED,
        "wording": ("sunlit polar terrain is terrain where the criterion's proponents do not claim ice. It "
                    "is NOT a proven ice-free null: subsurface ice can be thermally stable outside PSRs. "
                    "These are real-data comparisons, not false-positive rates."),
        "psr_mask": "LOLA LPSR_75S_120M_201608, nearest neighbour at each cell's interpolated position",
        "discs": {"radius_m": DISC_R_M, "lattice_pitch_m": 2 * DISC_R_M,
                  "signal_cells_per_disc": n_f2, "rule": ("square lattice in polar-stereographic x, y; "
                  "each disc keeps its n_F2 signal cells nearest the centre; discs with fewer dropped"),
                  "count": len(discs), "by_pass": {p: sum(d["pass"] == p for d in discs) for p in passes}},
        "summary": summ, "simulation_sunlit": sim, "comparison": comparison,
        "simulation_per_disc_mixture": mixture,
        "per_disc": discs, "run_info": {**run_info(), "wall_s": round(time.time() - t0, 1)}},
        indent=2, default=float), encoding="utf-8")
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(CACHE, **cache)
    print(f"  wrote {OUT_P2.relative_to(BASE_DIR)}, {OUT_P3.relative_to(BASE_DIR)}, cache "
          f"{CACHE.relative_to(BASE_DIR)} ({time.time() - t0:.0f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
