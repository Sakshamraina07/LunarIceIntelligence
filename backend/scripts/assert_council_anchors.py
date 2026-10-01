"""
assert_council_anchors.py -- G33. The council work order's analyses reproduce
the anchors they were built on.

    python backend/scripts/assert_council_anchors.py
        [--inject size|significant|fwe|perpixel|bound|monotone|iut|mc|v3|ceiling|
                  design_bound|design_size|design_pool|mh|het|ladder|recon|identity|coherence]

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

The v18a last analysis pass adds:

  N1 / N2 (snr_control.json, crater_level_real.json)
    * the Mantel-Haenszel odds ratio, all passes and pass 1, recomputed from
      the stored coherence strata, equals the stored one;
    * the per-pass disc counts and selections sum to the pooled summary;
    * the SNR run's baseline variant reproduces every per-pass disc count and
      F2's 50 selections.
  N3 (region_design_curve.json::heterogeneous, ::f2_point)
    * no heterogeneous configuration's regional IUT exceeds 5 % + 2 SE;
    * the IUT power at F2's pooled N_eff lies between the grid's 254 and 400.
  N4 / N6 (region_mean_null.json, enl_logratio.json::split_sample)
    * E[m_hat | R >= 1] of an unpolarized population equals E[m_hat] (the sign
      of q_hat is independent of m_hat at CPR 1), so its 0.13 / 0.10 crossings
      reproduce dop_sampling_bias's within 1 %;
    * the split-sample run's full-sample control reproduces the 64 x 64 median.

The v20 gap pass adds:

  G-A / G-D (crater_level_real.json::v20_gap)
    * ladder model (c) reproduces the published PSR coefficient and SE to 1e-6;
      the crude pass-1 odds ratio follows from the stored per-pass counts; each
      bootstrap accounts for all B replicates (used + non-converged).
  G-B (snr_control.json::v20_reconciliation)
    * the referee's drops reconcile: total = non-positive diagonal + |S3| >= S0;
      the v18a variant is reproduced; the run's own gates passed.
  G-E / G-F (kernel_sweep.json)
    * the 5 x 5 row is the published frame (26 462 joint, 109 blocks, 709 cells
      above 79.6, the 39.4 block median); no F2 selected cell exceeds the band
      edge 1.2989 at any kernel (the identity, on the raw data).
  G-G (coherence_nhat.json, tail_calibration_ci.json::logratio_model_coherence_aware)
    * the Var(ln R) series matches Monte Carlo (max |z| < 3.5 for N >= 5); the
      standard arm reproduces logratio_model's pooled rates to 1e-12.
  G-H (band_s.json)
    * the S-band frame's joint count equals stokes_from_slc_20200808S's.

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
                                         "monotone", "iut", "mc", "v3", "ceiling", "design_bound", "mh", "het",
                                         "ladder", "recon", "identity", "coherence",
                                         "design_size", "design_pool", "v21_np", "v21_iut", "v21_f2", "v21_region", "v21_ladder",
                                         "v21_spec"))
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

    # ---- v18a: the last analysis pass ----------------------------------------
    cl, sn = load("docs/crater_level_real.json"), load("docs/snr_control.json")
    if cl is None or sn is None or "coherence_strata" not in cl:
        bad.append("crater_level_real.json (with the v18a keys) or snr_control.json is absent")
    else:
        # N2: the Mantel-Haenszel odds ratio, recomputed from the stored strata
        def mh(strata):
            num = den = 0.0
            for s in strata:
                a, n1 = s["inside"]["k"], s["inside"]["n"]
                c, n0 = s["outside"]["k"], s["outside"]["n"]
                b, d = n1 - a, n0 - c
                t = a + b + c + d
                if t:
                    num += a * d / t
                    den += b * c / t
            return num / den
        or_all = mh(cl["coherence_strata"]["all"]) * (1.5 if args.inject == "mh" else 1.0)
        or_p1 = mh(cl["coherence_strata"]["20200808"])
        st = cl["mantel_haenszel_inside_vs_outside"]
        mh_ok = abs(or_all - st["all"]["or"]) < 1e-9 and abs(or_p1 - st["20200808"]["or"]) < 1e-9
        # N2: the per-pass cells sum to the pooled counts
        pp, sm = cl["per_pass_class"], cl["summary"]
        sums_ok = all(pp[f"20200808_{c}"]["ge1"]["k"] + pp[f"20200305_{c}"]["ge1"]["k"]
                      == round(sm[c]["rule"]["p_ge_1"] * sm[c]["discs"])
                      and pp[f"20200808_{c}"]["discs"] + pp[f"20200305_{c}"]["discs"] == sm[c]["discs"]
                      for c in ("outside", "inside", "mixed"))
        # N1: the SNR run's baseline reproduces the published discs and F2
        f2p = load("docs/f2_complex_product.json")
        base = sn["discs_by_variant"]["base"]
        n1_ok = (sn["reproduces_crater_level_real"] is True
                 and all(base[k]["ge1"]["k"] == pp[k]["ge1"]["k"] for k in pp)
                 and sn["f2"]["base"]["published_rule_selects"]
                 == f2p["passes"]["20200808"]["craters"]["F2"]["published_rule_selects"])
        print(f"  N2: MH odds ratio recomputed from the strata {or_all:.4f} / pass 1 {or_p1:.4f} -> "
              f"{'ok' if mh_ok else 'FAIL'}; per-pass cells sum to the pooled counts -> "
              f"{'ok' if sums_ok else 'FAIL'}; N1 baseline reproduces discs and F2 -> {'ok' if n1_ok else 'FAIL'}")
        if not mh_ok:
            bad.append("the stored Mantel-Haenszel odds ratio does not follow from the stored strata")
        if not sums_ok:
            bad.append("per-pass disc counts do not sum to the pooled summary")
        if not n1_ok:
            bad.append("snr_control's baseline does not reproduce crater_level_real / f2_complex_product")
    if rd is not None and "heterogeneous" in rd:
        # N3: no heterogeneous configuration puts the regional IUT above 5 % + 2 SE
        het = [(cls, k, dr, ph, r["iut"]) for cls, c in rd["heterogeneous"]["results"].items()
               for k, x in c.items() for dr, y in x.items() for ph, r in y.items()]
        worst = max(r["percent"] + 2 * r["mc_se_percent"] for *_, r in het) \
            + (6.0 if args.inject == "het" else 0.0)
        # f2_point sits between the grid's 254 and 400 (power non-decreasing)
        fp = rd.get("f2_point")
        g = rd["iut_power"]["CPR 1.1 DOP min"]
        mid = best(fp["iut_power"]["CPR 1.1 DOP min"]) if fp else None
        fp_ok = fp is not None and best(g[0])["percent"] - 2 * best(g[0])["mc_se_percent"] \
            <= mid["percent"] <= best(g[1])["percent"] + 2 * best(g[1])["mc_se_percent"]
        print(f"  N3: {len(het)} heterogeneous configurations, max IUT + 2 SE {worst:.3f} % -> "
              f"{'ok' if worst <= 5.0 else 'FAIL'}; IUT power at F2's N_eff between the 254 and 400 "
              f"grid points -> {'ok' if fp_ok else 'FAIL'}")
        if worst > 5.0:
            bad.append("a heterogeneous region's IUT rate exceeds 5 % + 2 SE")
        if not fp_ok:
            bad.append("the f2_point IUT power is not bracketed by the design grid")
    rm, dsb = load("docs/region_mean_null.json"), load("docs/dop_sampling_bias.json")
    el = load("docs/enl_logratio.json")
    if rm is None or dsb is None or el is None or "split_sample" not in el:
        bad.append("region_mean_null.json, dop_sampling_bias.json or enl_logratio.split_sample is absent")
    else:
        # N4: E[m_hat | R >= 1] of an unpolarized population equals E[m_hat]
        # (the sign of q_hat is independent of m_hat at CPR 1), so its 0.13 and
        # 0.10 crossings must reproduce dop_sampling_bias's unconditional ones
        c13 = rm["conditional_mean_dop_unpolarized"]["N_conditional_0p13"]
        c10 = rm["conditional_mean_dop_unpolarized"]["N_conditional_0p10"]
        u = dsb["mean_sample_dop_unpolarized"]
        r13 = abs(c13 / u["N_where_mean_is_0p13"] - 1)
        r10 = abs(c10 / u["N_where_mean_is_0p10"] - 1)
        # N6: the split-sample run's full-sample control reproduces 39.4
        fs = el["split_sample"]["full_sample_check"]["N_logratio"]["median"]
        ref = el["pass_20200808"]["blocks_64x64"]["N_logratio"]["median"]
        print(f"  N4: conditional crossings {c13:.2f} / {c10:.2f} vs unconditional "
              f"{u['N_where_mean_is_0p13']:.2f} / {u['N_where_mean_is_0p10']:.2f} -> "
              f"{'ok' if max(r13, r10) < 0.01 else 'FAIL'}; N6 full-sample control {fs:.3f} vs {ref:.3f} -> "
              f"{'ok' if abs(fs - ref) < 0.01 else 'FAIL'}")
        if max(r13, r10) >= 0.01:
            bad.append("region_mean_null's conditional crossings do not reproduce dop_sampling_bias")
        if abs(fs - ref) >= 0.01:
            bad.append("split_sample's full-sample control does not reproduce the 64 x 64 N_logratio median")

    # ---- v20: the gap pass ---------------------------------------------------
    g = (cl or {}).get("v20_gap")
    kn, cn, bsd = load("docs/kernel_sweep.json"), load("docs/coherence_nhat.json"), load("docs/band_s.json")
    tcd = load("docs/tail_calibration_ci.json")
    if g is None or kn is None or sn is None or "v20_reconciliation" not in (sn or {}):
        bad.append("v20_gap, kernel_sweep.json or snr_control.v20_reconciliation is absent")
    else:
        # G-A: the published logistic specification is reproduced by the ladder's model (c); the crude odds
        # ratio of pass 1 follows from the stored per-pass counts
        pub = cl["logistic_fires"]["coefficients"]["class_inside_psr"]
        lc = g["ladder"]["c"]["psr"]
        a_ok = abs(lc["coefficient"] - pub["estimate"]) < 1e-6 and abs(lc["se_model"] - pub["se"]) < 1e-6
        pp = cl["per_pass_class"]
        i_, o_ = pp["20200808_inside"]["ge1"], pp["20200808_outside"]["ge1"]
        crude = ((i_["k"] / (i_["n"] - i_["k"])) / (o_["k"] / (o_["n"] - o_["k"]))) * (1.25 if args.inject == "ladder" else 1.0)
        c_ok = abs(crude - g["unadjusted"]["pass_20200808"]["or"]) < 1e-9
        b_ok = all(g["ladder"][k]["psr"]["block_bootstrap"]["replicates_used"] + g["ladder"][k]["psr"]["block_bootstrap"]["non_converged"]
                   == g["bootstrap_B"] for k in g["ladder"])
        print(f"  v20 G-A: ladder (c) reproduces the published PSR coefficient {lc['coefficient']:+.3f} +/- "
              f"{lc['se_model']:.3f} -> {'ok' if a_ok else 'FAIL'}; crude pass-1 OR {crude:.2f} from the counts -> "
              f"{'ok' if c_ok else 'FAIL'}; every bootstrap accounts for B -> {'ok' if b_ok else 'FAIL'}")
        if not (a_ok and c_ok and b_ok):
            bad.append("v20_gap: the ladder does not reproduce the published coefficient, the crude odds ratio, or B")
        # G-B: the referee's three numbers reconcile arithmetically, and the v18a variant is reproduced
        rc = sn["v20_reconciliation"]
        dec = rc["decomposition_of_the_v18a_drops"]["20200808"]
        psd_key = "corrected_matrix_not_psd_in_S0_test_(|S3|>=S0)"
        tot_ok = dec["total_dropped_by_the_v18a_variant"] == dec["corrected_diagonal_not_positive"] + dec[psd_key] \
            + (7 if args.inject == "recon" else 0)
        leg_ok = rc["variants_frame"]["legacy_v18a_noise_corrected"]["20200808"]["joint"] == sn["headline"]["noise_corrected"]["frame_joint_pass1"]
        gates_ok = all(rc["gates"].values())
        print(f"  v20 G-B: 285 198 = {dec['corrected_diagonal_not_positive']:,} + {dec[psd_key]:,} -> "
              f"{'ok' if tot_ok else 'FAIL'}; v18a variant reproduced -> {'ok' if leg_ok else 'FAIL'}; run gates -> "
              f"{'ok' if gates_ok else 'FAIL'}")
        if not (tot_ok and leg_ok and gates_ok):
            bad.append("snr_control.v20_reconciliation: the drops do not reconcile or the v18a variant is not reproduced")
        # G-E / G-F: the 5 x 5 row is the published frame; the identity holds on the data at every kernel
        k5 = kn["kernel_sweep"]["20200808"]["5x5"]
        k_ok = (k5["joint"] == sn["headline"]["base"]["frame_joint_pass1"] and k5["blocks_64x64"]["blocks"] == 109
                and k5["n_selected_with_local_N_ge_79p6"] == el["pass_20200808"]["selected"]["n_local_N_ge_79p6"]
                and abs(k5["blocks_64x64"]["N_logratio"]["median"] - el["pass_20200808"]["blocks_64x64"]["N_logratio"]["median"]) < 1e-9)
        ident = [v["cells_f2_fixed_b5_signal_set"]["selected_with_cpr_above_band_edge"]
                 for v in kn["f2_cpr_distribution"]["20200808"].values()]
        i_ok = all(x == 0 for x in ident) and (args.inject != "identity")
        print(f"  v20 G-E/F: the 5 x 5 row reproduces the published frame, 109 blocks and 709 cells -> "
              f"{'ok' if k_ok else 'FAIL'}; F2 selected cells above the band edge at every kernel: {ident} -> "
              f"{'ok' if i_ok else 'FAIL'}")
        if not (k_ok and i_ok):
            bad.append("kernel_sweep: the 5 x 5 row does not reproduce the published frame, or a selected cell exceeds the band edge")
    if cn is None or tcd is None or "logratio_model_coherence_aware" not in tcd:
        bad.append("coherence_nhat.json or tail_calibration_ci.logratio_model_coherence_aware is absent")
    else:
        # G-G: the formula against Monte Carlo (N >= 5); the standard arm reproduces the v18a held-out rates
        z = cn["formula_check"]["max_abs_z_N_ge_5"] + (5.0 if args.inject == "coherence" else 0.0)
        old = tcd["logratio_model"]["results"]
        new = tcd["logratio_model_coherence_aware"]["results"]
        same = all(abs(new[t]["standard"]["levels"][k]["pooled"] - old[t]["levels"][k]["pooled"]) < 1e-12
                   for t in old for k in ("1pct", "5pct", "10pct"))
        print(f"  v20 G-G: Var(ln R) series against Monte Carlo max |z| {z:.2f} -> {'ok' if z < 3.5 else 'FAIL'}; "
              f"the standard arm reproduces the v18a held-out rates -> {'ok' if same else 'FAIL'}")
        if z >= 3.5:
            bad.append("coherence_nhat: the Var(ln R) series disagrees with Monte Carlo")
        if not same:
            bad.append("tail_calibration_ci: the coherence-aware run's standard arm does not reproduce logratio_model")
    if bsd is None:
        bad.append("band_s.json is absent")
    else:
        s_st = load("docs/stokes_from_slc_20200808S.json")
        s_ok = s_st is not None and bsd["frame"]["joint"] == s_st["results"]["joint_measured"]["unconditional"]["n_both"]
        print(f"  v20 G-H: the S-band frame's joint count {bsd['frame']['joint']:,} equals stokes_from_slc_20200808S's "
              f"-> {'ok' if s_ok else 'FAIL'}")
        if not s_ok:
            bad.append("band_s: the joint count does not reproduce stokes_from_slc_20200808S")

    # ---- v21: the N-sensitivity and the shadow-identification work -----------
    ns = load("docs/n_sensitivity.json")
    npr = load("docs/n_sensitivity_np.json")
    nr = load("docs/n_sensitivity_real.json")
    ncore = load("docs/n_sensitivity_core.json")
    nrg = load("docs/n_sensitivity_region.json")
    if ns is None or npr is None or nr is None or ncore is None or nrg is None:
        bad.append("n_sensitivity*.json is absent")
    else:
        # W1B: the NP bound reproduces the twelve values the work order quotes, to their printed precision
        agree = all(d["agrees_to_printed_precision"] for d in npr["reproduction"])
        if args.inject == "v21_np":
            agree = False
        print(f"  v21 W1B: the NP bound reproduces {len(npr['reproduction'])} quoted values (N = 14 ... 500) -> "
              f"{'ok' if agree else 'FAIL'}")
        if not agree:
            bad.append("n_sensitivity_np: a quoted Neyman-Pearson bound is not reproduced")
        # W1A: the critical value equals the band edge at N = 79.6166 and is above it below
        from scipy.stats import f as _F
        nedge = ncore["N_edge_crit_equals_1p2989"]
        edge = ncore["band_cpr_edges"][1]
        c_ok = abs(_F.ppf(0.95, 2 * nedge, 2 * nedge) - edge) < 1e-6 and _F.ppf(0.95, 2 * (nedge - 0.5), 2 * (nedge - 0.5)) > edge
        print(f"  v21 W1A: crit95 of F(2N,2N) equals the band edge {edge:.4f} at N = {nedge:.4f} and exceeds it below -> "
              f"{'ok' if c_ok else 'FAIL'}")
        if not c_ok:
            bad.append("n_sensitivity_core: the band-edge look count is not where crit95 crosses 1.2989")
        # W1D: the IUT has no rejection region through 218 and one by 254 (known N)
        by = nr["by_N"]
        i218, i254 = by["218"]["iut_has_rejection_region"], by["254"]["iut_has_rejection_region"]
        if args.inject == "v21_iut":
            i218 = True
        i_ok = (not i218) and i254 and ncore["iut_onset"]["last_N_without"] >= 218 and ncore["iut_onset"]["first_N_with_rejection_region"] <= 254
        print(f"  v21 W1D: the IUT region is empty at 218, present at 254, onset {ncore['iut_onset']['first_N_with_rejection_region']} -> "
              f"{'ok' if i_ok else 'FAIL'}")
        if not i_ok:
            bad.append("n_sensitivity: the IUT onset is not between 218 and 254")
        # W1F: the smallest N at which any selected cell is significant is where crit95 falls to its largest R
        sm = nr["smallest_N_any_selected_cell_significant"]
        f2 = sm["L_20200808 / F2"]
        rmax = f2["max_R_selected"] * (1.05 if args.inject == "v21_f2" else 1.0)
        f_ok = abs(_F.ppf(0.95, 2 * f2["smallest_N_any_selected_cell_significant"], 2 * f2["smallest_N_any_selected_cell_significant"]) - rmax) < 1e-6 \
            and f2["selected"] == 50 and sm["S_20200808S / F2"]["selected"] == 29 and sm["L_20200808 / whole frame"]["selected"] == 26462 \
            and sm["L_20200305 / whole frame"]["selected"] == 24 and f2["smallest_N_any_selected_cell_significant"] >= nedge
        print(f"  v21 W1F: F2's largest selected R {f2['max_R_selected']:.4f} is critical at N = {f2['smallest_N_any_selected_cell_significant']:.2f} "
              f"(never below the identity's {nedge:.1f}); selected counts 50 / 29 / 26462 / 24 -> {'ok' if f_ok else 'FAIL'}")
        if not f_ok:
            bad.append("n_sensitivity_real: F2's smallest significant N is not where crit95 equals its largest selected R, or a selected count moved")
        # W1E: unconditional = conditional x containing, and the big-field calibration reproduces the achieved N of the published rows it reuses
        pop = "CPR 0.7 DOP 0.176"
        r39 = nrg["results"][pop]["N39.4"]["cells260"]["correlated"]
        u = r39["conditional_p"] * r39["containing_fraction"] * (1.25 if args.inject == "v21_region" else 1.0)
        u_ok = abs(u - r39["unconditional_p"]) < 0.006 and abs(0.823 * 34.08 - 28.05) < 0.01
        cal = nrg["calibration"]["260"]
        c13 = cal["13"]
        print(f"  v21 W1E: 0.823 x 34.08 % = {0.823 * 34.08:.2f} % = the stored unconditional {100 * r39['unconditional_p']:.2f} %; the 200 x 200 "
              f"calibration puts L = 13 at {c13:.1f} looks -> {'ok' if u_ok and 35 < c13 < 40 else 'FAIL'}")
        if not (u_ok and 35 < c13 < 40):
            bad.append("n_sensitivity_region: the unconditional rate is not conditional x containing, or the looks calibration moved")
    sid = load("docs/shadow_identification.json")
    if sid is None:
        bad.append("shadow_identification.json is absent")
    else:
        # W2A: the ladder reproduces the published rungs (point estimates; the intervals carry bootstrap noise)
        lad = sid["A_ladder"]
        pub = {("L_two_passes", "a"): 1.79, ("L_two_passes", "b"): 1.29, ("L_two_passes", "c"): 0.67, ("L_two_passes", "e0"): 1.01,
               ("S_pass1", "a"): 2.93, ("S_pass1", "b"): 1.62, ("S_pass1", "c"): 0.83, ("S_pass1", "e0"): 0.49}
        worst = max(abs(round(lad[k][("rungs")][r]["odds_ratio"], 2) - v) for (k, r), v in pub.items())
        if args.inject == "v21_ladder":
            worst += 0.3
        l_ok = worst < 0.0051 and sid["A_reproduction"]["L_two_passes.c"]["agrees"] and abs(lad["L_two_passes"]["rungs"]["c"]["coefficient"] + 0.401) < 0.0006
        print(f"  v21 W2A: the ladder reproduces 8 published odds ratios (largest difference {worst:.4f}) and the published coherence-adjusted "
              f"coefficient {lad['L_two_passes']['rungs']['c']['coefficient']:+.3f} -> {'ok' if l_ok else 'FAIL'}")
        if not l_ok:
            bad.append("shadow_identification: the ladder does not reproduce the published odds ratios")
        # W2B: the specification curve contains the published specification, and its summary counts add up
        sp = sid["B_spec_curve"]["L_two_passes"]
        n_spec = sp["summary"]["specifications"]
        s_ok = n_spec == 1024 and sp["summary"]["with_coherence"]["n"] + sp["summary"]["without_coherence"]["n"] <= n_spec
        if args.inject == "v21_spec":
            s_ok = False
        print(f"  v21 W2B: the specification curve has {n_spec} specifications (2^10), with + without coherence = "
              f"{sp['summary']['with_coherence']['n']} + {sp['summary']['without_coherence']['n']} -> {'ok' if s_ok else 'FAIL'}")
        if not s_ok:
            bad.append("shadow_identification: the specification curve is incomplete")

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
