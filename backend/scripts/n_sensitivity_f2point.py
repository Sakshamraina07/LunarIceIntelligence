"""
n_sensitivity_f2point.py -- F2's pooled-looks point at higher precision. (v21
work order, W1F)

    python backend/scripts/n_sensitivity_f2point.py

v21 prints "Their 6.7 independent samples pool to about 262 looks, where the IUT's
power is about 0.6 %". region_design_curve.json::f2_point has 0.5775 +- 0.017 % from
2 x 10^5 draws (seed 20261014, q05 from 10^6 draws); n_sensitivity_real.py's grid
row at N = 39.4 (same N_eff, seed 20261041, q05 from 2 x 10^6) read 0.5245 +- 0.016 %.
Both are small-probability estimates that depend on q05(N_eff) as well, so here
q05 comes from 2 x 10^7 draws and the power from 10^7, for several seeds, to say
which number v21's 0.6 is closest to. Draws: Bartlett sampler of
region_design_curve, seeds 20261051..20261054.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402
import region_design_curve as RDC  # noqa: E402
from scipy.stats import f as Fd  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "n_sensitivity_f2point.json"
NEFF = 262.2710843373494
SEEDS = (20261051, 20261052, 20261053, 20261054)


def main() -> int:
    t0 = time.time()
    crit = float(Fd.ppf(0.95, 2 * NEFF, 2 * NEFF))
    rows = []
    for sd in SEEDS:
        rng = np.random.default_rng(sd)
        q = []
        for _ in range(10):
            _, m = RDC.stats(*RDC.bartlett(rng, NEFF, 2_000_000, RDC.chol_sigma(1.0, 0.13)))
            q.append(m)
        q05 = float(np.quantile(np.concatenate(q), 0.05))
        hit = n = 0
        for _ in range(20):
            r, m = RDC.stats(*RDC.bartlett(rng, NEFF, 500_000, RDC.chol_sigma(1.1, 0.1 / 2.1)))
            hit += int(((r > crit) & (m < q05)).sum()); n += r.size
        p = hit / n
        rows.append({"seed": sd, "q05": q05, "power_percent": 100 * p, "mc_se_percent": 100 * float(np.sqrt(p * (1 - p) / n)), "trials": n, "q05_draws": 20_000_000})
        print(f"  seed {sd}: q05 {q05:.6f}, power {100 * p:.4f} +/- {100 * np.sqrt(p * (1 - p) / n):.4f} %", flush=True)
    pp = np.array([r["power_percent"] for r in rows])
    doc = {"schema": "lunar-ice/n-sensitivity-f2point/1", "generated_utc": datetime.now(timezone.utc).isoformat(),
           "generator": "backend/scripts/n_sensitivity_f2point.py", "seed": list(SEEDS), "N_eff": NEFF, "crit95": crit,
           "alternative": "CPR 1.1, DOP = |q| = 0.0476 (minimum)", "runs": rows,
           "mean_power_percent": float(pp.mean()), "sd_between_seeds_percent": float(pp.std(ddof=1)),
           "reference_region_design_curve_percent": 0.5775, "reference_n_sensitivity_real_percent": 0.5245,
           "run_info": {**run_info(), "wall_s": round(time.time() - t0, 1)}}
    OUT.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print(f"  mean {pp.mean():.4f} % (sd between seeds {pp.std(ddof=1):.4f}); wrote {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
