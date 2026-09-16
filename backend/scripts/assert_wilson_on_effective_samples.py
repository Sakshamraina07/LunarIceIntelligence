"""
assert_wilson_on_effective_samples.py -- G23. The interval counts samples, not pixels.

    python backend/scripts/assert_wilson_on_effective_samples.py [--inject WHICH]

WHY
---
`docs/detection_statistics.json` carried `ci_km2 = [0, 0.002401]`, a Wilson
interval on 2,337,086 raw pixels. METHODS 7.9.1 measures the correlation area of
that same field at 61.42 px per independent sample, so the pixel count overstates
the sample size by about sixty-one, and the interval came out about sixty-one
times too narrow.

**A confidence interval that is too narrow is worse than no interval.** It states
a precision the data does not have, and it does so on the single number this
project exists to report honestly: the measured zero. The bare zero was never the
risk; the risk was a zero wearing a tight error bar.

WHAT IT ASSERTS
  1. ci_km2 is the EFFECTIVE-sample interval, not the raw-pixel one
  2. its upper bound rounds to 0.147 km2 at three decimals
  3. n_effective == round(measured_pixels / correlation_area), and the
     correlation area matches cpr_significance.json rather than a second copy
  4. the raw-pixel interval is retained and labelled, not deleted -- a
     superseded computation that vanishes cannot be audited
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DET = BASE_DIR / "docs" / "detection_statistics.json"
SIG = BASE_DIR / "docs" / "cpr_significance.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

EXPECTED_UPPER_3DP = 0.147
INJECTIONS = ("rawpixels", "wrongn", "droppedraw", "copiedarea")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inject", choices=INJECTIONS)
    args = ap.parse_args()

    print("=" * 78)
    print("G23 — the candidate-area interval is taken on effective samples")
    print("=" * 78)

    for f in (DET, SIG):
        if not f.is_file():
            print(f"  GATE FAIL — {f.relative_to(BASE_DIR)} is absent.")
            return 1
    det = json.loads(DET.read_text(encoding="utf-8"))
    sig = json.loads(SIG.read_text(encoding="utf-8"))
    ca = dict(det.get("candidate_area") or {})

    if args.inject == "rawpixels":
        print("  --inject rawpixels: headline reverted to the raw-pixel interval\n")
        ca["ci_km2"] = list(ca["ci_km2_raw_pixels"])
    elif args.inject == "wrongn":
        print("  --inject wrongn: n_effective off by the rounding\n")
        ca["n_effective"] = int(ca["n_effective"]) - 1
    elif args.inject == "droppedraw":
        print("  --inject droppedraw: the superseded interval deleted\n")
        ca.pop("ci_km2_raw_pixels", None)
    elif args.inject == "copiedarea":
        print("  --inject copiedarea: a second copy of the correlation area\n")
        ca["correlation_area_px"] = 61.5

    bad: list[str] = []
    truth_area = float(sig["effective_samples"]["area_all_lags"])
    n_px = int(ca["measured_pixels"])
    area = float(ca.get("correlation_area_px", 0.0))
    n_eff = int(ca.get("n_effective", 0))
    hi = float(ca["ci_km2"][1])
    hi_eff = float(ca["ci_km2_effective"][1])

    print(f"  correlation area   {area!r}")
    print(f"  cpr_significance   {truth_area!r}")
    print(f"  measured pixels    {n_px:,}")
    print(f"  n_effective        {n_eff:,}   round -> {round(n_px / truth_area):,}")
    print(f"  ci_km2             [{ca['ci_km2'][0]}, {hi}]")
    print(f"  ci_km2_raw_pixels  {ca.get('ci_km2_raw_pixels', 'ABSENT')}")

    # 3. the correlation area is READ, not re-transcribed
    if abs(area - truth_area) > 1e-12:
        bad.append(f"correlation_area_px {area} is not cpr_significance.json's "
                   f"{truth_area}. 7.9.1 and 7.10 once carried 61.5 and 61.42 for "
                   f"this one quantity; a third copy is how that happens again.")
    if n_eff != round(n_px / truth_area):
        bad.append(f"n_effective {n_eff} != round({n_px} / {truth_area}) = "
                   f"{round(n_px / truth_area)}")

    # 1 + 2. the headline is the effective interval and lands on 0.147
    if abs(hi - hi_eff) > 1e-12:
        bad.append(f"ci_km2 upper {hi} is not ci_km2_effective {hi_eff}; the "
                   f"headline interval is not the one taken on effective samples")
    if round(hi, 3) != EXPECTED_UPPER_3DP:
        bad.append(f"ci_km2 upper rounds to {round(hi, 3)} at three decimals, "
                   f"not {EXPECTED_UPPER_3DP}")

    # 4. the superseded computation is retained and labelled
    if "ci_km2_raw_pixels" not in ca:
        bad.append("ci_km2_raw_pixels is absent. The superseded computation is "
                   "kept and labelled, not deleted: a wrong number that vanishes "
                   "cannot be audited and its correction cannot be checked.")
    elif "note" not in ca or "too narrow" not in str(ca.get("note", "")).lower():
        bad.append("the raw-pixel interval is retained without a note saying why "
                   "it is superseded")

    print()
    if args.inject:
        if bad:
            print(f"  INJECTION CAUGHT ({args.inject}). The gate works.")
            for b in bad:
                print(f"    {b}")
            return 0
        print(f"  INJECTION NOT CAUGHT ({args.inject}).")
        return 1

    if bad:
        print("  GATE FAIL")
        for b in bad:
            print(f"    - {b}")
        return 1
    print("  GATE PASS — the interval is taken on effective samples, its upper")
    print("  bound is 0.147 km2, the sample count follows from the measured")
    print("  correlation area, and the superseded interval is kept and labelled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
