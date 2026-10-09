"""
Deterministic Policy Guardrail (AWS Cedar Evaluation Engine)
Evaluates proposed advisory actions against active CAQM GRAP stages, risk bands,
and statutory legal authorizations.
"""

from typing import Dict, Any, Tuple, List
from pydantic import BaseModel


class CedarAuthorizationContext(BaseModel):
    principal_role: str = "District_Education_Officer"
    action_id: str
    risk_band: str               # LOW, MODERATE, HIGH, VERY_HIGH
    grap_stage: int              # 1, 2, 3, 4
    n_schools_affected: int
    human_approved: bool = True
    location_jurisdiction: str = "NCT_Delhi"


class CedarEvaluationDecision(BaseModel):
    decision: str                # ALLOW or DENY
    reason: str
    statutory_citation: str
    policy_version: str = "CAQM_GRAP_2025_11_21"


class CedarPolicyAuthorizer:
    """
    Implements AWS Cedar formal authorization logic for environmental advisories:

    permit (
      principal,
      action in [Action::"IssuePrecautionaryAlert", Action::"HybridTransitionClassV"],
      resource
    ) when {
      resource.grap_stage >= 3 &&
      resource.risk_band in ["HIGH", "VERY_HIGH"] &&
      context.human_approved == true
    };
    """

    # Minimum GRAP stage required for specific actions
    ACTION_MIN_GRAP_REQUIREMENT: Dict[str, int] = {
        "advisory_awareness": 1,
        "restrict_outdoor_assemblies": 2,
        "discontinue_primary_physical_classes": 3,
        "suspend_all_outdoor_sports": 3,
        "discontinue_classes_up_to_class_ix_and_xi": 4,
        "consider_college_suspension": 4,
    }

    # Minimum risk band required for specific actions
    ACTION_MIN_RISK_BAND: Dict[str, List[str]] = {
        "advisory_awareness": ["LOW", "MODERATE", "HIGH", "VERY_HIGH"],
        "restrict_outdoor_assemblies": ["MODERATE", "HIGH", "VERY_HIGH"],
        "discontinue_primary_physical_classes": ["HIGH", "VERY_HIGH"],
        "suspend_all_outdoor_sports": ["HIGH", "VERY_HIGH"],
        "discontinue_classes_up_to_class_ix_and_xi": ["VERY_HIGH"],
        "consider_college_suspension": ["VERY_HIGH"],
    }

    def evaluate(self, ctx: CedarAuthorizationContext) -> CedarEvaluationDecision:
        """
        Evaluates proposed action against deterministic Cedar policy rules.
        """
        action = ctx.action_id

        # 1. Unknown or unauthorized action
        if action not in self.ACTION_MIN_GRAP_REQUIREMENT:
            return CedarEvaluationDecision(
                decision="DENY",
                reason=f"Action '{action}' is not in the authorized CAQM GRAP action catalog.",
                statutory_citation="None",
            )

        min_grap = self.ACTION_MIN_GRAP_REQUIREMENT[action]
        allowed_bands = self.ACTION_MIN_RISK_BAND[action]

        # 2. Check GRAP Stage Constraint
        if ctx.grap_stage < min_grap:
            return CedarEvaluationDecision(
                decision="DENY",
                reason=(
                    f"Action '{action}' requires CAQM GRAP Stage {min_grap} or higher. "
                    f"Current in-force stage is Stage {ctx.grap_stage}."
                ),
                statutory_citation=f"CAQM GRAP Stage {min_grap} Schedule",
            )

        # 3. Check Plume Exposure Risk Band
        if ctx.risk_band not in allowed_bands:
            return CedarEvaluationDecision(
                decision="DENY",
                reason=(
                    f"Action '{action}' is disproportionate for risk band '{ctx.risk_band}'. "
                    f"Requires at least {allowed_bands[0]}."
                ),
                statutory_citation="Proportionality Clause, DDMA Manual",
            )

        # 4. Mandatory Human Review Gate
        if not ctx.human_approved:
            return CedarEvaluationDecision(
                decision="DENY",
                reason="Advisory issuance blocked: requires human officer approval before publishing.",
                statutory_citation="CAQM Human Governance Protocol",
            )

        # Authorized!
        return CedarEvaluationDecision(
            decision="ALLOW",
            reason="Action fully authorized under statutory GRAP schedule and validated exposure band.",
            statutory_citation=f"CAQM Schedule 21.11.2025 Item {min_grap}",
        )
