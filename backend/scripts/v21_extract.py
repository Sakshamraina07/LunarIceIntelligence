"""
v21_extract.py -- one pass over each pass / band that writes the disc table and
the selected-cell table the v21 analyses (W1F, W2) read. (v21 work order)

    python backend/scripts/v21_extract.py

Writes docs/disc_table_v21.json (one row per disc) and docs/selected_cells_v21.json (LOCAL ONLY: per-cell values, gitignored, not published)
(every cell the published rule selects, plus F2's signal cells), for
  L-band 2020-08-08 (pass 1), L-band 2020-03-05 (pass 2), S-band 2020-08-08.
Draws nothing. The chain is the published one (gap_v20_frame.read_pass,
evaluate2, snr_control.tile); the gates below reproduce the 1888 discs of
crater_level_real.json and the S-band ladder's 1300 discs / 96 firing.

Per disc (the 663 nearest signal cells of a 550 m disc on the 1100 m lattice):
  class (outside / inside / mixed PSR), cx, cy, psr_fraction;
  rule            cells the published rule selects (DOP-hat < 0.13 and R-hat > 1);
  n_dop, n_cpr    cells with DOP-hat < 0.13, cells with R-hat > 1 (for the outcome
                  decomposition);
  coherence, N-hat, min SNR (medians); the min SNR of the firing cells (median) and
  the fraction of the firing cells and of all cells below 6 and 3 dB (nominal
  noise floor);
  geometry: slant-range sample (the SLC column, from the geometry grid's own
  sample axis), slant range and incidence from the bundle's geometry file, LOLA
  local incidence, and LOLA slope;
  terrain (LDEM_80S_20M, 80 m slope baseline): mean slope, slope SD over the
  cells, plane-detrended RMS height in 100 m and 500 m windows (median over the
  cells), and the fraction of the disc's cells that are radar-shadowed or laid
  over by the LOCAL-SLOPE criterion (signed look-plane incidence theta_i - alpha
  above 90 deg or below 0), NOT by ray tracing.
"""
from __future__ import annotations

import gc
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.ndimage import uniform_filter

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runinfo import run_info  # noqa: E402
import f2_complex_product as FCP  # noqa: E402
import snr_control as SC  # noqa: E402
import gap_v20_frame as GF  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT_DISC = BASE_DIR / "docs" / "disc_table_v21.json"
OUT_SEL = BASE_DIR / "docs" / "selected_cells_v21.json"
DOP_T = 0.13
PASSES = (("L", "20200808"), ("L", "20200305"), ("S", "20200808S"), ("S", "20200305S"))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def plane_rms(z, w):
    """Local plane-detrended RMS height over w x w windows of the post grid (metres)."""
    mu = uniform_filter(z, w, mode="nearest")
    v = uniform_filter(z * z, w, mode="nearest") - mu ** 2
    yy, xx = np.mgrid[0:z.shape[0], 0:z.shape[1]].astype(float)
    vx = (w * w - 1) / 12.0
    cxz = uniform_filter(xx * z, w, mode="nearest") - xx * mu
    cyz = uniform_filter(yy * z, w, mode="nearest") - yy * mu
    return np.sqrt(np.maximum(v - cxz ** 2 / vx - cyz ** 2 / vx, 0.0))


def terrain(dem, xs, ys, ux, uy, inc_deg):
    """Terrain and radar-geometry statistics of one disc's cells."""
    g = dem.g
    l = np.rint(g.lpo - ys / g.scale_m - dem.base).astype(np.int64)
    s = np.rint(g.spo + xs / g.scale_m - dem.base).astype(np.int64)
    m = 16
    l0, l1, s0, s1 = l.min() - m, l.max() + m + 1, s.min() - m, s.max() + m + 1
    if l0 < 0 or s0 < 0 or l1 > g.lines or s1 > g.samples:
        return None
    patch = np.asarray(dem.mm[l0:l1, s0:s1], dtype=np.float64)
    if np.abs(patch).max() > 30000:
        return None
    z = patch * g.scaling_factor
    li, si = l - l0, s - s0
    r100, r500 = plane_rms(z, 5), plane_rms(z, 25)
    p, q = dem.pq(xs, ys)
    slope = np.rad2deg(np.arctan(np.hypot(p, q)))
    th = np.deg2rad(inc_deg)
    s_r = p * ux + q * uy                      # dz / d(toward the sensor)
    alpha = np.arctan(-s_r)                    # slope of the face towards the sensor in the look plane
    signed = np.rad2deg(th - alpha)            # signed look-plane incidence
    good = np.isfinite(slope)
    return {"slope_mean_deg": float(np.nanmean(slope)), "slope_sd_deg": float(np.nanstd(slope)),
            "rms_height_100m": float(np.median(r100[li, si])), "rms_height_500m": float(np.median(r500[li, si])),
            "fraction_shadow_local_slope": float(np.mean((signed[good] > 90.0))),
            "fraction_layover_local_slope": float(np.mean((signed[good] < 0.0))),
            "signed_incidence_median_deg": float(np.nanmedian(signed))}


def main() -> int:
    import validate_psr_vs_lola as V
    t0 = time.time()
    psr = V.load_pds("LPSR_75S_120M_201608")
    dr = json.loads((BASE_DIR / "docs" / "decision_rule.json").read_text(encoding="utf-8"))
    qtab = {int(k): v for k, v in dr["dop_quantile_table"]["q05"].items()}
    clr = json.loads((BASE_DIR / "docs" / "crater_level_real.json").read_text(encoding="utf-8"))
    n_target = clr["discs"]["signal_cells_per_disc"]
    foot = json.loads(FCP.FOOT.read_text(encoding="utf-8"))["target"]
    x0, y0 = FCP.stereo(foot["lat_deg"], foot["lon_deg"])
    dem = GF.LDEM()
    FCP.PASS_STEM["20200808S"] = "ch2_sar_ncxs_20200808t201154198"
    FCP.GEOM["20200808S"] = FCP.GEOM["20200808"]
    FCP.PASS_STEM["20200305S"] = "ch2_sar_ncxs_20200305t114902885"
    FCP.GEOM["20200305S"] = FCP.GEOM["20200305"]
    discs_out, sel_out = {}, {}
    print("=" * 78); print("v21 extraction: discs and selected cells"); print("=" * 78, flush=True)
    for band, pid in PASSES:
        R = GF.read_pass(pid)
        rows, cols = R["shape"]
        c0 = R["c0"]
        hh, vv, hv = GF.boxed(R, 5)
        E = GF.evaluate2(hh, vv, hv, None, qtab)
        G = GF.geometry_xy(R, pid, psr)
        signal = E["ok"] & (hh > c0[0]) & (vv > c0[1])
        snr = 10 * np.log10(np.maximum(np.minimum(hh / c0[0], vv / c0[1]), 1e-30))
        discs = SC.tile({"x": G["x"], "y": G["y"]}, signal, n_target, FCP.DISC_R_M)
        f2mask = signal & (np.hypot(G["x"] - x0, G["y"] - y0) <= FCP.DISC_R_M)
        spec, g = G["spec"], G["grid"]
        dxs = np.gradient(G["tx"], axis=1) / spec["interval_pix"]
        dys = np.gradient(G["ty"], axis=1) / spec["interval_pix"]
        flat = {k: E[k].ravel() for k in ("R", "dop", "coh", "gam", "nh", "rule", "ok")}
        snr_f, psr_f = snr.ravel(), G["psr"].ravel()
        xf, yf = G["x"].ravel(), G["y"].ravel()
        out = []
        for d in discs:
            c = d["cells"]
            ii, jj = np.divmod(c, cols)
            LI = R["AL"] * ii + (R["AL"] - 1) / 2.0
            SI = jj.astype(float)
            rng_c = FCP.interp(g[..., 2], LI, SI, spec)
            inc = FCP.interp(g[..., 3], LI, SI, spec)
            ux, uy = -FCP.interp(dxs, LI, SI, spec), -FCP.interp(dys, LI, SI, spec)
            nr = np.hypot(ux, uy)
            ux, uy = ux / nr, uy / nr
            xs, ys = xf[c], yf[c]
            p, q = dem.pq(xs, ys)
            th = np.deg2rad(inc)
            loc = np.rad2deg(np.arccos(np.clip((np.cos(th) - np.sin(th) * (p * ux + q * uy)) /
                                               np.sqrt(1 + p * p + q * q), -1, 1)))
            pf = float(psr_f[c].mean())
            rule = flat["rule"][c]
            dopm, cprm = flat["ok"][c] & (flat["dop"][c] < DOP_T), flat["ok"][c] & (flat["R"][c] > 1.0)
            sn = snr_f[c]
            row = {"id": len(out), "band": band, "pass": pid, "class": "outside" if pf == 0.0 else ("inside" if pf == 1.0 else "mixed"),
                   "cx": d["cx"], "cy": d["cy"], "psr_fraction": pf, "cells": int(c.size),
                   "rule": int(rule.sum()), "n_dop": int(dopm.sum()), "n_cpr": int(cprm.sum()),
                   "median_cpr": float(np.nanmedian(flat["R"][c])), "median_gamma_c": float(np.nanmedian(flat["gam"][c])),
                   "median_coherence": float(np.nanmedian(flat["coh"][c])), "median_N_hat": float(np.nanmedian(flat["nh"][c])),
                   "median_min_snr_db": float(np.median(sn)),
                   "rule_cells_median_min_snr_db": float(np.median(sn[rule])) if rule.any() else None,
                   "rule_cells_fraction_snr_lt_6dB": float(np.mean(sn[rule] < 6.0)) if rule.any() else None,
                   "rule_cells_fraction_snr_lt_3dB": float(np.mean(sn[rule] < 3.0)) if rule.any() else None,
                   "cells_fraction_snr_lt_6dB": float(np.mean(sn < 6.0)),
                   "slant_range_sample": float(np.median(jj)), "slant_range_m": float(np.median(rng_c)),
                   "incidence_geometry_deg": float(np.median(inc)), "lola_local_incidence_deg": float(np.nanmedian(loc)),
                   "lola_slope_deg": float(np.nanmedian(np.rad2deg(np.arctan(np.hypot(p, q)))))}
            t = terrain(dem, xs, ys, ux, uy, inc)
            row["terrain"] = t
            out.append(row)
        discs_out[f"{band}_{pid}"] = out
        # the selected cells and F2's signal cells
        sel = E["rule"]
        ridx = np.flatnonzero(sel.ravel())
        f2idx = np.flatnonzero(f2mask.ravel())

        def cols_of(ix):
            return {"index": ix.tolist(), "R": flat["R"][ix].tolist(), "dop": flat["dop"][ix].tolist(),
                    "N_hat_local": flat["nh"][ix].tolist(), "min_snr_db": snr_f[ix].tolist(),
                    "in_psr": psr_f[ix].tolist()}
        sel_out[f"{band}_{pid}"] = {"shape": [rows, cols], "selected": cols_of(ridx), "f2_signal_cells": cols_of(f2idx),
                                    "f2_selected": int((sel & f2mask).sum()),
                                    "matched_cells": int(E["ok"].sum()),
                                    "note": "index = row * columns + column of the 5 x 5 boxcar'd complex grid"}
        print(f"  {band} {pid}: {len(out)} discs ({sum(1 for r in out if r['rule'] >= 1)} fire); selected {ridx.size:,}; "
              f"F2 {f2idx.size} signal cells, {int((sel & f2mask).sum())} selected ({time.time() - t0:.0f} s)", flush=True)
        del R, hh, vv, hv, E, G, flat, snr, snr_f, psr_f, xf, yf
        gc.collect()
    # gates
    prev = sorted((d["pass"], d["rule"]) for d in clr["per_disc_v18"])
    now = sorted((r["pass"], r["rule"]) for k in ("L_20200808", "L_20200305") for r in discs_out[k])
    ok_l = prev == now
    s_ok = (len(discs_out["S_20200808S"]) == 1300 and sum(1 for r in discs_out["S_20200808S"] if r["rule"] >= 1) == 96)
    print(f"  L-band discs reproduce crater_level_real: {ok_l}; S-band 1300 discs / 96 fire: {s_ok}", flush=True)
    meta = {"generated_utc": datetime.now(timezone.utc).isoformat(), "generator": "backend/scripts/v21_extract.py",
            "seed": None, "seed_note": "draws nothing", "run_info": {**run_info(), "wall_s": round(time.time() - t0, 1)}}
    OUT_DISC.write_text(json.dumps({"schema": "lunar-ice/disc-table-v21/1", **meta,
                                    "gates": {"L_band_discs_reproduce_crater_level_real": bool(ok_l), "S_band_1300_96": bool(s_ok)},
                                    "discs": discs_out}, default=float), encoding="utf-8")
    OUT_SEL.write_text(json.dumps({"schema": "lunar-ice/selected-cells-v21/1", **meta, "passes": sel_out}, default=float),
                       encoding="utf-8")
    print(f"  wrote {OUT_DISC.name}, {OUT_SEL.name} ({time.time() - t0:.0f} s)")
    return 0 if (ok_l and s_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
