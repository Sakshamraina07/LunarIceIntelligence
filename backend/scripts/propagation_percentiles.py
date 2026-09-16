"""
propagation_percentiles.py -- P6. How far does sin(theta) move the screening?

    python backend/scripts/propagation_percentiles.py

incidence_audit.py already shows the screening does not move -- zero pixels
pass with or without sin(theta) -- and reports the MAXIMUM |dCPR_a| and
|dDOP_a| over the amplitude mask (0.0131 and 0.139). A maximum on its own says
nothing about where it sits or how typical it is. So: the 50th, 90th and 99th
percentiles and the maximum of both differences, the location of the maximum,
and a map of |dDOP_a| written as a PNG under docs/ so the paper can say whether
the maximum sits on a boundary of the mask.

The two pipelines are incidence_audit.screen(True) and screen(False), copied
verbatim: float32 DN, the 5x5 boxcar (uniform_filter, mode="nearest") applied
AFTER the per-channel calibration, and the ratios formed on the boxcar output.
sin(theta) multiplies both channels, so every difference here is float32
round-off through the boxcar -- which is why the percentiles are the point.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import tifffile
from scipy.ndimage import binary_erosion, uniform_filter

BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
RAW = BASE_DIR / "data" / "pradan" / "raw" / "data" / "calibrated" / "20200808"
NATIVE = BASE_DIR / "data" / "pradan" / "native"
STEM = "ch2_sar_ncxl_20200808t201154198"
OUT = BASE_DIR / "docs" / "propagation_percentiles.json"
PNG = BASE_DIR / "docs" / "propagation_ddop_map.png"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def boxcar(a: np.ndarray, k: int = 5) -> np.ndarray:
    return uniform_filter(a, size=k, mode="nearest")


def pct(x: np.ndarray) -> dict:
    return {"p50": float(np.percentile(x, 50)), "p90": float(np.percentile(x, 90)),
            "p99": float(np.percentile(x, 99)), "max": float(x.max()),
            "mean": float(x.mean()), "n": int(x.size)}


def main() -> int:
    from app.ingestion.sar_geometry import parse_calibration
    cal = parse_calibration(RAW / f"{STEM}_d_sri_xx_cp_xx_d18.xml")
    K = 10.0 ** (float(cal["calibration_constant_db"]) / 10.0)
    g_lh = float(cal["channels"]["LH"]["gain_imbalance"])
    g_lv = float(cal["channels"]["LV"]["gain_imbalance"])
    lh = tifffile.imread(str(RAW / f"{STEM}_d_sri_xx_cp_lh_d18.tif")).astype(np.float32)
    lv = tifffile.imread(str(RAW / f"{STEM}_d_sri_xx_cp_lv_d18.tif")).astype(np.float32)
    inc = tifffile.imread(str(RAW / f"{STEM}_d_sri_in_cp_xx_d18.tif")).astype(np.float64)
    valid = np.asarray(tifffile.imread(str(NATIVE / "valid_native.tif"))) > 0

    def screen(use_sin: bool):
        s = np.sin(np.deg2rad(inc)).astype(np.float32) if use_sin else np.float32(1.0)
        a = boxcar((lh ** 2 * s) / (K * g_lh ** 2))
        b = boxcar((lv ** 2 * s) / (K * g_lv ** 2))
        ra, rb = np.sqrt(np.maximum(a, 0)), np.sqrt(np.maximum(b, 0))
        sc, oc = 0.5 * (ra - rb) ** 2, 0.5 * (ra + rb) ** 2
        with np.errstate(divide="ignore", invalid="ignore"):
            cpr = np.where(oc > 0, sc / oc, 0.0)
            dop = np.where((a + b) > 0, np.abs(a - b) / (a + b), 0.0)
        return cpr, dop

    cpr_w, dop_w = screen(True)
    cpr_o, dop_o = screen(False)
    d_cpr = np.abs(cpr_w - cpr_o).astype(np.float64)
    d_dop = np.abs(dop_w - dop_o).astype(np.float64)
    interior = binary_erosion(valid, np.ones((5, 5), bool))
    edge = valid & ~interior

    print("=" * 78)
    print("PROPAGATION OF sin(theta): |dCPR_a| and |dDOP_a| over the amplitude mask")
    print("=" * 78)
    res = {}
    for name, d in (("cpr", d_cpr), ("dop", d_dop)):
        allm, inn, edg = pct(d[valid]), pct(d[interior]), pct(d[edge])
        k = np.unravel_index(int(np.argmax(np.where(valid, d, -1.0))), d.shape)
        on_edge = bool(edge[k])
        res[name] = {"over_amplitude_mask": allm, "interior_5x5_eroded": inn,
                     "edge_band_within_2px_of_mask_boundary": edg,
                     "argmax": {"line": int(k[0]), "sample": int(k[1]),
                                "on_mask_edge": on_edge,
                                "value_with_sin": float((cpr_w if name == "cpr" else dop_w)[k]),
                                "value_without": float((cpr_o if name == "cpr" else dop_o)[k])}}
        print(f"  |d{name.upper()}_a|  p50 {allm['p50']:.3e}  p90 {allm['p90']:.3e}  "
              f"p99 {allm['p99']:.3e}  max {allm['max']:.3e}  "
              f"(max at line {k[0]}, sample {k[1]}, {'ON' if on_edge else 'NOT on'} the mask edge)")
        print(f"        interior max {inn['max']:.3e}   edge-band max {edg['max']:.3e}")
    n_w = int(((cpr_w > 1.0) & (dop_w < 0.13))[valid].sum())
    n_o = int(((cpr_o > 1.0) & (dop_o < 0.13))[valid].sum())
    print(f"  pixels passing CPR > 1 and DOP < 0.13: with {n_w}, without {n_o}")

    # the map
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        img = np.where(valid, d_dop, np.nan)
        fig, ax = plt.subplots(figsize=(12, 4.6), dpi=110)
        im = ax.imshow(np.log10(np.maximum(img, 1e-9)), cmap="viridis", aspect="auto",
                       interpolation="nearest")
        ax.plot(res["dop"]["argmax"]["sample"], res["dop"]["argmax"]["line"], "r+", ms=14, mew=1.5)
        ax.set_title("|ΔDOP_a| between the with-sin(θ) and without-sin(θ) pipelines "
                     "(log10; red + = maximum)")
        ax.set_xlabel("sample"); ax.set_ylabel("line")
        fig.colorbar(im, ax=ax, label="log10 |ΔDOP_a|")
        fig.tight_layout(); fig.savefig(PNG); plt.close(fig)
        png_status = str(PNG.relative_to(BASE_DIR))
    except Exception as exc:  # noqa: BLE001
        png_status = f"NOT WRITTEN: {exc}"
    print(f"  map: {png_status}")

    OUT.write_text(json.dumps({
        "schema": "lunar-ice/propagation-percentiles/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/propagation_percentiles.py",
        "pipelines": "incidence_audit.screen(True) vs screen(False), verbatim: float32 "
                     "DN, per-channel calibration, 5x5 uniform_filter mode='nearest', "
                     "ratios on the boxcar output",
        "mask": {"amplitude_px": int(valid.sum()), "interior_px": int(interior.sum()),
                 "edge_band_px": int(edge.sum()),
                 "edge_definition": "amplitude mask minus its 5x5 binary erosion"},
        "pixels_passing": {"with_sin": n_w, "without_sin": n_o},
        "map_png": png_status,
        **res,
    }, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
