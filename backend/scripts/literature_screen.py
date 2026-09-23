"""
literature_screen.py -- P8. The literature audit, rebuilt with access and
per-claim fields, and the abstract-only records re-screened.

    python backend/scripts/literature_screen.py

Reads docs/literature_search_record.csv (the screen G29 asserts against; NOT
modified here) and writes docs/literature_screen.json and
docs/literature_screen.md with, per record:

    access   in {full_text, abstract_only, inaccessible}
    measured_ENL_reported, critical_value_reported, exceedance_rate_reported,
    ratio_bias_corrected   in {yes, no, not_found_in_accessible_material,
                               not_assessed}

Two rules the values follow. A claim is `no` only where the accessible material
is the whole item and was read; where only an abstract was reachable it is
`not_found_in_accessible_material`, which is a statement about this pass and not
about the paper. `ratio_bias_corrected` was not a column of the original screen;
for the twelve full texts it is `not_assessed` here rather than guessed.

The re-screen of the abstract-only records is recorded attempt by attempt --
URL, date, outcome -- so a reader can see which full texts were obtained (two)
and why the others were not (publisher 403s, an unresolvable host, and a
rate-limited index). Setting spudis2013.measured_ENL_reported = yes is done with
the quotation P8 supplies and the note that the paper attributes it to
unpublished analysis.
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
CSV = BASE_DIR / "docs" / "literature_search_record.csv"
OUT_JSON = BASE_DIR / "docs" / "literature_screen.json"
OUT_MD = BASE_DIR / "docs" / "literature_screen.md"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

VALUES = ("yes", "no", "not_found_in_accessible_material", "not_assessed")
NF = "not_found_in_accessible_material"

#: The original search, verbatim from the record kept beside the CSV.
ORIGINAL_SEARCH = {
    "executed": "2026-09-09",
    #: from the search-flow record kept with the screen: "raw links returned
    #: ~75 ... unique scholarly records 34". Transcribed, not measured.
    "raw_links_returned": 75,
    "index": "web search index (Google-class) returning ADS, IEEE Xplore, Wiley/AGU, "
             "ScienceDirect, Springer, MDPI, ResearchGate, NTRS, LPI/USRA records",
    "not_queried": "Scopus, IEEE Xplore native search, ADS API (institutional/API access)",
    "date_range": "1994 - 2026-09-09", "language": "none excluded",
    "types": "journal, conference abstracts, preprints, agency reports",
    "strings": [
        '"circular polarization ratio" lunar "Mini-RF" ice crater',
        '"circular polarization ratio" "permanently shadowed" Moon radar ice',
        'Chandrayaan-2 DFSAR "circular polarization ratio" polar crater water ice',
        '"Mini-SAR" Chandrayaan-1 "circular polarization ratio" north pole ice',
        '"equivalent number of looks" OR "effective number of looks" Mini-RF OR DFSAR OR "Mini-SAR" lunar',
        'lunar radar "circular polarization ratio" "false alarm" OR "false positive" OR "detection threshold" ice',
        '"m-chi" OR "m-delta" decomposition lunar crater ice Mini-RF DFSAR',
        'Mini-RF "CPR" lunar polar craters Thomson OR Neish OR Campbell OR Patterson OR Cahill',
    ],
}

#: P8 step 3: every abstract-only (or not-accessed) relevant record, re-tried
#: for full text on the date given. `obtained` records what was actually read.
RESCREEN_DATE = "2026-09-16"
RESCREEN = {
    "3": {"query": 'Spudis 2010 GRL "Initial results for the north pole of the Moon from Mini-SAR, Chandrayaan-1"',
          "attempts": [("https://repository.si.edu/items/8c4e325a-34f1-4a82-bbe3-22072072d0db", "HTTP 403"),
                       ("https://api.semanticscholar.org/graph/v1/paper/DOI:10.1029/2009GL042259", "isOpenAccess false, no OA PDF")],
          "obtained": None, "doi": "10.1029/2009GL042259"},
    "9": {"query": "Kumar 2022 Advances in Space Research polarimetric analysis L-band DFSAR water ice permanently shadowed regions Chandrayaan-2",
          "attempts": [("https://www.sciencedirect.com/science/article/abs/pii/S0273117722000758", "abstract page only (subscription)"),
                       ("https://api.semanticscholar.org/graph/v1/paper/search?query=...", "HTTP 429 rate-limited")],
          "obtained": None, "note": "Adv. Space Res. 70(12) 4000-4029"},
    "11": {"query": '"Backscatter Coefficients and Circular Polarization Ratio" permanently shadowed region lunar south pole Chandrayaan-2 DFSAR 2025 preprint',
           "attempts": [("https://www.researchgate.net/publication/391614433_...", "ResearchGate blocks non-browser fetches; not attempted beyond the index"),
                        ("https://api.semanticscholar.org/graph/v1/paper/search?query=...", "HTTP 429 rate-limited")],
           "obtained": None},
    "12": {"query": '"Detection of water ice" Faustini crater floor DFSAR IEEE 2024 10641024',
           "attempts": [("https://ieeexplore.ieee.org/document/10641024/", "subscription; not fetched"),
                        ("https://ui.adsabs.harvard.edu/abs/2024igar.conf.1390S/abstract", "ADS abstract record only"),
                        ("https://api.semanticscholar.org/graph/v1/paper/search?query=...", "HTTP 429 rate-limited")],
           "obtained": None, "note": "IGARSS 2024; Shroff, Shukla, Patel, Mohan"},
    "13": {"query": '"Hermite-A" crater dielectric polarimetric analysis Mini-SAR Mini-RF DFSAR Advances in Space Research 2022',
           "attempts": [("https://www.sciencedirect.com/science/article/abs/pii/S0273117722003362", "abstract page only (subscription)"),
                        ("https://api.semanticscholar.org/graph/v1/paper/search?query=...", "HTTP 429 rate-limited")],
           "obtained": None},
    "14": {"query": '"Erlanger" crater water ice integrated analysis Mini-SAR DFSAR Remote Sensing 2025 17(1) 31',
           "attempts": [("https://www.mdpi.com/2072-4292/17/1/31", "HTTP 403 from this host (journal is open access)"),
                        ("https://www.mdpi.com/2072-4292/17/1/31/htm", "HTTP 403 from this host")],
           "obtained": None, "doi": "10.3390/rs17010031",
           "note": "open-access venue; a browser session will obtain it -- flagged for the author"},
    "15": {"query": "Ohm Stevinus craters Mini-RF circular polarization ratio m-chi Journal of Earth System Science 2020",
           "attempts": [("https://www.ias.ac.in/public/Volumes/jess/129/00/0105.pdf", "DNS EAI_AGAIN (host unresolvable from this pass), twice"),
                        ("https://link.springer.com/article/10.1007/s12040-020-1370-8", "303 to idp.springer.com authorisation")],
           "obtained": None, "doi": "10.1007/s12040-020-1370-8",
           "note": "open PDF exists at ias.ac.in; host did not resolve in this pass -- flagged for the author"},
    "16": {"query": 'Spudis 2013 "excess" enhanced CPR craters polar regions Mini-RF abstract',
           "attempts": [("https://www.researchgate.net/publication/258674786_...", "ResearchGate; not fetched"),
                        ("https://api.semanticscholar.org/graph/v1/paper/search?query=...", "HTTP 429 rate-limited")],
           "obtained": None},
    "18": {"query": 'Raney 2012 LPSC abstract "m-chi" characterization lunar craters Mini-RF',
           "attempts": [("https://www.lpi.usra.edu/meetings/lpsc2012/pdf/2676.pdf", "PDF obtained (260 KB), text extracted")],
           "obtained": "full text (2-page LPSC abstract 2676)",
           "extract": {"measured_ENL_reported": "no", "critical_value_reported": "no",
                       "exceedance_rate_reported": "no", "ratio_bias_corrected": "no",
                       "data_statement": "Mini-RF S1 data shown over a '100 m/pixel simple cylindrical LROC WAC image'; "
                                         "no radar product level, spacing, mode or look count is stated"}},
    "19": {"query": '"Studies of polarimetric properties of lunar surface using Mini-SAR data" 2013',
           "attempts": [("https://api.semanticscholar.org/graph/v1/paper/0a688093a7a12c35198425a2aa6f2b5261b3bfb8", "HTTP 429 rate-limited"),
                        ("academia.edu / researchgate.net", "login-walled; not fetched")],
           "obtained": None},
    "21": {"query": "EGU General Assembly 2020 Mini-RF observations polar craters ice distribution Moon abstract",
           "attempts": [("https://meetingorganizer.copernicus.org/EGU2020/EGU2020-11285.html", "abstract obtained in full")],
           "obtained": "full text (the item is a conference abstract, EGU2020-11285; Jozwiak & Patterson)",
           "extract": {"measured_ENL_reported": "no", "critical_value_reported": "no",
                       "exceedance_rate_reported": "no", "ratio_bias_corrected": "no",
                       "data_statement": "monostatic and bistatic Mini-RF observations of the poles; no product level, spacing or look count stated"}},
    "22": {"query": "Science Bulletin 2025 upper limit water ice lunar south pole SYISR FAST bistatic radar",
           "attempts": [("https://www.sciencedirect.com/science/article/pii/S2095927325001999", "HTTP 403 from this host"),
                        ("https://pubmed.ncbi.nlm.nih.gov/40069062/", "abstract record only")],
           "obtained": None},
    "26": {"query": "IEEE JSTARS 2023 Pol-SAR image simulation lunar surface DFSAR Mini-RF equivalent number of looks",
           "attempts": [("https://ieeexplore.ieee.org/document/10298630/", "subscription; not fetched"),
                        ("https://api.semanticscholar.org/graph/v1/paper/search?query=...", "HTTP 429 rate-limited")],
           "obtained": None, "doi": "10.1109/JSTARS.2023.3328063"},
    "29": {"query": '"Characterization of the Moon\'s South polar craters using optical, microwave and thermal remote sensing" Advances in Space Research 2023',
           "attempts": [("https://www.sciencedirect.com/science/article/abs/pii/S0273117723008955", "abstract page only (subscription)"),
                        ("https://api.semanticscholar.org/graph/v1/paper/search?query=...", "HTTP 429 rate-limited")],
           "obtained": None, "doi": "10.1016/j.asr.2023.11.009"},
}

SPUDIS_2013_QUOTE = ("effective number of looks of about 6.7 … as opposed to the planned 8 looks")

#: III-E prints "mean DOP 0.10-0.13 in F2, F3, H3 and S1" and says the values
#: are region means of the pixels with CPR >= 1. Both quotations were supplied
#: with the third-review instructions (2026-09-23) and verified at the
#: publisher by the author (response letter, M2); they are recorded here as
#: supplied, not re-fetched by this script.
SINHA_2026_AGGREGATION = {
    "quote_average_dop": ("low average DOP values, ranging from 0.1 to 0.13 in "
                          "craters F2, F3, H3, and S1"),
    "quote_fig4_caption": "average CPR and DOP of pixels having CPR ≥ 1",
    "average_dop_range": [0.10, 0.13],
    "craters": ["F2", "F3", "H3", "S1"],
    "aggregation": ("region means over the pixels with CPR >= 1; per-pixel CPR "
                    "and DOP are not published"),
    "source_of_quotation": ("supplied with the third-review instructions, "
                            "2026-09-23; verified at the publisher per the "
                            "response letter (M2); not re-fetched here"),
}


def main() -> int:
    rows = list(csv.DictReader(CSV.read_text(encoding="utf-8-sig").splitlines()))
    records = []
    for r in rows:
        rid = r["id"]
        level = (r.get("screen_level") or "").strip().lower()
        relevant = (r.get("relevant_lunar_cpr_ice_study") or "").strip() == "yes"
        rs = RESCREEN.get(rid)
        if level.startswith("full text ("):
            access = "full_text"
        elif rs and rs.get("obtained"):
            access = "full_text"
        elif level == "abstract" or level.startswith("full text not accessed"):
            access = "abstract_only"
        else:
            access = "inaccessible"

        def claim(col):
            v = (r.get(col) or "").strip()
            if access == "full_text" and rs and rs.get("obtained"):
                return None  # filled from the extract below
            if access == "full_text":
                return "yes" if v == "yes" else ("no" if v == "no" else "not_assessed")
            if not relevant:
                return "not_assessed"
            return NF

        rec = {
            "id": int(rid), "first_author": r["first_author"], "year": r["year"],
            "venue": r["venue"], "title_short": r["title_short"], "instrument": r["instrument"],
            "relevant_lunar_cpr_ice_study": relevant,
            "screen_level_original": r["screen_level"],
            "access": access,
            "measured_ENL_reported": claim("reports_measured_enl_of_analysed_product"),
            "critical_value_reported": claim("reports_perpixel_floor_at_stated_N"),
            "exceedance_rate_reported": claim("reports_fp_rate_for_cpr_criterion"),
            "ratio_bias_corrected": ("not_assessed" if access == "full_text" and not (rs and rs.get("obtained"))
                                     else ("not_assessed" if not relevant else NF)),
            "note": r.get("note", ""),
        }
        if rs:
            rec["rescreen"] = {"date": RESCREEN_DATE, "query": rs["query"],
                               "attempts": [{"url": u, "outcome": o} for u, o in rs["attempts"]],
                               "obtained": rs.get("obtained"), "doi": rs.get("doi"),
                               "note": rs.get("note")}
            if rs.get("obtained"):
                rec.update({k: rs["extract"][k] for k in
                            ("measured_ENL_reported", "critical_value_reported",
                             "exceedance_rate_reported", "ratio_bias_corrected")})
                rec["data_statement"] = rs["extract"]["data_statement"]
        if rid == "4":   # Sinha et al. 2026, npj Space Exploration
            rec["aggregation_record"] = SINHA_2026_AGGREGATION
        if rid == "2":   # Spudis et al. 2013, JGR Planets
            rec["measured_ENL_reported"] = "yes"
            rec["measured_ENL_quote"] = SPUDIS_2013_QUOTE
            rec["measured_ENL_note"] = ("para. [13]; the figure is attributed to unpublished "
                                        "analysis, not to a stated estimator")
        for k in ("measured_ENL_reported", "critical_value_reported",
                  "exceedance_rate_reported", "ratio_bias_corrected"):
            assert rec[k] in VALUES, (rid, k, rec[k])
        records.append(rec)

    rel = [x for x in records if x["relevant_lunar_cpr_ice_study"]]
    counts = {"unique": len(records), "relevant": len(rel),
              "access": {a: sum(1 for x in rel if x["access"] == a)
                         for a in ("full_text", "abstract_only", "inaccessible")},
              "rescreened": len(RESCREEN),
              "full_text_obtained_on_rescreen": sum(1 for v in RESCREEN.values() if v.get("obtained")),
              "claims_yes": {k: [x["id"] for x in rel if x[k] == "yes"] for k in
                             ("measured_ENL_reported", "critical_value_reported",
                              "exceedance_rate_reported", "ratio_bias_corrected")}}
    doc = {
        "schema": "lunar-ice/literature-screen/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/literature_screen.py",
        "record_csv": "docs/literature_search_record.csv (unmodified; G29 asserts its counts)",
        "value_set": list(VALUES),
        "value_rules": {
            "no": "the whole item was read and the claim is absent",
            NF: "only an abstract (or nothing) was reachable in this pass; a statement about "
                "access, not about the paper",
            "not_assessed": "not examined for this claim (excluded records; and "
                            "ratio_bias_corrected for the twelve cited full texts, which "
                            "the original screen did not assess)"},
        "original_search": ORIGINAL_SEARCH,
        "rescreen": {"date": RESCREEN_DATE, "tool": "WebSearch / WebFetch from the analysis host; "
                                                    "no institutional access",
                     "records": RESCREEN},
        "counts": counts,
        "records": records,
    }
    OUT_JSON.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")

    # ---- the summary table ----------------------------------------------
    short = {"yes": "yes", "no": "no", NF: "n/f", "not_assessed": "n/a"}
    lines = ["# Literature screen — access and per-claim record", "",
             f"Generated by `backend/scripts/literature_screen.py` from "
             f"`docs/literature_search_record.csv`; re-screen of abstract-only records on "
             f"{RESCREEN_DATE}. Values: **yes**, **no** (whole item read, claim absent), "
             "**n/f** = not found in accessible material (only an abstract reached), "
             "**n/a** = not assessed.", "",
             f"Relevant lunar CPR-ice studies: {counts['relevant']} of {counts['unique']} unique "
             f"records; access on the relevant set: {counts['access']['full_text']} full text, "
             f"{counts['access']['abstract_only']} abstract only, "
             f"{counts['access']['inaccessible']} inaccessible. Re-screened "
             f"{counts['rescreened']}; full text obtained for "
             f"{counts['full_text_obtained_on_rescreen']}.", "",
             "| id | first author | year | relevant | access | ENL | critical value | exceedance | bias corr. | note |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for x in records:
        note = x.get("measured_ENL_quote") or x.get("data_statement") or \
            (x.get("rescreen", {}) or {}).get("note") or x.get("note") or ""
        lines.append(f"| {x['id']} | {x['first_author']} | {x['year']} | "
                     f"{'yes' if x['relevant_lunar_cpr_ice_study'] else 'no'} | {x['access']} | "
                     f"{short[x['measured_ENL_reported']]} | {short[x['critical_value_reported']]} | "
                     f"{short[x['exceedance_rate_reported']]} | {short[x['ratio_bias_corrected']]} | "
                     f"{note.replace('|', '/')} |")
    lines += ["", "## Search strings (original, executed " + ORIGINAL_SEARCH["executed"] + ")", ""]
    lines += [f"- `{s}`" for s in ORIGINAL_SEARCH["strings"]]
    lines += ["", f"## Re-screen queries ({RESCREEN_DATE})", ""]
    for rid, v in RESCREEN.items():
        got = v.get("obtained") or "not obtained"
        lines.append(f"- id {rid}: `{v['query']}` — {got}; " +
                     "; ".join(f"{u} → {o}" for u, o in v["attempts"]))
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(counts, indent=2))
    print(f"\n  wrote {OUT_JSON.relative_to(BASE_DIR)} and {OUT_MD.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
