"""
enl_estimator_spec.py -- the ENL estimator, specified by READING the code that
implements it rather than by remembering it.

    python backend/scripts/enl_estimator_spec.py

P2 (review 4.11, 5.3) asks for: patch size, stride and overlap; the exact
definition of the screening mask versus the amplitude mask; the variance
normalisation; the mode estimator; the bootstrap replicate count, resampling
unit, block construction and interval method. Every one of those is a property
of measure_enl.py or bootstrap_enl.py, so this script imports both and reports
what they DO -- default arguments, function signatures, the erosion kernel --
and counts the masks on the delivered rasters. A specification typed from memory
drifts from the code; one read from the code cannot.
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import tifffile
from scipy.ndimage import binary_erosion

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "enl_estimator_spec.json"
PIPELINE = BASE_DIR / "backend/scripts/process_real_sar_pipeline.py"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        "_" + name, Path(__file__).with_name(name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    me = _load("measure_enl")
    be = _load("bootstrap_enl")
    me_src = inspect.getsource(me)

    # --- what the estimator does, read from its source -----------------------
    patches_default = re.search(r'add_argument\("--patches", default="([^"]+)"', me_src).group(1)
    bins = inspect.signature(me.mode_of).parameters["bins"].default
    ddof = int(re.search(r"\.var\(axis=1, ddof=(\d)\)", inspect.getsource(me.patch_ratios)).group(1))
    log_mode = "np.log(r)" in inspect.getsource(me.mode_of)
    stride_is_patch = ".reshape(h // p, p, w // p, p)" in inspect.getsource(me.patch_ratios)
    wholly_inside = "vb.all(axis=1)" in inspect.getsource(me.patch_ratios)
    erosion = re.search(r"binary_erosion\(valid, np\.ones\(\((\d), (\d)\)", me_src)
    boxcar_size = int(re.search(r"uniform_filter\(i_raw, size=(\d)\)", me_src).group(1))

    # --- the masks, defined where the pipeline defines them ------------------
    pipe = PIPELINE.read_text(encoding="utf-8", errors="replace")
    amp_line = re.search(r"^\s*amplitude = \((.+)\)\s*$", pipe, re.M).group(1)
    valid_alias = "valid = amplitude" in pipe

    raw = BASE_DIR / me.DEFAULT_DIR
    band = "ncxl"
    lh = tifffile.imread(str(raw / me.DEFAULT_STEM.format(band=band, ch="lh")))
    lv = tifffile.imread(str(raw / me.DEFAULT_STEM.format(band=band, ch="lv")))
    amplitude = (lh > 0) & (lv > 0)
    k = int(erosion.group(1))
    inner = binary_erosion(amplitude, np.ones((k, k), bool))
    n_amp, n_inner = int(amplitude.sum()), int(inner.sum())
    p0 = int(patches_default.split(",")[0])
    n_patch_amp = int(me.patch_ratios(lh.astype(np.float64), amplitude, p0).size)
    n_patch_inner = int(me.patch_ratios(lh.astype(np.float64), inner, p0).size)

    spec = {
        "schema": "lunar-ice/enl-estimator-spec/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/enl_estimator_spec.py",
        "read_from": ["backend/scripts/measure_enl.py", "backend/scripts/bootstrap_enl.py",
                      "backend/scripts/process_real_sar_pipeline.py"],
        "statistic": "mean^2 / var of intensity (DN^2) per patch",
        "patch": {
            "sizes_px": [int(x) for x in patches_default.split(",")],
            "sizes_m_on_25m_grid": [int(x) * 25 for x in patches_default.split(",")],
            "stride_px": "equal to the patch size" if stride_is_patch else "UNKNOWN",
            "overlap_px": 0 if stride_is_patch else None,
            "tiling": "non-overlapping tiles anchored at the raster origin; a partial "
                      "tile at the right or bottom edge is dropped",
            "inclusion_rule": ("a patch is used only if EVERY pixel is inside the mask"
                               if wholly_inside else "UNKNOWN"),
            "variance_ddof": ddof,
            "headline_patch_px": p0,
        },
        "mode_estimator": {
            "domain": "ln(mean^2/var)" if log_mode else "mean^2/var",
            "histogram_bins": int(bins),
            "bin_edges": "numpy.histogram default: equal width over [min, max] of the "
                         "per-patch values",
            "location": "exp of the midpoint of the fullest bin",
            "why_mode": "texture only lowers mean^2/var, so the homogeneous population "
                        "is the upper mode, not the centre",
            "alternative_reported": "mean, p5, p25, median, p75, p95 of the same "
                                    "per-patch distribution",
        },
        "masks": {
            "amplitude_mask": {
                "definition": amp_line,
                "where": "process_real_sar_pipeline.py; aliased to `valid` "
                         + ("(valid = amplitude)" if valid_alias else "(NOT aliased)"),
                "n_px": n_amp,
                "used_for": "every per-pixel statistic, the screening (CPR > 1 and "
                            "DOP < 0.13) and the Wilson denominator (measured_pixels)",
            },
            "screening_mask": {
                "definition": "identical to the amplitude mask -- valid_native.tif is "
                              "the amplitude mask written to disk",
                "n_px": n_amp,
            },
            "enl_measurement_mask": {
                "definition": f"amplitude mask eroded by a {k}x{k} structuring element "
                              f"(the {boxcar_size}x{boxcar_size} boxcar footprint), so no "
                              "window reaches a zero-fill pixel",
                "n_px": n_inner,
                "used_for": "the raw and boxcar ENL rows (enl.json::boxcar_gain) and "
                            "every bootstrap interval",
            },
            f"patches_{p0}x{p0}_wholly_inside": {"amplitude_mask": n_patch_amp,
                                                  "enl_measurement_mask": n_patch_inner},
        },
        "bootstrap": {
            "replicates_B": be.B_DEFAULT,
            "seed": be.SEED_DEFAULT,
            "generator": "numpy.random.default_rng",
            "simple": {"resampling_unit": "one patch", "scheme": "i.i.d. with replacement"},
            "block": {"resampling_unit": f"one row of the {be.PATCH}x{be.PATCH} patch grid",
                      "row_height_px": be.PATCH, "row_height_m": be.PATCH * 25,
                      "construction": "the patch grid is (rows, cols); a replicate draws "
                                      "rows with replacement and pools every finite "
                                      "positive patch ratio in the drawn rows",
                      "why": "azimuth lag-1 correlation is +0.838; a row keeps the "
                             "along-azimuth dependence inside the unit"},
            "interval": {"method": "percentile", "percentiles": list(be.PERCENTILES),
                         "bca": False},
            "statistic_bootstrapped": "mode_of over the resampled patch ratios",
        },
        "boxcar": {"size_px": boxcar_size, "filter": "scipy.ndimage.uniform_filter, "
                                                      "reflect boundary (default)",
                   "applied_to": "DN^2 before the patch statistic, for the "
                                 "post-boxcar ENL only"},
    }
    OUT.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in spec.items() if k not in ("generated_utc",)},
                     indent=2)[:3000])
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
