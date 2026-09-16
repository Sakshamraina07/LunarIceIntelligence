"""
assert_manuscript_claims.py -- G30. The Section V-VI sensitivity claims are the
artifacts' numbers, not remembered ones.

    python backend/scripts/assert_manuscript_claims.py [--inject <check>]

Seven artifacts were emitted so the manuscript's sensitivity sentences would
have a source (Section 5 of the repository pass); an artifact nobody asserts
against is a file, not a gate. Each check below states the CLAIM the manuscript
makes and asserts it against the artifact that produced it -- digits where the
computation is deterministic, the claim where it is a Monte Carlo whose digits
depend on RNG state (kclutter, patch_bias: see those scripts).

    S1 slepian     2WT = 6.77, participation ratio 7.34, Hamming 4.07;
                   Hamming < measured spatial arm < rectangular
    S2 table5      the row at the raw ENL 5.83 reproduces the screened field's
                   N = 13.72, floor 1.895 and FP 17.79 %
    S3 background  FP rises monotonically with the assumed background and
                   spans more than a hundred-fold from 0.3 to 0.9
    S4 correlated  17.6 / 14.1 / 6.3 / 1.9 % at |rho| = 0 / 0.5 / 0.8 / 0.9
    S5 joint       the joint rate at N = 14, CPR 0.7 prints as 1.8 %; the
                   Monte Carlo marginal is within 0.5 points of F
    S6 kclutter    |shared - F| <= 3 sigma_MC at the recorded trial count for
                   every order, and <= 0.02 points; independent rows span
                   27-40 % over nu = 1.5..10
    S7 patch_bias  correlation inflates the 16x16 mode above 6 by more than
                   the 32x32 mode; the uncorrelated control is 6 at both
    S8 stationary  four blocks, the 16x16 mode ranging 3.3 to 8.0

Fails on purpose with --inject <check>.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
D = BASE_DIR / "docs"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

CHECKS = ("slepian", "table5", "background", "correlated", "joint", "kclutter",
          "patch_bias", "stationarity")


def load(name):
    return json.loads((D / f"{name}.json").read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inject", choices=CHECKS, default=None)
    args = ap.parse_args()
    inj = args.inject
    bad = []

    def note(ok, label):
        print(f"  {'ok ' if ok else 'BAD'}  {label}")
        if not ok:
            bad.append(label)

    print("=" * 78)
    print("G30 — manuscript sensitivity claims against their artifacts")
    print("=" * 78)

    # S1
    s = load("slepian_ceiling")
    twt, pr, hm, meas = s["two_WT_asymptotic"], s["participation_ratio_rectangular"], \
        s["enl_hamming_054"], s["measured_spatial_arm"]
    if inj == "slepian":
        pr = 7.0
    note(round(twt, 2) == 6.77, f"S1 2WT {twt:.4f} prints 6.77")
    note(round(pr, 2) == 7.34, f"S1 participation ratio {pr:.4f} prints 7.34")
    note(round(hm, 2) == 4.07, f"S1 Hamming {hm:.4f} prints 4.07")
    note(hm < meas < pr, f"S1 ordering Hamming {hm:.2f} < measured {meas:.2f} < rectangular {pr:.2f}")

    # S2
    t = load("table5_sensitivity")
    det = load("detection_statistics")
    row = min(t["rows"], key=lambda r: abs(r["raw_enl"] - 5.83))
    n = row["N"] + (1.0 if inj == "table5" else 0.0)
    note(abs(row["raw_enl"] - 5.83) < 1e-9, "S2 a row exists at raw ENL 5.83")
    note(abs(n - 13.72) < 0.01, f"S2 its N {n:.4f} is the screened field's 13.72")
    note(abs(row["floor_95"] - det["per_pixel_significance"]["floor_at_low_N"]) < 1e-3,
         f"S2 its floor {row['floor_95']:.4f} matches detection_statistics "
         f"{det['per_pixel_significance']['floor_at_low_N']}")
    note(round(row["fp_percent_at_cpr_0p7"], 2) == 17.79, f"S2 its FP {row['fp_percent_at_cpr_0p7']:.4f} prints 17.79")

    # S3
    b = load("background_cpr_sweep")
    fps = [r["fp_percent"] for r in b["rows"]]
    if inj == "background":
        fps[2], fps[3] = fps[3], fps[2]
    note(all(x < y for x, y in zip(fps, fps[1:])), "S3 FP is monotone in the assumed background")
    note(fps[-1] / fps[0] > 100, f"S3 span 0.3 -> 0.9 is {fps[-1] / fps[0]:.0f}x (> 100)")
    fp07 = next(r["fp_percent"] for r in b["rows"] if abs(r["true_cpr"] - 0.7) < 1e-9)
    note(round(fp07, 2) == 17.79, f"S3 FP at 0.7 {fp07:.4f} prints 17.79")

    # S4
    c = load("correlated_ratio")
    want = {0.0: 17.6, 0.5: 14.1, 0.8: 6.3, 0.9: 1.9}
    for r in c["rows"]:
        if r["rho"] in want:
            v = r["fp_percent"] + (1.0 if inj == "correlated" and r["rho"] == 0.5 else 0.0)
            note(round(v, 1) == want[r["rho"]], f"S4 |rho| {r['rho']}: {v:.3f} prints {want[r['rho']]}")

    # S5
    j = load("joint_criterion")
    jr = j["headline"]["joint_fp_percent"] + (0.3 if inj == "joint" else 0.0)
    note(round(jr, 1) == 1.8, f"S5 joint rate {jr:.4f} prints 1.8 %")
    note(abs(j["headline"]["marginal_fp_percent_monte_carlo"] - j["marginal_fp_percent_analytic_F"]) < 0.5,
         f"S5 MC marginal {j['headline']['marginal_fp_percent_monte_carlo']:.3f} within 0.5 of F "
         f"{j['marginal_fp_percent_analytic_F']:.3f}")

    # S6
    k = load("kclutter")
    p = k["fp_percent_F_gaussian"] / 100.0
    sigma = 100.0 * math.sqrt(p * (1 - p) / k["trials_per_row"])
    diffs = [abs(r["fp_shared_percent"] - k["fp_percent_F_gaussian"]) for r in k["rows"]]
    if inj == "kclutter":
        diffs[0] = 0.1
    note(max(diffs) <= 3 * sigma, f"S6 max |shared - F| {max(diffs):.4f} <= 3 sigma_MC {3 * sigma:.4f} "
                                  f"at {k['trials_per_row']:,} trials")
    note(max(diffs) <= 0.02, f"S6 max |shared - F| {max(diffs):.4f} <= 0.02 points (the sentence)")
    fin = [r["fp_independent_percent"] for r in k["rows"] if r["nu"] is not None]
    note(27.0 <= min(fin) and max(fin) <= 40.0, f"S6 independent rows span {min(fin):.2f}-{max(fin):.2f} % within 27-40")

    # S7
    pb = load("patch_bias")
    c16, c32 = pb["correlated"]["16"]["mode"], pb["correlated"]["32"]["mode"]
    u16, u32 = pb["uncorrelated_control"]["16"], pb["uncorrelated_control"]["32"]
    if inj == "patch_bias":
        c16 = 6.0
    note(c16 - 6.0 > c32 - 6.0 > -0.15, f"S7 correlated 16x16 {c16:.2f} above 32x32 {c32:.2f} above ~6")
    note(c16 > 6.3, f"S7 16x16 mode {c16:.2f} inflated above 6.3")
    note(abs(u16 - 6.0) < 0.15 and abs(u32 - 6.0) < 0.15, f"S7 uncorrelated control {u16:.2f} / {u32:.2f} at 6")

    # S8
    st = load("stationarity")
    lo, hi = st["enl_min"], st["enl_max"] + (0.5 if inj == "stationarity" else 0.0)
    note(st["n_blocks_used"] == 4, f"S8 {st['n_blocks_used']} blocks with coverage (manuscript: four)")
    note(round(lo, 1) == 3.3 and round(hi, 1) == 8.0, f"S8 mode ranges {lo:.2f} to {hi:.2f} (prints 3.3 to 8.0)")

    print()
    if bad:
        print(f"  GATE FAIL — {len(bad)} claim(s) not backed by their artifact")
        return 1
    print("  GATE PASS — every sensitivity claim is the number its artifact holds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
