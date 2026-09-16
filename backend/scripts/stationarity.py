"""
stationarity.py -- is the ENL one number across the frame?

    python backend/scripts/stationarity.py

WHY
---
The frame-wide ENL is the mode over 8,337 patches. If the population those
patches come from is not stationary -- different terrain, different
correlation, different texture in different parts of the frame -- then the
frame-wide value is a mode over a heterogeneous population and every downstream
statistic is a frame-wide summary, not a local one. This splits the frame into
azimuth thirds x range halves and measures, per block with enough coverage, the
16x16 mode on LH DN^2 (the estimator, unchanged) and the lag-one correlations.

    manuscript: "over the four spatial blocks with sufficient coverage, the
    16x16 mode ranges from 3.3 to 8.0"

Ported verbatim from block D3 of Claude outputs/reviewer2_computations.py; no
random numbers are involved.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import tifffile
from scipy.ndimage import binary_erosion

BASE_DIR = Path(__file__).resolve().parents[2]
RAW = BASE_DIR / "data/pradan/raw/data/calibrated/20200808"
STEM = "ch2_sar_ncxl_20200808t201154198_d_sri_xx_cp_{ch}_d18.tif"
OUT = BASE_DIR / "docs" / "stationarity.json"
MIN_VALID = 5000
PATCH = 16

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def _measure_enl():
    spec = importlib.util.spec_from_file_location(
        "_measure_enl", Path(__file__).with_name("measure_enl.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.patch_ratios, mod.mode_of


def lag1(a, mask, axis):
    m = mask & np.roll(mask, -1, axis)
    x, y = a[m], np.roll(a, -1, axis)[m]
    x, y = x - x.mean(), y - y.mean()
    return float((x * y).mean() / np.sqrt((x * x).mean() * (y * y).mean()))


def main() -> int:
    patch_ratios, mode_of = _measure_enl()
    lh = tifffile.imread(str(RAW / STEM.format(ch="lh"))).astype(np.float64)
    lv = tifffile.imread(str(RAW / STEM.format(ch="lv"))).astype(np.float64)
    valid = (lh > 0) & (lv > 0)
    inner = binary_erosion(valid, np.ones((5, 5), bool))
    i2 = lh * lh
    H, W = lh.shape
    print("=" * 78)
    print("STATIONARITY — 16x16 mode ENL (LH) over azimuth thirds x range halves")
    print("=" * 78)
    blocks = []
    for ai, (r0, r1) in enumerate(((0, H // 3), (H // 3, 2 * H // 3), (2 * H // 3, H))):
        for ri, (c0, c1) in enumerate(((0, W // 2), (W // 2, W))):
            sub, msk = i2[r0:r1, c0:c1], inner[r0:r1, c0:c1]
            if msk.sum() < MIN_VALID:
                blocks.append({"az_third": ai, "range_half": ri, "n_valid": int(msk.sum()),
                               "enl": None, "reason": f"fewer than {MIN_VALID} valid px"})
                print(f"  az-third {ai} range-half {ri}: valid {int(msk.sum()):>8,} px  -- insufficient")
                continue
            rr = patch_ratios(sub, msk, PATCH)
            e = float(mode_of(rr)) if rr.size > 50 else float("nan")
            la, lr = lag1(sub, msk, 0), lag1(sub, msk, 1)
            blocks.append({"az_third": ai, "range_half": ri, "n_valid": int(msk.sum()),
                           "n_patches": int(rr.size), "enl": e, "lag1_az": la, "lag1_rg": lr})
            print(f"  az-third {ai} range-half {ri}: valid {int(msk.sum()):>8,} px  patches "
                  f"{rr.size:>5}  ENL mode {e:5.2f}  lag1 az {la:.3f} rg {lr:.3f}")
    used = [b for b in blocks if b.get("enl") is not None and np.isfinite(b["enl"])]
    lo, hi = min(b["enl"] for b in used), max(b["enl"] for b in used)
    print(f"\n  {len(used)} blocks with sufficient coverage: mode ranges {lo:.2f} to {hi:.2f}")
    OUT.write_text(json.dumps({
        "schema": "lunar-ice/stationarity/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/stationarity.py",
        "patch": PATCH, "min_valid_px": MIN_VALID,
        "mask": "amplitude mask eroded 5x5 (the ENL measurement mask)",
        "blocks": blocks, "n_blocks_used": len(used),
        "enl_min": lo, "enl_max": hi,
        "claim": "the frame-wide ENL is a mode over a heterogeneous population",
    }, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
