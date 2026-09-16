"""
mechanism_controls.py -- P3. Do the spatial and sub-band arms of the SLC control
measure the same thing at the same resolution?

    python backend/scripts/mechanism_controls.py [--windows 9] [--lines 8400]

THE REVIEWER'S POINT (4.9)
--------------------------
slc_multilook_control.py forms 21 looks two ways from the same complex samples
and finds ENL 4.52 (spatial average of 21 consecutive lines) against 9.95
(21 azimuth sub-bands). "The two methods do not deliver the same number of
looks" is the paper's reading. The alternative reading is that the two arms
have DIFFERENT AZIMUTH RESOLUTION on the same decimated grid -- each sub-band
look is band-limited to 1/21 of the processed spectrum, so its impulse response
is ~21 x the full-band one -- and a patch of correlated cells returns a smaller
sample variance and therefore a larger mean^2/var. If that were the whole
story, smoothing the finer arm to the coarser arm's resolution would close the
gap. So:

  1. the autocorrelation width at half maximum of each arm's intensity, along
     azimuth, per window; if they differ, the finer arm is smoothed along
     azimuth (Gaussian, sigma found by bisection) until its width matches the
     coarser arm's in that window, and its ENL is re-measured;
  2. the 2-D normalised autocovariance of intensity, lags 0-10 on both axes,
     per arm, median over windows;
  3. the PAIRED difference in ENL between arms over the windows, with its
     standard error from the nine paired differences -- not pooled.

Everything is imported from slc_multilook_control.py and measure_enl.py: the
same windows, the same crop, the same look-forming code, the same estimator.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter1d, uniform_filter

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "mechanism_controls.json"
MAX_LAG = 10
PATCH = 16
LOCAL_MEAN = 33

_T0 = time.time()
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def beat(msg: str) -> None:
    print(f"  [{time.strftime('%H:%M:%S')}  +{time.time() - _T0:7.1f}s]  {msg}", flush=True)


def hr(t: str) -> None:
    print("\n" + "=" * 78 + "\n" + t + "\n" + "=" * 78, flush=True)


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        "_" + name, Path(__file__).with_name(name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CTRL = _load("slc_multilook_control")
patch_ratios, mode_of = CTRL._enl_tools()


def enl(a: np.ndarray) -> float:
    return float(mode_of(patch_ratios(a, np.ones_like(a, dtype=bool), PATCH)))


def acf2d(i: np.ndarray, max_lag: int = MAX_LAG) -> np.ndarray:
    """Normalised autocovariance of the intensity FLUCTUATION i/<i>_local - 1,
    lags 0..max_lag on both axes. The local mean (uniform, LOCAL_MEAN x
    LOCAL_MEAN) removes terrain so the ACF is of the speckle-plus-residual, the
    same intent as measure_enl's patch-mean removal but without a hard 16-cell
    edge inside the lag range."""
    f = i / np.maximum(uniform_filter(i, LOCAL_MEAN, mode="reflect"), 1e-300) - 1.0
    f -= f.mean()
    F = np.fft.fft2(f)
    r = np.fft.ifft2(np.abs(F) ** 2).real
    r /= r[0, 0]
    return r[:max_lag + 1, :max_lag + 1]


def half_width(prof: np.ndarray) -> float:
    """Lag at which the normalised ACF first crosses 0.5, linearly interpolated;
    in units of the field's own grid. NaN if it never does within the lags."""
    for k in range(1, prof.size):
        if prof[k] < 0.5:
            a, b = prof[k - 1], prof[k]
            return float((k - 1) + (a - 0.5) / (a - b))
    return float("nan")


def match_resolution(fine: np.ndarray, target_width: float) -> tuple:
    """Gaussian-smooth `fine` along azimuth until its half-max width equals
    target_width. Bisection on sigma. Returns (smoothed, sigma, achieved)."""
    def width_at(s):
        return half_width(acf2d(gaussian_filter1d(fine, s, axis=0, mode="reflect"))[:, 0])
    lo, hi = 0.0, 8.0
    if width_at(hi) < target_width:
        return None, float("nan"), float("nan")
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if width_at(mid) < target_width:
            lo = mid
        else:
            hi = mid
    s = 0.5 * (lo + hi)
    return gaussian_filter1d(fine, s, axis=0, mode="reflect"), s, width_at(s)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", type=int, default=9)
    ap.add_argument("--lines", type=int, default=8400)
    args = ap.parse_args()

    hr("P3 — MECHANISM CONTROLS on the two arms of the SLC control")
    z_all = CTRL.open_slc()
    starts = np.linspace(0, CTRL.LINES - args.lines - 1, args.windows).astype(int)
    rows = []
    acf_sp, acf_sb = [], []
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
        sp = CTRL.mlook_spatial(z, CTRL.AZIMUTH_LOOKS)
        sb = CTRL.mlook_subband(z, CTRL.AZIMUTH_LOOKS, osamp["occupied_bins"])
        a_sp, a_sb = acf2d(sp), acf2d(sb)
        acf_sp.append(a_sp); acf_sb.append(a_sb)
        w_sp, w_sb = half_width(a_sp[:, 0]), half_width(a_sb[:, 0])
        e_sp, e_sb = enl(sp), enl(sb)
        row = {"window": wi, "start_line": int(s0), "shape": list(sp.shape),
               "occupied_bins": osamp["occupied_bins"],
               "width_az_spatial": w_sp, "width_az_subband": w_sb,
               "width_rg_spatial": half_width(a_sp[0, :]),
               "width_rg_subband": half_width(a_sb[0, :]),
               "lag1_az_spatial": float(a_sp[1, 0]), "lag1_az_subband": float(a_sb[1, 0]),
               "enl_spatial": e_sp, "enl_subband": e_sb, "diff_sb_minus_sp": e_sb - e_sp}
        # resample the finer arm to the coarser arm's azimuth width
        if np.isfinite(w_sp) and np.isfinite(w_sb) and abs(w_sp - w_sb) > 1e-3:
            fine, coarse_w, which = (sp, w_sb, "spatial") if w_sp < w_sb else (sb, w_sp, "subband")
            sm, sigma, got = match_resolution(fine, coarse_w)
            if sm is not None:
                e_m = enl(sm)
                row.update({"finer_arm": which, "smoothing_sigma_rows": sigma,
                            "width_after_smoothing": got, "enl_finer_at_matched_width": e_m,
                            "diff_at_matched_width":
                                (e_sb - e_m) if which == "spatial" else (e_m - e_sp)})
            else:
                row.update({"finer_arm": which, "smoothing_sigma_rows": None,
                            "note": "sigma up to 8 rows could not reach the coarser width"})
        rows.append(row)
        beat(f"window {wi}: width az sp {w_sp:5.2f} sb {w_sb:5.2f} rows | ENL sp {e_sp:5.2f} "
             f"sb {e_sb:5.2f} | matched: {row.get('enl_finer_at_matched_width', float('nan')):5.2f} "
             f"(sigma {row.get('smoothing_sigma_rows', float('nan')):.2f})")

    n = len(rows)
    d = np.array([r["diff_sb_minus_sp"] for r in rows])
    paired = {"n_windows": n, "mean": float(d.mean()), "sd": float(d.std(ddof=1)),
              "se": float(d.std(ddof=1) / np.sqrt(n)),
              "t": float(d.mean() / (d.std(ddof=1) / np.sqrt(n))),
              "min": float(d.min()), "max": float(d.max())}
    dm = np.array([r["diff_at_matched_width"] for r in rows if "diff_at_matched_width" in r])
    paired_matched = ({"n_windows": int(dm.size), "mean": float(dm.mean()),
                       "sd": float(dm.std(ddof=1)), "se": float(dm.std(ddof=1) / np.sqrt(dm.size)),
                       "t": float(dm.mean() / (dm.std(ddof=1) / np.sqrt(dm.size)))}
                      if dm.size >= 2 else {"n_windows": int(dm.size)})
    med = lambda k: float(np.median([r[k] for r in rows if np.isfinite(r.get(k, np.nan))]))

    hr("RESULT")
    print(f"  windows: {n}")
    print(f"  azimuth half-max width (output rows): spatial {med('width_az_spatial'):.2f}  "
          f"sub-band {med('width_az_subband'):.2f}   (medians)")
    print(f"  range   half-max width (bins):        spatial {med('width_rg_spatial'):.2f}  "
          f"sub-band {med('width_rg_subband'):.2f}")
    print(f"  ENL medians: spatial {med('enl_spatial'):.2f}  sub-band {med('enl_subband'):.2f}")
    print(f"  PAIRED difference sub-band - spatial: {paired['mean']:+.3f} +/- {paired['se']:.3f} "
          f"(sd {paired['sd']:.3f}, t = {paired['t']:.1f}, n = {n})")
    if "mean" in paired_matched:
        print(f"  at MATCHED azimuth width (finer arm smoothed): {paired_matched['mean']:+.3f} "
              f"+/- {paired_matched['se']:.3f} (n = {paired_matched['n_windows']}); "
              f"finer arm ENL median {med('enl_finer_at_matched_width'):.2f}")
    A_sp, A_sb = np.median(np.stack(acf_sp), axis=0), np.median(np.stack(acf_sb), axis=0)
    print("\n  2-D ACF, median over windows, azimuth lag down / range lag across (0..10):")
    for name, A in (("spatial", A_sp), ("sub-band", A_sb)):
        print(f"  {name}")
        for k in range(0, MAX_LAG + 1, 2):
            print("    " + " ".join(f"{A[k, j]:6.3f}" for j in range(0, MAX_LAG + 1, 2)))

    OUT.write_text(json.dumps({
        "schema": "lunar-ice/mechanism-controls/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/mechanism_controls.py",
        "windows": args.windows, "lines_per_window": args.lines, "patch": PATCH,
        "acf_normalisation": f"i / uniform_filter(i, {LOCAL_MEAN}) - 1, mean removed, "
                             "circular FFT autocovariance normalised at lag 0",
        "half_width_definition": "first lag at which the azimuth (range) profile of the "
                                 "normalised ACF crosses 0.5, linearly interpolated; units "
                                 "are the decimated grid (1 row = 21 SLC lines; 1 bin = 1 "
                                 "slant-range sample)",
        "resolution_matching": "the arm with the smaller azimuth width is Gaussian-smoothed "
                               "along azimuth; sigma found by bisection so its half-max width "
                               "equals the other arm's in the same window; ENL re-measured "
                               "with the same estimator",
        "medians": {k: med(k) for k in ("width_az_spatial", "width_az_subband",
                                         "width_rg_spatial", "width_rg_subband",
                                         "enl_spatial", "enl_subband",
                                         "enl_finer_at_matched_width", "smoothing_sigma_rows")},
        "paired_difference_subband_minus_spatial": paired,
        "paired_difference_at_matched_width": paired_matched,
        "acf2d_median_spatial": A_sp.tolist(), "acf2d_median_subband": A_sb.tolist(),
        "per_window": [{**r, "acf2d_spatial": a.tolist(), "acf2d_subband": b.tolist()}
                       for r, a, b in zip(rows, acf_sp, acf_sb)],
        "reference": "docs/slc_multilook_control.json medians: spatial 4.52, sub-band 9.95",
    }, indent=2, default=float), encoding="utf-8")
    beat(f"wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
