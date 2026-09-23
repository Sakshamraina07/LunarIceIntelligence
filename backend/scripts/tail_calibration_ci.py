"""
tail_calibration_ci.py -- intervals on the held-out tail calibration, and whether
"11 of 109 blocks above nominal" is consistent with exact calibration.
(council work order, Task 6)

    python backend/scripts/tail_calibration_ci.py

Reads stokes_from_slc.json::results.t3e.180_deg.tail_calibration.per_block.

1. Block-bootstrap 95 % intervals (blocks resampled with replacement, B = 10 000)
   on the median-over-blocks and the pooled rejection rates at nominal 1, 5
   and 10 %.
2. Under EXACT calibration a block's held-out rejection count is binomial at
   the nominal rate -- but over correlated cells. Each block's effective count
   n_eff = n_test / A_b, with A_b the block's own integrated autocorrelation
   area of ln CPR (stokes_from_slc.py records it per block). Then
   P(block above nominal) = P(Bin(n_eff, alpha) > alpha n_eff) per block, the
   number of blocks above nominal is Poisson-binomial over the blocks, and the
   observed count is set against that exact distribution (both tails). The
   pooled rate is tested the same way with the summed effective count.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.stats import binom, norm

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "tail_calibration_ci.json"
SEED = 20261004
B = 10_000
SOURCES = {"20200808_64px": "docs/stokes_from_slc.json",
           "20200808_32px": "docs/stokes_from_slc_block32.json",
           "20200305_32px": "docs/stokes_from_slc_20200305_block32.json"}

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def poisson_binomial(p: np.ndarray) -> np.ndarray:
    d = np.zeros(p.size + 1)
    d[0] = 1.0
    for q in p:
        d[1:] = d[1:] * (1 - q) + d[:-1] * q
        d[0] *= (1 - q)
    return d


def analyse(per: list, rng) -> dict:
    n = np.array([b["n_test"] for b in per], dtype=float)
    area = np.array([b["corr_area_px"] for b in per], dtype=float)
    neff = n / np.maximum(area, 1.0)
    out = {"blocks": len(per), "n_test_total": int(n.sum()),
           "corr_area_px": {"median": float(np.median(area)),
                            "iqr": [float(np.percentile(area, 25)), float(np.percentile(area, 75))]},
           "n_eff_per_block": {"median": float(np.median(neff)),
                               "iqr": [float(np.percentile(neff, 25)), float(np.percentile(neff, 75))]},
           "levels": {}}
    idx = rng.integers(0, len(per), (B, len(per)))
    for key, a in (("1pct", 0.01), ("5pct", 0.05), ("10pct", 0.10)):
        rej = np.array([b["rejection"][key] for b in per])
        med_b = np.median(rej[idx], axis=1)
        pool_b = (rej[idx] * n[idx]).sum(axis=1) / n[idx].sum(axis=1)
        pooled = float((rej * n).sum() / n.sum())
        above = int((rej > a).sum())
        # exact calibration: per-block P(above), Poisson-binomial count
        ne = np.maximum(np.rint(neff).astype(int), 1)
        p_above = np.array([1.0 - binom.cdf(np.floor(a * k), k, a) for k in ne])
        dist = poisson_binomial(p_above)
        cdf = np.cumsum(dist)
        p_low = float(cdf[above])
        p_high = float(1.0 - (cdf[above - 1] if above > 0 else 0.0))
        # pooled rate against the nominal, effective count summed
        neff_tot = float(neff.sum())
        z = (pooled - a) / np.sqrt(a * (1 - a) / neff_tot)
        out["levels"][key] = {
            "nominal": a,
            "median_over_blocks": float(np.median(rej)),
            "median_ci95": [float(np.percentile(med_b, 2.5)), float(np.percentile(med_b, 97.5))],
            "pooled": pooled,
            "pooled_ci95": [float(np.percentile(pool_b, 2.5)), float(np.percentile(pool_b, 97.5))],
            "blocks_above_nominal": above,
            "expected_above_if_exactly_calibrated": float(dist @ np.arange(dist.size)),
            "p_value_this_few_or_fewer": p_low,
            "p_value_this_many_or_more": p_high,
            "pooled_vs_nominal_z": float(z),
            "pooled_vs_nominal_p_two_sided": float(2 * norm.sf(abs(z))),
            "verdict": ("fewer blocks above nominal than exact calibration predicts: the "
                        "model is conservative here" if p_low < 0.025 else
                        "more blocks above nominal than exact calibration predicts: the "
                        "model is anti-conservative here" if p_high < 0.025 else
                        "consistent with exact calibration")}
    return out


def main() -> int:
    rng = np.random.default_rng(SEED)
    res = {}
    for tag, rel in SOURCES.items():
        p = BASE_DIR / rel
        if not p.is_file():
            res[tag] = {"missing": rel}
            continue
        t = json.loads(p.read_text(encoding="utf-8"))["results"]["t3e"]["180_deg"]["tail_calibration"]
        per = t.get("per_block", [])
        if not per:
            res[tag] = {"blocks": 0, "note": "no blocks on this pass at this size"}
            continue
        res[tag] = {"source": rel, **analyse(per, rng)}
        for k, v in res[tag]["levels"].items():
            print(f"  {tag} {k}: pooled {100 * v['pooled']:.2f} % [{100 * v['pooled_ci95'][0]:.2f}, "
                  f"{100 * v['pooled_ci95'][1]:.2f}], median {100 * v['median_over_blocks']:.2f} % "
                  f"[{100 * v['median_ci95'][0]:.2f}, {100 * v['median_ci95'][1]:.2f}]; above nominal "
                  f"{v['blocks_above_nominal']} vs expected {v['expected_above_if_exactly_calibrated']:.1f} "
                  f"(p<= {v['p_value_this_few_or_fewer']:.2e}, p>= {v['p_value_this_many_or_more']:.2e}) "
                  f"-> {v['verdict']}", flush=True)
    OUT.write_text(json.dumps({
        "schema": "lunar-ice/tail-calibration-ci/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/tail_calibration_ci.py",
        "seed": SEED, "bootstrap_B": B, "unit": "block, resampled with replacement",
        "effective_count": "n_test / the block's integrated autocorrelation area of ln CPR",
        "reference_distribution": ("binomial, at each block's effective sample count: "
                                   "P(block above nominal) = P(Bin(n_eff, alpha) > alpha n_eff); "
                                   "the count of blocks above nominal is Poisson-binomial"),
        "results": res, "run_info": run_info()}, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
