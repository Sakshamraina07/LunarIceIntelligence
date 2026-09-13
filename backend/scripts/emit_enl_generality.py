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
    ("2020-08-08", "L", "docs/enl.json",
     "measure_enl.py --band L --patches 16,32 (defaults; the screened product)"),
    ("2020-08-08", "S", "docs/enl_S_20200808.json",
     "measure_enl.py --band S --patches 16,32"),
    ("2020-03-05", "L", "docs/enl_L_20200305.json",
     "measure_enl.py --band L --patches 16,32 --dir data/generality/20200305/..."),
    ("2020-03-05", "S", "docs/enl_S_20200305.json",
     "measure_enl.py --band S --patches 16,32 --dir data/generality/20200305/..."),
]

#: WHICH ROWS THE PRE-REGISTRATION ACTUALLY COVERED. 4aba4cd predicted the
#: L-band ceilings only. The S-band rows were measured afterwards, with the
#: L-band result already known, so they are a POST-HOC EXTENSION and are never
#: pooled with the pre-registered four. A blended "8 of 8" would let four
#: after-the-fact measurements borrow the standing of four committed ones.
PREREGISTERED_BANDS = {"L"}


def ceiling_for(preds: dict, date: str, band: str):
    """The ceiling predicted from THIS date's and THIS band's own label.

    Keyed on both, because enl_generality.json once gave the S-band rows the
    L-band ceiling. The two agree -- L and S share the pass -- but nothing had
    read the S label, so a correct number rested on a provenance that did not
    exist. That is METHODS section 12's defect class.
    """
    for e in preds.get("predictions", []):
        d = e.get("declared") or {}
        if d.get("date_of_pass") == date and d.get("frequency_band") == band:
            return e.get("predicted_ceiling"), e.get("label"), d.get("azimuth_looks")
    return None, None, None


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
    preds_path = BASE_DIR / "docs" / "enl_predictions.json"
    if not preds_path.is_file():
        print("  docs/enl_predictions.json is absent; nothing to score against.")
        return 1
    preds = json.loads(preds_path.read_text(encoding="utf-8"))

    missing = []
    for date, band, rel, how in RUNS:
        f = BASE_DIR / rel
        if not f.is_file():
            missing.append(rel)
            continue
        ceiling, label, declared_looks = ceiling_for(preds, date, band)
        if ceiling is None:
            missing.append(f"no prediction for {date} band {band} in "
                           f"docs/enl_predictions.json")
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        for ch in ("LH", "LV"):
            enl = float(d["boxcar_gain"][ch]["enl_raw"])
            out["measurements"].append({
                "date_of_pass": date, "band": band, "channel": ch,
                "declared_azimuth_looks": declared_looks,
                "predicted_ceiling": ceiling,
                "ceiling_from_label": label,
                "preregistered": band in PREREGISTERED_BANDS,
                "measured_enl": enl,
                "attained_fraction": enl / ceiling,
                "below_own_ceiling": enl < ceiling,
                "invocation": how,
            })
    if missing:
        print("  ABSENT, so not written:", "; ".join(missing))
        return 1

    def summarise(rows, label):
        f = [m["attained_fraction"] for m in rows]
        return {
            "scope": label,
            "n_measurements": len(f),
            "all_below_own_ceiling": all(m["below_own_ceiling"] for m in rows),
            "attained_fraction_min": min(f),
            "attained_fraction_max": max(f),
            "attained_fraction_span_factor": max(f) / min(f),
        }

    pre = [m for m in out["measurements"] if m["preregistered"]]
    post = [m for m in out["measurements"] if not m["preregistered"]]
    out["preregistered_test"] = summarise(
        pre, "L-band only; the bands 4aba4cd actually predicted")
    out["post_hoc_extension"] = summarise(
        post, "S-band; measured AFTER the L-band result was known")
    out["summary_note"] = (
        "REPORTED SEPARATELY, NEVER POOLED. The pre-registration predicted the "
        "L-band ceilings. The S-band rows were measured with the L-band outcome "
        "already known, so pooling them into one span would let four post-hoc "
        "measurements borrow the standing of four committed ones. The BOUND holds "
        "in every row of both groups; the attained fraction clusters in neither.")

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
    for key in ("preregistered_test", "post_hoc_extension"):
        b = out[key]
        print(f"  {key:<22} {b['n_measurements']} rows, all below own ceiling: "
              f"{b['all_below_own_ceiling']}, attained "
              f"{b['attained_fraction_min']:.3f}..{b['attained_fraction_max']:.3f} "
              f"(span {b['attained_fraction_span_factor']:.2f}x)")
    print(f"  wrote {dest.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
