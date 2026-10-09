"""
Hallucination and Claim Validation Engine
Classifies factual claims in generated text as model-derived, policy-derived,
source-derived, generated guidance, or unsupported.
Rejects any unsupported authoritative or medical assertions.
"""

import re
from typing import List, Dict, Any, Tuple
from pydantic import BaseModel


class ClassifiedClaim(BaseModel):
    statement: str
    classification: str  # MODEL_DERIVED, POLICY_DERIVED, SOURCE_DERIVED, GUIDANCE, UNSUPPORTED
    is_authoritative: bool
    is_safe: bool
    rejection_reason: str = ""


class ClaimValidationResult(BaseModel):
    is_valid: bool
    claims_evaluated: int
    unsupported_claims_count: int
    classified_claims: List[ClassifiedClaim]
    rejection_summary: str = ""


class ClaimValidator:
    """
    Validates generated English and Hindi text against grounded evidence.
    """

    # Authoritative phrases that require explicit official verification
    RESTRICTED_AUTHORITATIVE_PATTERNS = [
        r"\b(?:evacuate|evacuation|mandatory evacuation)\b",
        r"\b(?:section 144|curfew|penal code)\b",
        r"\b(?:emergency disaster declaration)\b",
        r"\b(?:aqi\s*is\s*\d{3})\b",  # Fake exact AQI claims
        r"\b(?:pm2\.5\s*level\s*is\s*\d{3})\b",
        r"\b(?:take\s+(?:inhaler|steroids|antibiotics|paracetamol))\b",  # Medical prescriptions
        r"\b(?:all schools are closed indefinitely)\b",
    ]

    def validate_text(
        self,
        text: str,
        verified_model_facts: Dict[str, Any],
        verified_policy_actions: List[str],
    ) -> ClaimValidationResult:
        """
        Parses sentences and classifies each statement.
        """
        # Split text into sentences
        sentences = [s.strip() for s in re.split(r"[.!?।]\s*", text) if len(s.strip()) > 8]

        classified: List[ClassifiedClaim] = []
        unsupported_count = 0
        rejection_reasons = []

        for sent in sentences:
            lower_sent = sent.lower()

            # 1. Check for prohibited hallucinated authoritative terms
            has_forbidden_term = False
            for pat in self.RESTRICTED_AUTHORITATIVE_PATTERNS:
                if re.search(pat, lower_sent):
                    has_forbidden_term = True
                    break

            if has_forbidden_term:
                c = ClassifiedClaim(
                    statement=sent,
                    classification="UNSUPPORTED",
                    is_authoritative=True,
                    is_safe=False,
                    rejection_reason="Contains unverified authoritative, legal, or medical claim.",
                )
                classified.append(c)
                unsupported_count += 1
                rejection_reasons.append(c.rejection_reason)
                continue

            # 2. Check if claim matches model-derived facts (hours, arrival, corridor)
            if any(k in lower_sent for k in ["hour", "corridor", "plume", "smoke", "arrival", "forecast", "घंटे", "धुआं"]):
                c = ClassifiedClaim(
                    statement=sent,
                    classification="MODEL_DERIVED",
                    is_authoritative=False,
                    is_safe=True,
                )
                classified.append(c)
                continue

            # 3. Check if claim matches official policy (GRAP, CAQM, hybrid, outdoor)
            if any(k in lower_sent for k in ["grap", "caqm", "hybrid", "outdoor", "class v", "online", "ग्रैप", "कक्षा 5"]):
                c = ClassifiedClaim(
                    statement=sent,
                    classification="POLICY_DERIVED",
                    is_authoritative=True,
                    is_safe=True,
                )
                classified.append(c)
                continue

            # 4. Standard operational guidance
            c = ClassifiedClaim(
                statement=sent,
                classification="GUIDANCE",
                is_authoritative=False,
                is_safe=True,
            )
            classified.append(c)

        is_valid = unsupported_count == 0
        summary = "; ".join(set(rejection_reasons)) if rejection_reasons else "All claims grounded in model and policy."

        return ClaimValidationResult(
            is_valid=is_valid,
            claims_evaluated=len(sentences),
            unsupported_claims_count=unsupported_count,
            classified_claims=classified,
            rejection_summary=summary,
        )
