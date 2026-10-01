"""
shadow_c2_c3_c4.py -- the V22 work order's questions C2, C3 and C4, answered from the stored
disc table and the stored specification curve. (Draws nothing.)

    python backend/scripts/shadow_c2_c3_c4.py

C2  how the coherence strata of each Mantel-Haenszel number are formed, and the same
    odds ratio under every definition in use:
      published (Table III, `A_ladder.*.mantel_haenszel_coherence_strata`): FOUR strata of fixed
        WIDTH on the disc's median coherence, cut at 0.4, 0.5 and 0.6, POOLED over passes (pass is
        not a stratifier), all discs of the set; "pass 1" is the same cuts on the pass-1 discs;
      D_overlap `coherence_deciles` (pooled) and `coherence_deciles_by_pass`: DECILES (10 strata of
        equal count, cut at the 10th ... 90th percentiles of the POOLED coherence distribution of
        the set), pooled, and crossed with pass (decile x pass strata). Only strata that hold both
        a shadowed and a sunlit disc enter the odds ratio, which leaves 4 of the 10 deciles.
    Added here: fixed-width bins x pass; deciles computed WITHIN each pass x pass.
C3  the propensity statements of the V21 report: the population of each percentage.
C4  the specifications whose block interval excludes 1 from above, per set, with their covariates,
    and whether the rule "no coherence and no LOLA local incidence" holds for every one of them.
Writes the keys `N_mh_strata_definitions`, `O_propensity_populations`, `M_spec_curve_above` into
docs/shadow_identification.json and docs/spec_curve_above.md.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shadow_identification as SI  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
SID = BASE_DIR / "docs" / "shadow_identification.json"
MD = BASE_DIR / "docs" / "spec_curve_above.md"


def mh_row(ds, label, sel=None):
    r = SI.stratified(ds, label, sel)
    informative = len(r["breslow_day_tarone"] and [1] * r["breslow_day_tarone"]["strata_used"] or [])
    mh = r["mantel_haenszel"]
    return {"mh_or": mh["or"], "ci95_rbg": mh["ci95"], "strata_with_both_classes": r["breslow_day_tarone"]["strata_used"],
            "strata_total": len(r["strata"]), "tarone_p": r["breslow_day_tarone"]["p_tarone"]}


def main() -> int:
    tab = json.loads((BASE_DIR / "docs" / "disc_table_v21.json").read_text(encoding="utf-8"))["discs"]
    doc = json.loads(SID.read_text(encoding="utf-8"))
    dss = {}
    for name, keys in SI.SETS.items():
        dss[name] = SI.DS([r for k in keys for r in tab[f"{k[0]}_{k[1]}"]], name)
    # ---------------------------------------------------------------- C2
    c2 = {"published": ("4 strata of fixed width on the disc's median coherence, cut at 0.4, 0.5, 0.6 (np.digitize(coh, [0.4, 0.5, 0.6])); "
                        "pooled over passes (pass is not a stratifier); `pass1` = the same cuts on the pass-1 discs. Code: "
                        "shadow_identification.py `DS.cbins`, `mh_coh`; crater_ladder_v20.py `coherence_strata`."),
          "D_overlap_deciles": ("10 strata of equal count: cut at the 10th ... 90th percentiles of the POOLED coherence distribution of the set "
                                "(np.digitize(coh, percentile(coh, 10..90))), pooled; `_by_pass` crosses them with pass (decile x pass). Only strata "
                                "with both a shadowed and a sunlit disc enter the odds ratio."),
          "note_on_the_supplement_wording": ("S-VII says the 0.46 uses coherence strata 'formed within each pass'. The deciles are those of the "
                                              "POOLED distribution, crossed with pass; deciles computed within each pass are the `deciles_within_pass_x_pass` row."),
          "sets": {}}
    for name in ("L_two_passes", "L_pass1", "S_pass1"):
        ds = dss[name]
        coh = ds.cov["coh"]
        edges = np.percentile(coh, np.arange(10, 100, 10))
        dec = np.digitize(coh, edges)
        fixed = ds.cbins
        rows = {"fixed_width_4_bins_pooled (published)": mh_row(ds, fixed),
                "deciles_pooled": mh_row(ds, dec)}
        sizes = {"fixed_width_bins": {int(s): {"shadowed": int(((fixed == s) & ds.inside).sum()), "sunlit": int(((fixed == s) & ds.outside).sum())} for s in np.unique(fixed)}}
        if ds.pooled:
            rows["fixed_width_4_bins_x_pass"] = mh_row(ds, fixed * 2 + ds.p2.astype(int))
            rows["deciles_pooled_x_pass (D_overlap)"] = mh_row(ds, dec * 2 + ds.p2.astype(int))
            wp = np.zeros(ds.n, int)
            for p in sorted(set(ds.ps)):
                m = ds.ps == p
                wp[m] = np.digitize(coh[m], np.percentile(coh[m], np.arange(10, 100, 10)))
            rows["deciles_within_pass_x_pass"] = mh_row(ds, wp * 2 + ds.p2.astype(int))
            p1 = ds.ps == "20200808"
            rows["fixed_width_4_bins_pass1_only (published 0.44)"] = mh_row(ds, fixed, p1)
        sizes["deciles"] = {int(s): {"shadowed": int(((dec == s) & ds.inside).sum()), "sunlit": int(((dec == s) & ds.outside).sum())} for s in np.unique(dec)}
        sizes["decile_edges_coherence"] = [float(x) for x in edges]
        c2["sets"][name] = {"mh": rows, "stratum_counts": sizes}
    doc["N_mh_strata_definitions"] = c2
    # ---------------------------------------------------------------- C3
    c3 = {"definition": ("propensity score = logistic regression of 'shadowed' on the covariates [pass (pooled set), ln N-hat, min SNR, coherence, position x, y, "
                         "slant range, incidence, LOLA local incidence, slope, slope SD, RMS height 100 and 500 m, layover fraction], fitted on the shadowed and "
                         "sunlit discs only (mixed discs excluded): D_overlap in shadow_identification.py"),
          "sets": {}}
    for name in ("L_two_passes", "L_pass1", "S_pass1"):
        ds = dss[name]
        keep = ds.inside | ds.outside
        cov = ["lnN", "snr", "coh", "sp1", "sp2", "j", "inc", "loc", "slope", "slope_sd", "r100", "r500", "layover"]
        cols = [np.ones(ds.n)] + ([ds.p2] if ds.pooled else [])
        for k in cov:
            v = ds.cov[k]
            sd = np.nanstd(v[keep])
            if sd > 0:
                cols.append((v - np.nanmean(v[keep])) / sd)
        X = np.column_stack(cols)[keep]
        z = ds.inside[keep].astype(float)
        b, cv, ll, conv = SI.CL.irls(X, z)
        ps = 1 / (1 + np.exp(-np.clip(X @ b, -30, 30)))
        pst, psc = ps[z == 1], ps[z == 0]
        out = (pst < psc.min()) | (pst > psc.max())
        p95 = np.percentile(psc, 95); p5 = np.percentile(pst, 5)
        c3["sets"][name] = {
            "shadowed_discs": int(pst.size), "sunlit_discs": int(psc.size), "converged": bool(conv),
            "sunlit_propensity_range": [float(psc.min()), float(psc.max())],
            "shadowed_outside_sunlit_range": {"n": int(out.sum()), "fraction_of_all_shadowed": float(out.mean()),
                                              "above_the_sunlit_maximum": int((pst > psc.max()).sum()), "below_the_sunlit_minimum": int((pst < psc.min()).sum())},
            "shadowed_above_sunlit_95th_percentile": {"n": int((pst > p95).sum()), "of": int(pst.size), "fraction_of_ALL_shadowed_discs": float((pst > p95).mean()),
                                                       "sunlit_95th_percentile_of_propensity": float(p95),
                                                       "of_which_outside_the_support": int(((pst > p95) & out).sum()),
                                                       "fraction_of_those_outside_support_that_are_above_p95": float(((pst > p95) & out).sum() / max(out.sum(), 1))},
            "sunlit_below_shadowed_5th_percentile": {"n": int((psc < p5).sum()), "of": int(psc.size), "fraction_of_ALL_sunlit_discs": float((psc < p5).mean()),
                                                      "shadowed_5th_percentile_of_propensity": float(p5), "variable": "the propensity score of being shadowed"}}
    doc["O_propensity_populations"] = c3
    # ---------------------------------------------------------------- C4
    c4 = {"rule_tested": "every specification whose block-bootstrap 95 % interval excludes 1 from above has neither coherence nor LOLA local incidence",
          "sets": {}}
    lines = ["# Specifications whose block-bootstrap interval excludes 1 from above",
             "",
             "Generated by `backend/scripts/shadow_c2_c3_c4.py` from `docs/shadow_identification.json::B_spec_curve`. Class and pass are in every specification;",
             "covariates: lnN = ln N-hat, snr = minimum SNR, sp = position (cx, cy), j = slant-range sample, inc = geometry-file incidence, loc = LOLA local incidence,",
             "coh = coherence, slope, rough = RMS height 100 m, psrfrac = PSR fraction. B = 500 per specification; OR = exp(PSR coefficient).", ""]
    for name, lab in (("L_two_passes", "L-band, two passes"), ("L_pass1", "L-band, pass 1"), ("S_pass1", "S-band, pass 1")):
        rows = doc["B_spec_curve"][name]["specifications"]
        up = [r for r in rows if r["or_ci95_block_bootstrap"][0] > 1.0]
        no_coh_no_loc = [r for r in rows if "coh" not in r["covariates"] and "loc" not in r["covariates"]]
        c4["sets"][name] = {
            "n_above": len(up),
            "all_lack_coherence": all("coh" not in r["covariates"] for r in up),
            "all_lack_local_incidence": all("loc" not in r["covariates"] for r in up),
            "all_lack_coherence_and_local_incidence": all(("coh" not in r["covariates"]) and ("loc" not in r["covariates"]) for r in up),
            "all_contain_geometry_file_incidence": all("inc" in r["covariates"] for r in up),
            "n_contain_geometry_file_incidence": sum("inc" in r["covariates"] for r in up),
            "all_lack_slope_roughness_psrfraction": all(not (set(r["covariates"]) & {"slope", "rough", "psrfrac"}) for r in up),
            "specifications_without_coherence_and_without_local_incidence": len(no_coh_no_loc),
            "of_those_excluding_1_from_above": len(up),
            "covariate_frequency_among_above": {k: sum(k in r["covariates"] for r in up) for k in ("lnN", "snr", "sp", "j", "inc", "loc", "coh", "slope", "rough", "psrfrac")},
            "specifications": [{"covariates": r["covariates"], "odds_ratio": r["odds_ratio"], "block_bootstrap_ci95": r["or_ci95_block_bootstrap"],
                                "cluster_robust_ci95": r["or_ci95_cluster"], "model_ci95": r["or_ci95_model"]} for r in sorted(up, key=lambda r: (len(r["covariates"]), r["odds_ratio"]))]}
        lines += [f"## {lab}: {len(up)} of 1024", "",
                  f"All lack coherence: {c4['sets'][name]['all_lack_coherence']}; all lack LOLA local incidence: {c4['sets'][name]['all_lack_local_incidence']}; "
                  f"contain geometry-file incidence: {c4['sets'][name]['n_contain_geometry_file_incidence']} of {len(up)}; "
                  f"specifications without coherence and without local incidence: {len(no_coh_no_loc)} (of which {len(up)} exclude 1 from above).", "",
                  "| # | covariates (besides class, pass) | OR | block bootstrap 95 % | cluster-robust 95 % |", "|---|---|---|---|---|"]
        for i, r in enumerate(c4["sets"][name]["specifications"], 1):
            lines.append(f"| {i} | {', '.join(r['covariates']) or '(none)'} | {r['odds_ratio']:.2f} | {r['block_bootstrap_ci95'][0]:.2f}–{r['block_bootstrap_ci95'][1]:.2f} | "
                         f"{r['cluster_robust_ci95'][0]:.2f}–{r['cluster_robust_ci95'][1]:.2f} |")
        lines.append("")
    doc["M_spec_curve_above"] = c4
    SID.write_text(json.dumps(doc, indent=2, default=float), encoding="utf-8")
    MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for n, v in c4["sets"].items():
        print(f"  C4 {n}: {v['n_above']} above; lack coh {v['all_lack_coherence']}, lack loc {v['all_lack_local_incidence']}, inc in {v['n_contain_geometry_file_incidence']}; "
              f"{v['specifications_without_coherence_and_without_local_incidence']} specs without coh and loc")
    for n, v in c2["sets"].items():
        print(f"  C2 {n}: " + "; ".join(f"{k} {x['mh_or']:.2f} ({x['ci95_rbg'][0]:.2f}-{x['ci95_rbg'][1]:.2f}; {x['strata_with_both_classes']}/{x['strata_total']} strata)" for k, x in v["mh"].items()))
    for n, v in c3["sets"].items():
        print(f"  C3 {n}: outside range {v['shadowed_outside_sunlit_range']['n']}/{v['shadowed_discs']} = {v['shadowed_outside_sunlit_range']['fraction_of_all_shadowed']:.3f}; "
              f"above sunlit p95 {v['shadowed_above_sunlit_95th_percentile']['n']}/{v['shadowed_discs']} = {v['shadowed_above_sunlit_95th_percentile']['fraction_of_ALL_shadowed_discs']:.3f} "
              f"(of the {v['shadowed_outside_sunlit_range']['n']} outside: {v['shadowed_above_sunlit_95th_percentile']['of_which_outside_the_support']} are above p95); "
              f"sunlit below shadowed p5 {v['sunlit_below_shadowed_5th_percentile']['n']}/{v['sunlit_discs']} = {v['sunlit_below_shadowed_5th_percentile']['fraction_of_ALL_sunlit_discs']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
