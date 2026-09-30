"""
crater_ladder_v20.py -- the shadow-versus-sunlit contrast of the 1888 discs
done without the mediator and with spatial dependence. (v20 gap pass, G-A and
the model-(e) half of G-D)

    python backend/scripts/crater_ladder_v20.py

Merged into docs/crater_level_real.json under `v20_gap` (seed 20260930).

WHY
---
v19 says "at matched coherence shadowed discs fire no more often than sunlit
ones". Coherence is a depolarization proxy and the rule thresholds DOP, so
adjusting for it removes any effect of ice on polarization, and the printed
Mantel-Haenszel interval and logistic SEs treat the 1888 discs as independent.

WHAT
----
Outcome: the disc fires (at least one published-rule selection). "Shadowed"
is class inside the LOLA PSR, "sunlit" is class outside; mixed discs enter the
logistic models as their own class and are excluded from every odds ratio.

  unadjusted   the crude odds ratio, per pass (counts; Haldane-Anscombe where
               a cell is empty) and pooled with a pass term (Mantel-Haenszel
               over passes, and the logistic of model (a)).
  ladder       logistic models, each reported with the PSR coefficient, its
               model SE, the odds ratio, and a cluster-robust SE (sandwich,
               clusters = the 5 x 5 disc-lattice blocks):
                 (a)  pass + class
                 (b)  (a) + ln N-hat
                 (b2) (b) + median min SNR
                 (c)  (b2) + median coherence   <- the published specification
                      (v18a: -0.401 +/- 0.378); reproduced here to 3 decimals
                 (d)  (c) + spatial trend (cx/100, cy/100)
                 (e)  (c) + the slant-range sample, the geometry file's
                      incidence angle and the LOLA local incidence of the
                      disc's cells (G-D; present once gap_v20_frame.py has
                      written `per_disc_geometry`)
  bootstrap    blocks of 5 x 5 discs per pass resampled with replacement,
               B = 2000, one resample per replicate shared by every statistic:
               percentile 95 % intervals of the PSR odds ratio in every
               model, of the Mantel-Haenszel odds ratio (all passes; pass 1)
               and of the unadjusted odds ratios. A replicate whose logistic
               does not converge (separation) is counted and left out.

INTERPRETATION (stored in the artifact)
  The coefficient of model (a) is a TOTAL-effect estimate of shadow: it
  contains whatever shadow does to the discs' polarization. Adding coherence
  (model (c)) estimates the DIRECT effect not mediated by coherence, and
  coherence is itself a depolarization measure on the rule's own axis, so
  (c) removes by construction any effect of ice on polarization.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
ART = BASE_DIR / "docs" / "crater_level_real.json"
SEED = 20260930
B = 2000
BLOCK = 5

#: the values the requester computed with gap_calc.py, to be confirmed or
#: corrected (PSR coefficient, SE where given)
REQUESTED = {"a": (0.582, 0.210), "b": (0.256, 0.223), "c": (-0.401, 0.378), "d": (-0.322, 0.395)}

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def irls(X, y, iters=100):
    """Logistic regression by Newton steps with step halving. Returns
    (beta, cov, loglik, converged)."""
    b = np.zeros(X.shape[1])
    ll_old = -np.inf
    ok = False
    for _ in range(iters):
        eta = np.clip(X @ b, -40, 40)
        mu = 1 / (1 + np.exp(-eta))
        W = mu * (1 - mu) + 1e-12
        H = X.T @ (X * W[:, None]) + 1e-10 * np.eye(X.shape[1])
        try:
            step = np.linalg.solve(H, X.T @ (y - mu))
        except np.linalg.LinAlgError:
            return b, None, -np.inf, False
        t = 1.0
        while t > 1e-4:
            nb = b + t * step
            e2 = np.clip(X @ nb, -40, 40)
            ll = float(np.sum(y * e2 - np.logaddexp(0, e2)))
            if ll >= ll_old - 1e-12:
                break
            t /= 2
        b, ll_old = nb, ll
        if np.abs(t * step).max() < 1e-9:
            ok = True
            break
    eta = np.clip(X @ b, -40, 40)
    mu = 1 / (1 + np.exp(-eta))
    W = mu * (1 - mu) + 1e-12
    H = X.T @ (X * W[:, None]) + 1e-10 * np.eye(X.shape[1])
    cov = np.linalg.inv(H)
    # separation shows as a runaway standard error, not as a large coefficient
    # (the published fit has a coherence coefficient of -22.5)
    return b, cov, ll_old, bool(ok and np.sqrt(np.diag(cov)).max() < 50)


def cluster_cov(X, y, b, cov, groups):
    """Sandwich covariance with clusters, finite-sample G/(G-1) factor."""
    mu = 1 / (1 + np.exp(-np.clip(X @ b, -40, 40)))
    s = X * (y - mu)[:, None]
    ug = np.unique(groups)
    meat = np.zeros((X.shape[1], X.shape[1]))
    for g in ug:
        sg = s[groups == g].sum(axis=0)
        meat += np.outer(sg, sg)
    G = len(ug)
    return cov @ meat @ cov * (G / (G - 1.0))


def mh_or(a, b, c, d):
    """Mantel-Haenszel odds ratio and its Robins-Breslow-Greenland interval (two-sided, level 0.95)
    over strata given as arrays of exposed fires / not, unexposed fires / not."""
    a, b, c, d = (np.asarray(v, float) for v in (a, b, c, d))
    n = a + b + c + d
    keep = n > 0
    a, b, c, d, n = a[keep], b[keep], c[keep], d[keep], n[keep]
    R, S = a * d / n, b * c / n
    if S.sum() <= 0 or R.sum() <= 0:
        return {"or": float("nan"), "ci95": [float("nan")] * 2, "se_log_or": float("nan")}
    P, Q = (a + d) / n, (b + c) / n
    Rs, Ss = R.sum(), S.sum()
    var = (np.sum(P * R) / (2 * Rs ** 2) + np.sum(P * S + Q * R) / (2 * Rs * Ss) + np.sum(Q * S) / (2 * Ss ** 2))
    se = float(np.sqrt(var))
    o = float(Rs / Ss)
    return {"or": o, "ci95": [float(np.exp(np.log(o) - 1.96 * se)), float(np.exp(np.log(o) + 1.96 * se))],
            "se_log_or": se}


def crude_or(ins_fire, ins_n, out_fire, out_n):
    """Odds ratio of shadowed against sunlit from counts; Haldane-Anscombe
    (+ 0.5 in every cell) and a Woolf interval when a cell is empty."""
    a, b = ins_fire, ins_n - ins_fire
    c, d = out_fire, out_n - out_fire
    hal = min(a, b, c, d) == 0
    if hal:
        a, b, c, d = a + 0.5, b + 0.5, c + 0.5, d + 0.5
    o = (a * d) / (b * c)
    se = float(np.sqrt(1 / a + 1 / b + 1 / c + 1 / d))
    return {"or": float(o), "ci95_woolf": [float(np.exp(np.log(o) - 1.96 * se)), float(np.exp(np.log(o) + 1.96 * se))],
            "counts": {"shadowed_fires": int(ins_fire), "shadowed_n": int(ins_n),
                       "sunlit_fires": int(out_fire), "sunlit_n": int(out_n)},
            "haldane_anscombe_correction": bool(hal)}


def pct_with_se(v, q):
    """Percentile and its Monte Carlo SE (the asymptotic sqrt(q(1-q)/B) /
    density at the quantile, the density from a kernel estimate)."""
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    x = float(np.percentile(v, 100 * q))
    h = 1.06 * v.std() * len(v) ** -0.2 + 1e-12
    dens = float(np.mean(np.exp(-0.5 * ((v - x) / h) ** 2) / (h * np.sqrt(2 * np.pi))))
    return x, float(np.sqrt(q * (1 - q) / len(v)) / max(dens, 1e-12))


def interval(v, exp=False):
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    lo, lo_se = pct_with_se(v, 0.025)
    hi, hi_se = pct_with_se(v, 0.975)
    f = np.exp if exp else (lambda z: z)
    return {"ci95": [float(f(lo)), float(f(hi))], "ci95_mc_se_on_coefficient_scale": [lo_se, hi_se],
            "replicates_used": int(len(v)), "sd": float(v.std())}


def main() -> int:
    doc = json.loads(ART.read_text(encoding="utf-8"))
    P = doc["per_disc_v18"]
    n = len(P)
    arr = lambda k: np.array([p[k] for p in P], float)  # noqa: E731
    cls = np.array([p["class"] for p in P])
    ps = np.array([p["pass"] for p in P])
    y = (np.array([p["rule"] for p in P]) >= 1).astype(float)
    coh, lnN, snr = arr("median_coherence"), np.log(arr("median_N_hat")), arr("median_min_snr_db")
    cx, cy = arr("cx"), arr("cy")
    p2 = (ps == "20200305").astype(float)
    inside, mixed = (cls == "inside").astype(float), (cls == "mixed").astype(float)
    outside = cls == "outside"
    ins_b = cls == "inside"
    p1 = ps == "20200808"
    keys = [(p["pass"], p["cx"] // BLOCK, p["cy"] // BLOCK) for p in P]
    ukeys = sorted(set(keys))
    kid = {k: i for i, k in enumerate(ukeys)}
    groups = np.array([kid[k] for k in keys])
    idx = [np.flatnonzero(groups == g) for g in range(len(ukeys))]

    geo = doc.get("v20_gap", {}).get("per_disc_geometry")
    models = {
        "a": ("pass + class", [p2, inside, mixed]),
        "b": ("(a) + ln N-hat", [p2, inside, mixed, lnN]),
        "b2": ("(b) + median min SNR", [p2, inside, mixed, lnN, snr]),
        "c": ("(b2) + median coherence = the published specification", [p2, inside, mixed, coh, lnN, snr]),
        "d": ("(c) + spatial trend (cx/100, cy/100)", [p2, inside, mixed, coh, lnN, snr, cx / 100.0, cy / 100.0]),
    }
    if geo:
        g = {r["id"]: r for r in geo}
        ids = [p["id"] for p in P]
        J = np.array([g[i]["median_slant_range_sample"] for i in ids], float)
        INC = np.array([g[i]["median_incidence_geometry_deg"] for i in ids], float)
        LOC = np.array([g[i]["median_lola_local_incidence_deg"] for i in ids], float)
        models["e"] = ("(c) + slant-range sample/100, geometry-file incidence, LOLA local incidence",
                       [p2, inside, mixed, coh, lnN, snr, J / 100.0, INC, LOC])
        models["e0"] = ("(a) + slant-range sample/100, geometry-file incidence, LOLA local incidence "
                        "(geometry without coherence)", [p2, inside, mixed, J / 100.0, INC, LOC])
    names = {"a": ["pass_20200305", "inside", "mixed"]}
    cov_names = {
        "a": ["pass_20200305", "class_inside_psr", "class_mixed"],
        "b": ["pass_20200305", "class_inside_psr", "class_mixed", "ln_median_N_hat"],
        "b2": ["pass_20200305", "class_inside_psr", "class_mixed", "ln_median_N_hat", "median_min_snr_db"],
        "c": ["pass_20200305", "class_inside_psr", "class_mixed", "median_coherence", "ln_median_N_hat",
              "median_min_snr_db"],
        "d": ["pass_20200305", "class_inside_psr", "class_mixed", "median_coherence", "ln_median_N_hat",
              "median_min_snr_db", "cx_over_100", "cy_over_100"],
        "e": ["pass_20200305", "class_inside_psr", "class_mixed", "median_coherence", "ln_median_N_hat",
              "median_min_snr_db", "slant_range_sample_over_100", "incidence_geometry_deg",
              "lola_local_incidence_deg"],
        "e0": ["pass_20200305", "class_inside_psr", "class_mixed", "slant_range_sample_over_100",
               "incidence_geometry_deg", "lola_local_incidence_deg"],
    }

    def design(cols, sel=None):
        X = np.column_stack([np.ones(n)] + cols)
        return X if sel is None else X[sel]

    ladder = {}
    fits = {}
    for key, (label, cols) in models.items():
        X = design(cols)
        b, cov, ll, conv = irls(X, y)
        se = np.sqrt(np.diag(cov))
        ccov = cluster_cov(X, y, b, cov, groups)
        cse = np.sqrt(np.diag(ccov))
        names_k = ["intercept"] + cov_names[key]
        coefs = {nm: {"estimate": float(b[i]), "se_model": float(se[i]), "se_cluster_robust": float(cse[i]),
                      "z_model": float(b[i] / se[i]), "p_two_sided_model": float(2 * (1 - _phi(abs(b[i] / se[i])))),
                      "p_two_sided_cluster": float(2 * (1 - _phi(abs(b[i] / cse[i]))))}
                 for i, nm in enumerate(names_k)}
        i = 2
        ladder[key] = {
            "model": label, "n": n, "events": int(y.sum()), "log_likelihood": ll, "converged": conv,
            "covariates": names_k, "coefficients": coefs,
            "psr": {"coefficient": float(b[i]), "se_model": float(se[i]), "se_cluster_robust": float(cse[i]),
                    "odds_ratio": float(np.exp(b[i])),
                    "or_ci95_model": [float(np.exp(b[i] - 1.96 * se[i])), float(np.exp(b[i] + 1.96 * se[i]))],
                    "or_ci95_cluster_robust": [float(np.exp(b[i] - 1.96 * cse[i])),
                                               float(np.exp(b[i] + 1.96 * cse[i]))]},
        }
        if key in ("b2", "c", "d", "e"):
            ladder[key]["coherence"] = {} if "median_coherence" not in coefs else {
                "coefficient": coefs["median_coherence"]["estimate"],
                "se_model": coefs["median_coherence"]["se_model"],
                "se_cluster_robust": coefs["median_coherence"]["se_cluster_robust"]}
        fits[key] = (X, b)

    # -------- unadjusted contrast
    def counts(sel):
        return (int(((y == 1) & ins_b & sel).sum()), int((ins_b & sel).sum()),
                int(((y == 1) & outside & sel).sum()), int((outside & sel).sum()))
    unadj = {"pass_20200808": crude_or(*counts(p1)), "pass_20200305": crude_or(*counts(~p1)),
             "pooled_crude_no_pass_term": crude_or(*counts(np.ones(n, bool)))}
    sa = [counts(p1), counts(~p1)]
    mhp = mh_or([s[0] for s in sa], [s[1] - s[0] for s in sa], [s[2] for s in sa], [s[3] - s[2] for s in sa])
    unadj["pooled_mantel_haenszel_over_passes"] = mhp
    unadj["pooled_logistic_pass_and_class"] = {"model": "(a)", **ladder["a"]["psr"]}

    # -------- coherence-stratified Mantel-Haenszel (the published one)
    cbins = np.digitize(coh, [0.4, 0.5, 0.6])

    def mh_coh(sel):
        a, b_, c, d = [], [], [], []
        for s in range(4):
            m = sel & (cbins == s)
            a.append(((y == 1) & ins_b & m).sum()); b_.append(((y == 0) & ins_b & m).sum())
            c.append(((y == 1) & outside & m).sum()); d.append(((y == 0) & outside & m).sum())
        return a, b_, c, d
    mh_pub = {"all": mh_or(*mh_coh(np.ones(n, bool))), "20200808": mh_or(*mh_coh(p1))}

    # -------- block bootstrap
    rng = np.random.default_rng(SEED)
    boot = {k: [] for k in models}
    boot_all = {k: [] for k in models}
    boot_mh = {"all": [], "20200808": []}
    boot_un = {"pass_20200808": [], "pooled_mh_over_passes": [], "pooled_crude": []}
    fails = {k: 0 for k in models}
    n_pass2_empty = 0
    for _ in range(B):
        pick = rng.integers(0, len(ukeys), len(ukeys))
        ii = np.concatenate([idx[k] for k in pick])
        yy, cl, pp, cb = y[ii], cls[ii], ps[ii], cbins[ii]
        insb, outb = cl == "inside", cl == "outside"
        # A resample with no firing disc on pass 2 separates the pass-2 dummy
        # (its coefficient runs to -infinity). The other coefficients have a
        # well-defined limit: the fit on pass 1 alone with the dummy dropped.
        # That limit is used (and counted), not a runaway iterate.
        pass2_empty = bool(yy[pp == "20200305"].sum() == 0)
        n_pass2_empty += pass2_empty
        for key in models:
            X, _ = fits[key]
            Xb, yb = X[ii], yy
            col = 2
            if pass2_empty:
                keep = pp == "20200808"
                Xb, yb = np.delete(Xb[keep], 1, axis=1), yy[keep]
                col = 1
            bb, _c, _l, conv = irls(Xb, yb)
            if conv:
                boot[key].append(bb[col])
                full_b = np.insert(bb, 1, np.nan) if pass2_empty else bb
                boot_all[key].append(full_b)
            else:
                fails[key] += 1

        def cnt(m):
            return [((yy == 1) & insb & m).sum(), ((yy == 0) & insb & m).sum(),
                    ((yy == 1) & outb & m).sum(), ((yy == 0) & outb & m).sum()]
        for scope, sm in (("all", np.ones(len(ii), bool)), ("20200808", pp == "20200808")):
            A = np.array([cnt(sm & (cb == s)) for s in range(4)], float)
            n_ = A.sum(axis=1)
            Rn = np.sum(A[:, 0] * A[:, 3] / np.where(n_ > 0, n_, 1))
            Sn = np.sum(A[:, 1] * A[:, 2] / np.where(n_ > 0, n_, 1))
            boot_mh[scope].append(np.log(Rn / Sn) if Sn > 0 and Rn > 0 else np.nan)
        A1 = np.array(cnt(pp == "20200808"), float)
        boot_un["pass_20200808"].append(np.log(A1[0] * A1[3] / (A1[1] * A1[2])) if A1[1] * A1[2] > 0 and A1[0] * A1[3] > 0 else np.nan)
        A2 = np.array(cnt(pp == "20200305"), float)
        st = np.array([A1, A2])
        nn = st.sum(axis=1)
        Rn = np.sum(st[:, 0] * st[:, 3] / nn)
        Sn = np.sum(st[:, 1] * st[:, 2] / nn)
        boot_un["pooled_mh_over_passes"].append(np.log(Rn / Sn) if Sn > 0 and Rn > 0 else np.nan)
        At = A1 + A2
        boot_un["pooled_crude"].append(np.log(At[0] * At[3] / (At[1] * At[2])) if At[1] * At[2] > 0 and At[0] * At[3] > 0 else np.nan)

    for key in models:
        arr = np.array(boot_all[key])
        for i, nm in enumerate(["intercept"] + cov_names[key]):
            col_ = arr[:, i]
            col_ = col_[np.isfinite(col_)]
            ladder[key]["coefficients"][nm]["block_bootstrap"] = {
                "ci95": [float(np.percentile(col_, 2.5)), float(np.percentile(col_, 97.5))],
                "sd": float(col_.std()), "replicates_used": int(col_.size)}
        ladder[key]["psr"]["block_bootstrap"] = {"B": B, "non_converged": fails[key],
                                                 "replicates_with_no_pass2_event_fit_on_pass1": n_pass2_empty,
                                                 **interval(boot[key], exp=False)}
        ladder[key]["psr"]["block_bootstrap"]["or_ci95"] = [float(np.exp(v)) for v in
                                                           ladder[key]["psr"]["block_bootstrap"]["ci95"]]
    for scope in mh_pub:
        mh_pub[scope]["block_bootstrap"] = {"B": B, **interval(boot_mh[scope], exp=False)}
        mh_pub[scope]["block_bootstrap"]["or_ci95"] = [float(np.exp(v)) for v in
                                                      mh_pub[scope]["block_bootstrap"]["ci95"]]
    for k_, v_ in boot_un.items():
        tgt = unadj["pass_20200808"] if k_ == "pass_20200808" else (
            unadj["pooled_mantel_haenszel_over_passes"] if k_ == "pooled_mh_over_passes" else unadj["pooled_crude_no_pass_term"])
        tgt["block_bootstrap"] = {"B": B, **interval(v_, exp=False)}
        tgt["block_bootstrap"]["or_ci95"] = [float(np.exp(v)) for v in tgt["block_bootstrap"]["ci95"]]

    # -------- check against the requested values
    check = {}
    for k, (cf, se) in REQUESTED.items():
        got = ladder[k]["psr"]
        check[k] = {"requested_coefficient": cf, "requested_se": se, "computed_coefficient": got["coefficient"],
                    "computed_se_model": got["se_model"],
                    "coefficient_agrees_to_3_decimals": bool(abs(round(got["coefficient"], 3) - cf) < 1e-9),
                    "se_agrees_to_3_decimals": bool(abs(round(got["se_model"], 3) - se) < 1e-9)}
    check["published_v18a"] = {"coefficient": -0.4007800695710975, "se": 0.3783491896114816,
                              "reproduced": bool(abs(ladder["c"]["psr"]["coefficient"] - (-0.4007800695710975)) < 1e-6
                                                 and abs(ladder["c"]["psr"]["se_model"] - 0.3783491896114816) < 1e-6)}

    wording = ("The coefficient of model (a) is a TOTAL-effect estimate of shadow: it contains whatever "
               "shadow does to the discs' polarization. The coefficient after adjusting for median coherence "
               "(models (c) to (e)) is a DIRECT-effect estimate, the part of shadow not mediated by coherence; "
               "coherence is a depolarization measure on the axis the rule thresholds, so the adjustment removes "
               "by construction any effect of ice on polarization. Neither is a false-positive rate: sunlit "
               "terrain is not a proven ice-free null.")
    out = {
        "schema": "lunar-ice/crater-ladder/1", "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/crater_ladder_v20.py", "seed": SEED, "bootstrap_B": B,
        "blocks": {"definition": f"{BLOCK} x {BLOCK} disc-lattice blocks per pass", "count": len(ukeys)},
        "outcome": "disc has >= 1 published-rule selection", "n": n, "events": int(y.sum()),
        "interpretation": wording, "unadjusted": unadj, "ladder": ladder,
        "mantel_haenszel_coherence_strata": mh_pub,
        "requested_values_check": check,
    }
    if geo:
        out["per_disc_geometry"] = geo
        out["per_disc_geometry_source"] = doc["v20_gap"].get("per_disc_geometry_source")
    for k in ("geometry_frame", "geometry_frame_source"):
        if k in doc.get("v20_gap", {}):
            out[k] = doc["v20_gap"][k]
    doc["v20_gap"] = out
    doc["run_info_v20_gap"] = run_info()
    ART.write_text(json.dumps(doc, indent=2, default=float), encoding="utf-8")

    print(f"  n {n}, events {int(y.sum())}, blocks {len(ukeys)}")
    for k in models:
        r = ladder[k]["psr"]
        bs = r["block_bootstrap"]
        print(f"  ({k:>2}) PSR {r['coefficient']:+.3f} +/- {r['se_model']:.3f} (cluster {r['se_cluster_robust']:.3f})  "
              f"OR {r['odds_ratio']:.2f} ({r['or_ci95_model'][0]:.2f}-{r['or_ci95_model'][1]:.2f}); "
              f"block bootstrap OR {bs['or_ci95'][0]:.2f}-{bs['or_ci95'][1]:.2f}  [{bs['replicates_used']} replicates]")
    print(f"  MH all {mh_pub['all']['or']:.3f} (RBG {mh_pub['all']['ci95'][0]:.2f}-{mh_pub['all']['ci95'][1]:.2f}); "
          f"block bootstrap {mh_pub['all']['block_bootstrap']['or_ci95'][0]:.2f}-"
          f"{mh_pub['all']['block_bootstrap']['or_ci95'][1]:.2f}")
    print(f"  MH pass 1 {mh_pub['20200808']['or']:.3f} (RBG {mh_pub['20200808']['ci95'][0]:.2f}-"
          f"{mh_pub['20200808']['ci95'][1]:.2f}); block bootstrap "
          f"{mh_pub['20200808']['block_bootstrap']['or_ci95'][0]:.2f}-{mh_pub['20200808']['block_bootstrap']['or_ci95'][1]:.2f}")
    print(f"  unadjusted OR pass 1 {unadj['pass_20200808']['or']:.2f}; pooled MH over passes "
          f"{unadj['pooled_mantel_haenszel_over_passes']['or']:.2f}; logistic (a) {ladder['a']['psr']['odds_ratio']:.2f}")
    print(f"  published spec reproduced: {check['published_v18a']['reproduced']}")
    return 0


def _phi(x):
    from math import erf, sqrt
    return 0.5 * (1 + erf(x / sqrt(2)))


if __name__ == "__main__":
    raise SystemExit(main())
