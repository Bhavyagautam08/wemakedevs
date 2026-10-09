import { ClaimValidationResult, ClassifiedClaim } from "../types";

export const RESTRICTED_AUTHORITATIVE_PATTERNS = [
  /\b(?:evacuate|evacuation|mandatory evacuation)\b/i,
  /\b(?:section 144|curfew|penal code)\b/i,
  /\b(?:emergency disaster declaration)\b/i,
  /\b(?:aqi\s*is\s*\d{3})\b/i,
  /\b(?:pm2\.5\s*level\s*is\s*\d{3})\b/i,
  /\b(?:take\s+(?:inhaler|steroids|antibiotics|paracetamol))\b/i,
  /\b(?:all schools are closed indefinitely)\b/i,
];

export class ClaimsService {
  public static validate(text: string): ClaimValidationResult {
    if (!text || typeof text !== "string") {
      return {
        is_valid: true,
        claims_evaluated: 0,
        unsupported_claims_count: 0,
        classified_claims: [],
        rejection_summary: "No claims to evaluate.",
      };
    }

    const sentences = text
      .split(/[.!?।]\s+/)
      .map((s) => s.trim())
      .filter((s) => s.length > 8);

    const classified: ClassifiedClaim[] = [];
    let unsupportedCount = 0;
    const rejectionReasons: string[] = [];

    for (const sent of sentences) {
      const lower = sent.toLowerCase();

      let hasForbiddenTerm = false;
      for (const pat of RESTRICTED_AUTHORITATIVE_PATTERNS) {
        if (pat.test(lower)) {
          hasForbiddenTerm = true;
          break;
        }
      }

      if (hasForbiddenTerm) {
        const reason = "Contains unverified authoritative, legal, or medical claim.";
        classified.push({
          statement: sent,
          classification: "UNSUPPORTED",
          is_authoritative: true,
          is_safe: false,
          rejection_reason: reason,
        });
        unsupportedCount++;
        rejectionReasons.push(reason);
        continue;
      }

      if (["hour", "corridor", "plume", "smoke", "arrival", "forecast", "घंटे", "धुआं"].some((k) => lower.includes(k))) {
        classified.push({
          statement: sent,
          classification: "MODEL_DERIVED",
          is_authoritative: false,
          is_safe: true,
        });
        continue;
      }

      if (["grap", "caqm", "hybrid", "outdoor", "class v", "online", "ग्रैप", "कक्षा 5"].some((k) => lower.includes(k))) {
        classified.push({
          statement: sent,
          classification: "POLICY_DERIVED",
          is_authoritative: true,
          is_safe: true,
        });
        continue;
      }

      classified.push({
        statement: sent,
        classification: "GUIDANCE",
        is_authoritative: false,
        is_safe: true,
      });
    }

    return {
      is_valid: unsupportedCount === 0,
      claims_evaluated: sentences.length,
      unsupported_claims_count: unsupportedCount,
      classified_claims: classified,
      rejection_summary: rejectionReasons.length > 0
        ? Array.from(new Set(rejectionReasons)).join("; ")
        : "All claims grounded in model and policy.",
    };
  }
}
