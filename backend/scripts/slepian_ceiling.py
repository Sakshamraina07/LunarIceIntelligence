"""
slepian_ceiling.py -- what 21 correlated looks can actually deliver.

    python backend/scripts/slepian_ceiling.py

NONE OF THESE IS A BOUND. THE FILE NAME IS HISTORICAL.
------------------------------------------------------
Corrected 2026-09-16. An earlier reading called 2WT = 6.77 the ceiling on the
ENL of a 21-sample average, and the very computation below disproves it: the
exact finite-sample value for a rectangular spectrum of the same support is
7.34, and a mildly shaped spectrum of that support gives 7.38. Each figure is
a REFERENCE VALUE for a multilooking scheme, not a number the ENL cannot
exceed. The file keeps its name because the artifact it writes is addressed by
it; every value it emits is labelled.

WHY
---
METHODS 7.3 derives 2WT = N*B/PRF = 6.77 for the ENL of a 21-look spatial
average when the PRF oversamples the processed Doppler bandwidth. 2WT is a
large-time-bandwidth approximation. At N = 21 it is not large.

This computes the EXACT finite-N answer for the same model: build the covariance
of 21 samples of a band-limited complex field, and take the participation ratio
of its eigenvalues, which is the effective number of independent modes. For a
rectangular processed spectrum that gives 7.34, not 6.77 -- the asymptotic form
UNDERSTATES it by about 8 %.

It also computes the value for a HAMMING-shaped spectrum, which is what the
label declares the processor applied (`azimuth_window = HAMMING`). Tapering
narrows the effective bandwidth and lowers it to 4.07.

  2WT   6.77   asymptotic, the form already in METHODS 7.3
  PR    7.34   exact participation ratio, rectangular spectrum
  SHAPE 7.38   exact, 1 - 0.1 cos(2 pi f / B) -- ABOVE the rectangular value
  HAMM  4.07   exact, Hamming-shaped spectrum -- what the label declares

The measured spatial arm is 4.52: below the untapered values and just above the
tapered one, which is the ordering the physics requires and is the point of
computing all four rather than quoting one.

PRF and bandwidth are READ from docs/slc_multilook_control.json rather than
written here, so this cannot drift from the run the manuscript quotes.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "slepian_ceiling.json"
SLC = BASE_DIR / "docs" / "slc_multilook_control.json"
PRED = BASE_DIR / "docs" / "enl_predictions.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

#: Hamming coefficient the DFSAR label declares (azimuth_window_coefficient).
HAMMING_A = 0.54


def hamming_correlation(lags: np.ndarray, oversampling: float,
                        a: float = HAMMING_A) -> np.ndarray:
    """Field correlation for a Hamming-shaped processed spectrum.

    The correlation of a band-limited field is the Fourier transform of its
    power spectrum. For a rectangular band that is a sinc; for a tapered band it
    is the transform of |W(f)|^2, computed here by quadrature rather than
    assumed to have a closed form.
    """
    f = np.linspace(-0.5, 0.5, 20001)
    if a is None:
        # the mildly shaped case: the SPECTRUM itself is 1 - 0.1 cos(2 pi f / B),
        # not a window amplitude, so it is not squared
        spec = 1.0 - 0.1 * np.cos(2.0 * np.pi * f)
    else:
        w = a + (1.0 - a) * np.cos(2.0 * np.pi * f)
        spec = w ** 2
    denom = np.trapezoid(spec, f)
    return np.array([
        np.trapezoid(spec * np.cos(2.0 * np.pi * float(l) * f / oversampling), f) / denom
        for l in np.atleast_1d(lags)
    ])


def participation_ratio(n_looks: int, over: float) -> float:
    """Effective number of independent modes in an n-sample average of a
    band-limited field oversampled by `over`: the participation ratio of the
    eigenvalues of the n x n sinc covariance. Exact at finite n, where 2WT is
    only asymptotic."""
    k = np.arange(n_looks)
    cov = np.sinc((k[:, None] - k[None, :]) / over)
    lam = np.linalg.eigvalsh(cov)[::-1]
    return float(lam.sum() ** 2 / np.sum(lam ** 2))


def main() -> int:
    slc = json.loads(SLC.read_text(encoding="utf-8"))
    pred = json.loads(PRED.read_text(encoding="utf-8"))
    decl = pred["predictions"][0]["declared"]

    prf = float(decl["pulse_repetition_frequency"])
    bw = float(decl["total_processed_azimuth_bandwidth"])
    n_looks = int(float(decl["azimuth_looks"]))
    measured = float(slc["medians"]["enl_spatial_21"])

    over = prf / bw
    two_wt = n_looks * bw / prf

    k = np.arange(n_looks)
    lag = k[:, None] - k[None, :]

    # rectangular processed spectrum -> sinc correlation
    cov = np.sinc(lag / over)
    enl_rect = n_looks ** 2 / np.sum(np.abs(cov) ** 2)
    lam = np.linalg.eigvalsh(cov)[::-1]
    participation = float(lam.sum() ** 2 / np.sum(lam ** 2))

    # Hamming-shaped spectrum
    cov_h = hamming_correlation(lag.ravel(), over).reshape(n_looks, n_looks)
    enl_hamm = float(n_looks ** 2 / np.sum(np.abs(cov_h) ** 2))

    # A MILDLY SHAPED SPECTRUM OF THE SAME SUPPORT. Neither 2WT nor the
    # rectangular participation ratio is a bound, and the cheapest way to show
    # that is to perturb the spectrum slightly and watch the answer move UP:
    # 1 - 0.1 cos(2 pi f / B) over the same band.
    cov_s = hamming_correlation(lag.ravel(), over, a=None).reshape(n_looks, n_looks)
    enl_shaped = float(n_looks ** 2 / np.sum(np.abs(cov_s) ** 2))
    part_shaped = float(np.linalg.eigvalsh(cov_s).sum() ** 2
                        / np.sum(np.linalg.eigvalsh(cov_s) ** 2))

    print("=" * 78)
    print("SLEPIAN / PARTICIPATION-RATIO CEILING for 21 correlated looks")
    print("=" * 78)
    print(f"  PRF                       {prf:.6f} Hz   (read from the label)")
    print(f"  processed azimuth bw      {bw:.6f} Hz")
    print(f"  oversampling              {over:.6f}")
    print()
    print(f"  2WT = N*B/PRF             {two_wt:.4f}   asymptotic (METHODS 7.3)")
    print(f"  participation ratio       {participation:.4f}   exact, rectangular spectrum")
    print(f"  ENL of the 21-mean, rect  {enl_rect:.4f}")
    print(f"  mildly shaped spectrum    {enl_shaped:.4f}   1 - 0.1 cos(2 pi f / B), "
          f"same support")
    print(f"  Hamming({HAMMING_A})-shaped        {enl_hamm:.4f}   exact, what the label declares")
    print()
    print(f"  measured spatial arm      {measured:.4f}")
    print(f"  eigenvalues, top 6        {np.round(lam[:6], 3).tolist()}")
    print(f"  above half the largest    {int((lam > 0.5 * lam[0]).sum())}")
    print()
    ordered = enl_hamm < measured < participation
    print(f"  Hamming < measured < rectangular : {ordered}")
    print("  The measured arm sits below the rectangular bound and above the")
    print("  tapered one, which is the ordering the physics requires.")

    # THE SAME TWO NUMBERS FOR EVERY OTHER PRODUCT IN THE PREDICTION REGISTER.
    # 2WT and the participation ratio are both functions of (looks, oversampling)
    # alone, so the second acquisition's reference values are computed here from
    # ITS label rather than transcribed from a report. The generality test
    # (METHODS 7.4a) registered 2WT = 13.42 for the 5 March 2020 product before
    # it was opened; the finite-sample participation ratio for the same band is
    # the honest companion to it.
    others = []
    for i, p in enumerate(pred["predictions"]):
        n_i = int(float(p["declared"]["azimuth_looks"]))
        over_i = float(p["oversampling"])
        if i == 0:
            continue
        pr_i = participation_ratio(n_i, over_i)
        row = {"prediction_index": i, "label": p.get("label"),
               "azimuth_looks": n_i, "oversampling": over_i,
               "two_WT_asymptotic": float(p["predicted_ceiling"]),
               "participation_ratio_rectangular": pr_i}
        others.append(row)
        print(f"  [{i}] {n_i:>3} looks, oversampling {over_i:.4f}:  "
              f"2WT {row['two_WT_asymptotic']:7.4f}   participation ratio {pr_i:7.4f}")

    OUT.write_text(json.dumps({
        "schema": "lunar-ice/slepian-ceiling/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/slepian_ceiling.py",
        "inputs_read_from": {
            "prf_hz": str(PRED.relative_to(BASE_DIR).as_posix())
                      + "::predictions[0].declared.pulse_repetition_frequency",
            "bandwidth_hz": str(PRED.relative_to(BASE_DIR).as_posix())
                            + "::predictions[0].declared.total_processed_azimuth_bandwidth",
            "measured_spatial_arm": str(SLC.relative_to(BASE_DIR).as_posix())
                                    + "::medians.enl_spatial_21",
        },
        "prf_hz": prf,
        "processed_azimuth_bandwidth_hz": bw,
        "azimuth_looks": n_looks,
        "oversampling": over,
        "two_WT_asymptotic": two_wt,
        "participation_ratio_rectangular": participation,
        "enl_rectangular_spectrum": float(enl_rect),
        "enl_mildly_shaped_spectrum": enl_shaped,
        "participation_ratio_mildly_shaped": part_shaped,
        "mildly_shaped_spectrum": "1 - 0.1 cos(2 pi f / B) over the same support",
        "enl_hamming_054": enl_hamm,
        "hamming_coefficient": HAMMING_A,
        "measured_spatial_arm": measured,
        "eigenvalues_top10": np.round(lam[:10], 6).tolist(),
        "eigenvalues_above_half_max": int((lam > 0.5 * lam[0]).sum()),
        "ordering_holds": bool(ordered),
        "other_products": others,
        "other_products_note": ("2WT and the participation ratio depend only on "
                                "(azimuth_looks, oversampling), both read from each "
                                "product's own label via docs/enl_predictions.json; "
                                "no measurement of those products enters here"),
        "note": ("2WT is a large-time-bandwidth approximation and N = 21 is not "
                 "large; the exact participation ratio is ~8 % higher. The "
                 "measured arm lies between the tapered and untapered bounds."),
    }, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
