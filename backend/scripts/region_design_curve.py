"""
region_design_curve.py -- how many looks, cells and pixels a REGION-level test
of the joint criterion needs. (v17a referee report, P1; simulation only)

    python backend/scripts/region_design_curve.py [--workers 8]

THE TEST
--------
The region-level test is the single-cell intersection-union test (IUT) of
decision_rule.py applied to a region's POOLED Stokes vector: reject CPR <= 1
when R > F^-1_0.95(2N, 2N) and reject DOP >= 0.13 when the sample DOP is below
q05(N), its 5 % quantile at population DOP 0.13; select when both reject.

(a) POOLING. K independent cells of N looks over one population pool to a
    complex Wishart with K N degrees of freedom (a sum of independent Wisharts
    with one covariance), so the region test IS the single-cell IUT at
    N_eff = K N. Checked by simulation at K = 4 and 25, N = 39.4: pooled
    Bartlett draws against single draws at K N, on R and m_hat quantiles and
    on the IUT's rejection rate. Then with CORRELATED cells: L equal-weight
    looks of exactly stationary AR(1) complex fields at the complex product's
    SC / OC lag-one correlations (complex_grid_correlation.json), 5 x 5 boxcar,
    L chosen as in f2_maximum.py v3 (L = 10, boxcar'd ENL 38.0); regions are
    contiguous 2 x 2 and 5 x 5 blocks of cells. The N_eff they match is read
    three ways: from Var(ln R) (the log-ratio estimator), from the mean sample
    DOP at DOP 0 (E m_hat = B(2, N-1)/B(3/2, N-1)), and from the IUT rate at a
    band alternative.
(b) DESIGN CURVE. The IUT's power, by exact Bartlett sampling of the complex
    Wishart (a11^2 ~ Gamma(N), a22^2 ~ Gamma(N-1), a21 ~ CN(0, 1); valid for
    real N), and the Neyman-Pearson bound of np_power_bound.py (exact), at
    N_eff in {254, 400, 600, 1000, 1500, 2500, 4000, 6000, 10000}, for CPR 1.05,
    1.1, 1.2, 1.25 at the minimum admissible DOP and CPR 1.1, 1.2 at DOP =
    (minimum + 0.13)/2. q05(N) from 10^6 Bartlett draws at CPR 1.00, DOP 0.13
    (the law of m_hat depends on the population only through its DOP).
(c) The N_eff at which each reaches 50, 80 and 90 % power, interpolated on
    log N, with the grid bracket.
(d) In independent cells of 39.4 looks (K = N_eff / 39.4) and complex-product
    pixels at the correlation area 99.6 px; against crater F2.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.ndimage import uniform_filter
from scipy.stats import f as Fdist

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402
import np_power_bound as NPB  # noqa: E402
import dop_sampling_bias as D  # noqa: E402
import enl_logratio as L  # noqa: E402
import f2_maximum as F2  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "region_design_curve.json"
GRID_JSON = BASE_DIR / "docs" / "complex_grid_correlation.json"
F2P_JSON = BASE_DIR / "docs" / "f2_complex_product.json"
SEED = 20261008
ALPHA = 0.05
N_CELL = 39.4
AREA_PX = 99.6
N_GRID = (254, 400, 600, 1000, 1500, 2500, 4000, 6000, 10000)
TRIALS = 200_000
Q_TRIALS = 1_000_000
POOL_TRIALS = 200_000
LEVELS = (0.5, 0.8, 0.9)
CORR_LOOKS = 10
CORR_FIELD = (256, 256)
CORR_FIELDS = 24


def q_of(cpr):
    return (cpr - 1.0) / (cpr + 1.0)


def alternatives():
    out = []
    for c in (1.05, 1.1, 1.2, 1.25):
        out.append((f"CPR {c} DOP min", c, abs(q_of(c))))
    for c in (1.1, 1.2):
        dmin = abs(q_of(c))
        out.append((f"CPR {c} DOP mid", c, 0.5 * (dmin + 0.13)))
    return out


NULLS = [("CPR 1.00 DOP 0", 1.0, 0.0), ("CPR 1.00 DOP 0.065", 1.0, 0.065),
         ("CPR 1.00 DOP 0.13", 1.0, 0.13), ("CPR 1.1 DOP 0.13", 1.1, 0.13),
         ("CPR 1.2 DOP 0.13", 1.2, 0.13), ("CPR 1.2989 DOP 0.13", 1.13 / 0.87, 0.13)]


def chol_sigma(cpr, dop):
    S = NPB.sigma([cpr], [NPB.gamma_c(dop, cpr)], [0.0])[0]
    return np.linalg.cholesky(S)


def bartlett(rng, n, trials, chol):
    """(S11, S22, S12) of S = W / n, W ~ CW(n, Sigma), by Bartlett (real n)."""
    a11 = np.sqrt(rng.gamma(n, 1.0, trials))
    a22 = np.sqrt(rng.gamma(n - 1.0, 1.0, trials))
    a21 = (rng.standard_normal(trials) + 1j * rng.standard_normal(trials)) / np.sqrt(2.0)
    # W = L A A^H L^H, A = [[a11, 0], [a21, a22]]
    m11, m21, m22 = a11 * a11, a21 * a11, np.abs(a21) ** 2 + a22 * a22
    l11, l21, l22 = chol[0, 0], chol[1, 0], chol[1, 1]
    w11 = (l11.real ** 2) * m11
    w12 = l11 * (np.conj(l21) * m11 + l22 * np.conj(m21))          # (L M L^H)_12
    w22 = np.abs(l21) ** 2 * m11 + 2 * (np.conj(l21) * l22 * m21).real + (l22.real ** 2) * m22
    return w11 / n, w22 / n, w12 / n


def stats(s11, s22, s12):
    r = s11 / s22
    m = np.sqrt((s11 - s22) ** 2 + 4 * np.abs(s12) ** 2) / (s11 + s22)
    return r, m


def crit(n):
    return float(Fdist.ppf(1 - ALPHA, 2 * n, 2 * n))


def rate(x):
    x = np.asarray(x, dtype=bool)
    p = float(x.mean())
    return {"percent": 100 * p, "mc_se_percent": 100 * float(np.sqrt(p * (1 - p) / x.size)),
            "trials": int(x.size)}


def check_bartlett(rng) -> dict:
    """Bartlett against the look sum of dop_sampling_bias.simulate at N = 14."""
    out = []
    for cpr, dop in ((1.0, 0.0), (1.2, abs(q_of(1.2))), (1.0, 0.13)):
        g = D.gamma_c_for(dop, cpr)
        r0, m0 = D.simulate(rng, 14, 100_000, cpr, g)
        r1, m1 = stats(*bartlett(rng, 14.0, 100_000, chol_sigma(cpr, dop)))
        qs = (0.05, 0.5, 0.95)
        out.append({"cpr": cpr, "dop": dop,
                    "R_quantiles_looksum": np.quantile(r0, qs).tolist(),
                    "R_quantiles_bartlett": np.quantile(r1, qs).tolist(),
                    "m_quantiles_looksum": np.quantile(m0, qs).tolist(),
                    "m_quantiles_bartlett": np.quantile(m1, qs).tolist()})
    worst = max(max(abs(a - b) / b for a, b in zip(o["R_quantiles_looksum"], o["R_quantiles_bartlett"]))
                for o in out)
    return {"rows": out, "max_relative_quantile_gap_R": worst, "N": 14, "trials": 100_000}


def q05(rng, n) -> float:
    _, m = stats(*bartlett(rng, float(n), Q_TRIALS, chol_sigma(1.0, 0.13)))
    return float(np.quantile(m, ALPHA))


def iut_rate(rng, n, cpr, dop, qn, trials=TRIALS):
    """The IUT's rejection rate: the plain Monte Carlo frequency, and, where
    one component's probability is known exactly, the conditioned estimate
    P(A) P(B | A) with P(A) exact and P(B | A) simulated.

    Exactly known: at gamma_c = 0 (CPR 1.00 DOP 0, and every alternative at
    its minimum DOP) R / CPR ~ F(2N, 2N), so P(R > crit) = F.sf(crit / CPR);
    at population DOP 0.13, P(m_hat < q05) = 0.05 by the construction of q05
    (to the quantile's own Monte Carlo error, carried into the SE). The
    conditioned estimate removes the component's sampling noise, which is the
    whole of the noise where the IUT sits on a 5 % boundary or on the NP bound.
    Both are reported; the gates read the conditioned one where it exists."""
    r, m = stats(*bartlett(rng, float(n), trials, chol_sigma(cpr, dop)))
    a, b = r > crit(n), m < qn
    out = rate(a & b)
    c = crit(n)
    if NPB.gamma_c(dop, cpr) == 0.0:
        pa = float(Fdist.sf(c / cpr, 2 * n, 2 * n))
        k = int(a.sum())
        pb = float(b[a].mean()) if k else 0.0
        se = pa * np.sqrt(pb * (1 - pb) / max(k, 1))
        out["conditioned"] = {"percent": 100 * pa * pb, "mc_se_percent": 100 * se,
                              "exact_component": "P(R > crit) = F.sf(crit / CPR, 2N, 2N)",
                              "exact_component_percent": 100 * pa, "conditioning_draws": k}
    elif abs(dop - 0.13) < 1e-12:
        pb = ALPHA
        k = int(b.sum())
        pa = float(a[b].mean()) if k else 0.0
        q_se = np.sqrt(ALPHA * (1 - ALPHA) / Q_TRIALS)
        se = np.hypot(pb * np.sqrt(pa * (1 - pa) / max(k, 1)), pa * q_se)
        out["conditioned"] = {"percent": 100 * pb * pa, "mc_se_percent": 100 * se,
                              "exact_component": "P(m_hat < q05) = 0.05 by construction of q05",
                              "exact_component_percent": 100 * pb, "conditioning_draws": k}
    return out


def best(x):
    """The conditioned estimate where it exists, else the plain one."""
    return x.get("conditioned", x)


# ------------------------------------------------------------------ (a) pooling
def pooling_check(rng, qtab) -> dict:
    rows = []
    pops = [("null CPR 1.00 DOP 0", 1.0, 0.0), ("band CPR 1.2 DOP min", 1.2, abs(q_of(1.2))),
            ("band CPR 1.1 DOP mid", 1.1, 0.5 * (abs(q_of(1.1)) + 0.13))]
    for K in (4, 25):
        neff = K * N_CELL
        qn = qtab(neff)
        for lab, cpr, dop in pops:
            ch = chol_sigma(cpr, dop)
            s11 = np.zeros(POOL_TRIALS); s22 = np.zeros(POOL_TRIALS)
            s12 = np.zeros(POOL_TRIALS, dtype=complex)
            for _ in range(K):
                a, b, c = bartlett(rng, N_CELL, POOL_TRIALS, ch)
                s11 += a; s22 += b; s12 += c
            rp, mp = stats(s11 / K, s22 / K, s12 / K)
            rs, ms = stats(*bartlett(rng, neff, POOL_TRIALS, ch))
            qs = (0.05, 0.5, 0.95)
            ip, is_ = rate((rp > crit(neff)) & (mp < qn)), rate((rs > crit(neff)) & (ms < qn))
            z = (ip["percent"] - is_["percent"]) / max(np.hypot(ip["mc_se_percent"], is_["mc_se_percent"]), 1e-9)
            rows.append({"K": K, "N": N_CELL, "N_eff": neff, "population": lab,
                         "pooled": {"R_q": np.quantile(rp, qs).tolist(), "m_q": np.quantile(mp, qs).tolist(),
                                    "iut": ip},
                         "single_at_KN": {"R_q": np.quantile(rs, qs).tolist(), "m_q": np.quantile(ms, qs).tolist(),
                                          "iut": is_},
                         "iut_z": float(z)})
    ok = all(abs(r["iut_z"]) < 3 for r in rows)
    return {"rows": rows, "trials": POOL_TRIALS, "all_within_3se": ok}


def correlated_regions(rng, qtab) -> dict:
    """Correlated cells: stationary AR(1) complex fields at the complex
    product's SC / OC lags, CORR_LOOKS looks, 5 x 5 boxcar, pooled over
    contiguous K-cell blocks."""
    gc = json.loads(GRID_JSON.read_text(encoding="utf-8"))["lag_correlation_before_boxcar"]
    rsc = (np.sqrt(gc["SC"]["azimuth_lines"][0]), np.sqrt(gc["SC"]["range_samples"][0]))
    roc = (np.sqrt(gc["OC"]["azimuth_lines"][0]), np.sqrt(gc["OC"]["range_samples"][0]))
    out = {"model": ("CORR_LOOKS equal-weight looks per channel of exactly stationary separable "
                     "AR(1) complex fields (f2_maximum.ar1_stationary) at the complex product's SC and "
                     "OC lag-one field correlations; SC = sqrt(a)(g w_OC + sqrt(1-g^2) w_SC); 5 x 5 "
                     "boxcar on SC, OC and the cross product; regions = contiguous blocks of cells, "
                     "pooled by averaging the boxcar'd covariance"),
           "looks_per_channel": CORR_LOOKS, "field": list(CORR_FIELD), "fields": CORR_FIELDS,
           "lags_intensity": {"SC": [gc["SC"]["azimuth_lines"][0], gc["SC"]["range_samples"][0]],
                              "OC": [gc["OC"]["azimuth_lines"][0], gc["OC"]["range_samples"][0]]},
           "by_population": {}}
    pops = [("null CPR 1.00 DOP 0", 1.0, 0.0), ("band CPR 1.2 DOP min", 1.2, abs(q_of(1.2)))]
    H, W = CORR_FIELD
    for lab, cpr, dop in pops:
        g = NPB.gamma_c(dop, cpr)
        a, b = cpr / (1 + cpr), 1 / (1 + cpr)
        blocks = {1: [], 4: [], 25: [], 100: [], 400: [], 1600: []}
        for _ in range(CORR_FIELDS):
            sc = np.zeros((H, W)); oc = np.zeros((H, W)); x = np.zeros((H, W), dtype=complex)
            for _l in range(CORR_LOOKS):
                wo = F2.ar1_stationary(rng, (H, W), *roc, 1)[0]
                ws = F2.ar1_stationary(rng, (H, W), *rsc, 1)[0]
                zo = np.sqrt(b) * wo
                zs = np.sqrt(a) * (g * wo + np.sqrt(1 - g * g) * ws)
                sc += np.abs(zs) ** 2; oc += np.abs(zo) ** 2; x += zs * np.conj(zo)
            sc, oc, x = sc / CORR_LOOKS, oc / CORR_LOOKS, x / CORR_LOOKS
            bs = uniform_filter(sc, 5, mode="reflect")[4:-4, 4:-4]
            bo = uniform_filter(oc, 5, mode="reflect")[4:-4, 4:-4]
            bx = (uniform_filter(x.real, 5, mode="reflect") + 1j * uniform_filter(x.imag, 5, mode="reflect"))[4:-4, 4:-4]
            for k, side in ((1, 1), (4, 2), (25, 5), (100, 10), (400, 20), (1600, 40)):
                hh, ww = (bs.shape[0] // side) * side, (bs.shape[1] // side) * side
                def pool(f):
                    return f[:hh, :ww].reshape(hh // side, side, ww // side, side).mean(axis=(1, 3)).ravel()
                blocks[k].append((pool(bs), pool(bo), pool(bx)))
        res = {}
        for k, lst in blocks.items():
            s11 = np.concatenate([t[0] for t in lst]); s22 = np.concatenate([t[1] for t in lst])
            s12 = np.concatenate([t[2] for t in lst])
            r, m = stats(s11, s22, s12)
            n_lr = float(L.n_from_var(np.var(np.log(r), ddof=1)))
            row = {"regions": int(r.size), "N_eff_log_ratio": n_lr}
            if dop == 0.0:
                try:
                    row["N_eff_mean_dop"] = D.n_where_mean_dop_is(float(np.mean(m)))
                except ValueError:
                    row["N_eff_mean_dop"] = None
            else:
                n_iut = row["N_eff_log_ratio"]
                ir = rate((r > crit(n_iut)) & (m < qtab(n_iut)))
                row["iut_at_N_eff_log_ratio"] = ir
            res[str(k)] = row
        out["by_population"][lab] = res
    n1 = out["by_population"]["null CPR 1.00 DOP 0"]["1"]["N_eff_log_ratio"]
    for k in ("4", "25", "100", "400", "1600"):
        r = out["by_population"]["null CPR 1.00 DOP 0"][k]
        r["ratio_to_K_times_single"] = r["N_eff_log_ratio"] / (int(k) * n1)
        r["looks_per_cell"] = r["N_eff_log_ratio"] / int(k)
    # the pixel translation of (d): a region of P cells >> the correlation area
    # holds P / A independent samples. Its looks per cell at the largest blocks
    # are this model's own analogue of 39.4 / 99.6.
    out["looks_per_cell_at_1600"] = out["by_population"]["null CPR 1.00 DOP 0"]["1600"]["looks_per_cell"]
    return out


# ------------------------------------------------------------------ (b), (c)
def crossing(ns, ps, level):
    """First N (log-interpolated) at which ps reaches level; with the bracket."""
    for i, p in enumerate(ps):
        if p >= level:
            if i == 0:
                return {"N": None, "bracket": [None, ns[0]], "note": f"already >= {level:.0%} at {ns[0]}"}
            p0, p1 = ps[i - 1], p
            t = (level - p0) / (p1 - p0) if p1 > p0 else 0.0
            ln = np.log(ns[i - 1]) + t * (np.log(ns[i]) - np.log(ns[i - 1]))
            return {"N": float(np.exp(ln)), "bracket": [ns[i - 1], ns[i]]}
    return {"N": None, "bracket": [ns[-1], None], "note": f"not reached by N = {ns[-1]}"}


def _np_bound_job(args):
    n, alts = args
    f = NPB.search_one_n(float(n), alts)
    cand = [set() for _ in alts]
    for i, seg, p, ph in f["candidates"]:
        cand[i].add((seg, round(p, 7), round(ph, 5)))
    fin = NPB.final_one_n((float(n), alts, [sorted(c) for c in cand]))
    return n, [float(b) for b in fin["bound"]], fin["argmin"], fin["max_quantile_residual"]


def main() -> int:
    from concurrent.futures import ProcessPoolExecutor
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    t0 = time.time()
    ss = np.random.SeedSequence(SEED)
    r_chk, r_q, r_pool, r_corr, r_pow = [np.random.default_rng(s) for s in ss.spawn(5)]
    print("=" * 78)
    print("P1 — region-level design curve")
    print("=" * 78)
    chk = check_bartlett(r_chk)
    print(f"  Bartlett vs look sum at N = 14: max relative R-quantile gap "
          f"{chk['max_relative_quantile_gap_R']:.4f}", flush=True)

    q_needed = sorted(set(N_GRID) | {218, 4 * N_CELL, 25 * N_CELL})
    qt = {float(n): q05(r_q, n) for n in q_needed}
    dr = json.loads((BASE_DIR / "docs" / "decision_rule.json").read_text(encoding="utf-8"))
    dq = dr["dop_quantile_table"]["q05"]
    q_check = {"218": {"bartlett": qt[218.0], "decision_rule": dq["218"]},
               "254": {"bartlett": qt[254.0], "decision_rule": dq["254"]}}
    print(f"  q05 at 218 / 254: {qt[218.0]:.5f} / {qt[254.0]:.5f} (decision_rule "
          f"{dq['218']:.5f} / {dq['254']:.5f})", flush=True)

    def qtab(n):
        n = float(n)
        if n in qt:
            return qt[n]
        ks = np.array(sorted(qt))
        return float(np.interp(np.log(n), np.log(ks), [qt[k] for k in ks]))

    pool = pooling_check(r_pool, qtab)
    for r in pool["rows"]:
        print(f"  pooling K = {r['K']:>2} {r['population']:24s}: IUT pooled "
              f"{r['pooled']['iut']['percent']:.3f} % vs single at KN {r['single_at_KN']['iut']['percent']:.3f} % "
              f"(z {r['iut_z']:+.2f})", flush=True)
    corr = correlated_regions(r_corr, lambda n: qtab(max(n, 2.0)) if n >= 218 else
                              float(np.interp(np.log(max(n, 2.0)), np.log([float(k) for k in dq]),
                                              list(dq.values()))))
    for lab, v in corr["by_population"].items():
        print(f"  correlated, {lab}: " + "; ".join(
            f"K {k}: N_eff(log-ratio) {x['N_eff_log_ratio']:.1f}"
            + (f", N_eff(mean DOP) {x['N_eff_mean_dop']:.1f}" if x.get("N_eff_mean_dop") else "")
            for k, x in v.items()), flush=True)

    alts = alternatives()
    power = {a[0]: [] for a in alts}
    # the grids of (b) below are read through best(): conditioned where exact
    size = {nl[0]: [] for nl in NULLS}
    for n in N_GRID:
        qn = qtab(n)
        for lab, cpr, dop in alts:
            power[lab].append(iut_rate(r_pow, n, cpr, dop, qn))
        for lab, cpr, dop in NULLS:
            size[lab].append(iut_rate(r_pow, n, cpr, dop, qn))
        print(f"  N {n:>5}: IUT power " + ", ".join(f"{best(power[a[0]][-1])['percent']:.1f}" for a in alts)
              + f" | size max {max(best(size[k][-1])['percent'] for k in size):.3f} %", flush=True)

    npalts = [(c, d, 0.0, lab) for lab, c, d in alts]
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        nb = {n: (b, am, res) for n, b, am, res in ex.map(_np_bound_job, [(n, npalts) for n in N_GRID])}
    bound = {a[0]: [100 * nb[n][0][i] for n in N_GRID] for i, a in enumerate(alts)}
    print("  NP bound: " + "; ".join(f"{a[0]}: " + ", ".join(f"{v:.1f}" for v in bound[a[0]]) for a in alts),
          flush=True)

    # (c) crossings and (d) translation
    f2c = None
    if F2P_JSON.is_file():
        f2c = json.loads(F2P_JSON.read_text(encoding="utf-8")).get("passes", {}).get("20200808", {}).get(
            "craters", {}).get("F2")
    design = {}
    for lab, cpr, dop in alts:
        pw = [best(p)["percent"] / 100 for p in power[lab]]
        bd = [b / 100 for b in bound[lab]]
        row = {"cpr": cpr, "dop": dop, "iut": {}, "np_bound": {}}
        for lev in LEVELS:
            for key, ps in (("iut", pw), ("np_bound", bd)):
                c = crossing(list(N_GRID), ps, lev)
                if c["N"] is not None:
                    c["cells_at_39p4"] = c["N"] / N_CELL
                    c["complex_pixels_at_99p6"] = c["N"] / N_CELL * AREA_PX
                row[key][f"{int(lev * 100)}pct"] = c
        design[lab] = row
    f2_ref = {"delivered_grid": {"disc_pixels": 1521, "area_px": 61.42, "independent_samples": 1521 / 61.42,
                                 "N_eff_at_39p4": 1521 / 61.42 * N_CELL}}
    if f2c:
        k = f2c["cells_with_signal"] / AREA_PX
        f2_ref["complex_product"] = {"cells_with_signal": f2c["cells_with_signal"], "area_px": AREA_PX,
                                     "independent_samples": k, "N_eff_at_39p4": k * N_CELL}

    # gates
    mono = all(all(best(b[i + 1])["percent"] >= best(b[i])["percent"] - 2 * np.hypot(
        best(b[i + 1])["mc_se_percent"], best(b[i])["mc_se_percent"])
        for i in range(len(b) - 1)) for b in power.values())
    mono_b = all(all(v[i + 1] >= v[i] - 1e-6 for i in range(len(v) - 1)) for v in bound.values())
    le = all(best(power[a[0]][j])["percent"] - 2 * best(power[a[0]][j])["mc_se_percent"]
             <= bound[a[0]][j] + 1e-6 for a in alts for j in range(len(N_GRID)))
    sz = all(best(s)["percent"] <= 5.0 + 2 * best(s)["mc_se_percent"] for v in size.values() for s in v)
    le_plain = all(power[a[0]][j]["percent"] - 2 * power[a[0]][j]["mc_se_percent"] <= bound[a[0]][j] + 1e-6
                   for a in alts for j in range(len(N_GRID)))
    sz_plain = all(s["percent"] <= 5.0 + 2 * s["mc_se_percent"] for v in size.values() for s in v)
    gate = {"power_monotone_in_N_eff": bool(mono), "np_bound_monotone": bool(mono_b),
            "iut_never_exceeds_np_bound": bool(le), "iut_size_le_5pct_plus_2se": bool(sz),
            "pooling_equals_K_times_N": bool(pool["all_within_3se"])}
    gate["verdict"] = "PASS" if all(gate.values()) else "FAIL"
    gate["plain_mc_versions"] = {
        "iut_never_exceeds_np_bound": bool(le_plain), "iut_size_le_5pct_plus_2se": bool(sz_plain),
        "why_not_the_gate": ("at CPR 1.00 DOP 0 the IUT's size is 5 % x P(m_hat < q05) ~ 5 %, and for "
                             "an alternative at its minimum DOP the least-favourable null is CPR 1.00 "
                             "DOP 0, where the NP test IS the F test: the IUT sits ON the boundary, and "
                             "a 2-SE test of a quantity equal to its limit fails by chance about "
                             "2.3 % of the time per point. The conditioned estimate removes the "
                             "exactly known component's noise; both are reported")}
    doc = {
        "schema": "lunar-ice/region-design-curve/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/region_design_curve.py",
        "seed": SEED, "alpha": ALPHA, "trials_per_cell": TRIALS, "q05_trials": Q_TRIALS,
        "test": ("the single-cell IUT of decision_rule.py on a region's pooled Stokes vector: "
                 "R > F^-1_0.95(2N, 2N) AND m_hat < q05(N), N = N_eff"),
        "sampler": ("exact complex-Wishart Bartlett decomposition, real N: W = L A A^H L^H, "
                    "|a11|^2 ~ Gamma(N, 1), |a22|^2 ~ Gamma(N - 1, 1), a21 ~ CN(0, 1)"),
        "bartlett_check": chk,
        "q05_table": {str(k): v for k, v in qt.items()}, "q05_check_against_decision_rule": q_check,
        "pooling": pool, "correlated_cells": corr,
        "N_eff_grid": list(N_GRID),
        "alternatives": [{"label": a[0], "cpr": a[1], "dop": a[2]} for a in alts],
        "iut_power": power, "iut_size_at_nulls": size,
        "iut_size_max_percent": [max(best(size[k][j])["percent"] for k in size) for j in range(len(N_GRID))],
        "np_bound_percent": bound,
        "np_bound_null": {str(n): [list(map(float, x)) if isinstance(x, tuple) else x for x in nb[n][1]]
                          for n in N_GRID},
        "design": design,
        "translation": {"looks_per_independent_cell": N_CELL, "complex_pixels_per_independent_sample": AREA_PX,
                        "crater_F2": f2_ref},
        "gate": gate,
        "run_info": {**run_info(), "wall_s": round(time.time() - t0, 1)},
    }
    OUT.write_text(json.dumps(doc, indent=2, default=float), encoding="utf-8")
    for lab in design:
        d = design[lab]
        print(f"  {lab:18s} IUT 50/80/90 %: " + ", ".join(
            f"{d['iut'][k]['N']:.0f}" if d['iut'][k]['N'] else str(d['iut'][k]['bracket'])
            for k in ("50pct", "80pct", "90pct")) + " | NP: " + ", ".join(
            f"{d['np_bound'][k]['N']:.0f}" if d['np_bound'][k]['N'] else str(d['np_bound'][k]['bracket'])
            for k in ("50pct", "80pct", "90pct")))
    print(f"  gate: {gate}")
    print(f"  wrote {OUT.relative_to(BASE_DIR)} ({time.time() - t0:.0f} s)")
    return 0 if gate["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
