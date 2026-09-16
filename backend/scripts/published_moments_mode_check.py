"""
published_moments_mode_check.py -- P10. What Fa & Cai (2013) say their data are.

    python backend/scripts/published_moments_mode_check.py

The manuscript says the 14.8 m product Fa & Cai analysed is the Mini-RF S-band
ZOOM mode, nominally 8 looks, on the strength of the PDS instrument catalogue
and Spudis et al. (2013) Table 1 -- not on Fa & Cai's own text. P10 asks that
their data section be read and its product level, pixel spacing and imaging
mode recorded verbatim, and any discrepancy reported without resolving it.

This script records the OUTCOME of that attempt into docs/published_moments.json
under `mode_verification`. It is a record, not a computation: every field is
either a verbatim quotation with its source URL and access date, or an explicit
statement that the text could not be reached from this host. Nothing is inferred
from memory and written as if quoted.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
PM = BASE_DIR / "docs" / "published_moments.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

#: What was tried, in order, on the date recorded, from this host.
ATTEMPTS = [
    {"url": "https://agupubs.onlinelibrary.wiley.com/doi/full/10.1002/jgre.20110",
     "result": "HTTP 403 Forbidden (publisher full text)"},
    {"url": "https://agupubs.onlinelibrary.wiley.com/doi/pdfdirect/10.1002/jgre.20110",
     "result": "HTTP 403 Forbidden (publisher PDF)"},
    {"url": "https://ui.adsabs.harvard.edu/abs/2013JGRE..118.1582F/abstract",
     "result": "HTTP 405 Method Not Allowed (ADS renders client-side)"},
    {"url": "https://api.semanticscholar.org/graph/v1/paper/DOI:10.1002/jgre.20110",
     "result": "reachable; abstract field null, openAccessPdf empty (status CLOSED)"},
    {"url": "https://api.crossref.org/works/10.1002/jgre.20110",
     "result": "reachable; bibliographic record and abstract only; links are the "
               "Wiley TDM API (token required) and the Wiley PDF (403)"},
]

#: Verbatim from the Crossref-served abstract (the only text reached). It does
#: not name a product level, a pixel spacing, an imaging mode or a look count.
ABSTRACT_QUOTES = [
    "In an attempt to reduce the ambiguity on radar detection of water ice at the "
    "permanently shadowed regions near the lunar poles, radar echo strength and "
    "circular polarization ratio (CPR) of impact craters are analyzed using the "
    "Miniature Radio Frequency (Mini-RF) radar data from the Lunar Reconnaissance "
    "Orbiter mission.",
    "the enhanced CPR in the interior of anomalous craters is most probably caused "
    "by rocks that are perched on lunar surface or buried in regolith, instead of "
    "ice deposits as suggested in previous studies.",
]


def main() -> int:
    doc = json.loads(PM.read_text(encoding="utf-8"))
    block = {
        "status": "NOT VERIFIED — full text not accessible from this host",
        "accessed_utc": datetime.now(timezone.utc).isoformat(),
        "citation": doc["source"]["citation"],
        "what_was_needed": "the data section's statements of product level, pixel "
                           "spacing and imaging mode, verbatim, and the look count if "
                           "stated",
        "attempts": ATTEMPTS,
        "accessible_text": {"kind": "abstract (Crossref)", "quotes_verbatim": ABSTRACT_QUOTES,
                            "states_product_level": False, "states_pixel_spacing": False,
                            "states_imaging_mode": False, "states_look_count": False},
        "existing_transcription": {
            "table": doc["source"]["table"],
            "transcribed_by_hand": doc["source"]["transcribed_by_hand"],
            "note": "the moments in `craters` were transcribed from the paper's Table 1 "
                    "in an earlier pass; the data-section text was not captured then "
                    "and could not be re-read now"},
        "manuscript_claim_rests_on": "Raney et al. 2012 para. [4] (8 looks, S-band zoom, "
                                     "7.5 m) and the PDS instrument catalogue; NOT on Fa & "
                                     "Cai's own text",
        "discrepancy_check": "could not be performed; if Fa & Cai's data section names a "
                             "different mode or spacing, the manuscript's 14.8 m = zoom "
                             "attribution is unverified against its primary source",
        "action_for_author": "read Section 2 of the paper from an institutional copy and "
                             "replace this block with the verbatim statements",
    }
    doc["mode_verification"] = block
    PM.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print(json.dumps(block, indent=2))
    print(f"\n  updated {PM.relative_to(BASE_DIR)}::mode_verification")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
