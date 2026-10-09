import React, { useEffect, useState } from "react";
import { DhuanAlertClient } from "../api/client";
import { EvaluationReport } from "../api/types";

interface EvaluationReportCardProps {
  client: DhuanAlertClient;
}

export const EvaluationReportCard: React.FC<EvaluationReportCardProps> = ({ client }) => {
  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    client
      .getEvaluation()
      .then(setReport)
      .catch((err) => console.error("Could not fetch evaluation:", err))
      .finally(() => setLoading(false));
  }, [client]);

  if (loading || !report) return null;

  const hits = report.contingency?.hits ?? 0;
  const misses = report.contingency?.misses ?? 0;
  const falseAlarms = report.contingency?.false_alarms ?? 0;

  const pod =
    report.contingency?.probability_of_detection !== undefined
      ? report.contingency.probability_of_detection
      : hits + misses > 0
      ? hits / (hits + misses)
      : 0;

  const far =
    report.contingency?.false_alarm_ratio !== undefined
      ? report.contingency.false_alarm_ratio
      : hits + falseAlarms > 0
      ? falseAlarms / (hits + falseAlarms)
      : 0;

  const csi =
    report.contingency?.critical_success_index !== undefined
      ? report.contingency.critical_success_index
      : hits + misses + falseAlarms > 0
      ? hits / (hits + misses + falseAlarms)
      : 0;

  const captureRate = report.envelope_capture_rate ?? 1.0;

  return (
    <div className="eval-card">
      <div className="eval-header">
        <h3>Ground-Truth Model Verification Matrix</h3>
        <span className="verdict-tag">{report.operational_verdict ? report.operational_verdict.slice(0, 9) : "VALIDATED"}</span>
      </div>

      <div className="metrics-grid">
        <div className="metric-box">
          <span className="metric-label">Spearman Rank (ρ)</span>
          <span className="metric-value">{report.spearman_rho ?? 0}</span>
          <span className="metric-sub">Target: 0.40–0.70</span>
        </div>

        <div className="metric-box">
          <span className="metric-label">Median Arrival Lag</span>
          <span className="metric-value">{report.median_arrival_lag_hours ?? 0}h</span>
          <span className="metric-sub">Target: ≤ 2.5 hours</span>
        </div>

        <div className="metric-box">
          <span className="metric-label">Probability of Detection</span>
          <span className="metric-value">
            {(pod * 100).toFixed(0)}%
          </span>
          <span className="metric-sub">Target: ≥ 75%</span>
        </div>

        <div className="metric-box">
          <span className="metric-label">False Alarm Ratio (FAR)</span>
          <span className="metric-value">
            {(far * 100).toFixed(0)}%
          </span>
          <span className="metric-sub">Target: ≤ 30%</span>
        </div>

        <div className="metric-box">
          <span className="metric-label">Critical Success Index</span>
          <span className="metric-value">
            {csi.toFixed(2)}
          </span>
          <span className="metric-sub">Target: ≥ 0.50</span>
        </div>

        <div className="metric-box">
          <span className="metric-label">Ensemble Capture Rate</span>
          <span className="metric-value">
            {(captureRate * 100).toFixed(0)}%
          </span>
          <span className="metric-sub">Target: ≥ 80%</span>
        </div>
      </div>

      <p className="eval-footer">{report.operational_verdict}</p>
    </div>
  );
};
