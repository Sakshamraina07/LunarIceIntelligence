"""
bootstrap_enl.py -- confidence intervals for the measured ENL, using
measure_enl.py's estimator UNCHANGED, then propagated through F(2N, 2N).

    python backend/scripts/bootstrap_enl.py [--B 2000] [--seed 2026]

WHY TWO BOOTSTRAPS
------------------
A simple bootstrap resamples the per-patch ratios as if they were independent.
They are not: azimuth neighbours are correlated at lag one by +0.838, and the
patch grid inherits some of that. The BLOCK bootstrap resamples whole ROWS of the
patch grid -- one row is an azimuth band PATCH lines high (16 px = 400 m on the
25 m grid) spanning the full range extent -- so whatever correlation runs along
azimuth is kept inside the resampling unit. Both are reported; where they
disagree, the block interval is the honest one.

Ported from the reference `Claude outputs/bootstrap_enl.py`: the estimator is
imported, not re-implemented, and the interval is the percentile interval at
2.5 / 97.5 -- not BCa, and that is stated in the artifact.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import tifffile
from scipy.ndimage import binary_erosion, uniform_filter
from scipy.stats import f as Fdist

BASE_DIR = Path(__file__).resolve().parents[2]
RAW = BASE_DIR / "data/pradan/raw/data/calibrated/20200808"
STEM = "ch2_sar_ncxl_20200808t201154198_d_sri_xx_cp_{ch}_d18.tif"
OUT = BASE_DIR / "docs" / "bootstrap_enl.json"

PATCH = 16
B_DEFAULT = 2000
SEED_DEFAULT = 2026
BOXCAR = 5
TRUE_CPR = 0.7
PERCENTILES = (2.5, 97.5)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def _measure_enl():
    """THEIR functions, unmodified."""
    spec = importlib.util.spec_from_file_location(
        "_measure_enl", Path(__file__).with_name("measure_enl.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_ME = _measure_enl()
patch_ratios, mode_of = _ME.patch_ratios, _ME.mode_of


def ratio_grid(a: np.ndarray, mask: np.ndarray, p: int) -> np.ndarray:
    """Per-patch mean^2/var on the (rows, cols) patch grid; NaN where a patch is
    not wholly inside the mask or has zero variance. Same arithmetic as
    patch_ratios, kept on the grid so rows can be resampled."""
    h, w = (a.shape[0] // p) * p, (a.shape[1] // p) * p
    blk = a[:h, :w].reshape(h // p, p, w // p, p).swapaxes(1, 2)
    vb = mask[:h, :w].reshape(h // p, p, w // p, p).swapaxes(1, 2)
    vb = vb.reshape(h // p, w // p, p * p).all(axis=2)
    flat = blk.reshape(h // p, w // p, p * p).astype(np.float64)
    m = flat.mean(axis=2)
    v = flat.var(axis=2, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        rat = np.where(v > 0, m * m / v, np.nan)
    return np.where(vb, rat, np.nan)


def simple_boot(r: np.ndarray, B: int, rng) -> np.ndarray:
    n = r.size
    return np.array([mode_of(r[rng.integers(0, n, n)]) for _ in range(B)])


def block_boot(rat: np.ndarray, B: int, rng) -> np.ndarray:
    """Resample whole ROWS of the patch grid (azimuth bands) with replacement."""
    R = rat.shape[0]
    out = np.empty(B)
    for b in range(B):
        s = rat[rng.integers(0, R, R)].ravel()
        s = s[np.isfinite(s) & (s > 0)]
        out[b] = mode_of(s)
    return out


def ci(b: np.ndarray) -> list:
    return [float(np.percentile(b, PERCENTILES[0])),
            float(np.percentile(b, PERCENTILES[1]))]


def fp(n: float) -> float:
    return float((1.0 - Fdist.cdf(1.0 / TRUE_CPR, 2 * n, 2 * n)) * 100.0)


def floor95(n: float) -> float:
    return float(Fdist.ppf(0.95, 2 * n, 2 * n))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=B_DEFAULT)
    ap.add_argument("--seed", type=int, default=SEED_DEFAULT)
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)

    lh = tifffile.imread(str(RAW / STEM.format(ch="lh"))).astype(np.float64)
    lv = tifffile.imread(str(RAW / STEM.format(ch="lv"))).astype(np.float64)
    valid = (lh > 0) & (lv > 0)
    inner = binary_erosion(valid, np.ones((BOXCAR, BOXCAR), bool))
    print("=" * 78)
    print(f"BOOTSTRAP ENL — B = {args.B:,}, seed {args.seed}, patch {PATCH}, "
          f"rows of the patch grid = {PATCH} px = {PATCH * 25} m")
    print("=" * 78)
    print(f"  amplitude mask {int(valid.sum()):,} px; eroded by {BOXCAR}x{BOXCAR}: "
          f"{int(inner.sum()):,} px")

    res: dict = {}
    for ch, dn in (("LH", lh), ("LV", lv)):
        i_raw = dn * dn
        i_box = uniform_filter(i_raw, size=BOXCAR)
        r_raw = patch_ratios(i_raw, inner, PATCH)
        r_box = patch_ratios(i_box, inner, PATCH)
        pt_raw, pt_box = mode_of(r_raw), mode_of(r_box)
        b_raw, b_box = simple_boot(r_raw, args.B, rng), simple_boot(r_box, args.B, rng)
        g_raw, g_box = ratio_grid(i_raw, inner, PATCH), ratio_grid(i_box, inner, PATCH)
        bb_raw, bb_box = block_boot(g_raw, args.B, rng), block_boot(g_box, args.B, rng)
        fp_b, fl_b = np.array([fp(n) for n in b_box]), np.array([floor95(n) for n in b_box])
        fp_bb, fl_bb = np.array([fp(n) for n in bb_box]), np.array([floor95(n) for n in bb_box])
        res[ch] = {
            "n_patches": int(r_raw.size),
            "patch_grid_rows": int(g_raw.shape[0]), "patch_grid_cols": int(g_raw.shape[1]),
            "rows_with_any_patch": int(np.isfinite(g_raw).any(axis=1).sum()),
            "enl_raw": pt_raw, "enl_raw_ci_simple": ci(b_raw), "enl_raw_ci_block": ci(bb_raw),
            "enl_box": pt_box, "enl_box_ci_simple": ci(b_box), "enl_box_ci_block": ci(bb_box),
            "fp_point": fp(pt_box), "fp_ci_simple": ci(fp_b), "fp_ci_block": ci(fp_bb),
            "floor_point": floor95(pt_box), "floor_ci_simple": ci(fl_b),
            "floor_ci_block": ci(fl_bb),
            "bootstrap_sd_block_raw": float(bb_raw.std(ddof=1)),
            "bootstrap_sd_block_box": float(bb_box.std(ddof=1)),
        }
        r = res[ch]
        print(f"\n  {ch}: {r['n_patches']:,} patches on a {r['patch_grid_rows']} x "
              f"{r['patch_grid_cols']} grid ({r['rows_with_any_patch']} rows populated)")
        print(f"    ENL raw  {pt_raw:.4f}  simple {r['enl_raw_ci_simple']}  block {r['enl_raw_ci_block']}")
        print(f"    ENL 5x5  {pt_box:.4f}  simple {r['enl_box_ci_simple']}  block {r['enl_box_ci_block']}")
        print(f"    FP@0.7   {r['fp_point']:.2f} %  block {r['fp_ci_block']}")
        print(f"    floor95  {r['floor_point']:.3f}  block {r['floor_ci_block']}")

    res.update({
        "schema": "lunar-ice/bootstrap-enl/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/bootstrap_enl.py",
        "seed": args.seed, "B": args.B, "patch": PATCH,
        "resampling_unit_block": f"whole rows of the {PATCH}x{PATCH} patch grid: one row "
                                 f"is an azimuth band {PATCH} px = {PATCH * 25} m high "
                                 "spanning the full range extent",
        "resampling_unit_simple": "individual patches, i.i.d.",
        "interval_method": f"percentile, {PERCENTILES[0]} / {PERCENTILES[1]}; not BCa",
        "mask": f"amplitude mask (LH>0 & LV>0) eroded by the {BOXCAR}x{BOXCAR} boxcar "
                "footprint, so no window reaches a zero-fill pixel",
        "estimator": "measure_enl.patch_ratios (ddof=1) + measure_enl.mode_of "
                     "(120-bin log-space histogram), imported unmodified",
        "propagation": f"FP = 1 - F(1/{TRUE_CPR}; 2N, 2N) and floor = F^-1(0.95; 2N, 2N) "
                       "at each replicate's post-boxcar ENL",
        "true_cpr": TRUE_CPR,
    })
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
