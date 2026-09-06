"""
report_data.py -- the report's inputs, read from the artifacts the UI reads.

WHY THIS EXISTS
---------------
The PDF was generated from `mission_service`'s payload. That payload still
carries the pre-Phase-3 world: five hardcoded landing sites from
`module_e_landing.py` named Alpha Ridge, Beta Plateau, Gamma Bench, Delta Spur
and Epsilon Crest, and a rover distance in kilometres with an energy in watt
hours for an invented 30 kg vehicle. So a formal report -- the one artefact that
leaves the browser and is read without the provenance badge beside it -- was
printing five sites that no longer exist and marking one RECOMMENDED, beside a
rover figure the screen reports as NO DATA.

This is the same defect Phase 1 fixed for the verdict: a second computation of
an answer that already exists. The fix is the same one. THE REPORT IS A
RENDERING OF THE ARTIFACTS, NOT A SECOND COMPUTATION. Every figure in it comes
from the files below, which are the files the mission screen reads:

    frontend/public/analysis/<crater>.json    the verdict, the masks, the marks
    frontend/public/analysis/landing_sites.json   Phase 3, the searched sites
    frontend/public/analysis/traverse.json        Phase 4, the planned routes
    frontend/public/analysis/detection_statistics.json  Phase 8, floor and CI

There is no fallback. A missing artifact raises, and the endpoint refuses to
issue a report -- the same rule the DEMO gate follows, for the same reason: a
report that degrades quietly is worse than no report.

`backend/scripts/assert_pdf_agrees_with_analysis.py` re-reads the rendered PDF
and fails the build if any figure it prints is not in these files.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

BASE_DIR = Path(__file__).resolve().parents[3]
ANALYSIS_DIR = BASE_DIR / "frontend" / "public" / "analysis"


class ReportArtifactsMissing(RuntimeError):
    """Raised when an artifact the report is a rendering of is not on disk."""


def _read(name: str, why: str) -> Dict[str, Any]:
    p = ANALYSIS_DIR / name
    if not p.exists():
        raise ReportArtifactsMissing(
            f"{p.relative_to(BASE_DIR)} is not on disk, so {why} cannot be reported. "
            "The PDF is a rendering of the analysis artifacts and does not compute "
            "them a second time; without the file there is nothing to render and "
            "the report is refused rather than filled in."
        )
    return json.loads(p.read_text(encoding="utf-8"))


def load_report_bundle(crater_id: str) -> Dict[str, Any]:
    """Everything the report prints, from the files the screen reads.

    Returns the four documents verbatim. NOTHING IS RE-DERIVED HERE -- not a
    rounding, not a unit conversion, not a sum. The generator formats what it is
    given, so a figure in the report and the same figure on screen cannot come
    from two different calculations.
    """
    analysis = _read(f"{crater_id}.json", "the verdict")
    if analysis.get("schema") != "lunar-ice/analysis/1":
        raise ReportArtifactsMissing(
            f"{crater_id}.json declares schema {analysis.get('schema')!r}; the report "
            "reads 'lunar-ice/analysis/1'. A half-understood document would be "
            "rendered under labels that no longer mean what they say."
        )
    if analysis.get("data_mode") != "REAL":
        raise ReportArtifactsMissing(
            f"{crater_id}.json declares data_mode {analysis.get('data_mode')!r}, not 'REAL'."
        )

    # Phase 3, 4 and 8 are OPTIONAL in the sense that a host may not have run
    # them -- and their absence is reported as absence, in the report, in the
    # section that would have held them. It is never reported as a shorter
    # report with no gap where the section was.
    def optional(name: str, why: str):
        try:
            return _read(name, why)
        except ReportArtifactsMissing as e:
            return {"__absent__": str(e)}

    return {
        "crater_id": crater_id,
        "analysis": analysis,
        "sites": optional("landing_sites.json", "the landing sites"),
        "traverse": optional("traverse.json", "the traverse"),
        "detection": optional("detection_statistics.json", "the detection statistics"),
    }


def absent(doc: Dict[str, Any]) -> str | None:
    """The reason a section has nothing to show, or None when it does."""
    return doc.get("__absent__") if isinstance(doc, dict) else "not a document"
