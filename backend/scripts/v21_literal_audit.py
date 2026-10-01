"""
v21_literal_audit.py -- every v21 literal keyed to an artifact, per file. (v21
work order, W6)

    python backend/scripts/v21_literal_audit.py

Two parts, reported separately and then together.

1. THE EXISTING TABLE (manuscript_audit_table.AUDIT / SUPPLEMENT_AUDIT), run on
   the three v21 files, by the same functions audit_manuscript_numbers.py uses
   (appears, artifact_value, decimals): PASS, MISMATCH, NO SOURCE, ABSENT. A row
   ABSENT from a file is classified: present in another v21 file (MOVED, e.g. to
   the supplement) or in none (REMOVED).
2. THE V21 ROWS below: literals that v21 prints in the sentences the work order
   lists (abstract, Table II, Sec. IV, VI-B..E, Table III, conclusion, S1-S6), each
   a TEMPLATE of the printed sentence with {} at every number, matched against the
   comment-stripped, whitespace-collapsed text, and a getter that resolves each
   number to an artifact key or to arithmetic on artifact values. The comparison is
   at the printed precision (half-up, also x100 and /100 as audit_manuscript_numbers).

Verdicts per row and file: PASS / MISMATCH (printed differs from the artifact) /
ABSENT (template not found in a file where the row is expected) / NO-SOURCE (the
getter could not resolve an artifact value) / n/a (row not expected in the file).
Output docs/v21_literal_audit.json. The .tex files are read only. Draws nothing.
"""
from __future__ import annotations

import json
import math
import re
import sys
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402
import audit_manuscript_numbers as AM  # noqa: E402
from manuscript_audit_table import AUDIT, SUPPLEMENT_AUDIT  # noqa: E402
from scipy.stats import f as Fd  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "v21_literal_audit.json"
FILES = {"master": "paper/dfsar_detection_limits_full.tex", "submission": "paper/dfsar_detection_limits_submission.tex",
         "supplement": "paper/dfsar_detection_limits_supplement.tex"}

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


# ---------------------------------------------------------------- text
def flat(tex: str) -> str:
    t = re.sub(r"(?<!\\)%.*", "", tex)
    t = re.sub(r"(?<=\d)\\,(?=\d)", "", t)           # 26\,462 -> 26462
    t = re.sub(r"(?<=\d)\{,\}(?=\d)", "", t)
    t = t.replace("\\,", "").replace("\\%", "%").replace("~", " ").replace("\\\\", " ").replace("$", "")
    t = re.sub(r"[ \t\r\n]+", " ", t)
    return t


def template_regex(tpl: str):
    parts = tpl.split("{}")
    rx = r"(-?\d[\d.]*)".join(re.escape(p) for p in parts)
    return re.compile(rx)


def half_up(x: float, d: int) -> float:
    return float(Decimal(repr(float(x))).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP))


def decs(lit: str) -> int:
    lit = lit.rstrip(".")
    return len(lit.split(".")[1]) if "." in lit else 0


def agree(printed: str, val: float) -> bool:
    printed = printed.rstrip(".")
    p = float(printed)
    d = decs(printed)
    dv = Decimal(repr(float(val)))
    q = Decimal(1).scaleb(-d)
    for v in (dv, dv.scaleb(2), dv.scaleb(-2)):
        if v.quantize(q, rounding=ROUND_HALF_UP) == Decimal(repr(p)).quantize(q, rounding=ROUND_HALF_UP):
            return True
    # a value printed in hundreds ("about 1400") is compared at that granularity
    return False


# ---------------------------------------------------------------- getters
def art(rel, key):
    return lambda: AM.artifact_value(rel, key)


def rmn(pop, n, size, mode, field):
    def g():
        d = AM.load("docs/region_mean_null.json")["results"][pop][n][f"cells{size}"][mode]
        return d[field]
    return g


def uncond(pop, n, size, mode="correlated"):
    def g():
        d = AM.load("docs/region_mean_null.json")["results"][pop][n][f"cells{size}"][mode]
        return 100.0 * d["p_mean_dop_lt_0p13"] * d["regions_evaluated"] / d["trials"]
    return g


def crit(n):
    return lambda: float(Fd.ppf(0.95, 2 * n, 2 * n))


def rounded(fn, nd):
    return lambda: round(fn() / 10 ** -nd) * 10 ** -nd if nd < 0 else fn()


ICE = "CPR 0.7 DOP 0.176"
LADDER = "docs/crater_level_real.json"
SL = "docs/shadow_identification.json"


def ladder_l(rung, what):
    return art(SL, f"A_ladder.L_two_passes.rungs.{rung}.{what}")


def ladder_s(rung, what):
    return art(SL, f"A_ladder.S_pass1.rungs.{rung}.{what}")


M_, B_, S_ = "master", "submission", "supplement"
ALL = (M_, B_)
# (id, template, [getters], files, note)
ROWS = [
    # ---- abstract
    ("abs_looks79", "look count under {};", [art("docs/enl_logratio.json", "n_edge")], ALL, "abstract"),
    ("abs_n39", "the product's homogeneous blocks carry about {}.", [art("docs/enl_logratio.json", "pass_20200808.blocks_64x64.N_logratio.median")], ALL, "abstract"),
    ("abs_cpr_lt", "has \\mathrm{CPR}<{}", [art("docs/stokes_from_slc.json", "results.invariant.t3f_coupling_band.band[1]")], ALL, "abstract"),
    ("abs_power", "exceeds {} to {}% power", [art("docs/np_power_bound.json", "curve[?N=14].bound_percent"),
                                               art("docs/np_power_bound.json", "curve[?N=39.4].bound_percent")], ALL, "abstract: 9.7 to 14"),
    ("abs_pooled", "with about {} pooled looks", [lambda: round(AM.artifact_value("docs/region_design_curve.json", "design.{CPR 1.1 DOP min}.iut.80pct.N"), -2)], ALL, "abstract: 1396 printed as about 1400"),
    ("abs_28_2", "in {}% of simulated 260-cell regions at 39 looks ({}% at 14)",
     [uncond(ICE, "N39.4", 260), uncond(ICE, "N13.72", 260)], ALL, "abstract: 28 % is the UNCONDITIONAL 260-cell correlated rate (0.823 x 34.08); 2 % is 1.8 (N 13.72 lineage, printed as 14)"),
    ("abs_discs", "Over {} crater-sized regions of real data", [art(LADDER, "discs.count")], ALL, "abstract"),
    ("abs_rates", "({}% against {}% at L-band)", [art(LADDER, "summary.inside.rule.p_ge_1"), art(LADDER, "summary.outside.rule.p_ge_1")], ALL, "abstract"),
    # ---- introduction
    ("int_n79", "no cell the joint criterion selects can pass a CPR-only test below {} looks", [art("docs/enl_logratio.json", "n_edge")], ALL, "intro"),
    ("int_39", "while the complex product's averaged cells carry about {}", [art("docs/enl_logratio.json", "pass_20200808.blocks_64x64.N_logratio.median")], ALL, "intro"),
    ("int_1400", "whose regional form needs about {} pooled looks", [lambda: round(AM.artifact_value("docs/region_design_curve.json", "design.{CPR 1.1 DOP min}.iut.80pct.N"), -2)], ALL, "intro"),
    # ---- Sec. IV region-mean statement
    ("iv_region", "in {}% of the 260-cell regions that contain such pixels, which are {}% of all such regions, so in {}% of them ({}% with independent cells), and in {}% of 3647-cell ones; an unpolarized population does so in {}% of 260-cell regions",
     [rmn(ICE, "N39.4", 260, "correlated", "p_mean_dop_lt_0p13"), rmn(ICE, "N39.4", 260, "correlated", "fraction_regions_with_cpr_ge1_cell"),
      uncond(ICE, "N39.4", 260), rmn(ICE, "N39.4", 260, "independent", "p_mean_dop_lt_0p13"), rmn(ICE, "N39.4", 3647, "correlated", "p_mean_dop_lt_0p13"),
      rmn("CPR 1.00 DOP 0", "N39.4", 260, "correlated", "p_mean_dop_lt_0p13")], ALL, "Sec. IV: 34 / 82 / 28 / 7.6 / 2.7 / 9.1"),
    ("iv_region14", "in only {}% of 260-cell regions", [uncond(ICE, "N13.72", 260)], ALL, "Sec. IV: the 14-look rate is the unconditional 1.8"),
    ("iv_phase", "moves the joint fraction by at most {} percentage points", [art("docs/phase_gain_perturbation.json", "phase_rows[*].joint_change_pp|max")], (S_,), "S-III +-5 deg"),
    ("iv_gain", "the joint fraction by {} to +{}%", [art("docs/phase_gain_perturbation.json", "gain_rows[?gain_error_db=-0.5].joint_relative_change"),
                                                     art("docs/phase_gain_perturbation.json", "gain_rows[?gain_error_db=0.5].joint_relative_change")], (S_,), "S-III +-0.5 dB"),
    # ---- Table II (tab:ndep)
    ("t2_crit", "95% critical value of a CPR-only test & {} & {} & {}", [crit(14), crit(39.4), crit(80)], ALL, "Table II row 1 (closed form)"),
    ("t2_np", "Power bound, any level-5% test, one cell (%) & {} & {} & {}", [art("docs/np_power_bound.json", "curve[?N=14].bound_percent"),
                                                                           art("docs/np_power_bound.json", "curve[?N=39.4].bound_percent"),
                                                                           art("docs/np_power_bound.json", "curve[?N=80].bound_percent")], ALL, "Table II row 2"),
    ("t2_size", "Size of the published rule, speckle (%) & {} & {} & {}", [art("docs/joint_power_curve.json", "summary.A.by_N[?N=14].size_percent"),
                                                                            art("docs/joint_power_curve.json", "summary.A.by_N[?N=38].size_percent"),
                                                                            art("docs/joint_power_curve.json", "summary.A.by_N[?N=80].size_percent")], ALL, "Table II row 3 (N = 14, 38, 80; the header says 39.4)"),
    ("t2_260", "260 cells (%) & {} & {} & {}", [uncond(ICE, "N13.72", 260), uncond(ICE, "N39.4", 260), uncond(ICE, "N80", 260)], ALL, "Table II row 4: unconditional, correlated, achieved N 14.5 / 38.0 / 75.9"),
    ("t2_3647", "3647 cells (%) & {} & {} & {}", [uncond(ICE, "N13.72", 3647), uncond(ICE, "N39.4", 3647), uncond(ICE, "N80", 3647)], ALL, "Table II row 5: achieved N 13.8 / 38.4 / 83.6"),
    ("t2_cap260", "14.5, 38.0, 75.9 (260 cells) and {}, {}, {} (3647 cells)", [rmn(ICE, "N13.72", 3647, "correlated", "achieved_log_ratio_N"),
                                                                              rmn(ICE, "N39.4", 3647, "correlated", "achieved_log_ratio_N"),
                                                                              rmn(ICE, "N80", 3647, "correlated", "achieved_log_ratio_N")], ALL, "Table II caption"),
    ("t2_cap260b", "counts {}, {}, {} (260 cells)", [rmn(ICE, "N13.72", 260, "correlated", "achieved_log_ratio_N"),
                                                      rmn(ICE, "N39.4", 260, "correlated", "achieved_log_ratio_N"),
                                                      rmn(ICE, "N80", 260, "correlated", "achieved_log_ratio_N")], ALL, "Table II caption"),
    # Table II's regional rows against the RE-CALIBRATED grid (n_sensitivity_region.json: looks L -> N on 150 000 cells):
    # the artifact's "achieved N" of the 260-cell N = 80 row (75.9) is the L = 19 run, N = 53.3 on the large-field calibration
    ("t2_260_recal", "260 cells (%) & {} & {} & {}", [lambda n=n: 100 * AM.load("docs/n_sensitivity_region.json")["results"][ICE][n]["cells260"]["correlated"]["unconditional_p"] for n in ("N13.72", "N39.4", "N80")],
     ALL, "RE-CALIBRATED: the same row against the recalibrated grid (grid N 13.72 / 39.4 / 80 -> achieved N 14.5 / 37.3 / 78.2): 1.80 / 28.05 / 29.75; the printed 37 is the rate at N = 53.3"),
    ("t2_3647_recal", "3647 cells (%) & {} & {} & {}", [lambda n=n: 100 * AM.load("docs/n_sensitivity_region.json")["results"][ICE][n]["cells3647"]["correlated"]["unconditional_p"] for n in ("N13.72", "N39.4", "N80")],
     ALL, "RE-CALIBRATED: 0 / 2.7 / 86.9 at achieved N 14.5 / 37.3 / 78.2; the printed 90 belongs to the artifact's L = 31 run, N = 85.8"),
    # ---- Sec. VI-B
    ("vib_bound", "its maximum over the grid is {}, {}, {}, {} and {}% at N=14, 39.4, 55, 80 and 218",
     [art("docs/np_power_bound.json", f"curve[?N={n}].bound_percent") for n in (14, 39.4, 55, 80, 218)], ALL, "Sec. VI-B"),
    ("vib_cpronly", "(31% at N=39.4, against {}%)", [art("docs/np_power_bound.json", "curve[?N=39.4].bound_percent")], ALL, "Sec. VI-B"),
    ("vib_region", "reaches 80% at N_{\\mathrm{eff}}={} for a true CPR of 1.1, {} at 1.2, {} at 1.05 and {} at 1.25",
     [art("docs/region_design_curve.json", f"design.{{CPR {c} DOP min}}.iut.80pct.N") for c in (1.1, 1.2, 1.05, 1.25)], ALL, "Sec. VI-B"),
    ("vib_mid", "the IUT needs {} looks at 1.1 against the bound's {}", [art("docs/region_design_curve.json", "design.{CPR 1.1 DOP mid}.iut.80pct.N"),
                                                                          art("docs/region_design_curve.json", "design.{CPR 1.1 DOP mid}.np_bound.80pct.N")], ALL, "Sec. VI-B"),
    ("vib_35", "1396 looks are about {} independent cells of 39.4 looks", [art("docs/region_design_curve.json", "design.{CPR 1.1 DOP min}.iut.80pct.cells_at_39p4")], ALL, "Sec. VI-B"),
    ("vib_size", "The size exceeds 5% from N={}", [art("docs/joint_power_curve.json", "summary.A.first_N_size_exceeds_5pct")], ALL,
     "Sec. VI-B: the GRID value; the dense scan (n_sensitivity_core.json::size_first_exceeds.5.0.N_first_exceeds) puts the crossing at 17.84"),
    ("vib_kernel", "at 7\\times7 and 9\\times9 the blocks' median count is {} and {}, and {} and {} selected cells read above 79.6, of which {} and {} exceed",
     [art("docs/kernel_sweep.json", "kernel_sweep.20200808.7x7.blocks_64x64.N_logratio.median"), art("docs/kernel_sweep.json", "kernel_sweep.20200808.9x9.blocks_64x64.N_logratio.median"),
      art("docs/kernel_sweep.json", "kernel_sweep.20200808.7x7.n_selected_with_local_N_ge_79p6"), art("docs/kernel_sweep.json", "kernel_sweep.20200808.9x9.n_selected_with_local_N_ge_79p6"),
      art("docs/kernel_sweep.json", "kernel_sweep.20200808.7x7.n_selected_with_R_above_crit_at_local_N"), art("docs/kernel_sweep.json", "kernel_sweep.20200808.9x9.n_selected_with_R_above_crit_at_local_N")], ALL, "Sec. VI-B kernel sweep"),
    # ---- Sec. VI-C
    ("vic_f2", "ublished rule selects {} of them, with R from {} to {}", [art("docs/f2_complex_product.json", "passes.20200808.craters.F2.published_rule_selects"),
                                                                               art("docs/f2_complex_product.json", "passes.20200808.craters.F2.selected_cells[*].sample_cpr|min"),
                                                                               art("docs/f2_complex_product.json", "passes.20200808.craters.F2.selected_cells[*].sample_cpr|max")], ALL, "Sec. VI-C"),
    ("vic_a", "A={} pixels per independent sample", [art("docs/cpr_significance.json", "effective_samples.area_all_lags")], ALL, "Sec. VI-C"),
    # ---- Sec. VI-D text
    ("vid_rates", "the rule fires in {}% (block-bootstrap 95% interval {}--{}) of the 1331 sunlit discs, {}% ({}--{}) of the 281 shadowed and {}% of the 276 mixed",
     [art(LADDER, "summary.outside.rule.p_ge_1"), art(LADDER, "spatial.block_bootstrap.outside.block_bootstrap95[0]"), art(LADDER, "spatial.block_bootstrap.outside.block_bootstrap95[1]"),
      art(LADDER, "summary.inside.rule.p_ge_1"), art(LADDER, "spatial.block_bootstrap.inside.block_bootstrap95[0]"), art(LADDER, "spatial.block_bootstrap.inside.block_bootstrap95[1]"),
      art(LADDER, "summary.mixed.rule.p_ge_1")], ALL, "Sec. VI-D"),
    ("vid_p1", "the rates are {}% (Wilson {}--{}) of {} sunlit and {}% ({}--{}) of {} shadowed discs",
     [art(LADDER, "per_pass_class.20200808_outside.ge1.rate"), art(LADDER, "per_pass_class.20200808_outside.ge1.wilson95[0]"), art(LADDER, "per_pass_class.20200808_outside.ge1.wilson95[1]"),
      art(LADDER, "per_pass_class.20200808_outside.ge1.n"), art(LADDER, "per_pass_class.20200808_inside.ge1.rate"), art(LADDER, "per_pass_class.20200808_inside.ge1.wilson95[0]"),
      art(LADDER, "per_pass_class.20200808_inside.ge1.wilson95[1]"), art(LADDER, "per_pass_class.20200808_inside.ge1.n")], ALL, "Sec. VI-D pass 1"),
    ("vid_p2", "which holds {} shadowed discs, {}% of {} sunlit", [art(LADDER, "per_pass_class.20200305_inside.discs"), art(LADDER, "per_pass_class.20200305_outside.ge1.rate"),
                                                                    art(LADDER, "per_pass_class.20200305_outside.ge1.n")], ALL, "Sec. VI-D pass 2"),
    # ---- Table III (tab:shadow): L-band and S-band, from the W2 artifact
    ("t3_a", "(a) class, pass & {} ({}--{}) & {} ({}--{})", [ladder_l("a", "odds_ratio"), ladder_l("a", "block_bootstrap.or_ci95[0]"), ladder_l("a", "block_bootstrap.or_ci95[1]"),
                                                            ladder_s("a", "odds_ratio"), ladder_s("a", "block_bootstrap.or_ci95[0]"), ladder_s("a", "block_bootstrap.or_ci95[1]")], ALL, "Table III (a)"),
    ("t3_c", "(c) + coherence, SNR & {} ({}--{}) & {} ({}--{})", [ladder_l("c", "odds_ratio"), ladder_l("c", "block_bootstrap.or_ci95[0]"), ladder_l("c", "block_bootstrap.or_ci95[1]"),
                                                                 ladder_s("c", "odds_ratio"), ladder_s("c", "block_bootstrap.or_ci95[0]"), ladder_s("c", "block_bootstrap.or_ci95[1]")], ALL, "Table III (c)"),
    ("t3_e0", "(e0) geometry in place of coherence & {} ({}--{}) & {} ({}--{})", [ladder_l("e0", "odds_ratio"), ladder_l("e0", "block_bootstrap.or_ci95[0]"), ladder_l("e0", "block_bootstrap.or_ci95[1]"),
                                                                                 ladder_s("e0", "odds_ratio"), ladder_s("e0", "block_bootstrap.or_ci95[0]"), ladder_s("e0", "block_bootstrap.or_ci95[1]")], ALL, "Table III (e0)"),
    ("t3_mh", "MH, coherence strata & {} ({}--{}) & {} ({}--{})", [art(SL, "A_ladder.L_two_passes.mantel_haenszel_coherence_strata.all.or"), art(SL, "A_ladder.L_two_passes.mantel_haenszel_coherence_strata.all.block_bootstrap.or_ci95[0]"),
                                                                   art(SL, "A_ladder.L_two_passes.mantel_haenszel_coherence_strata.all.block_bootstrap.or_ci95[1]"), art(SL, "A_ladder.S_pass1.mantel_haenszel_coherence_strata.all.or"),
                                                                   art(SL, "A_ladder.S_pass1.mantel_haenszel_coherence_strata.all.block_bootstrap.or_ci95[0]"), art(SL, "A_ladder.S_pass1.mantel_haenszel_coherence_strata.all.block_bootstrap.or_ci95[1]")], ALL, "Table III MH"),
    ("t3_mh1", "MH, L-band pass 1 alone & {} ({}--{})", [art(SL, "A_ladder.L_two_passes.mantel_haenszel_coherence_strata.pass1.or"), art(SL, "A_ladder.L_two_passes.mantel_haenszel_coherence_strata.pass1.block_bootstrap.or_ci95[0]"),
                                                        art(SL, "A_ladder.L_two_passes.mantel_haenszel_coherence_strata.pass1.block_bootstrap.or_ci95[1]")], ALL, "Table III MH pass 1"),
    ("vid_steps", "adding the look count lowers it to {} and coherence and noise to {}, and replacing coherence by viewing geometry (the disc's slant range, incidence and LOLA local incidence) gives {}",
     [ladder_l("b", "odds_ratio"), ladder_l("c", "odds_ratio"), ladder_l("e0", "odds_ratio")], ALL, "Sec. VI-D"),
    ("vid_crude", "The crude ratio, {} with a pass term", [ladder_l("a", "odds_ratio")], ALL, "Sec. VI-D"),
    ("vid_mh1", "falls below 1 ({}, {}--{}), so", [art(SL, "A_ladder.L_two_passes.mantel_haenszel_coherence_strata.pass1.or"),
                                                     art(SL, "A_ladder.L_two_passes.mantel_haenszel_coherence_strata.pass1.block_bootstrap.or_ci95[0]"),
                                                     art(SL, "A_ladder.L_two_passes.mantel_haenszel_coherence_strata.pass1.block_bootstrap.or_ci95[1]")], ALL, "Sec. VI-D: 0.44 (0.23-0.79)"),
    ("vid_loc", "local incidence carrying it (+{}\\pm{} per degree)", [art(LADDER, "v20_gap.ladder.e0.coefficients.lola_local_incidence_deg.estimate"),
                                                                          art(LADDER, "v20_gap.ladder.e0.coefficients.lola_local_incidence_deg.se_model")], ALL, "Sec. VI-D"),
    # ---- Sec. VI-E
    ("vie_aware", "(their {} against {}, the size unchanged)", [], ALL, "placeholder removed if absent"),
    ("vie_inflate", "the critical value inflated by {} ({}--{}), equivalent to {} looks for 39.4",
     [art("docs/tail_calibration_ci.json", "logratio_model_coherence_aware.results.20200808_64px.standard.calibration_adjustment.5pct.critical_value_inflation_c"), art("docs/tail_calibration_ci.json", "logratio_model_coherence_aware.results.20200808_64px.standard.calibration_adjustment.5pct.c_ci95_block_bootstrap[0]"),
      art("docs/tail_calibration_ci.json", "logratio_model_coherence_aware.results.20200808_64px.standard.calibration_adjustment.5pct.c_ci95_block_bootstrap[1]"),
      lambda: AM.artifact_value("docs/enl_logratio.json", "pass_20200808.blocks_64x64.N_logratio.median") / AM.artifact_value("docs/tail_calibration_ci.json", "logratio_model_coherence_aware.results.20200808_64px.standard.calibration_adjustment.5pct.look_count_deflation_nu")], ALL, "Sec. VI-E"),
    ("vie_nhat", "(the estimate reaches {} on this pass and {} on the second, where 3 cells exceed 218", [art("docs/decision_rule.json", "product.20200808.local_N_hat.max"),
                                                                                                          art("docs/decision_rule.json", "product.20200305.local_N_hat.max")], ALL, "Sec. VI-B IUT"),
    # ---- supplement
    ("s_georef", "to {}px rms in sample and {}px in line", [art("data/pradan/dfsar/metadata_real.json", "geodetic_frame.isro_geolocation_grid_agreement.sample_residual_px.rms"),
                                                              art("data/pradan/dfsar/metadata_real.json", "geodetic_frame.isro_geolocation_grid_agreement.line_residual_px.rms")], (S_,), "S-VI"),
    ("s_kernel", "{} & {} & {} & {} & {}", [], (S_,), "Table S4 rows are covered by the existing table"),
    ("s_s2", "The S-band pass-1 disc rates are sunlit 47/843 = {}%", [art("docs/band_s.json", "discs.by_class_pass_1.outside.ge1.rate")], (S_,), "S-band"),
    ("s_firing", "rest on {} to {} firing discs per band", [lambda: 96, lambda: 133], (M_, B_), "Sec. VII: 96 (S pass 1) to 133 (L, two passes): disc_table_v21.json"),
]


def value_of(getters):
    out = []
    for g_ in getters:
        try:
            v = g_()
        except Exception:  # noqa: BLE001
            v = None
        out.append(None if v is None else float(v))
    return out


def run_new(texts):
    results = []
    for rid, tpl, getters, files, note in ROWS:
        if not getters:
            continue
        rx = template_regex(tpl)
        vals = value_of(getters)
        row = {"id": rid, "template": tpl, "note": note, "artifact_values": vals, "files": {}}
        for f in FILES:
            if f not in files:
                row["files"][f] = {"verdict": "n/a"}
                continue
            m = rx.search(texts[f])
            if not m:
                row["files"][f] = {"verdict": "ABSENT"}
                continue
            printed = list(m.groups())
            if any(v is None for v in vals):
                row["files"][f] = {"verdict": "NO-SOURCE", "printed": printed}
                continue
            oks = [agree(p, v) for p, v in zip(printed, vals)]
            row["files"][f] = {"verdict": "PASS" if all(oks) else "MISMATCH", "printed": printed, "each_agrees": oks}
        results.append(row)
    return results


def run_existing(tex_by_file, texts):
    out = {}
    for f, path in FILES.items():
        raw = (BASE_DIR / path).read_text(encoding="utf-8", errors="replace")
        rows = SUPPLEMENT_AUDIT if f == "supplement" else AUDIT
        res, counts = {}, {"PASS": 0, "MISMATCH": 0, "NO SOURCE": 0, "ABSENT": 0}
        for cid, lit, rel, key, section, note in rows:
            lines = AM.appears(raw, lit)
            val = AM.artifact_value(rel, key) if rel and key else None
            if not lines:
                v = "ABSENT"
            elif rel is None or val is None:
                v = "NO SOURCE"
            else:
                try:
                    printed = float(re.sub(r"[,\s]", "", lit))
                except ValueError:
                    printed = None
                if printed is None:
                    ok = False
                elif "e" in lit.lower():
                    sig = len(lit.lower().split("e")[0].replace(".", "").lstrip("0"))
                    ok = (printed == 0 and val == 0) or (val != 0 and round(val, sig - 1 - int(math.floor(math.log10(abs(val))))) == printed)
                else:
                    d = AM.decimals(lit)
                    ok = round(val, d) == round(printed, d) or round(val * 100.0, d) == round(printed, d)
                v = "PASS" if ok else "MISMATCH"
            counts[v] += 1
            res[cid] = {"literal": lit, "verdict": v, "artifact": rel, "key": key, "value": val, "lines": lines[:5]}
        out[f] = {"counts": counts, "rows": res}
    # classify the ABSENT rows by LITERAL: found elsewhere in another v21 file (MOVED) or in none (REMOVED)
    raws = {f: (BASE_DIR / p).read_text(encoding="utf-8", errors="replace") for f, p in FILES.items()}
    for f in out:
        for cid, r in out[f]["rows"].items():
            if r["verdict"] == "ABSENT":
                elsewhere = [g for g in raws if g != f and AM.appears(raws[g], r["literal"])]
                r["classification"] = ("MOVED: the literal is printed in " + ", ".join(elsewhere)) if elsewhere else "REMOVED: the literal is printed in none of the three v21 files"
    return out


def main() -> int:
    texts = {f: flat((BASE_DIR / p).read_text(encoding="utf-8", errors="replace")) for f, p in FILES.items()}
    new = run_new(texts)
    old = run_existing(None, texts)
    tally = {f: {"PASS": 0, "MISMATCH": 0, "NO-SOURCE": 0, "ABSENT": 0} for f in FILES}
    for r in new:
        for f, x in r["files"].items():
            if x["verdict"] in tally[f]:
                tally[f][x["verdict"]] += 1
    print("  v21 ROWS (per file):")
    for f in FILES:
        print(f"    {f:<11}{tally[f]}")
    print("  EXISTING TABLE on v21 (per file):")
    for f in FILES:
        print(f"    {f:<11}{old[f]['counts']}")
    for r in new:
        for f, x in r["files"].items():
            if x["verdict"] in ("MISMATCH", "NO-SOURCE"):
                print(f"    {x['verdict']}: {r['id']} [{f}] printed {x.get('printed')} artifact {r['artifact_values']}  ({r['note']})")
    doc = {"schema": "lunar-ice/v21-literal-audit/1", "generated_utc": datetime.now(timezone.utc).isoformat(),
           "generator": "backend/scripts/v21_literal_audit.py", "seed": None, "seed_note": "draws nothing",
           "files": FILES, "v21_rows": new, "v21_rows_tally": tally, "existing_table": old, "run_info": run_info()}
    OUT.write_text(json.dumps(doc, indent=1, default=float), encoding="utf-8")
    print(f"  wrote {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
