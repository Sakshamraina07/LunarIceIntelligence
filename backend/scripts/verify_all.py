"""
verify_all.py -- every gate's evidence, in one command, mapped to the PRD.

    python -u backend/scripts/verify_all.py [--skip-slow]

WHAT THIS IS FOR
----------------
PRD section 6 lists six statements the project is done when all six are true,
"and each is backed by a number in a report". Those numbers exist, but they were
spread across eight scripts and a browser verifier, so "is the project done" was
a question you answered by remembering where to look.

This runs them, collects the verdicts, and prints ONE table whose rows are the
six statements. It writes docs/verification.json.

IT ASSERTS NOTHING OF ITS OWN. Every verdict here is produced by the gate that
owns it; this script's only job is to run them all and map each to the statement
it backs. A verifier that computed its own opinion would be a seventh source of
truth, and this project has spent long enough removing those.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
SCRIPTS = Path(__file__).resolve().parent

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

#: (id, PRD statement, the gate that backs it, argv, slow?)
# The stamped-artifact count is READ from the registry, never written here. It
# was "15 artifacts" and went stale the moment a sixteenth was added -- METHODS
# section 0, first pattern, inside the file whose job is to catch it.
sys.path.insert(0, str(SCRIPTS))
from stamp_methods import ARTIFACTS as _STAMPED  # noqa: E402
_N_STAMPED = len(_STAMPED)


GATES = [
    ("G1", "Every number on #mission carries a mark and resolves to a raster "
           "read or an explicit absent state",
     "emit_provenance.py — six assertions, each injection-tested",
     [sys.executable, str(SCRIPTS / "emit_provenance.py"), "faustini"], False),

    ("G2", "PSR, cold-trap overlap and illumination come from a horizon "
           "computation over the full LOLA array at a stated resolution",
     "validate_psr_vs_lola.py — against the LOLA team's own published mask",
     [sys.executable, str(SCRIPTS / "validate_psr_vs_lola.py")], True),

    ("G3", "Landing sites are the argmax of a six-criterion search over 14.9 M "
           "native cells with stated NMS and per-criterion evidence",
     "search_landing_sites.py — plus the interpolation guard",
     [sys.executable, str(SCRIPTS / "search_landing_sites.py"), "--top", "5"], True),

    ("G4", "The traverse is Dijkstra over a slope-and-hazard cost surface at a "
           "stated planning resolution, with UNREACHABLE a real state",
     "plan_traverse.py — connectivity reported before any distance",
     [sys.executable, str(SCRIPTS / "plan_traverse.py")], True),

    ("G5", "CPR is an explicitly-labelled amplitude-only ratio with the claim "
           "withdrawn, and CANDIDATE AREA is a measurement including a zero",
     "detection_statistics.py — the floor, and the confidence interval",
     [sys.executable, str(SCRIPTS / "detection_statistics.py")], False),

    ("G6", "The map's relief is real at 25 m, lit from more than one direction, "
           "and the base filter is set from a histogram rather than by eye",
     "hillshade_histogram.py + composite_contrast.py",
     [sys.executable, str(SCRIPTS / "hillshade_histogram.py")], False),

    ("G6b", "(same statement) the science layers composite over that relief "
            "without hiding it",
     "composite_contrast.py — retention AND correlation with the base",
     [sys.executable, str(SCRIPTS / "composite_contrast.py"), "--opacity", "0.45"], False),

    ("G7", "The API and the static analysis agree on every terrain quantity "
           "they both report",
     "assert_paths_agree.py — in-process, needs no server",
     [sys.executable, str(SCRIPTS / "assert_paths_agree.py")], False),

    ("G8", "Every measured figure quoted in METHODS.md still matches the "
           "artifact it was transcribed from",
     f"stamp_methods.py --check — {_N_STAMPED} artifacts",
     [sys.executable, str(SCRIPTS / "stamp_methods.py"), "--check"], False),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-slow", action="store_true",
                    help="skip the gates that re-read multi-gigabyte rasters")
    ap.add_argument("--out", default="docs/verification.json")
    args = ap.parse_args()

    print("=" * 78)
    print("VERIFY ALL — every gate, mapped to PRD section 6")
    print("=" * 78)
    print("  This script asserts nothing of its own. Each verdict is produced by")
    print("  the gate that owns it; this only runs them and maps each to the")
    print("  statement it backs.\n")

    rows = []
    for gid, statement, owner, argv, slow in GATES:
        if slow and args.skip_slow:
            print(f"  {gid:>4}  SKIPPED (--skip-slow)   {owner}")
            rows.append({"id": gid, "statement": statement, "gate": owner,
                         "verdict": "SKIPPED", "seconds": 0.0})
            continue
        t0 = time.time()
        proc = subprocess.run(argv, cwd=str(BASE_DIR), capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        dt = time.time() - t0
        ok = proc.returncode == 0
        rows.append({"id": gid, "statement": statement, "gate": owner,
                     "verdict": "PASS" if ok else "FAIL",
                     "returncode": proc.returncode, "seconds": round(dt, 1)})
        print(f"  {gid:>4}  {'PASS' if ok else 'FAIL'}  {dt:>6.1f}s   {owner}")
        if not ok:
            tail = (proc.stdout or "").strip().splitlines()[-6:]
            for line in tail:
                print(f"          {line}")

    print("\n" + "=" * 78)
    print("PRD SECTION 6 — the six statements the project is done when true")
    print("=" * 78)
    for r in rows:
        mark = {"PASS": "[x]", "FAIL": "[ ] FAILED", "SKIPPED": "[?] not run"}[r["verdict"]]
        print(f"  {mark:>11}  {r['id']:>4}  {r['statement']}")
        print(f"               backed by: {r['gate']}")

    failed = [r for r in rows if r["verdict"] == "FAIL"]
    skipped = [r for r in rows if r["verdict"] == "SKIPPED"]
    print()
    if failed:
        print(f"  NOT DONE — {len(failed)} gate(s) failing: "
              f"{', '.join(r['id'] for r in failed)}")
    elif skipped:
        print(f"  {len(rows) - len(skipped)}/{len(rows)} gates pass; "
              f"{len(skipped)} skipped and therefore UNVERIFIED, not passed.")
    else:
        print(f"  ALL {len(rows)} GATES PASS. Every statement in PRD section 6 is")
        print("  backed by a number produced in this run.")

    doc = {"generated_utc": datetime.now(timezone.utc).isoformat(),
           "generator": "backend/scripts/verify_all.py", "gates": rows,
           "all_pass": not failed and not skipped}
    (BASE_DIR / args.out).write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print(f"\n  wrote {args.out}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
