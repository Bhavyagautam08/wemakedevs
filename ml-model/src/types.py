"""
DhuanAlert Data Types and Schemas
Defines all Pydantic models for Layer 1 (Predictive Output) and Layer 2 (Advisory Output),
strictly adhering to the architectural separation specifications.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


# =====================================================================
# 1. RAW INPUT SCHEMAS
# =====================================================================

class Hotspot(BaseModel):
    """Raw NASA FIRMS / VIIRS active-fire detection point."""
    detection_id: str
    latitude: float
    longitude: float
    acq_timestamp: datetime
    confidence: float = Field(..., ge=0.0, le=100.0)
    confidence_class: Optional[str] = None
    frp: float = Field(..., ge=0.0, description="Fire Radiative Power in MW")
    satellite: str = "VIIRS_NRT"


class FireCluster(BaseModel):
    """Clustered fire event with estimated relative source/emission strength."""
    fire_id: str
    centroid_lat: float
    centroid_lon: float
    hotspot_count: int
    weighted_centroid: Dict[str, float]  # {"lat": ..., "lon": ...}
    latest_detection_time: datetime
    confidence_summary: float
    frp_summary: float  # Total FRP in MW
    source_strength: float = Field(..., description="Estimated relative smoke emission strength [0.0 - 1.0]")
    source_freshness_hours: float
    status: str = "ACTIVE"


class WeatherObservation(BaseModel):
    """Atmospheric conditions from Open-Meteo GFS."""
    wind_speed_mps: float
    wind_direction_deg: float
    u_mps: float
    v_mps: float
    boundary_layer_height_m: float
    temperature_c: float
    relative_humidity_pct: Optional[float] = None
    forecast_timestamp: datetime


class School(BaseModel):
    """Geospatial school asset in the NCR region."""
    school_id: str
    name: str
    latitude: float
    longitude: float
    district: str
    state: str = "Delhi"


# =====================================================================
# 2. LAYER 1: PREDICTIVE OUTPUT SCHEMAS
# =====================================================================

class SchoolRiskAssessment(BaseModel):
    """Operational smoke risk assessment for a specific school."""
    school_id: str
    name: str
    district: str
    latitude: float = 28.6139
    longitude: float = 77.2090
    distance_to_fire_km: float
    predicted_arrival_time: Optional[datetime] = None
    peak_concentration: float
    exposure_duration_minutes: int
    ensemble_members_affected: int
    impact_probability: float  # members_affected / total_members
    uncertainty: float
    risk_score: float
    risk_band: str  # LOW, MODERATE, HIGH, VERY_HIGH


class EnsembleMemberSummary(BaseModel):
    member_id: str
    name: str
    wind_speed_factor: float
    wind_dir_shift: float
    peak_concentration: float
    mean_concentration: float


class EnsembleOutput(BaseModel):
    member_count: int
    members: List[EnsembleMemberSummary]
    affected_area_union_geojson: Dict[str, Any]
    affected_area_intersection_geojson: Dict[str, Any]


class TimelineSlice(BaseModel):
    """Map-ready time slice for the frontend time-slider animation."""
    horizon_offset_hours: int
    timestamp: datetime
    plume_center_lat: float
    plume_center_lon: float
    plume_area_sq_km: float
    affected_schools_count: int
    max_intensity: float
    contour_geojson: Dict[str, Any]
    scatter_points: List[List[float]] = []  # [[lat, lon, weight], ...]
    corridor_geojson: Optional[Dict[str, Any]] = None
    heatmap_levels: Optional[List[Dict[str, Any]]] = None


class PredictiveOutput(BaseModel):
    """
    Standardized predictive output object contract.
    The frontend and advisory layer consume this directly.
    """
    prediction_id: str
    generated_at: datetime
    valid_from: datetime
    valid_until: datetime

    model: Dict[str, str] = {
        "type": "lagrangian_smoke_transport",
        "version": "1.0.0",
        "mode": "physics_only",  # Or "physics_plus_ml"
    }

    fire: Dict[str, Any]
    weather: Dict[str, Any]
    simulation: Dict[str, Any]
    ensemble: EnsembleOutput
    schools: List[SchoolRiskAssessment]
    timeline: List[TimelineSlice]
    map_geojson: Dict[str, Any]

    provenance: Dict[str, Optional[str]] = {
        "fire_source": "NASA_FIRMS_VIIRS",
        "weather_source": "Open-Meteo_GFS",
        "policy_source": None,
    }


# =====================================================================
# 3. LAYER 2: GENERATIVE AI & ADVISORY SCHEMAS
# =====================================================================

class BilingualText(BaseModel):
    en: str
    hi: str


class RecommendedAction(BaseModel):
    action_id: str
    en: str
    hi: str
    policy_basis: str


class AdvisoryValidation(BaseModel):
    policy_check: str  # PASSED / FAILED / MANUAL_REVIEW_REQUIRED
    claim_check: str   # PASSED / REJECTED
    publication_status: str  # APPROVED / DRAFT / REJECTED
    rejection_reason: Optional[str] = None


class AdvisoryOutput(BaseModel):
    """
    Standardized Generative Advisory output object.
    Contains grounded, policy-checked, bilingual operational instructions.
    """
    advisory_id: str
    severity: str  # LOW, MODERATE, HIGH, VERY_HIGH
    headline: BilingualText
    summary: BilingualText
    affected_area: Dict[str, Any]  # {"name": ..., "school_count": ...}
    time_window: Dict[str, datetime]  # {"start": ..., "end": ...}
    recommended_actions: List[RecommendedAction]
    risk: Dict[str, Any]  # {"risk_band": ..., "impact_probability": ...}
    evidence: List[Dict[str, str]]
    validation: AdvisoryValidation
    model_metadata: Dict[str, str]


# =====================================================================
# 4. COMPOSITE FRONTEND PAYLOAD
# =====================================================================

class FrontendPayload(BaseModel):
    """Combined payload ready for direct display on the operator dashboard."""
    prediction: PredictiveOutput
    advisory: AdvisoryOutput
