"""
assert_pdf_refuses_without_rasters.py -- G16. A report is issued, or it is not.

    python backend/scripts/assert_pdf_refuses_without_rasters.py [--inject]

WHY
---
`/report/pdf/{crater}` renders the analysis artifacts. On a host that does not
have them -- which is every deployed host, since the 9 GB of Chandrayaan-2 and
LOLA products are gitignored -- it must REFUSE with 409 rather than issue a
thinner report. That is the same rule the rest of this project follows for an
absent measurement, applied to the one artefact that leaves the browser.

**The PDF is therefore verifiable LOCALLY ONLY**, and the report says so on its
own front page rather than leaving a reader to wonder why the deployed site
offers no download.

THE THREE STATES APPLY HERE TOO
-------------------------------
  (a) unreachable            no endpoint answers; nothing to check
  (b) reachable, NOT_INGESTED 409, and NO PDF MAY BE ISSUED
  (c) reachable, OK           a PDF, stamped with the state it was issued under

This asserts (b) and (c): the loader raises when an artifact is missing, the
endpoint turns that into 409, and a rendered report names the host state and the
artifacts it was rendered from. A report that did not say which state produced it
would be a document whose provenance depends on where it was generated and does
not record where that was.
"""
from __future__ import annotations

import argparse
import json
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

from pdf_text import extract_text  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--crater", default="faustini")
    ap.add_argument("--inject", action="store_true",
                    help="prove the gate fails when a report is issued without artifacts")
    args = ap.parse_args()

    from app.services import report_data
    from app.services.report_data import (load_report_bundle, ReportArtifactsMissing)
    from app.services.pdf_generator import generate_mission_pdf_report

    print("=" * 78)
    print("G16 — the report refuses on a host without the rasters, and says so")
    print("=" * 78)

    bad: list[str] = []

    # ── state (b): the artifacts are absent ──────────────────────────────────
    real_dir = report_data.ANALYSIS_DIR
    report_data.ANALYSIS_DIR = BASE_DIR / "docs" / "__no_such_directory__"
    try:
        # THE INJECTION IS ON THE LOADER, WHICH IS WHAT THIS GATE GUARDS.
        #
        # A first version injected at the GENERATOR instead -- handing it an empty
        # bundle to see whether a PDF came out. It did not, because the generator
        # raised a KeyError on the malformed dict, and the gate then reported
        # INJECTION CAUGHT for a reason that had nothing to do with the claim. An
        # injection that fails for the wrong reason tests nothing, and it is the
        # more dangerous kind of green light because it looks like one.
        #
        # The defect this gate exists to catch is A LOADER THAT TOLERATES ABSENCE.
        # So that is what is injected: `_read` is replaced by one that invents a
        # document instead of raising, exactly as a `.get(key, default)` would.
        if args.inject:
            print("  --inject: a loader that invents a document instead of raising\n")
            original_read = report_data._read
            report_data._read = lambda name, why: {
                "schema": "lunar-ice/analysis/1", "data_mode": "REAL",
                "crater_name": "invented",
                "generated_utc": "1970-01-01T00:00:00+00:00",
            }
            try:
                load_report_bundle(args.crater)
                bad.append("load_report_bundle returned a bundle with the analysis "
                           "directory absent; a report would be issued on a host "
                           "that has nothing to render")
            except ReportArtifactsMissing:
                pass
            finally:
                report_data._read = original_read
        else:
            try:
                load_report_bundle(args.crater)
                bad.append("load_report_bundle returned a bundle with the analysis "
                           "directory absent; a report would be issued on a host "
                           "that has nothing to render")
            except ReportArtifactsMissing as exc:
                print("  artifacts absent -> ReportArtifactsMissing, as required")
                print(f"    {str(exc)[:150]}")
    finally:
        report_data.ANALYSIS_DIR = real_dir

    # the endpoint turns that into 409, not 500 and not a thin PDF
    router = (BASE_DIR / "backend" / "app" / "api" / "api_router.py").read_text(encoding="utf-8")
    if "ReportArtifactsMissing" not in router or "status_code=409" not in router:
        bad.append("api_router no longer converts ReportArtifactsMissing into a 409")
    else:
        print("  api_router: ReportArtifactsMissing -> HTTP 409")

    # ── state (c): a report IS issued, and names the state ───────────────────
    print()
    try:
        bundle = load_report_bundle(args.crater)
    except ReportArtifactsMissing as exc:
        print(f"  no artifacts on THIS host either, so state (c) cannot be checked "
              f"here: {exc}")
        print("  That is not a pass. The gate needs a host with the artifacts.")
        bad.append("state (c) could not be exercised on this host")
        bundle = None

    if bundle is not None:
        pdf = generate_mission_pdf_report(bundle)
        text = extract_text(pdf)
        print(f"  rendered {len(pdf):,} bytes")
        required = [
            ("generated on a host that holds", "the host state it was issued under"),
            ("409", "what a host without the rasters returns instead"),
        ]
        for needle, what in required:
            if needle.lower() not in text.lower():
                bad.append(f"the report does not state {what} (looked for {needle!r})")
            else:
                print(f"  states {what}")

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
        return 1
    print("  GATE PASS — the report refuses without its artifacts, the endpoint")
    print("  returns 409, and an issued report names the host state that produced it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
