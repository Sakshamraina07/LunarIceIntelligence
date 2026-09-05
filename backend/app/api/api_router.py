"""
FastAPI API Router exposing modular endpoints for Lunar Ice Intelligence.
"""

from fastapi import APIRouter, HTTPException, Query, Response
from typing import Optional, Dict, Any

from app.core.config import settings
from app.demo.lunar_generator import demo_generator_enabled
from app.services.mission_service import mission_orchestrator
from app.modules.module_g_volume import run_sensitivity_sweep
from app.modules.experiments_runner import run_all_research_experiments
from app.services.pdf_generator import generate_mission_pdf_report

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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sensitivity/{parameter_name}")
def get_sensitivity_analysis(
    parameter_name: str,
    base_area_km2: float = Query(8.75, description="Base candidate ice area in km2")
):
    valid_params = ["cpr_threshold", "dop_threshold", "assumed_depth_m", "ice_fraction"]
    if parameter_name not in valid_params:
        raise HTTPException(status_code=400, detail=f"Parameter must be one of: {valid_params}")
    return run_sensitivity_sweep(parameter_name, base_candidate_area_km2=base_area_km2)


@router.get("/experiments")
def get_research_experiments(crater_id: str = "shackleton"):
    return run_all_research_experiments(crater_id=crater_id)


@router.get("/report/pdf/{crater_id}")
def download_mission_report_pdf(crater_id: str):
    mission_data = mission_orchestrator.run_full_mission_pipeline(crater_id=crater_id)

    # The absent state has no numeric sections, so there is nothing to typeset.
    # 409 rather than 500: the request was well-formed, the crater simply has no
    # ingested product. A PDF is the one artefact that leaves the browser without
    # the badge, so this is a refusal and not a thinner report.
    if mission_data.get("status") != "OK":
        raise HTTPException(
            status_code=409,
            detail={
                "error": "NOT_INGESTED",
                "message": f"No mission report can be issued for {crater_id}.",
                "gate": mission_data.get("gate"),
            },
        )

    pdf_payload = {
        "crater_name": mission_data["selected_crater"].name,
        "data_mode": mission_data["data_mode"],
        "candidate_area_km2": mission_data["ice"].scientific_candidate_area_km2,
        "expected_volume_m3": mission_data["volume"].expected_volume_m3,
        "recommended_site": mission_data["recommended_landing_site"].name,
        "rover_distance_km": mission_data["rover_routes"]["Science-Aware"].total_distance_km,
        "rover_energy_wh": mission_data["rover_routes"]["Science-Aware"].total_energy_wh,
        "landing_sites": [s.dict() for s in mission_data["landing_sites"]],
        "rover_routes": {k: v.dict() for k, v in mission_data["rover_routes"].items()}
    }

    pdf_bytes = generate_mission_pdf_report(pdf_payload)

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

