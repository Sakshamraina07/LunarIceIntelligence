"""
dop_exclusion.py -- what the amplitudes DO decide: the exclusion split.

    python backend/scripts/dop_exclusion.py

WHY THIS EXISTS
---------------
The manuscript's one positive statement about the amplitude product is a
counting statement: since the true DOP is at least DOP_a, a pixel with
DOP_a >= 0.13 CANNOT satisfy the DOP condition whatever its phase, so those
pixels are excluded on the amplitudes alone; the rest are undecidable. The
split is 40.21 % excluded / 59.79 % undecidable.

Until now those two figures lived in ONE place: `fig1_density.npz`, a binary
histogram cache beside the figure script. A number whose only home is a plot's
input cache is a number nobody can check, and the density block that wrote it
is not part of the pipeline. This recomputes the split from the delivered
rasters in the repository's own code path, and asserts it against the cache the
published figure was drawn from, so the figure and the sentence are the same
measurement.

WHAT IS AND IS NOT APPLIED
--------------------------
    l_X = (DN_X / G_X)^2
The per-channel gain imbalance G_X does NOT cancel in a ratio and is applied.
The calibration constant K and sin(theta) are common to both channels and
cancel exactly in both CPR_a and DOP_a, so they are omitted -- and omitting
them is what makes this reproducible from the rasters alone. No boxcar: the
statement, like Fig. 1, is about the delivered pixels.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import tifffile

BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
RAW = BASE_DIR / "data/pradan/raw/data/calibrated/20200808"
STEM = "ch2_sar_ncxl_20200808t201154198_d_sri_xx_cp_{ch}_d18.tif"
LABEL = RAW / "ch2_sar_ncxl_20200808t201154198_d_sri_xx_cp_xx_d18.xml"
OUT = BASE_DIR / "docs" / "dop_exclusion.json"
#: the histogram the published Fig. 1 is drawn from
NPZ = BASE_DIR / "Claude outputs" / "grsl" / "fig1_density.npz"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def main() -> int:
    from app.core.config import settings as cfg
    from app.ingestion.sar_geometry import parse_calibration

    dop_th = float(cfg.DOP_THRESHOLD)
    cal = parse_calibration(LABEL)
    g_lh = float(cal["channels"]["LH"]["gain_imbalance"])
    g_lv = float(cal["channels"]["LV"]["gain_imbalance"])

    lh = tifffile.imread(str(RAW / STEM.format(ch="lh"))).astype(np.float64)
    lv = tifffile.imread(str(RAW / STEM.format(ch="lv"))).astype(np.float64)
    m = (lh > 0) & (lv > 0)
    ih = (lh[m] / g_lh) ** 2
    iv = (lv[m] / g_lv) ** 2
    del lh, lv

    dop = np.abs(ih - iv) / (ih + iv)
    sh, sv = np.sqrt(ih), np.sqrt(iv)
    cpr = ((sh - sv) / (sh + sv)) ** 2
    n = int(dop.size)
    admitted = int((dop < dop_th).sum())
    excluded = n - admitted
    max_cpr_in_band = float(cpr[dop < dop_th].max())

    print("=" * 78)
    print(f"WHAT THE AMPLITUDES DECIDE — DOP_a against the published {dop_th}")
    print("=" * 78)
    print(f"  gains applied: G_LH {g_lh:.6f}, G_LV {g_lv:.6f}   "
          f"(K and sin(theta) cancel)")
    print(f"  measured pixels (DN > 0 in both channels)   {n:,}")
    print(f"  DOP_a >= {dop_th}: EXCLUDED, whatever the phase   "
          f"{excluded:,}  = {100 * excluded / n:.2f} %")
    print(f"  DOP_a <  {dop_th}: undecidable from amplitudes    "
          f"{admitted:,}  = {100 * admitted / n:.2f} %")
    print(f"  largest CPR_a among the admitted pixels      {max_cpr_in_band:.10f}")
    print("\n  The exclusion is one-sided and that is the whole content: the true")
    print("  DOP is at least DOP_a, so a pixel above the threshold cannot come")
    print("  back under it. A pixel below it decides nothing.")

    cache = {"present": NPZ.is_file()}
    if NPZ.is_file():
        z = np.load(NPZ)
        cache.update({"path": str(NPZ.relative_to(BASE_DIR)).replace("\\", "/"),
                      "n": int(z["n"]), "n_band": int(z["n_band"]),
                      "max_cpr_in_band": float(z["max_cpr_in_band"])})
        agree = (cache["n"] == n and cache["n_band"] == admitted)
        cache["agrees_with_this_run"] = bool(agree)
        print(f"\n  published figure cache: n {cache['n']:,}, in band "
              f"{cache['n_band']:,}  ->  {'AGREES' if agree else 'DISAGREES'}")
        if not agree:
            print("  THE FIGURE AND THE SENTENCE ARE NOT THE SAME MEASUREMENT.")
            return 1
    else:
        print("\n  published figure cache: ABSENT — nothing to cross-check against")

    OUT.write_text(json.dumps({
        "schema": "lunar-ice/dop-exclusion/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/dop_exclusion.py",
        "dop_threshold": dop_th,
        "gain_imbalance": {"LH": g_lh, "LV": g_lv},
        # III-A prints the ortho label's constant with its unit and the linear
        # factor built from it. The SLC label declares 80.0 dB, a different
        # product's constant (stokes_from_slc.json::calibration.K_db); this is
        # the sri one, read from the same label as the gains above.
        "calibration": {
            "product": "sri (ortho-rectified, Level-2) -- " + LABEL.name,
            "K_db": float(cal["calibration_constant_db"]),
            "K_db_unit": "dB",
            "K_lin": 10.0 ** (float(cal["calibration_constant_db"]) / 10.0),
            "K_lin_definition": "K = 10^(K_dB / 10)",
            "equation": "l_X = DN_X^2 sin(theta_inc) / (K G_X^2)",
            "cancels_here": "K and sin(theta_inc) are common to both channels"},
        "formula": "l_X = (DN_X / G_X)^2; DOP_a = |l_H - l_V| / (l_H + l_V); "
                   "CPR_a = ((sqrt l_H - sqrt l_V)/(sqrt l_H + sqrt l_V))^2; "
                   "K and sin(theta) are common to both channels and cancel",
        "smoothing": "none — the delivered pixels, before the 5x5 boxcar, as in Fig. 1",
        "measured_pixels": n,
        "excluded_pixels": excluded,
        "excluded_fraction": excluded / n,
        "excluded_percent": 100.0 * excluded / n,
        "undecidable_pixels": admitted,
        "undecidable_fraction": admitted / n,
        "undecidable_percent": 100.0 * admitted / n,
        "max_cpr_a_among_undecidable": max_cpr_in_band,
        "why_one_sided": ("the true DOP is at least DOP_a, so DOP_a >= threshold "
                          "excludes a pixel whatever its phase; DOP_a < threshold "
                          "decides nothing"),
        "figure_cache_cross_check": cache,
    }, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
