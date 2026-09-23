"""
Measure the equivalent number of looks (ENL) of the DFSAR sri product, and
settle whether its DN are AMPLITUDE or INTENSITY.

WHY THIS EXISTS
---------------
Everything in Phase 8 -- a per-pixel significance test on CPR built from speckle
statistics -- is a function of the look count N. The label declares a NOMINAL N.
The imagery carries an EFFECTIVE one, and the two are not the same number:
Hamming weighting and overlapped azimuth looks both correlate samples, which
costs independent looks. Nobody in the lunar CPR literature reports ENL at all,
so the nominal figure has never been checked against the pixels.

THE SECOND QUESTION, WHICH THE SAME MEASUREMENT ANSWERS
-------------------------------------------------------
Are the DN amplitude or intensity? This propagates: the CPR proxy forms
0.5*(sqrt(a) -+ sqrt(b))^2, which is only sigma_sc/sigma_oc if a and b are
INTENSITIES, and the 0.0042610 ceiling depends on it.

For an N-look INTENSITY, speckle gives  mean^2 / var = N.
For its AMPLITUDE (square-root gamma, Nakagami-m with m = N),

    mean^2 / var = c^2 / (1 - c^2),   c = Gamma(N+0.5) / (Gamma(N) * sqrt(N))

which is ~ 4N - 3/4. At N = 21 that is 21 against 83.3 -- a factor of four
apart, so the two hypotheses cannot be confused. Computing the ratio on DN and
on DN^2 and asking which one lands on the nominal look count settles it from the
data, with the label's own number as the reference.

TEXTURE ONLY EVER BIASES THIS DOWNWARD. Real terrain is not homogeneous, and
any real variation adds to the speckle variance, lowering mean^2/var. So a patch
population has a ceiling, not a centre: the estimate is the MODE of the
per-patch distribution, not its mean. The mean of the distribution is reported
too, and it is the wrong statistic on purpose -- to show the size of the bias.

Usage:
    python -u backend/scripts/measure_enl.py [--patches 16,32,64] [--band L]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import tifffile

for _stream in (sys.stdout, sys.stderr):          # cp1252 mojibake, once, here
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parents[2]
# WHERE THE PRODUCT IS. These are DEFAULTS, not constants: their values are
# exactly what they were when they were pinned, so every existing caller gets
# the same files, and --dir/--stem/--label let the SAME estimator read another
# acquisition.
#
# ONLY THE ADDRESSING IS PARAMETERISED. Nothing below this line changes: not the
# patch geometry, not the mode-versus-mean choice, not the wholly-inside-mask
# rule, not the patch sizes. An estimator adjusted per product measures the
# adjustment and not the product, so the argument that would let it be adjusted
# does not exist.
DEFAULT_DIR = "data/pradan/raw/data/calibrated/20200808"
DEFAULT_STEM = "ch2_sar_{band}_20200808t201154198_d_sri_xx_cp_{ch}_d18.tif"
DEFAULT_LABEL = "ch2_sar_{band}_20200808t201154198_d_sri_xx_cp_xx_d18.xml"


def hr(t: str) -> None:
    print("\n" + "=" * 78 + "\n" + t + "\n" + "=" * 78)


def amplitude_ratio(n: float) -> float:
    """mean^2/var of the AMPLITUDE of an n-look intensity. ~ 4n - 3/4."""
    c = math.exp(math.lgamma(n + 0.5) - math.lgamma(n)) / math.sqrt(n)
    return c * c / (1.0 - c * c)


def looks_from_amplitude_ratio(r: float) -> float:
    """Invert amplitude_ratio: the look count an amplitude ratio implies."""
    if not (r > 0) or not math.isfinite(r):
        return float("nan")
    lo, hi = 1e-3, 1e6
    for _ in range(200):
        mid = math.sqrt(lo * hi)
        if amplitude_ratio(mid) < r:
            lo = mid
        else:
            hi = mid
    return math.sqrt(lo * hi)


def label_looks(band: str, raw: Path, label_tmpl: str) -> dict:
    """The declared look count, read from the label rather than remembered."""
    name = label_tmpl.format(band=band)
    src = (raw / name).read_text(encoding="utf-8", errors="replace")

    def one(tag: str):
        m = re.search(r"<isda:" + tag + r">([^<]+)</isda:" + tag + r">", src)
        return None if m is None else m.group(1).strip()

    rl, al = one("range_looks"), one("azimuth_looks")
    return {"range_looks": int(rl) if rl else None,
            "azimuth_looks": int(al) if al else None,
            "total_looks": (int(rl) * int(al)) if (rl and al) else None,
            "calibration_constant": float(one("calibration_constant") or "nan"),
            "range_window": one("range_window"),
            "range_window_coefficient": float(one("range_window_coefficient") or "nan"),
            "azimuth_window": one("azimuth_window"),
            "azimuth_window_coefficient": float(one("azimuth_window_coefficient") or "nan"),
            "source": name}


def patch_ratios(a: np.ndarray, valid: np.ndarray, p: int) -> np.ndarray:
    """mean^2/var over every p x p patch that is ENTIRELY valid.

    Entirely-valid, not mostly: one zero-fill pixel inside a patch would dominate
    the variance and manufacture a low outlier.
    """
    h, w = (a.shape[0] // p) * p, (a.shape[1] // p) * p
    blk = a[:h, :w].reshape(h // p, p, w // p, p).swapaxes(1, 2).reshape(-1, p * p)
    vb = valid[:h, :w].reshape(h // p, p, w // p, p).swapaxes(1, 2).reshape(-1, p * p)
    blk = blk[vb.all(axis=1)].astype(np.float64)
    if blk.size == 0:
        return np.empty(0)
    m = blk.mean(axis=1)
    v = blk.var(axis=1, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.where(v > 0, m * m / v, np.nan)
    return r[np.isfinite(r)]


def mode_of(r: np.ndarray, bins: int = 120) -> float:
    """Mode in log space: the homogeneous population, not the textured tail."""
    r = r[r > 0]
    if r.size < 10:
        return float("nan")
    hist, edges = np.histogram(np.log(r), bins=bins)
    i = int(hist.argmax())
    return float(np.exp(0.5 * (edges[i] + edges[i + 1])))


def theory_skew(n: float, amplitude: bool) -> float:
    """Skewness of an n-look intensity, or of its amplitude. Scale-free.

    A SECOND MOMENT, INDEPENDENT OF THE VARIANCE RATIO. If DN are intensity the
    variance ratio and the skewness must BOTH land on the same n; agreement on
    two moments is much harder to get by accident than agreement on one.
    """
    if not amplitude:
        return 2.0 / math.sqrt(n)
    g = lambda k: math.exp(math.lgamma(n + k / 2.0) - math.lgamma(n))
    m1, m2, m3 = g(1), g(2), g(3)
    var = m2 - m1 * m1
    return (m3 - 3.0 * m1 * m2 + 2.0 * m1 ** 3) / var ** 1.5


def patch_skews(a: np.ndarray, valid: np.ndarray, p: int) -> np.ndarray:
    """Per-patch skewness, over patches that are entirely valid."""
    h, w = (a.shape[0] // p) * p, (a.shape[1] // p) * p
    blk = a[:h, :w].reshape(h // p, p, w // p, p).swapaxes(1, 2).reshape(-1, p * p)
    vb = valid[:h, :w].reshape(h // p, p, w // p, p).swapaxes(1, 2).reshape(-1, p * p)
    blk = blk[vb.all(axis=1)].astype(np.float64)
    if blk.size == 0:
        return np.empty(0)
    d = blk - blk.mean(axis=1, keepdims=True)
    sd = d.std(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        s = np.where(sd > 0, (d ** 3).mean(axis=1) / sd ** 3, np.nan)
    return s[np.isfinite(s)]


def lag_correlation(a: np.ndarray, valid: np.ndarray, p: int, max_lag: int = 3) -> dict:
    """Correlation of DN with itself at small lags, after removing the patch mean.

    Phase 8 needs this: a per-pixel CFAR test assumes it knows how many
    INDEPENDENT samples a neighbourhood holds, and Hamming weighting plus
    overlapped azimuth looks correlate adjacent pixels. Subtracting the patch
    mean removes the DC terrain level; sub-patch terrain structure survives, so
    these are an UPPER BOUND on the speckle correlation, not a clean estimate.
    """
    h, w = (a.shape[0] // p) * p, (a.shape[1] // p) * p
    out = {}
    for axis, name in ((0, "azimuth_lines"), (1, "range_samples")):
        sh = [h // p, p, w // p, p]
        blk = a[:h, :w].reshape(sh).swapaxes(1, 2)
        vb = valid[:h, :w].reshape(sh).swapaxes(1, 2)
        keep = vb.reshape(-1, p * p).all(axis=1)
        b = blk.reshape(-1, p, p)[keep].astype(np.float64)
        if b.size == 0:
            continue
        b = b - b.reshape(b.shape[0], -1).mean(axis=1)[:, None, None]
        ax = 1 if axis == 0 else 2
        r = []
        for lag in range(1, max_lag + 1):
            x = np.take(b, range(0, b.shape[ax] - lag), axis=ax)
            y = np.take(b, range(lag, b.shape[ax]), axis=ax)
            num = (x * y).mean()
            den = math.sqrt(float((x * x).mean()) * float((y * y).mean()))
            r.append(float(num / den) if den > 0 else float("nan"))
        out[name] = r
    return out


def log_cumulant_looks(i: np.ndarray, valid: np.ndarray, p: int) -> np.ndarray:
    """Per-patch log-cumulant ENL (Anfinsen, Doulgeris and Eltoft, IEEE TGRS
    47(11), 2009): for single-channel intensity the second sample
    log-cumulant kappa_2 = Var(ln I) equals psi_1(L) for an L-look gamma
    intensity, so L = psi_1^-1(kappa_2). Over every p x p patch ENTIRELY
    inside `valid` (the same patches patch_ratios uses), Var with ddof = 1.
    Texture adds variance to ln I, so it biases L low, as it does the moment
    ratio; common scale factors (K, G, sin theta) cancel in Var(ln I)."""
    from scipy.special import polygamma
    h, w = (i.shape[0] // p) * p, (i.shape[1] // p) * p
    blk = i[:h, :w].reshape(h // p, p, w // p, p).swapaxes(1, 2).reshape(-1, p * p)
    vb = valid[:h, :w].reshape(h // p, p, w // p, p).swapaxes(1, 2).reshape(-1, p * p)
    blk = blk[vb.all(axis=1)].astype(np.float64)
    k2 = np.log(blk).var(axis=1, ddof=1)
    ng = np.exp(np.linspace(np.log(0.05), np.log(1e5), 6000))
    vg = polygamma(1, ng)
    return np.interp(k2, vg[::-1], ng[::-1])


def describe(name: str, r: np.ndarray) -> dict:
    q = np.percentile(r, [5, 25, 50, 75, 95]) if r.size else [float("nan")] * 5
    return {"statistic": name, "n_patches": int(r.size), "mode": mode_of(r),
            "mean": float(r.mean()) if r.size else float("nan"),
            "p5": float(q[0]), "p25": float(q[1]), "median": float(q[2]),
            "p75": float(q[3]), "p95": float(q[4])}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--band", default="L", choices=["L", "S"])
    ap.add_argument("--patches", default="16,32,64")
    ap.add_argument("--out", default="docs/enl.json")
    ap.add_argument("--log-cumulant-only", action="store_true",
                    help=("v17a P6: compute the log-cumulant ENL on the headline patches "
                          "(16 x 16, the boxcar-eroded both-channel mask) and merge it into "
                          "the artifact under log_cumulant_enl; nothing else is rewritten"))
    ap.add_argument("--dir", default=DEFAULT_DIR,
                    help="directory holding the sri rasters and their label, "
                         "relative to the repo root or absolute")
    ap.add_argument("--stem", default=DEFAULT_STEM,
                    help="raster filename template with {band} and {ch}")
    ap.add_argument("--label", default=DEFAULT_LABEL,
                    help="label filename template with {band}")
    args = ap.parse_args()
    band = {"L": "ncxl", "S": "ncxs"}[args.band]
    raw = Path(args.dir)
    if not raw.is_absolute():
        raw = ROOT / args.dir
    stem_t, label_t = args.stem, args.label
    print(f"  product directory       {raw}")

    hr("A. THE DECLARED LOOK COUNT -- " + args.band + "-band sri, read from the label")
    lab = label_looks(band, raw, label_t)
    print("  source                  " + str(lab["source"]))
    print("  range_looks             " + str(lab["range_looks"]))
    print("  azimuth_looks           " + str(lab["azimuth_looks"]))
    print("  TOTAL NOMINAL LOOKS     " + str(lab["total_looks"]))
    print(f"  range window            {lab['range_window']} "
          f"(coefficient {lab['range_window_coefficient']:g})")
    print(f"  azimuth window          {lab['azimuth_window']} "
          f"(coefficient {lab['azimuth_window_coefficient']:g})")
    print(f"  calibration_constant    {lab['calibration_constant']:g}")
    n_nom = float(lab["total_looks"])
    print(f"\n  For {n_nom:g} looks, pure speckle predicts")
    print(f"    mean^2/var on INTENSITY   {n_nom:8.2f}")
    print(f"    mean^2/var on AMPLITUDE   {amplitude_ratio(n_nom):8.2f}")
    print("  A factor of ~4 apart, so the two cannot be mistaken for each other.")

    lh = tifffile.imread(str(raw / stem_t.format(band=band, ch="lh"))).astype(np.float64)
    lv = tifffile.imread(str(raw / stem_t.format(band=band, ch="lv"))).astype(np.float64)
    valid = (lh > 0) & (lv > 0)
    print(f"\n  raster {lh.shape[0]} x {lh.shape[1]}, declared UnsignedLSB2 (uint16 DN)")
    print(f"  DN > 0 in both channels: {int(valid.sum()):,} px "
          f"({valid.mean() * 100:.2f} % of the raster)")
    print(f"  LH DN over that mask: min {lh[valid].min():.0f}  median "
          f"{np.median(lh[valid]):.0f}  max {lh[valid].max():.0f}")

    if args.log_cumulant_only:
        from scipy.ndimage import binary_erosion
        p0 = int(args.patches.split(",")[0])
        inner = binary_erosion(valid, np.ones((5, 5), dtype=bool))
        out_p = ROOT / args.out
        doc = json.loads(out_p.read_text(encoding="utf-8"))
        lc = {"method": ("Anfinsen et al. 2009 log-cumulant: L = psi_1^-1(Var(ln I)) per patch, "
                         "I = DN^2; the same 16 x 16 patches and mask as boxcar_gain.enl_raw (both "
                         "channels DN > 0, eroded by the 5 x 5 boxcar half-width)"),
              "patch_px": p0, "mask_pixels": int(inner.sum())}
        for ch_name, dn in (("LH", lh), ("LV", lv)):
            lk = log_cumulant_looks(dn * dn, inner, p0)
            lc[ch_name] = {"patches": int(lk.size), "median": float(np.median(lk)),
                           "iqr": [float(np.percentile(lk, 25)), float(np.percentile(lk, 75))],
                           "mode": mode_of(lk),
                           "moment_mode_for_comparison": doc["boxcar_gain"][ch_name]["enl_raw"]}
            print(f"  {ch_name}: log-cumulant ENL median {lc[ch_name]['median']:.2f} "
                  f"(IQR {lc[ch_name]['iqr'][0]:.2f}-{lc[ch_name]['iqr'][1]:.2f}, mode "
                  f"{lc[ch_name]['mode']:.2f}) on {lk.size:,} patches; moment mode "
                  f"{doc['boxcar_gain'][ch_name]['enl_raw']:.2f}")
        doc["log_cumulant_enl"] = lc
        out_p.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        print("merged log_cumulant_enl into " + args.out)
        return 0

    results = {"label": lab, "patch_sizes": {}}
    for p in [int(x) for x in args.patches.split(",")]:
        hr("B/C. PATCH STATISTICS -- " + f"{p} x {p} patches, fully inside the DN mask")
        blockout = {}
        for ch_name, dn in (("LH", lh), ("LV", lv)):
            r_dn = patch_ratios(dn, valid, p)
            r_sq = patch_ratios(dn * dn, valid, p)
            if r_dn.size == 0:
                print("  " + ch_name + ": no fully-valid patch at this size")
                continue
            d_dn = describe("mean^2/var on DN", r_dn)
            d_sq = describe("mean^2/var on DN^2", r_sq)
            a_looks = looks_from_amplitude_ratio(d_dn["mode"])
            blockout[ch_name] = {
                "on_DN": d_dn, "on_DN_squared": d_sq,
                "implied_looks": {
                    "if_DN_are_amplitude__from_DN_squared": d_sq["mode"],
                    "if_DN_are_amplitude__from_DN_as_amplitude": a_looks,
                    "if_DN_are_intensity__from_DN": d_dn["mode"],
                    "declared": n_nom}}
            print(f"\n  {ch_name}  --  {d_dn['n_patches']:,} fully-valid patches")
            print(f"  {'quantity':>22}  {'mode':>8}  {'p5':>8}  {'median':>8}  "
                  f"{'p95':>8}  {'mean':>8}")
            for d in (d_dn, d_sq):
                print(f"  {d['statistic']:>22}  {d['mode']:8.2f}  {d['p5']:8.2f}  "
                      f"{d['median']:8.2f}  {d['p95']:8.2f}  {d['mean']:8.2f}")
            print(f"\n  {'hypothesis':>34}  {'intensity is':>16}  {'implied looks':>13}")
            print(f"  {'DN are AMPLITUDE':>34}  {'DN^2':>16}  {d_sq['mode']:13.2f}")
            print(f"  {'(same, cross-checked on DN)':>34}  {'DN^2':>16}  {a_looks:13.2f}")
            print(f"  {'DN are INTENSITY':>34}  {'DN':>16}  {d_dn['mode']:13.2f}")
            print(f"  {'declared':>34}  {'':>16}  {n_nom:13.2f}")
        results["patch_sizes"][str(p)] = blockout

    # ---- C: amplitude or intensity, settled against the instrument's own floor
    hr("C. ARE THE DN AMPLITUDE OR INTENSITY? -- decided against the NOISE FLOOR")
    print("  The variance ratio ALONE CANNOT DECIDE THIS, and it is worth being")
    print("  explicit about why: mean^2/var of X^k is ~ (1/k^2) times that of X, so")
    print("  every power of DN produces a self-consistent story with its own look")
    print("  count. Reading 21 off one of them only begs the question.")
    print()
    print("  The label settles it. sigma0 = DN^p * sin(theta) / 10^(K/10), and the")
    print("  two candidate exponents put the scene on opposite sides of the")
    print("  instrument's own noise-equivalent sigma0, which the label also carries.")
    k_db = lab["calibration_constant"]
    k_lin = 10.0 ** (k_db / 10.0)
    inc_deg = float(re.search(r"<isda:incidence_angle unit=\"deg\">([^<]+)<",
                              (raw / label_t.format(band=band)).read_text(
                                  encoding="utf-8", errors="replace")).group(1))
    nesz = {c: float(v) for c, v in re.findall(
        r"<isda:polarization>(\w+)</isda:polarization>.*?<isda:nes0_coeff_0>([^<]+)<",
        (raw / label_t.format(band=band)).read_text(encoding="utf-8", errors="replace"),
        flags=re.S)}
    dn_med = float(np.median(lh[valid]))
    sin_t = math.sin(math.radians(inc_deg))
    print(f"\n  K = {k_db:g} dB    incidence {inc_deg:.2f} deg    median LH DN {dn_med:.0f}")
    for ch, n0 in nesz.items():
        print(f"  NESZ (nes0_coeff_0, {ch}) {n0:.4g}  =  {10 * math.log10(n0):+.1f} dB")
    n0 = nesz.get("LH", float("nan"))
    print(f"\n  {'hypothesis':>20}  {'exponent':>8}  {'median sigma0':>14}  "
          f"{'vs NESZ':>10}")
    verdict = None
    for name, p_exp in (("DN are AMPLITUDE", 2), ("DN are INTENSITY", 1)):
        s0 = dn_med ** p_exp * sin_t / k_lin
        rel = 10 * math.log10(s0 / n0)
        print(f"  {name:>20}  {'DN^' + str(p_exp):>8}  {10 * math.log10(s0):>+10.1f} dB  "
              f"{rel:>+7.1f} dB")
        if rel > 0 and verdict is None:
            verdict = name
    print("\n  A measured intensity that contains the receiver's own noise cannot")
    print("  sit BELOW that noise floor, and the label declares no noise")
    print("  subtraction or offset. That supports one exponent over the other;")
    print("  it is not a proof, since the label declares no unit or convention.")
    print(f"\n  VERDICT: {verdict}. sigma0 = DN^2 * sin(theta) / 10^(K/10),")
    print("  which is what backend/scripts/process_real_sar_pipeline.py already")
    print("  computes. The CPR proxy's sqrt() therefore acts on sigma0 (an")
    print("  INTENSITY), recovering a field amplitude, and is correctly formed.")
    results["amplitude_vs_intensity"] = {
        "verdict": verdict, "calibration_constant_db": k_db,
        "incidence_deg": inc_deg, "median_DN_LH": dn_med, "nesz_linear": nesz,
        "sigma0_if_amplitude_db": 10 * math.log10(dn_med ** 2 * sin_t / k_lin),
        "sigma0_if_intensity_db": 10 * math.log10(dn_med * sin_t / k_lin)}
    n_eff_source = "on_DN_squared"

    # ---- cross-check 1: a second moment -------------------------------------
    p0 = int(args.patches.split(",")[0])
    hr(f"CROSS-CHECK 1 -- SKEWNESS at {p0} x {p0}, a moment the ratio test does not use")
    print(f"  theory at {n_nom:g} looks:  intensity {theory_skew(n_nom, False):+.4f}   "
          f"amplitude {theory_skew(n_nom, True):+.4f}")
    skew = {}
    for ch_name, dn in (("LH", lh), ("LV", lv)):
        s_dn = patch_skews(dn, valid, p0)
        s_sq = patch_skews(dn * dn, valid, p0)
        skew[ch_name] = {"median_skew_of_DN": float(np.median(s_dn)),
                         "median_skew_of_DN_squared": float(np.median(s_sq))}
        print(f"  {ch_name}  median skew of DN    {np.median(s_dn):+.4f}"
              f"   of DN^2 {np.median(s_sq):+.4f}")
    results["skewness"] = {
        "patch": p0, "theory_intensity": theory_skew(n_nom, False),
        "theory_amplitude": theory_skew(n_nom, True), "measured": skew}

    # ---- cross-check 2: are neighbouring pixels independent? ----------------
    hr("CROSS-CHECK 2 -- PIXEL-TO-PIXEL CORRELATION (Phase 8 needs this)")
    corr = {ch: lag_correlation(dn, valid, p0) for ch, dn in (("LH", lh), ("LV", lv))}
    for ch_name, c in corr.items():
        for axis, rs in c.items():
            print(f"  {ch_name}  {axis:>14}  " +
                  "  ".join(f"lag{i + 1} {v:+.3f}" for i, v in enumerate(rs)))
    results["lag_correlation"] = corr

    # ---- what the pipeline's 5x5 boxcar actually buys ------------------------
    hr("D. EFFECTIVE LOOKS AFTER THE 5x5 BOXCAR -- the number Phase 8 must use")
    print("  CPR and DOP are not formed on raw pixels. process_real_sar_pipeline.py")
    print("  applies a 5x5 boxcar to sigma0 first, so the significance test acts on")
    print("  SMOOTHED intensity. If pixels were independent the boxcar would supply")
    print("  25x the looks. They are not independent -- see the lag correlations")
    print("  above -- so the real gain has to be measured, not assumed.")
    from scipy.ndimage import uniform_filter, binary_erosion
    inner = binary_erosion(valid, np.ones((5, 5), dtype=bool))
    print(f"\n  valid mask eroded by the boxcar half-width: {int(valid.sum()):,} -> "
          f"{int(inner.sum()):,} px (so no window reaches a zero-fill pixel)")
    print(f"\n  {'channel':>8}  {'ENL raw':>9}  {'ENL 5x5':>9}  {'gain':>7}  "
          f"{'if independent':>15}")
    boxg = {}
    for ch_name, dn in (("LH", lh), ("LV", lv)):
        i_raw = dn * dn                       # sigma0 up to a constant factor
        r_raw = mode_of(patch_ratios(i_raw, inner, p0))
        r_box = mode_of(patch_ratios(uniform_filter(i_raw, size=5), inner, p0))
        boxg[ch_name] = {"enl_raw": r_raw, "enl_boxcar5": r_box,
                         "gain": r_box / r_raw if r_raw else float("nan")}
        print(f"  {ch_name:>8}  {r_raw:9.2f}  {r_box:9.2f}  {r_box / r_raw:6.2f}x  "
              f"{'25x':>15}")
    results["boxcar_gain"] = boxg
    print("\n  The shortfall against 25x is the cost of correlated neighbours. A")
    print("  CFAR test that assumed 25x would understate its own variance and")
    print("  manufacture detections.")

    out = ROOT / args.out
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("\nwrote " + args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
