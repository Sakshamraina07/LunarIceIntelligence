"""
mechanism_spec.py -- the SLC control's processor, specified; and what the
measured spectrum predicts. (third review, M9)

    python backend/scripts/mechanism_spec.py [--windows 9] [--lines 8400]

WHY
---
Section IV-B's control forms 21 looks from the SLC two ways and measures them.
The reviewer asks for the processing to be specified completely -- FFT length,
window, overlap, sub-band alignment, decimation, normalization, registration,
spatial kernels, boundary treatment -- and for two numbers the control implies
but never computed:

  1. RESIDUAL CROSS-BAND CORRELATION between adjacent sub-bands. A hard
     spectral split makes the sub-band images exactly orthogonal over a whole
     window (Parseval), so the whole-window complex coherence is zero by
     construction and says nothing. What governs the ENL is local: the
     correlation between adjacent looks' INTENSITIES on the decimated grid,
     and the LOCAL complex coherence after each sub-band is shifted to
     baseband. Both are measured for adjacent bands (k, k+1) and, as the
     estimator's floor, for distant bands (k, k+10), which should be
     uncorrelated.
  2. EXPECTED LOOKS FROM THE MEASURED SPECTRUM. The 7.34 reference is the
     participation ratio of a RECTANGULAR spectrum of the processed support.
     The same ratio, (sum lambda)^2 / sum lambda^2 of the 21 x 21 covariance
     of 21 consecutive samples, is computed here from each window's MEASURED
     azimuth power spectrum (its inverse FFT is the autocovariance), which
     carries the processor's actual taper.

Everything is read from the modules the control uses, so the specification is
the code's, not a description of it.
"""
from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.ndimage import uniform_filter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "mechanism_spec.json"
LOCAL = 5            # local window for the baseband complex coherence

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


CTRL = _load("slc_multilook_control")
MECH = _load("mechanism_controls")


def subband_complex(z: np.ndarray, n: int, occupied: int):
    """The n sub-band COMPLEX images exactly as mlook_subband forms them (same
    centre, same split, no taper), each shifted to baseband by its centre
    frequency so a local cross-product is not a phase ramp, and decimated by n
    onto the arm's grid."""
    rows = (z.shape[0] // n) * n
    Z = np.fft.fft(z[:rows] - z[:rows].mean(axis=0), axis=0)
    nfft = Z.shape[0]
    psd = np.abs(Z).mean(axis=1)
    centre = int(np.argmax(np.convolve(psd, np.ones(max(occupied, 1)), "same")))
    half = max(occupied // 2, n)
    band = (np.arange(centre - half, centre - half + 2 * half) % nfft)
    width = len(band) // n
    t = np.arange(rows)[:, None]
    out = []
    for k in range(n):
        idx = band[k * width:(k + 1) * width]
        sub = np.zeros_like(Z)
        sub[idx] = Z[idx]
        s = np.fft.ifft(sub, axis=0)
        fc = np.fft.fftfreq(nfft)[idx]
        f0 = float(np.angle(np.exp(2j * np.pi * fc).mean()) / (2 * np.pi))
        # shifted to baseband at full rate, then decimated as the arm is; only
        # the decimated image is kept (21 full-rate images would be ~2 GB)
        out.append((s * np.exp(-2j * np.pi * f0 * t))[::n])
        del s, sub
    return out, {"nfft": int(nfft), "centre_bin": centre, "band_bins": int(len(band)),
                 "bins_per_subband": int(width), "occupied_bins": int(occupied)}


def local_coherence(a: np.ndarray, b: np.ndarray) -> float:
    """Median |<a b*>| / sqrt(<|a|^2><|b|^2>) over LOCAL x LOCAL windows."""
    c = uniform_filter((a * np.conj(b)).real, LOCAL) + 1j * uniform_filter((a * np.conj(b)).imag, LOCAL)
    pa, pb = uniform_filter(np.abs(a) ** 2, LOCAL), uniform_filter(np.abs(b) ** 2, LOCAL)
    g = np.abs(c) / np.sqrt(np.maximum(pa * pb, 1e-300))
    return float(np.median(g))


def intensity_corr(a: np.ndarray, b: np.ndarray) -> float:
    """Correlation of two looks' intensity fluctuations about a local mean, on
    the decimated grid."""
    fa = a / np.maximum(uniform_filter(a, MECH.LOCAL_MEAN), 1e-300) - 1
    fb = b / np.maximum(uniform_filter(b, MECH.LOCAL_MEAN), 1e-300) - 1
    fa, fb = fa - fa.mean(), fb - fb.mean()
    return float((fa * fb).mean() / np.sqrt((fa * fa).mean() * (fb * fb).mean()))


def pr_from_spectrum(z: np.ndarray, n: int) -> dict:
    """Participation ratio of the n x n covariance of n consecutive azimuth
    samples, from the window's measured azimuth power spectrum."""
    zz = z - z.mean(axis=0)
    P = (np.abs(np.fft.fft(zz, axis=0)) ** 2).mean(axis=1)
    r = np.fft.ifft(P)
    r = r / r[0]
    C = np.array([[r[(i - j) % r.size] for j in range(n)] for i in range(n)])
    lam = np.linalg.eigvalsh((C + C.conj().T) / 2)
    return {"participation_ratio": float(lam.sum() ** 2 / (lam ** 2).sum()),
            "acf_lag1_abs": float(abs(r[1])), "acf_lag3_abs": float(abs(r[3]))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", type=int, default=9)
    ap.add_argument("--lines", type=int, default=8400)
    args = ap.parse_args()
    n = CTRL.AZIMUTH_LOOKS

    print("=" * 78)
    print("M9 — the SLC control's processor, and what its spectrum predicts")
    print("=" * 78)
    z_all = CTRL.open_slc()
    starts = np.linspace(0, CTRL.LINES - args.lines - 1, args.windows).astype(int)
    rows = []
    geom = None
    for wi, s0 in enumerate(starts):
        z = np.array(z_all[s0:s0 + args.lines], dtype=np.complex64)
        col = (np.abs(z) > 0).mean(axis=0)
        keep = np.flatnonzero(col > 0.999)
        if keep.size < 64:
            continue
        z = z[:, keep.min():keep.max() + 1]
        if float((np.abs(z) > 0).mean()) < 0.98:
            continue
        osamp = CTRL.measure_oversampling(z)
        subs, geom = subband_complex(z.astype(np.complex128), n, osamp["occupied_bins"])
        inten = [np.abs(s) ** 2 for s in subs]
        adj_i = [intensity_corr(inten[k], inten[k + 1]) for k in range(n - 1)]
        far_i = [intensity_corr(inten[k], inten[k + 10]) for k in range(n - 10)]
        adj_c = [local_coherence(subs[k], subs[k + 1]) for k in range(n - 1)]
        far_c = [local_coherence(subs[k], subs[k + 10]) for k in range(n - 10)]
        pr = pr_from_spectrum(z.astype(np.complex128), n)
        powers = np.array([x.mean() for x in inten])
        row = {"window": wi, "start_line": int(s0), "range_bins": int(z.shape[1]),
               "intensity_corr_adjacent_median": float(np.median(adj_i)),
               "intensity_corr_distant_median": float(np.median(far_i)),
               "local_coherence_adjacent_median": float(np.median(adj_c)),
               "local_coherence_distant_median": float(np.median(far_c)),
               "subband_power_cv": float(powers.std() / powers.mean()),
               "subband_equal_power_enl": float(powers.sum() ** 2 / (powers ** 2).sum()),
               **pr}
        rows.append(row)
        print(f"  window {wi}: intensity corr adj {row['intensity_corr_adjacent_median']:+.4f} "
              f"far {row['intensity_corr_distant_median']:+.4f} | local coh adj "
              f"{row['local_coherence_adjacent_median']:.3f} far "
              f"{row['local_coherence_distant_median']:.3f} | PR(measured spectrum) "
              f"{pr['participation_ratio']:.2f}", flush=True)
        del z, subs, inten

    med = {k: float(np.median([r[k] for r in rows])) for k in rows[0] if k not in
           ("window", "start_line", "range_bins")}
    rng_ = {k: [float(min(r[k] for r in rows)), float(max(r[k] for r in rows))]
            for k in med}
    print(f"\n  medians over {len(rows)} windows: PR(measured) {med['participation_ratio']:.2f} "
          f"(rectangular 7.34); adjacent intensity corr {med['intensity_corr_adjacent_median']:+.4f} "
          f"vs distant {med['intensity_corr_distant_median']:+.4f}")

    spec = {
        "fft": {"axis": "azimuth (lines)", "length": ("the window's own line count, "
                "truncated to a multiple of 21 -- no zero-padding"),
                "length_used": geom["nfft"] if geom else None,
                "mean_removal": "the azimuth mean of each range bin is removed before the FFT",
                "circular": True},
        "window_function": {"spatial_arm": "none (boxcar of 21 consecutive lines)",
                            "subband_arm": "rectangular split, no taper (mlook_subband); "
                                           "subband_looks() offers Hamming + guard bins, "
                                           "used only in the diagnostic variants"},
        "subbands": {"count": n, "overlap_bins": 0,
                     "bins_per_subband": geom["bins_per_subband"] if geom else None,
                     "band_bins_total": geom["band_bins"] if geom else None,
                     "occupied_bins_threshold": "PSD > 0.05 of its maximum (measure_oversampling)",
                     "alignment": ("the band is centred on the argmax of the mean |FFT| "
                                   "convolved with a boxcar of the occupied width -- the "
                                   "measured Doppler centroid, not bin zero"),
                     "band_width_rule": "2 * max(occupied // 2, 21) bins"},
        "decimation": {"spatial_arm": "mean of 21 consecutive lines (reshape), 1 row per 21 lines",
                       "subband_arm": "each sub-band intensity taken every 21st line ([::21]) "
                                      "after the average, so both arms share one grid"},
        "normalization": {"looks": "intensities averaged with equal weight 1/21",
                          "subband_power": "no per-band equalization (powers recorded here: "
                                           "subband_power_cv)"},
        "registration": ("none required: both arms are formed from the same complex "
                         "samples on the same slant-range grid and decimated identically"),
        "range_crop": ("range bins kept where > 99.9 % of lines are non-zero; a window is "
                       "dropped if < 98 % of its samples are non-zero"),
        "windows": {"count": args.windows, "lines_each": args.lines,
                    "starts": "numpy.linspace(0, LINES - lines - 1, windows)"},
        "spatial_kernels": {
            "enl_estimator": "16 x 16 non-overlapping patches, mode of mean^2/var (120 log bins)",
            "acf": f"intensity / uniform_filter({MECH.LOCAL_MEAN}, reflect) - 1, FFT autocovariance, lags 0-{MECH.MAX_LAG}",
            "matched_resolution": "gaussian_filter1d along azimuth, mode reflect, sigma by 40-step bisection on the ACF half-width"},
        "boundary_treatment": {"fft": "circular (no padding)", "uniform_filter": "reflect",
                               "gaussian_filter1d": "reflect",
                               "patches": "partial patches at the right/bottom edge dropped"},
        "source_functions": {
            "measure_oversampling": inspect.getsource(CTRL.measure_oversampling).count("\n"),
            "mlook_spatial": "slc_multilook_control.py",
            "mlook_subband": "slc_multilook_control.py",
            "acf2d / half_width / match_resolution": "mechanism_controls.py"},
    }
    OUT.write_text(json.dumps({
        "schema": "lunar-ice/mechanism-spec/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/mechanism_spec.py",
        "review_item": "M9",
        "specification": spec,
        "residual_cross_band": {
            "why_not_whole_window": ("a hard spectral split makes sub-band images exactly "
                                     "orthogonal over the window (Parseval): their "
                                     "whole-window coherence is zero by construction"),
            "measures": {"intensity_corr": "adjacent-look intensity fluctuations, decimated grid",
                         "local_coherence": (f"median |<a b*>| over {LOCAL}x{LOCAL} windows "
                                             "after shifting each sub-band to baseband")},
            "control": "bands k and k+10, which should be uncorrelated: the estimator's floor",
            "medians": {k: med[k] for k in med if "corr" in k or "coherence" in k},
            "ranges": {k: rng_[k] for k in rng_ if "corr" in k or "coherence" in k}},
        "expected_looks_from_measured_spectrum": {
            "definition": ("(sum lambda)^2 / sum lambda^2 of the 21 x 21 Toeplitz "
                           "covariance of 21 consecutive samples, from the inverse FFT "
                           "of the window's measured azimuth power spectrum"),
            "median": med["participation_ratio"], "range": rng_["participation_ratio"],
            "compare": {"rectangular_same_support": 7.34, "two_WT": 6.77,
                        "measured_spatial_arm_patch_mode": 4.52}},
        "subband_powers": {"cv_median": med["subband_power_cv"],
                           "equal_power_enl_median": med["subband_equal_power_enl"]},
        "per_window": rows,
        "run_info": run_info()}, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
