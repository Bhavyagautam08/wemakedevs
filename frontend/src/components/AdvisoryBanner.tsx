import React, { useState } from "react";
import { AdvisoryOutput } from "../api/types";

interface AdvisoryBannerProps {
  advisory?: AdvisoryOutput;
  onReview: (action: "APPROVE" | "REJECT", notes: string) => Promise<void>;
}

export const AdvisoryBanner: React.FC<AdvisoryBannerProps> = ({
  advisory,
  onReview,
}) => {
  const [lang, setLang] = useState<"en" | "hi">("en");
  const [officerNotes, setOfficerNotes] = useState<string>("");
  const [isReviewing, setIsReviewing] = useState<boolean>(false);

  if (!advisory) return null;

  const status = advisory.validation.publication_status;
  const isApproved = status === "APPROVED";

  const handleAction = async (action: "APPROVE" | "REJECT") => {
    setIsReviewing(true);
    try {
      await onReview(action, officerNotes);
      setOfficerNotes("");
    } finally {
      setIsReviewing(false);
    }
  };

  return (
    <div className={`advisory-card severity-${advisory.severity.toLowerCase()}`}>
      <div className="advisory-header">
        <div className="severity-badge">
          <span className="badge-pill">{advisory.severity} RISK</span>
          <span className="badge-status">{status}</span>
        </div>

        <div className="lang-toggle">
          <button
            className={`lang-btn ${lang === "en" ? "active" : ""}`}
            onClick={() => setLang("en")}
          >
            English
          </button>
          <button
            className={`lang-btn ${lang === "hi" ? "active" : ""}`}
            onClick={() => setLang("hi")}
          >
            हिन्दी (Hindi)
          </button>
        </div>
      </div>

      <h2 className="advisory-title">
        {lang === "en" ? advisory.headline.en : advisory.headline.hi}
      </h2>
      <p className="advisory-summary">
        {lang === "en" ? advisory.summary.en : advisory.summary.hi}
      </p>

      {/* Recommended Cedar Actions */}
      <div className="actions-section">
        <h3>Cedar-Authorized Operational Actions:</h3>
        <div className="action-list">
          {advisory.recommended_actions.map((act) => (
            <div key={act.action_id} className="action-item">
              <span className="action-check">✓</span>
              <div>
                <p className="action-text">{lang === "en" ? act.en : act.hi}</p>
                <span className="policy-basis">Legal Basis: {act.policy_basis}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Officer Workflow Sign-off */}
      <div className="officer-review-box">
        <h4>Officer Review & Sign-Off Gate</h4>
        <p className="gate-desc">
          Advisories require human authority sign-off before statutory broadcast to school networks.
        </p>

        {!isApproved ? (
          <div className="review-controls">
            <input
              type="text"
              placeholder="Officer review notes or approval remarks..."
              value={officerNotes}
              onChange={(e) => setOfficerNotes(e.target.value)}
              className="officer-input"
            />
            <div className="btn-group">
              <button
                className="btn btn-approve"
                disabled={isReviewing}
                onClick={() => handleAction("APPROVE")}
              >
                {isReviewing ? "Submitting..." : "Approve & Broadcast Advisory"}
              </button>
              <button
                className="btn btn-reject"
                disabled={isReviewing}
                onClick={() => handleAction("REJECT")}
              >
                Reject Draft
              </button>
            </div>
          </div>
        ) : (
          <div className="approval-confirmed">
            <span className="check-badge">✓</span>
            <span>
              Authorized by {advisory.model_metadata.reviewed_by || "Designated Officer"} on{" "}
              {new Date(advisory.model_metadata.reviewed_at || Date.now()).toLocaleTimeString()}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};
