"""
DhuanAlert Core Service Layer
Provides programmatic access to Layer 1 physics simulation, Layer 2 GenAI advisory,
Cedar policy evaluation, claim validation, evaluation matrix, and reference datasets.
"""

import json
import os
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone

from src.types import (
    Hotspot,
    WeatherObservation,
    School,
    PredictiveOutput,
    AdvisoryOutput,
    FrontendPayload,
    RecommendedAction,
    AdvisoryValidation,
)
from src.config import Config, DEFAULT_CONFIG
from src.pipeline import DhuanAlertPipeline
from src.layer1_predictive.pipeline import Layer1PredictivePipeline
from src.layer2_generative.pipeline import Layer2GenerativePipeline
from src.layer2_generative.grap_policy import GRAP_SCHEDULE
from src.layer2_generative.cedar_guardrail import (
    CedarPolicyAuthorizer,
    CedarAuthorizationContext,
    CedarEvaluationDecision,
)
from src.layer2_generative.claim_validator import ClaimValidator, ClaimValidationResult
from src.model.evaluation import (
    StationObservation,
    StationForecast,
    EvaluationReport,
    evaluate_model_against_ground_truth,
)


class EvaluationUnavailableError(ValueError):
    """Raised when evaluation is requested without real forecast/observation pairs."""

from src.data_sources import NasaFirmsClient, OpenMeteoClient, OpenAqWaqiClient, OsmSchoolClient


class DhuanAlertService:
    """
    Central service interface for all DhuanAlert platform capabilities.
    """

    def __init__(self, config: Config = None):
        self.config = config or DEFAULT_CONFIG
        self.pipeline = DhuanAlertPipeline(config=self.config)
        self.layer1 = Layer1PredictivePipeline(config=self.config)
        self.layer2 = Layer2GenerativePipeline()
        self.cedar = CedarPolicyAuthorizer()
        self.validator = ClaimValidator()

        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.join(base_dir, "data")
        self.firms_client = NasaFirmsClient()
        self.weather_client = OpenMeteoClient()
        self.openaq_client = OpenAqWaqiClient()
        self.schools_client = OsmSchoolClient()

    # =========================================================================
    # Reference Datasets & Ingestion
    # =========================================================================

    def get_sample_fires(self) -> List[Hotspot]:
        return self.firms_client.load_fallback_fires()

    def get_sample_weather(self) -> List[WeatherObservation]:
        return self.weather_client.load_fallback_weather()

    def get_sample_schools(self) -> List[School]:
        return self.schools_client.load_ncr_schools()

    def get_live_fires(self) -> List[Hotspot]:
        return self.firms_client.fetch_active_fires()

    def get_live_weather(self, latitude: float, longitude: float) -> List[WeatherObservation]:
        return self.weather_client.fetch_forecast(latitude=latitude, longitude=longitude)

    def primary_fire_location(self, hotspots: List[Hotspot], now: datetime) -> Tuple[float, float]:
        """Centroid of the strongest fire cluster: the point at which weather is fetched."""
        clusters = self.layer1.source_model.cluster_hotspots(hotspots, current_time=now)
        if not clusters:
            raise ValueError("INSUFFICIENT_DATA: Hotspots produced no fire clusters to fetch weather for.")
        return clusters[0].centroid_lat, clusters[0].centroid_lon

    # Weather sampling for the spatially varying wind field
    WEATHER_GRID_STEP_DEG = 1.0
    WEATHER_GRID_REACH_CELLS = 1  # grid points within +-1 cell (~110 km) of each cluster
    WEATHER_MAX_CLUSTER_POINTS = 10

    def weather_points_for(self, hotspots: List[Hotspot], now: datetime) -> List[Tuple[float, float]]:
        """
        Forecast points: the regular 1-degree grid points within WEATHER_GRID_REACH_CELLS of
        any fire cluster (room for ~9 h of plume travel), plus the centroids of the strongest
        clusters. Scales with where fires are, so India-wide runs stay a few hundred points.
        """
        import math as _m
        step, reach = self.WEATHER_GRID_STEP_DEG, self.WEATHER_GRID_REACH_CELLS
        clusters = self.layer1.source_model.cluster_hotspots(hotspots, current_time=now)
        grid = set()
        for c in clusters:
            i0, j0 = _m.floor(c.centroid_lat / step), _m.floor(c.centroid_lon / step)
            for di in range(-reach, reach + 2):
                for dj in range(-reach, reach + 2):
                    grid.add(((i0 + di) * step, (j0 + dj) * step))
        points = sorted(grid)
        points += [(c.centroid_lat, c.centroid_lon) for c in clusters[: self.WEATHER_MAX_CLUSTER_POINTS]]
        return points

    def get_live_weather_field(self, hotspots: List[Hotspot], now: datetime) -> List[WeatherObservation]:
        return self.weather_client.fetch_forecast_points(self.weather_points_for(hotspots, now))

    def get_replay_inputs(self) -> Tuple[List[Hotspot], List[WeatherObservation], datetime]:
        """
        Bundled replay snapshot. The run time T0 is the first hour of the recorded
        weather series, so the simulation uses the weather that applied at that time.
        """
        hotspots = self.get_sample_fires()
        weather = self.get_sample_weather()
        t0 = min(w.forecast_timestamp for w in weather)
        return hotspots, weather, t0

    def get_live_data_snapshot(self) -> Dict[str, Any]:
        """Return only records fetched successfully from live data providers."""
        sources: Dict[str, Dict[str, Any]] = {}
        records: Dict[str, List[Dict[str, Any]]] = {"fires": [], "weather": []}

        errors = (OSError, RuntimeError, ValueError, TypeError, KeyError, IndexError)

        try:
            fires = self.get_live_fires()
            records["fires"] = [item.model_dump(mode="json") for item in fires]
            sources["fires"] = {"name": "NASA FIRMS", "status": "ok", "count": len(fires)}
        except errors as error:
            fires = []
            sources["fires"] = {"name": "NASA FIRMS", "status": "error", "count": 0, "error": str(error)}

        # Weather is queried at the strongest fire cluster; with no fires there is no location.
        try:
            if not fires:
                raise ValueError("No live fire detections, so there is no fire location to query weather for.")
            lat, lon = self.primary_fire_location(fires, datetime.now(timezone.utc))
            weather = self.get_live_weather(lat, lon)
            records["weather"] = [item.model_dump(mode="json") for item in weather]
            sources["weather"] = {
                "name": "Open-Meteo",
                "status": "ok",
                "count": len(weather),
                "query_location": {"latitude": lat, "longitude": lon},
            }
        except errors as error:
            sources["weather"] = {"name": "Open-Meteo", "status": "error", "count": 0, "error": str(error)}

        return {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "sources": sources,
            **records,
        }

    def get_grap_catalog(self) -> Dict[str, Any]:
        catalog = {}
        for stage_num, defn in GRAP_SCHEDULE.items():
            catalog[f"stage_{stage_num}"] = defn.model_dump()
        return {
            "schedule_name": "CAQM Statutory GRAP Schedule (Revision 21.11.2025)",
            "stages": catalog,
        }

    def get_config_dict(self) -> Dict[str, Any]:
        return self.config.model_dump()

    # =========================================================================
    # Forecast Execution (End-to-End)
    # =========================================================================

    def create_run(
        self,
        mode: str = "replay",
        snapshot_id: str = "sample",
        grap_stage: int = 3,
        human_approved: bool = False,
        hotspots: Optional[List[Hotspot]] = None,
        weather: Optional[List[WeatherObservation]] = None,
        schools: Optional[List[School]] = None,
        run_timestamp: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Executes the complete forecast pipeline.
        Modes: 'live' (NASA FIRMS + Open-Meteo at the fire centroid, T0 = now),
        'replay' (bundled recorded snapshot, T0 = snapshot start), or 'custom'
        (caller supplies hotspots AND weather, and optionally run_timestamp).
        Evaluation is never run here: no real observations are paired with a forecast run.
        """
        if mode == "live":
            now = run_timestamp or datetime.now(timezone.utc)
            hotspots = hotspots or self.get_live_fires()
            if not hotspots:
                raise ValueError("NO_ACTIVE_FIRES: NASA FIRMS returned zero detections in the corridor bbox.")
            if not weather:
                weather = self.get_live_weather_field(hotspots, now)
        elif mode == "replay":
            if hotspots or weather:
                raise ValueError("Replay mode uses the bundled snapshot; use mode='custom' to supply inputs.")
            hotspots, weather, t0 = self.get_replay_inputs()
            now = run_timestamp or t0
        elif mode == "custom":
            if not hotspots or not weather:
                raise ValueError("INSUFFICIENT_DATA: custom mode requires both hotspots and weather.")
            now = run_timestamp or datetime.now(timezone.utc)
        else:
            raise ValueError(f"Unknown run mode '{mode}'. Expected live, replay, or custom.")

        payload: FrontendPayload = self.pipeline.run(
            hotspots=hotspots,
            weather=weather,
            schools=schools,
            grap_stage=grap_stage,
            human_approved=human_approved,
            run_timestamp=now,
            school_provider=self.schools_client.fetch_schools_in_bboxes,
        )

        return {
            "payload": payload,
            "prediction": payload.prediction,
            "advisory": payload.advisory,
            "map": payload.prediction.map_geojson,
            "evaluation": None,
            "evaluation_status": "NOT_VALIDATED",
        }

    # =========================================================================
    # Layer 1: Simulation Only
    # =========================================================================

    def simulate_layer1(
        self,
        hotspots: Optional[List[Hotspot]] = None,
        weather: Optional[List[WeatherObservation]] = None,
        schools: Optional[List[School]] = None,
        run_timestamp: Optional[datetime] = None,
    ) -> PredictiveOutput:
        """Layer 1 only. With no hotspots/weather given, runs the bundled replay snapshot.
        Without schools, schools are fetched from OpenStreetMap inside the plume footprint."""
        if not hotspots and not weather:
            hotspots, weather, t0 = self.get_replay_inputs()
            run_timestamp = run_timestamp or t0
        elif not hotspots or not weather:
            raise ValueError("INSUFFICIENT_DATA: simulate requires both hotspots and weather, or neither (replay).")

        return self.layer1.run(
            hotspots=hotspots,
            weather=weather,
            schools=schools,
            run_timestamp=run_timestamp,
            school_provider=self.schools_client.fetch_schools_in_bboxes,
        )

    # =========================================================================
    # Layer 2: Advisory Generation & Review
    # =========================================================================

    def generate_advisory(
        self,
        prediction: PredictiveOutput,
        grap_stage: int = 3,
        human_approved: bool = False,
    ) -> AdvisoryOutput:
        return self.layer2.run(
            prediction=prediction,
            grap_stage=grap_stage,
            human_approved=human_approved,
        )

    def review_advisory(
        self,
        advisory: AdvisoryOutput,
        action: str,  # "APPROVE" | "REJECT"
        officer_id: str = "Officer_Delhi_Disaster_Mgmt",
        notes: str = "",
    ) -> AdvisoryOutput:
        """
        Applies human-in-the-loop review decision to an advisory.
        """
        is_approve = action.upper() == "APPROVE"

        # Re-evaluate Cedar decisions with human_approved = is_approve
        new_actions: List[RecommendedAction] = []
        for act in advisory.recommended_actions:
            ctx = CedarAuthorizationContext(
                principal_role="District_Education_Officer",
                action_id=act.action_id,
                risk_band=advisory.severity,
                grap_stage=3,
                n_schools_affected=advisory.affected_area.get("school_count", 0),
                human_approved=is_approve,
            )
            decision = self.cedar.evaluate(ctx)
            if decision.decision == "ALLOW" or not is_approve:
                new_actions.append(
                    RecommendedAction(
                        action_id=act.action_id,
                        en=act.en,
                        hi=act.hi,
                        policy_basis=decision.statutory_citation if decision.decision == "ALLOW" else act.policy_basis,
                    )
                )

        new_status = "APPROVED" if is_approve else "REJECTED"
        rejection_reason = None if is_approve else (notes or "Advisory rejected by reviewing officer.")

        advisory.recommended_actions = new_actions
        advisory.validation = AdvisoryValidation(
            policy_check="PASSED" if is_approve else "FAILED",
            claim_check=advisory.validation.claim_check,
            publication_status=new_status,
            rejection_reason=rejection_reason,
        )
        advisory.model_metadata["reviewed_by"] = officer_id
        advisory.model_metadata["reviewed_at"] = datetime.now(timezone.utc).isoformat()
        if notes:
            advisory.model_metadata["review_notes"] = notes

        return advisory

    # =========================================================================
    # Policy Guardrails (Cedar & Claim Validator)
    # =========================================================================

    def evaluate_cedar_policy(
        self,
        action_id: str,
        risk_band: str,
        grap_stage: int,
        n_schools_affected: int = 1,
        human_approved: bool = True,
        principal_role: str = "District_Education_Officer",
    ) -> CedarEvaluationDecision:
        ctx = CedarAuthorizationContext(
            principal_role=principal_role,
            action_id=action_id,
            risk_band=risk_band.upper(),
            grap_stage=grap_stage,
            n_schools_affected=n_schools_affected,
            human_approved=human_approved,
        )
        return self.cedar.evaluate(ctx)

    def validate_claims(
        self,
        text: str,
        verified_model_facts: Optional[Dict[str, Any]] = None,
        verified_policy_actions: Optional[List[str]] = None,
    ) -> ClaimValidationResult:
        return self.validator.validate_text(
            text=text,
            verified_model_facts=verified_model_facts or {"lead_hours": 3.0, "school_count": 5},
            verified_policy_actions=verified_policy_actions or ["discontinue_primary_physical_classes"],
        )

    # =========================================================================
    # Layer 3: Evaluation Matrix
    # =========================================================================

    def run_evaluation(
        self,
        index_threshold: float = 40.0,
        delta_pm25_threshold: float = 50.0,
        forecasts: Optional[List[StationForecast]] = None,
        observations: Optional[List[StationObservation]] = None,
    ) -> EvaluationReport:
        if forecasts is not None and observations is not None:
            return evaluate_model_against_ground_truth(
                forecasts=forecasts,
                observations=observations,
                index_threshold=index_threshold,
                delta_pm25_threshold=delta_pm25_threshold,
            )
        raise EvaluationUnavailableError(
            "NO_VALIDATED_BACKTEST_AVAILABLE: evaluation requires real station forecasts and observations."
        )
