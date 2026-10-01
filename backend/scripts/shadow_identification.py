"""
shadow_identification.py -- is the shadow excess identified? (v21 work order,
W2 A-I)

    python backend/scripts/shadow_identification.py [--workers 6] [--part A,B,C,D,E,F,G,H,I]

Reads docs/disc_table_v21.json (v21_extract.py) and docs/crater_level_real.json,
docs/band_s.json; writes docs/shadow_identification.json, fig_spec_curve.pdf
(paper/) and fig_overlap.pdf. Seed 20260930 for every bootstrap and permutation;
B = 2000 except the specification curve (B = 500 per specification, stated).

Data sets: L-band two passes (1888 discs), L-band pass 1 (1303), L-band pass 2
(585; 10 shadowed, 0 firing), S-band pass 1 (1300). Outcome: the disc has at least
one cell the published rule selects. Class = PSR fraction 1 (shadowed), 0 (sunlit)
or between (mixed, its own level); a pass term in the pooled set. Covariates are
standardized for fitting (the PSR coefficient is unchanged by it).

A  the ladder, every rung, every set: (a) class [+ pass]; (b) + ln N-hat;
   (c) + min SNR + coherence (the published specification); (d) + cx/100, cy/100;
   (e) (c) + slant-range sample, geometry-file incidence, LOLA local incidence;
   (e0) (a) + the same geometry; (f) (e) + terrain (mean slope, slope SD, plane-
   detrended RMS height at 100 and 500 m, local-slope shadow and layover
   fractions); (f0) the same without coherence, ln N-hat, SNR. PSR coefficient,
   model SE, OR, model 95 % CI, cluster-robust SE, block-bootstrap 95 % CI.
B  the specification curve: all 2^10 subsets of {ln N-hat, coherence, min SNR,
   spatial trend, slant-range sample, incidence, LOLA local incidence, slope,
   roughness (RMS height, 100 m), PSR fraction} with class and pass always in.
C  the outcome decomposition: DOP gate only, CPR condition only, the joint rule
   (disc-level indicators; and the cell-level rates as binomial counts).
D  overlap and positivity: standardized mean differences, a propensity score,
   support, trimming, exact stratification (coherence deciles; slant-range
   deciles) with Mantel-Haenszel and Breslow-Day (Tarone).
E  the minimum detectable odds ratio: 80 % power at level 5 %, two-sided, with the
   cluster-robust variance (the noncentral normal approximation).
G  block-size sensitivity (3, 5, 8, 12) and a spatial permutation test (random
   toroidal shift of each pass's class lattice, 2000 permutations).
H  the pass-1 reversal: strata tables, leave-one-stratum-out, other stratum
   definitions, geometry strata, pass 2 and S-band, and the noise-floor fraction
   of the firing cells by class.
I  reconciliations.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from itertools import product
from pathlib import Path

import numpy as np
from scipy.optimize import brentq
from scipy.stats import chi2, mannwhitneyu

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402
import crater_ladder_v20 as CL  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "shadow_identification.json"
SEED = 20260930
B_FULL = 2000
B_SPEC = 500
SETS = {"L_two_passes": (("L", "20200808"), ("L", "20200305")), "L_pass1": (("L", "20200808"),),
        "L_pass2": (("L", "20200305"),), "S_pass1": (("S", "20200808S"),)}
RUNGS = {
    "a": [], "b": ["lnN"], "b2": ["lnN", "snr"], "c": ["lnN", "snr", "coh"],
    "d": ["lnN", "snr", "coh", "sp1", "sp2"], "e": ["lnN", "snr", "coh", "j", "inc", "loc"],
    "e0": ["j", "inc", "loc"],
    "f": ["lnN", "snr", "coh", "j", "inc", "loc", "slope", "slope_sd", "r100", "r500", "shadow", "layover"],
    "f0": ["j", "inc", "loc", "slope", "slope_sd", "r100", "r500", "shadow", "layover"]}
SPEC_COVS = ["lnN", "coh", "snr", "sp", "j", "inc", "loc", "slope", "rough", "psrfrac"]
SPEC_COLS = {"lnN": ["lnN"], "coh": ["coh"], "snr": ["snr"], "sp": ["sp1", "sp2"], "j": ["j"], "inc": ["inc"],
             "loc": ["loc"], "slope": ["slope"], "rough": ["r100"], "psrfrac": ["psrfrac"]}
#: published values to reproduce (PSR coefficient / OR / block interval), from the v20 artifacts
KNOWN = {
    "L_two_passes": {"a": (1.79, (0.90, 3.50)), "b": (1.29, None), "c": (0.67, (0.28, 1.56)), "d": (None, (0.33, 1.88)),
                     "e": (None, (0.37, 2.45)), "e0": (1.01, (0.49, 2.38))},
    "S_pass1": {"a": (2.93, (1.22, 6.47)), "b": (1.62, (0.72, 3.36)), "c": (0.83, (0.26, 2.03)), "d": (0.79, (0.23, 2.47)),
                "e": (0.50, (0.08, 1.61)), "e0": (0.49, (0.18, 1.30))}}

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


# ------------------------------------------------------------------ data
class DS:
    def __init__(self, rows, name):
        self.name, self.rows, n = name, rows, len(rows)
        self.n = n
        a = lambda f: np.array([f(r) for r in rows], float)  # noqa: E731
        self.cls = np.array([r["class"] for r in rows])
        self.ps = np.array([r["pass"] for r in rows])
        self.pooled = len(set(self.ps)) > 1
        self.y = (a(lambda r: r["rule"]) >= 1).astype(float)
        self.y_dop = (a(lambda r: r["n_dop"]) >= 1).astype(float)
        self.y_cpr = (a(lambda r: r["n_cpr"]) >= 1).astype(float)
        self.cells = a(lambda r: r["cells"])
        self.cnt = {"joint": a(lambda r: r["rule"]), "dop": a(lambda r: r["n_dop"]), "cpr": a(lambda r: r["n_cpr"])}
        t = lambda k: a(lambda r: (r["terrain"] or {}).get(k, np.nan))  # noqa: E731
        self.cov = {"lnN": np.log(a(lambda r: r["median_N_hat"])), "coh": a(lambda r: r["median_coherence"]),
                    "snr": a(lambda r: r["median_min_snr_db"]), "sp1": a(lambda r: r["cx"]) / 100.0,
                    "sp2": a(lambda r: r["cy"]) / 100.0, "j": a(lambda r: r["slant_range_sample"]) / 100.0,
                    "inc": a(lambda r: r["incidence_geometry_deg"]), "loc": a(lambda r: r["lola_local_incidence_deg"]),
                    "slope": t("slope_mean_deg"), "slope_sd": t("slope_sd_deg"), "r100": t("rms_height_100m"),
                    "r500": t("rms_height_500m"), "shadow": t("fraction_shadow_local_slope"),
                    "layover": t("fraction_layover_local_slope"), "psrfrac": a(lambda r: r["psr_fraction"])}
        self.cx, self.cy = a(lambda r: r["cx"]).astype(int), a(lambda r: r["cy"]).astype(int)
        self.inside, self.mixed, self.outside = self.cls == "inside", self.cls == "mixed", self.cls == "outside"
        self.p2 = (self.ps == "20200305").astype(float)
        self.cbins = np.digitize(self.cov["coh"], [0.4, 0.5, 0.6])
        self.missing_terrain = int(np.isnan(self.cov["slope"]).sum())

    def groups(self, bs):
        keys = [(self.ps[i], self.cx[i] // bs, self.cy[i] // bs) for i in range(self.n)]
        uk = sorted(set(keys))
        kid = {k: i for i, k in enumerate(uk)}
        g = np.array([kid[k] for k in keys])
        return g, [np.flatnonzero(g == k) for k in range(len(uk))]

    def design(self, keys):
        cols = [np.ones(self.n)]
        if self.pooled and self.p2.std() > 0:
            cols.append(self.p2)
        cols.append(self.inside.astype(float))
        if self.mixed.any():
            cols.append(self.mixed.astype(float))
        for k in keys:
            v = self.cov[k]
            sd = np.nanstd(v)
            if not sd > 0:
                continue      # a constant covariate (the local-slope radar-shadow fraction is 0 for every disc) is collinear with the intercept
            cols.append((v - np.nanmean(v)) / sd)
        return np.column_stack(cols)

    @property
    def psr_col(self):
        return 2 if (self.pooled and self.p2.std() > 0) else 1


def fit_one(ds, keys, y=None, bs=5, rows=None):
    X = ds.design(keys)
    y = ds.y if y is None else y
    if rows is not None:
        X, y = X[rows], y[rows]
        groups = ds.groups(bs)[0][rows]
    else:
        groups = ds.groups(bs)[0]
    b, cov, ll, conv = CL.irls(X, y)
    i = ds.psr_col
    out = {"n": int(len(y)), "events": int(y.sum()), "converged": bool(conv)}
    if cov is None:
        return {**out, "coefficient": float("nan")}
    se = np.sqrt(np.diag(cov))
    cse = np.sqrt(np.diag(CL.cluster_cov(X, y, b, cov, groups)))
    out.update({"coefficient": float(b[i]), "se_model": float(se[i]), "se_cluster_robust": float(cse[i]),
                "odds_ratio": float(np.exp(b[i])),
                "or_ci95_model": [float(np.exp(b[i] - 1.96 * se[i])), float(np.exp(b[i] + 1.96 * se[i]))],
                "or_ci95_cluster_robust": [float(np.exp(b[i] - 1.96 * cse[i])), float(np.exp(b[i] + 1.96 * cse[i]))],
                "log_likelihood": float(ll)})
    return out


def mh_coh(ds, sel, cb=None):
    cb = ds.cbins if cb is None else cb
    a, b, c, d = [], [], [], []
    for s in np.unique(cb[sel]):
        m = sel & (cb == s)
        a.append(((ds.y == 1) & ds.inside & m).sum()); b.append(((ds.y == 0) & ds.inside & m).sum())
        c.append(((ds.y == 1) & ds.outside & m).sum()); d.append(((ds.y == 0) & ds.outside & m).sum())
    return a, b, c, d


def bootstrap(ds, rung_keys, B, bs, seed, extra_y=None):
    """Block bootstrap of the PSR coefficient of every rung, the coherence-stratified MH (all; pass 1 when pooled)
    and the crude OR, one resample per replicate shared by all statistics."""
    g, idx = ds.groups(bs)
    rng = np.random.default_rng(seed)
    Xs = {k: ds.design(v) for k, v in rung_keys.items()}
    col = ds.psr_col
    boot = {k: [] for k in rung_keys}
    bmh = {"all": [], "pass1": []}
    bun = []
    fails = {k: 0 for k in rung_keys}
    n_empty = 0
    for _ in range(B):
        pick = rng.integers(0, len(idx), len(idx))
        ii = np.concatenate([idx[k] for k in pick])
        yy, cl, pp, cb = ds.y[ii], ds.cls[ii], ds.ps[ii], ds.cbins[ii]
        empty2 = bool(ds.pooled and yy[pp == "20200305"].sum() == 0)
        n_empty += empty2
        for k in rung_keys:
            Xb, yb, c_ = Xs[k][ii], yy, col
            if empty2:
                keep = pp == "20200808"
                Xb, yb, c_ = np.delete(Xb[keep], 1, axis=1), yy[keep], col - 1
            bt, _c, _l, conv = CL.irls(Xb, yb)
            if conv:
                boot[k].append(bt[c_])
            else:
                fails[k] += 1
        ib, ob = cl == "inside", cl == "outside"

        def mh_of(sel):
            A = np.array([[((yy == 1) & ib & sel & (cb == s)).sum(), ((yy == 0) & ib & sel & (cb == s)).sum(),
                           ((yy == 1) & ob & sel & (cb == s)).sum(), ((yy == 0) & ob & sel & (cb == s)).sum()] for s in range(4)], float)
            nn = A.sum(axis=1)
            Rn = np.sum(A[:, 0] * A[:, 3] / np.where(nn > 0, nn, 1)); Sn = np.sum(A[:, 1] * A[:, 2] / np.where(nn > 0, nn, 1))
            return np.log(Rn / Sn) if Rn > 0 and Sn > 0 else np.nan
        bmh["all"].append(mh_of(np.ones(len(yy), bool)))
        if ds.pooled:
            bmh["pass1"].append(mh_of(pp == "20200808"))
        t = np.array([((yy == 1) & ib).sum(), ((yy == 0) & ib).sum(), ((yy == 1) & ob).sum(), ((yy == 0) & ob).sum()], float)
        bun.append(np.log(t[0] * t[3] / (t[1] * t[2])) if t[1] * t[2] > 0 and t[0] * t[3] > 0 else np.nan)
    return {"coef": boot, "mh": bmh, "crude": bun, "fails": fails, "pass2_empty": n_empty, "B": B, "block": bs}


def pack(v):
    v = np.asarray(v, float)
    if np.isfinite(v).sum() < 50:
        return {"ci95": [float("nan")] * 2, "or_ci95": [float("nan")] * 2, "replicates_used": int(np.isfinite(v).sum()),
                "note": "fewer than 50 converged replicates: no interval"}
    iv = CL.interval(v)
    iv["or_ci95"] = [float(np.exp(x)) for x in iv["ci95"]]
    return iv


def ladder_for(ds, B, seed=SEED, bs=5, rungs=None):
    rungs = rungs or RUNGS
    if ds.missing_terrain:
        rungs = {k: v for k, v in rungs.items() if not (set(v) & {"slope", "slope_sd", "r100", "r500", "shadow", "layover"})}
    out = {"discs": ds.n, "events": int(ds.y.sum()), "classes": {c: {"discs": int((ds.cls == c).sum()), "fires": int(((ds.cls == c) & (ds.y == 1)).sum())}
                                                                   for c in ("outside", "inside", "mixed")}, "rungs": {}}
    bt = bootstrap(ds, rungs, B, bs, seed)
    for k, keys in rungs.items():
        f = fit_one(ds, keys, bs=bs)
        f["covariates"] = keys
        if "coefficient" in f and np.isfinite(f["coefficient"]):
            f["block_bootstrap"] = {**pack(bt["coef"][k]), "B": B, "non_converged": bt["fails"][k]}
            f["block_bootstrap"]["pass2_empty_replicates_fit_on_pass1"] = bt["pass2_empty"]
            f["ci_excludes_1_from_above"] = bool(f["block_bootstrap"]["or_ci95"][0] > 1.0)
            f["ci_excludes_1_from_below"] = bool(f["block_bootstrap"]["or_ci95"][1] < 1.0)
        out["rungs"][k] = f
    out["mantel_haenszel_coherence_strata"] = {}
    for scope, sel in (("all", np.ones(ds.n, bool)),) + ((("pass1", ds.ps == "20200808"),) if ds.pooled else ()):
        mh = CL.mh_or(*mh_coh(ds, sel))
        iv = pack(bt["mh"][scope])
        mh["block_bootstrap"] = {**iv, "B": B}
        mh["ci_excludes_1_from_above"] = bool(iv["or_ci95"][0] > 1.0)
        mh["ci_excludes_1_from_below"] = bool(iv["or_ci95"][1] < 1.0)
        out["mantel_haenszel_coherence_strata"][scope] = mh
    a, b, c, d = int(((ds.y == 1) & ds.inside).sum()), int(((ds.y == 0) & ds.inside).sum()), int(((ds.y == 1) & ds.outside).sum()), int(((ds.y == 0) & ds.outside).sum())
    un = CL.crude_or(a, a + b, c, c + d)
    un["block_bootstrap"] = {**pack(bt["crude"]), "B": B}
    out["crude_or_no_pass_term"] = un
    return out, bt


# ------------------------------------------------------------------ B: specification curve
_G = {}


def _init(ds_pack):
    _G["ds"], _G["X"], _G["groups"] = ds_pack


def _spec_chunk(args):
    masks, resamples = args
    ds = _G["ds"]
    out = []
    for mask in masks:
        keys = [c for bit, cov in zip(mask, SPEC_COVS) if bit for c in SPEC_COLS[cov]]
        X = ds.design(keys)
        b, cov, ll, conv = CL.irls(X, ds.y)
        i = ds.psr_col
        se = np.sqrt(np.diag(cov))
        cse = np.sqrt(np.diag(CL.cluster_cov(X, ds.y, b, cov, _G["groups"])))
        bs_ = []
        for ii in resamples:
            yy, pp = ds.y[ii], ds.ps[ii]
            Xb, yb, c_ = X[ii], yy, i
            if ds.pooled and yy[pp == "20200305"].sum() == 0:
                keep = pp == "20200808"
                Xb, yb, c_ = np.delete(Xb[keep], 1, axis=1), yy[keep], i - 1
            bt, _c, _l, cv = CL.irls(Xb, yb)
            if cv:
                bs_.append(bt[c_])
        out.append({"mask": mask, "coef": float(b[i]), "se_model": float(se[i]), "se_cluster": float(cse[i]), "converged": bool(conv),
                    "boot": [float(np.percentile(bs_, 2.5)), float(np.percentile(bs_, 97.5))] if len(bs_) > max(10, len(resamples) // 2) else None,
                    "boot_used": len(bs_)})
    return out


def spec_curve(ds, workers, B=B_SPEC, seed=SEED, limit=None):
    g, idx = ds.groups(5)
    rng = np.random.default_rng(seed)
    resamples = []
    for _ in range(B):
        pick = rng.integers(0, len(idx), len(idx))
        resamples.append(np.concatenate([idx[k] for k in pick]))
    avail = [c for c in SPEC_COVS if not (c in ("slope", "rough") and ds.missing_terrain)]
    combos = [m for m in product((0, 1), repeat=len(SPEC_COVS)) if all(m[SPEC_COVS.index(c)] == 0 for c in SPEC_COVS if c not in avail)]
    if limit:
        combos = combos[::max(1, len(combos) // limit)][:limit]
    chunks = [combos[i::workers * 4] for i in range(workers * 4)]
    with ProcessPoolExecutor(max_workers=workers, initializer=_init, initargs=((ds, None, g),)) as ex:
        parts = list(ex.map(_spec_chunk, [(ch, resamples) for ch in chunks]))
    rows = [r for p in parts for r in p]
    for r in rows:
        r["covariates"] = [c for bit, c in zip(r["mask"], SPEC_COVS) if bit]
        r["has_coherence"] = bool(r["mask"][SPEC_COVS.index("coh")])
        r["odds_ratio"] = math.exp(r["coef"])
        r["or_ci95_model"] = [math.exp(r["coef"] - 1.96 * r["se_model"]), math.exp(r["coef"] + 1.96 * r["se_model"])]
        r["or_ci95_cluster"] = [math.exp(r["coef"] - 1.96 * r["se_cluster"]), math.exp(r["coef"] + 1.96 * r["se_cluster"])]
        r["or_ci95_block_bootstrap"] = [math.exp(v) for v in r["boot"]] if r["boot"] else None
    return rows


def spec_summary(rows):
    ok = [r for r in rows if r["or_ci95_block_bootstrap"]]
    def cnt(pred, key="or_ci95_block_bootstrap"):
        return int(sum(1 for r in ok if pred(r, r[key])))
    ors = np.array([r["odds_ratio"] for r in ok])
    out = {"specifications": len(rows), "with_block_ci": len(ok), "B": B_SPEC,
           "or_median": float(np.median(ors)), "or_min": float(ors.min()), "or_max": float(ors.max()),
           "or_p5_p95": [float(np.percentile(ors, 5)), float(np.percentile(ors, 95))]}
    for key, lab in (("or_ci95_block_bootstrap", "block_bootstrap"), ("or_ci95_cluster", "cluster_robust"), ("or_ci95_model", "model_based")):
        sub = [r for r in rows if r.get(key)]
        out[lab] = {"excludes_1_from_above": int(sum(1 for r in sub if r[key][0] > 1.0)),
                    "excludes_1_from_below": int(sum(1 for r in sub if r[key][1] < 1.0)),
                    "or_gt_1": int(sum(1 for r in sub if r["odds_ratio"] > 1)), "or_lt_1": int(sum(1 for r in sub if r["odds_ratio"] < 1))}
    for lab, pick in (("with_coherence", True), ("without_coherence", False)):
        sub = [r for r in ok if r["has_coherence"] == pick]
        o = np.array([r["odds_ratio"] for r in sub])
        out[lab] = {"n": len(sub), "or_median": float(np.median(o)), "or_range": [float(o.min()), float(o.max())],
                    "block_bootstrap_excludes_1_from_above": int(sum(1 for r in sub if r["or_ci95_block_bootstrap"][0] > 1)),
                    "block_bootstrap_excludes_1_from_below": int(sum(1 for r in sub if r["or_ci95_block_bootstrap"][1] < 1)),
                    "cluster_robust_excludes_1_from_above": int(sum(1 for r in sub if r["or_ci95_cluster"][0] > 1)),
                    "model_based_excludes_1_from_above": int(sum(1 for r in sub if r["or_ci95_model"][0] > 1))}
    return out


# ------------------------------------------------------------------ C
def grouped_logistic(ds, keys, cnt, cells, bs=5):
    """Binomial (events, cells) logistic with the class / pass / covariate design, cluster-robust SE."""
    X = ds.design(keys)
    y = cnt / cells
    w = cells
    b = np.zeros(X.shape[1])
    for _ in range(100):
        eta = np.clip(X @ b, -30, 30)
        mu = 1 / (1 + np.exp(-eta))
        W = w * mu * (1 - mu) + 1e-12
        H = X.T @ (X * W[:, None]) + 1e-10 * np.eye(X.shape[1])
        step = np.linalg.solve(H, X.T @ (w * (y - mu)))
        b = b + step
        if np.abs(step).max() < 1e-9:
            break
    eta = np.clip(X @ b, -30, 30)
    mu = 1 / (1 + np.exp(-eta))
    W = w * mu * (1 - mu) + 1e-12
    H = X.T @ (X * W[:, None]) + 1e-10 * np.eye(X.shape[1])
    cov = np.linalg.inv(H)
    g = ds.groups(bs)[0]
    sc = X * (w * (y - mu))[:, None]
    meat = sum(np.outer(sc[g == k].sum(0), sc[g == k].sum(0)) for k in np.unique(g))
    G = len(np.unique(g))
    ccov = cov @ meat @ cov * G / (G - 1)
    i = ds.psr_col
    return {"coefficient": float(b[i]), "se_cluster_robust": float(np.sqrt(ccov[i, i])), "odds_ratio": float(np.exp(b[i])),
            "or_ci95_cluster_robust": [float(np.exp(b[i] - 1.96 * np.sqrt(ccov[i, i]))), float(np.exp(b[i] + 1.96 * np.sqrt(ccov[i, i])))]}


def outcome_decomposition(ds, B):
    out = {}
    for name, y, cnt in (("joint_rule", ds.y, ds.cnt["joint"]), ("dop_gate_only", ds.y_dop, ds.cnt["dop"]), ("cpr_condition_only", ds.y_cpr, ds.cnt["cpr"])):
        a, b, c, d = int(((y == 1) & ds.inside).sum()), int(((y == 0) & ds.inside).sum()), int(((y == 1) & ds.outside).sum()), int(((y == 0) & ds.outside).sum())
        blk = {"disc_level": {"shadowed_firing": a, "shadowed_n": a + b, "sunlit_firing": c, "sunlit_n": c + d,
                              "saturated": bool(min(a, b, c, d) == 0)}}
        for lab, keys in (("a", []), ("c", ["lnN", "snr", "coh"])):
            ds_y = y
            f = fit_one(ds, keys, y=ds_y)
            g, idx = ds.groups(5)
            rng = np.random.default_rng(SEED)
            X = ds.design(keys)
            boot = []
            for _ in range(B):
                pick = rng.integers(0, len(idx), len(idx))
                ii = np.concatenate([idx[k] for k in pick])
                yy, pp = y[ii], ds.ps[ii]
                Xb, yb, c_ = X[ii], yy, ds.psr_col
                if ds.pooled and yy[pp == "20200305"].sum() == 0:
                    keep = pp == "20200808"
                    Xb, yb, c_ = np.delete(Xb[keep], 1, axis=1), yy[keep], c_ - 1
                bt, _c, _l, cv = CL.irls(Xb, yb)
                if cv:
                    boot.append(bt[c_])
            f["block_bootstrap"] = {**pack(boot), "B": B} if len(boot) > 50 else None
            blk[f"rung_{lab}"] = f
        blk["cell_level_rates"] = {}
        for lab, keys in (("a", []), ("c", ["lnN", "snr", "coh"])):
            blk["cell_level_rates"][f"rung_{lab}"] = grouped_logistic(ds, keys, cnt, ds.cells)
        blk["cell_level_rates"]["mean_rate_shadowed"] = float(cnt[ds.inside].sum() / ds.cells[ds.inside].sum())
        blk["cell_level_rates"]["mean_rate_sunlit"] = float(cnt[ds.outside].sum() / ds.cells[ds.outside].sum())
        out[name] = blk
    return out


# ------------------------------------------------------------------ D
def breslow_day(tables, psi):
    """Breslow-Day statistic with Tarone's correction. tables: list of (a, b, c, d)."""
    stat = 0.0
    sum_dev = sum_var = 0.0
    k = 0
    for a, b, c, d in tables:
        n1, n0, m1 = a + b, c + d, a + c
        if n1 == 0 or n0 == 0 or m1 == 0 or (b + d) == 0:
            continue
        lo, hi = max(0.0, m1 - n0), min(n1, m1)
        if hi <= lo:
            continue
        f = lambda x: x * (n0 - m1 + x) - psi * (n1 - x) * (m1 - x)  # noqa: E731
        try:
            ah = brentq(f, lo + 1e-9, hi - 1e-9)
        except ValueError:
            continue
        v = 1.0 / (1 / ah + 1 / (n1 - ah) + 1 / (m1 - ah) + 1 / (n0 - m1 + ah))
        stat += (a - ah) ** 2 / v
        sum_dev += a - ah
        sum_var += v
        k += 1
    tarone = stat - (sum_dev ** 2) / sum_var if sum_var > 0 else float("nan")
    df = max(k - 1, 0)
    return {"strata_used": k, "df": df, "breslow_day": float(stat), "tarone_corrected": float(tarone),
            "p_tarone": float(chi2.sf(tarone, df)) if df > 0 else None}


def stratified(ds, label, sel=None):
    sel = np.ones(ds.n, bool) if sel is None else sel
    rows, tabs = [], []
    no_sun = 0
    for s in np.unique(label[sel]):
        m = sel & (label == s)
        a, b = int(((ds.y == 1) & ds.inside & m).sum()), int(((ds.y == 0) & ds.inside & m).sum())
        c, d = int(((ds.y == 1) & ds.outside & m).sum()), int(((ds.y == 0) & ds.outside & m).sum())
        r = {"stratum": int(s), "shadowed_fires": a, "shadowed_n": a + b, "sunlit_fires": c, "sunlit_n": c + d}
        if a + b > 0 and c + d == 0:
            no_sun += a + b
        if min(a + b, c + d) > 0:
            r["odds_ratio_haldane"] = ((a + .5) * (d + .5)) / ((b + .5) * (c + .5))
            tabs.append((a, b, c, d))
        rows.append(r)
    mh = CL.mh_or(*[[t[i] for t in tabs] for i in range(4)]) if tabs else None
    bd = breslow_day(tabs, mh["or"]) if mh else None
    return {"strata": rows, "mantel_haenszel": mh, "breslow_day_tarone": bd,
            "shadowed_discs_in_strata_without_a_sunlit_disc": int(no_sun)}


def overlap(ds, B):
    keep = ds.inside | ds.outside
    cov = ["lnN", "snr", "coh", "sp1", "sp2", "j", "inc", "loc"] + ([] if ds.missing_terrain else ["slope", "slope_sd", "r100", "r500", "shadow", "layover"])
    out = {"covariates": cov, "smd": {}, "propensity": {}}
    t, c = ds.inside, ds.outside
    for k in cov + ["psrfrac"]:
        v = ds.cov[k]
        sd = math.sqrt(0.5 * (np.nanvar(v[t]) + np.nanvar(v[c])))
        out["smd"][k] = {"smd": float((np.nanmean(v[t]) - np.nanmean(v[c])) / sd) if sd > 0 else None,
                         "mean_shadowed": float(np.nanmean(v[t])), "mean_sunlit": float(np.nanmean(v[c])),
                         "sd_shadowed": float(np.nanstd(v[t])), "sd_sunlit": float(np.nanstd(v[c]))}
    # propensity of shadow vs sunlit
    cols = [np.ones(ds.n)] + ([ds.p2] if ds.pooled else [])
    for k in cov:
        v = ds.cov[k]
        sd_ = np.nanstd(v[keep])
        if not sd_ > 0:
            continue
        cols.append((v - np.nanmean(v[keep])) / sd_)
    X = np.column_stack(cols)[keep]
    z = ds.inside[keep].astype(float)
    b, covm, ll, conv = CL.irls(X, z)
    ps = 1 / (1 + np.exp(-np.clip(X @ b, -30, 30)))
    idx_keep = np.flatnonzero(keep)
    pst, psc = ps[z == 1], ps[z == 0]
    q = [1, 5, 25, 50, 75, 95, 99]
    out["propensity"] = {"converged": bool(conv), "shadowed_quantiles": {str(p): float(np.percentile(pst, p)) for p in q},
                         "sunlit_quantiles": {str(p): float(np.percentile(psc, p)) for p in q},
                         "sunlit_support": [float(psc.min()), float(psc.max())],
                         "shadowed_outside_sunlit_support": int(((pst < psc.min()) | (pst > psc.max())).sum()),
                         "fraction_shadowed_outside_sunlit_support": float(((pst < psc.min()) | (pst > psc.max())).mean()),
                         "fraction_shadowed_above_sunlit_95th_percentile": float((pst > np.percentile(psc, 95)).mean()),
                         "fraction_sunlit_below_shadowed_5th_percentile": float((psc < np.percentile(pst, 5)).mean()),
                         "auc_shadow_vs_sunlit": float(mannwhitneyu(pst, psc).statistic / (len(pst) * len(psc)))}
    # trimmed analyses
    trims = {}
    for lab, (lo, hi) in (("common_support", (max(psc.min(), pst.min()), min(psc.max(), pst.max()))), ("crump_0p1_0p9", (0.1, 0.9))):
        sel_ = np.zeros(ds.n, bool)
        sel_[idx_keep[(ps >= lo) & (ps <= hi)]] = True
        sel_ |= ds.mixed & False
        rows = np.flatnonzero(sel_)
        t_ = {"bounds": [float(lo), float(hi)], "shadowed_kept": int((sel_ & ds.inside).sum()), "sunlit_kept": int((sel_ & ds.outside).sum())}
        if len(rows) < 40 or (sel_ & ds.inside).sum() < 5 or (sel_ & ds.outside).sum() < 5:
            t_["skipped"] = "fewer than 40 discs or fewer than 5 of a class inside the trimmed region"
            trims[lab] = t_
            continue
        sub = DS([ds.rows[i] for i in rows], ds.name + "_" + lab)
        for rung in ("a", "c"):
            try:
                f = fit_one(sub, RUNGS[rung])
                bt = bootstrap(sub, {rung: RUNGS[rung]}, B, 5, SEED)
                f["block_bootstrap"] = {**pack(bt["coef"][rung]), "B": B}
            except Exception as e:  # noqa: BLE001
                f = {"error": str(e)}
            t_[f"rung_{rung}"] = f
        trims[lab] = t_
    out["trimmed"] = trims
    # exact stratification
    coh_dec = np.digitize(ds.cov["coh"], np.percentile(ds.cov["coh"], np.arange(10, 100, 10)))
    j_dec = np.digitize(ds.cov["j"], np.percentile(ds.cov["j"], np.arange(10, 100, 10)))
    strat = {}
    for lab, dec in (("coherence_deciles", coh_dec), ("slant_range_deciles", j_dec)):
        if ds.pooled:
            lab_ = dec * 2 + ds.p2.astype(int)
            strat[lab + "_by_pass"] = stratified(ds, lab_)
        strat[lab] = stratified(ds, dec)
    out["stratification"] = strat
    return out


# ------------------------------------------------------------------ E
def mde(ladder):
    out = {}
    for k in ("a", "b", "c", "d", "e", "e0"):
        f = ladder["rungs"].get(k)
        if not f or "se_cluster_robust" not in f:
            continue
        se = f["se_cluster_robust"]
        out[k] = {"se_cluster_robust": se, "se_model": f["se_model"], "design_effect": (se / f["se_model"]) ** 2,
                  "mde_or_above_1_80pct": float(math.exp((1.959964 + 0.841621) * se)),
                  "mde_or_below_1_80pct": float(math.exp(-(1.959964 + 0.841621) * se)),
                  "observed_or": f["odds_ratio"],
                  "power_at_observed_effect": float(0.5 * (1 + math.erf((abs(f["coefficient"]) / se - 1.959964) / math.sqrt(2)))
                                                    + 0.5 * (1 - math.erf((abs(f["coefficient"]) / se + 1.959964) / math.sqrt(2))))}
    return out


# ------------------------------------------------------------------ G
def block_sizes(ds, B):
    out = {}
    for bs in (3, 5, 8, 12):
        rungs = {k: RUNGS[k] for k in ("a", "c", "e0")}
        bt = bootstrap(ds, rungs, B, bs, SEED)
        g, idx = ds.groups(bs)
        row = {"blocks": len(idx), "rungs": {}}
        for k in rungs:
            f = fit_one(ds, RUNGS[k], bs=bs)
            row["rungs"][k] = {"odds_ratio": f["odds_ratio"], "se_cluster_robust": f["se_cluster_robust"],
                               "or_ci95_cluster_robust": f["or_ci95_cluster_robust"],
                               "or_ci95_block_bootstrap": pack(bt["coef"][k])["or_ci95"], "B": B, "non_converged": bt["fails"][k]}
        out[f"{bs}x{bs}"] = row
    return out


def permutation(ds, B=2000, seed=SEED, min_valid=0.3):
    """Spatial permutation of the PSR class labels: the class field of each pass (a lattice of disc nodes, occupied
    where the pass has a disc) is shifted toroidally by (dx, dy); a disc takes the class of the node it lands on and
    is dropped for that permutation when the node is empty. A shift that leaves under 30 % of a pass's discs is
    not used (the swath is a strip, 151 x 40 nodes with 22 % occupied, so most shifts empty it). Shifts are drawn
    uniformly from the admissible ones, per pass independently; B draws with replacement (the number of distinct
    admissible shifts is reported). The covariates stay with the discs."""
    rng = np.random.default_rng(seed)
    obs = {k: fit_one(ds, RUNGS[k])["coefficient"] for k in ("a", "c")}
    passes = sorted(set(ds.ps))
    field, shifts = {}, {}
    code = {"outside": 1, "inside": 2, "mixed": 3}
    for p in passes:
        m = np.flatnonzero(ds.ps == p)
        x0, y0 = ds.cx[m].min(), ds.cy[m].min()
        nx, ny = ds.cx[m].max() - x0 + 1, ds.cy[m].max() - y0 + 1
        F = np.zeros((nx, ny), int)
        for i in m:
            F[ds.cx[i] - x0, ds.cy[i] - y0] = code[ds.cls[i]]
        occ = F > 0
        adm = [(dx, dy) for dx in range(nx) for dy in range(ny)
               if occ[(ds.cx[m] - x0 - dx) % nx, (ds.cy[m] - y0 - dy) % ny].mean() >= min_valid]
        field[p], shifts[p] = (F, x0, y0, nx, ny), adm
    Xa, Xc = ds.design(RUNGS["a"]), ds.design(RUNGS["c"])
    res = {"a": [], "c": []}
    kept, shadowed_kept = [], []
    for _ in range(B):
        inside = np.zeros(ds.n); mixed = np.zeros(ds.n); valid = np.ones(ds.n, bool)
        for p in passes:
            F, x0, y0, nx, ny = field[p]
            dx, dy = shifts[p][rng.integers(0, len(shifts[p]))]
            m = np.flatnonzero(ds.ps == p)
            c_ = F[(ds.cx[m] - x0 - dx) % nx, (ds.cy[m] - y0 - dy) % ny]
            valid[m[c_ == 0]] = False
            inside[m[c_ == 2]] = 1; mixed[m[c_ == 3]] = 1
        kept.append(int(valid.sum())); shadowed_kept.append(int((inside[valid] == 1).sum()))
        if inside[valid].sum() < 5 or (1 - inside[valid] - mixed[valid]).sum() < 5:
            continue
        for k, X in (("a", Xa), ("c", Xc)):
            Xp = X.copy()
            Xp[:, ds.psr_col], Xp[:, ds.psr_col + 1] = inside, mixed
            b, cov, ll, conv = CL.irls(Xp[valid], ds.y[valid])
            if conv:
                res[k].append(b[ds.psr_col])
    out = {"permutations": B, "min_valid_fraction": min_valid, "admissible_shifts": {p: len(v) for p, v in shifts.items()},
           "discs_kept_median": int(np.median(kept)), "discs_kept_min": int(min(kept)),
           "shadowed_discs_kept_median": int(np.median(shadowed_kept)), "shadowed_discs_kept_min": int(min(shadowed_kept))}
    for k in ("a", "c"):
        v = np.array(res[k])
        out[f"rung_{k}"] = {"observed_coefficient": obs[k], "observed_or": math.exp(obs[k]), "permutation_mean": float(v.mean()),
                            "permutation_sd": float(v.std()), "used": int(v.size),
                            "p_two_sided_abs": float((np.abs(v - v.mean()) >= abs(obs[k] - v.mean())).mean()),
                            "p_upper": float((v >= obs[k]).mean()), "p_lower": float((v <= obs[k]).mean()),
                            "permutation_or_2p5_97p5": [float(math.exp(np.percentile(v, 2.5))), float(math.exp(np.percentile(v, 97.5)))]}
    return out


# ------------------------------------------------------------------ H
def reversal(dss):
    L2 = dss["L_two_passes"]
    p1 = dss["L_pass1"]
    out = {}
    out["pass1_strata_tables"] = stratified(p1, p1.cbins)
    st = out["pass1_strata_tables"]["strata"]
    loo = []
    for s in np.unique(p1.cbins):
        sel = p1.cbins != s
        r = stratified(p1, p1.cbins, sel)["mantel_haenszel"]
        loo.append({"left_out_stratum": int(s), "mh_or": r["or"] if r else None, "ci95": r["ci95"] if r else None})
    out["leave_one_stratum_out"] = loo
    defs = {}
    coh = p1.cov["coh"]
    for k in (5, 8, 10, 15):
        eq_count = np.digitize(coh, np.percentile(coh, np.linspace(0, 100, k + 1)[1:-1]))
        eq_width = np.digitize(coh, np.linspace(coh.min(), coh.max(), k + 1)[1:-1])
        defs[f"{k}_equal_count"] = stratified(p1, eq_count)["mantel_haenszel"]
        defs[f"{k}_equal_width"] = stratified(p1, eq_width)["mantel_haenszel"]
    out["stratum_definitions_mh_pass1"] = defs
    geo = {}
    for lab, key in (("slant_range_deciles", "j"), ("local_incidence_deciles", "loc"), ("incidence_deciles", "inc"), ("slope_deciles", "slope")):
        v = p1.cov[key]
        if np.isnan(v).any():
            continue
        dec = np.digitize(v, np.percentile(v, np.arange(10, 100, 10)))
        geo[lab] = stratified(p1, dec)["mantel_haenszel"]
    out["geometry_strata_mh_pass1"] = geo
    out["other_sets_mh_coherence_strata"] = {k: (stratified(d, d.cbins)["mantel_haenszel"]) for k, d in dss.items()}
    out["pass2_counts"] = {"shadowed_n": int(dss["L_pass2"].inside.sum()), "shadowed_fires": int(((dss["L_pass2"].y == 1) & dss["L_pass2"].inside).sum()),
                           "sunlit_n": int(dss["L_pass2"].outside.sum()), "sunlit_fires": int(((dss["L_pass2"].y == 1) & dss["L_pass2"].outside).sum())}
    # noise-floor fraction of the firing cells, by class (and coherence stratum), pass 1 L and S
    nf = {}
    for k in ("L_pass1", "S_pass1"):
        d = dss[k]
        rows = d.rows
        for cls in ("outside", "inside"):
            sub = [r for r in rows if r["class"] == cls and r["rule"] >= 1]
            frac = np.array([r["rule_cells_fraction_snr_lt_6dB"] for r in sub], float)
            med = np.array([r["rule_cells_median_min_snr_db"] for r in sub], float)
            nf.setdefault(k, {})[cls] = {"firing_discs": len(sub), "median_of_firing_cells_median_min_snr_db": float(np.median(med)),
                                         "mean_fraction_of_firing_cells_below_6dB": float(frac.mean()),
                                         "all_cells_fraction_below_6dB_in_these_discs": float(np.mean([r["cells_fraction_snr_lt_6dB"] for r in sub]))}
        a = [r["rule_cells_fraction_snr_lt_6dB"] for r in rows if r["class"] == "outside" and r["rule"] >= 1]
        b = [r["rule_cells_fraction_snr_lt_6dB"] for r in rows if r["class"] == "inside" and r["rule"] >= 1]
        nf[k]["mannwhitney_p_fraction_below_6dB_shadowed_vs_sunlit"] = float(mannwhitneyu(a, b).pvalue) if len(a) > 2 and len(b) > 2 else None
        # within the low-coherence strata
        strata = {}
        for s in np.unique(d.cbins):
            for cls in ("outside", "inside"):
                sub = [r for r, cb in zip(rows, d.cbins) if cb == s and r["class"] == cls and r["rule"] >= 1]
                if sub:
                    strata.setdefault(int(s), {})[cls] = {"firing_discs": len(sub),
                                                          "median_firing_cell_snr_db": float(np.median([r["rule_cells_median_min_snr_db"] for r in sub])),
                                                          "mean_fraction_below_6dB": float(np.mean([r["rule_cells_fraction_snr_lt_6dB"] for r in sub]))}
        nf[k]["by_coherence_stratum"] = strata
    out["noise_floor_of_firing_cells"] = nf
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--part", default="A,B,C,D,E,F,G,H,I")
    ap.add_argument("--fast", action="store_true", help="smoke test: B = 50, 8 specifications")
    ap.add_argument("--merge", action="store_true", help="write only the parts run into the existing artifact (keeps the others)")
    ap.add_argument("--rerun-f", action="store_true", help="recompute ladder rungs (f) and (f0) only and merge them into the existing artifact")
    args = ap.parse_args()
    parts = set(args.part.split(","))
    t0 = time.time()
    if args.rerun_f:
        return rerun_f()
    tab = json.loads((BASE_DIR / "docs" / "disc_table_v21.json").read_text(encoding="utf-8"))
    dss = {}
    for name, keys in SETS.items():
        rows = [r for k in keys for r in tab["discs"][f"{k[0]}_{k[1]}"]]
        dss[name] = DS(rows, name)
    B = 50 if args.fast else B_FULL
    doc = {"schema": "lunar-ice/shadow-identification/1", "generated_utc": datetime.now(timezone.utc).isoformat(),
           "generator": "backend/scripts/shadow_identification.py", "seed": SEED, "bootstrap_B": B,
           "spec_curve_B": B_SPEC, "interpretation":
           ("The coefficient of rung (a) is a TOTAL-effect estimate of shadow; rungs that add coherence ((c), (d), (e), (f)) are "
            "DIRECT-effect estimates, the part of shadow not mediated by coherence, and coherence is a depolarization measure on "
            "the axis the rule thresholds, so they remove by construction any effect of ice on polarization. Rungs (e0) and (f0) "
            "adjust for viewing geometry and terrain instead. None is a false-positive rate."),
           "sets": {k: {"discs": d.n, "events": int(d.y.sum()), "missing_terrain": d.missing_terrain} for k, d in dss.items()}}
    if "A" in parts:
        doc["A_ladder"] = {}
        doc["A_ladder_bootstraps_kept"] = {}
        for name, d in dss.items():
            if name == "L_pass2":
                # 0 events among 10 shadowed discs: the PSR coefficient runs to -infinity; counts are reported, fits attempted
                pass
            lad, bt = ladder_for(d, B)
            doc["A_ladder"][name] = lad
            print(f"  A {name}: " + "; ".join(f"({k}) OR {v['odds_ratio']:.2f} {v.get('block_bootstrap', {}).get('or_ci95')}"
                                              for k, v in lad["rungs"].items() if "odds_ratio" in v), flush=True)
        rep = {}
        for name, known in KNOWN.items():
            for rung, (orv, ci) in known.items():
                f = doc["A_ladder"][name]["rungs"][rung]
                ok_or = orv is None or abs(round(f["odds_ratio"], 2) - orv) < 0.0051
                ok_ci = ci is None or (abs(round(f["block_bootstrap"]["or_ci95"][0], 2) - ci[0]) < 0.0051 and abs(round(f["block_bootstrap"]["or_ci95"][1], 2) - ci[1]) < 0.0051)
                rep[f"{name}.{rung}"] = {"published_or": orv, "published_ci": ci, "computed_or": f["odds_ratio"],
                                         "computed_ci": f["block_bootstrap"]["or_ci95"], "agrees": bool(ok_or and ok_ci)}
        mh = doc["A_ladder"]["L_two_passes"]["mantel_haenszel_coherence_strata"]
        for scope, (v, ci) in (("all", (0.59, (0.31, 1.06))), ("pass1", (0.44, (0.23, 0.79)))):
            rep[f"L_two_passes.MH.{scope}"] = {"published_or": v, "published_ci": ci, "computed_or": mh[scope]["or"],
                                               "computed_ci": mh[scope]["block_bootstrap"]["or_ci95"],
                                               "agrees": bool(abs(round(mh[scope]["or"], 2) - v) < 0.0051 and abs(round(mh[scope]["block_bootstrap"]["or_ci95"][0], 2) - ci[0]) < 0.0051 and abs(round(mh[scope]["block_bootstrap"]["or_ci95"][1], 2) - ci[1]) < 0.0051)}
        ms = doc["A_ladder"]["S_pass1"]["mantel_haenszel_coherence_strata"]["all"]
        rep["S_pass1.MH"] = {"published_or": 0.99, "published_ci": (0.42, 2.21), "computed_or": ms["or"],
                             "computed_ci": ms["block_bootstrap"]["or_ci95"],
                             "agrees": bool(abs(round(ms["or"], 2) - 0.99) < 0.0051 and abs(round(ms["block_bootstrap"]["or_ci95"][0], 2) - 0.42) < 0.0051 and abs(round(ms["block_bootstrap"]["or_ci95"][1], 2) - 2.21) < 0.0051)}
        doc["A_reproduction"] = rep
        print("  A reproduction: " + ", ".join(f"{k}={'ok' if v['agrees'] else 'DIFFERS'}" for k, v in rep.items()), flush=True)
    if "B" in parts:
        doc["B_spec_curve"] = {}
        for name in ("L_two_passes", "L_pass1", "S_pass1"):
            rows = spec_curve(dss[name], args.workers, B=50 if args.fast else B_SPEC, limit=8 if args.fast else None)
            summ = spec_summary(rows)
            doc["B_spec_curve"][name] = {"summary": summ, "specifications": rows}
            print(f"  B {name}: {summ['specifications']} specs; OR median {summ['or_median']:.2f} range {summ['or_min']:.2f}-{summ['or_max']:.2f}; "
                  f"block CI above-1 {summ['block_bootstrap']['excludes_1_from_above']}, below-1 {summ['block_bootstrap']['excludes_1_from_below']}", flush=True)
    if "C" in parts:
        doc["C_outcomes"] = {n: outcome_decomposition(dss[n], 200 if args.fast else 1000) for n in ("L_two_passes", "S_pass1")}
    if "D" in parts:
        doc["D_overlap"] = {n: overlap(dss[n], 100 if args.fast else 500) for n in ("L_two_passes", "L_pass1", "S_pass1")}
    if "E" in parts and "A_ladder" in doc:
        doc["E_minimum_detectable_effect"] = {n: mde(doc["A_ladder"][n]) for n in ("L_two_passes", "L_pass1", "S_pass1")}
        doc["E_minimum_detectable_effect"]["note"] = ("normal approximation: power = Phi(|beta| / se - 1.96) for the cluster-robust se of the PSR "
                                                      "coefficient; 80 % power at |beta| = (1.96 + 0.84) se; two-sided, level 5 %")
    if "G" in parts:
        doc["G_block_sizes"] = {n: block_sizes(dss[n], B) for n in ("L_two_passes", "S_pass1")}
        doc["G_permutation"] = {n: permutation(dss[n], 200 if args.fast else 2000) for n in ("L_two_passes", "L_pass1", "S_pass1")}
    if "H" in parts:
        doc["H_reversal"] = reversal(dss)
    if "K" in parts:
        doc["K_geometry_mh_block_bootstrap"] = geometry_mh_boot(dss, 200 if args.fast else B_FULL)
        for n, v in doc["K_geometry_mh_block_bootstrap"].items():
            print("  K " + n + ": " + "; ".join(f"{k} {x['mh_or']:.2f} {[round(y, 2) for y in x['block_bootstrap_or_ci95']]}" for k, x in v.items()), flush=True)
    if "I" in parts:
        doc["I_reconcile"] = reconcile(dss, tab, B)
    doc["run_info"] = {**run_info(), "wall_s": round(time.time() - t0, 1)}
    if args.merge and OUT.is_file() and not args.fast:
        base = json.loads(OUT.read_text(encoding="utf-8"))
        parts_done = [k for k in doc if k[:2] in tuple(p + "_" for p in sorted(parts))]
        for k in parts_done:
            base[k] = doc[k]
        base[f"run_info_rerun_{''.join(sorted(parts))}"] = doc["run_info"]
        doc = base
    if not args.fast:
        OUT.write_text(json.dumps(doc, indent=2, default=float), encoding="utf-8")
        print(f"  wrote {OUT.name} ({time.time() - t0:.0f} s)")
    return 0


def mh_block_bootstrap(ds, label, B=2000, bs=5, seed=SEED):
    """Mantel-Haenszel shadowed-versus-sunlit odds ratio over the strata `label` (fixed, from the full data), with a
    5 x 5 block-bootstrap interval: blocks resampled, the odds ratio recomputed over the same strata."""
    g, idx = ds.groups(bs)
    rng = np.random.default_rng(seed)
    strata = np.unique(label)

    def mh_of(ii):
        yy, cl, lb = ds.y[ii], ds.cls[ii], label[ii]
        ib, ob = cl == "inside", cl == "outside"
        Rn = Sn = 0.0
        for s_ in strata:
            m = lb == s_
            a_, b_, c_, d_ = ((yy == 1) & ib & m).sum(), ((yy == 0) & ib & m).sum(), ((yy == 1) & ob & m).sum(), ((yy == 0) & ob & m).sum()
            n_ = a_ + b_ + c_ + d_
            if n_:
                Rn += a_ * d_ / n_; Sn += b_ * c_ / n_
        return np.log(Rn / Sn) if Rn > 0 and Sn > 0 else np.nan
    point = mh_of(np.arange(ds.n))
    boot = []
    for _ in range(B):
        pick = rng.integers(0, len(idx), len(idx))
        boot.append(mh_of(np.concatenate([idx[k] for k in pick])))
    iv = pack(np.array(boot))
    mh = CL.mh_or(*[[((ds.y == 1) & ds.inside & (label == s_)).sum() for s_ in strata], [((ds.y == 0) & ds.inside & (label == s_)).sum() for s_ in strata],
                    [((ds.y == 1) & ds.outside & (label == s_)).sum() for s_ in strata], [((ds.y == 0) & ds.outside & (label == s_)).sum() for s_ in strata]])
    return {"mh_or": float(np.exp(point)), "model_ci95_rbg": mh["ci95"], "block_bootstrap_or_ci95": iv["or_ci95"], "B": B, "replicates_used": iv["replicates_used"],
            "excludes_1_from_above": bool(iv["or_ci95"][0] > 1.0), "excludes_1_from_below": bool(iv["or_ci95"][1] < 1.0), "strata": int(len(strata))}


def geometry_mh_boot(dss, B):
    out = {}
    for name in ("L_two_passes", "L_pass1", "S_pass1"):
        ds = dss[name]
        out[name] = {}
        for lab, key in (("coherence_quartile_bins_(published)", None), ("slant_range_deciles", "j"), ("incidence_deciles", "inc"),
                         ("local_incidence_deciles", "loc"), ("slope_deciles", "slope"), ("roughness_100m_deciles", "r100")):
            if key is None:
                label = ds.cbins
            else:
                v = ds.cov[key]
                label = np.digitize(v, np.percentile(v, np.arange(10, 100, 10)))
            if ds.pooled:
                label = label * 2 + ds.p2.astype(int)       # strata within pass
            out[name][lab] = mh_block_bootstrap(ds, label, B)
    return out


def rerun_f():
    """Recompute rungs (f), (f0) for every set with the zero-variance covariates dropped and merge them into the
    stored artifact (same seed: the block resamples are the ones the other rungs used)."""
    tab = json.loads((BASE_DIR / "docs" / "disc_table_v21.json").read_text(encoding="utf-8"))
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    rungs = {k: RUNGS[k] for k in ("f", "f0")}
    for name, keys in SETS.items():
        rows = [r for k in keys for r in tab["discs"][f"{k[0]}_{k[1]}"]]
        ds = DS(rows, name)
        if name == "L_pass2":
            continue
        lad, _ = ladder_for(ds, B_FULL, rungs=rungs)
        for r in ("f", "f0"):
            doc["A_ladder"][name]["rungs"][r] = lad["rungs"][r]
        print(f"  (f) {name}: OR {lad['rungs']['f']['odds_ratio']:.3f} block {lad['rungs']['f']['block_bootstrap']['or_ci95']}; "
              f"(f0) OR {lad['rungs']['f0']['odds_ratio']:.3f} block {lad['rungs']['f0']['block_bootstrap']['or_ci95']}", flush=True)
    doc["A_rungs_f_note"] = ("(f) and (f0) recomputed after dropping the zero-variance covariate (local-slope radar-shadow fraction is 0 for "
                             "every disc); the first run kept it and reported every bootstrap replicate as not converged")
    OUT.write_text(json.dumps(doc, indent=2, default=float), encoding="utf-8")
    return 0


def reconcile(dss, tab, B):
    out = {}
    # (a) pass-1 MH block interval: two-pass resample vs pass-1-only resample
    two = dss["L_two_passes"]
    p1 = dss["L_pass1"]
    bt1 = bootstrap(p1, {"a": []}, B, 5, SEED)
    bt2 = bootstrap(two, {"a": []}, B, 5, SEED)
    out["L_pass1_mh_block_interval"] = {
        "point": CL.mh_or(*mh_coh(p1, np.ones(p1.n, bool)))["or"],
        "resampling_blocks_of_both_passes_then_pass_1_subset": pack(bt2["mh"]["pass1"])["or_ci95"],
        "resampling_pass_1_blocks_only": pack(bt1["mh"]["all"])["or_ci95"],
        "explanation": ("the v20 gap report's 0.23-0.79 resamples the blocks of both passes and takes the pass-1 discs of each "
                        "replicate (the pass-1 block count then varies); the S-band message's 0.23-0.78 resamples pass-1 blocks only on "
                        "the L-band pass-1 discs; same 1303 discs, different resampling; v21 prints 0.23-0.79 (the former)")}
    # (b) the shadowed lattice cells in L and S
    L = {(r["cx"], r["cy"]) for r in tab["discs"]["L_20200808"] if r["class"] == "inside"}
    S = {(r["cx"], r["cy"]) for r in tab["discs"]["S_20200808S"] if r["class"] == "inside"}
    out["shadowed_lattice_cells"] = {"L": len(L), "S": len(S), "common": len(L & S), "only_L": sorted(L - S), "only_S": sorted(S - L)}
    # firing sets
    fL = {(r["cx"], r["cy"]) for r in tab["discs"]["L_20200808"] if r["class"] == "inside" and r["rule"] >= 1}
    fS = {(r["cx"], r["cy"]) for r in tab["discs"]["S_20200808S"] if r["class"] == "inside" and r["rule"] >= 1}
    out["shadowed_firing_sets"] = {"L": len(fL), "S": len(fS), "both": len(fL & fS), "jaccard": len(fL & fS) / len(fL | fS), "identical": fL == fS}
    # (c) firing discs per band / rung
    out["firing_discs"] = {k: {"discs": d.n, "firing": int(d.y.sum())} for k, d in dss.items()}
    out["firing_discs_per_band_range"] = [min(int(d.y.sum()) for k, d in dss.items() if k != "L_pass2"),
                                          max(int(d.y.sum()) for k, d in dss.items() if k != "L_pass2")]
    out["events_in_every_fit"] = {k: int(d.y.sum()) for k, d in dss.items()}
    # (d) where the slant-range sample comes from
    out["slant_range_sample"] = {
        "definition": ("the column index of each of the disc's cells in the SLC raster (the sample axis), median over the cells; "
                       "the geometry file's tie-point grid is indexed by that same axis and gives the slant range (m) and incidence "
                       "at the cell by interpolation (f2_complex_product.interp with the cell's line and sample)"),
        "code": "backend/scripts/v21_extract.py: ii, jj = np.divmod(c, cols); slant_range_sample = median(jj); slant_range_m = FCP.interp(g[..., 2], LI, SI, spec)",
        "computed_from_polarimetric_values": False,
        "depends_on_the_data_only_through": "which cells qualify as a disc's 663 signal cells (boxcar'd power above the label noise floor in both channels)"}
    return out


if __name__ == "__main__":
    raise SystemExit(main())
