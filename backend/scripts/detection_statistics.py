"""
plan: PRD Phase 8 -- detection statistics. The contribution.

    python -u backend/scripts/detection_statistics.py

FOUR DELIVERABLES
-----------------
  A. a PER-PIXEL SIGNIFICANCE field: not "is this value high" but "is it
     significantly above threshold", at a stated confidence and a NAMED
     effective look count;
  B. CANDIDATE AREA WITH A CONFIDENCE INTERVAL. A measured zero with a CI is
     still a result, and it is a better one than a bare zero;
  C. a re-analysis of the published detections against their own detection
     floors, with EVERY assumption listed beside it;
  D. the assertion, in emit_provenance, that a reported detection area must
     carry its interval.

TWO STATISTICS, AND THEY MUST NOT BE SWAPPED
---------------------------------------------
  * PUBLISHED CPR is sigma_SC/sigma_OC, a ratio of two N-look INTENSITIES, so it
    is distributed as CPR * F(2N, 2N). The literature critique uses that.
  * OUR PROXY is ((sqrt(LH) - sqrt(LV))/(sqrt(LH) + sqrt(LV)))^2, a different
    functional form with a different distribution, and METHODS 7.9.2 shows it has
    ZERO sensitivity to CPR. Anything about our own numbers uses the Monte Carlo,
    never F(2N,2N).

Mixing them would be exactly the error this phase exists to point out.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import tifffile
from scipy.stats import f as fdist

BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

NATIVE = BASE_DIR / "data" / "pradan" / "native"
OUT = BASE_DIR / "docs" / "detection_statistics.json"
OUT_UI = BASE_DIR / "frontend" / "public" / "analysis" / "detection_statistics.json"
SIG_TIF = NATIVE / "cpr_significance.tif"

#: Measured in METHODS 7.3-7.6. The raw product carries ~5 looks; the 5x5 boxcar
#: the pipeline applies buys 2.35x (LH) to 3.84x (LV), NOT 25x, because the
#: pixels are correlated. So the field that is actually thresholded carries
#: 13.7-19.8. Both ends are carried through rather than averaged into one.
ENL_SCREENING = (13.72, 19.77)
ENL_RAW = (5.83, 5.14)

#: Published detections this project can name. CPR values as reported.
PUBLISHED = [
    {"feature": "F2", "cpr": 1.95, "source": "Sinha et al. 2026",
     "mode": "full-pol L+S", "looks_stated": None},
    {"feature": "F3", "cpr": 1.60, "source": "Sinha et al. 2026",
     "mode": "full-pol L+S", "looks_stated": None},
    {"feature": "S1", "cpr": 1.45, "source": "Sinha et al. 2026",
     "mode": "full-pol L+S", "looks_stated": None},
    {"feature": "H3", "cpr": 1.30, "source": "Sinha et al. 2026",
     "mode": "full-pol L+S", "looks_stated": None},
]

#: Every assumption the re-analysis rests on. Listed beside the table, not
#: buried, because a re-analysis whose assumptions are not visible is an
#: assertion.
ASSUMPTIONS = [
    "Published CPR is sigma_SC/sigma_OC from the Stokes vector, so it is a ratio "
    "of two N-look intensities and distributed as CPR * F(2N,2N). This is stated "
    "in the source and is not our inference.",
    "The look count for their product is NOT STATED in the open text. The table "
    "is therefore computed ACROSS a range of N rather than at one value, and no "
    "single critical value is quoted for their data.",
    "OUR measured ENL cannot be transferred to their product. Ours is a "
    "compact-pol sri product from one pass; theirs is full-polarimetric L- and "
    "S-band from a different acquisition and a different processing chain. The "
    "point is not that their N is ours -- it is that NOBODY HAS MEASURED THEIRS.",
    "The floors below are for a SINGLE PIXEL at 95 % confidence. A detection "
    "averaged over many pixels has a lower floor, by roughly sqrt(n_eff) -- and "
    "n_eff, not n, because CPR pixels are correlated (METHODS 7.9.1 measures "
    "61.5 px per independent sample in our own field).",
    "No claim is made that any published detection is wrong. The claim is that "
    "the floor is not reported alongside it, so a reader cannot tell.",
]


def hr(t: str) -> None:
    print("\n" + "-" * 78)
    print(t)
    print("-" * 78, flush=True)


def ratio_sd(n: float) -> float:
    """Relative SD of a ratio of two n-look intensities. NOT 1/sqrt(n)."""
    return math.sqrt((2 * n - 1) / (n * (n - 2))) if n > 2 else float("inf")


def floor_95(n: float) -> float:
    """True CPR needed for a single pixel to read above 1.0 with 95 % confidence."""
    return 1.0 / fdist.ppf(0.05, 2 * n, 2 * n)


#: The look counts of the manuscript's sampling-statistics table, each with the
#: reason it is in the table. They are NOT a smooth grid: every row is a number
#: this project measured, read from a label, or took from print, and the table
#: is read DOWN a column because the published look count is not stated.
#: (N as the table prints it, N as the measurement carries it, why)
#: Four of the seven are rounded in print, and the rounding is not cosmetic:
#: at three decimals it moves a cell. Both columns are computed and emitted,
#: because a reader can only reproduce from the printed value while the
#: measurement is the unrounded one.
SAMPLING_TABLE_N = [
    (5.00, 5.00, "the raw product's ENL rounded down (5.83 LH, 5.14 LV) — METHODS 7.3"),
    (6.77, 6.77, "2WT = 21 / 3.10, the asymptotic value for a 21-sample average of an "
                 "oversampled band — docs/slepian_ceiling.json::two_WT_asymptotic "
                 "carries 6.773174590024859"),
    (8.75, 8.754410943745066,
     "median N inverted from the published CPR dispersion of Fa & Cai 2013 — "
     "docs/published_moments.json::median_N_from_dispersion"),
    (13.72, 13.716639679503347,
     "THE OPERATING POINT: the ENL of the boxcar-smoothed LH field, the field the "
     "screen is formed on — docs/enl.json::boxcar_gain.LH.enl_boxcar5"),
    (19.77, 19.76772534356128,
     "the same for LV; the two smoothed channels differ — "
     "docs/enl.json::boxcar_gain.LV.enl_boxcar5"),
    (21.00, 21.00, "the label's declared azimuth_looks — a processing parameter"),
    (38.00, 38.00, "the '~38 look average' quoted for Peary crater in the DFSAR "
                   "instrument paper (Bhiravarasu et al. 2021)"),
]

#: True CPR values at which the test's POWER is quoted. 1.2989 is the largest
#: the DOP < 0.13 coupling admits, which is why it is the interesting one.
POWER_AT_TRUE_CPR = [1.00, 1.2988505747126435, 1.5, 2.0, 3.0]


def exceedance(n: float, true_cpr: float, threshold: float = 1.0) -> float:
    """P(R > threshold) as a percentage, R/CPR ~ F(2N, 2N)."""
    return float((1.0 - fdist.cdf(threshold / true_cpr, 2 * n, 2 * n)) * 100.0)


def _correlation_area() -> float:
    """Pixels per independent sample, READ from cpr_significance.json.

    Not a literal. METHODS 7.9.1 measures it by integrating the two-dimensional
    autocorrelation of the CPR field, and 7.9.1 and 7.10 once carried 61.5 and
    61.42 for this one quantity. A second transcription here would be a third.
    """
    f = Path(__file__).resolve().parents[2] / "docs" / "cpr_significance.json"
    doc = json.loads(f.read_text(encoding="utf-8"))
    return float(doc["effective_samples"]["area_all_lags"])


def wilson(k: int, n: int, z: float = 1.959964):
    """Wilson score interval for a proportion. Correct AT ZERO, which is the
    whole reason it is used here: the normal approximation gives [0, 0] for k = 0
    and would report a measured zero as having no uncertainty at all."""
    if n <= 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def _textured_rows() -> list:
    base = Path(__file__).resolve().parents[2]
    k = json.loads((base / "docs" / "kclutter_within_cell.json").read_text(encoding="utf-8"))
    out = []
    for i in (1, 4):
        n = float(k["rows"][i]["enl_of_textured_intensity"])
        out.append({"row": i, "moment_enl": n,
                    "p_exceed_true_cpr_0p7_percent": exceedance(n, 0.7, 1.0),
                    # the manuscript prints the ENL to one decimal (11.2, 9.3);
                    # at that printed value the tail differs in the third digit
                    "moment_enl_printed": round(n, 1),
                    "p_exceed_true_cpr_0p7_percent_at_printed_enl": exceedance(round(n, 1), 0.7, 1.0),
                    "simulated_exceed_percent": float(k["rows"][i]["exceed_percent"])})
    return out


def derived_closed_forms(area_px: float) -> dict:
    """Closed forms Section V prints in running text, computed here so each
    literal resolves to a key rather than to arithmetic done in the prose.
    Every figure is a function of the F(2N, 2N) model or of measured inputs
    read from their own artifacts; none is a new measurement."""
    from scipy.optimize import brentq

    base = Path(__file__).resolve().parents[2]
    edge = (1.0 + 0.13) / (1.0 - 0.13)          # the coupling band's upper edge
    n_edge = float(brentq(lambda n: floor_95(n) - edge, 10.0, 1000.0))
    n_op = 13.72
    f2 = json.loads((base / "docs" / "f2_footprint.json").read_text(encoding="utf-8"))
    disc = int(f2["disc_pixels"])
    t3 = json.loads((base / "docs" / "table5_sensitivity.json").read_text(encoding="utf-8"))
    sens = []
    for r in t3["rows"]:
        n_print = round(float(r["N"]), 2)
        sens.append({"raw_enl": r["raw_enl"], "N_unrounded": float(r["N"]),
                     "N_printed": n_print,
                     "crit_95_at_printed_N": floor_95(n_print),
                     "crit_95_at_unrounded_N": floor_95(float(r["N"])),
                     "p_exceed_true_cpr_0p7_percent_at_printed_N":
                         exceedance(n_print, 0.7, 1.0)})
    return {
        "note": ("closed forms printed in Section V's running text; each is a "
                 "function of F(2N, 2N) or of inputs read from other artifacts"),
        "n_at_which_crit_equals_band_edge": {
            "band_edge": edge, "N": n_edge,
            "printed": "N ~ 80",
            "statement": "one-sided 95 % point of F(2N, 2N) equals (1 + 0.13)/(1 - 0.13)"},
        "p_exceed_at_operating_point": {
            "N": n_op, "threshold": 1.0,
            "rows": [{"true_cpr": c, "p_exceed_percent": exceedance(n_op, c, 1.0)}
                     for c in (0.4, 0.5, 0.7, 0.8, 0.9, 1.0, 1.12)]},
        "sensitivity_crit_three_decimals": {
            "note": ("V-A prints the Table-III-era sensitivity rows in text, the "
                     "critical value to three decimals; at printed and unrounded N "
                     "they round alike"),
            "rows": sens},
        "f_exceedance_N14_cpr0p7_percent": exceedance(14.0, 0.7, 1.0),
        # V-C: the F model evaluated at the textured fields' OWN moment ENLs, as
        # the pipeline evaluates it (kclutter_within_cell.json rows 1 and 4)
        "f_exceedance_at_textured_enl": _textured_rows(),
        "effective_samples_f2_disc": {
            "disc_pixels": disc, "pixels_per_independent_sample": area_px,
            "effective_samples": disc / area_px,
            "sources": ["docs/f2_footprint.json::disc_pixels",
                        "docs/cpr_significance.json::effective_samples.area_all_lags"]},
    }


def main() -> int:
    from app.core.config import settings as cfg
    ap = argparse.ArgumentParser()
    ap.add_argument("--confidence", type=float, default=0.95)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    cpr = np.asarray(tifffile.imread(str(NATIVE / "cpr_native.tif")), dtype=np.float64)
    dop = np.asarray(tifffile.imread(str(NATIVE / "dop_native.tif")), dtype=np.float64)
    valid = np.asarray(tifffile.imread(str(NATIVE / "valid_native.tif"))) > 0
    cell_km2 = 25.0 * 25.0 / 1e6
    cpr_th = float(cfg.CPR_THRESHOLD)
    dop_th = float(cfg.DOP_THRESHOLD)

    hr("A. PER-PIXEL SIGNIFICANCE — not 'is it high' but 'is it ABOVE THRESHOLD'")
    print(f"  effective look count of the SCREENED field: "
          f"{ENL_SCREENING[0]:.2f} (LH) to {ENL_SCREENING[1]:.2f} (LV)")
    print(f"  measured in METHODS 7.3-7.6: the raw product carries "
          f"{ENL_RAW[0]:.2f}/{ENL_RAW[1]:.2f} looks and the 5x5 boxcar buys")
    print(f"  2.35-3.84x, NOT 25x, because the pixels are correlated.")
    print(f"  confidence: {args.confidence:.0%}, single pixel, threshold "
          f"CPR > {cpr_th:g}\n")

    for n in ENL_SCREENING:
        print(f"  at N = {n:5.2f}:  relative SD {ratio_sd(n):.3f}   "
              f"bias E[R]/CPR {n / (n - 1):.3f}   "
              f"single-pixel 95 % floor {floor_95(n):.3f}")
    n_lo, n_hi = ENL_SCREENING
    print(f"\n  A PIXEL MUST READ ABOVE {floor_95(n_hi):.3f}-{floor_95(n_lo):.3f} TO BE")
    print(f"  SIGNIFICANTLY ABOVE A THRESHOLD OF {cpr_th:g}. The swath's maximum is")
    print(f"  {cpr[valid].max():.4f}.")

    # THE SIGNIFICANCE FIELD. Our proxy is not F-distributed, so this is NOT a
    # p-value on it -- it is the ratio of the measured value to the floor a true
    # sigma_SC/sigma_OC would have to clear. Named accordingly.
    floor = floor_95(n_lo) * cpr_th
    sig = np.where(valid, cpr / max(floor, 1e-12), np.nan).astype(np.float32)
    tifffile.imwrite(str(SIG_TIF), sig)
    above = int(np.nansum(sig >= 1.0))
    print(f"\n  significance raster -> {SIG_TIF.relative_to(BASE_DIR)}")
    print(f"  pixels at or above the floor: {above:,} of {int(valid.sum()):,}")
    print(f"  ratio of the swath maximum to the floor: "
          f"{cpr[valid].max() / floor:.3e}  (it is {floor / max(cpr[valid].max(), 1e-12):,.0f}x short)")

    hr("B. CANDIDATE AREA, WITH A CONFIDENCE INTERVAL")
    print("  A measured zero with an interval is still a result, and a better one")
    print("  than a bare zero: it says how large a real signal could have been and")
    print("  still produced this observation.\n")
    cand = valid & (cpr > cpr_th) & (dop < dop_th)
    k, n_px = int(cand.sum()), int(valid.sum())
    _z = {0.95: 1.959964, 0.99: 2.575829}.get(args.confidence, 1.959964)
    lo_raw, hi_raw = wilson(k, n_px, _z)

    # THE INTERVAL MUST BE TAKEN ON INDEPENDENT SAMPLES, NOT ON PIXELS.
    #
    # The raw-pixel interval treats 2,337,086 correlated pixels as 2,337,086
    # independent trials. METHODS 7.9.1 measured the correlation area of this
    # field at 61.42 px per independent sample, so the pixel count overstates
    # the sample size by ~61x and the interval comes out ~61x too narrow. A
    # confidence interval that is too narrow is worse than none: it states a
    # precision the data does not have, on the one number this project exists
    # to report honestly.
    #
    # ROUND, AND THE REASON IS RECORDED. 2,337,086 / 61.420749918170166 =
    # 38050.43089..., which rounds to 38,050. An earlier revision used ceil to
    # match a manuscript that printed 38,051 -- bending the code to a typo. An
    # effective sample count is not something you round up; the manuscript was
    # corrected instead. The headline does not move: the upper bound is
    # 0.147 km2 at either count.
    area_px = float(_correlation_area())
    n_eff = round(n_px / area_px)
    lo_eff, hi_eff = wilson(k, n_eff, _z)
    lo, hi = lo_eff, hi_eff
    print(f"  candidate pixels      {k:,} of {n_px:,} measured")
    print(f"  candidate area        {k * cell_km2:.4f} km²")
    _frame = n_px * cell_km2
    print(f"  correlation area      {area_px:.4f} px per independent sample "
          f"(METHODS 7.9.1)")
    print(f"  effective samples     {n_eff:,}  = round({n_px:,} / {area_px:.4f})")
    print(f"  {args.confidence:.0%} Wilson, RAW PIXELS  "
          f"[{lo_raw * _frame:.4f}, {hi_raw * _frame:.4f}] km²   "
          f"<- SUPERSEDED, ~61x too narrow")
    print(f"  {args.confidence:.0%} Wilson interval  "
          f"[{lo * _frame:.4f}, {hi * _frame:.4f}] km²   <- on effective samples")
    print(f"  i.e. 0 km², and the data would not have distinguished anything up to")
    print(f"  {hi * n_px * cell_km2:.4f} km² from zero.")
    print("\n  WILSON, NOT THE NORMAL APPROXIMATION. At k = 0 the normal interval is")
    print("  [0, 0] -- it would report a measured zero as having no uncertainty at")
    print("  all, which is the single most misleading thing this table could say.")

    hr("B2. THE SAMPLING-STATISTICS TABLE — every cell, from the closed forms")
    print("  R/CPR ~ F(2N, 2N) for a ratio of two independent N-look intensities.")
    print("  rel.SD = sqrt((2N-1)/(N(N-2))),  bias = N/(N-1),")
    print("  95 % crit. = F^-1(0.95; 2N, 2N),  P_c = 1 - F(1/c; 2N, 2N).\n")
    print(f"  {'N':>7}{'rel.SD':>9}{'bias':>8}{'95% crit':>10}"
          f"{'P(0.7)':>9}{'P(0.5)':>9}   cells that move at the unrounded N")

    def cells(n: float) -> dict:
        return {"rel_sd": round(ratio_sd(n), 3), "bias": round(n / (n - 1), 3),
                "crit_95": round(floor_95(n), 3),
                "p_exceed_true_cpr_0p7_percent": round(exceedance(n, 0.7), 2),
                "p_exceed_true_cpr_0p5_percent": round(exceedance(n, 0.5), 2)}

    table_rows = []
    for n_pr, n_ex, why in SAMPLING_TABLE_N:
        at_printed, at_measured = cells(n_pr), cells(n_ex)
        moved = {k: [v, at_measured[k]] for k, v in at_printed.items()
                 if at_measured[k] != v}
        table_rows.append({"N": n_pr, "N_measured": n_ex, **at_printed,
                           "at_measured_N": at_measured,
                           "cells_that_move_at_measured_N": moved, "why": why})
        print(f"  {n_pr:>7.2f}{at_printed['rel_sd']:>9.3f}{at_printed['bias']:>8.3f}"
              f"{at_printed['crit_95']:>10.3f}"
              f"{at_printed['p_exceed_true_cpr_0p7_percent']:>8.2f}%"
              f"{at_printed['p_exceed_true_cpr_0p5_percent']:>8.2f}%   "
              + (", ".join(f"{k} {v[0]}->{v[1]}" for k, v in moved.items()) or "-"))

    n_op = ENL_SCREENING[0]
    crit_op = floor_95(n_op)
    print(f"\n  POWER at the operating point N = {n_op}, against the critical value "
          f"{crit_op:.4f}:")
    power = []
    for c in POWER_AT_TRUE_CPR:
        p = exceedance(n_op, c, crit_op)
        power.append({"true_cpr": c, "power_percent": round(p, 2)})
        tag = ("  <- the largest true CPR the DOP < 0.13 coupling admits"
               if abs(c - 1.2988505747126435) < 1e-9 else
               "  <- the size of the test at the null" if c == 1.0 else "")
        print(f"    true CPR {c:<8.4f}  P(R > {crit_op:.3f}) = {p:6.2f} %{tag}")
    print("  Inside the band the coupling admits, the test has almost no power.")

    hr("C. THE PUBLISHED DETECTIONS AGAINST THEIR OWN FLOORS")
    print("  Published CPR is sigma_SC/sigma_OC and IS F(2N,2N)-distributed, so the")
    print("  F machinery applies to these values and not to ours.\n")
    ns = [6, 9, 21, 38, 100]
    print(f"  {'feature':>8}{'CPR':>7}" + "".join(f"{'N=' + str(n):>9}" for n in ns))
    print(f"  {'':>8}{'':>7}" + "".join(f"{floor_95(n):>9.2f}" for n in ns)
          + "   <- 95 % single-pixel floor")
    rows = []
    for pub in PUBLISHED:
        marks = []
        for n in ns:
            marks.append("yes" if pub["cpr"] > floor_95(n) else "no")
        rows.append({**pub, "clears_floor_at": dict(zip(map(str, ns), marks)),
                     "floors": {str(n): round(floor_95(n), 3) for n in ns}})
        print(f"  {pub['feature']:>8}{pub['cpr']:>7.2f}"
              + "".join(f"{m:>9}" for m in marks))
    print("\n  Read DOWN a column, not across: at N = 6 no published value clears a")
    print("  single-pixel 95 % floor; by N = 38 all four do. THE LOOK COUNT DECIDES")
    print("  THE ANSWER, AND IT IS NOT REPORTED IN THE SOURCE.")

    print("\n  ASSUMPTIONS THIS RE-ANALYSIS RESTS ON:")
    for i, a in enumerate(ASSUMPTIONS, 1):
        print(f"   {i}. {a}")

    doc = {
        "schema": "detection_statistics/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/detection_statistics.py",
        "effective_looks": {
            "screened_field": {"lh": ENL_SCREENING[0], "lv": ENL_SCREENING[1]},
            "raw_product": {"lh": ENL_RAW[0], "lv": ENL_RAW[1]},
            "provenance": "MEASURED — METHODS 7.3, 7.4, 7.6",
        },
        "per_pixel_significance": {
            "confidence": args.confidence,
            "threshold": cpr_th,
            "floor_at_low_N": round(floor_95(n_lo), 4),
            "floor_at_high_N": round(floor_95(n_hi), 4),
            "swath_max": round(float(cpr[valid].max()), 6),
            "shortfall_factor": round(float(floor / max(cpr[valid].max(), 1e-12)), 1),
            "raster": str(SIG_TIF.relative_to(BASE_DIR)).replace("\\", "/"),
            "caveat": ("Our proxy is NOT F(2N,2N)-distributed — METHODS 7.9.2. This "
                       "raster is the ratio of the measured value to the floor a true "
                       "sigma_SC/sigma_OC would have to clear, not a p-value on our "
                       "own quantity."),
        },
        "sampling_statistics": {
            "model": ("R/CPR ~ F(2N, 2N) for a ratio of two independent N-look "
                      "intensities; rel.SD = sqrt((2N-1)/(N(N-2))), bias = N/(N-1), "
                      "95 % crit. = F^-1(0.95; 2N, 2N), P_c = 1 - F(1/c; 2N, 2N)"),
            "columns": ["N", "rel_sd", "bias", "crit_95",
                        "p_exceed_true_cpr_0p7_percent", "p_exceed_true_cpr_0p5_percent"],
            "rows": table_rows,
            "convention": ("each row is computed at the N the table PRINTS; "
                           "`at_measured_N` repeats it at the unrounded "
                           "measurement and `cells_that_move_at_measured_N` names "
                           "every cell that differs at three decimals"),
            "read_down_a_column": ("the published look count is not stated, so the "
                                   "table spans N rather than asserting one"),
            "all_exceedances_are_upper_bounds": (
                "within the correlated circular-Gaussian model and over the "
                "coherence range tested — docs/correlated_ratio.json; and an upper "
                "bound over coherence only, not over within-cell texture, which "
                "adds up to two points — docs/kclutter_within_cell.json"),
            "power_at_operating_point": {
                "N": n_op, "critical_value": round(crit_op, 4), "rows": power,
                "note": ("P(R > crit) at each true CPR. The 1.2989 row is the "
                         "largest true CPR the DOP < 0.13 coupling admits, so it "
                         "bounds the power of the joint criterion."),
            },
        },
        "candidate_area": {
            "pixels": k, "measured_pixels": n_px,
            "area_km2": round(k * cell_km2, 6),
            "confidence": args.confidence,
            "correlation_area_px": area_px,
            "n_effective": n_eff,
            "note": ("the raw-pixel interval was 61x too narrow because pixels are "
                     "not independent (61.42 px per independent sample); both "
                     "intervals are now withdrawn — see withdrawn_interval"),
            "n_effective_rounding": ("round. 2337086 / 61.420749918170166 = "
                                     "38050.43089 -> 38050. An earlier revision used "
                                     "ceil to match a manuscript that printed 38051; "
                                     "the manuscript was corrected."),
            "method": "Wilson score interval on the pass proportion, on EFFECTIVE samples",
            "why_effective": ("METHODS 7.9.1 measures 61.42 px per independent "
                              "sample by integrating the CPR autocorrelation. "
                              "Treating pixels as trials overstates n by ~61x and "
                              "narrows the interval by the same factor."),
            # THE INTERVAL IS WITHDRAWN AS A REPORTED FIGURE, 2026-09-16.
            # A Wilson interval answers "a detector fired k of n times; what is
            # its rate?". This screen is not that detector: METHODS 1 proves its
            # firing rate is zero ALGEBRAICALLY for every admissible input, so
            # the zero carries no sampling uncertainty to quantify and an
            # interval on it invites a reader to treat a structural zero as a
            # measured rate that happened to land on zero. The numbers stay for
            # the record, under a key that cannot be mistaken for a result.
            "reported_interval": None,
            "withdrawn_interval": {
                "what": "a 95 % Wilson interval on the candidate area",
                "values_km2": {
                    "on_raw_pixels": [round(lo_raw * n_px * cell_km2, 6),
                                      round(hi_raw * n_px * cell_km2, 6)],
                    "on_effective_samples": [round(lo_eff * n_px * cell_km2, 6),
                                             round(hi_eff * n_px * cell_km2, 6)]},
                "withdrawn_on": "2026-09-16",
                "why": ("the amplitude screen is not a detector with an unknown "
                        "success probability: its rate is zero by construction for "
                        "every admissible input (METHODS 1), so there is no "
                        "sampling uncertainty for an interval to express"),
                "manuscript": ("Sec. VII: 'the amplitude screen is not such a "
                               "detector, since its firing rate is zero "
                               "algebraically for every admissible input, and an "
                               "earlier draft that attached one has been "
                               "corrected. No candidate-area estimate is "
                               "reported.'"),
                "what_stands_instead": ("the measured zero itself, the 234.68x "
                                        "margin between the threshold and the "
                                        "field's largest CPR_a, and the 40.21 % "
                                        "excluded / 59.79 % undecidable split"),
            },
            "still_consumed_by": ("backend/app/services/pdf_generator.py renders "
                                  "ci_km2 in the operator report; that surface has "
                                  "not been changed by this pass and is reported "
                                  "rather than edited"),
            "provenance": "MEASURED",
        },
        "published_reanalysis": {"rows": rows, "assumptions": ASSUMPTIONS,
                                 "floors_by_N": {str(n): round(floor_95(n), 4)
                                                 for n in ns}},
    }
    doc["derived"] = derived_closed_forms(area_px)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(doc, indent=2), encoding="utf-8")
    OUT_UI.parent.mkdir(parents=True, exist_ok=True)
    OUT_UI.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print(f"\n  wrote {Path(args.out).relative_to(BASE_DIR)}")
    print(f"  wrote {OUT_UI.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
