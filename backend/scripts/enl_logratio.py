"""
enl_logratio.py -- the look count at the SELECTED cells, estimated without the
selection. (council work order, Task 2)

    python backend/scripts/enl_logratio.py
    python backend/scripts/enl_logratio.py --split-sample   (v18a N6: selection on
        half the rows, estimation on the other half; merged into the artifact)
    python backend/scripts/enl_logratio.py --only-random   (final pass B6: the random
        cells' local N with the selected cells' exclusion; merged into the artifact)

WHY
---
The joint criterion's cells carry a measured CPR below 1.2989, so no CPR-only
test at fewer than ~79.6 looks can call them significant. The open objection is
that the operating point N = 13.72 is a frame-wide moment ENL of ONE linear
channel, not the look count at the cells the rule selects. Common texture
cancels in the ratio R = SC/OC, and for independent gamma channels
Var(ln R) = psi1(N_SC) + psi1(N_OC) (trigamma), so the look count governing R
can be read from the ratio itself. Taking N_SC = N_OC = N, N solves
2 psi1(N) = Var(ln R).

TWO STEPS
  1. Validate the estimator on synthetic fields at the product's lag
     correlations (N = 5, 14, 21, 38, 80, 120; texture off and gamma texture of
     shape 8 shared by both channels): N from Var(ln R) inside 31 x 31
     windows, its bias, and the coverage of a 95 % moving-block bootstrap.
  2. On the complex product, for every joint-selected cell (DOP < 0.13 and
     CPR > 1, physical sign), estimate N from Var(ln R) over the NON-SELECTED
     cells of its 31 x 31 neighbourhood; the same for as many random
     non-selected cells; the local circular coherence as a covariate; and the
     estimate for each of the 64 x 64 blocks. Run on both passes.

WHAT BIASES IT, AND WHICH WAY
  * terrain CPR variation inside a window adds variance to ln R: N biased LOW;
  * channel correlation (gamma_c > 0) removes variance: N biased HIGH;
  * texture common to both channels cancels exactly (the synthetic arm with
    texture reproduces the arm without it draw for draw, by construction).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.ndimage import uniform_filter
from scipy.special import polygamma
from scipy.stats import f as Fdist, spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402
import stokes_from_slc as SFS  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "enl_logratio.json"
SEED_VAL = 20260930
SEED_RAND = 20260931
WINDOW = 31
VAL_N = (5, 14, 21, 38, 80, 120)
VAL_SCENES = 10
VAL_SHAPE = (256, 256)
BOOT_B = 200
BOOT_BLOCK = 10
N_EDGE = 79.6166   # crit_95 of F(2N, 2N) equals 1.2988506 (detection_statistics.json::derived)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

# inverse of 2 psi1(N) by interpolation on a log grid (psi1 is monotone)
_NG = np.exp(np.linspace(np.log(0.05), np.log(1e5), 6000))
_VG = 2.0 * polygamma(1, _NG)


def n_from_var(v):
    """N solving 2 psi1(N) = v; NaN where v is not positive."""
    v = np.asarray(v, dtype=np.float64)
    out = np.interp(v, _VG[::-1], _NG[::-1], left=np.inf, right=_NG[0])
    return np.where(v > 0, out, np.nan)


def crit95(n):
    return Fdist.ppf(0.95, 2 * np.asarray(n), 2 * np.asarray(n))


# ---------------------------------------------------------------------------
# step 1: validation
# ---------------------------------------------------------------------------
def validate(lags) -> dict:
    import enl_benchmark as EB
    rng = np.random.default_rng(SEED_VAL)
    rho = (np.sqrt(lags[0]), np.sqrt(lags[1]))
    rows = []
    for n in VAL_N:
        for tex in ("off", "shape 8"):
            est, cov, widths = [], [], []
            sub = np.random.default_rng(rng.integers(1 << 62))
            for _ in range(VAL_SCENES):
                sc = EB.speckle_field(sub, n, *VAL_SHAPE, *rho, float("inf"))
                oc = EB.speckle_field(sub, n, *VAL_SHAPE, *rho, float("inf"))
                if tex != "off":
                    t = sub.gamma(8.0, 1.0 / 8.0, sc.shape)   # shared by both channels
                    sc, oc = sc * t, oc * t
                lr = np.log(sc / oc)
                H, W = lr.shape
                for r0 in range(0, H - WINDOW + 1, WINDOW):
                    for c0 in range(0, W - WINDOW + 1, WINDOW):
                        w = lr[r0:r0 + WINDOW, c0:c0 + WINDOW]
                        nh = float(n_from_var(w.var(ddof=1)))
                        est.append(nh)
                        # moving-block bootstrap inside the window
                        nb = (WINDOW // BOOT_BLOCK) ** 2
                        starts = sub.integers(0, WINDOW - BOOT_BLOCK + 1, (BOOT_B, nb, 2))
                        bs = np.empty(BOOT_B)
                        for b in range(BOOT_B):
                            pix = np.concatenate([w[a:a + BOOT_BLOCK, c:c + BOOT_BLOCK].ravel()
                                                  for a, c in starts[b]])
                            bs[b] = n_from_var(pix.var(ddof=1))
                        lo, hi = np.percentile(bs, [2.5, 97.5])
                        cov.append(lo <= n <= hi)
                        widths.append(hi - lo)
            est = np.array(est)
            c = float(np.mean(cov))
            rows.append({"true_N": n, "texture": tex, "windows": int(est.size),
                         "median_estimate": float(np.median(est)),
                         "relative_bias_median": float(np.median(est) / n - 1),
                         "relative_bias_mean": float(np.mean(est[np.isfinite(est)]) / n - 1),
                         "iqr": [float(np.percentile(est, 25)), float(np.percentile(est, 75))],
                         "boot95_coverage": c, "coverage_mc_se": float(np.sqrt(c * (1 - c) / est.size)),
                         "median_interval_width": float(np.median(widths))})
            print(f"    N {n:>3} texture {tex:<7}: median N_hat {np.median(est):7.2f} "
                  f"(bias {100 * (np.median(est) / n - 1):+5.1f} %), block-boot coverage "
                  f"{100 * c:5.1f} +/- {100 * np.sqrt(c * (1 - c) / est.size):.1f} %", flush=True)
    return {"window": WINDOW, "scenes_per_config": VAL_SCENES, "scene_shape": list(VAL_SHAPE),
            "lags_intensity": list(lags), "seed": SEED_VAL,
            "bootstrap": {"kind": "moving block", "block_px": BOOT_BLOCK,
                          "blocks_per_replicate": (WINDOW // BOOT_BLOCK) ** 2, "B": BOOT_B,
                          "interval": "percentile 2.5 / 97.5"},
            "rows": rows}


# ---------------------------------------------------------------------------
# step 2: the product
# ---------------------------------------------------------------------------
def local_n(lr, use, k=WINDOW):
    """N from Var(ln R) over the cells `use` inside the k x k window of every
    cell (ddof = 1), and the count behind it."""
    a = float(k * k)
    w = use.astype(np.float64)
    x = np.where(use, lr, 0.0)
    n = uniform_filter(w, k, mode="constant") * a
    s1 = uniform_filter(x, k, mode="constant") * a
    s2 = uniform_filter(x * x, k, mode="constant") * a
    with np.errstate(invalid="ignore", divide="ignore"):
        var = (s2 - s1 * s1 / n) / (n - 1)
    return n_from_var(np.where(n > 30, var, np.nan)), n


def describe(x):
    x = np.asarray(x, dtype=np.float64)
    x = x[np.isfinite(x)]
    if not x.size:
        return {"n": 0}
    return {"n": int(x.size), "median": float(np.median(x)),
            "iqr": [float(np.percentile(x, 25)), float(np.percentile(x, 75))],
            "p95": float(np.percentile(x, 95))}


def product(pass_id: str) -> dict:
    SFS.configure(pass_id)
    hh, vv, hv, info = SFS.build_coherency(0)
    s0, s1 = hh + vv, hh - vv
    s2, s3 = 2.0 * hv.real, -2.0 * hv.imag           # the physical sign (180 deg)
    m = (hh > 0) & (vv > 0) & (s0 > 0)
    del hh, vv, hv
    eps = 1e-300
    sc, oc = 0.5 * (s0 - s3), 0.5 * (s0 + s3)
    ok = m & (sc > 0) & (oc > 0)
    lr = np.where(ok, np.log(np.where(ok, sc, 1.0) / np.where(ok, oc, 1.0)), np.nan)
    R = np.exp(lr)
    dop = np.where(m, np.sqrt(s1 ** 2 + s2 ** 2 + s3 ** 2) / (s0 + eps), np.nan)
    gam = np.where(m, np.sqrt(s1 ** 2 + s2 ** 2) / np.sqrt(np.maximum(s0 ** 2 - s3 ** 2, eps)), np.nan)
    del s0, s1, s2, s3, sc, oc
    sel = ok & (dop < 0.13) & (R > 1.0)
    use = ok & ~sel
    nloc, cnt = local_n(lr, use)
    gam_loc = uniform_filter(np.where(use, gam, 0.0), WINDOW, mode="constant") / np.maximum(
        uniform_filter(use.astype(float), WINDOW, mode="constant"), 1e-12)

    rng = np.random.default_rng(SEED_RAND)
    si = np.flatnonzero(sel.ravel())
    pool = np.flatnonzero(use.ravel())
    ri = rng.choice(pool, size=si.size, replace=False)

    def stats(idx, label):
        n_ = nloc.ravel()[idx]
        r_ = R.ravel()[idx]
        g_ = gam.ravel()[idx]
        gl = gam_loc.ravel()[idx]
        fin = np.isfinite(n_)
        c_ = crit95(np.where(fin, n_, 1.0))
        sig = fin & (r_ > c_)
        rho_s = spearmanr(n_[fin], gl[fin]).statistic if fin.sum() > 2 else None
        return {"cells": int(idx.size), "local_N": describe(n_),
                "fraction_local_N_ge_79p6": float((n_[fin] >= N_EDGE).mean()) if fin.any() else None,
                "n_local_N_ge_79p6": int((n_[fin] >= N_EDGE).sum()),
                "n_R_above_crit_at_local_N": int(sig.sum()),
                "R": describe(r_), "gamma_c_cell": describe(g_),
                "gamma_c_window_mean": describe(gl),
                "spearman_localN_vs_window_gamma_c": (float(rho_s) if rho_s is not None else None),
                "window_count_used": describe(cnt.ravel()[idx])}
    out = {"pass": pass_id, "matched_cells": int(m.sum()), "selected_cells": int(sel.sum()),
           "selected": stats(si, "selected"), "random_non_selected": stats(ri, "random")}
    print(f"  pass {pass_id}: {int(sel.sum()):,} selected; local N median "
          f"{out['selected']['local_N'].get('median', float('nan')):.2f} (random "
          f"{out['random_non_selected']['local_N'].get('median', float('nan')):.2f}); "
          f">= 79.6: {out['selected']['n_local_N_ge_79p6']}; R > crit at local N: "
          f"{out['selected']['n_R_above_crit_at_local_N']}", flush=True)

    # the tail blocks, if the pass has them
    t3 = json.loads(SFS.OUT.read_text(encoding="utf-8"))["results"]["t3e"]["180_deg"]["blocks_64x64"]
    bn = []
    for b in t3:
        r0, c0 = b["row"], b["col"]
        k = SFS.BLOCK
        w = lr[r0:r0 + k, c0:c0 + k]
        u = ok[r0:r0 + k, c0:c0 + k]
        bn.append(float(n_from_var(w[u].var(ddof=1))))
    out["blocks_64x64"] = {"n": len(bn), "N_logratio": describe(bn),
                           "per_block": bn,
                           "compare_moment_enl_medians": {
                               "n_sc": float(np.median([b["n_sc"] for b in t3])) if t3 else None,
                               "n_oc": float(np.median([b["n_oc"] for b in t3])) if t3 else None}}
    del lr, R, dop, gam, nloc, cnt, gam_loc
    return out


def random_like_for_like(pass_id: str) -> dict:
    """B6 (final pass): the random non-selected cells' local N with the
    exclusion the selected cells get. product() already drops every selected
    cell from every window; a selected cell is also absent from its OWN window,
    a random cell was not. Here the random cells (the same draw: same seed,
    same pool) are dropped too, so every tested cell is estimated from
    neighbours only, as the selected cells are."""
    SFS.configure(pass_id)
    hh, vv, hv, _ = SFS.build_coherency(0)
    s0, s1 = hh + vv, hh - vv
    s2, s3 = 2.0 * hv.real, -2.0 * hv.imag
    m = (hh > 0) & (vv > 0) & (s0 > 0)
    del hh, vv, hv
    sc, oc = 0.5 * (s0 - s3), 0.5 * (s0 + s3)
    ok = m & (sc > 0) & (oc > 0)
    lr = np.where(ok, np.log(np.where(ok, sc, 1.0) / np.where(ok, oc, 1.0)), np.nan)
    dop = np.where(m, np.sqrt(s1 ** 2 + s2 ** 2 + s3 ** 2) / (s0 + 1e-300), np.nan)
    del s0, s1, s2, s3, sc, oc
    sel = ok & (dop < 0.13) & (np.exp(lr) > 1.0)
    use = ok & ~sel
    rng = np.random.default_rng(SEED_RAND)
    si = np.flatnonzero(sel.ravel())
    pool = np.flatnonzero(use.ravel())
    ri = rng.choice(pool, size=si.size, replace=False)
    n_old, _ = local_n(lr, use)
    use2 = use.copy().ravel()
    use2[ri] = False
    use2 = use2.reshape(use.shape)
    n_new, cnt = local_n(lr, use2)
    old = n_old.ravel()[ri]
    new = n_new.ravel()[ri]
    fin = np.isfinite(new)
    out = {"pass": pass_id, "cells": int(ri.size),
           "exclusion": ("every selected cell AND every random cell dropped from every window: "
                         "each tested cell estimated from neighbours only"),
           "local_N": describe(new),
           "n_local_N_ge_79p6": int((new[fin] >= N_EDGE).sum()),
           "window_count_used": describe(cnt.ravel()[ri]),
           "reproduces_random_non_selected": describe(old),
           "selected_for_comparison": describe(n_old.ravel()[si])}
    print(f"  pass {pass_id}: random cells, like for like: median {out['local_N'].get('median', float('nan')):.2f} "
          f"IQR {out['local_N'].get('iqr')}  (as before: {out['reproduces_random_non_selected'].get('median', float('nan')):.2f}; "
          f"selected {out['selected_for_comparison'].get('median', float('nan')):.2f}); >= 79.6: "
          f"{out['n_local_N_ge_79p6']}", flush=True)
    return out


def split_sample() -> dict:
    """v18a N6: select the homogeneous blocks on half the rows, estimate N on
    the other half, so the selection cannot pick blocks whose ln R happens to
    vary little.

    Ranking statistic, exactly as stokes_from_slc.low_cv_tiles defines it:
    over non-overlapping 64 x 64 tiles of the complex-product grid wholly
    inside the matched mask (hh > 0, vv > 0, S0 > 0), the coefficient of
    variation of S0, sd (ddof 1) / mean, over the tile's cells; the tiles
    below the 10th percentile of that CV are selected. Here the CV is computed
    on the even rows of each tile (32 x 64 cells) and N = psi_1-inverse of
    Var(ln R) / 2 on the odd rows' matched cells, then the roles swap."""
    SFS.configure("20200808")
    hh, vv, hv, _ = SFS.build_coherency(0)
    s0, s3 = hh + vv, -2.0 * hv.imag
    m = (hh > 0) & (vv > 0) & (s0 > 0)
    sc, oc = 0.5 * (s0 - s3), 0.5 * (s0 + s3)
    ok = m & (sc > 0) & (oc > 0)
    lr = np.where(ok, np.log(np.where(ok, sc, 1.0) / np.where(ok, oc, 1.0)), np.nan)
    del hh, vv, hv, s3, sc, oc
    k = SFS.BLOCK
    H, W = (s0.shape[0] // k) * k, (s0.shape[1] // k) * k
    S = s0[:H, :W].reshape(H // k, k, W // k, k).swapaxes(1, 2)
    Mm = m[:H, :W].reshape(H // k, k, W // k, k).swapaxes(1, 2)
    LR = lr[:H, :W].reshape(H // k, k, W // k, k).swapaxes(1, 2)
    inside = Mm.all(axis=(2, 3))
    out = {}
    for name, sel_rows, est_rows in (("select_even_estimate_odd", slice(0, k, 2), slice(1, k, 2)),
                                     ("select_odd_estimate_even", slice(1, k, 2), slice(0, k, 2)),
                                     ("full_sample_check", slice(0, k), slice(0, k))):
        sub = S[:, :, sel_rows, :]
        mu = sub.mean(axis=(2, 3))
        sd = sub.reshape(sub.shape[0], sub.shape[1], -1).std(axis=2, ddof=1)
        cv = np.where(inside & (mu > 0), sd / np.where(mu > 0, mu, 1.0), np.inf)
        thr = np.percentile(cv[inside], 10)
        chosen = np.argwhere(inside & (cv < thr))
        ns = []
        for i, j in chosen:
            v = LR[i, j][est_rows]
            v = v[np.isfinite(v)]
            if v.size > 30:
                ns.append(float(n_from_var(v.var(ddof=1))))
        out[name] = {"blocks": int(len(chosen)), "N_logratio": describe(ns),
                     "cv_threshold_10th_percentile": float(thr)}
    both = [out["select_even_estimate_odd"]["N_logratio"], out["select_odd_estimate_even"]["N_logratio"]]
    print(f"  split sample: even->odd median {both[0]['median']:.2f} IQR {both[0]['iqr']}; odd->even "
          f"{both[1]['median']:.2f} {both[1]['iqr']}; full-sample check {out['full_sample_check']['N_logratio']['median']:.2f}",
          flush=True)
    return {"ranking_statistic": ("coefficient of variation of S0 (sd with ddof 1 over mean) over a 64 x 64 "
                                  "tile's cells, tiles wholly inside the matched mask (hh > 0, vv > 0, S0 > 0), "
                                  "selected below the 10th percentile of the CV over those tiles "
                                  "(stokes_from_slc.low_cv_tiles)"),
            "split": "rows of each tile: CV on one parity, Var(ln R) on the other; then swapped",
            "reference": {"N_median": 39.4, "iqr": [28.5, 46.0], "blocks": 109,
                          "source": "pass_20200808.blocks_64x64.N_logratio"},
            **out}


def main() -> int:
    if "--split-sample" in sys.argv:
        doc = json.loads(OUT.read_text(encoding="utf-8"))
        doc["split_sample"] = split_sample()
        doc["run_info_split_sample"] = run_info()
        OUT.write_text(json.dumps(doc, indent=2, default=float), encoding="utf-8")
        print(f"  merged split_sample into {OUT.relative_to(BASE_DIR)}")
        return 0
    if "--only-random" in sys.argv:
        doc = json.loads(OUT.read_text(encoding="utf-8"))
        doc["random_like_for_like"] = {p: random_like_for_like(p) for p in ("20200808", "20200305")}
        doc["run_info_random_like_for_like"] = run_info()
        OUT.write_text(json.dumps(doc, indent=2, default=float), encoding="utf-8")
        print(f"  merged random_like_for_like into {OUT.relative_to(BASE_DIR)}")
        return 0
    print("=" * 78)
    print("TASK 2 — the look count from Var(ln R), validated, then at the selected cells")
    print("=" * 78)
    enl = json.loads((BASE_DIR / "docs/enl.json").read_text(encoding="utf-8"))
    lags = (enl["lag_correlation"]["LH"]["azimuth_lines"][0], enl["lag_correlation"]["LH"]["range_samples"][0])
    print("  step 1: validation on synthetic fields", flush=True)
    val = validate(lags)
    print("  step 2: the complex product", flush=True)
    p1 = product("20200808")
    p2 = product("20200305")
    OUT.write_text(json.dumps({
        "schema": "lunar-ice/enl-logratio/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/enl_logratio.py",
        "estimator": ("N solving 2 psi1(N) = Var(ln R), R = SC/OC at the physical sign, "
                      "N_SC = N_OC = N assumed; Var with ddof = 1"),
        "window": WINDOW, "n_edge": N_EDGE,
        "seeds": {"validation": SEED_VAL, "random_cells": SEED_RAND},
        "bias_directions": {
            "terrain_cpr_variation_in_window": "adds variance -> N biased LOW",
            "channel_correlation_gamma_c": "removes variance -> N biased HIGH",
            "texture_common_to_both_channels": "cancels exactly in R"},
        "validation": val,
        "pass_20200808": p1, "pass_20200305": p2,
        "run_info": run_info()}, indent=2, default=float), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
