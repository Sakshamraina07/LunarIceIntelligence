"""
n_sensitivity_real.py -- the real-data counts with the per-cell look count
overridden by a constant N. (v21 work order, W1F, W1G)

    python backend/scripts/n_sensitivity_real.py

Reads docs/selected_cells_v21.json (LOCAL ONLY, gitignored, rebuilt on demand by local_cells.ensure(); written by v21_extract.py: every cell the
published rule selects and F2's signal cells, for L pass 1, L pass 2 and S-band)
and, for each N of the grid, reports

  * selected     cells with sample DOP < 0.13 and sample CPR > 1 (N-free: the rule
                 uses only sample quantities);
  * significant  selected cells whose R exceeds the one-sided 95 % critical value
                 of F(2N, 2N) (the CPR-only test at that N);
  * IUT          whether the intersection-union test has a rejection region at N
                 (the edge (crit - 1)/(crit + 1) below q05(N), the 5 % quantile of
                 the sample DOP at population DOP 0.13) and how many selected cells
                 it selects (R > crit and sample DOP < q05);
for F2 (its selected cells), the whole frame of each pass / band, and every scope
separately. Also the smallest N at which ANY selected cell is significant (the
N at which crit95(N) falls to the largest selected R), and F2's pooled looks: the
naive sum over its selected cells (n N) and the correlation-adjusted total
(the complex product's 6.657 independent samples x N, region_design_curve.json::
translation.crater_F2.complex_product.independent_samples) against the 1396
looks 80 % regional power at CPR 1.1 needs, with the IUT's power at CPR 1.1 (minimum
DOP) at that pooled count.

W1G -- the disc rule is N-free. The firing indicator is computed from the
boxcar'd coherency alone: v21_extract.py / gap_v20_frame.evaluate2 form
`rule = ok & (dop < 0.13) & (R > 1.0)` with `ok` the positivity mask of the
Stokes vector; N enters neither the mask, the cell set of a disc (the 663 cells
above the noise floor, snr_control.tile) nor the class. `local_n` is called in
evaluate2 only to fill `nh` for the IUT and for the ln N-hat covariate of
ladder rung (b); `rule` does not read it. The audit below records each use.
Draws: q05 and the IUT power by Bartlett sampling, seed 20261041.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.optimize import brentq
from scipy.stats import f as Fd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402
import local_cells as LC  # noqa: E402
import region_design_curve as RDC  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "n_sensitivity_real.json"
SEED = 20261041
GRID = (5.0, 7.0, 10.0, 13.72, 14.5, 17.4, 21.0, 28.0, 34.0, 38.0, 39.4, 45.0, 55.0, 70.0, 75.9, 79.6166, 80.0,
        100.0, 150.0, 218.0, 232.0, 254.0, 300.0)
REQ_1396 = 1396.0
DOP_T = 0.13


def crit(n):
    return float(Fd.ppf(0.95, 2 * n, 2 * n))


def q05(rng, n):
    _, m = RDC.stats(*RDC.bartlett(rng, float(n), 2_000_000, RDC.chol_sigma(1.0, 0.13)))
    return float(np.quantile(m, 0.05))


def n_for_crit(level):
    """N at which crit95(N) equals `level` (level > 1)."""
    return float(brentq(lambda n: crit(n) - level, 2.0, 2000.0, xtol=1e-9))


def main() -> int:
    t0 = time.time()
    if not LC.ensure():
        return 2
    sel = json.loads((BASE_DIR / "docs" / "selected_cells_v21.json").read_text(encoding="utf-8"))["passes"]
    rdc = json.loads((BASE_DIR / "docs" / "region_design_curve.json").read_text(encoding="utf-8"))
    indep = rdc["translation"]["crater_F2"]["complex_product"]["independent_samples"]
    rng = np.random.default_rng(SEED)
    qn = {n: q05(rng, n) for n in GRID}
    scopes = {}
    for key, blk in sel.items():
        s = blk["selected"]
        idx = np.array(s["index"])
        R, D = np.array(s["R"]), np.array(s["dop"])
        f2 = set(blk["f2_signal_cells"]["index"])
        is_f2 = np.array([i in f2 for i in idx])
        scopes[f"{key} / F2"] = (R[is_f2], D[is_f2])
        scopes[f"{key} / whole frame"] = (R, D)
    table = {}
    for n in GRID:
        c = crit(n)
        edge = (c - 1) / (c + 1)
        region = bool(edge < qn[n])
        row = {"N": n, "crit95": c, "iut_edge": edge, "q05": qn[n], "iut_has_rejection_region": region, "scopes": {}}
        for name, (R, D) in scopes.items():
            sig = R > c
            iut = sig & (D < qn[n])
            row["scopes"][name] = {"selected": int(R.size), "significant_cpr_only": int(sig.sum()), "iut_selected": int(iut.sum())}
        table[f"{n:g}"] = row
    first = {}
    for name, (R, D) in scopes.items():
        rmax = float(R.max()) if R.size else None
        first[name] = {"selected": int(R.size), "max_R_selected": rmax,
                       "smallest_N_any_selected_cell_significant": n_for_crit(rmax) if rmax and rmax > 1 else None,
                       "max_R_below_band_edge": bool(rmax < 1.13 / 0.87) if rmax else None}
    # F2's pooled looks
    pooled = {}
    for key in sel:
        n_sel = sel[key]["f2_selected"]
        rows = {}
        for n in GRID:
            neff = indep * n
            qn_eff = q05(rng, neff)
            r, m = RDC.stats(*RDC.bartlett(rng, float(neff), 200_000, RDC.chol_sigma(1.1, 0.1 / 2.1)))
            hit = (r > crit(neff)) & (m < qn_eff)
            p = float(hit.mean())
            rows[f"{n:g}"] = {"naive_sum_of_N_over_selected_cells": n_sel * n,
                              "independent_samples": indep, "pooled_looks_correlation_adjusted": neff,
                              "fraction_of_1396": neff / REQ_1396, "iut_power_cpr1p1_min_dop_percent": 100 * p,
                              "iut_power_mc_se_percent": 100 * float(np.sqrt(p * (1 - p) / hit.size)), "trials": int(hit.size)}
        pooled[key] = {"f2_selected": n_sel, "by_N": rows}
    doc = {
        "schema": "lunar-ice/n-sensitivity-real/1", "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/n_sensitivity_real.py", "seed": SEED,
        "source": "docs/selected_cells_v21.json (v21_extract.py)", "N_grid": list(GRID),
        "by_N": table, "smallest_N_any_selected_cell_significant": first,
        "f2_pooled_looks": pooled, "required_pooled_looks_80pct_cpr1p1": REQ_1396,
        "N_free_audit": {
            "rule": "backend/scripts/gap_v20_frame.py:222  rule = ok & (dop < DOP_T) & (R > 1.0)  (evaluate2): sample quantities only; ok is the positivity mask of the Stokes vector",
            "n_enters_at": "gap_v20_frame.py:226  nh, _ = L.local_n(lr, w_ok) (after rule is formed, line 222) and :229 iut = (R > crit(nh)) & (dop < q05_at(nh)); v21_extract.py reads rule from E['rule'] and nh only for the ln N-hat covariate (median_N_hat)",
            "where_N_enters": [
                "gap_v20_frame.evaluate2 calls enl_logratio.local_n to fill `nh`; `rule` is computed before and does not read it",
                "the IUT (R > crit(nh) and dop < q05(nh)) and the N-hat covariate of ladder rung (b) read nh",
                "the per-disc mixture simulation (crater_level_real.simulation_per_disc_mixture*) sets looks from the disc's median N-hat; it is a prediction, not the disc's firing indicator"],
            "masking_and_weighting": "signal = ok & boxcar'd power above the label floor in both channels (snr_control.tile); no N, no weighting",
            "conclusion": "disc firing rates and the odds ratios of rungs (a), (c) to (e0) are N-free; rung (b) carries ln N-hat as a covariate"},
        "run_info": {**run_info(), "wall_s": round(time.time() - t0, 1)}}
    OUT.write_text(json.dumps(doc, indent=2, default=float), encoding="utf-8")
    for name, v in first.items():
        print(f"  {name}: {v['selected']} selected, max R {v['max_R_selected']}, smallest significant N "
              f"{v['smallest_N_any_selected_cell_significant']}")
    print(f"  wrote {OUT.name} ({time.time() - t0:.0f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
