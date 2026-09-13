"""
assert_artifact_matches_repro_command.py -- G21. The artifact is the run METHODS names.

    python backend/scripts/assert_artifact_matches_repro_command.py [--inject]

WHY
---
METHODS section 7.4 prints a reproduction command:

    python -u backend/scripts/slc_multilook_control.py --windows 9

and quotes figures from it. `docs/slc_multilook_control.json` held a FIVE-window
run. The two runs share window 0 exactly (sub-band 9.95251789 in both), so
spot-checking one value would have agreed; what disagreed were the medians --
spatial 4.4144 and sub-band 8.7649 on disk against 4.52 and 9.95 in the text --
and the variants table had already absorbed the 5-window 8.76 while the narrative
kept the 9-window 9.95.

The staleness stamp could not catch it: the artifact's digest matched the
artifact, and the artifact was internally consistent. It was simply the WRONG
RUN. A digest answers "has this file changed"; it does not answer "is this file
the run the document says it is".

THIS GATE ASKS THE SECOND QUESTION. It parses the `--windows N` out of METHODS'
own reproduction command and requires the artifact to carry N windows. The
document and the artifact then cannot disagree about which run produced the
figures, because the document defines the run and the artifact must match it.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
METHODS = BASE_DIR / "docs" / "METHODS.md"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

#: (script name, artifact, the JSON key holding the per-run list)
#: Extend this when another artifact gains a reproduction command with a count
#: argument in it. A pairing that is not listed is not checked, so the list is
#: the claim about what is covered.
PAIRS = [
    ("slc_multilook_control.py", "docs/slc_multilook_control.json", "windows"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inject", action="store_true",
                    help="prove the gate fails when the counts disagree")
    args = ap.parse_args()

    print("=" * 78)
    print("G21 — the artifact is the run METHODS says produced it")
    print("=" * 78)

    text = METHODS.read_text(encoding="utf-8")
    bad: list[str] = []

    for script, rel, key in PAIRS:
        # The command as METHODS prints it, with its count argument.
        pat = re.escape(script) + r"[^`\n]*?--windows\s+(\d+)"
        m = re.search(pat, text)
        if m is None:
            bad.append(f"METHODS prints no `--windows N` reproduction command for "
                       f"{script}; this gate cannot check an artifact against a "
                       f"command that is not stated")
            continue
        declared = int(m.group(1))

        path = BASE_DIR / rel
        if not path.is_file():
            bad.append(f"{rel} is absent")
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        actual = len(doc.get(key) or [])
        if args.inject:
            actual += 1

        line = text.count("\n", 0, m.start()) + 1
        print(f"  METHODS:{line}  {script} --windows {declared}")
        print(f"  {rel}: {actual} entries under {key!r}")
        if actual != declared:
            bad.append(
                f"{rel} holds {actual} {key} but METHODS:{line} reproduces "
                f"{script} with --windows {declared}. The artifact is not the run "
                f"the document names, so every median quoted from it is a median "
                f"of a different run.")
        else:
            print(f"  MATCH — {actual} == {declared}")

    print()
    if args.inject:
        if bad:
            print("  INJECTION CAUGHT. The gate works.")
            for b in bad:
                print(f"    {b}")
            return 0
        print("  INJECTION NOT CAUGHT. The gate does not do what it says.")
        return 1

    if bad:
        print("  GATE FAIL")
        for b in bad:
            print(f"    - {b}")
        print("\n  Re-run the command METHODS prints, or correct the command.")
        print("  Do NOT adjust the count in the document to match the file: that")
        print("  makes the document describe whatever happens to be on disk.")
        return 1
    print("  GATE PASS — every artifact with a stated reproduction command holds")
    print("  the number of runs that command produces.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
