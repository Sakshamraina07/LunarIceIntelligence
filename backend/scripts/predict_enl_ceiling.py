"""
predict_enl_ceiling.py -- the reference value the label implies for the ENL.

    python backend/scripts/predict_enl_ceiling.py LABEL.xml [LABEL2.xml ...]
                                                 [--out docs/enl_predictions.json]

NOT A BOUND, AND THE NAME IS A CORRECTION DATED 2026-09-16
----------------------------------------------------------
This script and its artifact key were written as `ceiling`, and the word was
wrong. 21 / 3.10 = 6.77 is the ASYMPTOTIC time-bandwidth product; the exact
finite-sample participation ratio for the same band is 7.34, and a mildly
shaped spectrum of the same support gives 7.38 -- above both. Nothing here is
an upper bound the ENL cannot exceed. It is a REFERENCE VALUE for a
multilooking scheme, and the key name is kept only because other artifacts
address it by name (docs/slepian_ceiling.json carries the exact companions).

WHY, AND WHY IT IS RUN BEFORE THE MEASUREMENT
---------------------------------------------
METHODS 7.3 measured 5.3-6.5 effective looks in a product whose label declares
21, and derived a reference value of 6.77 from the label's own numbers:

    oversampling      = PRF / total_processed_azimuth_bandwidth
    reference value   = azimuth_looks / oversampling

Azimuth looks are formed by splitting the processed Doppler bandwidth. When the
PRF exceeds that bandwidth the looks overlap in frequency, so they are not
independent, and the achievable ENL is the declared look count divided by the
oversampling factor. For the 2020-08-08 product: 3321.641156 / 1071.335975 =
3.1006, and 21 / 3.1006 = 6.77.

THIS SCRIPT COMPUTES THAT FROM THE LABEL AND NOTHING ELSE. It opens no raster.
It is run, and its output committed, BEFORE measure_enl.py touches a new
product, so the prediction cannot be adjusted after seeing the answer. That
ordering is the whole point: a reference value derived after the measurement is
a description of the measurement, not a test of it.

The prediction can be wrong. That is what makes it worth writing down.
"""
from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

#: Every field this prediction depends on. Read by LEAF NAME, because the two
#: label generations nest them differently and a path-based read returns a false
#: negative that looks like an absent field.
NEEDED = ("azimuth_looks", "range_looks", "pulse_repetition_frequency",
          "total_processed_azimuth_bandwidth", "azimuth_look_bandwidth",
          "frequency_band", "product_type", "processing_level", "imaging_mode",
          "num_polarizations", "calibration_constant", "output_pixel_spacing",
          "look_angle", "incidence_angle", "spacecraft_altitude",
          "pulse_bandwidth", "centre_latitude", "centre_longitude",
          "date_of_pass", "no_scans", "no_pixels")


def read_label(path: Path) -> dict:
    out: dict = {}
    def walk(el):
        tag = el.tag.split("}")[-1]
        kids = list(el)
        if not kids:
            out.setdefault(tag, []).append((el.text or "").strip())
        for k in kids:
            walk(k)
    walk(ET.parse(path).getroot())
    return {k: (v[0] if len(set(v)) == 1 else sorted(set(v))) for k, v in out.items()}


def predict(label: dict) -> dict:
    """The ceiling, or an explicit absence with its reason. Never a default."""
    missing = [f for f in ("azimuth_looks", "pulse_repetition_frequency",
                           "total_processed_azimuth_bandwidth")
               if f not in label]
    if missing:
        return {"predicted_ceiling": None, "oversampling": None,
                "reason_absent": f"the label carries no {', '.join(missing)}. "
                                 f"A raw (L0B) product has not formed looks yet, "
                                 f"so there is no ceiling to predict -- this is "
                                 f"an absent state, not a zero."}
    looks = float(label["azimuth_looks"])
    prf = float(label["pulse_repetition_frequency"])
    bw = float(label["total_processed_azimuth_bandwidth"])
    over = prf / bw
    return {"azimuth_looks": looks, "prf_hz": prf,
            "total_processed_azimuth_bandwidth_hz": bw,
            "oversampling": over, "predicted_ceiling": looks / over,
            "formula": "ceiling = azimuth_looks / (PRF / processed_azimuth_bandwidth)",
            "why": ("looks are formed by splitting the processed Doppler "
                    "bandwidth; when PRF exceeds it the looks overlap in "
                    "frequency and are not independent")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("labels", nargs="+")
    ap.add_argument("--out", default="docs/enl_predictions.json")
    args = ap.parse_args()

    print("=" * 78)
    print("PREDICTED ENL CEILING — from the label alone, before any measurement")
    print("=" * 78)

    entries = []
    for spec in args.labels:
        p = Path(spec)
        if not p.is_absolute():
            p = BASE_DIR / spec
        lab = read_label(p)
        pred = predict(lab)
        rec = {"label": p.relative_to(BASE_DIR).as_posix()
                        if str(p).startswith(str(BASE_DIR)) else str(p),
               "declared": {k: lab.get(k) for k in NEEDED if k in lab},
               **pred}
        entries.append(rec)
        print(f"\n  {p.name}")
        print(f"    product_type       {lab.get('product_type')}   "
              f"band {lab.get('frequency_band')}   "
              f"pol {lab.get('polarization', lab.get('num_polarizations'))}")
        if pred["predicted_ceiling"] is None:
            print(f"    PREDICTION ABSENT  {pred['reason_absent']}")
            continue
        print(f"    azimuth_looks      {pred['azimuth_looks']:g}")
        print(f"    PRF                {pred['prf_hz']:.6f} Hz")
        print(f"    processed az bw    {pred['total_processed_azimuth_bandwidth_hz']:.6f} Hz")
        print(f"    oversampling       {pred['oversampling']:.6f}")
        print(f"    PREDICTED CEILING  {pred['predicted_ceiling']:.4f}")

    doc = {
        "schema": "lunar-ice/enl-prediction/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "computed_by": "backend/scripts/predict_enl_ceiling.py",
        "status": "PRE-REGISTERED PREDICTION — committed before measure_enl.py "
                  "was run on any product listed here that was not already "
                  "measured. Reads labels only; opens no raster.",
        # BAND IS PART OF THE IDENTITY OF A PREDICTION, NOT A DETAIL.
        # enl_generality.json once carried S-band rows bounded by ceilings
        # computed from the L-band label, on the grounds that the two agree.
        # They do agree -- L and S share the pass (l_s_joint_mode = YES) and
        # declare identical PRF, bandwidth and looks -- but nothing had READ the
        # S label, so a correct number stood on a provenance that did not exist.
        # That is section 12's defect class: a label field from one product
        # bounding a raster from another. Each entry now records its own band.
        "keyed_by": ["date_of_pass", "frequency_band"],
        "predictions": entries,
    }
    out = BASE_DIR / args.out
    out.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print(f"\n  wrote {out.relative_to(BASE_DIR)}")
    print("\n  This is a PREDICTION. It is committed before the measurement so it")
    print("  cannot be adjusted afterwards. It is allowed to be wrong.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
