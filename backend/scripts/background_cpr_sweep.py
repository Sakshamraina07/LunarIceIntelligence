"""
background_cpr_sweep.py -- the false-positive rate is a function of the terrain.

    python backend/scripts/background_cpr_sweep.py

WHY
---
"17.79 % false positives" -- an UPPER BOUND, for the reason below -- is quoted
against a single assumed background, true CPR = 0.7. That choice is doing a great
deal of work and is easy to miss: the
rate at 0.3 is 0.12 %, and at 0.9 it is 39.23 %. Three hundred-fold, across a
range of ordinary lunar regolith.

Reporting one number invites the reader to treat the false-positive rate as a
property of the METHOD. It is a property of the method AND the terrain it is
pointed at, and a screen quoted without its assumed background is not a screen
with a stated error rate.

    FP(c) = 1 - F(1/c; 2N, 2N)   at the measured operating point N = 13.72

EVERY VALUE HERE IS AN UPPER BOUND, for the reason in METHODS 7.10: the rates
assume independent circular channels and the channels are correlated.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from scipy.stats import f as Fdist

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "background_cpr_sweep.json"
DET = BASE_DIR / "docs" / "detection_statistics.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

BACKGROUNDS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]


def main() -> int:
    det = json.loads(DET.read_text(encoding="utf-8"))
    n = float(det["effective_looks"]["screened_field"]["lh"])

    print("=" * 78)
    print(f"FALSE POSITIVES vs ASSUMED BACKGROUND CPR, at N = {n:g}")
    print("=" * 78)
    print(f"  N read from detection_statistics.json::effective_looks.screened_field.lh")
    print()
    print(f"  {'true CPR':>10}{'FP %':>10}")
    rows = []
    for c in BACKGROUNDS:
        fp = float((1.0 - Fdist.cdf(1.0 / c, 2 * n, 2 * n)) * 100.0)
        print(f"  {c:>10.1f}{fp:>10.2f}")
        rows.append({"true_cpr": c, "fp_percent": fp, "is_upper_bound": True})

    lo, hi = rows[0]["fp_percent"], rows[-1]["fp_percent"]
    print()
    print(f"  0.3 -> {lo:.2f} %   0.9 -> {hi:.2f} %   a factor of {hi / lo:,.0f}")
    print("  The false-positive rate is a property of the method AND the terrain")
    print("  it is pointed at. Quoted without its assumed background it is not a")
    print("  stated error rate.")

    OUT.write_text(json.dumps({
        "schema": "lunar-ice/background-cpr-sweep/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/background_cpr_sweep.py",
        "N": n,
        "N_read_from": "docs/detection_statistics.json::effective_looks.screened_field.lh",
        "formula": "FP(c) = 1 - F(1/c; 2N, 2N)",
        "all_values_are_upper_bounds": (
            "They assume independent circular channels; METHODS 7.10 measures "
            "|rho|^2 >= 0.3052 and correlation narrows the ratio."),
        "span_factor_0p3_to_0p9": hi / lo,
        "rows": rows,
    }, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
