"""
The decisive ENL control: form 21 looks OURSELVES, from the single-look complex.

THE QUESTION
------------
The delivered sri product declares 21 looks and measures ENL 5-6. That bound --
"somewhere between 9 and 21" -- is honest but too wide to build a significance
test on, because every quantity in Phase 8 scales with N.

The single-look complex (_sli_) from the SAME PASS is on disk: 355,768 azimuth
lines x 759 slant-range bins of ComplexLSB8, which is contiguous complex64 at
byte 5,725,302 (asserted below against the file size, exactly). From it we can
build our own 21-look product and measure it with the identical patch method.
That is a ground truth, not another inference.

THREE OUTCOMES, NOT TWO
-----------------------
  1. our 21-look version also measures 5-6  -> the shortfall is in the SCENE
     (terrain texture), and the delivered product is fine;
  2. ours measures ~21 while the delivered sri measures 5-6 -> the delivered
     product is not carrying its nominal looks, a finding about the ARCHIVE;
  3. it depends on HOW the 21 looks are formed.

(3) is a real possibility and the reason this script forms the looks two ways.
Azimuth is sampled at the PRF, 3321.64 Hz, but only 1071.34 Hz of azimuth
bandwidth is processed -- an oversampling factor of about 3.1. So:

  * SPATIAL multilook, averaging 21 consecutive lines, averages 21 samples that
    are NOT independent. It can deliver at most ~21/3.1 ~ 6.8 looks -- which is
    suspiciously close to the 5-6 measured on the delivered product.
  * SUB-BAND multilook, splitting the processed azimuth spectrum into 21
    non-overlapping bands and averaging their intensities, delivers looks that
    ARE independent, and should approach 21.

If those two disagree, the answer is neither "texture" nor "the archive is
wrong": it is that "21 looks" names a method, and the two methods do not deliver
the same number of looks. The oversampling factor is MEASURED here from the
azimuth power spectrum rather than taken from the label, and the label's
1071.34 Hz then serves as an independent check on that measurement.

Windowed memmap reads only; nothing multi-gigabyte is loaded whole.

Usage:
    python -u backend/scripts/slc_multilook_control.py [--windows 6] [--lines 8400]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

BASE_DIR = Path(__file__).resolve().parents[2]

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

RAW = BASE_DIR / "data/pradan/raw/data/calibrated/20200808"
STEM = "ch2_sar_ncxl_20200808t201154198"
SLC = RAW / f"{STEM}_d_sli_xx_cp_lh_d18.tif"

LINES, SAMPLES, OFFSET = 355768, 759, 5725302
PRF_HZ = 3321.641156
PROCESSED_BW_HZ = 1071.335975
AZIMUTH_LOOKS = 21

_T0 = time.time()


def beat(msg: str) -> None:
    """Heartbeat: wall-clock AND elapsed, so a stalled run and a dead one are
    distinguishable from the log alone, with no need to go looking for a pid."""
    print(f"  [{time.strftime('%H:%M:%S')}  +{time.time() - _T0:7.1f}s]  {msg}",
          flush=True)


def hr(t: str) -> None:
    print("\n" + "=" * 78 + "\n" + t + "\n" + "=" * 78, flush=True)


def _enl_tools():
    """Reuse measure_enl's estimator verbatim -- a control that used a different
    estimator would not be comparing like with like."""
    spec = importlib.util.spec_from_file_location(
        "_measure_enl", Path(__file__).with_name("measure_enl.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.patch_ratios, mod.mode_of


def open_slc() -> np.memmap:
    size = SLC.stat().st_size
    need = OFFSET + LINES * SAMPLES * 8
    assert size == need, (
        f"SLC layout does not match the label: {size} bytes on disk, "
        f"{need} implied by offset {OFFSET} + {LINES}x{SAMPLES}x8. Refusing to "
        f"memmap a raster whose geometry is not confirmed.")
    return np.memmap(SLC, dtype=np.complex64, mode="r",
                     offset=OFFSET, shape=(LINES, SAMPLES))


def measure_oversampling(z: np.ndarray) -> dict:
    """Occupied azimuth bandwidth, from the data's own spectrum.

    The processed band occupies a fraction of the PRF; 1/that fraction is the
    azimuth oversampling factor, i.e. how many samples it takes to get one
    independent look.
    """
    n = z.shape[0]
    spec = np.abs(np.fft.fft(z - z.mean(axis=0), axis=0)) ** 2
    psd = spec.mean(axis=1)
    psd = psd / psd.max()
    # Occupied = above a floor set well below the passband but above the skirts.
    occupied = int((psd > 0.05).sum())
    bw_hz = occupied / n * PRF_HZ
    return {"occupied_bins": occupied, "total_bins": n,
            "measured_bandwidth_hz": bw_hz,
            "label_bandwidth_hz": PROCESSED_BW_HZ,
            "ratio_to_label": bw_hz / PROCESSED_BW_HZ,
            "oversampling_factor": PRF_HZ / bw_hz if bw_hz > 0 else float("nan"),
            "max_looks_from_spatial_average": AZIMUTH_LOOKS * bw_hz / PRF_HZ}


def mlook_spatial(z: np.ndarray, n: int) -> np.ndarray:
    """Average the INTENSITY of n consecutive azimuth lines, then decimate."""
    rows = (z.shape[0] // n) * n
    i = (np.abs(z[:rows]) ** 2).astype(np.float64)
    return i.reshape(rows // n, n, z.shape[1]).mean(axis=1)


def mlook_subband(z: np.ndarray, n: int, occupied: int) -> np.ndarray:
    """Split the processed azimuth band into n non-overlapping sub-bands, image
    each separately, and average the n intensities. This is what a SAR processor
    means by 'n azimuth looks'.

    Decimated by n at the end so the output grid matches mlook_spatial's and the
    two ENLs are measured on comparably-sampled images.
    """
    rows = (z.shape[0] // n) * n
    Z = np.fft.fft(z[:rows] - z[:rows].mean(axis=0), axis=0)
    nfft = Z.shape[0]
    # The occupied band is centred on the Doppler centroid; find it on the
    # measured spectrum rather than assuming it sits at bin zero.
    psd = np.abs(Z).mean(axis=1)
    centre = int(np.argmax(np.convolve(psd, np.ones(max(occupied, 1)), "same")))
    half = max(occupied // 2, n)
    band = (np.arange(centre - half, centre - half + 2 * half) % nfft)
    width = len(band) // n
    acc = np.zeros((rows, z.shape[1]), dtype=np.float64)
    for k in range(n):
        sub = np.zeros_like(Z)
        idx = band[k * width:(k + 1) * width]
        sub[idx] = Z[idx]
        acc += np.abs(np.fft.ifft(sub, axis=0)) ** 2
    acc /= n
    return acc[::n]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", type=int, default=6)
    ap.add_argument("--lines", type=int, default=8400, help="azimuth lines per window")
    ap.add_argument("--patch", type=int, default=16)
    ap.add_argument("--out", default="docs/slc_multilook_control.json")
    args = ap.parse_args()

    patch_ratios, mode_of = _enl_tools()
    z_all = open_slc()

    hr("THE SINGLE-LOOK COMPLEX, AND THE CONTROL IT MAKES POSSIBLE")
    print(f"  {SLC.name}")
    print(f"  {LINES:,} azimuth lines x {SAMPLES} slant-range bins, complex64")
    print(f"  layout asserted against file size: EXACT")
    print(f"  PRF {PRF_HZ:.2f} Hz, processed azimuth bandwidth {PROCESSED_BW_HZ:.2f} Hz")
    print(f"  reading {args.windows} windows of {args.lines:,} lines "
          f"({args.lines * SAMPLES * 8 / 1e6:.0f} MB each), spread along the pass")

    starts = np.linspace(0, LINES - args.lines - 1, args.windows).astype(int)
    rows = []
    for wi, s0 in enumerate(starts):
        beat(f"window {wi + 1}/{args.windows}: lines {s0:,}–{s0 + args.lines:,}")
        z = np.array(z_all[s0:s0 + args.lines], dtype=np.complex64)
        # The swath occupies a fixed span of slant-range bins (the rest is
        # zero-fill outside the antenna footprint), so crop to the bins that are
        # non-zero down the whole window rather than carrying padding into an
        # FFT, where it would broaden the measured spectrum.
        col = (np.abs(z) > 0).mean(axis=0)
        keep = np.flatnonzero(col > 0.999)
        if keep.size < 64:
            print(f"      skipped: only {keep.size} fully-valid range bins")
            continue
        z = z[:, keep.min():keep.max() + 1]
        frac = float((np.abs(z) > 0).mean())
        if frac < 0.98:
            print(f"      skipped: {frac * 100:.1f} % non-zero inside the swath")
            continue
        if wi == 0:
            print(f"      swath: range bins {keep.min()}–{keep.max()} "
                  f"({z.shape[1]} of {SAMPLES}), {frac * 100:.2f} % non-zero")

        osamp = measure_oversampling(z)
        i1 = (np.abs(z) ** 2).astype(np.float64)
        v1 = np.ones_like(i1, dtype=bool)
        enl_1look = mode_of(patch_ratios(i1, v1, args.patch))

        sp = mlook_spatial(z, AZIMUTH_LOOKS)
        enl_sp = mode_of(patch_ratios(sp, np.ones_like(sp, dtype=bool), args.patch))

        sb = mlook_subband(z, AZIMUTH_LOOKS, osamp["occupied_bins"])
        enl_sb = mode_of(patch_ratios(sb, np.ones_like(sb, dtype=bool), args.patch))

        rows.append({"window": wi, "start_line": int(s0), **osamp,
                     "enl_single_look": enl_1look,
                     "enl_spatial_21": enl_sp, "enl_subband_21": enl_sb})
        beat(f"      bw {osamp['measured_bandwidth_hz']:7.1f} Hz "
             f"(x{osamp['ratio_to_label']:.2f} label)  oversampling "
             f"{osamp['oversampling_factor']:.2f}  ENL: 1-look {enl_1look:5.2f}  "
             f"spatial21 {enl_sp:5.2f}  subband21 {enl_sb:5.2f}")

    if not rows:
        print("\nNo usable window. Nothing measured.")
        return 1

    def med(k):
        return float(np.median([r[k] for r in rows]))

    hr("RESULT")
    print(f"  windows used: {len(rows)} of {args.windows}\n")
    print(f"  {'quantity':>38}  {'measured':>10}  {'expected':>12}")
    print(f"  {'azimuth bandwidth (Hz)':>38}  {med('measured_bandwidth_hz'):>10.1f}  "
          f"{PROCESSED_BW_HZ:>12.1f}")
    print(f"  {'azimuth oversampling factor':>38}  {med('oversampling_factor'):>10.2f}  "
          f"{PRF_HZ / PROCESSED_BW_HZ:>12.2f}")
    print(f"  {'ENL of the single-look intensity':>38}  {med('enl_single_look'):>10.2f}  "
          f"{1.0:>12.2f}")
    print(f"  {'ENL, 21 looks by SPATIAL average':>38}  {med('enl_spatial_21'):>10.2f}  "
          f"{med('max_looks_from_spatial_average'):>12.2f}")
    print(f"  {'ENL, 21 looks by SUB-BAND split':>38}  {med('enl_subband_21'):>10.2f}  "
          f"{float(AZIMUTH_LOOKS):>12.2f}")
    print(f"  {'ENL of the DELIVERED sri product':>38}  {'5–6':>10}  "
          f"{'21 (nominal)':>12}")

    hr("WHICH OUTCOME")
    sp, sb, one = med("enl_spatial_21"), med("enl_subband_21"), med("enl_single_look")
    print(f"  The single-look intensity measures {one:.2f} against a theoretical 1.00.")
    if one < 0.8:
        print("  Below 1.0 means real terrain texture is present even at single-look")
        print("  resolution, and every ENL here is depressed by it.")
    else:
        print("  At ~1.0 there is no detectable texture at single-look resolution, so")
        print("  texture is NOT what depresses the multilooked numbers.")
    print()
    if sb > 1.5 * sp:
        print(f"  Sub-band multilooking delivers {sb:.1f} looks where spatial averaging")
        print(f"  of the same 21 samples delivers {sp:.1f}. The two methods do NOT give")
        print("  the same number of looks, so '21 looks' names a METHOD, not a count.")
        print("  The delivered product's 5–6 sits with the spatial figure.")
    else:
        print(f"  Both methods land together ({sp:.1f} vs {sb:.1f}), so the look-forming")
        print("  method is not what separates nominal from measured.")

    (BASE_DIR / args.out).write_text(
        json.dumps({"windows": rows, "medians": {
            k: med(k) for k in ("measured_bandwidth_hz", "oversampling_factor",
                                "enl_single_look", "enl_spatial_21",
                                "enl_subband_21")}}, indent=2), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
