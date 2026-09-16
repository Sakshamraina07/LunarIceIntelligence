"""
literature_search_gate.py -- G29. The literature claim is checkable.

    python backend/scripts/literature_search_gate.py [--inject WHICH]

WHY
---
The manuscript's central negative claim about the field is that no lunar CPR ice
study reports the measured ENL of the product it analysed, a per-pixel floor at a
stated look count, or a noise exceedance rate for the CPR criterion. "We searched
and found none" is the least checkable sentence a paper can contain, and the
easiest to be wrong about.

`docs/literature_search_record.csv` is the search itself: every paper screened,
its venue, how deeply it was read, and its answer on each of the three criteria.
A reader who disagrees can point at a row. This gate asserts the counts the
manuscript prints are the counts in that file, so the sentence and the record
cannot drift apart.

  34 unique screened -> 9 excluded -> 25 relevant
  of the 25 relevant: 12 read in full text, 12 at abstract, 1 inaccessible
  0 report measured ENL, 0 report a per-pixel floor, 0 report an FP rate

THE INACCESSIBLE ROW IS COUNTED AND NAMED, not dropped. One paper could not be
read in full; a search that silently excluded it would be claiming a completeness
it does not have.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
SRC = BASE_DIR / "Claude outputs" / "literature_search_record.csv"
DEST = BASE_DIR / "docs" / "literature_search_record.csv"
OUT = BASE_DIR / "docs" / "literature_search.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

EXPECT = {"unique": 34, "excluded": 9, "relevant": 25,
          "full_text": 12, "abstract": 12, "inaccessible": 1}
CRITERIA = ("reports_measured_enl_of_analysed_product",
            "reports_perpixel_floor_at_stated_N",
            "reports_fp_rate_for_cpr_criterion")
INJECTIONS = ("count", "criterion", "dropped")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inject", choices=INJECTIONS)
    args = ap.parse_args()

    print("=" * 78)
    print("G29 — the literature-search record supports the claim made from it")
    print("=" * 78)

    if not DEST.is_file() and SRC.is_file():
        shutil.copyfile(SRC, DEST)
        print(f"  copied {SRC.name} -> {DEST.relative_to(BASE_DIR)}")
    if not DEST.is_file():
        print(f"  GATE FAIL — {DEST.relative_to(BASE_DIR)} is absent, so the "
              f"claim has no record behind it.")
        return 1

    rows = list(csv.DictReader(DEST.read_text(encoding="utf-8-sig").splitlines()))
    if args.inject == "dropped":
        print("  --inject dropped: the inaccessible row silently removed\n")
        rows = [r for r in rows
                if "NOT ACCESSED" not in (r.get("screen_level") or "")]
    if args.inject == "criterion":
        print("  --inject criterion: one paper marked as reporting an FP rate\n")
        rows = [dict(r) for r in rows]
        for r in rows:
            if r["relevant_lunar_cpr_ice_study"].strip() == "yes":
                r["reports_fp_rate_for_cpr_criterion"] = "yes"
                break

    relevant = [r for r in rows
                if (r.get("relevant_lunar_cpr_ice_study") or "").strip() == "yes"]
    levels = Counter((r.get("screen_level") or "").strip() for r in relevant)
    got = {
        "unique": len(rows),
        "excluded": len(rows) - len(relevant),
        "relevant": len(relevant),
        "full_text": sum(v for k, v in levels.items() if k.startswith("full text")),
        "abstract": levels.get("abstract", 0),
        "inaccessible": sum(v for k, v in levels.items() if "NOT ACCESSED" in k),
    }
    if args.inject == "count":
        print("  --inject count: the manuscript's unique-paper count moved\n")
        got["unique"] += 1

    bad: list[str] = []
    print(f"  {'quantity':<16}{'record':>9}{'claimed':>9}")
    for k, want in EXPECT.items():
        print(f"  {k:<16}{got[k]:>9}{want:>9}"
              + ("" if got[k] == want else "   <- DISAGREES"))
        if got[k] != want:
            bad.append(f"{k}: the record holds {got[k]}, the manuscript claims {want}")

    print()
    for c in CRITERIA:
        yes = [r for r in relevant if (r.get(c) or "").strip().lower() == "yes"]
        print(f"  {c:<46} yes = {len(yes)}")
        if yes:
            bad.append(f"{len(yes)} relevant paper(s) DO report {c} "
                       f"(e.g. {yes[0].get('first_author')}); the manuscript's "
                       f"0/0/0 claim is not what the record says")

    if got["full_text"] + got["abstract"] + got["inaccessible"] != got["relevant"]:
        bad.append("the screen-level breakdown does not sum to the relevant count")

    print()
    if args.inject:
        if bad:
            print(f"  INJECTION CAUGHT ({args.inject}). The gate works.")
            for b in bad:
                print(f"    {b}")
            return 0
        print(f"  INJECTION NOT CAUGHT ({args.inject}).")
        return 1

    if bad:
        print("  GATE FAIL")
        for b in bad:
            print(f"    - {b}")
        return 1

    OUT.write_text(json.dumps({
        "schema": "lunar-ice/literature-search/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/literature_search_gate.py",
        "record": "docs/literature_search_record.csv",
        "counts": got,
        "criteria_yes": {c: 0 for c in CRITERIA},
        "note": ("The inaccessible paper is counted and named rather than "
                 "dropped; a search that excluded it would claim a completeness "
                 "it does not have."),
    }, indent=2), encoding="utf-8")
    print("  GATE PASS — the record holds the counts the manuscript claims, and")
    print("  no relevant paper reports any of the three criteria.")
    print(f"  wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
