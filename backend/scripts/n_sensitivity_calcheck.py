"""
n_sensitivity_calcheck.py -- is the achieved log-ratio N of region_mean_null's
correlated model what the artifact says? (v21 work order, W1E)

    python backend/scripts/n_sensitivity_calcheck.py

region_mean_null.correlated calibrates the looks-per-channel L against the target
N on four realizations of the region's own bounding box (a few hundred correlated
cells), once per region size and run. n_sensitivity_region.py recalibrated on four
200 x 200 realizations and read L = 19 at 53 looks where the artifact (260 cells,
target 80) reports 75.9. This repeats the big-field calibration with other seeds
and a different field size (8 realizations of 256 x 256, then 4 of 200 x 200) for the L
values in question, and repeats the artifact's own small-box calibration 40 times
to show its spread. Seeds 20261061-20261063. Writes docs/n_sensitivity_calcheck.json.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.ndimage import uniform_filter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402
import region_mean_null as RM  # noqa: E402
import f2_maximum as F2M  # noqa: E402
import enl_logratio as L  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "n_sensitivity_calcheck.json"
LS = (5, 13, 19, 28, 37)
M = 4


def nlog(rng, Lk, shape, batch, rsc, roc, mask=None):
    H, W = shape
    sc = np.zeros((batch, H + 2 * M, W + 2 * M)); oc = np.zeros_like(sc)
    for _ in range(Lk):
        wo = F2M.ar1_stationary(rng, (H + 2 * M, W + 2 * M), *roc, batch)
        ws = F2M.ar1_stationary(rng, (H + 2 * M, W + 2 * M), *rsc, batch)
        sc += np.abs(np.sqrt(0.5) * ws) ** 2; oc += np.abs(np.sqrt(0.5) * wo) ** 2
    f = lambda v: uniform_filter(v, size=(1, 5, 5), mode="reflect")  # noqa: E731
    bs, bo = f(sc / Lk), f(oc / Lk)
    return float(L.n_from_var(np.var(np.log(bs / bo)[:, M:-M, M:-M], ddof=1)))


def main() -> int:
    t0 = time.time()
    gc = json.loads((BASE_DIR / "docs" / "complex_grid_correlation.json").read_text(encoding="utf-8"))["lag_correlation_before_boxcar"]
    rsc = (float(np.sqrt(gc["SC"]["azimuth_lines"][0])), float(np.sqrt(gc["SC"]["range_samples"][0])))
    roc = (float(np.sqrt(gc["OC"]["azimuth_lines"][0])), float(np.sqrt(gc["OC"]["range_samples"][0])))
    mask = RM.ellipse(260)
    bbox = mask.shape
    res = {}
    for Lk in LS:
        rng = np.random.default_rng(20261061 + Lk)
        big256 = nlog(rng, Lk, (256, 256), 8, rsc, roc)
        big200 = nlog(rng, Lk, (200, 200), 4, rsc, roc)
        small = [nlog(rng, Lk, bbox, 4, rsc, roc) for _ in range(40)]
        res[str(Lk)] = {"N_256x256_x8": big256, "N_200x200_x4": big200, "small_box_bbox": list(bbox),
                        "small_box_40_repeats": {"mean": float(np.mean(small)), "sd": float(np.std(small, ddof=1)),
                                                 "min": float(np.min(small)), "max": float(np.max(small))}}
        s = res[str(Lk)]["small_box_40_repeats"]
        print(f"  L={Lk}: big fields {big256:.1f} / {big200:.1f}; artifact-style small box {s['mean']:.1f} +/- {s['sd']:.1f} (range {s['min']:.1f}-{s['max']:.1f})", flush=True)
    doc = {"schema": "lunar-ice/n-sensitivity-calcheck/1", "generated_utc": datetime.now(timezone.utc).isoformat(),
           "generator": "backend/scripts/n_sensitivity_calcheck.py", "seed": [20261061 + l for l in LS],
           "artifact_values": {"260 cells, target 80 -> L 19 reported achieved N": 75.86695836166379},
           "results": res, "run_info": {**run_info(), "wall_s": round(time.time() - t0, 1)}}
    OUT.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print(f"  wrote {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
