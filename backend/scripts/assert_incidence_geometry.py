"""
assert_incidence_geometry.py -- G12/G13. One incidence field, one look count.

    python backend/scripts/assert_incidence_geometry.py [--inject-g12|--inject-g13]

G12 — INCIDENCE EXCEEDS THE LOOK ANGLE, EVERYWHERE
--------------------------------------------------
On a convex body,

    sin(theta_inc) = ((R + h) / R) sin(eta)

with (R+h)/R > 1, so theta_inc > eta at every pixel. It is an identity, not a
tolerance: NO CORRECT IMPLEMENTATION CAN VIOLATE IT, which is exactly what makes
it a good gate.

This project shipped a Bragg-domain criterion built on the product's incidence
raster, of which 80.53 % of the values over the valid mask sit BELOW the label's
own look angle of 19.9979 deg. The criterion reported an ellipsoid median of
14.44 deg, a local median of 17.73 deg, and that 62.58 % of the swath falls below
20 deg -- all from a field that cannot be an incidence angle. Nothing checked it,
because nothing had ever needed to.

The gate asserts BOTH halves:
  * the audit's identity check on the raster, and
  * that no consumer uses a field which fails it -- concretely, that the
    Bragg criterion is WITHHELD for as long as the audit says the field is not
    an incidence angle. A criterion reporting numbers from a rejected field is
    the failure this exists to stop.

G13 — ONE CPR FIELD, ONE LOOK COUNT
-----------------------------------
There is one CPR raster and it has one ENL. The screening threshold is applied to
`cpr_native.tif`, which `process_real_sar_pipeline.py` forms from the 5x5
BOXCAR-SMOOTHED sigma0 -- so the applicable ENL is the smoothed field's 13.72,
not the raw product's 5.83.

METHODS 7.7's narrative read the table at N ~ 5 while `detection_statistics.py`
published its floor at 13.72. The artifact was right and the prose quoting it was
wrong, which is worse than a wrong computation because the number looked
corroborated. The gate asserts every consumer reads the same ENL from the same
place.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
ANALYSIS = BASE_DIR / "frontend" / "public" / "analysis"
DOCS = BASE_DIR / "docs"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def hr(t: str) -> None:
    print("\n" + "=" * 78 + "\n" + t + "\n" + "=" * 78)


def g12(inject: bool) -> list[str]:
    hr("G12 — incidence exceeds the look angle, everywhere")
    bad: list[str] = []
    audit_p = DOCS / "incidence_audit.json"
    if not audit_p.exists():
        return ["docs/incidence_audit.json is absent: the identity has not been "
                "checked on this host. Run backend/scripts/incidence_audit.py."]
    a = json.loads(audit_p.read_text(encoding="utf-8"))
    lg = a["label_geometry"]
    frac = a["test_1_magnitude"]["fraction_below_look_angle"]
    if inject:
        frac = 0.0                       # pretend the raster passed
        a = {**a, "is_ellipsoid_incidence": True}
        print("  --inject-g12: the audit is overridden to claim the field is valid,")
        print("  while the criterion artifact still reports it withheld.\n")

    print(f"  label: look angle {lg['look_angle_deg']:.4f} deg, altitude "
          f"{lg['spacecraft_altitude_m']:,.0f} m, (R+h)/R = {lg['radius_ratio']:.6f}")
    print(f"  identity requires incidence >= "
          f"{lg['incidence_required_by_look_angle_deg']:.4f} deg at every pixel")
    print(f"  raster: {frac * 100:.2f} % of valid pixels below the look angle")
    if lg["label_gives_same_value_for_both"]:
        print("  NOTE: the label gives the SAME value for look_angle and "
              "incidence_angle,")
        print("  which cannot be true on a convex body. That is the product's, not ours.")

    field_ok = frac < 1e-9
    print(f"  -> the field {'satisfies' if field_ok else 'VIOLATES'} the identity")

    # Half two: no consumer may use a field that fails.
    mask_p = DOCS / "incidence_mask.json"
    available = None
    if mask_p.exists():
        available = bool(json.loads(mask_p.read_text(encoding="utf-8"))
                         .get("available", True))
        print(f"  Bragg criterion artifact: available = {available}")
    crit_measured = None
    fa = ANALYSIS / "faustini.json"
    if fa.exists():
        for e in json.loads(fa.read_text(encoding="utf-8"))["evidence"]:
            if e["criterion"] == "local_incidence_in_bragg_domain":
                crit_measured = e["measured"]
                print(f"  criterion row in the analysis: measured = {crit_measured}, "
                      f"provenance = {e['provenance']}")

    if not field_ok:
        if available:
            bad.append("the incidence field violates the geometric identity and the "
                       "Bragg criterion is still marked available")
        if crit_measured is not None:
            bad.append(f"the incidence field violates the identity but the criterion "
                       f"row reports a measured value of {crit_measured}")
    else:
        if available is False:
            bad.append("the field satisfies the identity but the criterion is "
                       "withheld — a withheld criterion needs a reason that is "
                       "still true")
    if not bad:
        print("  PASS — no consumer uses a field that violates the identity.")
    return bad


def g13(inject: bool) -> list[str]:
    hr("G13 — one CPR field, one look count")
    bad: list[str] = []

    # Which field does the threshold touch? Read the pipeline, do not infer.
    pipe = (BASE_DIR / "backend" / "scripts" / "process_real_sar_pipeline.py"
            ).read_text(encoding="utf-8")
    smoothed = bool(re.search(r"lh_smooth\s*=\s*_boxcar", pipe)
                    and re.search(r"sqrt_lh\s*=\s*np\.sqrt\(np\.maximum\(lh_smooth", pipe))
    print(f"  process_real_sar_pipeline.py forms CPR from the "
          f"{'BOXCAR-SMOOTHED' if smoothed else 'RAW'} sigma0")
    print("  (checked by reading the code, not by inference: the boxcar is applied")
    print("   to sigma0 and CPR is built from lh_smooth / lv_smooth)")
    if not smoothed:
        bad.append("CPR is no longer formed from the smoothed field; every ENL "
                   "consumer below is now reading the wrong look count")

    ds = json.loads((DOCS / "detection_statistics.json").read_text(encoding="utf-8"))
    enl_ds = ds["effective_looks"]["screened_field"]["lh"]
    print(f"\n  detection_statistics.py   screened-field ENL  {enl_ds}")

    disp = json.loads((DOCS / "cpr_dispersion.json").read_text(encoding="utf-8"))
    enl_disp = disp["reference_looks"]
    print(f"  cpr_dispersion.py         reference ENL       {enl_disp}")
    if inject:
        enl_disp = 5.0
        print("  --inject-g13: cpr_dispersion's reference forced to 5.00")

    if abs(enl_ds - enl_disp) > 1e-9:
        bad.append(f"detection_statistics.py uses ENL {enl_ds} and cpr_dispersion.py "
                   f"uses {enl_disp}. There is one CPR field and it has one look "
                   f"count; two consumers disagreeing about it is how the "
                   f"upper bound of 29.16 % at N = 5 came to be quoted for a "
                   f"screen whose field has ENL {enl_ds}.")

    # And METHODS must quote the operating point, not the raw product's.
    m = (DOCS / "METHODS.md").read_text(encoding="utf-8")
    if re.search(r"At the measured N\s*[≈~]\s*5\b", m):
        bad.append("METHODS still says 'at the measured N ~ 5' for the operating "
                   "point; the threshold touches the smoothed field at "
                   f"ENL {enl_ds}")
    if not bad:
        print("\n  PASS — every consumer reads the same look count for the same field.")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inject-g12", action="store_true")
    ap.add_argument("--inject-g13", action="store_true")
    # Two gates in one file because they share the geometry, but they back two
    # different statements and verify_all reports them as two rows.
    ap.add_argument("--only", choices=("g12", "g13"), default=None)
    args = ap.parse_args()
    inject = args.inject_g12 or args.inject_g13

    bad = []
    if args.only in (None, "g12"):
        bad += g12(args.inject_g12)
    if args.only in (None, "g13"):
        bad += g13(args.inject_g13)

    hr("RESULT")
    if bad:
        for b in bad:
            print(f"  FAIL  {b}")
    if inject:
        if bad:
            print("\n  INJECTION CAUGHT. The gate works.")
            return 0
        print("\n  INJECTION NOT CAUGHT. The gate does not do what it says.")
        return 1
    if bad:
        print("\n  GATE FAIL.")
        return 1
    print("  GATE PASS — one incidence field satisfying the identity, and one look")
    print("  count for the one CPR field.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
