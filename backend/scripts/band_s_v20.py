"""
band_s_v20.py -- the S-band product of the 2020-08-08 acquisition through the
same chain as the L-band one. (v20 gap pass, G-H / O4)

    python backend/scripts/band_s_v20.py

The bundle holds an S-band SLI for the same acquisition
(ch2_sar_ncxs_20200808t201154198_d_sli_xx_cp_{lh,lv}_d18.tif, the same
355 768 x 759 grid, the same geometry files under the stem ncxs). This script:
  1. reruns enl_logratio.product on it (merged into docs/enl_logratio.json as
     `band_S_20200808`), after stokes_from_slc.py --product 20200808S wrote
     docs/stokes_from_slc_20200808S.json;
  2. extracts F2 on it as f2_complex_product does for L-band: the disc's cells,
     the cells with boxcar'd power above the S-band label noise floor in both
     channels, the published rule's selections, the IUT, the sample-CPR
     distribution and the local look count;
  3. counts the frame's joint-rule and IUT selections, the discs by class,
     and the cells selected in BOTH bands;
  4. scans the noise scale against the coherence bound (as gap_v20_frame.py
     does for L-band): the same test of the label's nes0 reading.
Draws nothing.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runinfo import run_info  # noqa: E402
import enl_logratio as L  # noqa: E402
import f2_complex_product as FCP  # noqa: E402
import stokes_from_slc as SFS  # noqa: E402
import snr_control as SC  # noqa: E402
import gap_v20_frame as GF  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "band_s.json"
OUT_ENL = BASE_DIR / "docs" / "enl_logratio.json"
PID = "20200808S"


def main() -> int:
    import validate_psr_vs_lola as V
    t0 = time.time()
    FCP.PASS_STEM[PID] = "ch2_sar_ncxs_20200808t201154198"
    FCP.GEOM[PID] = FCP.GEOM["20200808"]
    dr = json.loads((BASE_DIR / "docs" / "decision_rule.json").read_text(encoding="utf-8"))
    qtab = {int(k): v for k, v in dr["dop_quantile_table"]["q05"].items()}
    clr = json.loads((BASE_DIR / "docs" / "crater_level_real.json").read_text(encoding="utf-8"))
    n_target = clr["discs"]["signal_cells_per_disc"]
    foot = json.loads(FCP.FOOT.read_text(encoding="utf-8"))["target"]
    x0, y0 = FCP.stereo(foot["lat_deg"], foot["lon_deg"])
    psr = V.load_pds("LPSR_75S_120M_201608")
    print("=" * 78); print("S-band, 2020-08-08"); print("=" * 78)

    # ---- 1. enl_logratio on the S-band product
    prod = L.product(PID)
    doc = json.loads(OUT_ENL.read_text(encoding="utf-8"))
    doc["band_S_20200808"] = prod
    doc["run_info_band_S"] = run_info()
    OUT_ENL.write_text(json.dumps(doc, indent=2, default=float), encoding="utf-8")

    # ---- 2-4. frame, F2, discs, overlap with L, noise scan
    def one(pid):
        R = GF.read_pass(pid)
        hh, vv, hv = GF.boxed(R, 5)
        E = GF.evaluate2(hh, vv, hv, None, qtab)
        return R, hh, vv, hv, E

    R, hh, vv, hv, E = one(PID)
    c0, sin_l = R["c0"], R["sin_t"]
    G = GF.geometry_xy(R, PID, psr)
    signal = E["ok"] & (hh > c0[0]) & (vv > c0[1])
    f2mask = signal & (np.hypot(G["x"] - x0, G["y"] - y0) <= FCP.DISC_R_M)
    disc_all = E["ok"] & (np.hypot(G["x"] - x0, G["y"] - y0) <= FCP.DISC_R_M)
    f2 = {"cells_in_disc": int(((np.hypot(G["x"] - x0, G["y"] - y0)) <= FCP.DISC_R_M).sum()),
          "cells_matched": int(disc_all.sum()), "cells_with_signal_S_nes0": int(f2mask.sum()),
          "nes0_S": c0, "published_rule_selects": int((f2mask & E["rule"]).sum()),
          "iut_selects": int((f2mask & E["iut"]).sum()),
          "selected_with_R_gt_crit_at_N_hat": int((f2mask & E["rule"] & (E["R"] > L.crit95(
              np.where(np.isfinite(E["nh"]), E["nh"], 1.0)))).sum()),
          "median_over_signal": {"cpr": float(np.nanmedian(E["R"][f2mask])), "dop": float(np.nanmedian(E["dop"][f2mask])),
                                 "coherence": float(np.nanmedian(E["coh"][f2mask])),
                                 "N_hat": float(np.nanmedian(E["nh"][f2mask]))},
          "cpr_distribution": GF.f2_cpr_block(E, f2mask)}
    sel = f2mask & E["rule"]
    f2["selected_local_N_hat"] = {"min": float(np.nanmin(E["nh"][sel])) if sel.any() else None,
                                  "max": float(np.nanmax(E["nh"][sel])) if sel.any() else None}
    discs = SC.tile({"x": G["x"], "y": G["y"]}, signal, n_target, FCP.DISC_R_M)
    rows = []
    rl = E["rule"].ravel()
    for d in discs:
        pf = float(G["psr"].ravel()[d["cells"]].mean())
        rows.append(("outside" if pf == 0 else "inside" if pf == 1 else "mixed", int(rl[d["cells"]].sum())))
    disc_out = {}
    for cls in ("outside", "inside", "mixed"):
        a = np.array([c for k, c in rows if k == cls])
        disc_out[cls] = {"discs": int(a.size), "ge1": SC.rate_block(int((a >= 1).sum()), int(a.size)) if a.size else None}
    frame = {"cells_matched": int(E["ok"].sum()), "joint": int(E["rule"].sum()), "joint_fraction": float(E["rule"].sum() / E["ok"].sum()),
             "dop_below_0p13": int((E["ok"] & (E["dop"] < 0.13)).sum()), "iut": int(E["iut"].sum()),
             "selected_local_N": GF.selected_n(E)}
    rule_S = E["rule"].copy()
    # noise scan (the S-band label's nes0)
    base_ok = E["ok"]
    scan = []
    for a in (1.0, 0.75, 0.5, sin_l, 0.25, 0.1):
        h_, v_ = hh - a * c0[0], vv - a * c0[1]
        p_ = (h_ > 0) & (v_ > 0)
        bad = base_ok & (~p_ | (np.abs(hv) ** 2 > h_ * v_))
        scan.append({"alpha": float(a), "violating_cells": int(bad.sum()), "fraction": float(bad.sum() / base_ok.sum())})
    snr_raw = 10 * np.log10(np.maximum(np.minimum(hh / c0[0], vv / c0[1]), 1e-30))
    hi = base_ok & (snr_raw > 10)
    hc, vc = hh - c0[0], vv - c0[1]
    base_violation = float((hi & ((hc <= 0) | (vc <= 0) | (np.abs(hv) ** 2 > hc * vc))).sum() / max(hi.sum(), 1))
    noise = {"nes0_S": c0, "scan": scan, "baseline_violation_fraction_at_snr_gt_10dB_nominal": base_violation,
             "median_min_snr_db_nominal": float(np.median(snr_raw[base_ok])),
             "selected_median_min_snr_db_nominal": float(np.median(snr_raw[E["rule"]]))}
    del R, hh, vv, hv, E, G
    import gc
    gc.collect()
    # overlap with L-band
    RL, hl, vl, xl, EL = one("20200808")
    both = int((rule_S & EL["rule"]).sum())
    overlap = {"L_joint": int(EL["rule"].sum()), "S_joint": int(rule_S.sum()), "selected_in_both": both,
               "fraction_of_L_also_in_S": both / int(EL["rule"].sum()),
               "fraction_of_S_also_in_L": both / int(rule_S.sum()),
               "expected_overlap_if_independent": float(EL["rule"].sum() * rule_S.sum() / EL["ok"].sum())}
    OUT.write_text(json.dumps({
        "schema": "lunar-ice/band-s/1", "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/band_s_v20.py", "seed": None, "seed_note": "draws nothing",
        "product": "ch2_sar_ncxs_20200808t201154198 (S-band SLI, same acquisition as the L-band pass)",
        "stokes_artifact": "docs/stokes_from_slc_20200808S.json (stokes_from_slc.py --product 20200808S)",
        "enl_logratio": "docs/enl_logratio.json::band_S_20200808",
        "frame": frame, "f2": f2, "discs": {"signal_cells_per_disc": n_target, "by_class_pass_1": disc_out},
        "noise_scan": noise, "overlap_with_L_band": overlap,
        "run_info": {**run_info(), "wall_s": round(time.time() - t0, 1)}}, indent=2, default=float), encoding="utf-8")
    print(f"  S-band: joint {frame['joint']:,}, IUT {frame['iut']}; F2: {f2['cells_with_signal_S_nes0']} signal cells, "
          f"{f2['published_rule_selects']} selected, IUT {f2['iut_selects']}; in both bands {both}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
