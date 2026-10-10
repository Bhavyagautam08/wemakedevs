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
  latitude?: number;
  longitude?: number;
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

export interface LiveWeatherObservation {
  forecast_timestamp: string;
  wind_speed_mps: number;
  wind_direction_deg: number;
  u_mps: number;
  v_mps: number;
  boundary_layer_height_m: number;
  temperature_c: number;
  relative_humidity_pct?: number | null;
}

export interface LiveDataSnapshot {
  fetched_at: string;
  sources: {
    fires: { name: string; status: "ok" | "error"; count: number; error?: string };
    weather: { name: string; status: "ok" | "error"; count: number; error?: string };
  };
  fires: Array<{
    detection_id: string;
    latitude: number;
    longitude: number;
    acq_timestamp: string;
    confidence: number;
    confidence_class?: string | null;
    frp: number;
    satellite: string;
  }>;
  weather: LiveWeatherObservation[];
}

export interface TimelineSlice {
  horizon_offset_hours: number;
  timestamp: string;
  plume_center_lat: number;
  plume_center_lon: number;
  plume_area_sq_km: number;
  affected_schools_count: number;
  max_intensity: number;
  peak_concentration_ugm3?: number;
  particle_count?: number;
  contour_geojson?: any;
  scatter_points?: Array<[number, number, number]>; // [lat, lon, weight]
  corridor_geojson?: any;
  heatmap_levels?: Array<{
    level: string;
    intensity: string;
    color: string;
    threshold_ugm3?: number;
    area_sq_km?: number;
    polygons?: number[][][];
    coordinates: number[][];
  }>;
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
    emission_rate_kg_s?: number;
    status: string;
  };
  simulation: {
    timestep_seconds: number;
    horizon_hours: number;
    forecast_horizons: number[];
    particle_count: number;
    fire_cluster_count: number;
    total_emission_rate_kg_s: number;
    emission_coefficient_kg_per_mj: number;
    emission_duration_hours: number;
    concentration_units: string;
    impact_threshold_ugm3: number;
    school_source?: string;
    schools_assessed?: number;
    footprint_area_sq_km?: number;
    horizon_states: Array<{
      horizon_hours: number;
      particle_count: number;
      total_mass_kg: number;
      mixing_height_m: number;
      centroid_lat?: number;
      centroid_lon?: number;
    }>;
  };
  weather: {
    wind_speed_mps: number;
    wind_direction_deg: number;
    u_mps: number;
    v_mps: number;
    boundary_layer_height_m: number;
    observation_count?: number;
    station_count?: number;
    stations?: number[][];
    spatial_interpolation?: string;
    at_horizons?: Array<{
      horizon_hours: number;
      u_mps: number;
      v_mps: number;
      wind_speed_mps: number;
      wind_direction_deg: number;
      boundary_layer_height_m: number;
      precipitation_mm: number;
    }>;
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
