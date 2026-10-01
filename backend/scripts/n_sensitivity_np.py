"""
n_sensitivity_np.py -- the Neyman-Pearson bound on any level-5 % single-cell
test of the criterion's null, at every N of the sensitivity grid. (v21 work
order, W1B)

    python backend/scripts/n_sensitivity_np.py [--workers 8]

Same procedure as np_power_bound.py (its functions are imported unchanged: the
838-population band grid plus the four decision-rule populations, the null
boundary searched and refined, exact quadrature), run at the sensitivity grid,
the N of the published curve and the values the work order asks to reproduce.
Writes docs/n_sensitivity_np.json (draws nothing; the MC check of the bound at
its maximizer uses seed 20261005 as np_power_bound.py does).

Reported per N: the bound (the maximum over the grid), its maximizing
alternative, the bound at the published operating point (CPR 1.1 at its minimum
DOP 0.0476) and at the other three decision-rule populations, and, for every N
the published artifact holds, the difference from it.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402
import np_power_bound as NPB  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "n_sensitivity_np.json"
GRID = (5.0, 7.0, 10.0, 13.72, 14.5, 17.4, 21.0, 28.0, 34.0, 38.0, 39.4, 45.0, 55.0, 70.0, 75.9, 80.0,
        100.0, 150.0, 218.0, 79.6166)
#: the values the work order asks to reproduce (percent), and the published artifact's own N
KNOWN = {14.0: 9.72, 21.0: 11.06, 30.0: 12.63, 38.0: 13.94, 39.4: 14.17, 55.0: 16.56, 80.0: 20.2,
         100.0: 22.9, 150.0: 29.4, 218.0: 37.6, 300.0: 46.5, 500.0: 64.1}
N_ALL = tuple(sorted(set(GRID) | set(KNOWN)))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    t0 = time.time()
    dr = json.loads(NPB.DECISION.read_text(encoding="utf-8"))
    band_pops = sorted({(r["population"], r["pop_cpr"], r["pop_dop"]) for r in dr["rows"]["A"]
                        if not r["null_cpr"] and not r["null_dop"]})
    alts = NPB.alternatives(band_pops)
    print("=" * 78); print("W1B — the Neyman-Pearson bound over the N grid"); print("=" * 78)
    print(f"  {len(alts)} alternatives; N = {N_ALL}", flush=True)
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        found = list(ex.map(NPB._search, [(n, alts) for n in N_ALL]))
    print(f"  search done in {time.time() - t0:.0f} s", flush=True)
    cand = [set() for _ in alts]
    for f in found:
        for i, seg, p, ph in f["candidates"]:
            cand[i].add((seg, round(p, 7), round(ph, 5)))
    cand = [sorted(s) for s in cand]
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        fin = list(ex.map(NPB.final_one_n, [(n, alts, cand) for n in N_ALL]))
    print(f"  final evaluation done in {time.time() - t0:.0f} s", flush=True)
    import pickle
    pickle.dump({'found': found, 'fin': fin, 'alts': alts}, open(str(OUT) + '.checkpoint.pkl', 'wb'))
    published = json.loads(NPB.OUT.read_text(encoding="utf-8"))
    pub = {c["N"]: c["bound_percent"] for c in published["curve"]}
    rng = np.random.default_rng(NPB.MC_SEED)
    by_n = {}
    for f in fin:
        n = f["N"]
        grid_i = [i for i, a in enumerate(alts) if a[3] == "grid"]
        i = grid_i[int(np.argmax(f["bound"][grid_i]))]
        a = alts[i]
        seg, pc, pd, ph = f["argmin"][i]
        mc = NPB.mc_check(n, a, (pc, pd, ph), rng)
        at_pop = {}
        for lab, cpr, dop in band_pops:
            idx = [j for j, b in enumerate(alts) if b[3] == lab]
            at_pop[lab] = {"cpr": cpr, "dop": dop, "bound_percent": min(100 * float(f["bound"][j]) for j in idx)}
        by_n[f"{n:g}"] = {
            "N": n, "bound_percent": 100 * float(f["bound"][i]),
            "maximizing_alternative": {"cpr": a[0], "dop": a[1], "phase_deg": a[2]},
            "least_favourable_null": {"segment": "CPR = 1" if seg == 0 else "DOP = 0.13", "cpr": pc, "dop": pd, "phase_deg": ph},
            "bound_at_decision_rule_populations": at_pop,
            "bound_at_published_operating_point_CPR1p1_DOPmin_percent": at_pop["band CPR 1.1 DOP min 0.0476"]["bound_percent"],
            "mc_check": mc, "max_quantile_residual": f["max_quantile_residual"],
            "published_artifact_percent": pub.get(n), "work_order_value_percent": KNOWN.get(n)}
        print(f"  N {n:>8g}: bound {by_n[f'{n:g}']['bound_percent']:7.3f} %  (published {pub.get(n)}; work order {KNOWN.get(n)}); "
              f"at CPR 1.1 DOP min {by_n[f'{n:g}']['bound_at_published_operating_point_CPR1p1_DOPmin_percent']:.3f} %", flush=True)
    diffs = []
    for n, v in KNOWN.items():
        got = by_n[f"{n:g}"]["bound_percent"]
        diffs.append({"N": n, "work_order_percent": v, "computed_percent": got, "abs_diff": abs(got - v),
                      "agrees_to_printed_precision": bool(abs(got - v) <= (0.0051 if n <= 55 else 0.051))})
    OUT.write_text(json.dumps({
        "schema": "lunar-ice/n-sensitivity-np/1", "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/n_sensitivity_np.py", "seed": None,
        "seed_note": "the bound is exact quadrature; the MC check of each maximizer uses seed %d" % NPB.MC_SEED,
        "alternatives": len(alts), "N": list(N_ALL), "by_N": by_n,
        "reproduction": diffs, "reproduction_all_agree": all(d["agrees_to_printed_precision"] for d in diffs),
        "run_info": {**run_info(), "wall_s": round(time.time() - t0, 1)}}, indent=2, default=float), encoding="utf-8")
    print(f"  wrote {OUT.name} ({time.time() - t0:.0f} s); reproduction: "
          f"{all(d['agrees_to_printed_precision'] for d in diffs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
