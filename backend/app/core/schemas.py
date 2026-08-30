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
    regional_classification: str = "Low/No ice signature (Typical dry regolith)"
    anomaly_classification: str = "Candidate signature consistent with potential ice"
    classification_label: str = "Low/No ice signature"
    data_source_tag: str = "Simulated placeholder — pending real data"
    provenance: ProvenanceMetadata


class IceIntelligenceResult(BaseModel):
    crater_id: str
    scientific_candidate_area_km2: float
    ml_ice_likelihood_mean: float
    ml_ice_likelihood_max: float
    confidence: str  # 'Low', 'Medium', 'High'
    scientific_screening_status: str  # 'PASS' or 'FAIL'
    evidence_checklist: Dict[str, bool]
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
    scientific_value: float  # 0 to 1
    composite_landing_score: float  # 0 to 100
    rank: int
    is_recommended: bool
    selection_rationale: List[str]


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
    parameter_name: str
    parameter_value: float
    candidate_ice_area_km2: float
    expected_volume_m3: float
    best_landing_site_id: str
    rover_distance_km: float
    rover_energy_wh: float


class SensitivityAnalysisResult(BaseModel):
    parameter_tested: str
    baseline_value: float
    sweep_values: List[float]
    results: List[SensitivityPoint]
    sensitivity_summary: str


class ExperimentResult(BaseModel):
    experiment_id: str
    title: str
    objective: str
    metrics: Dict[str, Any]
    qualitative_observations: List[str]
    scientific_conclusion: str
    is_synthetic_evaluation: bool


class AblationStepResult(BaseModel):
    step_name: str
    factors_included: List[str]
    path_distance_km: float
    mean_hazard: float
    energy_wh: float
    science_collected: float
    path_deviation_description: str


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
