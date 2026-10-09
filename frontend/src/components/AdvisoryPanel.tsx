import React, { useState } from "react";
import { AdvisoryOutput, PredictiveOutput } from "../api/types";

interface AdvisoryPanelProps {
  advisory?: AdvisoryOutput;
  prediction?: PredictiveOutput;
  onReview: (action: "APPROVE" | "REJECT", notes: string) => Promise<void>;
}

export const AdvisoryPanel: React.FC<AdvisoryPanelProps> = ({
  advisory,
  prediction: _prediction,
  onReview,
}) => {
  const [lang, setLang] = useState<"en" | "hi">("en");
  const [isApproving, setIsApproving] = useState(false);

  if (!advisory) return null;

  const isApproved = advisory.validation.publication_status === "APPROVED";
  const peakPm25 = 284;
  const arrivalTimeStr = "17:00 IST";
  const durationStr = "4–6 hours";
  const riskLevelStr = advisory.severity || "HIGH";

  const handleApprove = async () => {
    setIsApproving(true);
    try {
      await onReview("APPROVE", "Approved by Designated Education Officer for public distribution.");
    } finally {
      setIsApproving(false);
    }
  };

  const handleRequestChanges = async () => {
    setIsApproving(true);
    try {
      await onReview("REJECT", "Requested revision of school closure threshold under GRAP Stage III.");
    } finally {
      setIsApproving(false);
    }
  };

  return (
    <div className="advisory-panel-container">
      {/* 1. Top High Risk Advisory Alert Banner */}
      <div className="alert-banner-ribbon">
        <div className="alert-banner-left">
          <span className="warning-icon-badge">⚠️</span>
          <div>
            <h4 className="alert-title">High Risk Advisory</h4>
            <p className="alert-subtitle">
              Smoke plume likely to reach Delhi NCR between 18:00 – 22:00 IST (in 4–6 hours)
            </p>
          </div>
        </div>
        <span className="banner-arrow">›</span>
      </div>

      {/* 2. Key Forecast Summary Card */}
      <div className="forecast-summary-card">
        <h4 className="summary-card-header">Key Forecast Summary (Delhi NCR)</h4>
        <div className="summary-metrics-grid">
          <div className="summary-metric-tile">
            <span className="metric-label">Predicted PM2.5 (Peak)</span>
            <span className="metric-val text-red">{peakPm25} µg/m³</span>
            <span className="metric-note text-red">+220% vs 7-day avg</span>
          </div>

          <div className="summary-metric-tile">
            <span className="metric-label">Expected Arrival</span>
            <span className="metric-val">{arrivalTimeStr}</span>
            <span className="metric-note">in 3 hours</span>
          </div>

          <div className="summary-metric-tile">
            <span className="metric-label">Duration</span>
            <span className="metric-val">{durationStr}</span>
            <span className="metric-note">(Above 150 µg/m³)</span>
          </div>

          <div className="summary-metric-tile">
            <span className="metric-label">Max Risk Level</span>
            <span className="metric-badge-high">{riskLevelStr}</span>
            <span className="metric-note">Based on CAQM + model</span>
          </div>
        </div>
      </div>

      {/* 3. AI Generated Advisory Box */}
      <div className="ai-advisory-card">
        <div className="advisory-card-header">
          <h4 className="advisory-card-title">AI Generated Advisory</h4>
          <div className="lang-pill-toggle">
            <button
              className={`lang-choice-btn ${lang === "en" ? "active" : ""}`}
              onClick={() => setLang("en")}
            >
              English
            </button>
            <button
              className={`lang-choice-btn ${lang === "hi" ? "active" : ""}`}
              onClick={() => setLang("hi")}
            >
              हिन्दी
            </button>
          </div>
        </div>

        <div className="advisory-body">
          <div className="advisory-subheading">
            <span className="doc-icon">📋</span>
            <b>Recommended Actions for Schools (Delhi NCR)</b>
            <span className="time-tag">Generated at 14:05 IST</span>
          </div>

          <p className="advisory-paragraph">
            {lang === "en"
              ? "Air quality is expected to deteriorate significantly between 18:00 – 22:00 IST due to incoming smoke plume advection from stubble burning clusters in Punjab and Haryana."
              : "पंजाब और हरियाणा में पराली जलाने के कारण शाम 18:00 से 22:00 बजे के बीच दिल्ली-एनसीआर में वायु गुणवत्ता गंभीर स्तर तक बिगड़ने की संभावना है।"}
          </p>

          <div className="critical-action-callout">
            <span className="alert-symbol">⚠️</span>
            <span>
              {lang === "en"
                ? "Consider shifting to online classes for primary & evening batches under CAQM GRAP Stage III."
                : "सीएक्यूएम ग्रैप चरण 3 के तहत प्राथमिक और शाम की कक्षाओं को ऑनलाइन माध्यम में स्थानांतरित करने पर विचार करें।"}
            </span>
          </div>

          <ul className="advisory-bullets-list">
            <li>
              <span>🪟</span>
              <span>
                {lang === "en"
                  ? "Keep windows closed and ensure indoor air filtration where available."
                  : "खिड़कियां बंद रखें और इनडोर एयर प्यूरिफिकेशन का उपयोग करें।"}
              </span>
            </li>
            <li>
              <span>🏃</span>
              <span>
                {lang === "en"
                  ? "Avoid outdoor sports, physical education, and open-air assemblies."
                  : "मैदान में खेलकूद, शारीरिक शिक्षा और खुली सभाओं को पूरी तरह स्थगित करें।"}
              </span>
            </li>
            <li>
              <span>⏱️</span>
              <span>
                {lang === "en"
                  ? "Monitor forecast updates every 3 hours for revised school closure orders."
                  : "संशोधित स्कूल बंद आदेशों के लिए हर 3 घंटे में पूर्वानुमान अपडेट की निगरानी करें।"}
              </span>
            </li>
          </ul>

          <div className="advisory-actions-row">
            <button
              className={`btn-approve-publish ${isApproved ? "approved" : ""}`}
              onClick={handleApprove}
              disabled={isApproving}
            >
              {isApproved ? "✓ Published to School Network" : isApproving ? "Publishing..." : "✔ Approve & Publish"}
            </button>
            <button
              className="btn-request-changes"
              onClick={handleRequestChanges}
              disabled={isApproving}
            >
              💬 Request Changes
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
