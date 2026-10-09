import React from "react";

export const ModelEvaluationChart: React.FC = () => {
  const timeLabels = ["10:00", "12:00", "14:00", "16:00", "18:00", "20:00", "22:00"];
  const predictedData = [80, 95, 120, 190, 280, 340, 270];
  const observedData = [75, 88, 110, 160, 240, 310, 250];

  const maxVal = 400;
  const svgWidth = 480;
  const svgHeight = 140;
  const paddingX = 35;
  const paddingY = 20;

  const getPoints = (arr: number[]) =>
    arr.map((v, i) => ({
      x: paddingX + (i / (arr.length - 1)) * (svgWidth - 2 * paddingX),
      y: svgHeight - paddingY - (v / maxVal) * (svgHeight - 2 * paddingY),
      v,
    }));

  const predPoints = getPoints(predictedData);
  const obsPoints = getPoints(observedData);

  const predPath = predPoints.reduce((acc, p, i) => `${acc} ${i === 0 ? "M" : "L"} ${p.x} ${p.y}`, "");
  const obsPath = obsPoints.reduce((acc, p, i) => `${acc} ${i === 0 ? "M" : "L"} ${p.x} ${p.y}`, "");

  return (
    <div className="eval-chart-card">
      <div className="chart-header">
        <h4 className="chart-title">Model Evaluation (vs. OpenAQ)</h4>
        <button className="btn-link-details">View Details ›</button>
      </div>

      <div className="eval-metrics-inline-bar">
        <div className="eval-stat-item">
          <span className="stat-label">MAE</span>
          <span className="stat-val">18.4 µg/m³</span>
        </div>
        <div className="eval-stat-item">
          <span className="stat-label">RMSE</span>
          <span className="stat-val">26.7 µg/m³</span>
        </div>
        <div className="eval-stat-item">
          <span className="stat-label">Correlation</span>
          <span className="stat-val">0.72</span>
        </div>
        <div className="eval-stat-item">
          <span className="stat-label">Hit Rate</span>
          <span className="stat-val text-green">78%</span>
        </div>
      </div>

      <div className="chart-legend-row">
        <span className="legend-item">Predicted vs Observed PM2.5 (Delhi NCR)</span>
        <div className="legend-badges">
          <span className="legend-chip"><span className="dot dot-red"></span> Predicted (Model)</span>
          <span className="legend-chip"><span className="dot dot-blue"></span> Observed (OpenAQ)</span>
        </div>
      </div>

      <div className="chart-canvas-box">
        <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} className="svg-eval-curve">
          {/* Y Grid lines */}
          {[0, 100, 200, 300, 400].map((val) => {
            const y = svgHeight - paddingY - (val / maxVal) * (svgHeight - 2 * paddingY);
            return (
              <g key={val}>
                <line x1={paddingX} y1={y} x2={svgWidth - paddingX} y2={y} stroke="#1e293b" strokeDasharray="3 3" />
                <text x={paddingX - 6} y={y + 3} fill="#64748b" fontSize="8" textAnchor="end">{val}</text>
              </g>
            );
          })}

          {/* Observed Line (Blue) */}
          <path d={obsPath} fill="none" stroke="#3b82f6" strokeWidth="2.5" />
          {obsPoints.map((p, i) => (
            <circle key={`obs-${i}`} cx={p.x} cy={p.y} r="3.5" fill="#3b82f6" stroke="#fff" strokeWidth="1" />
          ))}

          {/* Predicted Line (Red) */}
          <path d={predPath} fill="none" stroke="#ef4444" strokeWidth="2.5" />
          {predPoints.map((p, i) => (
            <circle key={`pred-${i}`} cx={p.x} cy={p.y} r="3.5" fill="#ef4444" stroke="#fff" strokeWidth="1" />
          ))}

          {/* X Labels */}
          {timeLabels.map((lbl, i) => {
            const x = paddingX + (i / (timeLabels.length - 1)) * (svgWidth - 2 * paddingX);
            return (
              <text key={i} x={x} y={svgHeight - 4} fill="#94a3b8" fontSize="8" textAnchor="middle">
                {lbl}
              </text>
            );
          })}
        </svg>
      </div>
    </div>
  );
};
