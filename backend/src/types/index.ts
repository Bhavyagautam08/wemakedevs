/**
 * DhuanAlert Backend Domain & API Contracts
 */

export interface Hotspot {
  detection_id: string;
  latitude: number;
  longitude: number;
  acq_timestamp: string;
  confidence: number;
  frp: number;
  satellite?: string;
}

export interface WeatherObservation {
  wind_speed_mps: number;
  wind_direction_deg: number;
  u_mps: number;
  v_mps: number;
  boundary_layer_height_m: number;
  temperature_c: number;
  relative_humidity_pct?: number;
  forecast_timestamp: string;
}

export interface LiveSourceStatus {
  name: string;
  status: "ok" | "error";
  count: number;
  error?: string;
}

export interface LiveDataSnapshot {
  fetched_at: string;
  sources: {
    fires: LiveSourceStatus;
    weather: LiveSourceStatus;
  };
  fires: Array<Hotspot & { confidence_class?: string | null }>;
  weather: WeatherObservation[];
}

export interface School {
  school_id: string;
  name: string;
  latitude: number;
  longitude: number;
  district: string;
  state?: string;
}

export type RiskBand = "LOW" | "MODERATE" | "HIGH" | "VERY_HIGH";

export interface SchoolRiskAssessment {
  school_id: string;
  name: string;
  district: string;
  distance_to_fire_km: number;
  predicted_arrival_time?: string | null;
  peak_concentration: number;
  exposure_duration_minutes: number;
  ensemble_members_affected: number;
  impact_probability: number;
  uncertainty: number;
  risk_score: number;
  risk_band: RiskBand;
}

export interface EnsembleMemberSummary {
  member_id: string;
  name: string;
  wind_speed_factor: number;
  wind_dir_shift: number;
  peak_concentration: number;
  mean_concentration: number;
}

export interface EnsembleOutput {
  member_count: number;
  members: EnsembleMemberSummary[];
  affected_area_union_geojson: any;
  affected_area_intersection_geojson: any;
}

export interface TimelineSlice {
  horizon_offset_hours: number;
  timestamp: string;
  plume_center_lat: number;
  plume_center_lon: number;
  plume_area_sq_km: number;
  affected_schools_count: number;
  max_intensity: number;
  contour_geojson: any;
}

export interface PredictiveOutput {
  prediction_id: string;
  generated_at: string;
  valid_from: string;
  valid_until: string;
  model: {
    type: string;
    version: string;
    mode: string;
  };
  fire: {
    fire_id: string;
    latitude: number;
    longitude: number;
    hotspot_count: number;
    total_frp_mw: number;
    source_strength: number;
    source_freshness_hours: number;
    status: string;
  };
  weather: {
    wind_speed_mps: number;
    wind_direction_deg: number;
    u_mps: number;
    v_mps: number;
    boundary_layer_height_m: number;
    temperature_c: number;
  };
  simulation: {
    timestep_seconds: number;
    horizon_hours: number;
    particle_count: number;
    diffusion_kx: number;
    diffusion_ky: number;
    decay_rate: number;
  };
  ensemble: EnsembleOutput;
  schools: SchoolRiskAssessment[];
  timeline: TimelineSlice[];
  map_geojson: any;
  provenance: Record<string, string | null>;
}

export interface BilingualText {
  en: string;
  hi: string;
}

export interface RecommendedAction {
  action_id: string;
  en: string;
  hi: string;
  policy_basis: string;
}

export type PublicationStatus = "APPROVED" | "DRAFT" | "MANUAL_REVIEW_REQUIRED" | "REJECTED";

export interface AdvisoryValidation {
  policy_check: "PASSED" | "FAILED" | "MANUAL_REVIEW_REQUIRED";
  claim_check: "PASSED" | "REJECTED";
  publication_status: PublicationStatus;
  rejection_reason?: string | null;
}

export interface AdvisoryOutput {
  advisory_id: string;
  severity: RiskBand;
  headline: BilingualText;
  summary: BilingualText;
  affected_area: {
    name: string;
    school_count: number;
  };
  time_window: {
    start: string;
    end: string;
  };
  recommended_actions: RecommendedAction[];
  risk: {
    risk_band: RiskBand;
    impact_probability: number;
  };
  evidence: Array<{ source_id: string; type: string }>;
  validation: AdvisoryValidation;
  model_metadata: Record<string, any>;
}

export interface FrontendPayload {
  prediction: PredictiveOutput;
  advisory: AdvisoryOutput;
}

export interface CedarAuthorizationContext {
  action_id: string;
  risk_band: RiskBand;
  grap_stage: number;
  n_schools_affected?: number;
  human_approved?: boolean;
  principal_role?: string;
  location_jurisdiction?: string;
}

export interface CedarEvaluationDecision {
  decision: "ALLOW" | "DENY";
  reason: string;
  statutory_citation: string;
  policy_version: string;
}

export interface ClassifiedClaim {
  statement: string;
  classification: "MODEL_DERIVED" | "POLICY_DERIVED" | "SOURCE_DERIVED" | "GUIDANCE" | "UNSUPPORTED";
  is_authoritative: boolean;
  is_safe: boolean;
  rejection_reason?: string;
}

export interface ClaimValidationResult {
  is_valid: boolean;
  claims_evaluated: number;
  unsupported_claims_count: number;
  classified_claims: ClassifiedClaim[];
  rejection_summary: string;
}

export interface ContingencyTable {
  hits: number;
  misses: number;
  false_alarms: number;
  correct_negatives: number;
  probability_of_detection: number;
  false_alarm_ratio: number;
  critical_success_index: number;
}

export interface EvaluationReport {
  evaluation_id: string;
  generated_at: string;
  dataset_period: string;
  station_count: number;
  sample_points: number;
  median_arrival_lag_hours: number;
  mean_absolute_lag_hours: number;
  spearman_rho: number;
  pearson_r: number;
  contingency: ContingencyTable;
  envelope_capture_rate: number;
  operational_verdict: string;
}

export interface RunSummary {
  run_id: string;
  generated_at: string;
  valid_until: string;
  school_count: number;
  severity: RiskBand;
  mode: "replay" | "custom" | "live";
  snapshot_id: string;
  grap_stage: number;
}

export interface CreateRunRequest {
  mode?: "replay" | "custom" | "live";
  snapshot_id?: string;
  grap_stage?: number;
  human_approved?: boolean;
  hotspots?: Hotspot[];
  weather?: WeatherObservation[];
  schools?: School[];
}

export interface CreateRunResponse {
  run_id: string;
  mode: string;
  snapshot_id: string;
  links: {
    self: string;
    prediction: string;
    advisory: string;
    map: string;
    timeline: string;
    schools: string;
    ensemble: string;
  };
  payload: FrontendPayload;
}
