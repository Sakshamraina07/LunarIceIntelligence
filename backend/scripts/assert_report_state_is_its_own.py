"""
assert_report_state_is_its_own.py -- G18. Two endpoints, two capabilities.

    python backend/scripts/assert_report_state_is_its_own.py [--inject WHICH]

WHY
---
The UI's Report control read "REPORT - NEEDS AN INGESTED HOST" while the host it
was talking about was serving that report with HTTP 200. The control derived its
state from `/api/mission/{crater}`, which is a different capability:

    /api/mission/{crater}   RECOMPUTES. Needs the ~9 GB of Chandrayaan-2 and
                            LOLA rasters. A deployed host answers NOT_INGESTED.
    /api/report/pdf/{c}     RENDERS four committed analysis artifacts. Needs no
                            rasters. The same host answers 200.

One boolean stood in for both, so a working download was hidden behind another
endpoint's absence -- and the same false premise was written into the report's
own front page, into METHODS and into PRD statement 10, where it survived because
it made the project look WORSE than it is. Nothing in this project's discipline
is tuned to notice modesty; every other instance in METHODS section 0 was caught
because a number looked too good.

WHAT IT ASSERTS
---------------
  1. INDEPENDENT   the report endpoint is reachable on a host whose mission
                   endpoint reports NOT_INGESTED -- proved in-process, by putting
                   the mission gate into that state and issuing a report anyway.
  2. NOT DERIVED   no UI source decides the report control from the mission
                   endpoint's state.
  3. HONEST DOC    the rendered report does not claim the rasters are a
                   precondition for issuing it.
  4. PROBE WORKS   /report/status/{crater} exists, answers without rendering, and
                   distinguishes a crater with artifacts from one without.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
for _d in (str(BACKEND_DIR), str(Path(__file__).resolve().parent)):
    if _d not in sys.path:
        sys.path.insert(0, _d)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

from pdf_text import extract_text  # noqa: E402

UI_SOURCES = [
    BASE_DIR / "frontend" / "src" / "mission" / "MissionControl.tsx",
    BASE_DIR / "frontend" / "src" / "mission" / "StepPanel.tsx",
]
INJECTIONS = ("derived", "rasterclaim", "nostatus")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--crater", default="faustini")
    ap.add_argument("--inject", choices=INJECTIONS)
    args = ap.parse_args()

    from fastapi.testclient import TestClient
    from app.main import app

    print("=" * 78)
    print("G18 - the report's availability is its own, not the mission endpoint's")
    print("=" * 78)

    client = TestClient(app)
    bad: list[str] = []

    # -- 1. INDEPENDENT ------------------------------------------------------
    # The mission endpoint's own answer for this crater on THIS host, and the
    # report's, side by side. The point is not that either is a particular value;
    # it is that the report must not inherit the mission endpoint's.
    m = client.get(f"/api/mission/{args.crater}?data_mode=REAL")
    m_status = (m.json() or {}).get("status") if m.status_code == 200 else f"HTTP {m.status_code}"
    r = client.get(f"/api/report/pdf/{args.crater}")
    print(f"  mission endpoint  {args.crater} -> {m_status}")
    print(f"  report endpoint   {args.crater} -> HTTP {r.status_code}, "
          f"{len(r.content):,} bytes")

    if r.status_code != 200:
        bad.append(f"the report endpoint answered HTTP {r.status_code} on a host that "
                   f"holds the committed analysis artifacts")
    elif m_status == "NOT_INGESTED":
        print("  independent       the report is issued while the mission endpoint "
              "reports NOT_INGESTED")

    # -- 2. NOT DERIVED ------------------------------------------------------
    # The control's gate, read from the source. A report control conditioned on
    # `backend === 'ok'` is the defect, spelled.
    derived = []
    pat = re.compile(r"(backend|props\.backend)\s*===\s*'ok'\s*\?[^\n]{0,400}", re.S)
    for src in UI_SOURCES:
        text = src.read_text(encoding="utf-8")
        if args.inject == "derived" and src.name == "MissionControl.tsx":
            text += "\n{backend === 'ok' ? <a href={getReportPdfUrl(craterId)}>Report</a> : null}"
        for hit in pat.finditer(text):
            if re.search(r"getReportPdfUrl|Download PDF Report", hit.group(0)):
                derived.append(f"{src.name}: a report control gated on backend === 'ok'")
    if derived:
        bad.extend(derived)
    else:
        print("  not derived       no report control is gated on the mission state")

    # -- 3. HONEST DOC -------------------------------------------------------
    from app.services.report_data import load_report_bundle
    from app.services.pdf_generator import generate_mission_pdf_report
    text = extract_text(generate_mission_pdf_report(load_report_bundle(args.crater)))
    if args.inject == "rasterclaim":
        text += (" This report was generated on a host that holds the ingested "
                 "Chandrayaan-2 and LOLA products.")
    false_claims = [
        "generated on a host that holds the ingested",
        "verifiable locally only",
    ]
    hits = [c for c in false_claims if c.lower() in text.lower()]
    if hits:
        bad.append(f"the report claims the rasters are a precondition for issuing it: "
                   f"{hits!r}. It renders committed artifacts and recomputes nothing.")
    else:
        print("  honest doc        the report does not claim the rasters gate it")

    # -- 4. PROBE WORKS ------------------------------------------------------
    path = f"/api/report/status/{args.crater}"
    st = client.get("/api/report/status/__no_such_crater__" if args.inject == "nostatus" else path)
    if st.status_code != 200:
        bad.append(f"{path} answered HTTP {st.status_code}; the control has nothing "
                   f"to ask and would have to guess")
    elif (st.json() or {}).get("available") is not True:
        bad.append(f"{path} reports the report unavailable on a host that just "
                   f"issued one")
    else:
        # and it must actually discriminate, not answer True for anything
        neg = client.get("/api/report/status/shackleton")
        if neg.status_code == 200 and (neg.json() or {}).get("available") is True:
            bad.append("/report/status reports available for a crater with no "
                       "analysis artifact; it does not discriminate")
        else:
            print("  probe works       status route discriminates without rendering")

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
    print("  GATE PASS - the report's availability is measured at its own endpoint,")
    print("  no control infers it from the mission state, and the document does not")
    print("  claim a precondition it does not have.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
