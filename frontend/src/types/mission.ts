export interface ProvenanceMetadata {
  dataset_name: string;
  data_source: string;
  data_mode: string;
  algorithm: string;
  parameters: Record<string, any>;
  model_version: string;
  random_seed?: number;
  timestamp: string;
}

export interface CraterInfo {
  id: string;
  name: string;
  latitude_deg: number;
  longitude_deg: number;
  diameter_km: number;
  depth_km: number;
  target_description: string;
  is_psr_present: boolean;
  is_doubly_shadowed_candidate: boolean;
  is_real_data?: boolean;
  is_active?: boolean;
  status_label?: string;
  product_id?: string;
  observed_date?: string;
  bounds?: Record<string, number>;
}

export interface PSRAnalysisResult {
  crater_id: string;
  total_area_km2: number;
  psr_area_km2: number;
  psr_area_fraction: number;
  doubly_shadowed_area_km2: number;
  mean_illumination_fraction: number;
  shadow_depth_estimate_m: number;
  confidence_level: 'Low' | 'Medium' | 'High';
  provenance: ProvenanceMetadata;
}

export interface RadarAnalysisResult {
  crater_id: string;
  mean_cpr: number;
  max_cpr: number;
  mean_dop: number;
  min_dop: number;
  cpr_threshold_used: number;
  dop_threshold_used: number;
  radar_anomalous_area_km2: number;
  screening_pass_fraction: number;
  scientific_interpretation: string;
  provenance: ProvenanceMetadata;
}

export interface IceIntelligenceResult {
  crater_id: string;
  scientific_candidate_area_km2: number;
  ml_ice_likelihood_mean: number;
  ml_ice_likelihood_max: number;
  confidence: 'Low' | 'Medium' | 'High';
  scientific_screening_status: 'PASS' | 'FAIL';
  evidence_checklist: Record<string, boolean>;
  explainability_notes: string[];
  provenance: ProvenanceMetadata;
}

export interface TerrainAnalysisResult {
  crater_id: string;
  mean_slope_deg: number;
  max_slope_deg: number;
  safe_slope_fraction: number;
  mean_roughness: number;
  mean_hazard_score: number;
  high_hazard_area_km2: number;
  weights_used: Record<string, number>;
  provenance: ProvenanceMetadata;
}

export interface CandidateLandingSite {
  site_id: string;
  name: string;
  grid_x: number;
  grid_y: number;
  lat_deg: number;
  lon_deg: number;
  slope_deg: number;
  roughness: number;
  hazard_score: number;
  illumination_fraction: number;
  distance_to_target_km: number;
  scientific_value: number;
  composite_landing_score: number;
  rank: number;
  is_recommended: boolean;
  selection_rationale: string[];
}

export interface PathWaypoint {
  x: number;
  y: number;
  elevation_m: number;
  slope_deg: number;
  hazard_score: number;
  illumination: number;
  science_value: number;
  cumulative_distance_km: number;
  cumulative_energy_wh: number;
}

export interface RoverRouteResult {
  strategy: 'Shortest' | 'Safest' | 'Science-Aware';
  algorithm_used: 'A*' | 'Dijkstra';
  path_found: boolean;
  path_length_waypoints: number;
  total_distance_km: number;
  estimated_travel_time_hours: number;
  total_energy_wh: number;
  mean_hazard_encountered: number;
  max_slope_encountered_deg: number;
  total_scientific_value_collected: number;
  waypoints: PathWaypoint[];
  avoidance_explanations: string[];
  failure_reason?: string | null;
}

export interface IceVolumeEstimateResult {
  candidate_area_km2: number;
  conservative_volume_m3: number;
  conservative_mass_metric_tons: number;
  conservative_assumptions: Record<string, any>;
  expected_volume_m3: number;
  expected_mass_metric_tons: number;
  expected_assumptions: Record<string, any>;
  upper_volume_m3: number;
  upper_mass_metric_tons: number;
  upper_assumptions: Record<string, any>;
  scientific_label: string;
  limitation_statement: string;
  provenance: ProvenanceMetadata;
}

export interface SensitivityPoint {
  parameter_name: string;
  parameter_value: number;
  candidate_ice_area_km2: number;
  expected_volume_m3: number;
  best_landing_site_id: string;
  rover_distance_km: number;
  rover_energy_wh: number;
}

export interface SensitivityAnalysisResult {
  parameter_tested: string;
  baseline_value: number;
  sweep_values: number[];
  results: SensitivityPoint[];
  sensitivity_summary: string;
}

export interface ExperimentResult {
  experiment_id: string;
  title: string;
  objective: string;
  metrics: Record<string, any>;
  qualitative_observations: string[];
  scientific_conclusion: string;
  is_synthetic_evaluation: boolean;
}

export interface AblationStepResult {
  step_name: string;
  factors_included: string[];
  path_distance_km: number;
  mean_hazard: number;
  energy_wh: number;
  science_collected: number;
  path_deviation_description: string;
}

export interface MissionState {
  selected_crater: CraterInfo;
  data_mode: 'DEMO' | 'REAL';
  psr: PSRAnalysisResult;
  radar: RadarAnalysisResult;
  ice: IceIntelligenceResult;
  terrain: TerrainAnalysisResult;
  landing_sites: CandidateLandingSite[];
  recommended_landing_site: CandidateLandingSite;
  rover_routes: Record<string, RoverRouteResult>;
  volume: IceVolumeEstimateResult;
  raster_layers: Record<string, string>;
  grid_dimensions: { width: number; height: number; pixel_scale_m: number };
  target_coordinates: { x: number; y: number };
  generated_at: string;
}
