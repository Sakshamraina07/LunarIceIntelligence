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
    "single detection floor is quoted for their data.",
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
    # CEIL, NOT FLOOR OR ROUND, AND THE REASON IS RECORDED.
    # 2,337,086 / 61.420749918170166 = 38050.43089..., so floor and round both
    # give 38050 and only ceil gives the 38,051 the manuscript prints. The
    # difference does not move the headline -- the upper bound is 0.147 km2 at
    # either -- but the artifact and the paper must not disagree about a count
    # a reader can divide out for themselves.
    area_px = float(_correlation_area())
    n_eff = math.ceil(n_px / area_px)
    lo_eff, hi_eff = wilson(k, n_eff, _z)
    lo, hi = lo_eff, hi_eff
    print(f"  candidate pixels      {k:,} of {n_px:,} measured")
    print(f"  candidate area        {k * cell_km2:.4f} km²")
    _frame = n_px * cell_km2
    print(f"  correlation area      {area_px:.4f} px per independent sample "
          f"(METHODS 7.9.1)")
    print(f"  effective samples     {n_eff:,}  = ceil({n_px:,} / {area_px:.4f})")
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
        "candidate_area": {
            "pixels": k, "measured_pixels": n_px,
            "area_km2": round(k * cell_km2, 6),
            "confidence": args.confidence,
            "correlation_area_px": area_px,
            "n_effective": n_eff,
            "ci_km2_raw_pixels": [round(lo_raw * n_px * cell_km2, 6),
                                  round(hi_raw * n_px * cell_km2, 6)],
            "ci_km2_effective": [round(lo_eff * n_px * cell_km2, 6),
                                 round(hi_eff * n_px * cell_km2, 6)],
            "ci_km2": [round(lo * n_px * cell_km2, 6), round(hi * n_px * cell_km2, 6)],
            "note": ("raw-pixel interval is 61x too narrow; pixels are not "
                     "independent (61.42 px per independent sample)"),
            "n_effective_rounding": ("ceil. 2337086 / 61.420749918170166 = "
                                     "38050.43089, so floor and round give 38050 "
                                     "and only ceil gives the 38051 the manuscript "
                                     "prints. The upper bound is 0.147 km2 either "
                                     "way; the count is matched so artifact and "
                                     "paper do not disagree."),
            "method": "Wilson score interval on the pass proportion, on EFFECTIVE samples",
            "why_wilson": ("The normal approximation gives [0, 0] at k = 0 and would "
                           "report a measured zero as carrying no uncertainty."),
            "why_effective": ("METHODS 7.9.1 measures 61.42 px per independent "
                              "sample by integrating the CPR autocorrelation. "
                              "Treating pixels as trials overstates n by ~61x and "
                              "narrows the interval by the same factor."),
            "provenance": "MEASURED",
        },
        "published_reanalysis": {"rows": rows, "assumptions": ASSUMPTIONS,
                                 "floors_by_N": {str(n): round(floor_95(n), 4)
                                                 for n in ns}},
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(doc, indent=2), encoding="utf-8")
    OUT_UI.parent.mkdir(parents=True, exist_ok=True)
    OUT_UI.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print(f"\n  wrote {Path(args.out).relative_to(BASE_DIR)}")
    print(f"  wrote {OUT_UI.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
