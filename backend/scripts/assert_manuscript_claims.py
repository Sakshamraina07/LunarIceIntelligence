"""
assert_manuscript_claims.py -- G30. The manuscript's claims are the artifacts'
numbers, and the claims are the CURRENT ones.

    python backend/scripts/assert_manuscript_claims.py [--inject <check>]

WHY, AND WHY IT WAS REWRITTEN 2026-09-16
----------------------------------------
Artifacts were emitted so the manuscript's sensitivity sentences would have a
source; an artifact nobody asserts against is a file, not a gate. The first
version of this gate asserted eight of those sentences -- and the 10-page
revision then changed four of them. A gate that goes on asserting a withdrawn
sentence is worse than no gate: it holds the old claim in place and reports
PASS while doing it.

So every check below states the claim the manuscript makes NOW, and the ones
that changed say what they used to say. Digits where the computation is
deterministic; the claim where the digits depend on RNG state (kclutter,
patch_bias: see those scripts).

    S1  slepian      2WT 6.77, participation ratio 7.34, Hamming 4.07 -- and
                     NEITHER IS A BOUND: a mildly shaped spectrum of the same
                     support gives 7.38, above the rectangular value.
                     WAS: "Hamming < measured < rectangular", read as bracketing.
    S2  table5       the row at raw ENL 5.83 reproduces N = 13.72, critical
                     value 1.895 and a 17.79 % noise exceedance (an upper bound
                     over the coherence range tested)
    S3  background   exceedance rises monotonically with the assumed background
                     and spans more than a hundred-fold from 0.3 to 0.9
    S4  correlated   17.6 / 14.1 / 6.3 / 1.9 % at |rho| = 0 / 0.5 / 0.8 / 0.9
    S5  joint        the joint rate at N = 14, CPR 0.7 prints as 1.8 %; the
                     Monte Carlo marginal is within 0.5 points of F
    S6  kclutter     |shared - F| within the sampling error of the DIFFERENCE at
                     the recorded trial count; independent rows span 27-40 %
    S7  patch_bias   correlation inflates the 16x16 mode above 6 by more than
                     the 32x32 mode; the uncorrelated control is 6 at both
    S8  stationary   four blocks, the 16x16 mode ranging 3.3 to 8.0
    S9  mechanism    the arms differ by +4.47 +/- 0.43 looks, and by
                     -1.00 +/- 0.57 at matched azimuth resolution: a resolution
                     effect on the estimator, not a look-count difference.
                     WAS: "the two methods do not deliver the same number of
                     looks" -- withdrawn.
    S10 benchmark    the nominally 95 % procedure covers 12-26 % of the time and
                     the mode estimator reads ~16 % high, so the ENL ranges
                     state PRECISION, not confidence. WAS: "95 % bootstrap
                     interval" -- withdrawn.
    S11 power        P(R > crit) is 5 % at true CPR 1.00 and 16.4 % at 1.2989,
                     the largest the DOP coupling admits
    S12 exclusion    40.21 % excluded / 59.79 % undecidable, summing to the
                     measured pixel count, and agreeing with the figure cache
    S13 stokes       coherence 0.658, DOP < 0.13 on 1.50 % of cells, zero
                     violations of either band, and the physical sign is the
                     reading whose median is below 1
    S14 no_interval  no interval is reported on the candidate area, and the
                     withdrawal is on the record. WAS: a Wilson interval --
                     withdrawn.

Fails on purpose with --inject <check>.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
D = BASE_DIR / "docs"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

CHECKS = ("slepian", "table5", "background", "correlated", "joint", "kclutter",
          "patch_bias", "stationarity", "mechanism", "benchmark", "power",
          "exclusion", "stokes", "no_interval")


def load(name):
    return json.loads((D / f"{name}.json").read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inject", choices=CHECKS, default=None)
    args = ap.parse_args()
    inj = args.inject
    bad = []

    def note(ok, label):
        print(f"  {'ok ' if ok else 'BAD'}  {label}")
        if not ok:
            bad.append(label)

    print("=" * 78)
    print("G30 — the manuscript's current claims against their artifacts")
    print("=" * 78)

    # ---- S1 ---------------------------------------------------------------
    s = load("slepian_ceiling")
    twt, pr, hm = (s["two_WT_asymptotic"], s["participation_ratio_rectangular"],
                   s["enl_hamming_054"])
    shaped, meas = s["enl_mildly_shaped_spectrum"], s["measured_spatial_arm"]
    if inj == "slepian":
        shaped = 7.0
    note(round(twt, 2) == 6.77, f"S1 2WT {twt:.4f} prints 6.77")
    note(round(pr, 2) == 7.34, f"S1 participation ratio {pr:.4f} prints 7.34")
    note(round(hm, 2) == 4.07, f"S1 Hamming {hm:.4f} prints 4.07")
    note(round(shaped, 2) == 7.38, f"S1 mildly shaped spectrum {shaped:.4f} prints 7.38")
    note(shaped > pr > twt,
         f"S1 NEITHER IS A BOUND: shaped {shaped:.3f} > rectangular {pr:.3f} > "
         f"asymptotic {twt:.3f}")
    note(hm < meas < pr, f"S1 the measured arm {meas:.2f} lies between the tapered "
                         f"{hm:.2f} and untapered {pr:.2f} values")
    note(round(s["other_products"][-1]["participation_ratio_rectangular"], 2) == 14.04,
         "S1 the 39-sample product's participation ratio prints 14.04")

    # ---- S2 ---------------------------------------------------------------
    t = load("table5_sensitivity")
    det = load("detection_statistics")
    row = min(t["rows"], key=lambda r: abs(r["raw_enl"] - 5.83))
    n = row["N"] + (1.0 if inj == "table5" else 0.0)
    note(abs(row["raw_enl"] - 5.83) < 1e-9, "S2 a row exists at raw ENL 5.83")
    note(abs(n - 13.72) < 0.01, f"S2 its N {n:.4f} is the screened field's 13.72")
    note(round(row["floor_95"], 3) == 1.895,
         f"S2 its critical value {row['floor_95']:.4f} prints 1.895")
    note(round(row["fp_percent_at_cpr_0p7"], 2) == 17.79,
         f"S2 its exceedance {row['fp_percent_at_cpr_0p7']:.4f} prints 17.79 "
         f"(an upper bound over the coherence range tested)")

    # ---- S3 ---------------------------------------------------------------
    b = load("background_cpr_sweep")
    fps = [r["fp_percent"] for r in b["rows"]]
    if inj == "background":
        fps[2], fps[3] = fps[3], fps[2]
    note(all(x < y for x, y in zip(fps, fps[1:])),
         "S3 exceedance is monotone in the assumed background")
    note(fps[-1] / fps[0] > 100, f"S3 span 0.3 -> 0.9 is {fps[-1] / fps[0]:.0f}x (> 100)")

    # ---- S4 ---------------------------------------------------------------
    c = load("correlated_ratio")
    want = {0.0: 17.6, 0.5: 14.1, 0.8: 6.3, 0.9: 1.9}
    for r in c["rows"]:
        if r["rho"] in want:
            v = r["fp_percent"] + (1.0 if inj == "correlated" and r["rho"] == 0.5 else 0.0)
            note(round(v, 1) == want[r["rho"]],
                 f"S4 |rho| {r['rho']}: {v:.3f} prints {want[r['rho']]}")

    # ---- S5 ---------------------------------------------------------------
    j = load("joint_criterion")
    jr = j["headline"]["joint_fp_percent"] + (0.3 if inj == "joint" else 0.0)
    note(round(jr, 1) == 1.8, f"S5 joint rate {jr:.4f} prints 1.8 %")
    note(abs(j["headline"]["marginal_fp_percent_monte_carlo"]
             - j["marginal_fp_percent_analytic_F"]) < 0.5,
         f"S5 MC marginal {j['headline']['marginal_fp_percent_monte_carlo']:.3f} "
         f"within 0.5 of F {j['marginal_fp_percent_analytic_F']:.3f}")

    # ---- S6 ---------------------------------------------------------------
    k = load("kclutter")
    sigma_diff = k["mc_sigma_of_difference_points"]
    diffs = [abs(r["fp_shared_percent"] - k["fp_percent_F_gaussian"]) for r in k["rows"]]
    if inj == "kclutter":
        diffs[0] = 0.5
    note(max(diffs) <= 3 * sigma_diff,
         f"S6 max |shared - F| {max(diffs):.4f} <= 3 sigma of the difference "
         f"{3 * sigma_diff:.4f} at {k['trials_per_row']:,} trials")
    note(round(sigma_diff, 2) == 0.02,
         f"S6 the quoted sampling error {sigma_diff:.4f} prints 0.02 points")
    fin = [r["fp_independent_percent"] for r in k["rows"] if r["nu"] is not None]
    note(27.0 <= min(fin) and max(fin) <= 40.0,
         f"S6 independent rows span {min(fin):.2f}-{max(fin):.2f} % within 27-40")

    # ---- S7 ---------------------------------------------------------------
    pb = load("patch_bias")
    c16, c32 = pb["correlated"]["16"]["mode"], pb["correlated"]["32"]["mode"]
    u16, u32 = pb["uncorrelated_control"]["16"], pb["uncorrelated_control"]["32"]
    if inj == "patch_bias":
        c16 = 6.0
    note(c16 - 6.0 > c32 - 6.0 > -0.15,
         f"S7 correlated 16x16 {c16:.2f} above 32x32 {c32:.2f} above ~6")
    note(c16 > 6.3, f"S7 16x16 mode {c16:.2f} inflated above 6.3")
    note(abs(u16 - 6.0) < 0.15 and abs(u32 - 6.0) < 0.15,
         f"S7 uncorrelated control {u16:.2f} / {u32:.2f} at 6")

    # ---- S8 ---------------------------------------------------------------
    st = load("stationarity")
    lo, hi = st["enl_min"], st["enl_max"] + (0.5 if inj == "stationarity" else 0.0)
    note(st["n_blocks_used"] == 4,
         f"S8 {st['n_blocks_used']} blocks with coverage (manuscript: four)")
    note(round(lo, 1) == 3.3 and round(hi, 1) == 8.0,
         f"S8 mode ranges {lo:.2f} to {hi:.2f} (prints 3.3 to 8.0)")

    # ---- S9 ---------------------------------------------------------------
    m = load("mechanism_controls")
    raw = m["paired_difference_subband_minus_spatial"]
    mat = m["paired_difference_at_matched_width"]
    mm = mat["mean"] + (3.0 if inj == "mechanism" else 0.0)
    note(round(raw["mean"], 2) == 4.47 and round(raw["se"], 2) == 0.43,
         f"S9 raw paired difference {raw['mean']:+.3f} +/- {raw['se']:.3f} "
         f"over {raw['n_windows']} windows")
    note(round(mm, 2) == -1.00 and round(mat["se"], 2) == 0.57,
         f"S9 at matched width {mm:+.3f} +/- {mat['se']:.3f} over "
         f"{mat['n_windows']} windows")
    note(abs(mm) < 2 * mat["se"],
         f"S9 THE ARMS AGREE at matched resolution: |{mm:.2f}| is inside "
         f"2 SE ({2 * mat['se']:.2f}), so the 4.47 gap is a resolution effect")
    note(m["medians"]["width_az_subband"] > 2 * m["medians"]["width_az_spatial"],
         f"S9 and they differ in azimuth resolution: "
         f"{m['medians']['width_az_spatial']:.2f} vs "
         f"{m['medians']['width_az_subband']:.2f} rows")

    # ---- S10 --------------------------------------------------------------
    eb = load("enl_benchmark")["synthetic"]["speckle_only_summary"]
    cov = eb["coverage_percent_range"]
    relb = eb["relative_bias_percent_median"] + (20.0 if inj == "benchmark" else 0.0)
    note(round(cov[0]) == 12 and round(cov[1]) == 26,
         f"S10 the nominally 95 % procedure covers {cov[0]:.0f}-{cov[1]:.0f} % "
         f"of the time")
    note(cov[1] < 95.0,
         f"S10 THE RANGES STATE PRECISION, NOT CONFIDENCE: best coverage "
         f"{cov[1]:.0f} % is far below the nominal 95 %")
    note(round(relb) == 16, f"S10 the mode estimator reads {relb:.1f} % high")
    note(round(eb["raw_enl_5p83_corrected"], 1) == 5.0,
         f"S10 5.83 read through that bias is "
         f"{eb['raw_enl_5p83_corrected']:.3f}, near 5.0")

    # ---- S11 --------------------------------------------------------------
    pw = det["sampling_statistics"]["power_at_operating_point"]
    rows = {r["true_cpr"]: r["power_percent"] for r in pw["rows"]}
    p1299 = rows[1.2988505747126435] + (10.0 if inj == "power" else 0.0)
    note(round(rows[1.0]) == 5, f"S11 the size of the test at CPR 1.00 is "
                                f"{rows[1.0]:.2f} %, the nominal 5 %")
    note(round(p1299, 1) == 16.4,
         f"S11 power at 1.2989, the largest the coupling admits, is {p1299:.2f} %")
    note(p1299 < 20.0, "S11 inside the admissible band the test has almost no power")
    note([round(rows[c]) for c in (1.5, 2.0, 3.0)] == [27, 56, 88],
         f"S11 power at 1.5 / 2 / 3 prints 27 / 56 / 88 %")

    # ---- S12 --------------------------------------------------------------
    dx = load("dop_exclusion")
    exc = dx["excluded_percent"] + (5.0 if inj == "exclusion" else 0.0)
    note(round(exc, 2) == 40.21, f"S12 excluded {exc:.4f} % prints 40.21")
    note(round(dx["undecidable_percent"], 2) == 59.79,
         f"S12 undecidable {dx['undecidable_percent']:.4f} % prints 59.79")
    note(dx["excluded_pixels"] + dx["undecidable_pixels"] == dx["measured_pixels"],
         f"S12 the two parts sum to the {dx['measured_pixels']:,} measured pixels")
    note(dx["figure_cache_cross_check"].get("agrees_with_this_run") is True,
         "S12 and they agree with the histogram the published figure is drawn from")

    # ---- S13 --------------------------------------------------------------
    sk = load("stokes_from_slc")["results"]
    coh = sk["invariant"]["coherence"]["median"]
    dopf = sk["invariant"]["dop_below_threshold"]["fraction"] * 100
    if inj == "stokes":
        dopf = 9.9
    note(round(coh, 3) == 0.658, f"S13 measured coherence {coh:.4f} prints 0.658")
    note(round(dopf, 2) == 1.50, f"S13 Stokes DOP < 0.13 on {dopf:.4f} % of cells")
    note(sk["t3b_0"]["violation_fraction"] == 0.0
         and sk["t3b_180"]["violation_fraction"] == 0.0,
         "S13 the Stokes CPR lies inside Eq. (1)'s band at every cell, both signs")
    note(sk["invariant"]["t3f_coupling_band"]["fraction_outside"] == 0.0,
         "S13 and inside the coupling band at every low-DOP cell")
    note(sk["sign"]["physical_median_cpr"] < 1.0,
         f"S13 the physical sign is the reading with median "
         f"{sk['sign']['physical_median_cpr']:.4f} < 1")

    # ---- S14 --------------------------------------------------------------
    ca = det["candidate_area"]
    reported = ca.get("reported_interval", "missing")
    if inj == "no_interval":
        reported = [0.0, 0.147453]
    note(reported is None, f"S14 no interval is reported: reported_interval = {reported}")
    note(bool(ca.get("withdrawn_interval", {}).get("why")),
         "S14 the withdrawal is on the record with its reason")
    note(ca["area_km2"] == 0.0 and ca["pixels"] == 0,
         f"S14 the candidate area is {ca['area_km2']} km2 from {ca['pixels']} pixels")

    print()
    if bad:
        print(f"  GATE FAIL — {len(bad)} claim(s) not backed by their artifact")
        return 1
    print(f"  GATE PASS — all {len(CHECKS)} claim groups are the numbers their")
    print("  artifacts hold, and each is the claim the manuscript makes now.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
