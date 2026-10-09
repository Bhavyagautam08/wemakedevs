/**
 * Frontend Typed Contracts for DhuanAlert
 */

export type RiskBand = "LOW" | "MODERATE" | "HIGH" | "VERY_HIGH";
export type PublicationStatus = "APPROVED" | "DRAFT" | "MANUAL_REVIEW_REQUIRED" | "REJECTED";

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

export interface TimelineSlice {
  horizon_offset_hours: number;
  timestamp: string;
  plume_center_lat: number;
  plume_center_lon: number;
  plume_area_sq_km: number;
  affected_schools_count: number;
  max_intensity: number;
  contour_geojson?: any;
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
  ensemble: {
    member_count: number;
    members: Array<{
      member_id: string;
      name: string;
      wind_speed_factor: number;
      wind_dir_shift: number;
      peak_concentration: number;
    }>;
  };
  schools: SchoolRiskAssessment[];
  timeline: TimelineSlice[];
  map_geojson: any;
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
  validation: {
    policy_check: "PASSED" | "FAILED" | "MANUAL_REVIEW_REQUIRED";
    claim_check: "PASSED" | "REJECTED";
    publication_status: PublicationStatus;
    rejection_reason?: string | null;
  };
  model_metadata: {
    reviewed_by?: string;
    reviewed_at?: string;
    review_notes?: string;
    [key: string]: any;
  };
}

export interface FrontendPayload {
  prediction: PredictiveOutput;
  advisory: AdvisoryOutput;
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
  contingency: {
    hits: number;
    misses: number;
    false_alarms: number;
    correct_negatives: number;
    probability_of_detection: number;
    false_alarm_ratio: number;
    critical_success_index: number;
  };
  envelope_capture_rate: number;
  operational_verdict: string;
}
