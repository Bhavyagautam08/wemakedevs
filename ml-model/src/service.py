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
from tests.test_evaluation import run_evaluation_demo


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

    # =========================================================================
    # Reference Datasets
    # =========================================================================

    def get_sample_fires(self) -> List[Hotspot]:
        path = os.path.join(self.data_dir, "sample_fires.json")
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return [Hotspot(**item) for item in raw]

    def get_sample_weather(self) -> List[WeatherObservation]:
        path = os.path.join(self.data_dir, "sample_weather.json")
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return [WeatherObservation(**item) for item in raw]

    def get_sample_schools(self) -> List[School]:
        path = os.path.join(self.data_dir, "ncr_schools.json")
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return [School(**item) for item in raw]

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
        Executes complete forecast pipeline and computes evaluation matrix.
        """
        if mode == "replay" or not hotspots:
            hotspots = self.get_sample_fires()
        if mode == "replay" or not weather:
            weather = self.get_sample_weather()
        if mode == "replay" or not schools:
            schools = self.get_sample_schools()

        now = run_timestamp or datetime.now(timezone.utc)
        payload: FrontendPayload = self.pipeline.run(
            hotspots=hotspots,
            weather=weather,
            schools=schools,
            grap_stage=grap_stage,
            human_approved=human_approved,
            run_timestamp=now,
        )

        evaluation_report: EvaluationReport = run_evaluation_demo()

        return {
            "payload": payload,
            "prediction": payload.prediction,
            "advisory": payload.advisory,
            "map": payload.prediction.map_geojson,
            "evaluation": evaluation_report,
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
        if not hotspots:
            hotspots = self.get_sample_fires()
        if not weather:
            weather = self.get_sample_weather()
        if not schools:
            schools = self.get_sample_schools()

        return self.layer1.run(
            hotspots=hotspots,
            weather=weather,
            schools=schools,
            run_timestamp=run_timestamp,
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
        return run_evaluation_demo()
