"""
band_s_ladder_v20.py -- the G-A ladder on the S-band pass-1 discs, and the
comparison of the S- and L-band firing sets. (v20, follow-up to G-A / G-H)

    python backend/scripts/band_s_ladder_v20.py

Merged into docs/band_s.json as `ladder_v20` (seed 20260930, B = 2000). The
S-band acquisition is the pass-1 frame, so the models carry no pass term:
  (a) class            (b) (a) + ln N-hat      (b2) (b) + min SNR
  (c) (b2) + coherence (d) (c) + cx/100, cy/100
  (e) (c) + slant-range sample, geometry-file incidence, LOLA local incidence
  (e0) (a) + the same geometry, no coherence
Discs are the published construction on the S-band signal mask (the 663
nearest cells with boxcar'd power above the S-band label floor in both
channels); the same 5 x 5 disc-lattice blocks are resampled. The L-band
pass-1 discs are fitted the same way for a like-for-like comparison.

Also: is the S-band set of fired shadowed discs the L-band set? The discs sit
on the same lattice, so they are compared by (cx, cy).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runinfo import run_info  # noqa: E402
import f2_complex_product as FCP  # noqa: E402
import snr_control as SC  # noqa: E402
import gap_v20_frame as GF  # noqa: E402
import crater_ladder_v20 as CL  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "band_s.json"
PID = "20200808S"
SEED, B = CL.SEED, CL.B


def s_band_discs(psr, qtab, n_target):
    FCP.PASS_STEM[PID] = "ch2_sar_ncxs_20200808t201154198"
    FCP.GEOM[PID] = FCP.GEOM["20200808"]
    R = GF.read_pass(PID)
    rows, cols = R["shape"]
    hh, vv, hv = GF.boxed(R, 5)
    E = GF.evaluate2(hh, vv, hv, None, qtab)
    c0 = R["c0"]
    G = GF.geometry_xy(R, PID, psr)
    signal = E["ok"] & (hh > c0[0]) & (vv > c0[1])
    discs = SC.tile({"x": G["x"], "y": G["y"]}, signal, n_target, FCP.DISC_R_M)
    snr = 10 * np.log10(np.maximum(np.minimum(hh / c0[0], vv / c0[1]), 1e-30))
    dem = GF.LDEM()
    spec, g = G["spec"], G["grid"]
    dxs = np.gradient(G["tx"], axis=1) / spec["interval_pix"]
    dys = np.gradient(G["ty"], axis=1) / spec["interval_pix"]
    out = []
    for d in discs:
        c = d["cells"]
        ii, jj = np.divmod(c, cols)
        LI = R["AL"] * ii + (R["AL"] - 1) / 2.0
        SI = jj.astype(float)
        inc = FCP.interp(g[..., 3], LI, SI, spec)
        ux, uy = -FCP.interp(dxs, LI, SI, spec), -FCP.interp(dys, LI, SI, spec)
        nr = np.hypot(ux, uy)
        ux, uy = ux / nr, uy / nr
        p, q = dem.pq(G["x"].ravel()[c], G["y"].ravel()[c])
        th = np.deg2rad(inc)
        loc = np.rad2deg(np.arccos(np.clip((np.cos(th) - np.sin(th) * (p * ux + q * uy)) /
                                           np.sqrt(1 + p * p + q * q), -1, 1)))
        pf = float(G["psr"].ravel()[c].mean())
        out.append({"cx": d["cx"], "cy": d["cy"],
                    "class": "outside" if pf == 0.0 else ("inside" if pf == 1.0 else "mixed"),
                    "rule": int(E["rule"].ravel()[c].sum()),
                    "median_coherence": float(np.nanmedian(E["coh"].ravel()[c])),
                    "median_N_hat": float(np.nanmedian(E["nh"].ravel()[c])),
                    "median_min_snr_db": float(np.median(snr.ravel()[c])),
                    "j": float(np.median(jj)), "inc": float(np.median(inc)), "loc": float(np.nanmedian(loc))})
    return out


def fit_ladder(rows, label):
    """The ladder on a list of disc dicts (keys class, rule, cx, cy, coh, lnN, snr, j, inc, loc)."""
    n = len(rows)
    cls = np.array([r["class"] for r in rows])
    y = (np.array([r["rule"] for r in rows]) >= 1).astype(float)
    arr = lambda k: np.array([r[k] for r in rows], float)  # noqa: E731
    coh, lnN, snr = arr("median_coherence"), np.log(arr("median_N_hat")), arr("median_min_snr_db")
    cx, cy, J, INC, LOC = arr("cx"), arr("cy"), arr("j"), arr("inc"), arr("loc")
    inside, mixed = (cls == "inside").astype(float), (cls == "mixed").astype(float)
    models = {"a": [inside, mixed], "b": [inside, mixed, lnN], "b2": [inside, mixed, lnN, snr],
              "c": [inside, mixed, coh, lnN, snr], "d": [inside, mixed, coh, lnN, snr, cx / 100., cy / 100.],
              "e": [inside, mixed, coh, lnN, snr, J / 100., INC, LOC],
              "e0": [inside, mixed, J / 100., INC, LOC]}
    names = {"a": ["class_inside_psr", "class_mixed"], "b": ["class_inside_psr", "class_mixed", "ln_median_N_hat"],
             "b2": ["class_inside_psr", "class_mixed", "ln_median_N_hat", "median_min_snr_db"],
             "c": ["class_inside_psr", "class_mixed", "median_coherence", "ln_median_N_hat", "median_min_snr_db"],
             "d": ["class_inside_psr", "class_mixed", "median_coherence", "ln_median_N_hat", "median_min_snr_db",
                   "cx_over_100", "cy_over_100"],
             "e": ["class_inside_psr", "class_mixed", "median_coherence", "ln_median_N_hat", "median_min_snr_db",
                   "slant_range_sample_over_100", "incidence_geometry_deg", "lola_local_incidence_deg"],
             "e0": ["class_inside_psr", "class_mixed", "slant_range_sample_over_100", "incidence_geometry_deg",
                    "lola_local_incidence_deg"]}
    keys = [(r["cx"] // CL.BLOCK, r["cy"] // CL.BLOCK) for r in rows]
    uk = sorted(set(keys))
    kid = {k: i for i, k in enumerate(uk)}
    groups = np.array([kid[k] for k in keys])
    idx = [np.flatnonzero(groups == g) for g in range(len(uk))]
    X = {k: np.column_stack([np.ones(n)] + v) for k, v in models.items()}
    ins = cls == "inside"
    out_ = cls == "outside"
    cbins = np.digitize(coh, [0.4, 0.5, 0.6])
    res = {"label": label, "discs": n, "events": int(y.sum()), "blocks": len(uk),
           "classes": {c: {"discs": int((cls == c).sum()), "fires": int(((cls == c) & (y == 1)).sum())}
                       for c in ("outside", "inside", "mixed")},
           "ladder": {}}
    fits = {}
    for k in models:
        b, cov, ll, conv = CL.irls(X[k], y)
        se = np.sqrt(np.diag(cov))
        cse = np.sqrt(np.diag(CL.cluster_cov(X[k], y, b, cov, groups)))
        res["ladder"][k] = {"covariates": ["intercept"] + names[k], "converged": conv,
                            "coefficients": {nm: {"estimate": float(b[i]), "se_model": float(se[i]),
                                                  "se_cluster_robust": float(cse[i])}
                                             for i, nm in enumerate(["intercept"] + names[k])},
                            "psr": {"coefficient": float(b[1]), "se_model": float(se[1]),
                                    "se_cluster_robust": float(cse[1]), "odds_ratio": float(np.exp(b[1])),
                                    "or_ci95_model": [float(np.exp(b[1] - 1.96 * se[1])), float(np.exp(b[1] + 1.96 * se[1]))],
                                    "or_ci95_cluster_robust": [float(np.exp(b[1] - 1.96 * cse[1])),
                                                               float(np.exp(b[1] + 1.96 * cse[1]))]}}
        fits[k] = b
    a, bb_, c, d = (int(((y == 1) & ins).sum()), int(((y == 0) & ins).sum()),
                    int(((y == 1) & out_).sum()), int(((y == 0) & out_).sum()))
    res["unadjusted"] = CL.crude_or(a, a + bb_, c, c + d)
    st = [[int(((y == 1) & ins & (cbins == s)).sum()), int(((y == 0) & ins & (cbins == s)).sum()),
           int(((y == 1) & out_ & (cbins == s)).sum()), int(((y == 0) & out_ & (cbins == s)).sum())] for s in range(4)]
    res["mantel_haenszel_coherence_strata"] = CL.mh_or(*[[s[i] for s in st] for i in range(4)])
    # block bootstrap: one resample per replicate shared by every statistic
    rng = np.random.default_rng(SEED)
    boot = {k: [] for k in models}
    bmh, bun = [], []
    fails = {k: 0 for k in models}
    for _ in range(B):
        pick = rng.integers(0, len(uk), len(uk))
        ii = np.concatenate([idx[k] for k in pick])
        yy, cl, cb = y[ii], cls[ii], cbins[ii]
        for k in models:
            bt, _c, _l, conv = CL.irls(X[k][ii], yy)
            if conv:
                boot[k].append(bt[1])
            else:
                fails[k] += 1
        ib, ob = cl == "inside", cl == "outside"
        A = np.array([[((yy == 1) & ib & (cb == s)).sum(), ((yy == 0) & ib & (cb == s)).sum(),
                       ((yy == 1) & ob & (cb == s)).sum(), ((yy == 0) & ob & (cb == s)).sum()] for s in range(4)], float)
        nn = A.sum(axis=1)
        Rn = np.sum(A[:, 0] * A[:, 3] / np.where(nn > 0, nn, 1))
        Sn = np.sum(A[:, 1] * A[:, 2] / np.where(nn > 0, nn, 1))
        bmh.append(np.log(Rn / Sn) if Rn > 0 and Sn > 0 else np.nan)
        t = A.sum(axis=0)
        bun.append(np.log(t[0] * t[3] / (t[1] * t[2])) if t[1] * t[2] > 0 and t[0] * t[3] > 0 else np.nan)
    for k in models:
        iv = CL.interval(boot[k])
        iv["or_ci95"] = [float(np.exp(v)) for v in iv["ci95"]]
        iv["B"], iv["non_converged"] = B, fails[k]
        res["ladder"][k]["psr"]["block_bootstrap"] = iv
    for tgt, v in ((res["mantel_haenszel_coherence_strata"], bmh), (res["unadjusted"], bun)):
        iv = CL.interval(v)
        iv["or_ci95"] = [float(np.exp(x)) for x in iv["ci95"]]
        iv["B"] = B
        tgt["block_bootstrap"] = iv
    # which intervals exclude 1
    ex = {}
    for k in models:
        p = res["ladder"][k]["psr"]
        ex[f"model_{k}"] = {kind: bool(lo > 1 or hi < 1) for kind, (lo, hi) in (
            ("model_based", p["or_ci95_model"]), ("cluster_robust", p["or_ci95_cluster_robust"]),
            ("block_bootstrap", p["block_bootstrap"]["or_ci95"]))}
    ex["unadjusted"] = {"woolf": bool(res["unadjusted"]["ci95_woolf"][0] > 1 or res["unadjusted"]["ci95_woolf"][1] < 1),
                        "block_bootstrap": bool(res["unadjusted"]["block_bootstrap"]["or_ci95"][0] > 1 or
                                                res["unadjusted"]["block_bootstrap"]["or_ci95"][1] < 1)}
    ex["mantel_haenszel"] = {"rbg": bool(res["mantel_haenszel_coherence_strata"]["ci95"][0] > 1 or
                                        res["mantel_haenszel_coherence_strata"]["ci95"][1] < 1),
                            "block_bootstrap": bool(res["mantel_haenszel_coherence_strata"]["block_bootstrap"]["or_ci95"][0] > 1 or
                                                   res["mantel_haenszel_coherence_strata"]["block_bootstrap"]["or_ci95"][1] < 1)}
    res["interval_excludes_1"] = ex
    return res


def main() -> int:
    import validate_psr_vs_lola as V
    psr = V.load_pds("LPSR_75S_120M_201608")
    dr = json.loads((BASE_DIR / "docs" / "decision_rule.json").read_text(encoding="utf-8"))
    qtab = {int(k): v for k, v in dr["dop_quantile_table"]["q05"].items()}
    clr = json.loads((BASE_DIR / "docs" / "crater_level_real.json").read_text(encoding="utf-8"))
    n_target = clr["discs"]["signal_cells_per_disc"]
    S = s_band_discs(psr, qtab, n_target)
    geo = {r["id"]: r for r in clr["v20_gap"]["per_disc_geometry"]}
    Lrows = []
    for p in clr["per_disc_v18"]:
        if p["pass"] != "20200808":
            continue
        g = geo[p["id"]]
        Lrows.append({"cx": p["cx"], "cy": p["cy"], "class": p["class"], "rule": p["rule"],
                      "median_coherence": p["median_coherence"], "median_N_hat": p["median_N_hat"],
                      "median_min_snr_db": p["median_min_snr_db"], "j": g["median_slant_range_sample"],
                      "inc": g["median_incidence_geometry_deg"], "loc": g["median_lola_local_incidence_deg"]})
    resS = fit_ladder(S, "S-band, pass 1 (no pass term)")
    resL = fit_ladder(Lrows, "L-band, pass 1 (no pass term), for comparison")
    # ---- are the fired sets the same discs?
    def fired(rows, cls):
        return {(r["cx"], r["cy"]) for r in rows if r["class"] == cls and r["rule"] >= 1}

    def allc(rows, cls):
        return {(r["cx"], r["cy"]) for r in rows if r["class"] == cls}
    sets = {}
    for cls in ("inside", "outside", "mixed"):
        fs, fl = fired(S, cls), fired(Lrows, cls)
        both_c = allc(S, cls) & allc(Lrows, cls)
        sets[cls] = {"S_fired": len(fs), "L_fired": len(fl), "fired_in_both": len(fs & fl),
                     "S_only": len(fs - fl), "L_only": len(fl - fs), "union": len(fs | fl),
                     "jaccard": len(fs & fl) / max(len(fs | fl), 1),
                     "discs_in_both_bands_same_class": len(both_c),
                     "expected_overlap_if_independent": len(fs & both_c) * len(fl & both_c) / max(len(both_c), 1),
                     "identical_sets": bool(fs == fl)}
    # a disc that is shadowed in S but has another class (or is absent) in L
    sh_S, sh_L = allc(S, "inside"), allc(Lrows, "inside")
    sets["shadowed_disc_sets"] = {"S": len(sh_S), "L": len(sh_L), "common": len(sh_S & sh_L)}
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    doc["ladder_v20"] = {
        "schema": "lunar-ice/band-s-ladder/1", "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/band_s_ladder_v20.py", "seed": SEED, "bootstrap_B": B,
        "blocks": "5 x 5 disc-lattice blocks (one pass)", "S_band": resS, "L_band_pass1_like_for_like": resL,
        "fired_sets": sets, "run_info": run_info()}
    OUT.write_text(json.dumps(doc, indent=2, default=float), encoding="utf-8")
    for res in (resS, resL):
        print(f"  {res['label']}: {res['discs']} discs, {res['events']} fire; classes {res['classes']}")
        for k, v in res["ladder"].items():
            p = v["psr"]
            print(f"    ({k:>2}) PSR {p['coefficient']:+.3f} +/- {p['se_model']:.3f} (cluster {p['se_cluster_robust']:.3f}) "
                  f"OR {p['odds_ratio']:.2f} model {p['or_ci95_model'][0]:.2f}-{p['or_ci95_model'][1]:.2f}, "
                  f"cluster {p['or_ci95_cluster_robust'][0]:.2f}-{p['or_ci95_cluster_robust'][1]:.2f}, "
                  f"block bootstrap {p['block_bootstrap']['or_ci95'][0]:.2f}-{p['block_bootstrap']['or_ci95'][1]:.2f} "
                  f"[{p['block_bootstrap']['replicates_used']}]")
        u = res["unadjusted"]
        print(f"    unadjusted OR {u['or']:.2f} Woolf {u['ci95_woolf'][0]:.2f}-{u['ci95_woolf'][1]:.2f}, block bootstrap "
              f"{u['block_bootstrap']['or_ci95'][0]:.2f}-{u['block_bootstrap']['or_ci95'][1]:.2f}")
        m = res["mantel_haenszel_coherence_strata"]
        print(f"    MH {m['or']:.3f} RBG {m['ci95'][0]:.2f}-{m['ci95'][1]:.2f}, block bootstrap "
              f"{m['block_bootstrap']['or_ci95'][0]:.2f}-{m['block_bootstrap']['or_ci95'][1]:.2f}")
        print("    intervals excluding 1:", {k: v for k, v in res["interval_excludes_1"].items()
                                              if any(v.values())})
    print("  fired sets:", json.dumps(sets))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
