"""
patch_bias.py -- what lag correlation does to the mode estimator, by patch size.

    python backend/scripts/patch_bias.py

WHY
---
The measured ENL falls with patch size (5.30 at 16x16, 2.64 at 32x32 for LH).
Two biases pull in opposite directions: texture inside a patch inflates the
variance and depresses the estimate, most at large patches; lag correlation
biases the sample variance LOW and inflates the estimate, most at small
patches. This isolates the second on pure correlated speckle whose ENL is known
to be 6.00 exactly: an AR(1) complex field with this product's lag-one
correlations (0.84 azimuth, 0.58 range), six independent looks, the identical
patch_ratios / mode_of pipeline, and an uncorrelated Gamma(6, 1/6) control.

    manuscript:  16x16 mode 6.61,  32x32 mode 6.01,  uncorrelated 6.00 at both

PORTED, NOT RE-DERIVED. The reference block (Claude outputs/
reviewer2_computations.py, block B3) ran AFTER blocks C1 and B2 had consumed
the generator seeded 11, and its digits depend on that state. So this script
replays exactly the draws those blocks made -- same distributions, same shapes,
same order, results discarded -- before running B3 verbatim, and records that
it did. A fresh default_rng(11) would give different fourth digits and the
manuscript audit would call a correct port a mismatch.

The gate (assert_patch_bias.py) asserts the CLAIM, not the digits: the 16x16
mode on correlated speckle sits above 6 by more than the 32x32 mode does, and
the uncorrelated control sits at 6 at both sizes.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "patch_bias.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

SEED = 11
N_LOOKS = 6
RHO_AZ, RHO_RG = 0.84, 0.58
SHAPE = (1024, 2048)
PATCHES = (8, 16, 32, 64)


def _measure_enl():
    spec = importlib.util.spec_from_file_location(
        "_measure_enl", Path(__file__).with_name("measure_enl.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.patch_ratios, mod.mode_of


def replay_reference_draws(rng) -> dict:
    """Advance the generator exactly as blocks C1 and B2 of the reference did."""
    M = 1_000_000
    rng.gamma(14, 1 / 14, M); rng.gamma(14, 1 / 14, M)                   # C1 G1, G2
    for nu in (1.5, 2, 5, 10, 1e9):
        rng.gamma(nu, 1 / nu, M); rng.gamma(nu, 1 / nu, M)               # C1 T, Tb
    for _ in range(4):                                                    # B2 four rows
        for _ in range(2):                                                # z1 then z2
            rng.normal(size=(600_000, 14)); rng.normal(size=(600_000, 14))
    return {"C1": "2 + 5x2 gamma draws of 1e6", "B2": "4 rows x (z1, z2) x (re, im) "
            "normal draws of (600000, 14)", "why": "the reference's B3 digits depend "
            "on this state; replaying it makes the port reproduce them"}


def ar1_field(rng, shape, ra, rr):
    """Verbatim from the reference: AR(1) along rows, then along columns."""
    w = (rng.normal(size=shape) + 1j * rng.normal(size=shape)) / np.sqrt(2)
    for i in range(1, shape[0]):
        w[i] = ra * w[i - 1] + np.sqrt(1 - ra ** 2) * w[i]
    for j in range(1, shape[1]):
        w[:, j] = rr * w[:, j - 1] + np.sqrt(1 - rr ** 2) * w[:, j]
    return w


def main() -> int:
    patch_ratios, mode_of = _measure_enl()
    rng = np.random.default_rng(SEED)
    replay = replay_reference_draws(rng)

    print("=" * 78)
    print(f"PATCH BIAS — pure correlated speckle, N = {N_LOOKS}, rho az {RHO_AZ} rg {RHO_RG}")
    print("=" * 78)
    I = np.zeros(SHAPE)
    for _ in range(N_LOOKS):
        I += np.abs(ar1_field(rng, SHAPE, RHO_AZ, RHO_RG)) ** 2
    I /= N_LOOKS
    ones = np.ones(SHAPE, bool)
    rows = {}
    for p in PATCHES:
        r = patch_ratios(I, ones, p)
        rows[str(p)] = {"mode": float(mode_of(r)), "median": float(np.median(r)), "n": int(r.size)}
        print(f"  patch {p:>2}: mode {rows[str(p)]['mode']:5.2f}  median "
              f"{rows[str(p)]['median']:5.2f}   (true per-pixel ENL {N_LOOKS:.2f})")
    I0 = rng.gamma(N_LOOKS, 1 / N_LOOKS, size=SHAPE)
    control = {}
    for p in (16, 32):
        control[str(p)] = float(mode_of(patch_ratios(I0, ones, p)))
        print(f"  uncorrelated control patch {p}: mode {control[str(p)]:5.2f}")
    # the measured lag-one of the field, as a check on the construction
    c = (I - I.mean())
    l_az = float((c[1:] * c[:-1]).mean() / (c ** 2).mean())
    l_rg = float((c[:, 1:] * c[:, :-1]).mean() / (c ** 2).mean())
    print(f"  intensity lag-1 of the field: az {l_az:.3f}  rg {l_rg:.3f}")

    OUT.write_text(json.dumps({
        "schema": "lunar-ice/patch-bias/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/patch_bias.py",
        "seed": SEED, "n_looks": N_LOOKS, "rho_az": RHO_AZ, "rho_rg": RHO_RG,
        "shape": list(SHAPE), "rng_replay": replay,
        "correlated": rows, "uncorrelated_control": control,
        "field_intensity_lag1": {"azimuth": l_az, "range": l_rg},
        "claim": "lag correlation inflates the small-patch mode above the true ENL; "
                 "the 32x32 mode is near 6 and the uncorrelated control is 6 at both",
        "note": "true per-pixel ENL is exactly 6.00; field rho are the manuscript's "
                "rounded 0.84 / 0.58, as in the reference",
    }, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
