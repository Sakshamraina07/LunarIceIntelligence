"""
n_sensitivity_assemble.py -- docs/n_sensitivity.json, the supplement-ready table
and the key map. (v21 work order, W1H)

    python backend/scripts/n_sensitivity_assemble.py

Reads docs/n_sensitivity_core.json (A analytic, C rule size and power, D regional
requirement and IUT onset), docs/n_sensitivity_np.json (B, the Neyman-Pearson
bound), docs/n_sensitivity_region.json (E), docs/n_sensitivity_real.json (F, G),
and the published artifacts the order says to reuse. Draws nothing. Writes
docs/n_sensitivity.json (one row per grid N, a `keys` map from every printed
number to its source), docs/n_sensitivity_table.md and docs/n_sensitivity_table.tex
(the supplement-ready table; the .tex is a snippet, not included by any manuscript
file).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.stats import f as Fd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
DOCS = BASE_DIR / "docs"
OUT = DOCS / "n_sensitivity.json"
#: the work order's grid, plus 79.6 where a threshold is stated
GRID = (5.0, 7.0, 10.0, 13.72, 14.5, 17.4, 21.0, 28.0, 34.0, 38.0, 39.4, 45.0, 55.0, 70.0, 75.9, 79.6166, 80.0,
        100.0, 150.0, 218.0)


def load(name):
    p = DOCS / name
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def g(n):
    return f"{n:g}"


def main() -> int:
    core, npb, reg, real = (load(f) for f in ("n_sensitivity_core.json", "n_sensitivity_np.json",
                                             "n_sensitivity_region.json", "n_sensitivity_real.json"))
    missing = [n for n, v in (("core", core), ("np", npb), ("region", reg), ("real", real)) if v is None]
    print("  missing inputs:", missing or "none")
    rows, keys = [], {}
    for n in GRID:
        r = {"N": n}
        c = core["rows"].get(g(n)) if core else None
        if c:
            r["crit95"] = c["analytic"]["crit95"]
            r["cpr_only_power_at_band_edge_percent"] = c["analytic"]["cpr_only_power_at_band_edge_percent"]
            r["noise_exceedance_of_1_at_true_cpr_0p7_percent"] = c["analytic"]["noise_exceedance_of_1_at_true_cpr_0p7_percent"]
            r["critical_value_below_band_edge_1p2989"] = bool(c["analytic"]["crit_below_band_edge"])
            r["rule_size_percent"] = c["rule"]["size"]["percent"]
            r["rule_size_mc_se_percent"] = c["rule"]["size"]["mc_se_percent"]
            r["rule_trials"] = c["rule"]["size"]["trials"]
            for lab in ("CPR 1.1", "CPR 1.2", "CPR 1.25"):
                pw = c["rule"]["power"].get(lab + " DOP min")
                if pw:
                    r[f"rule_power_{lab.replace('CPR ', 'cpr').replace('.', 'p')}_min_dop_percent"] = pw["percent"]
                    r[f"rule_power_{lab.replace('CPR ', 'cpr').replace('.', 'p')}_min_dop_mc_se_percent"] = pw["mc_se_percent"]
            keys[f"N={g(n)} crit95"] = f"n_sensitivity_core.json::rows.{g(n)}.analytic.crit95"
            keys[f"N={g(n)} rule size"] = f"n_sensitivity_core.json::rows.{g(n)}.rule.size.percent"
        if npb and g(n) in npb["by_N"]:
            b = npb["by_N"][g(n)]
            r["np_bound_percent"] = b["bound_percent"]
            r["np_bound_at_cpr1p1_min_dop_percent"] = b["bound_at_published_operating_point_CPR1p1_DOPmin_percent"]
            r["np_bound_mc_check"] = b["mc_check"]
            keys[f"N={g(n)} NP bound"] = f"n_sensitivity_np.json::by_N.{g(n)}.bound_percent"
        elif npb:
            r["np_bound_percent"] = None
            r["np_bound_note"] = "not in the NP grid"
        if reg:
            for sz in (260, 3647):
                key = f"N{g(n)}" if f"N{g(n)}" in reg["results"]["CPR 0.7 DOP 0.176"] else None
                if key is None and n == 79.6166:
                    key = "N80"
                if key is None:
                    continue
                e = reg["results"]["CPR 0.7 DOP 0.176"][key][f"cells{sz}"]["correlated"]
                i = reg["results"]["CPR 0.7 DOP 0.176"][key][f"cells{sz}"]["independent"]
                r[f"region_null_{sz}_cells_correlated"] = {
                    "achieved_log_ratio_N": e["achieved_log_ratio_N"], "looks_per_channel": e.get("looks_per_channel"),
                    "conditional_percent": 100 * e["conditional_p"], "containing_fraction": e["containing_fraction"],
                    "unconditional_percent": 100 * e["unconditional_p"], "unconditional_mc_se_percent": 100 * e["unconditional_se"],
                    "trials": e["trials"], "source": e.get("source"), "row_used_for_N": float(key[1:])}
                r[f"region_null_{sz}_cells_independent"] = {
                    "conditional_percent": 100 * i["conditional_p"], "containing_fraction": i["containing_fraction"],
                    "unconditional_percent": 100 * i["unconditional_p"], "unconditional_mc_se_percent": 100 * i["unconditional_se"],
                    "trials": i["trials"]}
                keys[f"N={g(n)} region null {sz} cells correlated"] = \
                    f"n_sensitivity_region.json::results.CPR 0.7 DOP 0.176.{key}.cells{sz}.correlated.unconditional_p"
        if real and g(n) in real["by_N"]:
            sc = real["by_N"][g(n)]["scopes"]
            r["f2_selected_significant_L_pass1"] = sc["L_20200808 / F2"]["significant_cpr_only"]
            r["f2_iut_selected_L_pass1"] = sc["L_20200808 / F2"]["iut_selected"]
            r["frame_selected_significant_L_pass1"] = sc["L_20200808 / whole frame"]["significant_cpr_only"]
            r["frame_selected_significant_L_pass2"] = sc["L_20200305 / whole frame"]["significant_cpr_only"]
            r["f2_selected_significant_S_pass1"] = sc["S_20200808S / F2"]["significant_cpr_only"]
            r["frame_selected_significant_S_pass1"] = sc["S_20200808S / whole frame"]["significant_cpr_only"]
            r["iut_region_exists"] = real["by_N"][g(n)]["iut_has_rejection_region"]
            r["iut_selected_frame_L_pass1"] = sc["L_20200808 / whole frame"]["iut_selected"]
            r["selected_L_pass1_frame"] = sc["L_20200808 / whole frame"]["selected"]
            r["selected_f2_L_pass1"] = sc["L_20200808 / F2"]["selected"]
            keys[f"N={g(n)} F2 significant"] = f"n_sensitivity_real.json::by_N.{g(n)}.scopes.L_20200808 / F2.significant_cpr_only"
        if real:
            for key, dim in (("f2_pooled_looks_correlation_adjusted", "pooled_looks_correlation_adjusted"),
                             ("f2_iut_power_cpr1p1_percent", "iut_power_cpr1p1_min_dop_percent")):
                p = real["f2_pooled_looks"].get("L_20200808", {}).get("by_N", {}).get(g(n))
                if p:
                    r[key] = p[dim]
        if core:
            r["K_cells_for_80pct_power"] = {lab: v["K_cells_by_N"].get(g(n)) for lab, v in core["regional_requirement"].items()
                                            if "K_cells_by_N" in v}
        rows.append(r)
    f2p = load("n_sensitivity_f2point.json")
    if f2p:
        for r in rows:
            if r["N"] == 39.4:
                r["f2_iut_power_cpr1p1_percent_high_precision"] = f2p["mean_power_percent"]
                r["f2_iut_power_cpr1p1_percent_high_precision_sd_between_seeds"] = f2p["sd_between_seeds_percent"]
                keys["N=39.4 F2 IUT power at its pooled looks"] = "n_sensitivity_f2point.json::mean_power_percent"
    doc = {"schema": "lunar-ice/n-sensitivity/1", "generated_utc": datetime.now(timezone.utc).isoformat(),
           "generator": "backend/scripts/n_sensitivity_assemble.py", "seed": None,
           "seed_note": "assembles the seeded artifacts named in `sources`; draws nothing",
           "sources": {"A_C_D": "docs/n_sensitivity_core.json (seed %s)" % (core or {}).get("seed"),
                       "B": "docs/n_sensitivity_np.json", "E": "docs/n_sensitivity_region.json (seed %s)" % (reg or {}).get("seed"),
                       "F_G": "docs/n_sensitivity_real.json (seed %s)" % (real or {}).get("seed")},
           "N_grid": list(GRID), "rows": rows, "keys": keys}
    # summaries the work order asks for by name
    if core:
        doc["analytic"] = {"N_at_which_crit95_equals_band_edge": core["N_edge_crit_equals_1p2989"],
                           "band_cpr_edges": core["band_cpr_edges"],
                           "minimum_N_with_critical_value_below_1p2989": core["N_edge_crit_equals_1p2989"],
                           "note": "the critical value falls below 1.2989 at N > 79.6166 (the printed 79.6)"}
        doc["rule_size_first_exceeds"] = core["size_first_exceeds"]
        doc["iut_onset"] = {"first_N_with_rejection_region": core["iut_onset"]["first_N_with_rejection_region"],
                            "last_N_without": core["iut_onset"]["last_N_without"], "q05_draws": core["iut_onset"]["q05_draws_fine"],
                            "iut_size_at": {k: v["size_percent"] for k, v in core["iut_size_at"].items()},
                            "iut_size_mc_se_percent": {k: v["size_mc_se_percent"] for k, v in core["iut_size_at"].items()}}
        doc["regional_requirement"] = core["regional_requirement"]
        doc["pooled_confirmation"] = core["pooled_confirmation"]
    if npb:
        doc["np_reproduction"] = {"all_agree": npb["reproduction_all_agree"], "rows": npb["reproduction"]}
    if reg:
        doc["region_null_summary"] = reg["summary"]
    if f2p:
        doc["f2_pooled_point"] = {"N_eff": f2p["N_eff"], "power_percent": f2p["mean_power_percent"], "sd_between_seeds": f2p["sd_between_seeds_percent"],
                                  "reference_region_design_curve_percent": f2p["reference_region_design_curve_percent"],
                                  "reference_n_sensitivity_real_percent": f2p["reference_n_sensitivity_real_percent"]}
    cc = load("n_sensitivity_calcheck.json")
    if cc:
        doc["region_calibration_check"] = cc["results"]
    if real:
        doc["smallest_N_any_selected_cell_significant"] = real["smallest_N_any_selected_cell_significant"]
        doc["N_free_audit"] = real["N_free_audit"]
    doc["run_info"] = run_info()
    OUT.write_text(json.dumps(doc, indent=2, default=float), encoding="utf-8")

    def f(v, d=1):
        return "—" if v is None else f"{v:.{d}f}"
    header = ["N", "crit", "NP bound %", "rule size %", "rule power 1.1 %", "region null 260 %", "region null 3647 %",
              "F2 signif.", "frame signif. (L1/L2/S)", "IUT region"]
    md = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    tex = [r"\begin{tabular}{rrrrrrrrrl}", r"\toprule",
           r"$N$ & crit. & NP bound & size & power 1.1 & region 260 & region 3647 & F2 sig. & frame sig. & IUT region\\",
           r"\midrule"]
    for r in rows:
        ra, rb = r.get("region_null_260_cells_correlated", {}), r.get("region_null_3647_cells_correlated", {})
        a = None if not ra else f"{ra['unconditional_percent']:.1f} (N {ra['achieved_log_ratio_N']:.0f})"
        b = None if not rb else f"{rb['unconditional_percent']:.1f} (N {rb['achieved_log_ratio_N']:.0f})"
        fr = "/".join(str(r.get(k, "—")) for k in ("frame_selected_significant_L_pass1", "frame_selected_significant_L_pass2",
                                                   "frame_selected_significant_S_pass1"))
        cells = [f"{r['N']:g}", f(r.get("crit95"), 3), f(r.get("np_bound_percent")), f(r.get("rule_size_percent")),
                 f(r.get("rule_power_cpr1p1_min_dop_percent")), a or "—", b or "—", str(r.get("f2_selected_significant_L_pass1", "—")), fr,
                 "yes" if r.get("iut_region_exists") else "no"]
        md.append("| " + " | ".join(cells) + " |")
        tex.append(" & ".join(cells) + r"\\")
    tex += [r"\bottomrule", r"\end{tabular}"]
    (DOCS / "n_sensitivity_table.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (DOCS / "n_sensitivity_table.tex").write_text("\n".join(tex) + "\n", encoding="utf-8")
    print(f"  wrote {OUT.name}, n_sensitivity_table.md/.tex ({len(rows)} rows, {len(keys)} keys)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
