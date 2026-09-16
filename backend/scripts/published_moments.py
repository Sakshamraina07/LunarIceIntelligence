"""
published_moments.py -- infer the effective number of looks from PUBLISHED CPR
moments, and record the mode the published product was acquired in.

    python backend/scripts/published_moments.py

The input is eight rows of Table 1 of

    W. Fa and Y. Cai, "Circular polarization ratio characteristics of impact
    craters from Mini-RF observations and implications for ice detection at the
    polar regions of the Moon," J. Geophys. Res. Planets, 118(8), 1582-1608,
    2013.  doi:10.1002/jgre.20110

transcribed by hand from the published table. They are literals here and that
is deliberate: they are somebody else's published numbers, so there is no
artifact of ours to read them from, and the transcription is the thing a reader
must be able to check.

WHAT THIS SHOWS
    A CPR image is a ratio of two N-look intensities, so R/CPR ~ F(2N,2N).
    The relative dispersion, the skewness and the excess kurtosis of F(2N,2N)
    are each monotone in N, so each is independently invertible. Applying all
    three to the same published distributions gives three estimates of one
    quantity whose AGREEMENT tests whether the distributions are F-shaped, and
    whose DISAGREEMENT carries the terrain.

WHAT IT DOES NOT SHOW
    Two biases act in opposite directions -- terrain widens the dispersion and
    biases N low, channel correlation narrows the ratio and biases it high --
    so the inversion is neither a lower nor an upper bound on the documented
    count. The published sigma is a POPULATION dispersion, the sample estimates
    from the same pixels are statistically dependent, and no uncertainty is
    propagated from finite samples, spatial dependence or rounded published
    moments. This is a model-consistency check with unknown nuisance
    parameters, not a validation of anything.

THE MODE TABLE, AND A CORRECTION DATED 2026-09-16
    Mini-RF ran two S-band modes, and which one Fa & Cai analysed decides what
    the inverted N is being compared against. An earlier revision of this file
    asserted "Fa & Cai used the 14.8 m baseline CDR"; the baseline mode is
    150 m, so a 14.8 m product cannot be one. The mode table below carries each
    figure with the source that documents it, and the superseded reading is
    kept in `superseded` rather than deleted. What remains genuinely
    unverified is Fa & Cai's own statement of their product, which was not
    reachable from this host -- `mode_verification`, written by
    published_moments_mode_check.py, records every attempt.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.optimize import brentq
from scipy.stats import f as Fdist

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "published_moments.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

SOURCE = {
    "citation": ("Fa, W. and Cai, Y. (2013), J. Geophys. Res. Planets, "
                 "118(8), 1582-1608, doi:10.1002/jgre.20110"),
    "table": "Table 1, p. 1585, interior region",
    "transcribed_by_hand": True,
}

ROWS = [
    # name,                mu,   sigma, gamma_1, gamma_2
    ("Hermite B",          0.97, 0.50,  1.75,    6.12),
    ("Rozhdestvenskiy N",  0.93, 0.50,  1.83,    7.66),
    ("Main L",             0.92, 0.48,  1.82,    7.06),
    ("Schomberger A",      0.99, 0.50,  1.77,    6.51),
    ("Cardanus E",         0.83, 0.46,  2.19,    7.19),
    ("Byrgius C",          1.12, 0.59,  1.88,    7.33),
    ("Dollond E",          1.00, 0.53,  1.85,    7.00),
    ("Stevinus A",         1.04, 0.56,  1.93,    7.95),
]

DOCUMENTED_LOOKS = 8.0

#: Every figure here is transcribed from print, with the sentence that carries
#: it. None is a measurement of ours, and none may be presented as one.
MODE_TABLE = {
    "instrument": "Mini-RF, Lunar Reconnaissance Orbiter, S-band (12.6 cm)",
    "zoom": {
        "nominal_looks": 8,
        "resolution_m": 7.5,
        "cdr_pixel_spacing_m": 14.8,
        "source": ("Raney, Cahill, Patterson & Bussey (2012), JGR Planets "
                   "117(E12), E00H21, para. [4]: the S-band zoom mode has "
                   "7.5-m pixels and 8 looks"),
    },
    "baseline": {
        "nominal_looks": 16,
        "resolution_m": 150,
        "source": "Spudis et al. (2013), JGR Planets, Mini-RF mode table",
    },
    "effective_looks_reported": {
        "value": 6.7,
        "source": ("Spudis et al. (2013), para. [13]: an effective number of "
                   "looks of about 6.7 against 8 planned"),
        "caveat": "attributed there to unpublished analysis; not reproducible from print",
    },
    "which_mode_fa_and_cai_analysed": {
        "reading": ("the 14.8 m calibrated data record is the zoom mode's, "
                    "nominal 8 looks — 14.8 m is twice the 7.5 m zoom "
                    "resolution and an order of magnitude finer than the "
                    "150 m baseline"),
        "rests_on": "the mode table above, not on Fa & Cai's own text",
        "status": "UNVERIFIED against the source — see mode_verification",
    },
    "superseded": {
        "was": ("Raney et al. 2012, para. [4], quotes 8 looks for the S-band "
                "ZOOM mode at 7.5 m. Fa & Cai used the 14.8 m baseline CDR. "
                "These are adjacent products of one instrument, not the same "
                "product."),
        "corrected_on": "2026-09-16",
        "why": ("the baseline mode images at 150 m, so a 14.8 m product is not "
                "a baseline product; the earlier note put the analysed data in "
                "the wrong mode and would have compared the inverted N against "
                "the wrong nominal count"),
    },
}


def rel_sd(N: float) -> float:
    """Relative standard deviation of F(2N, 2N)."""
    return float(np.sqrt((2 * N - 1) / (N * (N - 2))))


def skewness(N: float) -> float:
    """Skewness of F(d1, d2) with d1 = d2 = 2N. Requires d2 > 6, i.e. N > 3."""
    d1 = d2 = 2.0 * N
    return float(((2 * d1 + d2 - 2) * np.sqrt(8 * (d2 - 4)))
                 / ((d2 - 6) * np.sqrt(d1 * (d1 + d2 - 2))))


def excess_kurtosis(N: float) -> float:
    """Excess kurtosis of F(d1, d2), d1 = d2 = 2N. Requires d2 > 8, N > 4."""
    d1 = d2 = 2.0 * N
    num = (d1 * (5 * d2 - 22) * (d1 + d2 - 2) + (d2 - 4) * (d2 - 2) ** 2)
    den = d1 * (d2 - 6) * (d2 - 8) * (d1 + d2 - 2)
    return float(12.0 * num / den)


def _invert(fn, target, lo, hi, what):
    """Monotone decreasing in N over the domains used here."""
    try:
        return float(brentq(lambda N: fn(N) - target, lo, hi))
    except ValueError:
        print(f"  ! {what}: target {target:.4f} outside the invertible range "
              f"[{fn(hi):.4f}, {fn(lo):.4f}] -- reported as null")
        return None


def main() -> int:
    # The P10 access record belongs to published_moments_mode_check.py; this
    # script must not silently drop it by rewriting the file around it.
    previous = {}
    if OUT.is_file():
        try:
            previous = json.loads(OUT.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            previous = {}

    out = {"schema": "lunar-ice/published-moments/2",
           "generated_utc": datetime.now(timezone.utc).isoformat(),
           "generator": "backend/scripts/published_moments.py",
           "source": SOURCE,
           "documented_looks": DOCUMENTED_LOOKS,
           "mode_table": MODE_TABLE,
           "craters": []}

    print(f"{'crater':20s} {'mu':>5s} {'sd':>5s} {'relSD':>7s} "
          f"{'N(sd)':>7s} {'skew':>5s} {'N(skew)':>8s} {'kurt':>5s} {'N(kurt)':>8s}")

    n_sd, n_sk, n_ku = [], [], []
    for name, mu, sd, g1, g2 in ROWS:
        r = sd / mu
        Ns = _invert(rel_sd, r, 2.0001, 1e6, f"{name} sd")
        Nk = _invert(skewness, g1, 3.0001, 1e6, f"{name} skew")
        Nu = _invert(excess_kurtosis, g2, 4.0001, 1e6, f"{name} kurt")
        n_sd.append(Ns); n_sk.append(Nk); n_ku.append(Nu)
        out["craters"].append(dict(
            name=name, mu=mu, sigma=sd, skewness=g1, excess_kurtosis=g2,
            relative_sd=r, N_from_dispersion=Ns, N_from_skewness=Nk,
            N_from_kurtosis=Nu))
        f = lambda v: ("%8.2f" % v) if v is not None else "     n/a"
        print(f"{name:20s} {mu:5.2f} {sd:5.2f} {r:7.4f} "
              f"{f(Ns)[1:]} {g1:5.2f} {f(Nk)} {g2:5.2f} {f(Nu)}")

    med_sd = float(np.median(n_sd))
    med_sk = float(np.median([v for v in n_sk if v is not None]))
    ku_ok = [v for v in n_ku if v is not None]
    med_ku = float(np.median(ku_ok)) if ku_ok else None

    out["median_N_from_dispersion"] = med_sd
    out["median_N_from_skewness"] = med_sk
    out["median_N_from_kurtosis"] = med_ku
    out["agreement_sd_vs_skew_percent"] = abs(med_sk - med_sd) / med_sd * 100
    # The same spread computed from the medians AS PRINTED (8.75, 9.08) rather
    # than from the unrounded ones. It differs in the first decimal, and the
    # manuscript quotes the printed-input value, so both are emitted.
    out["agreement_sd_vs_skew_percent_from_printed_medians"] = (
        abs(round(med_sk, 2) - round(med_sd, 2)) / round(med_sd, 2) * 100)
    out["ordering_holds"] = bool(med_sd < med_sk < (med_ku if med_ku else 1e9))
    out["ordering_note"] = ("under a multiplicative-heterogeneity model the three "
                            "estimates fall in the order N_sigma < N_gamma1 < "
                            "N_gamma2; that is the order observed")

    print()
    print(f"median N from dispersion : {med_sd:.2f}  "
          f"(range {min(n_sd):.2f}-{max(n_sd):.2f})")
    print(f"median N from skewness   : {med_sk:.2f}")
    if med_ku is not None:
        print(f"median N from kurtosis   : {med_ku:.2f}")
    print(f"ordering N_sigma < N_g1 < N_g2 : {out['ordering_holds']}")
    print(f"\nmode table (all transcribed from print, none measured here):")
    print(f"  zoom      {MODE_TABLE['zoom']['nominal_looks']} looks at "
          f"{MODE_TABLE['zoom']['resolution_m']} m, CDR "
          f"{MODE_TABLE['zoom']['cdr_pixel_spacing_m']} m")
    print(f"  baseline  {MODE_TABLE['baseline']['nominal_looks']} looks at "
          f"{MODE_TABLE['baseline']['resolution_m']} m")
    print(f"  effective count reported for the zoom mode: "
          f"{MODE_TABLE['effective_looks_reported']['value']}")
    print(f"  CORRECTED {MODE_TABLE['superseded']['corrected_on']}: "
          f"{MODE_TABLE['superseded']['why']}")

    N = med_sd
    cons = dict(
        N=N,
        bias=N / (N - 1),
        relative_sd=rel_sd(N),
        floor_95=float(Fdist.ppf(0.95, 2 * N, 2 * N)),
        fp_at_true_cpr_0p7=float(1 - Fdist.cdf(1.0 / 0.7, 2 * N, 2 * N)) * 100,
        fp_at_true_cpr_0p5=float(1 - Fdist.cdf(1.0 / 0.5, 2 * N, 2 * N)) * 100,
        note=("Upper bounds. F(2N,2N) assumes the two circular channels are "
              "independent; see METHODS 7.10."),
    )
    out["consequence_at_median_dispersion_N"] = cons
    print(f"\nAt N = {N:.2f}:  bias {cons['bias']:.4f}   "
          f"95% floor {cons['floor_95']:.4f}   "
          f"exceedance@0.7 {cons['fp_at_true_cpr_0p7']:.2f}%   "
          f"@0.5 {cons['fp_at_true_cpr_0p5']:.2f}%")

    failures = []
    if out["agreement_sd_vs_skew_percent"] > 15.0:
        failures.append(
            f"dispersion and skewness disagree by "
            f"{out['agreement_sd_vs_skew_percent']:.1f}% (> 15%): the published "
            f"distributions are not F(2N,2N)-shaped and no look count may be "
            f"inferred from them")
    for label, v in (("dispersion", med_sd), ("skewness", med_sk)):
        if not (6.0 <= v <= 12.0):
            failures.append(f"median N from {label} = {v:.2f} outside [6, 12]")
    if med_sd > med_sk * 1.05:
        failures.append(
            f"N from dispersion ({med_sd:.2f}) exceeds N from skewness "
            f"({med_sk:.2f}) by more than 5%: texture cannot produce this "
            f"ordering, so check the transcription and the estimators")

    out["gate_failures"] = failures
    for f_ in failures:
        print(f"FAIL: {f_}")
    if not failures:
        print("PASS: three moments agree to "
              f"{out['agreement_sd_vs_skew_percent']:.1f}%, in band, ordering as "
              "texture predicts")

    if "mode_verification" in previous:
        out["mode_verification"] = previous["mode_verification"]
        print("  carried forward: mode_verification (P10 access record)")

    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(BASE_DIR)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
