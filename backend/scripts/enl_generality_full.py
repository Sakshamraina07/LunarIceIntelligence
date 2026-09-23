"""
enl_generality_full.py -- the second acquisition, run through everything. (M14)

    python backend/scripts/enl_generality_full.py

WHY
---
Section IV-C reports that the oversampling relation does not predict the look
count of an independent acquisition, ch2_sar_ncxl_20200305t114902885 (L band,
39 azimuth looks, 90 m output): reference 13.42, measured ENL 2.28 / 2.21,
fraction attained 0.17 against 0.86 on the 2020-08-08 pass. It names three
candidate causes -- output spacing against input resolution, pulse bandwidth,
lag-one correlations -- "recorded untested". The reviewer asks for the
identical estimator suite on that product and for the causes to be tested.

WHAT IS RUN (the 2020-08-08 pass's numbers are read from its artifacts)
  1. Both labels, sri and sli: band, calibration constant, looks, resolution,
     output spacing, pulse bandwidth, PRF, processed bandwidth, incidence.
  2. SLC availability: the sli rasters on disk, their size asserted against
     offset + lines x samples x 8.
  3. The delivered product: amplitude-mask and patch counts (16, 32), the
     incidence raster's range over the mask, the patch-mode ENL on DN^2 at 16
     and 32 px, the row-block bootstrap (B = 2000), the 5x5 boxcar gain on the
     eroded mask, and the intensity lag correlations -- measure_enl.py's and
     bootstrap_enl.py's own functions.
  4. The benchmark at THIS product's lags: synthetic correlated speckle at
     N = 2, 3, 4, the mode estimator's bias and the block bootstrap's coverage.
  5. The SLC control at 39 looks: the azimuth spectrum's occupied bandwidth
     and oversampling, and the ENL of a 39-consecutive-line average and of a
     39-sub-band average, over nine windows, with the participation ratio of
     the measured spectrum. This localizes the loss: if the SLC's own 39-line
     average reaches the reference, the looks are lost after multilooking.
  6. The candidate causes, each with both passes' numbers and what they
     predict against what is measured. With two acquisitions none of them can
     be tested statistically; each is tested for direction and magnitude.

Nothing is ingested into data/pradan/: the product stays in data/generality/.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import tifffile
from scipy.ndimage import binary_erosion, uniform_filter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
GEN = BASE_DIR / "data/generality/20200305/data/calibrated/20200305"
STEM = "ch2_sar_ncxl_20200305t114902885"
MAIN = BASE_DIR / "data/pradan/raw/data/calibrated/20200808"
MAIN_STEM = "ch2_sar_ncxl_20200808t201154198"
OUT = BASE_DIR / "docs" / "enl_L_20200305_full.json"
SEED = 20260927
B_BOOT = 2000
BENCH_N = (2, 3, 4)
BENCH_REPS = 100
SLC_WINDOWS = 9
N_LOOKS = 39

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).resolve().parent / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ME = _load("measure_enl")
BE = _load("bootstrap_enl")


def label(path: Path) -> dict:
    x = path.read_text(encoding="utf-8", errors="replace")

    def f(tag, nth=0):
        v = re.findall(rf"<isda:{tag}[^>]*>([^<]+)</isda:{tag}>", x)
        return float(v[nth]) if len(v) > nth else None
    elems = [int(v) for v in re.findall(r"<elements>(\d+)</elements>", x)[:2]]
    off = re.findall(r'<offset unit="byte">(\d+)</offset>', x)
    return {"file": path.name,
            "band": "L" if "_ncxl_" in path.name else "S",
            "azimuth_looks": f("azimuth_looks"), "range_looks": f("range_looks"),
            "calibration_constant_db": f("calibration_constant"),
            "gain_imbalance": [f("gain_imbalance", 0), f("gain_imbalance", 1)],
            "input_resolution_along_m": f("input_resolution_along"),
            "input_resolution_across_m": f("input_resolution_across"),
            "output_line_spacing_m": f("output_line_spacing"),
            "output_pixel_spacing_m": f("output_pixel_spacing"),
            "pulse_bandwidth_hz": f("pulse_bandwidth"),
            "prf_hz": f("pulse_repetition_frequency"),
            "total_processed_azimuth_bandwidth_hz": f("total_processed_azimuth_bandwidth"),
            "azimuth_look_bandwidth_hz": f("azimuth_look_bandwidth"),
            "incidence_angle_deg": f("incidence_angle"),
            "swath_m": f("swath"),
            "lines": elems[0] if elems else None, "samples": elems[1] if len(elems) > 1 else None,
            "offset_bytes": int(off[0]) if off else None}


def slc_available(lab: dict, stem: str, root: Path) -> dict:
    out = {}
    for ch in ("lh", "lv"):
        p = root / f"{stem}_d_sli_xx_cp_{ch}_d18.tif"
        need = lab["offset_bytes"] + lab["lines"] * lab["samples"] * 8
        size = p.stat().st_size if p.is_file() else None
        out[ch] = {"file": p.name, "present": p.is_file(), "bytes": size,
                   "bytes_implied": need, "layout_confirmed": size == need}
    return out


def delivered_suite(rng) -> dict:
    lh = tifffile.imread(str(GEN / f"{STEM}_d_sri_xx_cp_lh_d18.tif")).astype(np.float64)
    lv = tifffile.imread(str(GEN / f"{STEM}_d_sri_xx_cp_lv_d18.tif")).astype(np.float64)
    inc = tifffile.imread(str(GEN / f"{STEM}_d_sri_in_cp_xx_d18.tif")).astype(np.float64)
    amp = (lh > 0) & (lv > 0)
    inner = binary_erosion(amp, np.ones((5, 5), dtype=bool))
    out = {"frame": list(lh.shape), "amplitude_pixels": int(amp.sum()),
           "eroded_pixels": int(inner.sum()),
           "incidence_raster_over_mask_deg": {
               "min": float(inc[amp].min()), "p50": float(np.median(inc[amp])),
               "max": float(inc[amp].max())}}
    for ch, dn in (("LH", lh), ("LV", lv)):
        i = dn * dn
        row = {}
        for p in (16, 32):
            r = ME.patch_ratios(i, amp, p)
            row[f"patch_{p}"] = {"n_patches": int(r.size), "mode": float(ME.mode_of(r)),
                                 "median": float(np.median(r)) if r.size else None}
        g = BE.ratio_grid(i, amp, 16)
        bb = BE.block_boot(g, B_BOOT, rng)
        row["block_bootstrap_16"] = {"B": B_BOOT, "range_2p5_97p5": BE.ci(bb),
                                     "unit": "one row of the 16 x 16 patch grid"}
        raw = ME.mode_of(ME.patch_ratios(i, inner, 16))
        box = ME.mode_of(ME.patch_ratios(uniform_filter(i, size=5), inner, 16))
        row["boxcar5"] = {"enl_raw_eroded": float(raw), "enl_boxcar5": float(box),
                          "gain": float(box / raw) if raw else None,
                          "n_patches_eroded": int(ME.patch_ratios(i, inner, 16).size)}
        lc = ME.lag_correlation(i, amp, 16, max_lag=3)
        row["lag_correlation"] = {"azimuth": lc.get("azimuth_lines"),
                                  "range": lc.get("range_samples")}
        out[ch] = row
    return out


def benchmark_at_lags(rng, lag_az: float, lag_rg: float) -> dict:
    EB = _load("enl_benchmark")
    rows = []
    for n in BENCH_N:
        est, cov = [], []
        for _ in range(BENCH_REPS):
            i = EB.speckle_field(rng, n, 1024, 512, np.sqrt(max(lag_az, 0)),
                                 np.sqrt(max(lag_rg, 0)), float("inf"))
            ones = np.ones_like(i, dtype=bool)
            est.append(ME.mode_of(ME.patch_ratios(i, ones, 16)))
            lo, hi = BE.ci(BE.block_boot(BE.ratio_grid(i, ones, 16), 200, rng))
            cov.append(lo <= n <= hi)
        est = np.array(est)
        c = float(np.mean(cov))
        rows.append({"true_N": n, "estimate_mean": float(est.mean()),
                     "relative_bias": float(est.mean() / n - 1),
                     "bias_se": float(est.std(ddof=1) / np.sqrt(est.size) / n),
                     "block_coverage_95": c, "coverage_se": float(np.sqrt(c * (1 - c) / est.size))})
        print(f"    benchmark N {n}: relative bias {rows[-1]['relative_bias']:+.3f}, "
              f"block coverage {100 * c:.1f} %", flush=True)
    return {"lags_used": {"azimuth": lag_az, "range": lag_rg}, "replicates": BENCH_REPS,
            "rows": rows}


def occupied(z: np.ndarray, prf: float) -> dict:
    """measure_oversampling's rule (PSD > 0.05 of max) at THIS product's PRF."""
    n = z.shape[0]
    psd = (np.abs(np.fft.fft(z - z.mean(axis=0), axis=0)) ** 2).mean(axis=1)
    psd /= psd.max()
    occ = int((psd > 0.05).sum())
    bw = occ / n * prf
    return {"occupied_bins": occ, "measured_bandwidth_hz": bw,
            "oversampling_factor": prf / bw if bw > 0 else float("nan")}


def slc_control(lab: dict) -> dict:
    CTRL = _load("slc_multilook_control")
    MS = _load("mechanism_spec")
    p = GEN / f"{STEM}_d_sli_xx_cp_lh_d18.tif"
    z_all = np.memmap(p, dtype=np.complex64, mode="r", offset=lab["offset_bytes"],
                      shape=(lab["lines"], lab["samples"]))
    lines = N_LOOKS * 200
    starts = np.linspace(0, lab["lines"] - lines - 1, SLC_WINDOWS).astype(int)
    rows = []
    for wi, s0 in enumerate(starts):
        z = np.array(z_all[s0:s0 + lines], dtype=np.complex64)
        col = (np.abs(z) > 0).mean(axis=0)
        keep = np.flatnonzero(col > 0.999)
        if keep.size < 32:
            continue
        z = z[:, keep.min():keep.max() + 1]
        if float((np.abs(z) > 0).mean()) < 0.98:
            continue
        o = occupied(z, lab["prf_hz"])
        sp = CTRL.mlook_spatial(z, N_LOOKS)
        sb = CTRL.mlook_subband(z, N_LOOKS, o["occupied_bins"])
        ones_sp, ones_sb = np.ones_like(sp, dtype=bool), np.ones_like(sb, dtype=bool)
        single = (np.abs(z[::N_LOOKS]) ** 2).astype(np.float64)
        rows.append({"window": wi, "start_line": int(s0), "range_bins": int(z.shape[1]),
                     **o,
                     "enl_spatial_39": float(ME.mode_of(ME.patch_ratios(sp, ones_sp, 16))),
                     "enl_subband_39": float(ME.mode_of(ME.patch_ratios(sb, ones_sb, 16))),
                     "enl_single_look": float(ME.mode_of(ME.patch_ratios(
                         single, np.ones_like(single, dtype=bool), 16))),
                     "n_patches": int(ME.patch_ratios(sp, ones_sp, 16).size),
                     "participation_ratio_measured_spectrum":
                         MS.pr_from_spectrum(z.astype(np.complex128), N_LOOKS)["participation_ratio"]})
        r = rows[-1]
        print(f"    SLC window {wi}: oversampling {r['oversampling_factor']:.3f}, ENL spatial "
              f"{r['enl_spatial_39']:.2f}, sub-band {r['enl_subband_39']:.2f}, single "
              f"{r['enl_single_look']:.2f}, PR {r['participation_ratio_measured_spectrum']:.2f}",
              flush=True)
    keys = ("oversampling_factor", "measured_bandwidth_hz", "enl_spatial_39",
            "enl_subband_39", "enl_single_look", "participation_ratio_measured_spectrum")
    return {"windows": rows, "lines_per_window": lines,
            "medians": {k: float(np.median([r[k] for r in rows])) for k in keys},
            "min": {k: float(min(r[k] for r in rows)) for k in keys},
            "max": {k: float(max(r[k] for r in rows)) for k in keys}}


def main() -> int:
    rng = np.random.default_rng(SEED)
    print("=" * 78)
    print("M14 — the 2020-03-05 acquisition, through the identical suite")
    print("=" * 78)
    lab_sri = label(GEN / f"{STEM}_d_sri_xx_cp_xx_d18.xml")
    lab_sli = label(GEN / f"{STEM}_d_sli_xx_cp_xx_d18.xml")
    main_sri = label(MAIN / f"{MAIN_STEM}_d_sri_xx_cp_xx_d18.xml")
    main_sli = label(MAIN / f"{MAIN_STEM}_d_sli_xx_cp_xx_d18.xml")
    avail = slc_available(lab_sli, STEM, GEN)
    print(f"  sli on disk: {avail['lh']['layout_confirmed']} / {avail['lv']['layout_confirmed']}")

    print("  delivered product ...", flush=True)
    dl = delivered_suite(rng)
    for ch in ("LH", "LV"):
        print(f"    {ch}: ENL16 {dl[ch]['patch_16']['mode']:.2f} ({dl[ch]['patch_16']['n_patches']} "
              f"patches), ENL32 {dl[ch]['patch_32']['mode']:.2f} ({dl[ch]['patch_32']['n_patches']}), "
              f"boot {dl[ch]['block_bootstrap_16']['range_2p5_97p5']}, boxcar gain "
              f"{dl[ch]['boxcar5']['gain']:.2f}, lag1 az {dl[ch]['lag_correlation']['azimuth'][0]:.3f} "
              f"rg {dl[ch]['lag_correlation']['range'][0]:.3f}", flush=True)
    la, lr = dl["LH"]["lag_correlation"]["azimuth"][0], dl["LH"]["lag_correlation"]["range"][0]
    print("  benchmark at this product's lags ...", flush=True)
    bench = benchmark_at_lags(rng, la, lr)
    print("  SLC control at 39 looks ...", flush=True)
    ctrl = slc_control(lab_sli)

    # the 2020-08-08 pass, read from its own artifacts
    enl = json.loads((BASE_DIR / "docs/enl.json").read_text(encoding="utf-8"))
    smc = json.loads((BASE_DIR / "docs/slc_multilook_control.json").read_text(encoding="utf-8"))
    gen = json.loads((BASE_DIR / "docs/enl_generality.json").read_text(encoding="utf-8"))
    m_lag = enl["lag_correlation"]["LH"]
    main_side = {"enl_raw_LH": enl["boxcar_gain"]["LH"]["enl_raw"],
                 "lag1_LH": {"azimuth": m_lag["azimuth_lines"][0], "range": m_lag["range_samples"][0]},
                 "slc_spatial_21_median": smc["medians"].get("enl_spatial_21"),
                 "oversampling": smc["medians"].get("oversampling_factor")}

    def cells(l):
        """Resolution cells per output pixel, on the GROUND. The label's
        input_resolution_across is the SLANT-range resolution (c / 2B: 19.986 m
        at 7.5 MHz, 74.948 m at 2 MHz), so it is projected to ground range
        with the label's incidence before it is compared with a ground
        spacing; the first version compared slant with ground."""
        import math
        ground_across = l["input_resolution_across_m"] / math.sin(math.radians(l["incidence_angle_deg"]))
        return {"along": l["output_line_spacing_m"] / l["input_resolution_along_m"],
                "across_ground": l["output_pixel_spacing_m"] / ground_across,
                "ground_range_resolution_m": ground_across,
                "product": (l["output_line_spacing_m"] / l["input_resolution_along_m"])
                           * (l["output_pixel_spacing_m"] / ground_across)}
    ref_0305 = 13.42
    dl_enl = dl["LH"]["patch_16"]["mode"]
    causes = {
        "output_spacing_vs_input_resolution": {
            "resolution_cells_per_output_pixel": {"20200808": cells(main_sri), "20200305": cells(lab_sri)},
            "predicts": ("an output pixel spanning k > 1 independent resolution cells "
                         "and averaging them multiplies the ENL by up to k; at k <= 1 the "
                         "grid OVERSAMPLES the resolution, adds no looks and correlates "
                         "neighbours -- more strongly the smaller k"),
            "boxcar5_gain_LH": {"20200808": enl["boxcar_gain"]["LH"]["gain"],
                                "20200305": dl["LH"]["boxcar5"]["gain"]},
            "measured": {"enl_ratio_delivered_over_slc_39": dl_enl / ctrl["medians"]["enl_spatial_39"],
                         "lag1_azimuth": {"20200808": main_side["lag1_LH"]["azimuth"], "20200305": la}},
        },
        "pulse_bandwidth": {
            "hz": {"20200808": main_sri["pulse_bandwidth_hz"], "20200305": lab_sri["pulse_bandwidth_hz"]},
            "slant_range_resolution_m": {k: 299792458.0 / (2 * v) for k, v in
                                         (("20200808", main_sri["pulse_bandwidth_hz"]),
                                          ("20200305", lab_sri["pulse_bandwidth_hz"]))},
            "predicts": ("with one range look, bandwidth sets the range resolution, not the "
                         "look count; it enters the ENL only through how many resolution "
                         "cells the 90 m output pixel spans (the cause above)"),
        },
        "lag_one_correlations": {
            "LH_intensity": {"20200808": main_side["lag1_LH"], "20200305": {"azimuth": la, "range": lr}},
            "benchmark_relative_bias_at_0305_lags": [r["relative_bias"] for r in bench["rows"]],
            "predicts": ("lag correlation biases the patch variance low and the ENL HIGH "
                         "(benchmark); weaker correlation removes that inflation but cannot "
                         "by itself remove looks"),
        },
        "where_the_looks_are_lost": {
            "reference_from_label": ref_0305,
            "slc_39_line_average_median": ctrl["medians"]["enl_spatial_39"],
            "slc_39_subband_median": ctrl["medians"]["enl_subband_39"],
            "slc_participation_ratio_measured_spectrum": ctrl["medians"]["participation_ratio_measured_spectrum"],
            "delivered_enl_LH": dl_enl,
            "fraction_attained": {"slc_39_line_average": ctrl["medians"]["enl_spatial_39"] / ref_0305,
                                  "delivered": dl_enl / ref_0305},
        },
        "limit": ("two acquisitions: every cause is examined for direction and magnitude "
                  "against the measured numbers; none is tested statistically"),
    }
    print(f"\n  delivered ENL {dl_enl:.2f}; SLC 39-line average {ctrl['medians']['enl_spatial_39']:.2f}; "
          f"reference {ref_0305}; ground resolution cells / output pixel 0808 "
          f"{cells(main_sri)['product']:.2f}, 0305 {cells(lab_sri)['product']:.2f}")

    OUT.write_text(json.dumps({
        "schema": "lunar-ice/enl-generality-full/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/enl_generality_full.py",
        "review_item": "M14",
        "product": f"{STEM}_d_sri_xx_cp",
        "stays_in": "data/generality/20200305 (not ingested into data/pradan)",
        "seed": SEED,
        "labels": {"20200305": {"sri": lab_sri, "sli": lab_sli},
                   "20200808": {"sri": main_sri, "sli": main_sli}},
        "slc_availability": {"20200305": avail},
        "delivered": dl,
        "benchmark_at_product_lags": bench,
        "slc_control_39_looks": ctrl,
        "registered_reference": {"value": ref_0305,
                                 "source": "docs/enl_generality.json (registered before the product was opened)",
                                 "recorded": gen.get("predictions", gen.get("rows", None)) is not None},
        "comparison_20200808": main_side,
        "candidate_causes": causes,
        "run_info": run_info()}, indent=2, default=float), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
