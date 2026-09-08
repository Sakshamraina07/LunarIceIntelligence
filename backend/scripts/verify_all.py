"""
verify_all.py -- every gate's evidence, in one command, mapped to the PRD.

    python -u backend/scripts/verify_all.py [--skip-slow]

WHAT THIS IS FOR
----------------
PRD section 6 lists the statements the project is done when all of them are
true -- the count is READ from PRD.md, never spelled here,
"and each is backed by a number in a report". Those numbers exist, but they were
spread across eight scripts and a browser verifier, so "is the project done" was
a question you answered by remembering where to look.

This runs them, collects the verdicts, and prints ONE table whose rows are the
those statements. It writes docs/verification.json.

IT ASSERTS NOTHING OF ITS OWN. Every verdict here is produced by the gate that
owns it; this script's only job is to run them all and map each to the statement
it backs. A verifier that computed its own opinion would be a seventh source of
truth, and this project has spent long enough removing those.
"""
from __future__ import annotations

import argparse
import json
import re
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


def _prd_statement_count() -> int:
    """How many statements PRD section 6 actually lists, read from the file.

    It said "six" while the section listed nine, for the same reason METHODS
    section 0's first pattern exists: a human wrote a count once and nothing
    afterwards made it agree with the thing counted. Both of the other counts in
    this file are read (the stamped artifacts, the gate rows); this one was the
    last one spelled.
    """
    text = (BASE_DIR / "PRD.md").read_text(encoding="utf-8")
    sec = text.split("## 6 · Definition of done", 1)
    if len(sec) < 2:
        return 0
    body = re.split(r"\n## ", sec[1], maxsplit=1)[0]
    return len(re.findall(r"^(\d+)\. ", body, flags=re.M))


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

    # G7 compares the API against the analysis on slope, roughness and hazard.
    # It has never looked at the PDF, which is how a formal report came to print
    # five landing sites that Phase 3 deleted, one of them marked RECOMMENDED,
    # beside a rover figure the screen reports as NO DATA. Third time two
    # surfaces have disagreed; this closes the last one.
    ("G9", "The PDF report prints nothing the analysis artifacts do not contain",
     "assert_pdf_agrees_with_analysis.py — the rendered bytes, not the inputs",
     [sys.executable, str(SCRIPTS / "assert_pdf_agrees_with_analysis.py")], False),

    # A figure that is an upper bound and a figure that is a rate are different
    # claims, and the difference is one phrase -- exactly the kind of thing that
    # survives one edit and is gone by the third.
    ("G10", "A figure that is an upper bound is never quoted as if it were a rate",
     "assert_upper_bounds_labelled.py — every occurrence, every tracked source",
     [sys.executable, str(SCRIPTS / "assert_upper_bounds_labelled.py")], False),

    # sin(theta) = ((R+h)/R) sin(eta) with (R+h)/R > 1 is an identity on a convex
    # body. The project shipped a criterion built on a field where 80.53 % of the
    # values sat below the look angle, and nothing checked it because nothing had
    # ever needed to. And there is one CPR field with one look count: the
    # narrative quoted N ~ 5 while the artifact published 13.72.
    ("G12", "There is one incidence field, it satisfies incidence > look angle, "
            "and nothing consumes a field that does not",
     "assert_incidence_geometry.py --only g12 — the identity, and every consumer",
     [sys.executable, str(SCRIPTS / "assert_incidence_geometry.py"),
      "--only", "g12"], False),

    ("G13", "There is one CPR field and every consumer reads the same look count "
            "for it",
     "assert_incidence_geometry.py --only g13 — read from the pipeline, not inferred",
     [sys.executable, str(SCRIPTS / "assert_incidence_geometry.py"),
      "--only", "g13"], False),

    # The deployed page was blank: one uncaught throw in one effect unmounted the
    # whole tree. No gate had ever loaded the BUILT application, and the dev
    # server cannot see it -- the crash needs the production bundle and the
    # production API base. This builds it, serves it against a stub returning the
    # exact degraded payload the deployed backend returns, and refuses a blank
    # page or a single console error.
    ("G15", "The production build mounts and renders against a backend that "
            "answers 200 and says it has no data",
     "verify_production.mjs --all-states — the built bundle, all three backend states",
     ["node", str(BASE_DIR / "frontend" / "scripts" / "verify_production.mjs"),
      "--all-states"], True),

    # The report is the one artefact that leaves the browser, and it must obey
    # the same three-state rule the screen does: on a host that answers but
    # holds no ARTIFACTS, NO PDF IS ISSUED -- 409 -- and a PDF that IS issued
    # says what it was rendered from.
    #
    # This comment used to end "the deployed backend is in exactly that state,
    # so this gate, and the PDF fix it guards, are VERIFIABLE LOCALLY ONLY."
    # That was false: the precondition is the committed artifacts, not the
    # rasters, and the deployed host serves the report with HTTP 200. METHODS
    # and PRD were corrected when the claim was withdrawn; this line was missed,
    # and G19 found it.
    ("G16", "A report is issued only on a host that holds the artifacts, and it "
            "names the state it was issued under",
     "assert_pdf_refuses_without_rasters.py — the loader, the 409, the rendered bytes",
     [sys.executable, str(SCRIPTS / "assert_pdf_refuses_without_rasters.py")], False),

    # Stage 09's sliders stopped re-querying a host that has no rasters and now
    # read a precomputed grid. That removed a dependency and introduced a new way
    # to be wrong: a grid of identical cells is a control surface over a criterion
    # that does not discriminate. A CPR axis spanning the PUBLISHED threshold is
    # exactly that -- nothing here comes within 235x of it -- so the axis is built
    # from the measured field, and this asserts it still is.
    ("G17", "The precomputed sweep discriminates on both axes, its axes are built "
            "from the measured field, and it agrees with the analysis",
     "assert_sweep_grid_discriminates.py - agreement, measured axes, it moves, the crossing",
     [sys.executable, str(SCRIPTS / "assert_sweep_grid_discriminates.py")], False),

    # The Report control said "NEEDS AN INGESTED HOST" while the host it named was
    # serving that report with HTTP 200. It derived its state from the MISSION
    # endpoint, which recomputes and needs the rasters; the report renders
    # committed artifacts and needs none. One boolean, two capabilities -- and the
    # same false premise reached the report's own front page, METHODS and PRD.
    # It survived because it made the project look WORSE than it is, and nothing
    # here is tuned to notice modesty.
    ("G18", "The report's availability is measured at its own endpoint and never "
            "inferred from the mission endpoint's state",
     "assert_report_state_is_its_own.py - independent, not derived, honest doc, probe works",
     [sys.executable, str(SCRIPTS / "assert_report_state_is_its_own.py")], False),

    # Eight claims have been withdrawn after being measured wrong, each recorded
    # in METHODS section 0. A withdrawal only holds if the claim cannot come
    # back, and prose is copied forward -- one of these was found still alive in
    # THIS FILE's own comment when the gate was written.
    #
    # Every term names a CLAIM, never a figure. An ad-hoc predecessor rejected
    # the bare string "8.75", which is simultaneously a deleted fabrication, the
    # measured 8.75 km amplitude ribbon, and a look count derivable from Fa &
    # Cai 2013. A scan that fires on a bare number either blocks correct work or
    # gets disabled, and both are worse than one that names what it forbids.
    ("G19", "A claim this project withdrew cannot reappear in a tracked source, "
            "and every scan term names a claim rather than a figure",
     "assert_withdrawn_claims_absent.py --list prints each term with the sentence it forbids",
     [sys.executable, str(SCRIPTS / "assert_withdrawn_claims_absent.py")], False),
]

# WHY THE SEQUENCE SKIPS G11 AND G14.
#
# It skips them because they were never allocated. No gate was written under
# either number, no gate was deleted, and nothing was quietly dropped: G12 and
# G13 were named as a pair when the two incidence defects were found, and G15
# was named when the blank production page needed one. The numbers in between
# were simply never used.
#
# This note exists because a gap in a numbered sequence of checks reads like a
# check that used to pass and does not any more, which is the most misleading
# shape a verification table can have. The gap is stated rather than closed:
# renumbering would silently move G12, G13 and G15, which are cited by number in
# METHODS, in docs/testing.md and in the commit history, and a citation that
# resolves to a different gate is worse than a documented gap.
_NEVER_ALLOCATED = ("G11", "G14")
assert not {g[0] for g in GATES} & set(_NEVER_ALLOCATED), (
    "G11/G14 are documented as never allocated; a gate now uses one of them, so "
    "either the note is wrong or the number is")


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
    _n_prd = _prd_statement_count()
    print(f"PRD SECTION 6 — the {_n_prd} statements the project is done when true")
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
