"""
audit_manuscript_numbers.py -- every load-bearing number in the manuscript,
against the artifact it claims to come from.

    python backend/scripts/audit_manuscript_numbers.py [--tex PATH]

WHY
---
`METHODS.md` has a numeric-literal coverage checker (G8). The MANUSCRIPT does
not, and that asymmetry is exactly how a stale figure survives: 4.52 and 9.95
were quoted from a nine-window run whose artifact had been overwritten by a
five-window run, and nothing compared the two.

THIS READS THE .tex READ-ONLY. It never writes to it, and it must not: the
manuscript is edited elsewhere and a second editor would fork it. The output is
a report -- `docs/manuscript_number_audit.json` -- naming, for every audited
figure, the artifact and key it resolves to and whether it agrees.

WHAT A VERDICT MEANS
  PASS       the number appears in the .tex AND matches the artifact value at
             the precision printed
  MISMATCH   it appears, and the artifact says something else. A finding.
  NO SOURCE  it appears, and no artifact on disk carries it. Also a finding --
             a number with nothing behind it is the defect, not an inconvenience
  ABSENT     the audit expected it in the .tex and did not find it. Usually
             means the manuscript rewrote a sentence; still reported, because a
             silently vanished figure is a change nobody reviewed
  DERIVED    arithmetic from other audited figures; the arithmetic is checked
             here and the inputs are audited on their own rows
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_TEX = "Claude outputs/dfsar_detection_limits_full.tex"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def load(rel: str):
    p = BASE_DIR / rel
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


_CACHE: dict = {}


def artifact_value(rel: str, path: str):
    """Resolve a dotted/indexed path inside an artifact. None if absent."""
    if rel not in _CACHE:
        _CACHE[rel] = load(rel)
    doc = _CACHE[rel]
    if doc is None:
        return None
    cur = doc
    for part in path.strip(".").split("."):
        m = re.fullmatch(r"([^\[]*)\[(\d+)\]", part)
        try:
            if m:
                if m.group(1):
                    cur = cur[m.group(1)]
                cur = cur[int(m.group(2))]
            else:
                cur = cur[part]
        except (KeyError, IndexError, TypeError):
            return None
    if isinstance(cur, bool):
        return None
    if isinstance(cur, (int, float)):
        return float(cur)
    # Labels are transcribed as strings, so "21" and "3321.641156" are values.
    # Refusing to coerce them reported real sources as NO SOURCE.
    if isinstance(cur, str):
        try:
            return float(cur.strip())
        except ValueError:
            return None
    return None


#: (id, printed value as a string, artifact, key path, section, note)
#: `artifact=None` marks a figure with no artifact expected -- a definition, a
#: count of something in the text, or a value from the cited literature. Those
#: are reported as NO SOURCE unless a note says why, because "no artifact" is
#: the finding this audit exists to surface.
AUDIT = [
    # ---- degeneracy -----------------------------------------------------
    ("ceiling", "4.261e-3", "docs/degeneracy_replication.json",
     "closed_form_ceiling", "III", "tanh^2(artanh(0.13)/2)"),
    ("x_bound", "0.2614797", None, None, "III",
     "2*artanh(0.13); closed form, checked as DERIVED below"),
    ("factor", "235", "frontend/public/analysis/sweep_grid.json",
     "crossing.factor_below_published", "III", "1.00 / measured crossing"),
    ("valid_px", "2,337,086", "docs/detection_statistics.json",
     "candidate_area.measured_pixels", "II", "valid-amplitude pixel count"),
    ("max_resid_stored", "1.241e-6", "frontend/public/analysis/faustini.json",
     "cpr_dop_identity.max_abs_residual", "III", "stored float32 field"),
    ("rms_resid", "8.025e-9", "frontend/public/analysis/faustini.json",
     "cpr_dop_identity.rms_residual", "III", "stored float32 field"),
    ("crossing", "4.2610574e-3", "frontend/public/analysis/sweep_grid.json",
     "crossing.cpr_value", "III", "max CPR where DOP < 0.13, screened field"),
    ("crossing_rel", "5.99e-6", None, None, "III",
     "relative agreement, crossing vs closed form; DERIVED"),
    # ---- Monte Carlo ----------------------------------------------------
    ("mc_trials", "120 000", None, None, "IV",
     "trials per Monte Carlo row; the count is a run parameter, not a measurement"),
    ("rho", "0.9822", None, None, "IV", "measured LH/LV coherence"),
    ("mc_N", "5", "docs/cpr_significance.json",
     "monte_carlo[0].n_looks", "IV", "look count the simulator ran at"),
    ("mc_stokes_med_03", "0.300", "docs/cpr_significance.json",
     "monte_carlo[0].stokes_cpr.median", "IV", None),
    ("mc_stokes_med_07", "0.700", "docs/cpr_significance.json",
     "monte_carlo[1].stokes_cpr.median", "IV", None),
    ("mc_stokes_med_10", "1.000", "docs/cpr_significance.json",
     "monte_carlo[2].stokes_cpr.median", "IV", None),
    ("mc_stokes_med_15", "1.500", "docs/cpr_significance.json",
     "monte_carlo[3].stokes_cpr.median", "IV", None),
    ("mc_proxy_med_07", "0.00043", "docs/cpr_significance.json",
     "monte_carlo[1].amplitude_proxy.median", "IV", None),
    ("mc_proxy_1db", "0.00331", "docs/cpr_significance.json",
     "monte_carlo[4].amplitude_proxy.median", "IV", "1 dB imbalance"),
    ("mc_proxy_3db", "0.02922", "docs/cpr_significance.json",
     "monte_carlo[5].amplitude_proxy.median", "IV", "3 dB imbalance"),
    # ---- SLC control ----------------------------------------------------
    ("bw_measured", "1071.2", "docs/slc_multilook_control.json",
     "medians.measured_bandwidth_hz", "V", "median across windows"),
    ("bw_label", "1071.336", "docs/enl_predictions.json",
     "predictions[0].declared.total_processed_azimuth_bandwidth", "V", "label"),
    ("prf", "3321.64", "docs/enl_predictions.json",
     "predictions[0].declared.pulse_repetition_frequency", "V", "label"),
    ("osamp", "3.10", "docs/slc_multilook_control.json",
     "medians.oversampling_factor", "V", None),
    ("ceiling_677", "6.77", "docs/enl_predictions.json",
     "predictions[0].predicted_ceiling", "V", "21 / 3.1005"),
    ("looks21", "21", "docs/enl_predictions.json",
     "predictions[0].declared.azimuth_looks", "V", "label field"),
    ("sl_median", "1.04", "docs/slc_multilook_control.json",
     "medians.enl_single_look", "V", None),
    ("sl_min", "0.93", "docs/slc_multilook_control.json",
     "min.enl_single_look", "V", "range endpoint"),
    ("sl_max", "1.12", "docs/slc_multilook_control.json",
     "max.enl_single_look", "V", None),
    ("spatial", "4.52", "docs/slc_multilook_control.json",
     "medians.enl_spatial_21", "V", None),
    ("subband", "9.95", "docs/slc_multilook_control.json",
     "medians.enl_subband_21", "V", None),
    ("ceiling_128", "12.8", "docs/slc_multilook_control.json",
     "medians.enl_subband_unequal_power_ceiling", "V", None),
    # ---- measured ENL ---------------------------------------------------
    ("enl_lh", "5.83", "docs/enl.json", "boxcar_gain.LH.enl_raw", "V", None),
    ("enl_lv", "5.14", "docs/enl.json", "boxcar_gain.LV.enl_raw", "V", None),
    # ---- correlation ----------------------------------------------------
    ("lag_az", "0.838", "docs/enl.json",
     "lag_correlation.LH.azimuth_lines[0]", "V", None),
    ("lag_rg", "0.576", "docs/enl.json",
     "lag_correlation.LH.range_samples[0]", "V", None),
    ("gain_lh", "2.35", "docs/enl.json", "boxcar_gain.LH.gain", "V", None),
    ("gain_lv", "3.84", "docs/enl.json", "boxcar_gain.LV.gain", "V", None),
    ("enl5_lh", "13.72", "docs/detection_statistics.json",
     "effective_looks.screened_field.lh", "V", None),
    ("enl5_lv", "19.77", "docs/detection_statistics.json",
     "effective_looks.screened_field.lv", "V", None),
    # ---- detection statistics -------------------------------------------
    ("bias1079", "1.079", None, None, "VI", "N/(N-1) at N = 13.72; DERIVED"),
    ("floor1895", "1.895", "docs/detection_statistics.json",
     "per_pixel_significance.floor_at_low_N", "VI", None),
    ("fp1779", "17.79", None, None, "VI", "upper bound at true CPR 0.7"),
    ("floor38", "1.44", None, None, "VI",
     "sqrt((2N-1)/(N-2)) at N=38, the ratio of relSD(R) to 1/sqrt(N); DERIVED"),
    ("floor6", "1.66", None, None, "VI",
     "sqrt((2N-1)/(N-2)) at N=6; DERIVED"),
    # ---- the null --------------------------------------------------------
    ("null_area", "0.0000", "docs/detection_statistics.json",
     "candidate_area.area_km2", "VIII", None),
    ("wilson_lo", "0.0000", "docs/detection_statistics.json",
     "candidate_area.ci_km2[0]", "VIII", None),
    ("wilson_hi", "0.147", "docs/detection_statistics.json",
     "candidate_area.ci_km2[1]", "VIII", "effective-sample interval (Section 1)"),
    ("n_eff", "38,050", "docs/detection_statistics.json",
     "candidate_area.n_effective", "VIII", "round(2337086 / 61.4207)"),
    ("corr_area", "61.42", "docs/cpr_significance.json",
     "effective_samples.area_all_lags", "VIII", None),
    # ---- external check (Putrevu) ------------------------------------------
    ("putrevu_inc", "27.62", "docs/cpr_dispersion.json",
     "external_check.led_with_triple.incidence_deg", "VII", None),
    ("putrevu_grs", "20.707", "docs/cpr_dispersion.json",
     "external_check.led_with_triple.ground_range_spacing_m", "VII", None),
    ("putrevu_N", "54.88", "docs/cpr_dispersion.json",
     "external_check.led_with_triple.N", "VII", None),
    ("putrevu_floor", "0.1936", "docs/cpr_dispersion.json",
     "external_check.led_with_triple.independent_floor", "VII", None),
    ("putrevu_rho", "0.307", "docs/cpr_dispersion.json",
     "external_check.led_with_triple.rho_I_min", "VII", None),
    ("obs_duration", "107.106", "docs/data_provenance.json",
     "observation_duration_s", "II", None),
    # ---- published moments, the gamma_2 column and the medians ------------
    ("g2_hermite", "6.12", "docs/published_moments.json", "craters[0].excess_kurtosis", "VII", None),
    ("g2_rozh", "7.66", "docs/published_moments.json", "craters[1].excess_kurtosis", "VII", None),
    ("g2_main", "7.06", "docs/published_moments.json", "craters[2].excess_kurtosis", "VII", None),
    ("g2_schom", "6.51", "docs/published_moments.json", "craters[3].excess_kurtosis", "VII", None),
    ("g2_card", "7.19", "docs/published_moments.json", "craters[4].excess_kurtosis", "VII", None),
    ("g2_byrg", "7.33", "docs/published_moments.json", "craters[5].excess_kurtosis", "VII", None),
    ("g2_doll", "7.00", "docs/published_moments.json", "craters[6].excess_kurtosis", "VII", None),
    ("g2_stev", "7.95", "docs/published_moments.json", "craters[7].excess_kurtosis", "VII", None),
    ("pm_med_sigma", "8.75", "docs/published_moments.json", "median_N_from_dispersion", "VII", None),
    ("pm_med_skew", "9.08", "docs/published_moments.json", "median_N_from_skewness", "VII", None),
    ("pm_med_kurt", "9.17", "docs/published_moments.json", "median_N_from_kurtosis", "VII", None),
    # ---- literature counts. Small integers are found anywhere in the text, so
    # these rows check the artifact holds the count, not that the sentence does.
    ("lit_unique", "34", "docs/literature_search.json", "counts.unique", "VII",
     "presence check only; 34 is not a discriminating literal"),
    ("lit_relevant", "25", "docs/literature_search.json", "counts.relevant", "VII",
     "presence check only"),
    ("lit_excluded", "9", "docs/literature_search.json", "counts.excluded", "VII",
     "presence check only"),
    ("lit_fulltext", "12", "docs/literature_search.json", "counts.full_text", "VII",
     "presence check only; P8 re-screen obtained two more, see docs/literature_screen.json"),
    # ---- sensitivity artifacts (Section 5) ----------------------------------
    ("slepian_pr", "7.34", "docs/slepian_ceiling.json", "participation_ratio_rectangular", "V", None),
    ("slepian_hamm", "4.07", "docs/slepian_ceiling.json", "enl_hamming_054", "V", None),
    ("pb_16", "6.61", "docs/patch_bias.json", "correlated.16.mode", "V", None),
    ("pb_32", "6.01", "docs/patch_bias.json", "correlated.32.mode", "V", None),
    ("stat_lo", "3.3", "docs/stationarity.json", "enl_min", "V", None),
    ("stat_hi", "8.0", "docs/stationarity.json", "enl_max", "V", None),
    ("cr_0", "17.6", "docs/correlated_ratio.json", "rows[0].fp_percent", "VII", None),
    ("cr_05", "14.1", "docs/correlated_ratio.json", "rows[1].fp_percent", "VII", None),
    ("cr_08", "6.3", "docs/correlated_ratio.json", "rows[2].fp_percent", "VII", None),
    ("cr_09", "1.9", "docs/correlated_ratio.json", "rows[3].fp_percent", "VII", None),
    ("joint_18", "1.8", "docs/joint_criterion.json", "headline.joint_fp_percent", "VII", None),
    ("boot_lh_lo", "4.03", "docs/bootstrap_enl.json", "LH.enl_raw_ci_block[0]", "V", None),
    ("boot_lh_hi", "6.19", "docs/bootstrap_enl.json", "LH.enl_raw_ci_block[1]", "V", None),
    ("boot_lv_lo", "4.38", "docs/bootstrap_enl.json", "LV.enl_raw_ci_block[0]", "V", None),
    ("boot_lv_hi", "7.29", "docs/bootstrap_enl.json", "LV.enl_raw_ci_block[1]", "V", None),
    ("boot_lh5_lo", "10.7", "docs/bootstrap_enl.json", "LH.enl_box_ci_block[0]", "V", None),
    ("boot_lh5_hi", "22.5", "docs/bootstrap_enl.json", "LH.enl_box_ci_block[1]", "V", None),
    ("boot_lv5_lo", "12.1", "docs/bootstrap_enl.json", "LV.enl_box_ci_block[0]", "V", None),
    ("boot_lv5_hi", "24.8", "docs/bootstrap_enl.json", "LV.enl_box_ci_block[1]", "V", None),
    # ---- peer-review block P1-P7: numbers the paper will place ------------
    ("p1_coherence", "0.658", "docs/stokes_from_slc.json",
     "results.invariant.coherence.median", "III", "P1; III-E"),
    ("p1_dop_frac", "1.50", "docs/stokes_from_slc.json",
     "results.invariant.dop_below_threshold.fraction", "III", "P1; fraction printed as %"),
    ("p1_phase", "-88.33", "docs/stokes_from_slc.json",
     "results.sign.phase_evidence.circular_mean_deg", "III", "P1"),
    ("p1_resultant", "0.946", "docs/stokes_from_slc.json",
     "results.sign.phase_evidence.resultant_length", "III", "P1"),
    ("p1_median_cpr", "0.21", "docs/stokes_from_slc.json",
     "results.sign.physical_median_cpr", "III", "P1; physical sign"),
    ("p1_3b", "0.000000", "docs/stokes_from_slc.json",
     "results.t3b_180.violation_fraction", "III", "P1; Eq. (1) band"),
    ("p1_joint_cond", "29.93", "docs/stokes_from_slc.json",
     "results.joint_measured.conditional.fraction", "VII", "P1; fraction printed as %"),
    ("p1_joint_all", "0.45", "docs/stokes_from_slc.json",
     "results.joint_measured.unconditional.fraction", "VII", "P1; fraction printed as %"),
    ("p2_tm", "6.09", "docs/enl_benchmark.json",
     "slc_spatial_arm.estimators.trace_moment_2x2.mode", "V", "P2"),
    ("p2_lc", "4.83", "docs/enl_benchmark.json",
     "slc_spatial_arm.estimators.log_cumulant_2x2.mode", "V", "P2"),
    ("p2_mom", "4.64", "docs/enl_benchmark.json",
     "slc_spatial_arm.estimators.moment_LH.mode", "V", "P2"),
    ("p3_paired", "4.47", "docs/mechanism_controls.json",
     "paired_difference_subband_minus_spatial.mean", "V", "P3"),
    ("p3_paired_se", "0.43", "docs/mechanism_controls.json",
     "paired_difference_subband_minus_spatial.se", "V", "P3"),
    ("p3_matched", "-1.00", "docs/mechanism_controls.json",
     "paired_difference_at_matched_width.mean", "V", "P3"),
    ("p3_width_sp", "0.95", "docs/mechanism_controls.json", "medians.width_az_spatial", "V", "P3"),
    ("p3_width_sb", "2.79", "docs/mechanism_controls.json", "medians.width_az_subband", "V", "P3"),
    ("p4_8_ind", "18.81", "docs/kclutter_within_cell.json", "rows[1].exceed_percent", "VII", "P4"),
    ("p4_4_ind", "19.69", "docs/kclutter_within_cell.json", "rows[4].exceed_percent", "VII", "P4"),
    ("p4_enl_4", "9.34", "docs/kclutter_within_cell.json",
     "rows[4].enl_of_textured_intensity", "VII", "P4"),
    ("p5_max_med", "1.91", "docs/f2_maximum.json",
     "results.N13p72.correlated_max_over_amplitude_pixels.median", "VII", "P5"),
    ("p5_max_p95", "2.73", "docs/f2_maximum.json",
     "results.N13p72.correlated_max_over_amplitude_pixels.p95", "VII", "P5"),
    ("p5_count", "46.5", "docs/f2_maximum.json",
     "results.N13p72.exceedance_count_over_amplitude_pixels.mean", "VII", "P5"),
    ("p6_dcpr_max", "1.31e-2", "docs/propagation_percentiles.json",
     "cpr.over_amplitude_mask.max", "II", "P6"),
    ("p6_ddop_max", "0.139", "docs/propagation_percentiles.json",
     "dop.over_amplitude_mask.max", "II", "P6"),
    ("p7_joint_se", "0.017", "docs/cpr_significance.json",
     "joint_criterion.headline_at_cpr_0p7.joint_se_percent", "VII", "P7"),
    ("p7_joint_max", "3.4", "docs/cpr_significance.json",
     "joint_criterion.maximising_point_requested.joint_fp_percent", "VII", "P7"),
    # ---- generality -------------------------------------------------------
    ("gen_lh", "2.28", "docs/enl_generality.json",
     "measurements[4].measured_enl", "V", "2020-03-05 L LH"),
    ("gen_lv", "2.21", "docs/enl_generality.json",
     "measurements[5].measured_enl", "V", "2020-03-05 L LV"),
    # predictions[] gained the two S-band labels; the 2020-03-05 L-band row is
    # index 2 (its `label` path names the product, which the audit prints).
    ("gen_ceiling", "13.42", "docs/enl_predictions.json",
     "predictions[2].predicted_ceiling", "V", "2020-03-05 L; predictions[2].label"),
    ("gen_osamp", "2.905", "docs/enl_predictions.json",
     "predictions[2].oversampling", "V", "2020-03-05 L"),
    ("gen_looks", "39", "docs/enl_predictions.json",
     "predictions[2].declared.azimuth_looks", "V", "2020-03-05 L"),
    # ---- coverage ---------------------------------------------------------
    ("cov_amp", "15.64", "frontend/public/analysis/faustini.json",
     "masks.amplitude.fraction", "II", "fraction stored; printed as a percentage"),
    ("cov_f2", "17.09", "docs/f2_footprint.json",
     "disc_amplitude_fraction", "VII", "fraction stored; printed as a percentage"),
]

#: Arithmetic checked here, with the inputs audited on their own rows.
DERIVED = [
    ("x_bound", 0.2614797, lambda: 2 * math.atanh(0.13), 1e-6),
    ("factor", 235.0, lambda: 1.0 / 0.004261057358235121, 1.0),
    ("bias1079", 1.079, lambda: 13.72 / (13.72 - 1.0), 1e-3),
    ("floor38", 1.44, lambda: ((2 * 38 - 1) / (38 - 2)) ** 0.5, 5e-3),
    ("floor6", 1.66, lambda: ((2 * 6 - 1) / (6 - 2)) ** 0.5, 5e-3),
    ("crossing_rel", 5.99e-6,
     lambda: abs(0.004261057358235121 - 0.004261082862785302)
             / 0.004261082862785302, 5e-8),
]


def decimals(lit: str) -> int:
    lit = lit.replace(",", "")
    if "e" in lit.lower():
        return 12
    return len(lit.split(".")[1]) if "." in lit else 0


def normalise(tex: str) -> str:
    """Strip LaTeX digit separators so 120\\,000 and 2,337,086 are findable.

    Replaced with a SPACE, not deleted, so offsets stay usable for line numbers
    and so adjacent tokens cannot fuse into a number that is not in the text.
    """
    out = re.sub(r"(?<=\d)\\,(?=\d)", " ", tex)
    out = re.sub(r"(?<=\d),(?=\d\d\d)", " ", out)
    out = re.sub(r"(?<=\d)\{,\}(?=\d)", "   ", out)
    return out


def appears(tex: str, lit: str) -> list:
    """Line numbers where the literal appears, tolerating LaTeX spacing."""
    bare = lit.replace(",", "")
    pats = [re.escape(lit), re.escape(bare)]
    # the same digits with separators removed
    tex = tex + "\n" + normalise(tex)
    if "e-" in bare:
        mant, exp = bare.split("e-")
        pats.append(re.escape(mant) + r"\s*\\times\s*10\^\{?-\s*" + exp.lstrip("0"))
        pats.append(re.escape(mant) + r"[^0-9]{0,20}10\^\{?-" + exp.lstrip("0"))
    hits = []
    for p in pats:
        for m in re.finditer(p, tex):
            hits.append(tex.count("\n", 0, m.start()) + 1)
    return sorted(set(hits))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tex", default=DEFAULT_TEX)
    args = ap.parse_args()

    tex_path = BASE_DIR / args.tex
    if not tex_path.is_file():
        print(f"  MANUSCRIPT NOT FOUND: {tex_path}")
        return 1
    tex = tex_path.read_text(encoding="utf-8", errors="replace")

    print("=" * 100)
    print(f"MANUSCRIPT NUMBER AUDIT — {args.tex} (READ-ONLY)")
    print("=" * 100)
    print(f"  {'id':<18}{'printed':>12}{'artifact value':>18}  {'verdict':<10} source")
    print("  " + "-" * 96)

    rows, mismatch, nosource, absent = [], [], [], []
    for cid, lit, rel, key, section, note in AUDIT:
        lines = appears(tex, lit)
        val = artifact_value(rel, key) if rel and key else None
        if not lines:
            verdict = "ABSENT"
            absent.append((cid, lit, section))
        elif rel is None:
            verdict = "NO SOURCE"
            nosource.append((cid, lit, section, note))
        elif val is None:
            verdict = "NO SOURCE"
            nosource.append((cid, lit, section,
                             f"{rel} has no key {key}"))
        else:
            try:
                printed = float(lit.replace(",", ""))
            except ValueError:
                printed = None
            if printed is None:
                ok = False
            elif "e" in lit.lower():
                # SIGNIFICANT FIGURES, not decimal places. Comparing 4.261e-3 at
                # twelve decimals against 0.004261082862785302 called a correct
                # figure a MISMATCH -- the audit was wrong, not the manuscript.
                sig = len(lit.lower().split("e")[0].replace(".", "").lstrip("0"))
                ok = (printed == 0 and float(val) == 0) or (
                    float(val) != 0
                    and round(float(val),
                              sig - 1 - int(math.floor(math.log10(abs(float(val))))))
                    == printed)
            else:
                d = decimals(lit)
                # A fraction stored 0..1 and printed as a percentage is the same
                # measurement, not a second source.
                ok = (round(float(val), d) == round(printed, d)
                      or round(float(val) * 100.0, d) == round(printed, d))
            verdict = "PASS" if ok else "MISMATCH"
            if not ok:
                mismatch.append((cid, lit, val, rel, key, section))
        shown = "—" if val is None else f"{val:.6g}"
        src = f"{rel}::{key}" if rel else (note or "")
        print(f"  {cid:<18}{lit:>12}{shown:>18}  {verdict:<10} {src}")
        rows.append({"id": cid, "printed": lit, "artifact": rel, "key": key,
                     "artifact_value": val, "verdict": verdict,
                     "section": section, "note": note,
                     "tex_lines": lines})

    print("\n  DERIVED arithmetic:")
    derived_bad = []
    for cid, printed, fn, tol in DERIVED:
        got = fn()
        ok = abs(got - printed) <= tol
        print(f"    {cid:<16} printed {printed:<14g} computed {got:<20.10g} "
              f"{'ok' if ok else 'MISMATCH'}")
        if not ok:
            derived_bad.append((cid, printed, got))

    out = {
        "schema": "lunar-ice/manuscript-audit/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "computed_by": "backend/scripts/audit_manuscript_numbers.py",
        "manuscript": args.tex,
        "manuscript_is_read_only": True,
        "n_audited": len(rows),
        "counts": {"PASS": sum(1 for r in rows if r["verdict"] == "PASS"),
                   "MISMATCH": len(mismatch), "NO SOURCE": len(nosource),
                   "ABSENT": len(absent)},
        "rows": rows,
        "derived_checks_failed": derived_bad,
    }
    (BASE_DIR / "docs" / "manuscript_number_audit.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")

    print(f"\n  {out['counts']}")
    if mismatch:
        print("\n  MISMATCH:")
        for cid, lit, val, rel, key, sec in mismatch:
            print(f"    {cid} (§{sec}): manuscript {lit}, {rel}::{key} = {val}")
    if nosource:
        print("\n  NO SOURCE:")
        for cid, lit, sec, why in nosource:
            print(f"    {cid} (§{sec}): {lit} — {why}")
    if absent:
        print("\n  ABSENT from the .tex:")
        for cid, lit, sec in absent:
            print(f"    {cid} (§{sec}): {lit}")
    print("\n  wrote docs/manuscript_number_audit.json")
    print("  This is a REPORT. The manuscript is not edited here.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
