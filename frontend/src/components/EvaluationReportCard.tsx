import React, { useEffect, useState } from "react";
import { DhuanAlertClient } from "../api/client";
import { EvaluationReport } from "../api/types";

interface EvaluationReportCardProps {
  client: DhuanAlertClient;
}

export const EvaluationReportCard: React.FC<EvaluationReportCardProps> = ({ client }) => {
  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    client
      .getEvaluation()
      .then(setReport)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Could not fetch evaluation.");
      })
      .finally(() => setLoading(false));
  }, [client]);

  if (loading) return null;
  if (error || !report) {
    return (
      <div className="eval-card" role="alert">
        <h3>Evaluation unavailable</h3>
        <p>{error || "The API returned no evaluation report."}</p>
      </div>
    );
  }

  return (
    <div className="eval-card">
      <div className="eval-header">
        <h3>Evaluation Demo (Synthetic Backtest)</h3>
        <span className="verdict-tag">DEMO DATA</span>
      </div>
      <p className="eval-footer">
        Demonstration metrics from a bundled synthetic backtest; these are not live observations or validation of this forecast run.
      </p>

      <div className="metrics-grid">
        <div className="metric-box">
          <span className="metric-label">Spearman Rank (ρ)</span>
          <span className="metric-value">{report.spearman_rho}</span>
          <span className="metric-sub">Target: 0.40–0.70</span>
        </div>

        <div className="metric-box">
          <span className="metric-label">Median Arrival Lag</span>
          <span className="metric-value">{report.median_arrival_lag_hours}h</span>
          <span className="metric-sub">Target: ≤ 2.5 hours</span>
        </div>

        <div className="metric-box">
          <span className="metric-label">Probability of Detection</span>
          <span className="metric-value">
            {(report.contingency.probability_of_detection * 100).toFixed(0)}%
          </span>
          <span className="metric-sub">Target: ≥ 75%</span>
        </div>

        <div className="metric-box">
          <span className="metric-label">False Alarm Ratio (FAR)</span>
          <span className="metric-value">
            {(report.contingency.false_alarm_ratio * 100).toFixed(0)}%
          </span>
          <span className="metric-sub">Target: ≤ 30%</span>
        </div>

        <div className="metric-box">
          <span className="metric-label">Critical Success Index</span>
          <span className="metric-value">
            {report.contingency.critical_success_index.toFixed(2)}
          </span>
          <span className="metric-sub">Target: ≥ 0.50</span>
        </div>

        <div className="metric-box">
          <span className="metric-label">Ensemble Capture Rate</span>
          <span className="metric-value">
            {(report.envelope_capture_rate * 100).toFixed(0)}%
          </span>
          <span className="metric-sub">Target: ≥ 80%</span>
        </div>
      </div>

      <p className="eval-footer">
        {report.station_count} synthetic stations · {report.sample_points} demonstration samples
      </p>
    </div>
  );
};
