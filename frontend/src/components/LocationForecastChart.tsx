import React, { useState } from "react";

export const LocationForecastChart: React.FC = () => {
  const [selectedCity, setSelectedCity] = useState("Delhi NCR");

  const hourlyData = [
    { time: "14:00 Now", pm25: 72 },
    { time: "15:00", pm25: 98 },
    { time: "16:00", pm25: 145 },
    { time: "17:00", pm25: 198 },
    { time: "18:00", pm25: 248 },
    { time: "19:00 T+5h", pm25: 284 },
    { time: "20:00 T+6h", pm25: 232 },
  ];

  const maxVal = 320;
  const svgWidth = 480;
  const svgHeight = 160;
  const paddingX = 40;
  const paddingY = 25;

  const points = hourlyData.map((d, i) => {
    const x = paddingX + (i / (hourlyData.length - 1)) * (svgWidth - 2 * paddingX);
    const y = svgHeight - paddingY - (d.pm25 / maxVal) * (svgHeight - 2 * paddingY);
    return { x, y, ...d };
  });

  const pathD = points.reduce((acc, p, i) => `${acc} ${i === 0 ? "M" : "L"} ${p.x} ${p.y}`, "");
  const areaD = `${pathD} L ${points[points.length - 1].x} ${svgHeight - paddingY} L ${points[0].x} ${svgHeight - paddingY} Z`;

  return (
    <div className="forecast-chart-card">
      <div className="chart-header">
        <h4 className="chart-title">PM2.5 Forecast for Selected Location</h4>
        <div className="location-pill-dropdown">
          <select
            value={selectedCity}
            onChange={(e) => setSelectedCity(e.target.value)}
            className="chart-city-select"
          >
            <option value="Delhi NCR">Delhi NCR</option>
            <option value="North West Delhi">North West Delhi</option>
            <option value="Gurugram">Gurugram</option>
            <option value="Noida">Noida</option>
          </select>
        </div>
      </div>

      <div className="chart-canvas-box">
        <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} className="svg-forecast-curve">
          <defs>
            <linearGradient id="curveGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#ef4444" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#ef4444" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          {[0, 100, 200, 300].map((val) => {
            const y = svgHeight - paddingY - (val / maxVal) * (svgHeight - 2 * paddingY);
            return (
              <g key={val}>
                <line x1={paddingX} y1={y} x2={svgWidth - paddingX} y2={y} stroke="#1e293b" strokeDasharray="3 3" />
                <text x={paddingX - 8} y={y + 3} fill="#64748b" fontSize="9" textAnchor="end">{val}</text>
              </g>
            );
          })}

          {/* Area fill */}
          <path d={areaD} fill="url(#curveGradient)" />

          {/* Line stroke */}
          <path d={pathD} fill="none" stroke="#f97316" strokeWidth="2.5" />

          {/* Points */}
          {points.map((p, i) => (
            <circle key={i} cx={p.x} cy={p.y} r={i === 5 ? "5" : "3.5"} fill={i === 5 ? "#ef4444" : "#f97316"} stroke="#fff" strokeWidth="1.5" />
          ))}

          {/* Peak Callout Badge at 19:00 */}
          <g transform={`translate(${points[5].x - 45}, ${points[5].y - 32})`}>
            <rect width="90" height="24" rx="4" fill="#ef4444" />
            <text x="45" y="12" fill="#ffffff" fontSize="9" fontWeight="bold" textAnchor="middle" dominantBaseline="middle">
              Peak: 284 µg/m³
            </text>
            <text x="45" y="21" fill="#fecaca" fontSize="7" textAnchor="middle">
              19:00 IST
            </text>
          </g>

          {/* X axis labels */}
          {points.map((p, i) => (
            <text key={i} x={p.x} y={svgHeight - 8} fill="#94a3b8" fontSize="8" textAnchor="middle">
              {p.time.split(" ")[0]}
            </text>
          ))}
        </svg>
      </div>

      <div className="chart-bottom-metrics">
        <div className="bottom-metric-item">
          <span className="dot dot-green"></span>
          <span className="label">Current</span>
          <span className="value">72 µg/m³ <small>(Moderate)</small></span>
        </div>
        <div className="bottom-metric-item">
          <span className="label">7-day Avg</span>
          <span className="value">82 µg/m³</span>
        </div>
        <div className="bottom-metric-item">
          <span className="dot dot-red"></span>
          <span className="label">Predicted Peak</span>
          <span className="value text-red">284 µg/m³ <small>(Severe)</small></span>
        </div>
        <div className="bottom-metric-item">
          <span className="label">Duration</span>
          <span className="value">4–6 hours <small>(&gt; 150 µg/m³)</small></span>
        </div>
      </div>
    </div>
  );
};
