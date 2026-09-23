"""
assert_council_anchors.py -- G33. The council work order's analyses reproduce
the anchors they were built on.

    python backend/scripts/assert_council_anchors.py [--inject size|significant|fwe|perpixel]

The work order named two gates, and each is checked here from its artifact
rather than trusted from the run that wrote it:

  Task 1 (joint_power_curve.json)
    * arm A at N = 14 reproduces the joint rule's size 3.575 % of
      joint_calibration.json within three combined Monte Carlo standard errors;
    * P(joint AND R > crit_95) is EXACTLY zero for every N below 79.6, in every
      arm -- the sample identity m_hat >= |1 - R|/(1 + R) makes it so, and a
      single non-zero cell would mean the simulator does not form the Stokes
      vector with one set of weights.
  Task 4 (f2_maximum.json::complex_field_v2)
    * the gamma_c = 0 arm reproduces the first complex run's crater-level rate
      at 1.895 (86.3 +/- 0.3 %) and its per-pixel rate (7.76 %), each within
      three combined standard errors.

Each check is recomputed from the stored cells, not read from the artifact's
own gate verdict.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

BASE_DIR = Path(__file__).resolve().parents[2]
N_EDGE = 79.6166

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def load(rel):
    p = BASE_DIR / rel
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inject", choices=("size", "significant", "fwe", "perpixel"))
    args = ap.parse_args()
    print("=" * 78)
    print("G33 — the council analyses reproduce their anchors")
    print("=" * 78)
    bad = []

    jp, jc = load("docs/joint_power_curve.json"), load("docs/joint_calibration.json")
    if jp is None or jc is None:
        bad.append("joint_power_curve.json or joint_calibration.json is absent")
    else:
        ref = max(c["p_joint_selection"]["percent"] for c in jc["cells"]
                  if c["N"] == 14 and c["pop_cpr"] == 1.0 and c["pop_dop"] <= 0.13 + 1e-12)
        ref_se = max(c["p_joint_selection"]["mc_se_percent"] for c in jc["cells"]
                     if c["N"] == 14 and c["pop_cpr"] == 1.0)
        a14 = [c for c in jp["arms"]["A"]["cells"] if c["N"] == 14 and c["kind"] == "null"]
        top = max(a14, key=lambda c: c["p_joint"]["percent"])
        size, se = top["p_joint"]["percent"], top["p_joint"]["mc_se_percent"]
        if args.inject == "size":
            size += 1.0
        ok = abs(size - ref) <= 3 * np.hypot(se, ref_se)
        print(f"  Task 1: arm A size at N = 14 {size:.3f} +/- {se:.3f} % against {ref:.3f} +/- "
              f"{ref_se:.3f} %  -> {'ok' if ok else 'FAIL'}")
        if not ok:
            bad.append("arm A at N = 14 does not reproduce the joint rule's size")
        nz = [(arm, c["N"], c["population"]) for arm, v in jp["arms"].items() for c in v["cells"]
              if c["N"] < N_EDGE and c["n_joint_and_significant"] > 0]
        if args.inject == "significant":
            nz.append(("A", 14, "injected"))
        print(f"  Task 1: cells below N = 79.6 with a jointly selected cell above crit_95: "
              f"{len(nz)}  -> {'ok' if not nz else 'FAIL'}")
        if nz:
            bad.append(f"P(joint AND significant) non-zero below N = 79.6 at {nz[:3]}")

    f2 = load("docs/f2_maximum.json")
    v2 = (f2 or {}).get("complex_field_v2")
    if v2 is None:
        bad.append("f2_maximum.json::complex_field_v2 is absent")
    else:
        cf = f2["complex_field"]["true_cpr_1"]
        fwe, fse = v2["fwe_at_1p895"]["rate"], v2["fwe_at_1p895"]["mc_se"]
        if args.inject == "fwe":
            fwe -= 0.05
        ok = abs(fwe - cf["fwe_p_max_gt_crit"]) <= 3 * np.hypot(fse, cf["fwe_se"])
        print(f"  Task 4: FWE at 1.895 {100 * fwe:.2f} +/- {100 * fse:.2f} % against "
              f"{100 * cf['fwe_p_max_gt_crit']:.2f} +/- {100 * cf['fwe_se']:.2f} %  -> "
              f"{'ok' if ok else 'FAIL'}")
        if not ok:
            bad.append("complex_field_v2 does not reproduce the crater-level rate")
        pp, pse = v2["per_pixel"]["exceedance_rate"], v2["per_pixel"]["mc_se"]
        ref_pp = cf["area_gt_crit"]["mean"] / f2["complex_field"]["amplitude_pixels"]
        ref_se = cf["area_gt_crit"]["se"] / f2["complex_field"]["amplitude_pixels"]
        if args.inject == "perpixel":
            pp += 0.01
        ok = abs(pp - ref_pp) <= 3 * np.hypot(pse, ref_se)
        print(f"  Task 4: per-pixel rate {100 * pp:.2f} +/- {100 * pse:.2f} % against "
              f"{100 * ref_pp:.2f} +/- {100 * ref_se:.2f} %  -> {'ok' if ok else 'FAIL'}")
        if not ok:
            bad.append("complex_field_v2 does not reproduce the per-pixel rate")

    if bad:
        print("\n  GATE FAIL —")
        for b in bad:
            print(f"    {b}")
        return 1
    print("\n  GATE PASS — Task 1 reproduces the size at N = 14 and has no significant joint")
    print("  selection below N = 79.6 in any arm; Task 4 reproduces 86.3 % and 7.76 %.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
