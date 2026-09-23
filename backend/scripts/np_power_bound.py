"""
np_power_bound.py -- an upper bound on the power of ANY level-5 % per-cell test
of the joint criterion. (v14 work order, Task 3 / final pass B3)

    python backend/scripts/np_power_bound.py [--workers 8]

THE QUESTION
------------
The joint criterion asks whether a cell's population lies in the band
    H1:  1 < CPR < 1.2989  and  DOP < 0.13
against the null
    H0:  CPR <= 1  or  DOP >= 0.13.
A cell is a 2 x 2 complex Wishart sample covariance S (circular basis, SC and
OC) with N looks. Any test of level 5 % for the COMPOSITE null is of level 5 %
for each simple null Sigma0 in it, so by Neyman-Pearson its power at an
alternative Sigma1 cannot exceed the power of the most powerful level-5 % test
of Sigma0 against Sigma1. Hence, for every alternative,

    power_any(Sigma1) <= min over Sigma0 in H0 of NP(Sigma0, Sigma1),

and the minimum over any SUBSET of H0 is still a valid bound (only a looser
one). The subset searched is the null boundary: CPR = 1 at every DOP in
[0, 0.13] and coherence phase, and DOP = 0.13 at every CPR in (1, 1.2989] and
phase. The reported bound at N is the maximum of that bound over a grid of the
band: no level-5 % test can reach a higher power ANYWHERE on the grid.

THE COMPUTATION IS EXACT, NOT SIMULATED
---------------------------------------
The NP test rejects for large T = tr(A S), A = Sigma0^-1 - Sigma1^-1 (the
log-likelihood ratio of two complex Wisharts with the same N is N T plus a
constant). With S = (1/N) sum of N looks, T = l1 X + l2 Y where X, Y are
independent Gamma(N, 1/N) and l1, l2 are the eigenvalues of A Sigma, Sigma the
true covariance (its MGF is prod (1 - t l_i / N)^-N, so this holds for real N,
e.g. 39.4). So

    P(T > c) = int_0^1 P(l_big Y > c - l_small F^-1(u)) du,

evaluated by Gauss-Legendre quadrature in u (Y's law is the regularized
incomplete gamma function). The null quantile c is solved by safeguarded Newton
to a residual below 1e-10. A Monte Carlo check (10 batches of 10^5 draws, seed
20261005) at each N's maximizing pair gives the rate with its standard error.

GRIDS
-----
Alternatives: CPR 1.005 to 1.295 in steps of 0.01 (step <= 0.01), DOP from the
admissible minimum |q| to 0.1299 in steps of 0.005 (both ends included), phase
0 and 90 deg; plus decision_rule.json's four in-band populations. Null search,
per alternative and per boundary segment: a coarse grid (DOP / CPR step 0.01 /
0.02, phase step 30 deg), then the two best coarse points each refined by six
zoom rounds of a 5 x 5 local grid with halving spacing. The final bound at
every N takes the minimum over the UNION of the least-favourable nulls found at
all N, re-evaluated with 256 quadrature nodes, so the reported curve is the
same functional of one null set at every N.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from numpy.polynomial.legendre import leggauss
from scipy.special import gammainc, gammaincc, gammaincinv, gammaln

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "np_power_bound.json"
DECISION = BASE_DIR / "docs" / "decision_rule.json"
ALPHA = 0.05
DOP_T = 0.13
EDGE = (1 + DOP_T) / (1 - DOP_T)          # 1.2989: the band's CPR edge
#: the look counts the work order names, plus 38 and 100 (decision_rule.json's
#: evaluation points, for the IUT gate) and a grid for the figure's curve
N_REPORT = (14.0, 21.0, 39.4, 80.0, 218.0, 500.0)
N_GATE = (38.0, 100.0)
N_CURVE = (2.0, 3.0, 5.0, 8.0, 30.0, 55.0, 150.0, 300.0)
N_ALL = tuple(sorted(set(N_REPORT + N_GATE + N_CURVE)))
K_SEARCH, K_FINAL, K_CHECK = 64, 256, 1024
NEWTON_ITERS = 60
TOL = 1e-10
MC_SEED = 20261005
MC_BATCHES, MC_DRAWS = 10, 100_000
SKETCH = {"14": 12, "39": 20, "80": 31, "218": 60, "500": 89}

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


# ------------------------------------------------------------ covariances
def gamma_c(dop, cpr):
    q = (cpr - 1.0) / (cpr + 1.0)
    return np.sqrt(np.clip(dop * dop - q * q, 0.0, None) / (1.0 - q * q))


def sigma(cpr, gam, phi_deg):
    """(..., 2, 2) circular-basis covariance, S0 = 1: SC power CPR/(1+CPR),
    OC power 1/(1+CPR), coherence gam at phase phi."""
    cpr, gam, phi = np.broadcast_arrays(np.asarray(cpr, float), np.asarray(gam, float),
                                        np.deg2rad(np.asarray(phi_deg, float)))
    a, b = cpr / (1 + cpr), 1 / (1 + cpr)
    c = gam * np.sqrt(a * b) * np.exp(1j * phi)
    S = np.empty(cpr.shape + (2, 2), dtype=complex)
    S[..., 0, 0], S[..., 1, 1], S[..., 0, 1], S[..., 1, 0] = a, b, c, np.conj(c)
    return S


def eig2(M):
    """Eigenvalues of a (..., 2, 2) matrix similar to a Hermitian one."""
    t = np.real(M[..., 0, 0] + M[..., 1, 1])
    d = np.real(M[..., 0, 0] * M[..., 1, 1] - M[..., 0, 1] * M[..., 1, 0])
    r = np.sqrt(np.clip(t * t / 4 - d, 0.0, None))
    return t / 2 - r, t / 2 + r


def ordered(l1, l2):
    """(small, big) by magnitude."""
    swap = np.abs(l1) > np.abs(l2)
    return np.where(swap, l2, l1), np.where(swap, l1, l2)


# ------------------------------------------------------------ exact laws
class Quad:
    def __init__(self, n: float, k: int):
        u, w = leggauss(k)
        u = 0.5 * (u + 1.0)
        self.n, self.w = n, 0.5 * w
        self.x = gammaincinv(n, u) / n          # Gamma(N, 1/N) quantiles
        self.lognorm = n * np.log(n) - gammaln(n)

    def _y(self, ls, lb, c):
        return (c[:, None] - ls[:, None] * self.x[None, :]) / lb[:, None]

    def exceed(self, ls, lb, c):
        """P(ls X + lb Y > c)."""
        y = np.clip(self._y(ls, lb, c), 0.0, None)
        v = np.where(lb[:, None] > 0, gammaincc(self.n, self.n * y), gammainc(self.n, self.n * y))
        return v @ self.w

    def density(self, ls, lb, c):
        y = self._y(ls, lb, c)
        pos = y > 0
        yl = np.where(pos, y, 1.0)
        f = np.where(pos, np.exp(self.lognorm + (self.n - 1) * np.log(yl) - self.n * yl), 0.0)
        return (f @ self.w) / np.abs(lb)

    def quantile(self, ls, lb):
        """c with P(T > c) = ALPHA, safeguarded Newton. Returns (c, residual)."""
        m = ls + lb
        sd = np.sqrt((ls * ls + lb * lb) / self.n)
        lo, hi = m - 14 * sd, m + 14 * sd
        c = m + 1.645 * sd
        res = np.full(c.shape, np.inf)
        act = np.arange(c.size)
        for _ in range(NEWTON_ITERS):
            a_s, a_b, cc = ls[act], lb[act], c[act]
            F = self.exceed(a_s, a_b, cc) - ALPHA
            res[act] = np.abs(F)
            done = res[act] < TOL
            act, F, a_s, a_b, cc = act[~done], F[~done], a_s[~done], a_b[~done], cc[~done]
            if act.size == 0:
                break
            lo[act] = np.where(F > 0, cc, lo[act])
            hi[act] = np.where(F <= 0, cc, hi[act])
            f = self.density(a_s, a_b, cc)
            with np.errstate(divide="ignore", invalid="ignore"):
                cn = cc + F / f
            bad = ~np.isfinite(cn) | (cn <= lo[act]) | (cn >= hi[act])
            c[act] = np.where(bad, 0.5 * (lo[act] + hi[act]), cn)
        return c, res


def np_power(q: Quad, S0, S1):
    """NP power of level ALPHA for Sigma0 vs Sigma1, paired arrays (M, 2, 2)."""
    A = np.linalg.inv(S0) - np.linalg.inv(S1)
    l0s, l0b = ordered(*eig2(A @ S0))
    c, res = q.quantile(l0s, l0b)
    l1s, l1b = ordered(*eig2(A @ S1))
    return q.exceed(l1s, l1b, c), res


# ------------------------------------------------------------ grids
def alternatives(decision_pops):
    rows = []
    for cpr in np.round(np.arange(1.005, 1.2951, 0.01), 3):
        qa = (cpr - 1) / (cpr + 1)
        dops = np.unique(np.r_[np.arange(qa, 0.1299, 0.005), 0.1299])
        for dop in dops:
            for ph in (0.0, 90.0):
                rows.append((float(cpr), float(dop), ph, "grid"))
    for lab, cpr, dop in decision_pops:
        for ph in (0.0, 90.0):
            rows.append((float(cpr), float(dop), ph, lab))
    return rows


def seg_sigma(seg, p, phi):
    """Null boundary: seg 0 = CPR 1 at DOP p; seg 1 = DOP 0.13 at CPR p."""
    p = np.asarray(p, float)
    if seg == 0:
        g = np.clip(p, 0.0, DOP_T)
        return sigma(np.ones_like(g), g, phi), np.ones_like(g), g
    c = np.clip(p, 1.0, EDGE)
    return sigma(c, gamma_c(DOP_T, c), phi), c, np.full_like(c, DOP_T)


COARSE = {0: np.round(np.arange(0.0, 0.1301, 0.01), 4),
          1: np.r_[np.arange(1.0, EDGE, 0.02), EDGE]}
COARSE_PHI = np.arange(0.0, 360.0, 30.0)
START_STEP = {0: 0.01, 1: 0.02}


def search_one_n(n: float, alts) -> dict:
    """Per alternative: the least-favourable nulls found on each segment."""
    t0 = time.time()
    q = Quad(n, K_SEARCH)
    na = len(alts)
    S1 = sigma([a[0] for a in alts], [gamma_c(a[1], a[0]) for a in alts], [a[2] for a in alts])
    cands = []            # (alt index, seg, p, phi)
    for seg in (0, 1):
        P, PH = np.meshgrid(COARSE[seg], COARSE_PHI, indexing="ij")
        P, PH = P.ravel(), PH.ravel()
        S0, _, _ = seg_sigma(seg, P, PH)
        pw = np.empty((na, P.size))
        for i in range(na):
            pw[i], _ = np_power(q, S0, np.broadcast_to(S1[i], S0.shape))
        best2 = np.argsort(pw, axis=1)[:, :2]
        for chain in range(2):
            p = P[best2[:, chain]].copy()
            ph = PH[best2[:, chain]].copy()
            step_p, step_ph = START_STEP[seg], 30.0
            cur = pw[np.arange(na), best2[:, chain]]
            off = np.array([-2, -1, 0, 1, 2]) / 2.0
            for _ in range(6):
                dp, dh = np.meshgrid(off * step_p, off * step_ph, indexing="ij")
                gp = p[:, None] + dp.ravel()[None, :]
                gh = (ph[:, None] + dh.ravel()[None, :]) % 360.0
                S0g, _, _ = seg_sigma(seg, gp.ravel(), gh.ravel())
                S1g = np.repeat(S1, gp.shape[1], axis=0)
                pwg, _ = np_power(q, S0g, S1g)
                pwg = pwg.reshape(na, -1)
                j = pwg.argmin(axis=1)
                better = pwg[np.arange(na), j] < cur
                p = np.where(better, gp[np.arange(na), j], p)
                ph = np.where(better, gh[np.arange(na), j], ph)
                cur = np.minimum(cur, pwg[np.arange(na), j])
                step_p, step_ph = step_p / 2, step_ph / 2
            lim = (0.0, DOP_T) if seg == 0 else (1.0, EDGE)
            p = np.clip(p, *lim)
            for i in range(na):
                cands.append((i, seg, float(p[i]), float(ph[i])))
    return {"N": n, "candidates": cands, "wall_s": time.time() - t0}


def final_one_n(args) -> dict:
    n, alts, cand_by_alt = args
    q = Quad(n, K_FINAL)
    na = len(alts)
    S1 = sigma([a[0] for a in alts], [gamma_c(a[1], a[0]) for a in alts], [a[2] for a in alts])
    bound = np.empty(na)
    arg = []
    worst_res = 0.0
    for i in range(na):
        cs = cand_by_alt[i]
        seg0 = [c for c in cs if c[0] == 0]
        seg1 = [c for c in cs if c[0] == 1]
        S0 = []
        meta = []
        for seg, lst in ((0, seg0), (1, seg1)):
            if lst:
                s, cc, dd = seg_sigma(seg, [c[1] for c in lst], [c[2] for c in lst])
                S0.append(s)
                meta += [(seg, float(a), float(b), c[2]) for a, b, c in zip(cc, dd, lst)]
        S0 = np.concatenate(S0)
        pw, res = np_power(q, S0, np.broadcast_to(S1[i], S0.shape))
        worst_res = max(worst_res, float(res.max()))
        j = int(pw.argmin())
        bound[i] = pw[j]
        arg.append(meta[j])
    return {"N": n, "bound": bound, "argmin": arg, "max_quantile_residual": worst_res}


def mc_check(n, alt, null, rng) -> dict:
    S1 = sigma(alt[0], gamma_c(alt[1], alt[0]), alt[2])
    S0 = sigma(null[0], gamma_c(null[1], null[0]), null[2])
    A = np.linalg.inv(S0) - np.linalg.inv(S1)
    l0 = eig2(A @ S0)
    l1 = eig2(A @ S1)
    p = []
    for _ in range(MC_BATCHES):
        t0 = l0[0] * rng.gamma(n, 1 / n, MC_DRAWS) + l0[1] * rng.gamma(n, 1 / n, MC_DRAWS)
        c = np.quantile(t0, 1 - ALPHA)
        t1 = l1[0] * rng.gamma(n, 1 / n, MC_DRAWS) + l1[1] * rng.gamma(n, 1 / n, MC_DRAWS)
        p.append(float((t1 > c).mean()))
    p = np.array(p)
    return {"power_percent": 100 * float(p.mean()),
            "mc_se_percent": 100 * float(p.std(ddof=1) / np.sqrt(MC_BATCHES)),
            "draws": MC_BATCHES * MC_DRAWS,
            "method": (f"{MC_BATCHES} batches of {MC_DRAWS:,}: null quantile and "
                       "alternative rate from independent draws in each batch; "
                       "SE from the batch spread (includes the quantile's error)")}


def exact_at(n, alt, null, k) -> float:
    q = Quad(n, k)
    S1 = sigma([alt[0]], [gamma_c(alt[1], alt[0])], [alt[2]])
    S0 = sigma([null[0]], [gamma_c(null[1], null[0])], [null[2]])
    pw, _ = np_power(q, S0, S1)
    return float(pw[0])


def _search(args):
    return search_one_n(*args)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--grid-keys", action="store_true",
                    help=("v17a: merge the grid resolution as numbers, read from this script's "
                          "own constants (no computation)"))
    args = ap.parse_args()
    if args.grid_keys:
        doc = json.loads(OUT.read_text(encoding="utf-8"))
        rounds = 6
        doc["grids"]["numeric"] = {
            "alternative_cpr_step": 0.01, "alternative_dop_step": 0.005,
            "alternatives": doc["grids"]["alternatives"],
            "null_coarse_dop_step": START_STEP[0], "null_coarse_cpr_step": START_STEP[1],
            "null_coarse_phase_step_deg": float(COARSE_PHI[1] - COARSE_PHI[0]),
            "zoom_rounds": rounds,
            "null_final_spacing_dop": START_STEP[0] / 2 ** rounds,
            "null_final_spacing_cpr": START_STEP[1] / 2 ** rounds,
            "null_final_spacing_phase_deg": float(COARSE_PHI[1] - COARSE_PHI[0]) / 2 ** rounds}
        OUT.write_text(json.dumps(doc, indent=2, default=float), encoding="utf-8")
        print(doc["grids"]["numeric"])
        return 0
    dr = json.loads(DECISION.read_text(encoding="utf-8"))
    band_pops = sorted({(r["population"], r["pop_cpr"], r["pop_dop"]) for r in dr["rows"]["A"]
                        if not r["null_cpr"] and not r["null_dop"]})
    alts = alternatives(band_pops)
    print("=" * 78)
    print("B3 — Neyman-Pearson upper bound on any level-5 % per-cell test")
    print("=" * 78)
    print(f"  {len(alts)} alternatives; N = {N_ALL}", flush=True)
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        found = list(ex.map(_search, [(n, alts) for n in N_ALL]))
    print(f"  search done in {time.time() - t0:.0f} s", flush=True)
    cand_by_alt = [set() for _ in alts]
    for f in found:
        for i, seg, p, ph in f["candidates"]:
            cand_by_alt[i].add((seg, round(p, 7), round(ph, 5)))
    cand_by_alt = [sorted(s) for s in cand_by_alt]
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        fin = list(ex.map(final_one_n, [(n, alts, cand_by_alt) for n in N_ALL]))
    print(f"  final evaluation done in {time.time() - t0:.0f} s", flush=True)

    rng = np.random.default_rng(MC_SEED)
    by_n = {}
    for f in fin:
        n = f["N"]
        grid_idx = [i for i, a in enumerate(alts)]
        i = int(np.argmax(f["bound"][grid_idx]))
        a = alts[i]
        seg, pc, pd, ph = f["argmin"][i]
        null = (pc, pd, ph)
        mc = mc_check(n, a, null, rng)
        e_fin = float(f["bound"][i])
        e_chk = exact_at(n, a, null, K_CHECK)
        by_phase = {}
        for phv in (0.0, 90.0):
            idx = [j for j, b in enumerate(alts) if b[2] == phv]
            jj = idx[int(np.argmax(f["bound"][idx]))]
            by_phase[f"{int(phv)}"] = {"bound_percent": 100 * float(f["bound"][jj]),
                                       "at_cpr": alts[jj][0], "at_dop": alts[jj][1]}
        by_n[f"{n:g}"] = {
            "N": n,
            "bound_percent": 100 * e_fin,
            "maximizing_alternative": {"cpr": a[0], "dop": a[1], "phase_deg": a[2]},
            "least_favourable_null": {"segment": "CPR = 1" if seg == 0 else "DOP = 0.13",
                                      "cpr": pc, "dop": pd, "phase_deg": ph},
            "by_alternative_phase": by_phase,
            "quadrature_check": {"nodes": K_FINAL, "value_percent": 100 * e_fin,
                                 "nodes_check": K_CHECK, "value_check_percent": 100 * e_chk,
                                 "abs_diff_percent": 100 * abs(e_chk - e_fin)},
            "mc_check": mc,
            "max_quantile_residual": f["max_quantile_residual"]}
        print(f"  N {n:>6g}: bound {100 * e_fin:6.2f} %  at CPR {a[0]:.3f} DOP {a[1]:.4f} "
              f"phase {a[2]:g}  | null {'CPR=1' if seg == 0 else 'DOP=0.13'} "
              f"({pc:.4f}, {pd:.4f}, {ph:.2f})  | MC {mc['power_percent']:.2f} +/- "
              f"{mc['mc_se_percent']:.2f}  | K{K_CHECK} {100 * e_chk:.3f}", flush=True)

    # bound at decision_rule's populations, and the IUT gate
    iut_rows = []
    for key, blk in dr["summary"].items():
        arm, nn = key.split("_N")
        if arm != "A":
            continue
        f = next(x for x in fin if x["N"] == float(nn))
        for pop, pwr in blk["oracle"]["iut_power_percent"].items():
            idx = [j for j, a in enumerate(alts) if a[3] == pop]
            b = min(100 * float(f["bound"][j]) for j in idx)
            iut_rows.append({"N": float(nn), "population": pop, "iut_power_percent": pwr,
                             "bound_percent": b, "ok": pwr <= b})
        for variant in ("plugin_W960", "plugin_W16"):
            for pop, pwr in blk[variant]["iut_power_percent"].items():
                idx = [j for j, a in enumerate(alts) if a[3] == pop]
                b = min(100 * float(f["bound"][j]) for j in idx)
                iut_rows.append({"N": float(nn), "population": pop, "variant": variant,
                                 "iut_power_percent": pwr, "bound_percent": b, "ok": pwr <= b})
    curve = [{"N": x["N"], "bound_percent": 100 * float(np.max(x["bound"]))} for x in fin]
    vals = [c["bound_percent"] for c in curve]
    g_ge5 = all(v >= 5.0 - 1e-6 for v in vals)
    g_mono = all(b >= a - 1e-6 for a, b in zip(vals, vals[1:]))
    g_iut = all(r["ok"] for r in iut_rows)
    # the per-alternative map at the complex product's look count
    f39 = next(x for x in fin if x["N"] == 39.4)
    grid_map = [{"cpr": a[0], "dop": a[1], "phase_deg": a[2], "bound_percent": 100 * float(b)}
                for a, b in zip(alts, f39["bound"]) if a[3] == "grid"]
    report = {f"{k}": by_n[f"{k:g}"]["bound_percent"] for k in N_REPORT}
    doc = {
        "schema": "lunar-ice/np-power-bound/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/np_power_bound.py",
        "alpha": ALPHA,
        "definition": ("for each alternative Sigma1 in the band, the minimum over null-boundary "
                       "Sigma0 of the Neyman-Pearson power of the level-5 % test of Sigma0 vs "
                       "Sigma1 (statistic tr((Sigma0^-1 - Sigma1^-1) S), N-look complex "
                       "Wishart); bound_percent = the maximum of that over the band grid. No "
                       "level-5 % per-cell test of H0 = {CPR <= 1} U {DOP >= 0.13} has higher "
                       "power at any grid point."),
        "method": ("exact: T = l1 X + l2 Y, X, Y ~ Gamma(N, 1/N) independent, l = "
                   "eigenvalues of A Sigma; P(T > c) by Gauss-Legendre in the quantile of "
                   "the smaller-weight variable; null quantile by safeguarded Newton. Monte "
                   "Carlo check at each maximizing pair."),
        "grids": {"alternative_cpr": "1.005 to 1.295 step 0.01",
                  "alternative_dop": "admissible minimum |q| to 0.1299, step 0.005, ends included",
                  "alternative_phase_deg": [0, 90],
                  "alternatives": len(alts),
                  "extra_alternatives": [p[0] for p in band_pops],
                  "null_segments": {"CPR = 1": "DOP 0 to 0.13", "DOP = 0.13": "CPR 1 to 1.2989",
                                    "phase": "all"},
                  "null_coarse": {"dop_step": 0.01, "cpr_step": 0.02, "phase_step_deg": 30.0,
                                  "points": int(sum(COARSE[s].size for s in (0, 1)) * COARSE_PHI.size)},
                  "null_refinement": ("two best coarse points per segment, six rounds of a "
                                      "5 x 5 grid, spacing halved each round (final spacing "
                                      "DOP 1.6e-4, CPR 3.1e-4, phase 0.47 deg)"),
                  "final": ("minimum over the union of refined nulls found at all N, "
                            f"{K_FINAL} quadrature nodes (search {K_SEARCH})")},
        "bound_percent_at": report,
        "by_N": by_n,
        "curve": curve,
        "iut_comparison": iut_rows,
        "map_N39p4": grid_map,
        "sketch_comparison": {"sketch_percent": SKETCH,
                              "note": ("np_bound_sketch.py compared each alternative with two "
                                       "nulls (CPR 1 at the same coherence; DOP 0.13 at the "
                                       "same CPR, phase 0 and 180) on a 12 x 6 grid; the search "
                                       "here reaches nulls it did not, so its bound is lower or "
                                       "equal wherever the grids coincide")},
        "gate": {"bound_ge_5pct_every_N": g_ge5, "monotone_in_N": g_mono,
                 "iut_power_le_bound": g_iut,
                 "verdict": "PASS" if (g_ge5 and g_mono and g_iut) else "FAIL"},
        "mc_seed": MC_SEED,
        "run_info": run_info(),
    }
    OUT.write_text(json.dumps(doc, indent=2, default=float), encoding="utf-8")
    print(f"  curve: " + ", ".join(f"{c['N']:g}: {c['bound_percent']:.2f}" for c in curve))
    print(f"  gate: >=5 % {g_ge5}, monotone {g_mono}, IUT <= bound {g_iut} -> {doc['gate']['verdict']}")
    print(f"  wrote {OUT.relative_to(BASE_DIR)}  ({time.time() - t0:.0f} s)")
    return 0 if doc["gate"]["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
