"""
assert_wilson_on_effective_samples.py -- G23. No interval is reported on a
structural zero, and the sample count that survives it is a measurement.

    python backend/scripts/assert_wilson_on_effective_samples.py [--inject WHICH]

WHY, IN TWO CORRECTIONS
-----------------------
FIRST: `docs/detection_statistics.json` carried `ci_km2 = [0, 0.002401]`, a
score interval on 2,337,086 raw pixels. METHODS 7.9.1 measures the correlation
area of that same field at 61.42 px per independent sample, so the pixel count
overstated the sample size by about sixty-one and the interval came out about
sixty-one times too narrow. This gate was written to hold the corrected
interval, on 38 050 effective samples, in the headline slot.

SECOND, 2026-09-16, and it supersedes the first: there should be no interval in
that slot at all. An interval of that kind answers "a detector fired k of n
times; what is its rate?". This screen is not that detector -- METHODS 1 proves
its firing rate is zero ALGEBRAICALLY for every admissible input -- so the zero
carries no sampling uncertainty for an interval to express, and the manuscript
has withdrawn it. A gate that REQUIRED the interval would now be holding a
withdrawn claim in place, which is the failure mode this project names in
METHODS 0.

WHAT IT ASSERTS NOW
  1. no interval is reported: `reported_interval` is null and no `ci_km2` key
     sits in the candidate-area block where a reader would quote it
  2. the withdrawal is recorded, with its reason and its date, and BOTH
     superseded intervals are kept inside it -- a wrong number that vanishes
     cannot be audited and its correction cannot be checked
  3. n_effective == round(measured_pixels / correlation_area), and the
     correlation area is READ from cpr_significance.json rather than copied
  4. the effective-sample count still lands on 38 050, because that half of the
     first correction was right and stands as a measurement
"""
from __future__ import annotations

import argparse
import json
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

EXPECTED_N_EFFECTIVE = 38050
INJECTIONS = ("reportinterval", "wrongn", "droppedwithdrawal", "copiedarea",
              "unexplained")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inject", choices=INJECTIONS)
    args = ap.parse_args()

    print("=" * 78)
    print("G23 — a structural zero carries no interval, and the sample count is read")
    print("=" * 78)

    for f in (DET, SIG):
        if not f.is_file():
            print(f"  GATE FAIL — {f.relative_to(BASE_DIR)} is absent.")
            return 1
    det = json.loads(DET.read_text(encoding="utf-8"))
    sig = json.loads(SIG.read_text(encoding="utf-8"))
    ca = dict(det.get("candidate_area") or {})

    if args.inject == "reportinterval":
        print("  --inject reportinterval: the withdrawn interval put back in the "
              "headline slot\n")
        ca["ci_km2"] = list(ca["withdrawn_interval"]["values_km2"]["on_effective_samples"])
    elif args.inject == "wrongn":
        print("  --inject wrongn: n_effective off by the rounding\n")
        ca["n_effective"] = int(ca["n_effective"]) - 1
    elif args.inject == "droppedwithdrawal":
        print("  --inject droppedwithdrawal: the withdrawn interval deleted "
              "rather than labelled\n")
        ca.pop("withdrawn_interval", None)
    elif args.inject == "copiedarea":
        print("  --inject copiedarea: a second copy of the correlation area\n")
        ca["correlation_area_px"] = 61.5
    elif args.inject == "unexplained":
        print("  --inject unexplained: the withdrawal kept, its reason removed\n")
        ca["withdrawn_interval"] = dict(ca["withdrawn_interval"])
        ca["withdrawn_interval"].pop("why", None)

    bad: list[str] = []
    truth_area = float(sig["effective_samples"]["area_all_lags"])
    n_px = int(ca["measured_pixels"])
    area = float(ca.get("correlation_area_px", 0.0))
    n_eff = int(ca.get("n_effective", 0))
    w = ca.get("withdrawn_interval")

    print(f"  correlation area   {area!r}")
    print(f"  cpr_significance   {truth_area!r}")
    print(f"  measured pixels    {n_px:,}")
    print(f"  n_effective        {n_eff:,}   round -> {round(n_px / truth_area):,}")
    print(f"  candidate area     {ca.get('area_km2')} km2 from {ca.get('pixels')} pixels")
    print(f"  reported interval  {ca.get('reported_interval', 'KEY ABSENT')}")
    print(f"  withdrawn interval {'present' if w else 'ABSENT'}"
          + (f", {w.get('withdrawn_on')}" if w else ""))

    # 1. nothing in this block may read as a reported interval
    leaked = [k for k in ca if k.startswith("ci_km2")]
    if leaked:
        bad.append(f"the candidate-area block still carries {leaked}. A key a "
                   f"reader would quote is a reported interval whatever the "
                   f"surrounding prose says; the withdrawn values belong inside "
                   f"withdrawn_interval.")
    if ca.get("reported_interval", "missing") is not None:
        bad.append("reported_interval must be present and null: the absence of an "
                   "interval is a decision, and a decision that is merely implicit "
                   "is indistinguishable from an oversight.")

    # 2. the withdrawal is recorded with its reason and both superseded values
    if not w:
        bad.append("withdrawn_interval is absent. The superseded computation is "
                   "kept and labelled, not deleted: a wrong number that vanishes "
                   "cannot be audited and its correction cannot be checked.")
    else:
        for field in ("why", "withdrawn_on", "values_km2"):
            if not w.get(field):
                bad.append(f"withdrawn_interval has no {field}")
        vals = w.get("values_km2") or {}
        for key in ("on_raw_pixels", "on_effective_samples"):
            if key not in vals:
                bad.append(f"withdrawn_interval.values_km2 has no {key}: both "
                           f"superseded intervals are part of the record")

    # 3. the correlation area is READ, not re-transcribed
    if abs(area - truth_area) > 1e-12:
        bad.append(f"correlation_area_px {area} is not cpr_significance.json's "
                   f"{truth_area}. 7.9.1 and 7.10 once carried 61.5 and 61.42 for "
                   f"this one quantity; a third copy is how that happens again.")
    if n_eff != round(n_px / truth_area):
        bad.append(f"n_effective {n_eff} != round({n_px} / {truth_area}) = "
                   f"{round(n_px / truth_area)}")

    # 4. the count that survived the first correction
    if n_eff != EXPECTED_N_EFFECTIVE:
        bad.append(f"n_effective is {n_eff}, not {EXPECTED_N_EFFECTIVE}")

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
    print("  GATE PASS — no interval is reported on the candidate area, the")
    print("  withdrawal is on the record with its reason and both superseded")
    print("  values, and the 38 050 effective samples follow from the measured")
    print("  correlation area rather than from a second copy of it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
