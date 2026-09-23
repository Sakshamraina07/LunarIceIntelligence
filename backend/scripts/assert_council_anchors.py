"""
assert_council_anchors.py -- G33. The council work order's analyses reproduce
the anchors they were built on.

    python backend/scripts/assert_council_anchors.py
        [--inject size|significant|fwe|perpixel|bound|monotone|iut|mc|v3|ceiling|
                  design_bound|design_size|design_pool]

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

The final pass (v14 work order) adds:

  B3 (np_power_bound.json)
    * the Neyman-Pearson bound is >= 5 % at every N (a level-5 % test exists)
      and non-decreasing in N;
    * the calibrated IUT's power in decision_rule.json (arm A, oracle and all
      plug-ins, read afresh) never exceeds the bound at the same population and N;
    * at every reported N the exact quadrature agrees with its Monte Carlo
      check within three standard errors (plus 0.05 points).
  B2 (f2_maximum.json::complex_field_v3)
    * with the delivered lags and v2's four looks, the null (CPR 1.00, DOP 0)
      reproduces v2's joint-rule rate and crater-level rate within three
      combined standard errors (the exactly stationary fields change nothing).
  B4 (complex_cell_ceiling.json)
    * the 21 x 1 participation ratio from the 2-D spectrum reproduces
      mechanism_spec.json's 1-D 7.13 within 0.1: the same spectrum, read twice.

The v17a pre-submission pass adds:

  P1 (region_design_curve.json)
    * the IUT's power is non-decreasing in N_eff (within two combined SEs)
      and never exceeds the NP bound at the same alternative and N_eff (by
      more than two SEs); its size at every null point and N_eff is at most
      5 % + 2 SE; pooled cells reproduce the single cell at K N within 3 SE.
      Each reads the conditioned estimate where the artifact has one (an
      exactly known component times a simulated conditional), else the
      plain frequency.

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
    ap.add_argument("--inject", choices=("size", "significant", "fwe", "perpixel", "bound",
                                         "monotone", "iut", "mc", "v3", "ceiling", "design_bound",
                                         "design_size", "design_pool"))
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

    # ---- B3: the Neyman-Pearson bound ----------------------------------------
    nb, dr = load("docs/np_power_bound.json"), load("docs/decision_rule.json")
    if nb is None or dr is None:
        bad.append("np_power_bound.json or decision_rule.json is absent")
    else:
        curve = sorted(nb["curve"], key=lambda c: c["N"])
        vals = [c["bound_percent"] for c in curve]
        if args.inject == "bound":
            vals[0] = 4.0
        if args.inject == "monotone":
            vals[3], vals[4] = vals[4], vals[3]
        ok5 = all(v >= 5.0 - 1e-6 for v in vals)
        okm = all(b >= a - 1e-6 for a, b in zip(vals, vals[1:]))
        print(f"  B3: bound >= 5 % at all {len(vals)} N -> {'ok' if ok5 else 'FAIL'}; "
              f"non-decreasing in N -> {'ok' if okm else 'FAIL'}")
        if not ok5:
            bad.append("the NP bound falls below 5 %")
        if not okm:
            bad.append("the NP bound is not monotone in N")
        bound_at = {(r["N"], r["population"]): r["bound_percent"] for r in nb["iut_comparison"]}
        over = []
        for key, blk in dr["summary"].items():
            arm, nn = key.split("_N")
            if arm != "A":
                continue
            for variant in ("oracle", "plugin_W960", "plugin_W16", "plugin_Wcomplex"):
                if variant not in blk:
                    continue
                for pop, pw in blk[variant]["iut_power_percent"].items():
                    b = bound_at.get((float(nn), pop))
                    if args.inject == "iut" and variant == "oracle":
                        pw = 100.0
                    if b is None or pw > b:
                        over.append((nn, variant, pop, pw, b))
        print(f"  B3: calibrated IUT power above the bound: {len(over)}  -> "
              f"{'ok' if not over else 'FAIL'}")
        if over:
            bad.append(f"IUT power exceeds the NP bound at {over[:2]}")
        mc_bad = []
        for k, v in nb["by_N"].items():
            e, m = v["bound_percent"], v["mc_check"]
            mv = m["power_percent"] + (5.0 if args.inject == "mc" else 0.0)
            if abs(e - mv) > 3 * m["mc_se_percent"] + 0.05:
                mc_bad.append((k, e, mv))
        print(f"  B3: exact vs Monte Carlo at {len(nb['by_N'])} N: {len(mc_bad)} disagree  -> "
              f"{'ok' if not mc_bad else 'FAIL'}")
        if mc_bad:
            bad.append(f"NP bound quadrature disagrees with its MC check at {mc_bad[:2]}")

    # ---- B2: complex_field_v3 reproduces v2 on the null --------------------
    v3 = (f2 or {}).get("complex_field_v3")
    if v3 is None:
        bad.append("f2_maximum.json::complex_field_v3 is absent")
    else:
        n13 = v3["results"]["delivered_LH"]["N13p72"]
        nul = n13["null CPR 1.00 DOP 0"]
        v2 = f2["complex_field_v2"]
        if n13["looks"] != v2["looks"]:
            bad.append("complex_field_v3's delivered-lag arm did not choose v2's look count")
        else:
            j3 = nul["joint_rule"]["p_at_least_1_cell"]
            f3 = nul["cpr_only"]["at_N13p72"]["p_at_least_1_pixel"]
            r3 = j3["rate"] - (0.05 if args.inject == "v3" else 0.0)
            ok1 = abs(r3 - v2["joint_rule_on_null"]["p_at_least_1_cell"]) <= 3 * np.hypot(
                j3["mc_se"], v2["joint_rule_on_null"]["p_at_least_1_se"])
            ok2 = abs(f3["rate"] - v2["fwe_at_1p895"]["rate"]) <= 3 * np.hypot(
                f3["mc_se"], v2["fwe_at_1p895"]["mc_se"])
            print(f"  B2: v3 null joint >=1 {100 * r3:.2f} % vs v2 "
                  f"{100 * v2['joint_rule_on_null']['p_at_least_1_cell']:.2f} %; FWE at 1.895 "
                  f"{100 * f3['rate']:.2f} vs {100 * v2['fwe_at_1p895']['rate']:.2f} %  -> "
                  f"{'ok' if ok1 and ok2 else 'FAIL'}")
            if not (ok1 and ok2):
                bad.append("complex_field_v3 does not reproduce v2 on the null")

    # ---- B4: the 2-D spectrum reproduces the 1-D participation ratio -------
    ce, ms = load("docs/complex_cell_ceiling.json"), load("docs/mechanism_spec.json")
    if ce is None or ms is None:
        bad.append("complex_cell_ceiling.json or mechanism_spec.json is absent")
    else:
        here = ce["summary"]["LH"]["21x1"]["median"] + (0.5 if args.inject == "ceiling" else 0.0)
        ref = ms["expected_looks_from_measured_spectrum"]["median"]
        ok = abs(here - ref) <= 0.1
        print(f"  B4: 21 x 1 participation ratio {here:.3f} vs mechanism_spec {ref:.3f}  -> "
              f"{'ok' if ok else 'FAIL'}")
        if not ok:
            bad.append("the 2-D spectrum does not reproduce mechanism_spec's 21-sample ratio")

    # ---- P1: the region-level design curve --------------------------------
    rd = load("docs/region_design_curve.json")
    if rd is None:
        bad.append("region_design_curve.json is absent")
    else:
        def best(x):
            return x.get("conditioned", x)
        ns = rd["N_eff_grid"]
        mono_bad, over, big = [], [], []
        for lab, rows in rd["iut_power"].items():
            b = [best(r) for r in rows]
            for i in range(len(b) - 1):
                if b[i + 1]["percent"] < b[i]["percent"] - 2 * np.hypot(b[i + 1]["mc_se_percent"],
                                                                        b[i]["mc_se_percent"]):
                    mono_bad.append((lab, ns[i + 1]))
            for j, r in enumerate(b):
                pw = r["percent"] + (50.0 if args.inject == "design_bound" and j == 0 else 0.0)
                if pw - 2 * r["mc_se_percent"] > rd["np_bound_percent"][lab][j] + 1e-6:
                    over.append((lab, ns[j], pw, rd["np_bound_percent"][lab][j]))
        for lab, rows in rd["iut_size_at_nulls"].items():
            for j, r in enumerate(rows):
                sz = best(r)["percent"] + (1.0 if args.inject == "design_size" else 0.0)
                if sz > 5.0 + 2 * best(r)["mc_se_percent"]:
                    big.append((lab, ns[j], sz))
        zs = [abs(r["iut_z"]) + (10.0 if args.inject == "design_pool" else 0.0)
              for r in rd["pooling"]["rows"]]
        print(f"  P1: power non-decreasing -> {'ok' if not mono_bad else 'FAIL'}; IUT above the NP "
              f"bound: {len(over)} -> {'ok' if not over else 'FAIL'}; size above 5 % + 2 SE: {len(big)} "
              f"-> {'ok' if not big else 'FAIL'}; pooled vs K N max |z| {max(zs):.2f} -> "
              f"{'ok' if max(zs) < 3 else 'FAIL'}")
        if mono_bad:
            bad.append(f"design-curve power decreases at {mono_bad[:2]}")
        if over:
            bad.append(f"design-curve IUT power exceeds the NP bound at {over[:2]}")
        if big:
            bad.append(f"design-curve IUT size exceeds 5 % + 2 SE at {big[:2]}")
        if max(zs) >= 3:
            bad.append("pooled cells do not reproduce the single cell at K N")

    if bad:
        print("\n  GATE FAIL —")
        for b in bad:
            print(f"    {b}")
        return 1
    print("\n  GATE PASS — Task 1 reproduces the size at N = 14 and has no significant joint")
    print("  selection below N = 79.6 in any arm; Task 4 reproduces 86.3 % and 7.76 %;")
    print("  the NP bound is >= 5 %, monotone, above every IUT power and matches its MC")
    print("  check; complex_field_v3 reproduces v2; the 2-D spectrum reproduces 7.13;")
    print("  the region design curve is monotone, under the NP bound, and of size 5 %.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
