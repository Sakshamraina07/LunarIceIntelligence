"""
n_sensitivity_region_39.py -- the region-mean null at the product's look count.
(V22 work order, C1)

    python backend/scripts/n_sensitivity_region_39.py [--workers 3]

The correlated model has integer looks per channel L, so the grid of
n_sensitivity_region.py reaches N = 37.3 (L = 13) where the paper aims at 39.4.
Here the log-ratio N of L = 12 ... 16 is measured on 16 realizations of 256 x 256 cells
(about 1 000 000 cells; a per cent or better) and the region-mean null (CPR 0.7 / DOP 0.176,
and 0.7 / 0.20; 260 and 3647 cells; correlated cells) is simulated at the L whose N is nearest
to 38, 39.4 and 40, with more trials than the grid run (4000 regions at 260 cells, 2000 at
3647), reporting conditional rate, containing fraction, unconditional rate and the binomial MC
SE of the unconditional rate; and, beside them, the L whose N is nearest on each side of 39.4,
with the linear interpolation in N between the two L bracketing 39.4. The 3647-cell 2.7 % of
the paper is re-run at 39.4. Seeds 20261071 + index. Writes docs/n_sensitivity_region_39.json.
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
from scipy.ndimage import uniform_filter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402
import n_sensitivity_region as NR  # noqa: E402
import region_mean_null as RM  # noqa: E402
import f2_maximum as F2M  # noqa: E402
import enl_logratio as L  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "n_sensitivity_region_39.json"
LS = (12, 13, 14, 15, 16)
TARGETS = (38.0, 39.4, 40.0)
POPS = (("CPR 0.7 DOP 0.176", 0.7, 0.3 / 1.7), ("CPR 0.7 DOP 0.20", 0.7, 0.20))
TRIALS = {260: 4000, 3647: 2000}
SEED = 20261071

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def nlog(args):
    Lk, seed, rsc, roc = args
    rng = np.random.default_rng(seed)
    H = W = 256
    M = 4
    vals = []
    for _ in range(4):                    # 4 x 4 realizations
        sc = np.zeros((4, H + 2 * M, W + 2 * M)); oc = np.zeros_like(sc)
        for _ in range(Lk):
            wo = F2M.ar1_stationary(rng, (H + 2 * M, W + 2 * M), *roc, 4)
            ws = F2M.ar1_stationary(rng, (H + 2 * M, W + 2 * M), *rsc, 4)
            sc += np.abs(np.sqrt(0.5) * ws) ** 2; oc += np.abs(np.sqrt(0.5) * wo) ** 2
        f = lambda v: uniform_filter(v, size=(1, 5, 5), mode="reflect")  # noqa: E731
        bs, bo = f(sc / Lk), f(oc / Lk)
        vals.append(float(L.n_from_var(np.var(np.log(bs / bo)[:, M:-M, M:-M], ddof=1))))
    return Lk, float(np.mean(vals)), float(np.std(vals, ddof=1) / np.sqrt(len(vals)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    t0 = time.time()
    gc = json.loads((BASE_DIR / "docs" / "complex_grid_correlation.json").read_text(encoding="utf-8"))["lag_correlation_before_boxcar"]
    rsc = (float(np.sqrt(gc["SC"]["azimuth_lines"][0])), float(np.sqrt(gc["SC"]["range_samples"][0])))
    roc = (float(np.sqrt(gc["OC"]["azimuth_lines"][0])), float(np.sqrt(gc["OC"]["range_samples"][0])))
    print("=" * 78); print("V22 C1 — region-mean null at 38 / 39.4 / 40 looks"); print("=" * 78, flush=True)
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        cal = list(ex.map(nlog, [(l, SEED + 100 + l, rsc, roc) for l in LS]))
    calN = {l: (n, se) for l, n, se in cal}
    print("  large-field N(L): " + ", ".join(f"L{l}->{n:.2f}+-{se:.2f}" for l, (n, se) in calN.items()), flush=True)
    # the L nearest each target, and the two bracketing 39.4
    chosen = {t: min(calN, key=lambda l: abs(calN[l][0] - t)) for t in TARGETS}
    below = max((l for l in LS if calN[l][0] <= 39.4), key=lambda l: calN[l][0])
    above = min((l for l in LS if calN[l][0] >= 39.4), key=lambda l: calN[l][0])
    needed = sorted(set(chosen.values()) | {below, above})
    print(f"  nearest L: {chosen}; bracketing 39.4: L{below} ({calN[below][0]:.2f}), L{above} ({calN[above][0]:.2f})", flush=True)
    jobs = [(pop, c, d, Lc, sz) for pop, c, d in POPS for Lc in needed for sz in RM.SIZES]
    ss = np.random.SeedSequence(SEED).spawn(len(jobs))
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        res = list(ex.map(NR.correlated_L, [(ss[i], c, d, Lc, sz, TRIALS[sz], rsc, roc) for i, (pop, c, d, Lc, sz) in enumerate(jobs)]))
    rows = {}
    for (pop, c, d, Lc, sz), r in zip(jobs, res):
        r = NR.with_unconditional(dict(r))
        r["large_field_N"] = calN[Lc][0]; r["large_field_N_se"] = calN[Lc][1]
        rows.setdefault(pop, {}).setdefault(f"cells{sz}", {})[f"L{Lc}"] = r
        print(f"  {pop} {sz} cells L={Lc} (N {calN[Lc][0]:.1f}): conditional {100 * r['conditional_p']:.2f} %, containing {r['containing_fraction']:.3f}, "
              f"unconditional {100 * r['unconditional_p']:.2f} +- {100 * r['unconditional_se']:.2f} % ({r['trials']} regions)", flush=True)
    # linear interpolation in N to 39.4 between the bracketing L (reported as an interpolation, with the propagated SE)
    interp = {}
    for pop, c, d in POPS:
        for sz in RM.SIZES:
            a, b = rows[pop][f"cells{sz}"][f"L{below}"], rows[pop][f"cells{sz}"][f"L{above}"]
            if below == above:
                interp.setdefault(pop, {})[f"cells{sz}"] = {"unconditional_percent": 100 * a["unconditional_p"], "unconditional_se_percent": 100 * a["unconditional_se"],
                                                            "note": "the setting L reaches 39.4 to within the calibration"}
                continue
            w = (39.4 - calN[below][0]) / (calN[above][0] - calN[below][0])
            p = (1 - w) * a["unconditional_p"] + w * b["unconditional_p"]
            se = float(np.sqrt(((1 - w) * a["unconditional_se"]) ** 2 + (w * b["unconditional_se"]) ** 2))
            interp.setdefault(pop, {})[f"cells{sz}"] = {"weight_on_upper_L": w, "unconditional_percent": 100 * p, "unconditional_se_percent": 100 * se,
                                                        "bracketing_L": [below, above]}
    doc = {"schema": "lunar-ice/n-sensitivity-region-39/1", "generated_utc": datetime.now(timezone.utc).isoformat(),
           "generator": "backend/scripts/n_sensitivity_region_39.py", "seed": SEED,
           "statistic": "unconditional P(mean sample DOP < 0.13 over the pixels with sample CPR >= 1, and the region has such a pixel)",
           "large_field_N": {str(l): {"N": n, "se": se} for l, (n, se) in calN.items()},
           "calibration": "4 x 4 realizations of 256 x 256 cells (about 10^6 cells) per L", "targets": list(TARGETS),
           "nearest_L": {str(t): l for t, l in chosen.items()}, "bracketing_L_for_39p4": [below, above],
           "trials": {str(k): v for k, v in TRIALS.items()}, "results": rows, "interpolated_to_39p4": interp,
           "run_info": {**run_info(), "wall_s": round(time.time() - t0, 1)}}
    OUT.write_text(json.dumps(doc, indent=2, default=float), encoding="utf-8")
    for pop in interp:
        for sz, v in interp[pop].items():
            print(f"  interpolated to N = 39.4, {pop}, {sz}: {v['unconditional_percent']:.2f} +- {v['unconditional_se_percent']:.2f} %")
    print(f"  wrote {OUT.name} ({time.time() - t0:.0f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
