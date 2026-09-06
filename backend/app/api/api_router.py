"""
FastAPI API Router exposing modular endpoints for Lunar Ice Intelligence.
"""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Response
from typing import Optional, Dict, Any

from app.core.config import settings
from app.core.exceptions import UnknownCraterError
from app.demo.lunar_generator import demo_generator_enabled
from app.services.mission_service import mission_orchestrator
from app.services.pdf_generator import generate_mission_pdf_report
from app.services.report_data import load_report_bundle, ReportArtifactsMissing

router = APIRouter()


@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "system": settings.PROJECT_NAME,
        "version": settings.VERSION,
        # A request, not a verdict: eligibility is per crater. Named so this
        # endpoint cannot be quoted as "the system is in REAL mode".
        "requested_data_mode": settings.DATA_MODE,
        "demo_generator_enabled": demo_generator_enabled(),
    }


@router.get("/craters")
def get_crater_catalog():
    return mission_orchestrator.get_available_craters()


@router.get("/mission/{crater_id}")
def get_mission_state(
    crater_id: str,
    data_mode: str = Query("REAL", description="Requested data mode. Eligibility is decided per crater by real_data_gate; an un-ingested crater answers NOT_INGESTED regardless."),
    cpr_threshold: Optional[float] = Query(None, description="CPR Screening Threshold"),
    dop_threshold: Optional[float] = Query(None, description="DOP Screening Threshold"),
    ice_depth_m: Optional[float] = Query(None, description="Assumed ice deposit depth in meters"),
    ice_fraction: Optional[float] = Query(None, description="Assumed ice volumetric pore fraction"),
    algorithm: str = Query("A*", description="Path planning algorithm: A* or Dijkstra")
):
    try:
        mission_data = mission_orchestrator.run_full_mission_pipeline(
            crater_id=crater_id,
            data_mode=data_mode,
            cpr_threshold=cpr_threshold,
            dop_threshold=dop_threshold,
            ice_depth_m=ice_depth_m,
            ice_fraction=ice_fraction,
            rover_algorithm=algorithm
        )
        return mission_data
    except UnknownCraterError as e:
        # 404, not 500 and not a Shackleton payload. The orchestrator used to
        # answer an unknown id with CRATER_CATALOG["shackleton"], so a typo
        # returned a complete confident payload attributed to the wrong crater.
        raise HTTPException(status_code=404, detail={"error": e.error_code,
                                                     "message": e.message,
                                                     **e.details})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sensitivity/{parameter_name}")
def get_sensitivity_analysis(
    parameter_name: str,
    crater_id: str = Query("faustini", description="Crater whose precomputed sweep to serve"),
):
    """
    Serve the PRECOMPUTED sweep, or refuse.

    This endpoint used to accept `base_area_km2` (defaulting to 8.75, a number
    with no origin in this project) and hand it to run_sensitivity_sweep, which
    scaled it by a closed-form expression and returned the result as a threshold
    study. No raster was read and no threshold was applied to any data.

    The real sweep is computed offline from the native arrays by
    backend/scripts/build_analysis.py and committed alongside layers.json. This
    reads that file. If the crater has no precomputed analysis, the answer is
    404 -- not a curve.
    """
    valid_params = ["cpr_threshold", "dop_threshold", "assumed_depth_m", "ice_fraction"]
    if parameter_name not in valid_params:
        raise HTTPException(status_code=400, detail=f"Parameter must be one of: {valid_params}")

    analysis_path = (Path(__file__).resolve().parents[3]
                     / "frontend" / "public" / "analysis" / f"{crater_id}.json")
    if not analysis_path.is_file():
        raise HTTPException(
            status_code=404,
            detail={
                "error": "NO_PRECOMPUTED_ANALYSIS",
                "crater_id": crater_id,
                "message": (f"No precomputed analysis exists for {crater_id}, so no measured sweep "
                            f"can be served. Run: python backend/scripts/build_analysis.py "
                            f"{crater_id}"),
            },
        )

    doc = json.loads(analysis_path.read_text(encoding="utf-8"))
    block = (doc.get("sensitivity") or {}).get(parameter_name)
    if not block:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "PARAMETER_NOT_SWEPT",
                "parameter": parameter_name,
                "message": f"{analysis_path.name} carries no sweep for {parameter_name}.",
            },
        )

    return {
        "parameter_tested": parameter_name,
        "crater_id": crater_id,
        "source": "frontend/public/analysis/%s.json (build_analysis.py)" % crater_id,
        "generated_utc": doc.get("generated_utc"),
        "data_mode": doc.get("data_mode"),
        "baseline_value": block.get("baseline"),
        "grid_source": block.get("grid_source"),
        "held_constant": block.get("held_constant"),
        "sweep_values": [r["threshold"] for r in block.get("rows", [])],
        "results": block.get("rows", []),
        "withheld_columns": (doc.get("sensitivity") or {}).get("withheld_columns"),
        "sensitivity_summary": (doc.get("sensitivity") or {}).get("note"),
    }


@router.get("/report/pdf/{crater_id}")
def download_mission_report_pdf(crater_id: str):
    """The report, rendered from the artifacts the mission screen reads.

    THIS USED TO RUN THE FULL MISSION PIPELINE AND TYPESET ITS PAYLOAD. That
    payload still carries the pre-Phase-3 world -- five hardcoded landing sites
    from module_e_landing.py, and a rover distance in km with an energy in Wh
    for an invented 30 kg vehicle -- so the PDF was printing five sites that no
    longer exist, one of them marked RECOMMENDED, beside a traverse figure the
    screen reports as NO DATA.

    The report is now a RENDERING of the same four documents the UI reads. It is
    the Phase 1 fix applied to the one surface that never got it: a report that
    computes its own answer is a second source of truth, and this project has
    spent long enough removing those.

    The DEMO gate is unchanged in effect and stricter in form: the analysis
    artifact carries its own data_mode, and both this endpoint and the generator
    refuse anything but REAL.
    """
    try:
        bundle = load_report_bundle(crater_id)
    except ReportArtifactsMissing as exc:
        # 409, not 500: the request was well-formed and the artifact is simply
        # not on this host. A PDF is the one artefact that leaves the browser
        # without the badge, so this is a refusal and not a thinner report.
        raise HTTPException(
            status_code=409,
            detail={
                "error": "NO_ANALYSIS_ARTIFACT",
                "message": f"No mission report can be issued for {crater_id}.",
                "reason": str(exc),
            },
        )

    pdf_bytes = generate_mission_pdf_report(bundle)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Lunar_Ice_Report_{crater_id}.pdf"}
    )


@router.get("/ingest/status")
def get_pradan_ingestion_status():
    from app.ingestion.pradan_pipeline import PRADAN_DATA_DIR, ensure_pradan_directories
    from app.ingestion.real_data_gate import hash_table
    ensure_pradan_directories()

    dfsar_files = [f.name for f in (PRADAN_DATA_DIR / "dfsar").glob("*.tif")]
    ohrc_files = [f.name for f in (PRADAN_DATA_DIR / "ohrc").glob("*.tif")]
    dem_files = [f.name for f in (PRADAN_DATA_DIR / "dem").glob("*.tif")]

    catalog = mission_orchestrator.get_available_craters()
    rows = hash_table(catalog)

    return {
        "status": "ready",
        "data_directory": str(PRADAN_DATA_DIR),
        "available_files": {
            "dfsar": dfsar_files,
            "ohrc": ohrc_files,
            "dem": dem_files
        },
        # A count of .tif files is not evidence of anything. `has_real_data` used
        # to be `len(dfsar) > 0 and len(dem) > 0`, which was true on a host whose
        # only rasters were seeded copies. Eligibility is per crater and comes
        # from the catalogue; the digests are published here so a reviewer can
        # see for themselves which of these filenames are the same bytes.
        "eligible_craters": sorted({r["crater_id"] for r in rows if r["eligible"]}),
        "raster_provenance": rows,
    }


@router.post("/ingest/generate-samples")
def generate_sample_pradan_dataset(crater_id: str = "shackleton"):
    from app.ingestion.pradan_pipeline import create_sample_georeferenced_pradan_data
    try:
        created = create_sample_georeferenced_pradan_data(crater_id=crater_id)
    except RuntimeError as e:
        # Writes seeded rasters under real product filenames. That is how
        # `shackleton_lola_dem.tif` came to be a byte copy of Faustini's crop.
        raise HTTPException(status_code=403, detail=str(e))
    return {
        "message": f"Wrote SEEDED sample rasters for {crater_id} — not measurements",
        "files_created": created
    }


@router.post("/copilot/ask")
def ask_henry_copilot(payload: Dict[str, Any]):
    from app.services.ai_copilot import henry_ai_copilot
    prompt = payload.get("prompt", "")
    crater_id = payload.get("crater_id", "shackleton")
    mission_context = payload.get("mission_context")

    if not prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt must not be empty.")

    if not mission_context and crater_id:
        try:
            mission_context = mission_orchestrator.run_full_mission_pipeline(crater_id=crater_id)
        except Exception:
            mission_context = None

    result = henry_ai_copilot.ask(prompt, mission_context)
    return result

