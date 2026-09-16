"""
recompute_manuscript_tables.py -- the manuscript's closed-form tables, rebuilt
from the pipeline's own code and diffed against the printed cells.

    python backend/scripts/recompute_manuscript_tables.py [--tex PATH]

WHY THIS IS NOT THE SAME AS THE NUMBER AUDIT
--------------------------------------------
`audit_manuscript_numbers.py` asks whether a printed figure equals a value
stored in an artifact. That catches transcription, and it is blind to the case
where the artifact and the manuscript inherited the same arithmetic mistake from
the same script.

This parses the tables OUT OF THE .tex and recomputes every cell from the
functions the pipeline itself uses -- `detection_statistics.ratio_sd`,
`floor_95`, `exceedance` for the sampling statistics, and
`published_moments.rel_sd`, `skewness`, `excess_kurtosis` inverted for the
Mini-RF moments. Nothing is read from an artifact, so an artifact cannot
launder an error into agreement.

Three tables:
  Table II   sampling statistics, 7 rows x 5 columns
  Table III  the sensitivity block, 4 rows x 3 columns
  Table IV   24 Mini-RF inversions and their three medians

Each cell is compared at the precision the manuscript prints it. Where a cell
matches only at the unrounded N (the table prints 8.75 for a median of
8.754410943745066), both are reported and the row says which convention
reproduces the printed digit -- the script does not choose.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_TEX = "Claude outputs/grsl/dfsar_detection_limits_submission.tex"
OUT = BASE_DIR / "docs" / "table_recompute.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        "_" + name, Path(__file__).with_name(name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_" + name] = mod
    spec.loader.exec_module(mod)
    return mod


DS = _load("detection_statistics")
PM = _load("published_moments")

#: The unrounded value behind each printed N, from the measurement that produced
#: it. Only the four that are rounded in print appear here.
UNROUNDED = {8.75: 8.754410943745066, 13.72: 13.716639679503347,
             19.77: 19.76772534356128, 6.77: 6.773174590024859}


def cells(row: str) -> list:
    """The cells of one LaTeX table row, stripped of markup."""
    row = row.split(r"\\")[0]
    out = []
    for c in row.split("&"):
        c = re.sub(r"\\textbf\{([^}]*)\}", r"\1", c)
        c = re.sub(r"\\,|\\%|\\!|\$|\{|\}|\\emph|\\text", "", c)
        out.append(c.strip())
    return out


def num(s: str):
    s = re.sub(r"[^\d.\-]", "", s)
    try:
        return float(s)
    except ValueError:
        return None


def dec(s: str) -> int:
    s = re.sub(r"[^\d.]", "", s)
    return len(s.split(".")[1]) if "." in s else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tex", default=DEFAULT_TEX)
    ap.add_argument("--assert-none-differ", action="store_true",
                    help="exit non-zero if any cell differs, or if a table "
                         "parses to fewer cells than it has")
    ap.add_argument("--inject", choices=("cell", "row"),
                    help="break one cell, or drop a row, to prove the check runs")
    args = ap.parse_args()
    tex = (BASE_DIR / args.tex).read_text(encoding="utf-8", errors="replace")
    raw_lines = [re.sub(r"(?<!\\)%.*", "", ln) for ln in tex.splitlines()]
    # A table row may be wrapped across source lines -- the bolded operating
    # point is -- so rows are joined up to their terminating \\ before parsing.
    # Without this the 13.72 row is silently invisible: five cells of the
    # manuscript's most load-bearing table, unchecked.
    lines, buf = [], ""
    for ln in raw_lines:
        buf = (buf + " " + ln).strip() if buf else ln
        if r"\\" in buf or "&" not in buf:
            lines.append(buf)
            buf = ""
    if buf:
        lines.append(buf)

    print("=" * 78)
    print(f"RECOMPUTE — the manuscript's tables from the pipeline's own functions")
    print("=" * 78)
    print(f"  {args.tex}")

    report = {"schema": "lunar-ice/table-recompute/1",
              "generated_utc": datetime.now(timezone.utc).isoformat(),
              "generator": "backend/scripts/recompute_manuscript_tables.py",
              "manuscript": args.tex,
              "recomputed_from": ["backend/scripts/detection_statistics.py",
                                  "backend/scripts/published_moments.py"],
              "tables": {}}
    total_bad = 0

    # ---------------- Table II ------------------------------------------
    print("\n  TABLE II — sampling statistics")
    print(f"    {'N':>7} {'cell':<10} {'printed':>9} {'at printed N':>13} "
          f"{'at measured N':>14}  verdict")
    rows2, bad2 = [], 0
    for ln in lines:
        c = cells(ln)
        if len(c) != 6 or num(c[0]) is None or "rel" in ln:
            continue
        n = num(c[0])
        if n is None or not (4.0 <= n <= 40.0) or "." not in c[0]:
            continue
        nu = UNROUNDED.get(n, n)
        want = {"rel_sd": c[1], "bias": c[2], "crit_95": c[3],
                "p_0.7": c[4], "p_0.5": c[5]}
        got_p = {"rel_sd": DS.ratio_sd(n), "bias": n / (n - 1),
                 "crit_95": DS.floor_95(n),
                 "p_0.7": DS.exceedance(n, 0.7), "p_0.5": DS.exceedance(n, 0.5)}
        got_m = {"rel_sd": DS.ratio_sd(nu), "bias": nu / (nu - 1),
                 "crit_95": DS.floor_95(nu),
                 "p_0.7": DS.exceedance(nu, 0.7), "p_0.5": DS.exceedance(nu, 0.5)}
        for k, printed in want.items():
            p = num(printed)
            d = dec(printed)
            ok_p = p is not None and round(got_p[k], d) == round(p, d)
            ok_m = p is not None and round(got_m[k], d) == round(p, d)
            verdict = ("MATCH (printed N)" if ok_p else
                       "MATCH (measured N only)" if ok_m else "DIFFERS")
            if not ok_p and not ok_m:
                bad2 += 1
            rows2.append({"N": n, "N_measured": nu, "cell": k, "printed": p,
                          "at_printed_N": round(got_p[k], d + 2),
                          "at_measured_N": round(got_m[k], d + 2),
                          "verdict": verdict})
            if not ok_p:
                print(f"    {n:>7.2f} {k:<10} {printed:>9} "
                      f"{round(got_p[k], d + 2):>13} {round(got_m[k], d + 2):>14}"
                      f"  {verdict}")
    print(f"    {len(rows2)} cells; {sum(1 for r in rows2 if r['verdict'].startswith('MATCH (printed'))}"
          f" reproduce at the printed N, "
          f"{sum(1 for r in rows2 if 'measured N only' in r['verdict'])} only at the "
          f"unrounded one, {bad2} differ")
    report["tables"]["II_sampling_statistics"] = {"cells": rows2, "differ": bad2}
    total_bad += bad2

    # ---------------- Table III (sensitivity block) ----------------------
    print("\n  TABLE III — sensitivity to the raw ENL estimate")
    rows3, bad3 = [], 0
    scale = 13.72 / 5.83
    for ln in lines:
        m = re.search(r"mode, (\d+\.\d+)|amplitude-domain, (\d+\.\d+)|"
                      r"screening mask, (\d+\.\d+)", ln)
        if not m:
            continue
        raw = float(next(g for g in m.groups() if g))
        # `crit.\ 2.64` -- the LaTeX inter-word space is a BACKSLASH followed by
        # a space, and leaving it in made the critical-value column invisible to
        # the parser: four cells of a four-row table, silently unchecked.
        flat = re.sub(r"\\,|\\!|\\%|\\ |\$|\{|\}|\\textbf", " ", ln)
        mn = re.search(r"N\s*=\s*(\d+\.?\d*)", flat)
        mc = re.search(r"crit\.?\s*(\d+\.\d+)", flat)
        mp = re.search(r"P_?\s*0\.7\s*(\d+\.\d+)", flat)
        n = raw * scale
        for label, mm, val in (("N", mn, n), ("crit", mc, DS.floor_95(n)),
                               ("P_0.7", mp, DS.exceedance(n, 0.7))):
            if not mm:
                continue
            printed = mm.group(1)
            d = dec(printed)
            ok = round(val, d) == round(float(printed), d)
            if not ok:
                bad3 += 1
                print(f"    raw {raw}: {label} printed {printed}, computed "
                      f"{round(val, d + 2)}  DIFFERS")
            rows3.append({"raw_enl": raw, "cell": label, "printed": float(printed),
                          "computed": round(val, d + 2),
                          "verdict": "MATCH" if ok else "DIFFERS"})
    print(f"    {len(rows3)} cells; {len(rows3) - bad3} match, {bad3} differ")
    report["tables"]["III_sensitivity"] = {"cells": rows3, "differ": bad3,
                                           "scaling": "N = raw x 13.72 / 5.83"}
    total_bad += bad3

    # ---------------- Table IV (Mini-RF inversions) ----------------------
    print("\n  TABLE IV — 24 Mini-RF inversions and three medians")
    rows4, bad4 = [], 0
    n_sd, n_sk, n_ku = [], [], []
    for ln in lines:
        c = cells(ln)
        if len(c) != 8 or num(c[1]) is None or not c[0] or c[0].startswith("Crater"):
            continue
        name, mu, sd, g1, g2 = c[0], num(c[1]), num(c[2]), num(c[3]), num(c[4])
        if None in (mu, sd, g1, g2):
            continue
        got = {"N_sigma": PM._invert(PM.rel_sd, sd / mu, 2.0001, 1e6, name),
               "N_gamma1": PM._invert(PM.skewness, g1, 3.0001, 1e6, name),
               "N_gamma2": PM._invert(PM.excess_kurtosis, g2, 4.0001, 1e6, name)}
        n_sd.append(got["N_sigma"]); n_sk.append(got["N_gamma1"])
        n_ku.append(got["N_gamma2"])
        for k, printed in zip(got, (c[5], c[6], c[7])):
            d = dec(printed)
            ok = round(got[k], d) == round(float(printed), d)
            if not ok:
                bad4 += 1
                print(f"    {name:<20} {k:<9} printed {printed}, computed "
                      f"{round(got[k], d + 2)}  DIFFERS")
            rows4.append({"crater": name, "cell": k, "printed": float(printed),
                          "computed": round(got[k], d + 2),
                          "verdict": "MATCH" if ok else "DIFFERS"})
    import statistics
    meds = {"N_sigma": statistics.median(n_sd), "N_gamma1": statistics.median(n_sk),
            "N_gamma2": statistics.median(n_ku)}
    printed_meds = None
    for ln in lines:
        if ln.strip().startswith("median"):
            got = [num(x) for x in cells(ln) if num(x) is not None]
            if len(got) == 3:
                printed_meds = got
    for k, p in zip(meds, printed_meds or []):
        ok = round(meds[k], 2) == round(p, 2)
        if not ok:
            bad4 += 1
            print(f"    median {k:<9} printed {p}, computed {meds[k]:.4f}  DIFFERS")
        rows4.append({"crater": "median", "cell": k, "printed": p,
                      "computed": round(meds[k], 4),
                      "verdict": "MATCH" if ok else "DIFFERS"})
    print(f"    {len(rows4)} cells ({len(n_sd)} craters x 3 + 3 medians); "
          f"{len(rows4) - bad4} match, {bad4} differ")
    report["tables"]["IV_published_moments"] = {"cells": rows4, "differ": bad4,
                                                "craters": len(n_sd)}
    total_bad += bad4

    report["total_cells"] = len(rows2) + len(rows3) + len(rows4)
    report["total_differ"] = total_bad
    # A table that parses to FEWER cells than it has is the quiet failure this
    # check is most exposed to: a wrapped row or a LaTeX spacing macro silently
    # removes cells from the comparison and the summary still reads "0 differ".
    # Both have happened here. So the expected counts are asserted too.
    EXPECT = {"II_sampling_statistics": 35, "III_sensitivity": 12,
              "IV_published_moments": 27}
    short = {k: (len(report["tables"][k]["cells"]), v) for k, v in EXPECT.items()
             if len(report["tables"][k]["cells"]) != v}
    if args.inject == "cell":
        print("\n  --inject cell: one cell marked as differing\n")
        total_bad += 1
    if args.inject == "row":
        print("\n  --inject row: one table parsed short\n")
        short["II_sampling_statistics"] = (30, 35)
    report["expected_cells"] = EXPECT
    report["tables_parsed_short"] = {k: {"parsed": a, "expected": b}
                                     for k, (a, b) in short.items()}
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n  {report['total_cells']} cells recomputed, {total_bad} differ from print")
    for k, (got, want) in short.items():
        print(f"  TABLE PARSED SHORT: {k} gave {got} cells, expected {want}")
    print(f"  wrote {OUT.relative_to(BASE_DIR)}")

    if args.assert_none_differ or args.inject:
        if total_bad or short:
            print("\n  GATE FAIL — a printed cell does not follow from the "
                  "pipeline's own arithmetic, or a table was parsed short.")
            return 1
        print("\n  GATE PASS — every cell of Tables II, III and IV recomputes "
              "from the pipeline's functions at the precision printed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
