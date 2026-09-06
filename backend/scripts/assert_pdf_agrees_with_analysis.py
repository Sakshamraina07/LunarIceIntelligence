"""
assert_pdf_agrees_with_analysis.py -- every number the report prints is in the
artifacts it claims to render.

    python backend/scripts/assert_pdf_agrees_with_analysis.py [--crater faustini]
    python backend/scripts/assert_pdf_agrees_with_analysis.py --inject

WHY THIS GATE EXISTS
--------------------
THE THIRD TIME TWO SURFACES HAVE DISAGREED IN THIS PROJECT, and the worst of the
three, because a PDF is read without the badge that said DEMO. The report was
generated from `mission_service`'s legacy payload and printed:

  * five landing sites that Phase 3 deleted -- Alpha Ridge (North), Beta
    Plateau, Gamma Bench, Delta Spur, Epsilon Crest -- one marked RECOMMENDED,
    with slopes 6.7-12.2 deg against the real 0.05-0.55 and a score of 37.1 on a
    scale the search does not use;
  * a rover traverse of 18.06 km and 3,137.5 Wh, while the screen said NO DATA;
  * a Random Forest described in section 2 and withdrawn in section 5;
  * "re-running the pipeline reproduces them", of hardcoded figures.

`assert_paths_agree.py` compares the API against the analysis on SLOPE,
ROUGHNESS AND HAZARD. It has never looked at the report, which is why none of
the above was caught. This gate closes that surface.

WHAT IT CHECKS
--------------
It renders the PDF, extracts the text from the RENDERED BYTES -- not from the
generator's inputs, which would be checking one assumption against itself -- and
asserts that every numeric literal on the page is present in the four artifacts
the report is a rendering of, at the precision printed.

It also asserts the four contradictions above are gone by name, because "the
number is in the artifact" would not have caught "Random Forest ... provides
continuous probability distributions": that sentence contains no numbers.

WHAT IT DOES NOT CHECK, stated so it is not over-trusted: it does not check that
a figure is in the RIGHT PLACE. A landing site's latitude printed in the energy
column would pass. It checks that nothing on the page came from outside the
artifacts, which is the failure that actually happened.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
for d in (str(BACKEND_DIR), str(Path(__file__).resolve().parent)):
    if d not in sys.path:
        sys.path.insert(0, d)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

from pdf_text import extract_text, numbers  # noqa: E402

ANALYSIS_DIR = BASE_DIR / "frontend" / "public" / "analysis"

# ── page furniture ──────────────────────────────────────────────────────────
#
# Integers that are part of the document, not claims about the Moon: the five
# section numbers and the five numbered limitation items. Listed explicitly with
# the reason, because an allow-list is where a gate goes to die -- anything here
# is a number the gate has stopped checking.
FURNITURE = {
    "1": "section and limitation-item numbering",
    "2": "section and limitation-item numbering",
    "3": "section and limitation-item numbering",
    "4": "section and limitation-item numbering",
    "5": "section and limitation-item numbering",
    # An HTTP status code is a fact about this server, not a figure about the
    # Moon, and there is no artifact it could ever appear in. It is here because
    # the front page now states what a host WITHOUT the rasters returns instead
    # of a report -- see G16. Listed as furniture rather than smuggled past by
    # spelling it "four-oh-nine", which would have hidden it from this gate and
    # from a reader at the same time.
    "409": "the HTTP status a host without the analysis artifacts returns (G16)",
}

# Sentences that must NOT appear. Each one is a defect this gate was written for.
FORBIDDEN = [
    (r"Alpha Ridge|Beta Plateau|Gamma Bench|Delta Spur|Epsilon Crest",
     "the five hardcoded site names module_e_landing.py used before Phase 3"),
    # Not a bare /RECOMMENDED/: the report's own sentence says "No site is marked
    # RECOMMENDED", and a check that fires on its own disclaimer is a check that
    # gets waved through. The lookbehind matches the table cell, not the denial.
    (r"(?<!marked )RECOMMENDED",
     "a recommendation over sites whose cold-trap target is modelled, not detected"),
    (r"Random Forest[^.]*provides continuous probability",
     "section 2 describing a classifier section 5 says was withdrawn"),
    (r"re-running the pipeline on that product reproduces them",
     "the false reproducibility claim, which had already been removed once"),
    (r"\bWh\b",
     "watt-hours, which require a rover mass this project does not model"),
    (r"30 kg",
     "an invented rover mass"),
]


def leaf_numbers(obj, out: set) -> None:
    """Every number in a document, including the ones inside its prose.

    Strings count. `quantisation_note` reads "A route reported as 4,180 m is
    4,180 +/- 50 m", and the report quotes it verbatim; those figures are in the
    artifact and the gate has to see them there.
    """
    if isinstance(obj, dict):
        for v in obj.values():
            leaf_numbers(v, out)
    elif isinstance(obj, list):
        for v in obj:
            leaf_numbers(v, out)
    elif isinstance(obj, bool):
        return
    elif isinstance(obj, (int, float)):
        out.add(float(obj))
        # A fraction printed as a percentage is the same measurement.
        out.add(float(obj) * 100.0)
        # MAGNITUDE, because the extractor reads unsigned literals: a latitude
        # of -86.2714 prints as "-86.2714" and comes back as "86.2714", and
        # teaching the extractor about signs would make "2020-08-08" parse as
        # 2020, -8, -8. The cost is stated rather than hidden: THIS GATE CANNOT
        # SEE A SIGN ERROR. The one place a sign error has actually happened in
        # this project -- the longitude convention in plan_traverse.py -- is
        # covered by that script's own cross-file check against
        # landing_sites.json, which compares great-circle distance and does see
        # signs. These are the only two transforms allowed; no sums, no ratios,
        # no unit conversions, because each of those would let the report derive
        # a figure the artifacts do not contain and still pass.
        out.add(abs(float(obj)))
        out.add(abs(float(obj)) * 100.0)
    elif isinstance(obj, str):
        for n in numbers(obj):
            try:
                out.add(float(n))
            except ValueError:
                pass


def load_artifacts(crater: str) -> tuple[dict, set]:
    docs = {}
    for name in (f"{crater}.json", "landing_sites.json", "traverse.json",
                 "detection_statistics.json"):
        p = ANALYSIS_DIR / name
        if p.exists():
            docs[name] = json.loads(p.read_text(encoding="utf-8"))
    allowed: set = set()
    for d in docs.values():
        leaf_numbers(d, allowed)
    return docs, allowed


def check(text: str, allowed: set) -> tuple[list, list]:
    """Returns (unmatched numbers, forbidden phrases found)."""
    bad = []
    for lit in numbers(text):
        if lit in FURNITURE:
            continue
        try:
            printed = float(lit)
        except ValueError:
            continue
        decimals = len(lit.split(".")[1]) if "." in lit else 0
        # Match at the precision PRINTED. A report that prints 0.9290 must have
        # an artifact value that rounds to 0.9290 -- not merely one that is
        # close, which is how a figure from a different computation slips past a
        # tolerance check.
        if any(round(c, decimals) == printed for c in allowed):
            continue
        bad.append(lit)
    found = [(pat, why) for pat, why in FORBIDDEN if re.search(pat, text)]
    return bad, found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--crater", default="faustini")
    ap.add_argument("--inject", action="store_true",
                    help="prove the gate fails on a fabricated figure")
    args = ap.parse_args()

    from app.services.report_data import load_report_bundle
    from app.services.pdf_generator import generate_mission_pdf_report

    print("=" * 78)
    print("PDF vs ANALYSIS — every printed figure, against the artifacts it renders")
    print("=" * 78)

    docs, allowed = load_artifacts(args.crater)
    print(f"  artifacts read: {', '.join(sorted(docs))}")
    print(f"  distinct numeric values in them: {len(allowed):,}\n")

    bundle = load_report_bundle(args.crater)

    if args.inject:
        # THE INJECTION. A site the search never found, with a slope, an
        # illumination and a score from the deleted hardcoded list -- exactly
        # the defect this gate exists for. If the gate passes on this, it is
        # not a gate.
        print("  --inject: adding a fabricated site (Alpha Ridge (North), score 37.1)\n")
        fake = json.loads(json.dumps(bundle["sites"]["sites"][0]))
        fake["rank"] = 6
        fake["lat_deg"] = -87.3312
        fake["lon_deg"] = 41.9987
        fake["suitability_score"] = 37.1
        fake["criteria"]["slope_deg"]["value"] = 6.7
        fake["criteria"]["illumination_fraction"]["value"] = 0.02
        fake["ice_access"]["psr_distance_km"] = 11.44
        bundle["sites"]["sites"].append(fake)

    pdf = generate_mission_pdf_report(bundle)
    text = extract_text(pdf)
    print(f"  rendered {len(pdf):,} bytes, {len(text.splitlines()):,} text runs, "
          f"{len(numbers(text)):,} numeric literals\n")

    bad, forbidden = check(text, allowed)

    for pat, why in forbidden:
        print(f"  FORBIDDEN  /{pat}/  — {why}")
    if bad:
        print(f"  NOT IN ANY ARTIFACT: {len(bad)} figure(s)")
        for b in sorted(set(bad), key=lambda x: (len(x), x)):
            print(f"    {b}")

    if args.inject:
        if bad or forbidden:
            print(f"\n  INJECTION CAUGHT — {len(set(bad))} fabricated figure(s), "
                  f"{len(forbidden)} forbidden phrase(s). The gate works.")
            return 0
        print("\n  INJECTION NOT CAUGHT. The gate does not do what it says.")
        return 1

    if bad or forbidden:
        print("\n  GATE FAIL — the report prints something the artifacts do not contain.")
        print("  The PDF is a RENDERING of the analysis, not a second computation of it;")
        print("  a figure here that is not there came from somewhere else.")
        return 1

    print("  GATE PASS — every figure the report prints is in the artifacts,")
    print("  at the precision printed, and none of the four known contradictions")
    print("  is present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
