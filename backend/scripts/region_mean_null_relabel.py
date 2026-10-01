"""
region_mean_null_relabel.py -- add the large-field achieved N to the correlated rows
of docs/region_mean_null.json. (V22 work order, D)

    python backend/scripts/region_mean_null_relabel.py   # after n_sensitivity_region.py

region_mean_null.correlated picks the looks per channel L so that the single-cell
log-ratio N, calibrated on four realizations of the region's own bounding box, is
nearest the target. That calibration scatters (n_sensitivity_calcheck.json: 40
repetitions at L = 19 read 57.2 +- 10.2 looks, range 38.9-91.3, against 53.1-53.6 on
150 000 cells), so the stored `achieved_log_ratio_N` of a row can be 30 % off its L's
true N: the 260-cell "N = 80" row used L = 19, N = 53.3 on the large field, and its
stored 75.9 is the small-box reading.

NOTHING STORED IS CHANGED. Each correlated row gains
  achieved_log_ratio_N_large_field   the N of its `looks_per_channel` on the large field
                                     (n_sensitivity_region.json::calibration; four 200 x 200
                                     realizations, about 150 000 cells, a few per cent),
  achieved_log_ratio_N_large_field_source,
and the artifact gains a top-level `achieved_N_labels` note. The simulated rates of the rows
are untouched (they are a function of L, not of the calibration). Idempotent. Draws nothing.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

BASE_DIR = Path(__file__).resolve().parents[2]
RMN = BASE_DIR / "docs" / "region_mean_null.json"
NSR = BASE_DIR / "docs" / "n_sensitivity_region.json"
CAL = BASE_DIR / "docs" / "n_sensitivity_calcheck.json"


def main() -> int:
    doc = json.loads(RMN.read_text(encoding="utf-8"))
    nsr = json.loads(NSR.read_text(encoding="utf-8"))
    cal = nsr["calibration"]["260"]            # identical for both sizes (one calibration)
    n = 0
    for pop, byN in doc["results"].items():
        for nk, bysz in byN.items():
            for szk, x in bysz.items():
                c = x["correlated"]
                L = c.get("looks_per_channel")
                if L is None:
                    continue
                c["achieved_log_ratio_N_large_field"] = cal[str(L)]
                c["achieved_log_ratio_N_large_field_source"] = (
                    f"n_sensitivity_region.json::calibration.260.{L} (4 x 200 x 200 realizations); check: n_sensitivity_calcheck.json")
                n += 1
    doc["achieved_N_labels"] = {
        "note": ("`achieved_log_ratio_N` is the reading of a calibration on four realizations of the region's own bounding box "
                 "and is imprecise (about +-10-15 %, biased high by about 8 % at L = 19; n_sensitivity_calcheck.json). "
                 "`achieved_log_ratio_N_large_field` is the N of the same looks-per-channel on four 200 x 200 realizations. "
                 "The stored rates are unchanged; use the large-field label as the look count of a row."),
        "relabelled_by": "backend/scripts/region_mean_null_relabel.py",
        "relabelled_utc": datetime.now(timezone.utc).isoformat(),
        "rows_relabelled": n}
    RMN.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    for pop in ("CPR 0.7 DOP 0.176",):
        for nk in doc["results"][pop]:
            for szk in ("cells260", "cells3647"):
                c = doc["results"][pop][nk][szk]["correlated"]
                print(f"  {pop} {nk} {szk}: L {c['looks_per_channel']}  stored N {c['achieved_log_ratio_N']:.1f}  large-field N {c['achieved_log_ratio_N_large_field']:.1f}")
    print(f"  relabelled {n} correlated rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
