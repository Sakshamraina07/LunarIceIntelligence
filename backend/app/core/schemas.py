"""
Pydantic Schemas and Data Contracts for Lunar Ice Intelligence.
Enforces strict typing, input validation, and clear data provenance across all modules.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone


class ProvenanceMetadata(BaseModel):
    dataset_name: str
    data_source: str
    data_mode: str  # 'DEMO' or 'REAL'
    algorithm: str
    parameters: Dict[str, Any]
    model_version: str
    random_seed: Optional[int] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CraterInfo(BaseModel):
    id: str
    name: str
    latitude_deg: float
    longitude_deg: float
    diameter_km: float
    depth_km: float
    target_description: str
    is_psr_present: bool
    is_doubly_shadowed_candidate: bool
    is_real_data: bool = False
    is_active: bool = True
    status_label: Optional[str] = None
    product_id: Optional[str] = None
    observed_date: Optional[str] = None
    bounds: Optional[Dict[str, float]] = None


class PSRAnalysisResult(BaseModel):
    crater_id: str
    total_area_km2: float
    psr_area_km2: float
    psr_area_fraction: float
    doubly_shadowed_area_km2: float
    mean_illumination_fraction: float
    shadow_depth_estimate_m: float
    confidence_level: str  # 'Low', 'Medium', 'High'
    provenance: ProvenanceMetadata


class RadarAnalysisResult(BaseModel):
    crater_id: str
    mean_cpr: float
    max_cpr: float
    mean_dop: float
    min_dop: float
    cpr_threshold_used: float
    dop_threshold_used: float
    radar_anomalous_area_km2: float
    screening_pass_fraction: float
    scientific_interpretation: str
    # All four were defaulted, and `anomaly_classification` defaulted to
    # "Candidate signature consistent with potential ice" — a caller who forgot
    # the field inherited the strongest possible claim about the scene. Required
    # now: a caller who forgets must fail, not inherit an ice detection.
    regional_classification: str
    anomaly_classification: str
    classification_label: str
    data_source_tag: str
    provenance: ProvenanceMetadata


class IceIntelligenceResult(BaseModel):
    crater_id: str
    scientific_candidate_area_km2: float
    # None, not 0.0. The Random Forest that produced these was unwired in PRD
    # Phase 1C — it was fitted to np.random.uniform labels whose ice class lies
    # outside this product's achievable CPR range. A 0.0 here would read as
    # "the model ran and found no ice"; None reads as "no model ran".
    ml_ice_likelihood_mean: Optional[float] = None
    ml_ice_likelihood_max: Optional[float] = None
    ml_model_status: str
    confidence: str  # 'Low', 'Medium', 'High'
    scientific_screening_status: str  # 'PASS' or 'FAIL'
    # A criterion that cannot be evaluated is not a failed criterion. False
    # would collapse "tested and failed" into "never tested", which is exactly
    # the distinction the whole provenance discipline exists to keep.
    evidence_checklist: Dict[str, Optional[bool]]
    explainability_notes: List[str]
    provenance: ProvenanceMetadata


class TerrainAnalysisResult(BaseModel):
    crater_id: str
    mean_slope_deg: float
    max_slope_deg: float
    safe_slope_fraction: float
    mean_roughness: float
    mean_hazard_score: float
    high_hazard_area_km2: float
    weights_used: Dict[str, float]
    provenance: ProvenanceMetadata


class CandidateLandingSite(BaseModel):
    site_id: str
    name: str
    grid_x: int
    grid_y: int
    lat_deg: float
    lon_deg: float
    slope_deg: float
    roughness: float
    hazard_score: float  # 0 to 1
    illumination_fraction: float  # 0 to 1
    distance_to_target_km: float
    # Renamed from `scientific_value`. It contains only a distance term, so the
    # old name claimed a scientific merit the number does not carry — and it was
    # then blended into the composite score alongside the distance term it
    # duplicates. It is reported, not scored, until the Phase 3 site search.
    distance_proximity_index: float  # 0 to 1
    composite_landing_score: float  # 0 to 100
    rank: int
    is_recommended: bool
    selection_rationale: List[str]
    # Without these, a fabricated site is structurally unlabelable.
    data_mode: str
    provenance: ProvenanceMetadata


class PathWaypoint(BaseModel):
    x: int
    y: int
    elevation_m: float
    slope_deg: float
    hazard_score: float
    illumination: float
    science_value: float
    cumulative_distance_km: float
    cumulative_energy_wh: float


class RoverRouteResult(BaseModel):
    strategy: str  # 'Shortest', 'Safest', 'Science-Aware'
    algorithm_used: str  # 'A*' or 'Dijkstra'
    path_found: bool
    path_length_waypoints: int
    total_distance_km: float
    estimated_travel_time_hours: float
    total_energy_wh: float
    mean_hazard_encountered: float
    max_slope_encountered_deg: float
    total_scientific_value_collected: float
    waypoints: List[PathWaypoint]
    avoidance_explanations: List[str]
    failure_reason: Optional[str] = None
    data_mode: str
    provenance: ProvenanceMetadata


class IceVolumeEstimateResult(BaseModel):
    candidate_area_km2: float
    conservative_volume_m3: float
    conservative_mass_metric_tons: float
    conservative_assumptions: Dict[str, Any]

    expected_volume_m3: float
    expected_mass_metric_tons: float
    expected_assumptions: Dict[str, Any]

    upper_volume_m3: float
    upper_mass_metric_tons: float
    upper_assumptions: Dict[str, Any]

    scientific_label: str  # Must be "Estimated Ice-Equivalent Volume"
    limitation_statement: str
    provenance: ProvenanceMetadata


class SensitivityPoint(BaseModel):
    """
    One row of a real sweep, computed by re-thresholding the native arrays in
    backend/scripts/build_analysis.py.

    `best_landing_site_id`, `rover_distance_km` and `rover_energy_wh` were
    removed in PRD Phase 1B. They were `"site_1"` constant, `11.2 + val * 0.1`
    and `145.0 + val * 2.5` — straight lines through the swept parameter with no
    planner behind them. They return when Phases 3 and 4 can actually replan.
    """
    parameter_name: str
    parameter_value: float
    is_configured_value: bool
    candidate_px: Optional[int] = None
    candidate_ice_area_km2: float
    candidate_area_provenance: str
    expected_volume_m3: float
    volume_provenance: str


class SensitivityAnalysisResult(BaseModel):
    parameter_tested: str
    baseline_value: float
    grid_source: str
    held_constant: Dict[str, float]
    sweep_values: List[float]
    results: List[SensitivityPoint]
    sensitivity_summary: str
    withheld_columns: Dict[str, str]
    data_mode: str
    provenance: ProvenanceMetadata


class MissionState(BaseModel):
    selected_crater: CraterInfo
    data_mode: str
    psr: PSRAnalysisResult
    radar: RadarAnalysisResult
    ice: IceIntelligenceResult
    terrain: TerrainAnalysisResult
    landing_sites: List[CandidateLandingSite]
    recommended_landing_site: CandidateLandingSite
    rover_routes: Dict[str, RoverRouteResult]
    volume: IceVolumeEstimateResult
    generated_at: str
    provenance: ProvenanceMetadata
