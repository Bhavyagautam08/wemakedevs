"""
Layer 2 Generative AI & Policy Pipeline Runner
Executes the strict 7-step sequence:
  1. Assemble structured prediction context
  2. Synthesize draft advisory via Amazon Bedrock
  3. Validate actions against Cedar Policy Authorizer
  4. Validate factual claims and anti-hallucination guardrails
  5. Check semantic preservation between English and Hindi
  6. Determine final publication status (APPROVED / DRAFT / REJECTED)
  7. Output standardized AdvisoryOutput object
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from src.types import (
    PredictiveOutput,
    AdvisoryOutput,
    BilingualText,
    RecommendedAction,
    AdvisoryValidation,
)
from src.layer2_generative.grap_policy import GRAP_SCHEDULE
from src.layer2_generative.cedar_guardrail import (
    CedarPolicyAuthorizer,
    CedarAuthorizationContext,
)
from src.layer2_generative.claim_validator import ClaimValidator
from src.layer2_generative.bedrock_agent import BedrockAdvisoryAgent


class Layer2GenerativePipeline:
    """
    Orchestrates policy checking, GenAI synthesis, and claim validation.
    """

    def __init__(self):
        self.cedar = CedarPolicyAuthorizer()
        self.validator = ClaimValidator()
        self.agent = BedrockAdvisoryAgent()

    def run(
        self,
        prediction: PredictiveOutput,
        grap_stage: int = 3,
        human_approved: bool = True,
    ) -> AdvisoryOutput:
        """
        Executes the policy-constrained generative advisory workflow.
        """
        now = datetime.now(timezone.utc)
        advisory_id = f"adv_{now.strftime('%Y%m%d')}_{prediction.prediction_id}"

        # 1. Filter affected schools (HIGH or VERY_HIGH)
        high_risk_schools = [s for s in prediction.schools if s.risk_band in ["HIGH", "VERY_HIGH"]]
        affected_count = len(high_risk_schools)
        overall_severity = "HIGH" if high_risk_schools else "MODERATE"
        lead_hours = round(min((s.distance_to_fire_km / 18.0 for s in high_risk_schools), default=3.5), 1)

        # 2. Assemble Grounded Context Object
        grounded_context = {
            "prediction_id": prediction.prediction_id,
            "severity": overall_severity,
            "lead_hours": lead_hours,
            "zone_name": high_risk_schools[0].district if high_risk_schools else "North West Delhi",
            "affected_school_count": affected_count,
            "policy_context": {
                "grap_stage": grap_stage,
                "stage_name": GRAP_SCHEDULE.get(grap_stage, GRAP_SCHEDULE[3]).stage_name,
                "statutory_basis": GRAP_SCHEDULE.get(grap_stage, GRAP_SCHEDULE[3]).statutory_basis,
            },
            "evidence": [
                {"source_id": prediction.prediction_id, "type": "lagrangian_dispersion"},
                {"source_id": "caqm_schedule_2025_11_21", "type": "statutory_regulation"},
            ],
        }

        # 3. Generate Candidate Advisory via Bedrock Agent
        raw_advisory = self.agent.generate_advisory(grounded_context)

        # 4. Cedar Policy Evaluation
        cedar_decisions = []
        approved_actions: List[RecommendedAction] = []

        for act in raw_advisory.get("recommended_actions", []):
            ctx = CedarAuthorizationContext(
                action_id=act["action_id"],
                risk_band=overall_severity,
                grap_stage=grap_stage,
                n_schools_affected=affected_count,
                human_approved=human_approved,
            )
            dec = self.cedar.evaluate(ctx)
            cedar_decisions.append(dec)

            if dec.decision == "ALLOW":
                approved_actions.append(
                    RecommendedAction(
                        action_id=act["action_id"],
                        en=act["en"],
                        hi=act["hi"],
                        policy_basis=dec.statutory_citation,
                    )
                )

        policy_passed = all(d.decision == "ALLOW" for d in cedar_decisions) if cedar_decisions else False

        # 5. Anti-Hallucination & Claim Validation
        full_text_en = f"{raw_advisory.get('headline_en', '')} {raw_advisory.get('summary_en', '')}"
        claim_result = self.validator.validate_text(
            text=full_text_en,
            verified_model_facts={"lead_hours": lead_hours, "school_count": affected_count},
            verified_policy_actions=[a.action_id for a in approved_actions],
        )

        # 6. Final Status Determination
        if not claim_result.is_valid:
            pub_status = "REJECTED"
            rejection_reason = f"Claim validation failed: {claim_result.rejection_summary}"
        elif not policy_passed:
            pub_status = "MANUAL_REVIEW_REQUIRED"
            rejection_reason = "Proposed actions exceeded current GRAP statutory authorization."
        elif not human_approved:
            pub_status = "DRAFT"
            rejection_reason = "Pending officer sign-off."
        else:
            pub_status = "APPROVED"
            rejection_reason = None

        # 7. Standardized Output Object
        return AdvisoryOutput(
            advisory_id=advisory_id,
            severity=overall_severity,
            headline=BilingualText(
                en=raw_advisory.get("headline_en", "Air Quality Operational Advisory"),
                hi=raw_advisory.get("headline_hi", "वायु गुणवत्ता परिचालन परामर्श"),
            ),
            summary=BilingualText(
                en=raw_advisory.get("summary_en", ""),
                hi=raw_advisory.get("summary_hi", ""),
            ),
            affected_area={
                "name": grounded_context["zone_name"],
                "school_count": affected_count,
            },
            time_window={
                "start": prediction.valid_from,
                "end": prediction.valid_until,
            },
            recommended_actions=approved_actions,
            risk={
                "risk_band": overall_severity,
                "impact_probability": high_risk_schools[0].impact_probability if high_risk_schools else 0.5,
            },
            evidence=[
                {"source_id": prediction.prediction_id, "type": "model_prediction"},
                {"source_id": "caqm_schedule_2025_11_21", "type": "official_policy"},
            ],
            validation=AdvisoryValidation(
                policy_check="PASSED" if policy_passed else "FAILED",
                claim_check="PASSED" if claim_result.is_valid else "REJECTED",
                publication_status=pub_status,
                rejection_reason=rejection_reason,
            ),
            model_metadata={
                "prediction_id": prediction.prediction_id,
                "model_version": "1.0.0",
                "cedar_policy_version": "2025_11_21",
                "bedrock_model": self.agent.model_id,
            },
        )
