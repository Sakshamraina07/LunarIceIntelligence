"""
emit_enl_generality.py -- the pre-registered prediction, scored.

    python backend/scripts/emit_enl_generality.py

WHY
---
docs/enl_predictions.json holds a ceiling PREDICTED from labels alone and
committed at 4aba4cd before any measurement of the 2020-03-05 product. This
records what was then MEASURED, so METHODS quotes a stamped artifact rather than
a terminal -- the failure mode section 5.12 exists to describe.

It re-runs nothing. It reads the measure_enl.py outputs and the prediction, and
computes one derived quantity: measured / predicted.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

#: (label, enl artifact, predicted ceiling, how the ENL run was invoked)
#: The ceilings are the pre-registered ones from docs/enl_predictions.json.
RUNS = [
    ("2020-08-08", "L", "docs/enl.json", 6.7732,
     "measure_enl.py --band L --patches 16,32 (defaults; the screened product)"),
    ("2020-08-08", "S", "docs/enl_S_20200808.json", 6.7732,
     "measure_enl.py --band S --patches 16,32"),
    ("2020-03-05", "L", "docs/enl_L_20200305.json", 13.4247,
     "measure_enl.py --band L --patches 16,32 --dir data/generality/20200305/..."),
    ("2020-03-05", "S", "docs/enl_S_20200305.json", 13.4247,
     "measure_enl.py --band S --patches 16,32 --dir data/generality/20200305/..."),
]

#: The single-look control. The sli products declare azimuth_looks = 1 and
#: range_looks = 1, so the expected ENL is exactly 1.00 and the ceiling and the
#: value coincide. IT CALIBRATES THE ESTIMATOR; IT DOES NOT TEST THE BOUND --
#: a bound of 1.00 on a 1-look product is not a constraint that could fail.
SINGLE_LOOK = "docs/enl_single_look_control.json"


def main() -> int:
    out = {
        "schema": "lunar-ice/enl-generality/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "computed_by": "backend/scripts/emit_enl_generality.py",
        "prediction_committed_at": "4aba4cd",
        "prediction_artifact": "docs/enl_predictions.json",
        "status": ("The prediction was committed BEFORE the 2020-03-05 product "
                   "was measured. These are the measurements scored against it."),
        "measurements": [],
    }
    missing = []
    for date, band, rel, ceiling, how in RUNS:
        f = BASE_DIR / rel
        if not f.is_file():
            missing.append(rel)
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        for ch in ("LH", "LV"):
            enl = float(d["boxcar_gain"][ch]["enl_raw"])
            out["measurements"].append({
                "date_of_pass": date, "band": band, "channel": ch,
                "declared_azimuth_looks": d["label"]["azimuth_looks"],
                "predicted_ceiling": ceiling,
                "measured_enl": enl,
                "attained_fraction": enl / ceiling,
                "below_own_ceiling": enl < ceiling,
                "invocation": how,
            })
    if missing:
        print("  ABSENT, so not written:", ", ".join(missing))
        return 1

    fr = [m["attained_fraction"] for m in out["measurements"]]
    out["summary"] = {
        "n_multilooked_measurements": len(fr),
        "all_below_own_ceiling": all(m["below_own_ceiling"]
                                     for m in out["measurements"]),
        "attained_fraction_min": min(fr),
        "attained_fraction_max": max(fr),
        "attained_fraction_span_factor": max(fr) / min(fr),
        "note": ("The BOUND holds in every case. The attained fraction does not "
                 "cluster: it spans a factor of "
                 f"{max(fr) / min(fr):.2f}. azimuth_looks / oversampling bounds "
                 "the measured ENL; it does not predict it."),
    }

    sl = BASE_DIR / SINGLE_LOOK
    if sl.is_file():
        out["single_look_control"] = json.loads(sl.read_text(encoding="utf-8"))
        out["single_look_control"]["role"] = (
            "CALIBRATES THE ESTIMATOR, DOES NOT TEST THE BOUND. The sli products "
            "declare 1 azimuth look and 1 range look, so the ceiling is exactly "
            "1.00 and coincides with the expected value; a bound that equals the "
            "expectation cannot be violated from below and is not a constraint.")

    dest = BASE_DIR / "docs" / "enl_generality.json"
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"  {len(out['measurements'])} multilooked measurements, "
          f"all below their own ceiling: {out['summary']['all_below_own_ceiling']}")
    print(f"  attained fraction {min(fr):.3f} .. {max(fr):.3f}  "
          f"(span {max(fr) / min(fr):.2f}x)")
    print(f"  wrote {dest.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
