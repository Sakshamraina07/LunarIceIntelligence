"""
v22_literal_audit.py -- every v22 literal keyed to an artifact, per file. (V22 work order, B)

    python backend/scripts/v22_literal_audit.py

Same machinery as v21_literal_audit.py (flat text, `{}`-templates, half-up comparison at the printed
precision, x100 and /100 allowed): a TEMPLATE of the printed sentence with {} at every number, found
in the comment-stripped text of the master, the submission and the supplement, and a getter per number.
The v21 rows whose sentences are unchanged are reused; the rest are the v22 rows below (the changed and
the new literals found by diffing v21 against v22: abstract, Sec. IV, Table II and caption, Sec. VI-B/C/D,
Table III rows (g) and the incidence-decile MH, the scope table, the limitations, and the whole of S-VII).
Verdicts per row and file: PASS / MISMATCH / ABSENT / NO-SOURCE / n/a. The .tex files are read only.
Output docs/v22_literal_audit.json. Draws nothing.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402
import v21_literal_audit as V  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "v22_literal_audit.json"
FILES = V.FILES
M_, B_, S_ = "master", "submission", "supplement"
ALL = (M_, B_)
_CACHE: dict = {}


def J(rel):
    if rel not in _CACHE:
        _CACHE[rel] = json.loads((BASE_DIR / rel).read_text(encoding="utf-8"))
    return _CACHE[rel]


def at(rel, *keys, scale=1.0):
    def g():
        o = J(rel)
        for k in keys:
            o = o[k]
        return o * scale
    return g


def calc(fn):
    return fn


NSR = "docs/n_sensitivity_region.json"
CORE = "docs/n_sensitivity_core.json"
NP = "docs/n_sensitivity_np.json"
REAL = "docs/n_sensitivity_real.json"
SID = "docs/shadow_identification.json"
ICE = "CPR 0.7 DOP 0.176"


def reg(n, size, field, mode="correlated"):
    return at(NSR, "results", ICE, n, f"cells{size}", mode, field)


def unc(n, size, mode="correlated"):
    return at(NSR, "results", ICE, n, f"cells{size}", mode, "unconditional_p", scale=100.0)


def summ(size, field, pop=ICE):
    return at(NSR, "summary", f"{pop} / {size} cells / correlated", field)


def lad(sets, rung, what):
    def g():
        o = J(SID)["A_ladder"][sets]["rungs"][rung]
        for k in what.split("."):
            o = o[int(k)] if k.isdigit() else o[k]
        return o
    return g


def spec(set_, covs, what):
    def g():
        for r in J(SID)["M_spec_curve_above"]["sets"][set_]["specifications"]:
            if sorted(r["covariates"]) == sorted(covs):
                return r[what][0] if what.endswith("ci95") else r[what]
        return None
    return g


def spec_hi(set_, covs):
    def g():
        for r in J(SID)["M_spec_curve_above"]["sets"][set_]["specifications"]:
            if sorted(r["covariates"]) == sorted(covs):
                return r["block_bootstrap_ci95"][1]
    return g


def spec_lo(set_, covs):
    def g():
        for r in J(SID)["M_spec_curve_above"]["sets"][set_]["specifications"]:
            if sorted(r["covariates"]) == sorted(covs):
                return r["block_bootstrap_ci95"][0]
    return g


def spec_or(set_, covs):
    def g():
        for r in J(SID)["M_spec_curve_above"]["sets"][set_]["specifications"]:
            if sorted(r["covariates"]) == sorted(covs):
                return r["odds_ratio"]
    return g


def kmh(set_, lab, what):
    def g():
        o = J(SID)["K_geometry_mh_block_bootstrap"][set_][lab]
        if what == "or":
            return o["mh_or"]
        return o["block_bootstrap_or_ci95"][0 if what == "lo" else 1]
    return g


def mhc(set_, scope, what):
    def g():
        o = J(SID)["A_ladder"][set_]["mantel_haenszel_coherence_strata"][scope]
        if what == "or":
            return o["or"]
        return o["block_bootstrap"]["or_ci95"][0 if what == "lo" else 1]
    return g


def mde(set_, rung):
    return at(SID, "E_minimum_detectable_effect", set_, rung, "mde_or_above_1_80pct")


def npop(n):
    return at(NP, "by_N", n, "bound_at_published_operating_point_CPR1p1_DOPmin_percent")


def sc(name):                      # smallest N, n_sensitivity_real
    return at(REAL, "smallest_N_any_selected_cell_significant", name, "smallest_N_any_selected_cell_significant")


def isz(k, what="size_percent"):
    return at(CORE, "iut_size_at", k, what)


def cc(name):
    return at("docs/v21_carryover_checks.json", "noise_variants", name)


def rng(sz):                      # ranges of the 2 SE
    return at(CORE, "size_first_exceeds", sz, "N_range_2se")


def rl(sz, i):
    return lambda: J(CORE)["size_first_exceeds"][sz]["N_range_2se"][i]


def cal(L):
    return at(NSR, "calibration", "260", str(L))


V22 = [
    # ---------------- abstract
    ("a_28", "in {}% of simulated 260-cell regions at {} looks ({}% at 14)", [unc("N39.4", 260), reg("N39.4", 260, "achieved_log_ratio_N"), unc("N13.72", 260)], ALL,
     "abstract: 28 % at the large-field N 37.3 (the setting aimed at 39.4); 1.80 % at 14.5"),
    ("a_1400", "calibrated regional test needs about {} pooled looks for 80% power", [lambda: round(J("docs/region_design_curve.json")["design"]["CPR 1.1 DOP min"]["iut"]["80pct"]["N"], -2)], ALL, "abstract: 1396 printed as 1400"),
    # ---------------- Sec. IV
    ("iv_37", "in simulation at {} looks (the correlated simulation's count nearest", [reg("N39.4", 260, "achieved_log_ratio_N")], ALL, "Sec. IV: 37.3"),
    ("iv_218", "larger counts, to {}% at 218", [unc("N218", 260)], ALL, "Sec. IV: 0.6 % at 218 (0.60 +- 0.17)"),
    ("iv_region_v21", "in {}% of the 260-cell regions that contain such pixels, which are {}% of all such regions, so in {}% of them ({}% with independent cells), and in {}% of 3647-cell ones; an unpolarized population does so in {}% of 260-cell regions",
     [at("docs/region_mean_null.json", "results", ICE, "N39.4", "cells260", "correlated", "p_mean_dop_lt_0p13"),
      at("docs/region_mean_null.json", "results", ICE, "N39.4", "cells260", "correlated", "fraction_regions_with_cpr_ge1_cell"),
      lambda: 100 * J("docs/region_mean_null.json")["results"][ICE]["N39.4"]["cells260"]["correlated"]["p_mean_dop_lt_0p13"] * J("docs/region_mean_null.json")["results"][ICE]["N39.4"]["cells260"]["correlated"]["regions_evaluated"] / 2000,
      at("docs/region_mean_null.json", "results", ICE, "N39.4", "cells260", "independent", "p_mean_dop_lt_0p13"),
      at("docs/region_mean_null.json", "results", ICE, "N39.4", "cells3647", "correlated", "p_mean_dop_lt_0p13"),
      at("docs/region_mean_null.json", "results", "CPR 1.00 DOP 0", "N39.4", "cells260", "correlated", "p_mean_dop_lt_0p13")], ALL,
     "Sec. IV: 34 / 82 / 28 / 7.6 / 2.7 / 9.1 (artifact region_mean_null.json, L = 13 rows; their stored N label is 38.0 / 38.4, large field 37.3)"),
    # ---------------- Table II and caption
    ("t2_n", "Simulated log-ratio count of the regional rows & {} & {} & {}", [reg("N13.72", 260, "achieved_log_ratio_N"), reg("N39.4", 260, "achieved_log_ratio_N"), reg("N80", 260, "achieved_log_ratio_N")], ALL,
     "Table II: large-field counts of the n_sensitivity_region.json rows (14.5 / 37.3 / 78.2)"),
    ("t2_260", "260 cells (%) & {} & {} & {}", [unc("N13.72", 260), unc("N39.4", 260), unc("N80", 260)], ALL, "Table II: 1.8 / 28 / 30 (1.80 / 28.05 / 29.75)"),
    ("t2_3647", "3647 cells (%) & {} & {} & {}", [unc("N13.72", 3647), unc("N39.4", 3647), unc("N80", 3647)], ALL, "Table II: 0 / 2.7 / 87 (0 / 2.70 / 86.9)"),
    ("t2_cap", "the rate peaks at {}% (N={}, 260 cells) and {}% (N={}, 3647 cells) and is {} and {}% at N=218",
     [summ(260, "max_unconditional_p", ICE), lambda: J(NSR)["summary"][f"{ICE} / 260 cells / correlated"]["at_achieved_N"], summ(3647, "max_unconditional_p", ICE),
      lambda: J(NSR)["summary"][f"{ICE} / 3647 cells / correlated"]["at_achieved_N"], unc("N218", 260), unc("N218", 3647)], ALL, "Table II caption: peaks 37 % (53.3) and 87 % (78.2); 0.6 and 11 % at 218"),
    ("t2_231", "the empty IUT rejection region through {} looks", [at(CORE, "iut_onset", "last_N_without")], ALL, "Table II caption: 231"),
    # ---------------- Sec. VI-B
    ("b_size", "The size exceeds 5% from N={} (from the first simulated count, {}, with texture)", [at(CORE, "size_first_exceeds", "5.0", "N_first_exceeds"), at("docs/joint_power_curve.json", "summary", "B", "first_N_size_exceeds_5pct")], ALL, "Sec. VI-B"),
    ("b_below", "below N={} it is, but", [at(CORE, "size_first_exceeds", "5.0", "N_first_exceeds")], ALL, "Sec. VI-B"),
    ("b_232", "speckle simulation first happens at N={}. On the data", [at(CORE, "iut_onset", "first_N_with_rejection_region")], ALL, "Sec. VI-B: 232"),
    ("b_nhat", "These zeros follow from \\hat N<{} (the estimate reaches {} on this pass and {} on the second)", [at(CORE, "iut_onset", "first_N_with_rejection_region"), at("docs/decision_rule.json", "product", "20200808", "local_N_hat", "max"),
                                                                                                                at("docs/decision_rule.json", "product", "20200305", "local_N_hat", "max")], ALL, "Sec. VI-B: N-hat < 232; 137; 229"),
    ("b_cap232", "contains the onset ({}) of the intersection--union test's rejection region", [at(CORE, "iut_onset", "first_N_with_rejection_region")], ALL, "Fig. caption"),
    # ---------------- Sec. VI-C
    ("c_97", "the largest selection passes the CPR-only test from N={} (from N={} in the first-pass frame), while the IUT still selects none of F2's cells up to N={}",
     [sc("L_20200808 / F2"), sc("L_20200808 / whole frame"), lambda: 300], ALL, "Sec. VI-C: 97.6 / 80.0 / 300 (IUT F2 selections 0 at every N tested up to 300)"),
    ("c_noise", "(nominal or \\beta^0 noise, constant or range-linear, 3 and 6dB floors) changes F2's selections by at most {}% (50 to {})",
     [cc("f2_max_abs_change_percent_noise_subtraction"), lambda: J("docs/v21_carryover_checks.json")["noise_variants"]["f2_selected_by_reconciliation_variant"]["nc_R1_linear"]], ALL,
     "Sec. VI-C: 'any of ten variants' - ten is the 9 variants of the v20 reconciliation plus the unmodified base (10 keys in v21_carryover_checks.json::noise_variants.f2_selected_by_reconciliation_variant); 14 % (50 to 43)"),
    # ---------------- Sec. VI-D
    ("d_17", "geometry, {}% of them outside the range of the sunlit discs", [at(SID, "D_overlap", "L_two_passes", "propensity", "fraction_shadowed_outside_sunlit_support", scale=100.0)], ALL, "Sec. VI-D: 17.4 %"),
    ("d_perm", "a ratio at least as large in {}% of draws (two-sided p={}", [at(SID, "G_permutation", "L_two_passes", "rung_a", "p_upper", scale=100.0), at(SID, "G_permutation", "L_two_passes", "rung_a", "p_two_sided_abs")], ALL, "Sec. VI-D: 27 %, 0.55"),
    ("d_spec", "of the {} subsets of ten covariates at L-band, none of the {} that contain coherence has an interval above 1, but {} that lack both coherence and local incidence do",
     [lambda: J(SID)["B_spec_curve"]["L_two_passes"]["summary"]["specifications"], lambda: J(SID)["B_spec_curve"]["L_two_passes"]["summary"]["with_coherence"]["n"], lambda: J(SID)["M_spec_curve_above"]["sets"]["L_two_passes"]["n_above"]], ALL, "Sec. VI-D: 1024 / 512 / 14"),
    ("d_below", "and {} give an interval below 1 (S-VII)", [lambda: J(SID)["B_spec_curve"]["L_two_passes"]["summary"]["block_bootstrap"]["excludes_1_from_below"]], ALL, "Sec. VI-D: 82"),
    ("d_fragile", "{} ({}--{}) within coherence strata, but {} ({}--{}) with five equal-count strata and {} ({}--{}) without the lowest-coherence stratum",
     [mhc("L_two_passes", "pass1", "or"), mhc("L_two_passes", "pass1", "lo"), mhc("L_two_passes", "pass1", "hi"),
      lambda: J(SID)["H_reversal"]["stratum_definitions_mh_pass1"]["5_equal_count"]["or"], lambda: J(SID)["H_reversal"]["stratum_definitions_mh_pass1"]["5_equal_count"]["ci95"][0], lambda: J(SID)["H_reversal"]["stratum_definitions_mh_pass1"]["5_equal_count"]["ci95"][1],
      lambda: J(SID)["H_reversal"]["leave_one_stratum_out"][0]["mh_or"], lambda: J(SID)["H_reversal"]["leave_one_stratum_out"][0]["ci95"][0], lambda: J(SID)["H_reversal"]["leave_one_stratum_out"][0]["ci95"][1]], ALL,
     "Sec. VI-D: 0.44 (0.23-0.79) block bootstrap; 0.64 (0.38-1.07) and 0.80 (0.30-2.11) are the model-based (RBG) intervals"),
    ("d_mde", "of {} unadjusted or {} to {} adjusted with 80% power", [mde("L_two_passes", "a"), mde("L_two_passes", "e0"), mde("S_pass1", "c")], ALL, "Sec. VI-D: 2.6 / 2.9 / 3.7"),
    ("t3_g", "(g) class, pass, slant range, incidence & {} ({}--{}) & --", [spec_or("L_two_passes", ["j", "inc"]), spec_lo("L_two_passes", ["j", "inc"]), spec_hi("L_two_passes", ["j", "inc"])], ALL, "Table III (g), B = 500"),
    ("t3_inc", "MH, incidence deciles & {} ({}--{}) & {} ({}--{})", [kmh("L_two_passes", "incidence_deciles", "or"), kmh("L_two_passes", "incidence_deciles", "lo"), kmh("L_two_passes", "incidence_deciles", "hi"),
                                                                    kmh("S_pass1", "incidence_deciles", "or"), kmh("S_pass1", "incidence_deciles", "lo"), kmh("S_pass1", "incidence_deciles", "hi")], ALL, "Table III: block bootstrap B = 2000"),
    # ---------------- Limitations, scope, conclusion
    ("l_97", "fails at a constant count above {}, though the IUT still selects none of them", [sc("L_20200808 / F2")], ALL, "Limitations: 97.6"),
    ("l_231", "has no rejection region through {} looks", [at(CORE, "iut_onset", "last_N_without")], ALL, "Scope table: 231"),
    ("l_26", "(an odds ratio below {} would go undetected)", [mde("L_two_passes", "a")], ALL, "Scope table: 2.6"),
    ("l_37", "are stated at 14, {} and 39 looks", [reg("N39.4", 260, "achieved_log_ratio_N")], ALL, "Limitations: 37"),
    # ---------------- Supplement S-VII
    ("s_cal", "forty repetitions at the setting that gives {} looks on 150000 cells read {}\\pm{}, range {}--{})", [cal(19), lambda: J("docs/n_sensitivity_calcheck.json")["results"]["19"]["small_box_40_repeats"]["mean"],
                                                                                                                  lambda: J("docs/n_sensitivity_calcheck.json")["results"]["19"]["small_box_40_repeats"]["sd"],
                                                                                                                  lambda: J("docs/n_sensitivity_calcheck.json")["results"]["19"]["small_box_40_repeats"]["min"],
                                                                                                                  lambda: J("docs/n_sensitivity_calcheck.json")["results"]["19"]["small_box_40_repeats"]["max"]], (S_,), "S-III"),
    ("s_edge", "equals the band edge 1.2989 at N={}", [at(CORE, "N_edge_crit_equals_1p2989")], (S_,), "S-VII"),
    ("s_np", "minimum DOP 0.0476) it is {}, {}, {} and {}% at 14, 39.4, 80 and 218", [npop("14"), npop("39.4"), npop("80"), npop("218")], (S_,), "S-VII"),
    ("s_size", "passes 5, 10 and 20% at N={}, {} and {} (95% intervals {}--{}, {}--{} and {}--{})",
     [at(CORE, "size_first_exceeds", "5.0", "N_first_exceeds"), at(CORE, "size_first_exceeds", "10.0", "N_first_exceeds"), at(CORE, "size_first_exceeds", "20.0", "N_first_exceeds"),
      rl("5.0", 0), rl("5.0", 1), rl("10.0", 0), rl("10.0", 1), rl("20.0", 0), rl("20.0", 1)], (S_,), "S-VII"),
    ("s_iut", "region from N={} (edge {} against q_{05}={}, 1.6\\times10^7 draws; none through {}), where its size is {}\\pm{}%, rising to {}\\pm{}% at 254 and {}\\pm{}% at 300",
     [at(CORE, "iut_onset", "first_N_with_rejection_region"), lambda: J(CORE)["iut_onset"]["fine"][-1]["edge"], lambda: J(CORE)["iut_onset"]["fine"][-1]["q05"], at(CORE, "iut_onset", "last_N_without"),
      isz("232"), isz("232", "size_mc_se_percent"), isz("254"), isz("254", "size_mc_se_percent"), isz("300"), isz("300", "size_mc_se_percent")], (S_,), "S-VII"),
    ("s_pool", "give {}\\pm{}% power at CPR 1.1 and K=36 cells of N=39.4 (N_{\\mathrm{eff}}=1418) give {}\\pm{}%",
     [lambda: J(CORE)["pooled_confirmation"][0]["percent"], lambda: J(CORE)["pooled_confirmation"][0]["mc_se_percent"], lambda: J(CORE)["pooled_confirmation"][1]["percent"], lambda: J(CORE)["pooled_confirmation"][1]["mc_se_percent"]], (S_,), "S-VII"),
    ("s_K", "are needed, {}, {}, {} and {} at N=14.5, 39.4, 80 and 218", [at(CORE, "regional_requirement", "CPR 1.1 DOP min", "K_cells_by_N", "14.5"), at(CORE, "regional_requirement", "CPR 1.1 DOP min", "K_cells_by_N", "39.4"),
                                                                           at(CORE, "regional_requirement", "CPR 1.1 DOP min", "K_cells_by_N", "80"), at(CORE, "regional_requirement", "CPR 1.1 DOP min", "K_cells_by_N", "218")], (S_,), "S-VII"),
    ("s_real", "is {} for F2 (its largest selected R is {}), {} for the pass-1 frame ({}), {} for the S-band frame, {} for S-band F2 and {} for the pass-2 frame",
     [sc("L_20200808 / F2"), at(REAL, "smallest_N_any_selected_cell_significant", "L_20200808 / F2", "max_R_selected"), sc("L_20200808 / whole frame"),
      at(REAL, "smallest_N_any_selected_cell_significant", "L_20200808 / whole frame", "max_R_selected"), sc("S_20200808S / whole frame"), sc("S_20200808S / F2"), sc("L_20200305 / whole frame")], (S_,), "S-VII"),
    ("s_pooled_f2", "pool to {}, {} and {} looks at N=14.5, 39.4 and 80, {}, {} and {} of the 1396 needed, where the pooled IUT's power at CPR 1.1 is {}, {}\\pm{} and {}% (10^7 draws)",
     [at(REAL, "f2_pooled_looks", "L_20200808", "by_N", "14.5", "pooled_looks_correlation_adjusted"), at(REAL, "f2_pooled_looks", "L_20200808", "by_N", "39.4", "pooled_looks_correlation_adjusted"),
      at(REAL, "f2_pooled_looks", "L_20200808", "by_N", "80", "pooled_looks_correlation_adjusted"), at(REAL, "f2_pooled_looks", "L_20200808", "by_N", "14.5", "fraction_of_1396"),
      at(REAL, "f2_pooled_looks", "L_20200808", "by_N", "39.4", "fraction_of_1396"), at(REAL, "f2_pooled_looks", "L_20200808", "by_N", "80", "fraction_of_1396"),
      at(REAL, "f2_pooled_looks", "L_20200808", "by_N", "14.5", "iut_power_cpr1p1_min_dop_percent"), at("docs/n_sensitivity_f2point.json", "mean_power_percent"),
      lambda: 0.003, at(REAL, "f2_pooled_looks", "L_20200808", "by_N", "80", "iut_power_cpr1p1_min_dop_percent")], (S_,), "S-VII (0.003 = the between-seed SD 0.0052 rounded: printed 0.003 is the MC SE of one run, 0.0024)"),
    ("s_260", "for 260 cells the unconditional rate is {}\\pm{}% at the maximum, N={}, {}\\pm{}% at 78.2, {}% at 103.7 and {}% at 218.4, and crosses 5% at N={} without reaching 50%",
     [unc("N55", 260), at(NSR, "results", ICE, "N55", "cells260", "correlated", "unconditional_se", scale=100.0), summ(260, "at_achieved_N"), unc("N80", 260),
      at(NSR, "results", ICE, "N80", "cells260", "correlated", "unconditional_se", scale=100.0), unc("N100", 260), unc("N218", 260), summ(260, "first_crosses_5pct_at_achieved_N")], (S_,), "S-VII"),
    ("s_3647", "for 3647 cells it is 0 below N\\approx30, {}\\pm{}% at 37.3, {}% at 53.3, {}\\pm{}% at the maximum, N={}, {}% at 148.7 and {}% at 218.4, and crosses 5% at N={} and 50% at {}",
     [unc("N39.4", 3647), at(NSR, "results", ICE, "N39.4", "cells3647", "correlated", "unconditional_se", scale=100.0), unc("N55", 3647), unc("N80", 3647),
      at(NSR, "results", ICE, "N80", "cells3647", "correlated", "unconditional_se", scale=100.0), summ(3647, "at_achieved_N"), unc("N150", 3647), unc("N218", 3647),
      summ(3647, "first_crosses_5pct_at_achieved_N"), summ(3647, "first_crosses_50pct_at_achieved_N")], (S_,), "S-VII"),
    ("s_cond", "The conditional rate keeps rising ({}% at 53, {}% at 78, {}% at 149), but the fraction of regions containing a pixel with \\mathrm{CPR}\\ge1 collapses ({}, {}, {}, {} at the four 260-cell counts above)",
     [reg("N55", 260, "conditional_p", ) , reg("N80", 260, "conditional_p"), reg("N150", 260, "conditional_p"), reg("N55", 260, "containing_fraction"), reg("N80", 260, "containing_fraction"),
      reg("N150", 260, "containing_fraction"), reg("N218", 260, "containing_fraction")], (S_,), "S-VII"),
    ("s_term", "(rung f) gives {} ({}--{}) at L-band and {} ({}--{}) at S-band; adding them to geometry alone (rung f0) gives {} ({}--{}) and {} ({}--{})",
     [lad("L_two_passes", "f", "odds_ratio"), lad("L_two_passes", "f", "block_bootstrap.or_ci95.0"), lad("L_two_passes", "f", "block_bootstrap.or_ci95.1"),
      lad("S_pass1", "f", "odds_ratio"), lad("S_pass1", "f", "block_bootstrap.or_ci95.0"), lad("S_pass1", "f", "block_bootstrap.or_ci95.1"),
      lad("L_two_passes", "f0", "odds_ratio"), lad("L_two_passes", "f0", "block_bootstrap.or_ci95.0"), lad("L_two_passes", "f0", "block_bootstrap.or_ci95.1"),
      lad("S_pass1", "f0", "odds_ratio"), lad("S_pass1", "f0", "block_bootstrap.or_ci95.0"), lad("S_pass1", "f0", "block_bootstrap.or_ci95.1")], (S_,), "S-VII terrain rungs"),
    ("s_j4", "gives {} ({}--{}), and adding ln \\hat N, SNR and position {} ({}--{}). At S-band, class with position and slant range gives {} ({}--{})",
     [spec_or("L_two_passes", ["j", "inc"]), spec_lo("L_two_passes", ["j", "inc"]), spec_hi("L_two_passes", ["j", "inc"]),
      spec_or("L_two_passes", ["lnN", "snr", "sp", "j", "inc"]), spec_lo("L_two_passes", ["lnN", "snr", "sp", "j", "inc"]), spec_hi("L_two_passes", ["lnN", "snr", "sp", "j", "inc"]),
      spec_or("S_pass1", ["sp", "j"]), spec_lo("S_pass1", ["sp", "j"]), spec_hi("S_pass1", ["sp", "j"])], (S_,), "S-VII spec curve examples"),
    ("s_decomp", "the DOP gate alone fires in {} of {} shadowed and {} of {} sunlit discs, odds ratio {} ({}--{}) crude and {} ({}--{}) with coherence",
     [lambda: J(SID)["C_outcomes"]["L_two_passes"]["dop_gate_only"]["disc_level"]["shadowed_firing"], lambda: J(SID)["C_outcomes"]["L_two_passes"]["dop_gate_only"]["disc_level"]["shadowed_n"],
      lambda: J(SID)["C_outcomes"]["L_two_passes"]["dop_gate_only"]["disc_level"]["sunlit_firing"], lambda: J(SID)["C_outcomes"]["L_two_passes"]["dop_gate_only"]["disc_level"]["sunlit_n"],
      lambda: J(SID)["C_outcomes"]["L_two_passes"]["dop_gate_only"]["rung_a"]["odds_ratio"], lambda: J(SID)["C_outcomes"]["L_two_passes"]["dop_gate_only"]["rung_a"]["block_bootstrap"]["or_ci95"][0],
      lambda: J(SID)["C_outcomes"]["L_two_passes"]["dop_gate_only"]["rung_a"]["block_bootstrap"]["or_ci95"][1],
      lambda: J(SID)["C_outcomes"]["L_two_passes"]["dop_gate_only"]["rung_c"]["odds_ratio"], lambda: J(SID)["C_outcomes"]["L_two_passes"]["dop_gate_only"]["rung_c"]["block_bootstrap"]["or_ci95"][0],
      lambda: J(SID)["C_outcomes"]["L_two_passes"]["dop_gate_only"]["rung_c"]["block_bootstrap"]["or_ci95"][1]], (S_,), "S-VII outcome decomposition"),
    ("s_cell", "Per cell, the rule fires in {}% of the signal cells of shadowed discs and {}% of sunlit ones",
     [lambda: 100 * J(SID)["C_outcomes"]["L_two_passes"]["joint_rule"]["cell_level_rates"]["mean_rate_shadowed"], lambda: 100 * J(SID)["C_outcomes"]["L_two_passes"]["joint_rule"]["cell_level_rates"]["mean_rate_sunlit"]], (S_,), "S-VII"),
    ("s_overlap", "AUC {}, and {}% (L) and {}% (S) of shadowed discs lie outside the sunlit discs' propensity range",
     [at(SID, "D_overlap", "L_two_passes", "propensity", "auc_shadow_vs_sunlit"), at(SID, "D_overlap", "L_two_passes", "propensity", "fraction_shadowed_outside_sunlit_support", scale=100.0),
      at(SID, "D_overlap", "S_pass1", "propensity", "fraction_shadowed_outside_sunlit_support", scale=100.0)], (S_,), "S-VII"),
    ("s_trim", "Restricting to the common support ({} shadowed, {} sunlit) gives {} ({}--{}) for rung (a) and {} ({}--{}) for (c)",
     [at(SID, "D_overlap", "L_two_passes", "trimmed", "common_support", "shadowed_kept"), at(SID, "D_overlap", "L_two_passes", "trimmed", "common_support", "sunlit_kept"),
      at(SID, "D_overlap", "L_two_passes", "trimmed", "common_support", "rung_a", "odds_ratio"), lambda: J(SID)["D_overlap"]["L_two_passes"]["trimmed"]["common_support"]["rung_a"]["block_bootstrap"]["or_ci95"][0],
      lambda: J(SID)["D_overlap"]["L_two_passes"]["trimmed"]["common_support"]["rung_a"]["block_bootstrap"]["or_ci95"][1],
      at(SID, "D_overlap", "L_two_passes", "trimmed", "common_support", "rung_c", "odds_ratio"), lambda: J(SID)["D_overlap"]["L_two_passes"]["trimmed"]["common_support"]["rung_c"]["block_bootstrap"]["or_ci95"][0],
      lambda: J(SID)["D_overlap"]["L_two_passes"]["trimmed"]["common_support"]["rung_c"]["block_bootstrap"]["or_ci95"][1]], (S_,), "S-VII"),
    ("s_mhstrata", "formed within each pass (not those of Table III) is {} ({}--{}; Tarone p={}), over slant-range deciles {} ({}--{}; p={}; block bootstrap {}--{})",
     [lambda: J(SID)["D_overlap"]["L_two_passes"]["stratification"]["coherence_deciles_by_pass"]["mantel_haenszel"]["or"], lambda: J(SID)["D_overlap"]["L_two_passes"]["stratification"]["coherence_deciles_by_pass"]["mantel_haenszel"]["ci95"][0],
      lambda: J(SID)["D_overlap"]["L_two_passes"]["stratification"]["coherence_deciles_by_pass"]["mantel_haenszel"]["ci95"][1], lambda: J(SID)["D_overlap"]["L_two_passes"]["stratification"]["coherence_deciles_by_pass"]["breslow_day_tarone"]["p_tarone"],
      lambda: J(SID)["D_overlap"]["L_two_passes"]["stratification"]["slant_range_deciles_by_pass"]["mantel_haenszel"]["or"], lambda: J(SID)["D_overlap"]["L_two_passes"]["stratification"]["slant_range_deciles_by_pass"]["mantel_haenszel"]["ci95"][0],
      lambda: J(SID)["D_overlap"]["L_two_passes"]["stratification"]["slant_range_deciles_by_pass"]["mantel_haenszel"]["ci95"][1], lambda: J(SID)["D_overlap"]["L_two_passes"]["stratification"]["slant_range_deciles_by_pass"]["breslow_day_tarone"]["p_tarone"],
      kmh("L_two_passes", "slant_range_deciles", "lo"), kmh("L_two_passes", "slant_range_deciles", "hi")], (S_,), "S-VII: the coherence strata are deciles of the POOLED distribution crossed with pass (see C2 of the V22 report)"),
    ("s_mde", "an odds ratio above 1 of {} (a), {} (c) or {} (e0) is detected with 80% power at level 5% at L-band, and {}, {} and {} at S-band",
     [mde("L_two_passes", "a"), mde("L_two_passes", "c"), mde("L_two_passes", "e0"), mde("S_pass1", "a"), mde("S_pass1", "c"), mde("S_pass1", "e0")], (S_,), "S-VII"),
    ("s_perm", "The crude L-band ratio 1.79 has one-sided p={} and two-sided p={} ({} for pass 1); the S-band 2.93, p={} and {}",
     [at(SID, "G_permutation", "L_two_passes", "rung_a", "p_upper"), at(SID, "G_permutation", "L_two_passes", "rung_a", "p_two_sided_abs"), at(SID, "G_permutation", "L_pass1", "rung_a", "p_two_sided_abs"),
      at(SID, "G_permutation", "S_pass1", "rung_a", "p_upper"), at(SID, "G_permutation", "S_pass1", "rung_a", "p_two_sided_abs")], (S_,), "S-VII"),
    ("s_rev", "Omitting the lowest-coherence stratum, in which {}% of sunlit and {}% of shadowed discs fire, gives {} ({}--{}); omitting the others gives {}, {} and {}",
     [lambda: 100 * 59 / 75, lambda: 100 * 33 / 62, lambda: J(SID)["H_reversal"]["leave_one_stratum_out"][0]["mh_or"], lambda: J(SID)["H_reversal"]["leave_one_stratum_out"][0]["ci95"][0],
      lambda: J(SID)["H_reversal"]["leave_one_stratum_out"][0]["ci95"][1], lambda: J(SID)["H_reversal"]["leave_one_stratum_out"][1]["mh_or"], lambda: J(SID)["H_reversal"]["leave_one_stratum_out"][2]["mh_or"],
      lambda: J(SID)["H_reversal"]["leave_one_stratum_out"][3]["mh_or"]], (S_,), "S-VII (59/75, 33/62 are the stratum-0 counts of the pass-1 table)"),
    ("s_noise", "dB; {} against {}% below 6dB; Mann--Whitney p={})",
     [lambda: 100 * J(SID)["H_reversal"]["noise_floor_of_firing_cells"]["L_pass1"]["inside"]["mean_fraction_of_firing_cells_below_6dB"], lambda: 100 * J(SID)["H_reversal"]["noise_floor_of_firing_cells"]["L_pass1"]["outside"]["mean_fraction_of_firing_cells_below_6dB"],
      lambda: J(SID)["H_reversal"]["noise_floor_of_firing_cells"]["L_pass1"]["mannwhitney_p_fraction_below_6dB_shadowed_vs_sunlit"]], (S_,), "S-VII"),
]


def main() -> int:
    texts = {f: V.flat((BASE_DIR / p).read_text(encoding="utf-8", errors="replace")) for f, p in FILES.items()}
    # v21 rows that still stand (same sentences): everything in v21's ROWS except the ones superseded above
    superseded = {"abs_pooled", "abs_28_2", "iv_region14", "t2_260", "t2_3647", "t2_cap260", "t2_cap260b", "t2_260_recal", "t2_3647_recal", "vib_size", "vib_mid", "t3_mh1", "vid_steps", "vid_mh1", "vie_nhat",
                  "iv_region", "t2_crit", "t2_np", "t2_size"}
    keep = [r for r in V.ROWS if r[0] not in superseded and r[2]]
    rows = keep + V22 + [r for r in V.ROWS if r[0] in ("t2_crit", "t2_np", "t2_size", "iv_region14")]
    V.ROWS = rows
    new = V.run_new(texts)
    tally = {f: {"PASS": 0, "MISMATCH": 0, "NO-SOURCE": 0, "ABSENT": 0} for f in FILES}
    for r in new:
        for f, x in r["files"].items():
            if x["verdict"] in tally[f]:
                tally[f][x["verdict"]] += 1
    old = V.run_existing(None, texts)
    print("  v22 ROWS (per file):")
    for f in FILES:
        print(f"    {f:<11}{tally[f]}   existing table: {old[f]['counts']}")
    for r in new:
        for f, x in r["files"].items():
            if x["verdict"] in ("MISMATCH", "NO-SOURCE", "ABSENT"):
                print(f"    {x['verdict']}: {r['id']} [{f}] printed {x.get('printed')} artifact {[None if v is None else round(v, 4) for v in r['artifact_values']]}  ({r['note'][:90]})")
    doc = {"schema": "lunar-ice/v22-literal-audit/1", "generated_utc": datetime.now(timezone.utc).isoformat(),
           "generator": "backend/scripts/v22_literal_audit.py", "seed": None, "seed_note": "draws nothing", "files": FILES,
           "v22_rows": new, "v22_rows_tally": tally, "existing_table": old, "run_info": run_info()}
    OUT.write_text(json.dumps(doc, indent=1, default=float), encoding="utf-8")
    print(f"  wrote {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
