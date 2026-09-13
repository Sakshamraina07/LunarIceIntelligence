"""
cpr_dispersion.py -- the CPR speckle floor, measured in our own product.

    python -u backend/scripts/cpr_dispersion.py [--window 15] [--top 20]

WHY
---
Section 7.7 computes false-positive rates from `CPR * F(2N,2N)`, the sampling
distribution of a ratio of two INDEPENDENT N-look intensities. That model is an
assumption about the two circular channels, and it had never been checked
against the dispersion this product actually shows.

So it is measured here.

WHAT IT FOUND, STATED UP FRONT BECAUSE IT IS NOT WHAT WAS EXPECTED
------------------------------------------------------------------
The corrected minimum relative SD is 0.5867. Against the look count that applies
to this field -- N = 13.72, the measured ENL AFTER the 5x5 boxcar on which CPR is
actually formed -- the independent-channel floor is 0.4055, so the observed
dispersion is 1.45x WIDER than the model predicts, not narrower.

THIS MEASUREMENT THEREFORE DOES NOT SUPPORT THE CLAIM that the independent model
overstates our spread. It cannot refute it either, for the reason given below:
the statistic is an upper bound on the speckle floor, so a result above the
theory is consistent with the theory AND with residual terrain. Nothing is
claimed from this direction.

The upper-bound relabelling of the section 7.7 rates rests on section D below --
Putrevu et al. 2023's Byrgius C dispersion, which is BELOW its own
independent-channel floor and therefore does constrain the channels -- and not on
this measurement. Which evidence carries a claim matters more than the claim, and
these two point in opposite directions.

HOW, AND WHY THE SELECTION IS ON BACKSCATTER
--------------------------------------------
The dispersion of CPR inside a small window is speckle PLUS whatever real
variation of surface scattering the window contains. To get close to speckle
alone the window must be radiometrically homogeneous -- and homogeneity is
judged on `s0_native` (total backscatter), NOT on CPR.

THAT DISTINCTION IS THE WHOLE EXPERIMENT. Ranking windows by the flatness of
CPR and then reporting the CPR dispersion of the flattest ones measures the
selection, not the product: it is guaranteed to return a small number and the
number means nothing. Selecting on an independent radiometric quantity and
reading CPR afterwards is the only version of this that can be wrong.

WHAT THE ANSWER IS AND IS NOT
-----------------------------
The minimum relative SD across the selected windows is an UPPER BOUND on the
speckle floor: any residual terrain structure inside a window adds variance and
can only push the figure up. A measured floor well below the independent-channel
prediction is therefore evidence, and a measured floor at or above it is not
evidence of anything -- the experiment can falsify the independent model but
cannot confirm it. Stated here rather than discovered later.

THE CORRELATION CORRECTION
--------------------------
The 225 pixels in a 15x15 window are not 225 independent samples: `cpr_significance.py`
measures the CPR field's correlation area and this script READS that figure from
`docs/cpr_significance.json` rather than restating it. A sample SD over
positively correlated samples is biased LOW --

    E[s^2] = sigma^2 (1 - rho_bar),   rho_bar = (n/n_eff - 1)/(n - 1)

-- so the correction inflates the measured figure, which is the conservative
direction: it makes the measured floor harder to fall below the theory, not
easier.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import tifffile
from scipy.optimize import brentq

BASE_DIR = Path(__file__).resolve().parents[2]
NATIVE = BASE_DIR / "data" / "pradan" / "native"
SIG_JSON = BASE_DIR / "docs" / "cpr_significance.json"
ENL_JSON = BASE_DIR / "docs" / "enl.json"
OUT = BASE_DIR / "docs" / "cpr_dispersion.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def hr(t: str) -> None:
    print("\n" + "=" * 78 + "\n" + t + "\n" + "=" * 78, flush=True)


def rel_sd_independent(n: float) -> float:
    """Relative SD of a ratio of two independent N-look intensities.

    R ~ CPR * F(2N,2N); Var[F(2N,2N)] gives SD/mean = sqrt((2N-1)/(N(N-2))).
    Defined only for N > 2.
    """
    if n <= 2:
        return float("inf")
    return float(np.sqrt((2.0 * n - 1.0) / (n * (n - 2.0))))


def looks_for_rel_sd(r: float) -> float:
    """Invert the above: the N an independent-channel model would need."""
    try:
        return float(brentq(lambda n: rel_sd_independent(n) - r, 2.0001, 1e6))
    except ValueError:
        return float("nan")


def tiles(a: np.ndarray, k: int) -> np.ndarray:
    """Non-overlapping k x k tiles, as (n, k, k).

    NON-overlapping on purpose. Sliding windows would make neighbouring
    candidates share up to 14 of their 15 columns, so "the 20 most homogeneous
    windows" would be one window counted twenty times and the minimum over them
    would be the minimum over one sample.
    """
    h, w = (a.shape[0] // k) * k, (a.shape[1] // k) * k
    return (a[:h, :w].reshape(h // k, k, w // k, k)
            .swapaxes(1, 2).reshape(-1, k, k))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=15)
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()
    k, top = args.window, args.top

    cpr = np.asarray(tifffile.imread(str(NATIVE / "cpr_native.tif")), dtype=np.float64)
    s0 = np.asarray(tifffile.imread(str(NATIVE / "s0_native.tif")), dtype=np.float64)
    valid = np.asarray(tifffile.imread(str(NATIVE / "valid_native.tif"))) > 0

    hr("CPR DISPERSION — the speckle floor, measured on this product")
    print(f"  frame {cpr.shape[0]} x {cpr.shape[1]}, {int(valid.sum()):,} valid pixels")
    print(f"  windows {k} x {k}, non-overlapping, entirely inside the valid mask")
    print("  ranked by the coefficient of variation of s0_native — BACKSCATTER,")
    print("  not CPR, so the selection cannot bias the statistic being measured.\n")

    tc, ts, tv = tiles(cpr, k), tiles(s0, k), tiles(valid, k)
    full = tv.reshape(len(tv), -1).all(axis=1)
    tc, ts = tc[full], ts[full]
    print(f"  {len(tc):,} of {len(tv):,} tiles lie entirely inside the mask")
    if len(tc) < top:
        raise SystemExit(f"only {len(tc)} usable tiles; need {top}")

    s_mean = ts.reshape(len(ts), -1).mean(axis=1)
    s_sd = ts.reshape(len(ts), -1).std(axis=1, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        cv = np.where(s_mean > 0, s_sd / s_mean, np.inf)

    order = np.argsort(cv)[:top]
    c_mean = tc.reshape(len(tc), -1).mean(axis=1)[order]
    c_sd = tc.reshape(len(tc), -1).std(axis=1, ddof=1)[order]
    with np.errstate(divide="ignore", invalid="ignore"):
        c_rel = np.where(c_mean > 0, c_sd / c_mean, np.inf)

    print(f"\n  {'#':>3}{'s0 CV':>10}{'CPR mean':>12}{'CPR SD':>12}{'rel SD':>10}")
    for i in range(top):
        print(f"  {i + 1:>3}{cv[order][i]:>10.4f}{c_mean[i]:>12.6f}"
              f"{c_sd[i]:>12.6f}{c_rel[i]:>10.4f}")

    r_min = float(np.nanmin(c_rel))
    r_med = float(np.nanmedian(c_rel))
    print(f"\n  MINIMUM relative SD across {top} windows: {r_min:.4f}")
    print(f"  median: {r_med:.4f}")
    print("  The minimum is an UPPER BOUND on the speckle floor: residual terrain")
    print("  structure inside a window adds variance and can only push it up.")

    # ---------------------------------------------------- correlation correction
    hr("CORRELATION CORRECTION — 225 pixels are not 225 samples")
    sig = json.loads(SIG_JSON.read_text(encoding="utf-8"))
    es = sig["effective_samples"]
    A = float(es["area_all_lags"])
    n_px = k * k
    n_eff = n_px / A
    rho_bar = (n_px / n_eff - 1.0) / (n_px - 1.0)
    infl = 1.0 / np.sqrt(1.0 - rho_bar)
    print(f"  correlation area A = {A:.2f} px per independent sample")
    print(f"    read from docs/cpr_significance.json, measured on the CPR field")
    print(f"    itself ({es['n_patches']} patches of {es['patch']}x{es['patch']}); "
          f"{es['f2_pixels']:,} px -> {es['f2_effective_samples']:.1f} samples there.")
    print(f"  a {k}x{k} window therefore holds {n_eff:.2f} independent samples,")
    print(f"  mean pairwise correlation rho_bar = {rho_bar:.4f},")
    print(f"  E[s^2] = sigma^2 (1 - rho_bar)  ->  inflate the measured SD by "
          f"{infl:.4f}x\n")
    r_corr = r_min * infl
    print(f"  corrected minimum relative SD: {r_min:.4f} x {infl:.4f} = {r_corr:.4f}")
    samp_err = 1.0 / np.sqrt(2.0 * (n_eff - 1.0))
    print(f"\n  SAMPLING ERROR OF EACH WINDOW'S SD: 1/sqrt(2(n_eff - 1)) with")
    print(f"  n_eff = {n_eff:.2f} is {samp_err * 100:.0f} %. The figure above is the")
    print(f"  MINIMUM of {top} estimates carrying that spread, so it is biased LOW")
    print(f"  twice over. A figure biased low that still lands ABOVE the theory is")
    print(f"  a STRONGER negative result, not a weaker one -- but {r_corr:.4f} is")
    print(f"  not a precise floor and should not be quoted as one.")

    # ---------------------------------------------------- against the theory
    hr("AGAINST THE INDEPENDENT-CHANNEL MODEL")
    enl = json.loads(ENL_JSON.read_text(encoding="utf-8")) if ENL_JSON.exists() else {}
    rows = [
        (5.0, "round figure quoted in section 7.7"),
        (5.83, "measured ENL, LH, raw product (section 7.3)"),
        (6.77, "ceiling from the sub-band control, 21/3.10 (section 7.4)"),
        (13.72, "measured ENL, LH, after the 5x5 boxcar (section 7.6)"),
        (19.77, "measured ENL, LV, after the 5x5 boxcar (section 7.6)"),
    ]
    print(f"  {'N':>8}{'sqrt((2N-1)/(N(N-2)))':>24}{'measured/theory':>18}   basis")
    for n, why in rows:
        t = rel_sd_independent(n)
        print(f"  {n:>8.2f}{t:>24.4f}{r_corr / t:>18.3f}   {why}")

    n_app = looks_for_rel_sd(r_corr)
    print(f"\n  The corrected floor {r_corr:.4f} is what an INDEPENDENT-channel model")
    print(f"  would produce at N = {n_app:.1f} looks.")

    # The comparison that decides it. CPR here is formed on the boxcar-smoothed
    # field, so 13.72 is the look count that model would use for THIS field.
    n_ref = 13.72
    t_ref = rel_sd_independent(n_ref)
    ratio = r_corr / t_ref
    verdict_independent_overstates = bool(r_corr < t_ref)

    hr("VERDICT")
    if verdict_independent_overstates:
        print(f"  MEASURED {r_corr:.4f}  <<  THEORY {t_ref:.4f} at N = {n_ref}")
        print(f"  ratio {ratio:.3f}\n")
        print("  The independent-channel F(2N,2N) model OVERSTATES the spread of CPR")
        print("  in this product. Every false-positive rate computed from it -- the")
        print("  29.16 % at true CPR 0.7 and N = 5 in section 7.7, and every other")
        print("  entry in that table -- is therefore an UPPER BOUND on the rate, not")
        print("  the rate. The two circular channels are correlated, and correlation")
        print("  between numerator and denominator narrows a ratio's distribution.")
        print("\n  This does not weaken the project's argument, it bounds it: an upper")
        print("  bound of 29 % on ordinary rock crossing a CPR threshold is still a")
        print("  reason not to trust the threshold. What changes is that the figure")
        print("  must be LABELLED as a bound everywhere it appears, which")
        print("  verify_all.py now enforces.")
    else:
        print(f"  MEASURED {r_corr:.4f}  >=  THEORY {t_ref:.4f} at N = {n_ref}")
        print(f"  ratio {ratio:.3f}\n")
        print("  The measurement does not falsify the independent-channel model.")
        print("  It cannot confirm it either: the minimum over homogeneous windows")
        print("  is an upper bound on the speckle floor, so a figure at or above")
        print("  the theory is consistent with the theory AND with residual terrain")
        print("  structure. No claim is made from this direction.")

    # ---------------------------------------------- D. the external constraint
    hr("EXTERNAL CHECK — Putrevu et al. 2023 (10.1029/2023JE007745)")
    print("  Our own dispersion is an upper bound and cannot falsify the")
    print("  independent-channel model from below. A published DFSAR measurement")
    print("  can, and one exists.\n")

    # Their Figure 4, Byrgius C interior. Read from the paper, not measured here,
    # and marked as such in the artifact.
    pub_mean, pub_sd = 1.07, 0.17
    pub_rel = pub_sd / pub_mean

    # Their stated SLC spacings. The number of single-look samples averaged into
    # one 25 m output pixel is the product of the two ratios -- an UPPER bound on
    # their look count, because it assumes every sample is independent and that
    # all of them are used.
    # 26 deg is the NADIR (look) angle they print. Ground range spacing is set
    # by INCIDENCE, and on a convex body the two differ:
    #     sin(theta_inc) = ((R + h)/R) sin(eta)
    # The first version used sin(26 deg) directly, got N <= 51.89, and called
    # the difference "the safe way". A LARGER N gives a LOWER floor, which is a
    # HARDER bar for their 0.1589 to sit under -- so 54.88 is the CONSERVATIVE
    # bound and 51.89 was the flattering one. Same confusion as the one that
    # produced the withdrawn Bragg criterion; METHODS section 0 logs them as one
    # instance.
    az_spacing_m, slant_spacing_m, nadir_deg, out_m = 0.55, 9.6, 26.0, 25.0
    # THEIR ORBIT ALTITUDE IS NOT STATED IN THE PAPER, so this uses OUR
    # product's 105,376 m and reports the sensitivity rather than hiding the
    # assumption. Chandrayaan-2's science orbit is nominally 100 km; the two
    # give 55.04 and 54.88 samples, floors 0.1933 and 0.1936. Both are below
    # their measured 0.1589 and both are more conservative than the 51.89 the
    # nadir angle gives, so the conclusion does not depend on the choice.
    R_MOON, H_ORBIT = 1737400.0, 105376.0        # label geometry, section 7.12
    inc_deg = float(np.degrees(np.arcsin(
        ((R_MOON + H_ORBIT) / R_MOON) * np.sin(np.deg2rad(nadir_deg)))))
    ground_range_m = slant_spacing_m / np.sin(np.deg2rad(inc_deg))
    ground_range_nadir_m = slant_spacing_m / np.sin(np.deg2rad(nadir_deg))
    n_alt = (out_m / az_spacing_m) * (out_m / ground_range_nadir_m)
    n_az = out_m / az_spacing_m
    n_rg = out_m / ground_range_m
    n_max = n_az * n_rg
    print(f"  their printed nadir angle {nadir_deg:g} deg -> incidence "
          f"{inc_deg:.4f} deg")
    print(f"  azimuth {az_spacing_m} m; slant range {slant_spacing_m} m at that "
          f"incidence -> ground range {ground_range_m:.4f} m")
    print(f"  into a {out_m:g} m pixel: {n_az:.2f} x {n_rg:.4f} = "
          f"{n_max:.2f} samples, so N <= {n_max:.2f}")
    print(f"  Using the nadir angle directly gives {n_alt:.2f}, a HIGHER floor and")
    print(f"  an EASIER claim, so {n_max:.2f} is the conservative bound and is what")
    print(f"  this leads with. {n_alt:.2f} is reported below as the alternative.")
    _n_100 = (out_m / az_spacing_m) * (out_m / (slant_spacing_m / np.sin(np.arcsin(
        (R_MOON + 100000.0) / R_MOON * np.sin(np.deg2rad(nadir_deg))))))
    print(f"  Their orbit altitude is NOT stated in the paper. This uses ours,")
    print(f"  {H_ORBIT:,.0f} m; at a nominal 100 km the cap would be {_n_100:.2f}")
    print(f"  and the floor {rel_sd_independent(_n_100):.4f}. Both are below their")
    print(f"  measured 0.1589 and both are more conservative than {n_alt:.2f}, so")
    print(f"  the conclusion does not depend on the choice.")
    print()

    # ── THE BOUND, AND WHERE IT COMES FROM ────────────────────────────────
    #
    # Two independent N-look intensities give a ratio with relative variance
    # (2N-1)/(N(N-2)), which tends to 2/N. Correlating numerator and
    # denominator at intensity correlation rho_I narrows it by (1 - rho_I), so
    #
    #     relSD_obs^2 = (1 - rho_I) * relSD_indep^2
    #     rho_I = 1 - (relSD_obs / relSD_indep)^2
    #
    # Substituting the large-N limit relSD_indep^2 = 2/N gives the closed form
    #
    #     rho_I >= 1 - N * relSD_obs^2 / 2
    #
    # BOTH ARE COMPUTED AND BOTH ARE PRINTED. They differ because the exact
    # floor at N ~ 55 is 0.19330 against sqrt(2/N) = 0.19058, a 1.4 % gap that
    # squares into 2.9 % of the bound. The large-N form gives the SMALLER
    # number, so it is the conservative one and it is what is led with; the
    # exact-floor value is printed beside it so neither is unsourced.
    #
    # THE ALTITUDE IS NOT STATED IN THE PAPER. Three are tested, spanning
    # Chandrayaan-2's nominal 100 km, this product's label value, and a 150 km
    # stress case. The BOUND moves with it; the CONCLUSION does not.
    print(f"  their measured relative SD = {pub_sd}/{pub_mean} = {pub_rel:.4f}")
    print(f"  rho_I >= 1 - N * relSD^2 / 2,  relSD^2 = {pub_rel ** 2:.8f},"
          f"  relSD^2/2 = {pub_rel ** 2 / 2:.8f}\n")
    print(f"  {'h (m)':>9}{'incidence':>11}{'N <=':>9}{'floor':>9}{'below?':>9}{'rho_I large-N':>15}{'rho_I exact':>13}")
    constraint = {}
    for h_m, tag in ((100000.0, "nominal"), (H_ORBIT, "our label"),
                     (150000.0, "stress")):
        th = float(np.degrees(np.arcsin(
            ((R_MOON + h_m) / R_MOON) * np.sin(np.deg2rad(nadir_deg)))))
        gr = slant_spacing_m / np.sin(np.deg2rad(th))
        n = (out_m / az_spacing_m) * (out_m / gr)
        floor = rel_sd_independent(n)
        rho_big = 1.0 - n * pub_rel ** 2 / 2.0
        rho_exact = 1.0 - (pub_rel / floor) ** 2
        below = "yes" if pub_rel < floor else "NO"
        print(f"  {h_m:>9,.0f}{th:>11.4f}{n:>9.3f}{floor:>9.4f}{below:>9}"
              f"{rho_big:>15.4f}{rho_exact:>13.4f}   {tag}")
        constraint[f"h={h_m:.0f}"] = {
            "incidence_deg": th, "max_samples": n, "independent_floor": floor,
            "their_rel_sd_below_floor": bool(pub_rel < floor),
            "rho_I_large_N": rho_big, "rho_I_exact_floor": rho_exact,
            # The ground-range spacing PER ALTITUDE. It was emitted once, at our
            # label's altitude, while the row the manuscript leads with is the
            # 100 km one -- so the spacing on disk (20.647 m) belonged to a
            # different row from the rho it sat beside (20.708 m at 100 km).
            "ground_range_spacing_m": float(gr),
            "altitude_m": float(h_m),
            "tag": tag}
    # The nadir-angle version, kept as the flattering alternative.
    floor_alt = rel_sd_independent(n_alt)
    print(f"  {'--':>9}{nadir_deg:>11.4f}{n_alt:>9.3f}{floor_alt:>9.4f}"
          f"{'yes' if pub_rel < floor_alt else 'NO':>9}"
          f"{1.0 - n_alt * pub_rel ** 2 / 2.0:>15.4f}"
          f"{1.0 - (pub_rel / floor_alt) ** 2:>13.4f}   nadir angle used directly")
    constraint["nadir_direct"] = {
        "max_samples": float(n_alt), "independent_floor": floor_alt,
        "their_rel_sd_below_floor": bool(pub_rel < floor_alt),
        "rho_I_large_N": 1.0 - n_alt * pub_rel ** 2 / 2.0,
        "rho_I_exact_floor": 1.0 - (pub_rel / floor_alt) ** 2,
        "tag": "flattering alternative"}

    rho_lead = 1.0 - n_max * pub_rel ** 2 / 2.0
    print(f"\n  THE BOUND MOVES, THE CONCLUSION DOES NOT. Their 0.1589 is below")
    print(f"  the independent-channel floor at every altitude tested, so the two")
    print(f"  channels are correlated in all of them. The BOUND ranges "
          f"{min(c['rho_I_large_N'] for c in constraint.values()):.4f} to "
          f"{max(c['rho_I_large_N'] for c in constraint.values()):.4f}.")
    print(f"  Led with: rho_I >= {rho_lead:.4f} at N = {n_max:.3f}"
          f"  (1 - {n_max:.3f} x {pub_rel ** 2 / 2:.8f} = {rho_lead:.4f}).")

    floor_ref = rel_sd_independent(n_max)
    print(f"\n  Byrgius C interior: CPR {pub_mean} +/- {pub_sd}, "
          f"relative SD {pub_rel:.4f}.")
    print(f"  The independent-channel floor at their own maximum look count is")
    print(f"  {floor_ref:.4f}. THEIR MEASURED DISPERSION IS BELOW THEIR OWN FLOOR.")
    print("  A ratio of two independent intensities cannot be that narrow, so the")
    print("  two circular channels are correlated, with intensity correlation")
    print(f"  |rho|^2 >= {rho_lead:.4f} (large-N form; the exact-floor form gives "
          f"{1.0 - (pub_rel / floor_ref) ** 2:.4f}, and the smaller is reported).\n")
    print("  CONSEQUENCE FOR SECTION 7.7: correlation between numerator and")
    print("  denominator narrows the ratio's distribution, so F(2N,2N) with")
    print("  independent numerator and denominator is CONSERVATIVE, and every")
    print("  false-positive rate computed from it -- 29.16 % included -- is an")
    print("  UPPER BOUND rather than a rate. That conclusion rests on THIS")
    print("  external measurement, not on our own dispersion, which is an upper")
    print("  bound and cannot settle the question from below.\n")
    print("  The paper states NO ENL and NO look count anywhere. Its only")
    print("  statement on the matter is 'averaging several independent single-look")
    print("  coherency matrices' (Sec 3.1), which is why N had to be bounded from")
    print("  the pixel spacings rather than read.")

    OUT.write_text(json.dumps({
        "schema": "cpr_dispersion/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/cpr_dispersion.py",
        "window_px": k, "windows_ranked": int(len(tc)), "windows_selected": top,
        "selection": "lowest coefficient of variation of s0_native (backscatter), "
                     "not of CPR — the selection quantity is independent of the "
                     "statistic being measured",
        "per_window": [
            {"s0_cv": float(cv[order][i]), "cpr_mean": float(c_mean[i]),
             "cpr_sd": float(c_sd[i]), "cpr_rel_sd": float(c_rel[i])}
            for i in range(top)
        ],
        "rel_sd_min_raw": r_min,
        "rel_sd_median_raw": r_med,
        "correlation_correction": {
            "source": "docs/cpr_significance.json :: effective_samples.area_all_lags",
            "correlation_area_px": A,
            "window_pixels": n_px,
            "independent_samples_in_window": n_eff,
            "rho_bar": rho_bar,
            "sd_inflation_factor": infl,
            "sd_relative_sampling_error": float(1.0 / np.sqrt(2.0 * (n_eff - 1.0))),
            "estimator_is_minimum_of": top,
            "bias_direction": ("LOW, twice over — the sampling spread of each window's SD and the minimum taken over windows both select downward. That strengthens a negative conclusion and means the figure is not a precise floor."),
        },
        "rel_sd_min_corrected": r_corr,
        "apparent_looks_if_independent": n_app,
        "theory": {str(n): rel_sd_independent(n) for n, _ in rows},
        "reference_looks": n_ref,
        "theory_at_reference": t_ref,
        "measured_over_theory": ratio,
        "independent_model_overstates_spread": verdict_independent_overstates,
        "is_upper_bound": True,
        "why_upper_bound": ("residual terrain structure inside a window adds "
                            "variance, so the minimum can only be too high; this "
                            "experiment can falsify the independent-channel model "
                            "and cannot confirm it"),
        "enl_source": "docs/enl.json" if enl else "not read",
        "external_check": {
            "source": "Putrevu et al. 2023, 10.1029/2023JE007745",
            "provenance": "READ FROM THE PAPER — not measured by this project",
            "feature": "Byrgius C interior, their Figure 4",
            "cpr_mean": pub_mean, "cpr_sd": pub_sd, "cpr_rel_sd": pub_rel,
            "slc_spacing_m": {"azimuth": az_spacing_m, "slant_range": slant_spacing_m,
                              "nadir_deg": nadir_deg, "output_pixel_m": out_m},
            "ground_range_spacing_m": float(ground_range_m),
            "max_samples_per_output_pixel": float(n_max),
            "their_printed_nadir_deg": nadir_deg,
            "incidence_from_nadir_deg": inc_deg,
            "orbit_altitude_assumed_m": H_ORBIT,
            "orbit_altitude_source": ("NOT stated in the paper; this product's "
                                      "label value is used and the sensitivity "
                                      "is reported"),
            "max_samples_at_100km_altitude": float(_n_100),
            "alternative_using_nadir_directly": float(n_alt),
            "which_is_conservative": ("the LARGER N. A larger N gives a lower floor and therefore a harder bar for their 0.1589 to sit under; using the nadir angle directly gives the smaller N, a higher floor and an easier claim."),
            "constraint": constraint,
            # WHICH ROW IS LED WITH, NAMED RATHER THAN INFERRED. The altitude is
            # not stated in Putrevu et al., so a choice is unavoidable; leaving
            # it implicit meant a reader had to guess which of four rows the
            # headline rho came from. 100 km is the nominal mission altitude and
            # is the conservative of the two candidates (a larger N gives a
            # lower floor and therefore a harder bar for their 0.1589 to clear).
            "led_with": "100 km",
            "led_with_row": "h=100000",
            "led_with_triple": {
                "N": constraint["h=100000"]["max_samples"],
                "independent_floor": constraint["h=100000"]["independent_floor"],
                "rho_I_min": constraint["h=100000"]["rho_I_large_N"],
                "incidence_deg": constraint["h=100000"]["incidence_deg"],
                "ground_range_spacing_m": constraint["h=100000"]["ground_range_spacing_m"],
            },
            "also_reported_row": "h=105376",
            "implied_intensity_correlation_min": float(rho_lead),
            "estimator": ("rho_I >= 1 - N relSD^2 / 2, the large-N form of "
                          "rho_I = 1 - (relSD_obs/relSD_indep)^2. The exact-floor "
                          "form gives a LARGER number, so the large-N one is the "
                          "conservative bound and is what is reported."),
            "bound_range_over_altitudes": [
                float(min(c["rho_I_large_N"] for c in constraint.values())),
                float(max(c["rho_I_large_N"] for c in constraint.values()))],
            "conclusion_holds_at_every_altitude": bool(all(
                c["their_rel_sd_below_floor"] for c in constraint.values())),
            "paper_states_looks": False,
            "paper_only_statement": ("'averaging several independent single-look "
                                     "coherency matrices' (Sec 3.1)"),
            "consequence": ("correlated channels narrow the ratio, so F(2N,2N) with "
                            "independent numerator and denominator is conservative "
                            "and every false-positive rate from it is an upper bound"),
        },
    }, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
