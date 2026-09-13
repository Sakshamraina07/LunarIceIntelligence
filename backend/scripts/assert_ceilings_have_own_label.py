"""
assert_ceilings_have_own_label.py -- G22. A ceiling comes from its own label.

    python backend/scripts/assert_ceilings_have_own_label.py [--inject WHICH]

WHY
---
`docs/enl_generality.json` gave its four S-band rows the ceilings 6.7732 and
13.4247, and the declared look counts 21 and 39, computed from the L-band label.
The VALUES were right -- L and S share the pass (`l_s_joint_mode = YES`) and
declare identical PRF, processed bandwidth and look count -- but nothing had ever
read the S-band label. A correct number stood on a provenance that did not exist.

**That is METHODS section 12's defect class**: a label field belonging to one
product used to bound a raster belonging to another. It is not made safe by the
two agreeing, because "they agree" is a fact nobody had checked either.

WHAT IT ASSERTS
  1. every row of enl_generality.json carries a predicted_ceiling that appears in
     enl_predictions.json for THAT date AND THAT band
  2. the declared look count on the row matches that same prediction entry
  3. the pre-registered and post-hoc groups are reported separately, never as one
     pooled span -- a blended figure lets post-hoc rows borrow the standing of
     committed ones
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
GEN = BASE_DIR / "docs" / "enl_generality.json"
PRED = BASE_DIR / "docs" / "enl_predictions.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

INJECTIONS = ("crossband", "pooled", "looks")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inject", choices=INJECTIONS)
    args = ap.parse_args()

    print("=" * 78)
    print("G22 — every ceiling is predicted from its own product's own label")
    print("=" * 78)

    for f in (GEN, PRED):
        if not f.is_file():
            print(f"  GATE FAIL — {f.relative_to(BASE_DIR)} is absent.")
            return 1
    gen = json.loads(GEN.read_text(encoding="utf-8"))
    pred = json.loads(PRED.read_text(encoding="utf-8"))

    # index the predictions by (date, band) -- the identity of a prediction
    index = {}
    for e in pred.get("predictions", []):
        d = e.get("declared") or {}
        key = (d.get("date_of_pass"), d.get("frequency_band"))
        if key[0] and key[1]:
            index[key] = e

    rows = gen.get("measurements", [])
    if args.inject == "crossband":
        print("  --inject crossband: an S row given the L label's ceiling\n")
        for r in rows:
            if r["band"] == "S":
                r["predicted_ceiling"] = index[(r["date_of_pass"], "L")]["predicted_ceiling"]
                r["band"] = "S"
                r["_forced"] = True
        # and remove the S predictions, so the ceiling has no S-band source
        index = {k: v for k, v in index.items() if k[1] != "S"}
    if args.inject == "looks":
        print("  --inject looks: a row declaring a look count its label does not\n")
        rows[0] = dict(rows[0])
        rows[0]["declared_azimuth_looks"] = "999"
    if args.inject == "pooled":
        print("  --inject pooled: one blended summary across both groups\n")
        gen = dict(gen)
        gen.pop("preregistered_test", None)
        gen.pop("post_hoc_extension", None)
        gen["summary"] = {"n_measurements": len(rows), "scope": "all bands pooled"}

    bad: list[str] = []
    print(f"  {'date':<12}{'band':<6}{'ch':<5}{'ceiling':>10}{'from label':>10}  source")
    for r in rows:
        key = (r.get("date_of_pass"), r.get("band"))
        e = index.get(key)
        if e is None:
            bad.append(f"{key[0]} band {key[1]}: the row carries ceiling "
                       f"{r.get('predicted_ceiling')} but enl_predictions.json has "
                       f"NO entry for that date AND band. The ceiling comes from a "
                       f"label belonging to another product.")
            print(f"  {str(key[0]):<12}{str(key[1]):<6}{r.get('channel',''):<5}"
                  f"{r.get('predicted_ceiling', 0):>10.4f}{'NONE':>10}  —")
            continue
        ok_c = abs(float(r["predicted_ceiling"]) - float(e["predicted_ceiling"])) < 1e-9
        ok_l = str(r.get("declared_azimuth_looks")) == str(
            (e.get("declared") or {}).get("azimuth_looks"))
        print(f"  {key[0]:<12}{key[1]:<6}{r.get('channel',''):<5}"
              f"{r['predicted_ceiling']:>10.4f}{'yes' if ok_c else 'NO':>10}  "
              f"{Path(e['label']).name}")
        if not ok_c:
            bad.append(f"{key[0]} band {key[1]}: ceiling {r['predicted_ceiling']} "
                       f"!= {e['predicted_ceiling']} predicted from its own label")
        if not ok_l:
            bad.append(f"{key[0]} band {key[1]}: row declares "
                       f"{r.get('declared_azimuth_looks')} azimuth looks; its label "
                       f"declares {(e.get('declared') or {}).get('azimuth_looks')}")

    # 3. the two groups stay separate
    if "preregistered_test" not in gen or "post_hoc_extension" not in gen:
        bad.append("enl_generality.json does not report the pre-registered and "
                   "post-hoc groups separately. A pooled span lets post-hoc rows "
                   "borrow the standing of committed ones.")
    else:
        print(f"\n  preregistered {gen['preregistered_test']['n_measurements']} rows, "
              f"post-hoc {gen['post_hoc_extension']['n_measurements']} rows, "
              f"reported separately")

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
    print("  GATE PASS — every ceiling is predicted from its own product's own")
    print("  label, every declared look count matches that label, and the")
    print("  pre-registered and post-hoc groups are reported separately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
