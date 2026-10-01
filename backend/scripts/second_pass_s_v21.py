"""
second_pass_s_v21.py -- the S-band SLI of the 2020-03-05 acquisition (ncxs_20200305t114902885),
the one compact-polarimetric product on disk that had not been run through the chain.
(v21 work order, W4.1)

    python backend/scripts/second_pass_s_v21.py

Inputs: docs/stokes_from_slc_20200305S.json (stokes_from_slc.py --product 20200305S),
docs/disc_table_v21.json::discs.S_20200305S and docs/selected_cells_v21.json::passes.S_20200305S
(v21_extract.py). Reports cells, joint-rule selections, the IUT on the selected cells (R >
crit95(N-hat) and DOP < q05(N-hat); a subset of the selections), F2's signal cells, the
disc rates by class with Wilson intervals, and the L-band ladder rungs (a), (c) and (e0)
on these discs (5 x 5 block bootstrap, B = 2000, seed 20260930; pass 2 has 10-ish shadowed
discs, so a rung may be unestimable: the counts are reported).

INDEPENDENCE: this is the S-band product of the SAME acquisition as L pass 2 (same date,
time, orbit and geometry). It is not an independent replication of anything: it shares the
scene with L pass 2 and, in geometry, nothing with pass 1. Draws nothing except the bootstrap.
Output docs/second_pass_s_v21.json.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402
import local_cells as LC  # noqa: E402
import shadow_identification as SI  # noqa: E402
import decision_rule as DR  # noqa: E402
import snr_control as SC  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "second_pass_s_v21.json"


def main() -> int:
    if not LC.ensure():
        return 2
    st = json.loads((BASE_DIR / "docs" / "stokes_from_slc_20200305S.json").read_text(encoding="utf-8"))
    tab = json.loads((BASE_DIR / "docs" / "disc_table_v21.json").read_text(encoding="utf-8"))["discs"]["S_20200305S"]
    sel = json.loads((BASE_DIR / "docs" / "selected_cells_v21.json").read_text(encoding="utf-8"))["passes"]["S_20200305S"]
    dr = json.loads((BASE_DIR / "docs" / "decision_rule.json").read_text(encoding="utf-8"))
    qtab = {int(k): v for k, v in dr["dop_quantile_table"]["q05"].items()}
    s = sel["selected"]
    nh = np.array(s["N_hat_local"]); R = np.array(s["R"]); dop = np.array(s["dop"])
    fin = np.isfinite(nh)
    iut = np.zeros(R.size, bool)
    iut[fin] = (R[fin] > DR.crit(nh[fin])) & (dop[fin] < DR.q05_at(nh[fin], qtab))
    res = st["results"]
    disc = {}
    for cls in ("outside", "inside", "mixed"):
        d = [r for r in tab if r["class"] == cls]
        k = sum(1 for r in d if r["rule"] >= 1)
        w = SC.wilson(k, len(d))
        disc[cls] = {"discs": len(d), "fire": k, "rate_percent": 100 * k / max(len(d), 1), "wilson95_percent": [100 * w[0], 100 * w[1]]}
    ds = SI.DS(tab, "S_pass2")
    lad = {}
    if ds.inside.sum() > 0 and ((ds.y == 1) & ds.inside).sum() == 0:
        lad = {"estimable": False, "reason": f"0 of {int(ds.inside.sum())} shadowed discs fire: complete separation, the PSR coefficient runs to minus infinity"}
    elif ds.inside.sum() > 0:
        for rung in ("a", "c", "e0"):
            try:
                f = SI.fit_one(ds, SI.RUNGS[rung])
            except Exception as e:  # noqa: BLE001
                f = {"error": str(e)}
            lad[rung] = f
        bt = SI.bootstrap(ds, {r: SI.RUNGS[r] for r in ("a", "c", "e0")}, 2000, 5, SI.SEED)
        for r in lad:
            if "coefficient" in lad[r]:
                lad[r]["block_bootstrap"] = {**SI.pack(bt["coef"][r]), "B": 2000, "non_converged": bt["fails"][r]}
    doc = {"schema": "lunar-ice/second-pass-s-v21/1", "generated_utc": datetime.now(timezone.utc).isoformat(),
           "generator": "backend/scripts/second_pass_s_v21.py", "seed": SI.SEED,
           "product": "ch2_sar_ncxs_20200305t114902885 (S-band SLI, read in place from data/generality/20200305/; never ingested)",
           "independent_replication": False,
           "independence_note": "same acquisition as L pass 2 (20200305t114902885); shares date, orbit and geometry with it",
           "stokes_from_slc_20200305S": {"matched_cells": st["slc"]["matched_cells"],
                                         "dop_below_0p13_fraction": res["invariant"]["dop_below_threshold"]["fraction"],
                                         "joint_cells": res["joint_measured"]["unconditional"]["n_both"],
                                         "joint_fraction": res["joint_measured"]["unconditional"]["fraction"],
                                         "coherence_median": res["invariant"]["coherence"]["median"]},
           "selected_cells": int(R.size), "selected_max_R": float(R.max()) if R.size else None, "iut_selected_among_selected": int(iut.sum()),
           "f2_signal_cells": len(sel["f2_signal_cells"]["index"]), "f2_selected": sel["f2_selected"],
           "discs": disc, "discs_total": len(tab), "discs_firing": sum(1 for r in tab if r["rule"] >= 1),
           "ladder_no_pass_term": lad,
           "note": "the ladder has no pass term (single pass); rung (c) = class + ln N-hat + min SNR + coherence; (e0) = class + geometry",
           "run_info": run_info()}
    OUT.write_text(json.dumps(doc, indent=2, default=float), encoding="utf-8")
    print(json.dumps({k: doc[k] for k in ("stokes_from_slc_20200305S", "selected_cells", "selected_max_R", "iut_selected_among_selected", "f2_signal_cells", "discs")}, indent=1, default=float))
    for r, f in lad.items():
        if not isinstance(f, dict):
            print(" ", r, f); continue
        print(" ", r, {k: f.get(k) for k in ("odds_ratio", "or_ci95_model")}, f.get("block_bootstrap", {}).get("or_ci95"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
