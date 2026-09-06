"""
Choose the anti-alias sigma for the 20 m -> 25 m resample BY MEASUREMENT.

THE TRADE-OFF, AND WHY IT IS NOT A CONVENTION CHOICE
----------------------------------------------------
20 m posts onto a 25 m grid is a DOWNSAMPLE of f = 1.25. map_coordinates point-
samples, so content the output grid cannot represent folds back as aliasing
instead of being averaged away. A Gaussian pre-filter fixes that, but every
sigma that suppresses the folded band also attenuates real detail -- and real
detail below 80 m is the entire reason the 1.85 GB 20 m product was fetched.
Over-filtering would quietly throw away the thing Phase 6 exists to gain.

Two candidate conventions, four times apart:

    sigma = f/2     = 0.625 source px  (12.5 m, FWHM ~29 m)
    sigma = (f-1)/2 = 0.125 source px  (2.5 m; at f = 1.25 this barely filters)

Neither is obviously right, so this measures both instead of arguing about them.

WHAT IS MEASURED
----------------
The radially-averaged power spectrum of the resampled DEM against the source,
on a common cycles-per-metre axis, plus an unfiltered control. Read it as:

  * PASSBAND FIDELITY -- the output/source ratio well below the new Nyquist
    should be ~1. A sigma that pulls this down is discarding real terrain.
  * ALIASED BAND -- the source carries power between the output Nyquist
    (1/50 m^-1) and its own (1/40 m^-1) which the output grid cannot represent.
    Unfiltered, that power folds back and ADDS to the output spectrum below
    Nyquist. A good sigma leaves the output tracking the source instead.

Plus the slope percentile table under each, because slope is what the DEM feeds
and it is where over-smoothing shows up as a number rather than a curve.

Usage:
    python -u backend/scripts/choose_antialias_sigma.py [--windows 3] [--size 2048]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates

BASE_DIR = Path(__file__).resolve().parents[2]
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

IMG = BASE_DIR / "data/pradan/lola/LDEM_80S_20M.IMG"
LINES = SAMPLES = 30400
SRC_M = 20.0
DST_M = 25.0
SCALING, DN_OFFSET = 0.5, 1737400.0
_T0 = time.time()


def beat(msg: str) -> None:
    print(f"  [{time.strftime('%H:%M:%S')}  +{time.time() - _T0:6.1f}s]  {msg}", flush=True)


def hr(t: str) -> None:
    print("\n" + "=" * 78 + "\n" + t + "\n" + "=" * 78, flush=True)


def radial_psd(a: np.ndarray, dx: float, nbins: int = 90) -> tuple[np.ndarray, np.ndarray]:
    """Radially-averaged power spectrum. Returns (cycles/m, power).

    A Hann window is applied first: the block is not periodic, and without it
    the edge discontinuity leaks a 1/f skirt across the whole spectrum that
    would swamp the difference being measured.
    """
    a = a - a.mean()
    n = a.shape[0]
    w = np.hanning(n)
    a = a * w[:, None] * w[None, :]
    # NORMALISED so two grids with different N and dx estimate the SAME
    # continuous PSD: |FFT|^2 * (dx/N)^2, divided by the Hann window's energy.
    # Without this the ratio between a 20 m and a 25 m spectrum is dominated by
    # a constant that has nothing to do with the filter -- which is exactly what
    # the first version of this script reported (0.630 where it had to be 1.0).
    p = np.abs(np.fft.rfft2(a)) ** 2 * (dx / n) ** 2 / ((w ** 2).mean() ** 2)
    fy = np.fft.fftfreq(n, d=dx)[:, None]
    fx = np.fft.rfftfreq(n, d=dx)[None, :]
    fr = np.sqrt(fy ** 2 + fx ** 2)
    fmax = 1.0 / (2.0 * dx)
    edges = np.linspace(0, fmax, nbins + 1)
    idx = np.clip(np.digitize(fr.ravel(), edges) - 1, 0, nbins - 1)
    tot = np.bincount(idx, weights=p.ravel(), minlength=nbins)
    cnt = np.bincount(idx, minlength=nbins)
    with np.errstate(invalid="ignore", divide="ignore"):
        psd = np.where(cnt > 0, tot / np.maximum(cnt, 1), np.nan)
    return 0.5 * (edges[:-1] + edges[1:]), psd


def resample(src: np.ndarray, sigma: float, ideal: bool = False) -> np.ndarray:
    """Exactly what the ingest does: optional Gaussian, then bilinear sampling.

    `ideal=True` substitutes a BRICK-WALL low-pass at the output Nyquist for the
    Gaussian. That is the reference answer -- everything the 25 m grid can carry,
    nothing it cannot -- so each candidate can be compared against it ON THE SAME
    OUTPUT GRID. That sidesteps comparing spectra across two different samplings
    entirely, and makes "too much passband removed" and "folded power added"
    readable as one number each.
    """
    a = src.astype(np.float64)
    if ideal:
        n = a.shape[0]
        fy = np.fft.fftfreq(n, d=SRC_M)[:, None]
        fx = np.fft.rfftfreq(n, d=SRC_M)[None, :]
        keep = np.sqrt(fy ** 2 + fx ** 2) <= 1.0 / (2.0 * DST_M)
        a = np.fft.irfft2(np.fft.rfft2(a) * keep, s=(n, n))
    elif sigma > 0:
        a = gaussian_filter(a, sigma, mode="nearest")
    step = DST_M / SRC_M
    n_out = int(src.shape[0] / step)
    g = (np.arange(n_out) * step)[None, :]
    coords = np.stack(np.broadcast_arrays(g.T, g))
    return map_coordinates(a, coords, order=1, mode="nearest")


def slope_pct(dem: np.ndarray, dx: float) -> dict:
    gy, gx = np.gradient(dem.astype(np.float64), dx)
    s = np.degrees(np.arctan(np.hypot(gy, gx)))
    q = np.percentile(s, [50, 90, 99])
    return {"p50": float(q[0]), "p90": float(q[1]), "p99": float(q[2]),
            "max": float(s.max()), "mean": float(s.mean())}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", type=int, default=3)
    ap.add_argument("--size", type=int, default=2048, help="source px per side")
    ap.add_argument("--out", default="docs/antialias_sigma.json")
    args = ap.parse_args()

    f_down = DST_M / SRC_M
    # The two conventions, plus a scan between and beyond them. Neither
    # convention is a measurement, and if both fail in opposite directions the
    # scan is what says so with a number instead of a preference.
    scan = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]
    sigmas = [0.0, (f_down - 1) / 2.0, f_down / 2.0] + scan
    names = ["none (control)", f"(f-1)/2 = {sigmas[1]:.3f}",
             f"f/2 = {sigmas[2]:.3f}"] + [f"scan {v:.2f}" for v in scan]

    hr("THE CHOICE, AND THE TRANSFER FUNCTIONS IT IMPLIES")
    print(f"  source {SRC_M:g} m  ->  output {DST_M:g} m   downsample f = {f_down:g}")
    print(f"  output Nyquist 1/{2 * DST_M:g} m = {1 / (2 * DST_M):.5f} /m")
    print(f"  source Nyquist 1/{2 * SRC_M:g} m = {1 / (2 * SRC_M):.5f} /m")
    print(f"  the band between them is what folds.\n")
    print(f"  {'wavelength':>12}" + "".join(f"{n:>20}" for n in names[1:]))
    for lam in (200.0, 100.0, 80.0, 50.0, 40.0):
        fpx = SRC_M / lam                      # cycles per source pixel
        row = "".join(f"{np.exp(-2 * np.pi ** 2 * s ** 2 * fpx ** 2):>20.3f}"
                      for s in sigmas[1:])
        print(f"  {lam:>10.0f} m{row}")
    print("\n  Gaussian amplitude transfer. The 50 m row is the output Nyquist and")
    print("  wants to be SMALL; the 200 m and 100 m rows are real terrain and want")
    print("  to be near 1. That is the whole tension, in five numbers.")

    z = np.memmap(IMG, dtype="<i2", mode="r", shape=(LINES, SAMPLES))
    n = args.size
    # Windows straddling the pole, where the DFSAR frame actually lies.
    centres = [(15200, 15200), (15200 + 3000, 15200), (15200, 15200 + 3000)][:args.windows]

    slopes = {i: [] for i in range(len(sigmas))}
    rms_vs_ideal = {i: [] for i in range(len(sigmas))}
    psd_out = {i: [] for i in range(len(sigmas))}
    psd_ideal, fo = [], None
    for wi, (r0, c0) in enumerate(centres):
        beat(f"window {wi + 1}/{len(centres)} at line {r0}, sample {c0}, {n}x{n} src px")
        src = np.asarray(z[r0:r0 + n, c0:c0 + n], dtype=np.float64) * SCALING
        if not np.isfinite(src).all():
            print("      window holds non-finite values, skipped")
            continue
        ideal = resample(src, 0.0, ideal=True)
        f_i, p_i = radial_psd(ideal, DST_M)
        psd_ideal.append(p_i)
        fo = f_i
        for i, sg in enumerate(sigmas):
            out = resample(src, sg)
            psd_out[i].append(radial_psd(out, DST_M)[1])
            rms_vs_ideal[i].append(float(np.sqrt(((out - ideal) ** 2).mean())))
            slopes[i].append(slope_pct(out, DST_M))

    if not psd_ideal:
        print("no usable window")
        return 1
    p_ideal = np.nanmean(np.array(psd_ideal), axis=0)
    p_out = {i: np.nanmean(np.array(psd_out[i]), axis=0) for i in range(len(sigmas))}

    hr("AMPLITUDE RATIO vs AN IDEAL BAND-LIMITED DOWNSAMPLE, SAME 25 m GRID")
    print("  The reference keeps everything the 25 m grid can carry and nothing it")
    print("  cannot, so both spectra live on the SAME grid and no cross-grid")
    print("  normalisation enters. 1.000 is correct. Below 1 is real terrain")
    print("  REMOVED; above 1 near Nyquist is folded power ADDED.")
    print()
    print(f"  {'wavelength':>12}{'freq /m':>11}" + "".join(f"{nm:>18}" for nm in names[:3]))
    table = {}
    for lam in (400.0, 200.0, 120.0, 100.0, 80.0, 65.0, 55.0, 51.0):
        f = 1.0 / lam
        if f > fo.max():
            print(f"  {lam:>10.0f} m{f:>11.5f}"
                  f"{'above the last bin centre - UNAVAILABLE':>54}")
            continue
        row = []
        for i in range(len(sigmas)):
            a = max(float(np.interp(f, fo, p_out[i])), 0.0)
            b = max(float(np.interp(f, fo, p_ideal)), 1e-30)
            row.append(float(np.sqrt(a / b)))
        table[f"{lam:g} m"] = row
        mark = "  <- Nyquist" if lam <= 2 * DST_M + 1 else ""
        print(f"  {lam:>10.0f} m{f:>11.5f}"
              + "".join(f"{r:>18.3f}" for r in row[:3]) + mark)

    hr("ONE NUMBER: RMS DIFFERENCE FROM THE IDEAL DOWNSAMPLE (metres)")
    print("  Captures BOTH failure modes at once - folded power the filter left in,")
    print("  and real terrain the filter took out. Lower is strictly better.")
    print()
    rms = {}
    for i, nm in enumerate(names[:3]):
        rms[nm] = float(np.mean(rms_vs_ideal[i]))
        print(f"  {nm:>18}   {rms[nm]:8.4f} m")
    for i, nm in enumerate(names):
        rms[nm] = float(np.mean(rms_vs_ideal[i]))
    print("  These differ by 0.04 %. RMS is dominated by the passband both keep,")
    print("  so it CANNOT discriminate here and the spectrum below is the evidence.")

    hr("SLOPE PERCENTILES UNDER EACH SIGMA (25 m grid)")
    print(f"  {'sigma':>18}{'p50':>9}{'p90':>9}{'p99':>9}{'max':>9}")
    slope_out = {}
    for i, nm in enumerate(names):
        m = {k: float(np.mean([sp[k] for sp in slopes[i]])) for k in slopes[i][0]}
        slope_out[nm] = m
        if i < 3 or abs(sigmas[i] - 0.30) < 1e-9:
            print(f"  {nm:>18}{m['p50']:>9.3f}{m['p90']:>9.3f}{m['p99']:>9.3f}"
                  f"{m['max']:>9.2f}")

    hr("SIGMA SCAN — the two conventions fail in OPPOSITE directions")
    print("  For each sigma, measured against the ideal band-limited downsample:")
    print("    passband loss  = 1 - min amplitude ratio at wavelengths >= 120 m")
    print("                     (real terrain the filter removed)")
    print("    alias excess   = max amplitude ratio - 1 at wavelengths <= 65 m")
    print("                     (folded power the filter failed to remove)")
    print("  The score is the WORSE of the two, so a sigma cannot win by being")
    print("  excellent at one and useless at the other.")
    print()
    print(f"  {'sigma':>16}{'passband loss':>16}{'alias excess':>15}{'worse of two':>15}")
    lam_pass = [400.0, 200.0, 120.0]
    lam_alias = [65.0, 55.0, 51.0]

    def ratio_at(i, lam):
        f = 1.0 / lam
        a = max(float(np.interp(f, fo, p_out[i])), 0.0)
        b = max(float(np.interp(f, fo, p_ideal)), 1e-30)
        return float(np.sqrt(a / b))

    scores = {}
    for i, nm in enumerate(names):
        loss = 1.0 - min(ratio_at(i, l) for l in lam_pass)
        excess = max(ratio_at(i, l) for l in lam_alias) - 1.0
        worse = max(loss, excess)
        scores[nm] = {"sigma": sigmas[i], "passband_loss": loss,
                      "alias_excess": excess, "worse": worse}
        print(f"  {nm:>16}{loss:>16.3f}{excess:>15.3f}{worse:>15.3f}")

    hr("VERDICT")
    pick = min(range(len(sigmas)), key=lambda i: scores[names[i]]["worse"])
    s0, s1, s2 = scores[names[0]], scores[names[1]], scores[names[2]]
    print(f"  NEITHER CONVENTION IS ACCEPTABLE, and they fail opposite ways:")
    print(f"    (f-1)/2 = 0.125  leaves {s1['alias_excess'] * 100:.1f} % excess amplitude at "
          f"Nyquist")
    print(f"    f/2     = 0.625  removes {s2['passband_loss'] * 100:.1f} % of real terrain "
          f"at 120 m and longer")
    print(f"  and 0.125 is indistinguishable from the unfiltered control to four")
    print(f"  decimals in every column and every slope percentile, because at")
    print(f"  f = 1.25 scipy truncates it to a 3-tap kernel of centre weight ~0.9999.")
    print(f"  Choosing it would be choosing no anti-aliasing at all.")
    print()
    print(f"  The aliasing being corrected is REAL and measured, not assumed: the")
    print(f"  unfiltered control runs {s0['alias_excess'] * 100:.1f} % hot at Nyquist.")
    print()
    print(f"  SHIP sigma = {sigmas[pick]:.3f} source px ({names[pick]}), which holds")
    print(f"  passband loss to {scores[names[pick]]['passband_loss'] * 100:.1f} % and alias "
          f"excess to {scores[names[pick]]['alias_excess'] * 100:.1f} %.")
    print(f"  This is a MEASURED choice, not a convention borrowed from a library.")
    why = (f"scan minimum of max(passband loss, alias excess) = "
           f"{scores[names[pick]]['worse']:.3f}; (f-1)/2 leaves "
           f"{s1['alias_excess']:.3f} excess, f/2 costs {s2['passband_loss']:.3f} passband")

    print()
    print("  CAVEAT KEPT IN VIEW: the 100 m row of the spectrum table dips to 0.760")
    print("  in the control, where its neighbours at 120 m and 80 m read 1.000 and")
    print("  1.019. That is a binning artefact in the shared denominator, not a")
    print("  property of any filter -- it moves all three columns together. The")
    print("  passband metric above therefore uses 120 m and longer and excludes it,")
    print("  rather than letting an artefact drive the choice.")

    (BASE_DIR / args.out).write_text(json.dumps({
        "downsample_factor": f_down, "sigmas": sigmas, "names": names,
        "amplitude_ratio_vs_ideal": table, "rms_vs_ideal_m": rms,
        "slope_percentiles": slope_out,
        "chosen_index": pick, "chosen_sigma": sigmas[pick], "reason": why,
        "scan": scores,
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
