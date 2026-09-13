"""
table5_sensitivity.py -- how the floor and the false-positive rate move with N.

    python backend/scripts/table5_sensitivity.py

WHY
---
Every detection figure in this work is conditioned on one measured quantity: the
effective look count of the screened field, N = 13.72. That number is a
measurement and therefore has a range. A table of consequences computed at a
single N invites the reader to treat it as exact.

This computes the same three consequences across the plausible span of the raw
ENL, so the sensitivity is visible rather than asserted:

    N     = raw x 13.72 / 5.83          the screened field scales with the raw
    floor = F^-1(0.95; 2N, 2N)          the 95 % speckle floor on the ratio
    FP    = 1 - F(1/0.7; 2N, 2N)        false positives at true CPR 0.7

The scaling is the measured boxcar gain: the 5x5 average lifted the raw 5.83 to
13.72, and that ratio is applied to every raw value rather than re-measuring the
gain at each one.

ALL FALSE-POSITIVE RATES HERE ARE UPPER BOUNDS. They assume the two circular
channels are independent; METHODS 7.10 shows they are correlated at
|rho|^2 >= 0.3052, and correlation between numerator and denominator narrows a
ratio's distribution.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from scipy.stats import f as Fdist

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "table5_sensitivity.json"
DET = BASE_DIR / "docs" / "detection_statistics.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

#: The raw ENLs spanned. 5.83 is the measured LH value; the others bracket it.
RAW_VALUES = [2.64, 5.30, 5.83, 6.22]
TRUE_CPR = 0.7


def main() -> int:
    det = json.loads(DET.read_text(encoding="utf-8"))
    eff = det["effective_looks"]
    raw_ref = float(eff["raw_product"]["lh"])        # 5.83
    screened_ref = float(eff["screened_field"]["lh"])  # 13.72
    scale = screened_ref / raw_ref

    print("=" * 78)
    print("TABLE V SENSITIVITY — floor and FP across the plausible ENL span")
    print("=" * 78)
    print(f"  scaling read from detection_statistics.json: "
          f"{screened_ref:g} / {raw_ref:g} = {scale:.6f}")
    print(f"  FP is evaluated at true CPR = {TRUE_CPR:g}; every FP is an UPPER BOUND")
    print()
    print(f"  {'raw ENL':>9}{'N':>9}{'floor':>9}{'FP %':>9}")

    rows = []
    for raw in RAW_VALUES:
        n = raw * scale
        floor = float(Fdist.ppf(0.95, 2 * n, 2 * n))
        fp = float((1.0 - Fdist.cdf(1.0 / TRUE_CPR, 2 * n, 2 * n)) * 100.0)
        print(f"  {raw:>9.2f}{n:>9.1f}{floor:>9.2f}{fp:>9.1f}")
        rows.append({"raw_enl": raw, "N": n, "floor_95": floor,
                     "fp_percent_at_cpr_0p7": fp,
                     "fp_is_upper_bound": True})

    OUT.write_text(json.dumps({
        "schema": "lunar-ice/table5-sensitivity/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/table5_sensitivity.py",
        "scaling": {"raw_reference": raw_ref, "screened_reference": screened_ref,
                    "factor": scale,
                    "read_from": "docs/detection_statistics.json::effective_looks"},
        "true_cpr_for_fp": TRUE_CPR,
        "formulas": {
            "N": "raw x screened_reference / raw_reference",
            "floor": "F^-1(0.95; 2N, 2N)",
            "fp": "1 - F(1/0.7; 2N, 2N)",
        },
        "all_fp_are_upper_bounds": (
            "They assume independent circular channels. METHODS 7.10 measures "
            "|rho|^2 >= 0.3052 from Putrevu et al. 2023's own dispersion, and "
            "correlation between numerator and denominator narrows the ratio."),
        "rows": rows,
    }, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
