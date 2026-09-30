"""
tail_calibration_ci.py -- intervals on the held-out tail calibration, and whether
"11 of 109 blocks above nominal" is consistent with exact calibration.
(council work order, Task 6)

    python backend/scripts/tail_calibration_ci.py
    python backend/scripts/tail_calibration_ci.py --logratio-model-coherence   (v20 G-G: the
        same held-out test beside a coherence-aware N_hat; adds the critical-value
        inflation and look-count deflation that make the size nominal; merged)
    python backend/scripts/tail_calibration_ci.py --logratio-model   (v18a N5: the
        held-out test of F(2 N_hat, 2 N_hat) with the log-ratio N_hat; merged)

Reads stokes_from_slc.json::results.t3e.180_deg.tail_calibration.per_block.

1. Block-bootstrap 95 % intervals (blocks resampled with replacement, B = 10 000)
   on the median-over-blocks and the pooled rejection rates at nominal 1, 5
   and 10 %.
2. Under EXACT calibration a block's held-out rejection count is binomial at
   the nominal rate -- but over correlated cells. Each block's effective count
   n_eff = n_test / A_b, with A_b the block's own integrated autocorrelation
   area of ln CPR (stokes_from_slc.py records it per block). Then
   P(block above nominal) = P(Bin(n_eff, alpha) > alpha n_eff) per block, the
   number of blocks above nominal is Poisson-binomial over the blocks, and the
   observed count is set against that exact distribution (both tails). The
   pooled rate is tested the same way with the summed effective count.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.stats import binom, norm

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "tail_calibration_ci.json"
SEED = 20261004
B = 10_000
SOURCES = {"20200808_64px": "docs/stokes_from_slc.json",
           "20200808_32px": "docs/stokes_from_slc_block32.json",
           "20200305_32px": "docs/stokes_from_slc_20200305_block32.json"}

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def poisson_binomial(p: np.ndarray) -> np.ndarray:
    d = np.zeros(p.size + 1)
    d[0] = 1.0
    for q in p:
        d[1:] = d[1:] * (1 - q) + d[:-1] * q
        d[0] *= (1 - q)
    return d


def analyse(per: list, rng) -> dict:
    n = np.array([b["n_test"] for b in per], dtype=float)
    area = np.array([b["corr_area_px"] for b in per], dtype=float)
    neff = n / np.maximum(area, 1.0)
    out = {"blocks": len(per), "n_test_total": int(n.sum()),
           "corr_area_px": {"median": float(np.median(area)),
                            "iqr": [float(np.percentile(area, 25)), float(np.percentile(area, 75))]},
           "n_eff_per_block": {"median": float(np.median(neff)),
                               "iqr": [float(np.percentile(neff, 25)), float(np.percentile(neff, 75))]},
           "levels": {}}
    idx = rng.integers(0, len(per), (B, len(per)))
    for key, a in (("1pct", 0.01), ("5pct", 0.05), ("10pct", 0.10)):
        rej = np.array([b["rejection"][key] for b in per])
        med_b = np.median(rej[idx], axis=1)
        pool_b = (rej[idx] * n[idx]).sum(axis=1) / n[idx].sum(axis=1)
        pooled = float((rej * n).sum() / n.sum())
        above = int((rej > a).sum())
        # exact calibration: per-block P(above), Poisson-binomial count
        ne = np.maximum(np.rint(neff).astype(int), 1)
        p_above = np.array([1.0 - binom.cdf(np.floor(a * k), k, a) for k in ne])
        dist = poisson_binomial(p_above)
        cdf = np.cumsum(dist)
        p_low = float(cdf[above])
        p_high = float(1.0 - (cdf[above - 1] if above > 0 else 0.0))
        # pooled rate against the nominal, effective count summed
        neff_tot = float(neff.sum())
        z = (pooled - a) / np.sqrt(a * (1 - a) / neff_tot)
        out["levels"][key] = {
            "nominal": a,
            "median_over_blocks": float(np.median(rej)),
            "median_ci95": [float(np.percentile(med_b, 2.5)), float(np.percentile(med_b, 97.5))],
            "pooled": pooled,
            "pooled_ci95": [float(np.percentile(pool_b, 2.5)), float(np.percentile(pool_b, 97.5))],
            "blocks_above_nominal": above,
            "expected_above_if_exactly_calibrated": float(dist @ np.arange(dist.size)),
            "p_value_this_few_or_fewer": p_low,
            "p_value_this_many_or_more": p_high,
            "pooled_vs_nominal_z": float(z),
            "pooled_vs_nominal_p_two_sided": float(2 * norm.sf(abs(z))),
            "verdict": ("fewer blocks above nominal than exact calibration predicts: the "
                        "model is conservative here" if p_low < 0.025 else
                        "more blocks above nominal than exact calibration predicts: the "
                        "model is anti-conservative here" if p_high < 0.025 else
                        "consistent with exact calibration")}
    return out


SEED_LR = 20261012
PASS_OF = {"20200808_64px": ("20200808", 64), "20200808_32px": ("20200808", 32),
           "20200305_32px": ("20200305", 32)}


def logratio_model() -> dict:
    """v18a N5: the held-out test of the model the decisions use,
    F(2 N_hat, 2 N_hat) with N_hat from Var(ln R), on the same blocks.
    Each block is split by rows; N_hat (Var ln R, ddof 1) and the median CPR
    are estimated on one half and the other half is tested at 1, 5 and 10 %:
    z = R / median x F^-1_0.5(2 N_hat, 2 N_hat), rejected above
    F^-1_(1-alpha)(2 N_hat, 2 N_hat); two folds, pooled. The effective count
    per block reuses the block's own correlation area of ln CPR."""
    import stokes_from_slc as SFS
    from scipy.stats import f as Fdist
    import enl_logratio as L
    rng = np.random.default_rng(SEED_LR)
    out, cache = {}, {}
    for tag, rel in SOURCES.items():
        pid, k = PASS_OF[tag]
        per_src = json.loads((BASE_DIR / rel).read_text(encoding="utf-8"))["results"]["t3e"]["180_deg"][
            "tail_calibration"].get("per_block", [])
        if not per_src:
            out[tag] = {"blocks": 0}
            continue
        if pid not in cache:
            SFS.configure(pid)
            hh, vv, hv, _ = SFS.build_coherency(0)
            s0, s3 = hh + vv, -2.0 * hv.imag
            m = (hh > 0) & (vv > 0) & (s0 > 0)
            cpr = SFS.cpr_from(s0, s3, m)
            cache = {pid: (cpr, m)}
            del hh, vv, hv, s0, s3
        cpr, m = cache[pid]
        per = []
        for b in per_src:
            r0, c0 = b["row"], b["col"]
            bc, bm = cpr[r0:r0 + k, c0:c0 + k], m[r0:r0 + k, c0:c0 + k]
            rej = {a: 0 for a in NOMINAL}
            n_test = 0
            nh_folds = []
            for tr, te in ((slice(0, k // 2), slice(k // 2, k)), (slice(k // 2, k), slice(0, k // 2))):
                ctr = bc[tr][bm[tr]]
                ctr = ctr[np.isfinite(ctr) & (ctr > 0)]
                cte = bc[te][bm[te]]
                cte = cte[np.isfinite(cte) & (cte > 0)]
                if ctr.size < 30 or cte.size < 30:
                    continue
                nh = float(L.n_from_var(np.var(np.log(ctr), ddof=1)))
                nh_folds.append(nh)
                med = float(np.median(ctr))
                z = cte / med * Fdist.ppf(0.5, 2 * nh, 2 * nh)
                for a in NOMINAL:
                    rej[a] += int((z > Fdist.ppf(1 - a, 2 * nh, 2 * nh)).sum())
                n_test += int(cte.size)
            if n_test == 0:
                continue
            per.append({"row": r0, "col": c0, "n_test": n_test, "corr_area_px": b["corr_area_px"],
                        "N_hat_folds": nh_folds,
                        "rejection": {f"{int(100 * a)}pct": rej[a] / n_test for a in NOMINAL}})
        res = analyse(per, rng)
        nh_all = [x for b in per for x in b["N_hat_folds"]]
        res["N_hat_train_halves"] = {"median": float(np.median(nh_all)),
                                     "iqr": [float(np.percentile(nh_all, 25)), float(np.percentile(nh_all, 75))]}
        out[tag] = {"source_blocks": rel, **res}
        for key, v in res["levels"].items():
            print(f"  log-ratio model {tag} {key}: pooled {100 * v['pooled']:.2f} % "
                  f"[{100 * v['pooled_ci95'][0]:.2f}, {100 * v['pooled_ci95'][1]:.2f}], median "
                  f"{100 * v['median_over_blocks']:.2f} %; above nominal {v['blocks_above_nominal']} vs "
                  f"{v['expected_above_if_exactly_calibrated']:.1f} -> {v['verdict']}", flush=True)
    return {"model": ("F(2 N_hat, 2 N_hat), N_hat from Var(ln R) (ddof 1) on the training half, scaled to "
                      "the training half's median CPR; the model the decision rule uses"),
            "split": "each block by rows, two folds (top -> bottom, bottom -> top), pooled",
            "seed": SEED_LR, "bootstrap_B": B, "results": out}


NOMINAL = (0.01, 0.05, 0.10)
B_INFL = 1000


def logratio_model_coherence() -> dict:
    """v20 G-G: the held-out test of F(2 N_hat, 2 N_hat) again, now beside a
    coherence-aware N-hat (coherence_nhat.py) and the correlated-ratio law it
    implies. Same 109 blocks (and the 32 x 32 ones), same two row folds, same
    statistic z = R / median x q_0.5; both estimators in one pass so the
    comparison is paired. Reports the held-out size at 1 / 5 / 10 %, and, where
    it is not nominal, the critical-value inflation c (reject above c x q_(1-a))
    and the look-count deflation nu (N-hat / nu in the test) that make the
    pooled held-out size equal the nominal level, c with a block-bootstrap
    interval, nu as a point solve."""
    import stokes_from_slc as SFS
    from scipy.optimize import brentq
    import enl_logratio as L
    import coherence_nhat as CN
    out, cache = {}, {}
    for tag, rel in SOURCES.items():
        pid, k = PASS_OF[tag]
        per_src = json.loads((BASE_DIR / rel).read_text(encoding="utf-8"))["results"]["t3e"]["180_deg"][
            "tail_calibration"].get("per_block", [])
        if not per_src:
            out[tag] = {"blocks": 0}
            continue
        if pid not in cache:
            SFS.configure(pid)
            hh, vv, hv, _ = SFS.build_coherency(0)
            s0, s1, s2, s3 = hh + vv, hh - vv, 2.0 * hv.real, -2.0 * hv.imag
            m = (hh > 0) & (vv > 0) & (s0 > 0)
            cpr = SFS.cpr_from(s0, s3, m).astype(np.float64)
            den = s0 ** 2 - s3 ** 2
            g2 = np.where(m & (den > 0), (s1 ** 2 + s2 ** 2) / np.where(den > 0, den, 1.0), np.nan)
            cache = {pid: (cpr, g2, m)}
            del hh, vv, hv, s0, s1, s2, s3, den
        cpr, g2, m = cache[pid]
        est = {"standard": [], "coherence_aware": []}
        per = {"standard": [], "coherence_aware": []}
        kap_all = []
        for b in per_src:
            r0, c0 = b["row"], b["col"]
            bc, bg, bm = cpr[r0:r0 + k, c0:c0 + k], g2[r0:r0 + k, c0:c0 + k], m[r0:r0 + k, c0:c0 + k]
            rej = {e: {a: 0 for a in NOMINAL} for e in per}
            n_test = {e: 0 for e in per}
            folds = {e: [] for e in per}
            for tr, te in ((slice(0, k // 2), slice(k // 2, k)), (slice(k // 2, k), slice(0, k // 2))):
                sel_tr, sel_te = bm[tr], bm[te]
                ctr, gtr = bc[tr][sel_tr], bg[tr][sel_tr]
                good = np.isfinite(ctr) & (ctr > 0)
                ctr, gtr = ctr[good], gtr[good]
                cte = bc[te][sel_te]
                cte = cte[np.isfinite(cte) & (cte > 0)]
                if ctr.size < 30 or cte.size < 30:
                    continue
                v = float(np.var(np.log(ctr), ddof=1))
                med = float(np.median(ctr))
                zr = cte / med
                nh_s = float(L.n_from_var(v))
                nh_a, kap = CN.nhat_aware(v, float(np.nanmean(gtr)))
                kap_all.append(kap)
                for e, nh, kp in (("standard", nh_s, 0.0), ("coherence_aware", nh_a, kap)):
                    q = CN.ratio_quantiles((0.5, 0.99, 0.95, 0.90), nh, kp)
                    z = zr * q[0]
                    for a, thr in zip(NOMINAL, (q[1], q[2], q[3])):
                        rej[e][a] += int((z > thr).sum())
                    n_test[e] += int(cte.size)
                    folds[e].append((zr, nh, kp))
                    est[e].append(nh)
            for e in per:
                if n_test[e]:
                    per[e].append({"row": r0, "col": c0, "n_test": n_test[e], "corr_area_px": b["corr_area_px"],
                                   "rejection": {f"{int(100 * a)}pct": rej[e][a] / n_test[e] for a in NOMINAL},
                                   "_folds": folds[e]})
        res = {}
        for e in per:
            rng = np.random.default_rng(SEED_LR + 1)
            r = analyse([{kk: vv_ for kk, vv_ in b.items() if kk != "_folds"} for b in per[e]], rng)
            r["N_hat_train_halves"] = {"median": float(np.median(est[e])),
                                       "iqr": [float(np.percentile(est[e], 25)), float(np.percentile(est[e], 75))]}
            infl = {}
            for a in NOMINAL:
                key = f"{int(100 * a)}pct"
                ratios = []
                for b in per[e]:
                    rr = []
                    for zr, nh, kp in b["_folds"]:
                        q = CN.ratio_quantiles((0.5, 1 - a), nh, kp)
                        rr.append(zr * q[0] / q[1])
                    ratios.append(np.concatenate(rr))
                allr = np.concatenate(ratios)
                c_hat = float(np.quantile(allr, 1 - a))
                brng = np.random.default_rng(SEED_LR + 2)
                cs = []
                for _ in range(B_INFL):
                    pick = brng.integers(0, len(ratios), len(ratios))
                    cs.append(np.quantile(np.concatenate([ratios[i] for i in pick]), 1 - a))

                def rate_nu(nu, a=a, blocks=per[e]):
                    hit = tot = 0
                    for b in blocks:
                        for zr, nh, kp in b["_folds"]:
                            q = CN.ratio_quantiles((0.5, 1 - a), nh / nu, kp)
                            hit += int((zr * q[0] > q[1]).sum())
                            tot += zr.size
                    return hit / tot - a
                try:
                    nu = float(brentq(rate_nu, 1.0, 4.0, xtol=1e-4))
                except ValueError:
                    nu = None
                infl[key] = {"nominal": a, "pooled_size_now": r["levels"][key]["pooled"],
                             "critical_value_inflation_c": c_hat,
                             "c_ci95_block_bootstrap": [float(np.percentile(cs, 2.5)), float(np.percentile(cs, 97.5))],
                             "c_bootstrap_B": B_INFL, "look_count_deflation_nu": nu}
            r["calibration_adjustment"] = infl
            res[e] = r
        res["kappa_hat_train_halves"] = {"median": float(np.median(kap_all)),
                                         "iqr": [float(np.percentile(kap_all, 25)), float(np.percentile(kap_all, 75))],
                                         "fraction_folds_with_kappa_hat_above_0": float(np.mean(np.array(kap_all) > 0))}
        out[tag] = {"source_blocks": rel, **res}
        for e in ("standard", "coherence_aware"):
            for key, v in res[e]["levels"].items():
                print(f"  {tag} {e:<16} {key}: pooled {100 * v['pooled']:.2f} % "
                      f"[{100 * v['pooled_ci95'][0]:.2f}, {100 * v['pooled_ci95'][1]:.2f}]; above nominal "
                      f"{v['blocks_above_nominal']} vs {v['expected_above_if_exactly_calibrated']:.1f}; "
                      f"c {res[e]['calibration_adjustment'][key]['critical_value_inflation_c']:.3f}", flush=True)
    return {"estimators": {"standard": "N from 2 psi_1(N) = Var(ln R), F(2N, 2N) (the decision model)",
                           "coherence_aware": "N from Var(ln R) and the measured squared coherence "
                                              "(coherence_nhat.py), the correlated-ratio law"},
            "split": "each block by rows, two folds (top -> bottom, bottom -> top), pooled",
            "seed": SEED_LR, "bootstrap_B": B, "results": out}


def main() -> int:
    import sys as _sys
    if "--logratio-model-coherence" in _sys.argv:
        doc = json.loads(OUT.read_text(encoding="utf-8"))
        doc["logratio_model_coherence_aware"] = logratio_model_coherence()
        doc["run_info_logratio_model_coherence_aware"] = run_info()
        OUT.write_text(json.dumps(doc, indent=2, default=float), encoding="utf-8")
        print(f"  merged logratio_model_coherence_aware into {OUT.relative_to(BASE_DIR)}")
        return 0
    import sys as _sys
    if "--logratio-model" in _sys.argv:
        doc = json.loads(OUT.read_text(encoding="utf-8"))
        doc["logratio_model"] = logratio_model()
        doc["run_info_logratio_model"] = run_info()
        OUT.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        print(f"  merged logratio_model into {OUT.relative_to(BASE_DIR)}")
        return 0
    rng = np.random.default_rng(SEED)
    res = {}
    for tag, rel in SOURCES.items():
        p = BASE_DIR / rel
        if not p.is_file():
            res[tag] = {"missing": rel}
            continue
        t = json.loads(p.read_text(encoding="utf-8"))["results"]["t3e"]["180_deg"]["tail_calibration"]
        per = t.get("per_block", [])
        if not per:
            res[tag] = {"blocks": 0, "note": "no blocks on this pass at this size"}
            continue
        res[tag] = {"source": rel, **analyse(per, rng)}
        for k, v in res[tag]["levels"].items():
            print(f"  {tag} {k}: pooled {100 * v['pooled']:.2f} % [{100 * v['pooled_ci95'][0]:.2f}, "
                  f"{100 * v['pooled_ci95'][1]:.2f}], median {100 * v['median_over_blocks']:.2f} % "
                  f"[{100 * v['median_ci95'][0]:.2f}, {100 * v['median_ci95'][1]:.2f}]; above nominal "
                  f"{v['blocks_above_nominal']} vs expected {v['expected_above_if_exactly_calibrated']:.1f} "
                  f"(p<= {v['p_value_this_few_or_fewer']:.2e}, p>= {v['p_value_this_many_or_more']:.2e}) "
                  f"-> {v['verdict']}", flush=True)
    OUT.write_text(json.dumps({
        "schema": "lunar-ice/tail-calibration-ci/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/tail_calibration_ci.py",
        "seed": SEED, "bootstrap_B": B, "unit": "block, resampled with replacement",
        "effective_count": "n_test / the block's integrated autocorrelation area of ln CPR",
        "reference_distribution": ("binomial, at each block's effective sample count: "
                                   "P(block above nominal) = P(Bin(n_eff, alpha) > alpha n_eff); "
                                   "the count of blocks above nominal is Poisson-binomial"),
        "results": res, "run_info": run_info()}, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
