import React, { useState } from "react";
import { TimelineSlice, SchoolRiskAssessment } from "../api/types";

interface LocationForecastChartProps {
  timeline?: TimelineSlice[];
  schools?: SchoolRiskAssessment[];
}

export const LocationForecastChart: React.FC<LocationForecastChartProps> = ({
  timeline,
  schools: _schools,
}) => {
  const [selectedCity, setSelectedCity] = useState("Delhi NCR");

  const hourlyData = timeline && timeline.length > 0
    ? timeline.map((sl, idx) => {
        const d = sl.timestamp ? new Date(sl.timestamp) : new Date();
        const timeStr = !isNaN(d.getTime())
          ? d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
          : `${14 + sl.horizon_offset_hours}:00`;
        const label = idx === 0 ? `${timeStr} Now` : `T+${sl.horizon_offset_hours}h`;
        const val = Math.round(sl.max_intensity * 320 + 72);
        return { time: label, pm25: val, rawTime: timeStr };
      })
    : [
        { time: "14:00 Now", pm25: 72, rawTime: "14:00" },
        { time: "15:00", pm25: 98, rawTime: "15:00" },
        { time: "16:00", pm25: 145, rawTime: "16:00" },
        { time: "17:00", pm25: 198, rawTime: "17:00" },
        { time: "18:00", pm25: 248, rawTime: "18:00" },
        { time: "19:00 T+5h", pm25: 284, rawTime: "19:00" },
        { time: "20:00 T+6h", pm25: 232, rawTime: "20:00" },
      ];

  let peakIdx = 0;
  hourlyData.forEach((d, i) => {
    if (d.pm25 > hourlyData[peakIdx].pm25) peakIdx = i;
  });
  const peakVal = hourlyData[peakIdx].pm25;
  const currentVal = hourlyData[0]?.pm25 || 72;

  const maxVal = Math.max(320, peakVal + 40);
  const svgWidth = 480;
  const svgHeight = 160;
  const paddingX = 40;
  const paddingY = 25;

  const points = hourlyData.map((d, i) => {
    const x = paddingX + (i / Math.max(1, hourlyData.length - 1)) * (svgWidth - 2 * paddingX);
    const y = svgHeight - paddingY - (d.pm25 / maxVal) * (svgHeight - 2 * paddingY);
    return { x, y, ...d };
  });

  const pathD = points.reduce((acc, p, i) => `${acc} ${i === 0 ? "M" : "L"} ${p.x} ${p.y}`, "");
  const areaD = points.length > 0
    ? `${pathD} L ${points[points.length - 1].x} ${svgHeight - paddingY} L ${points[0].x} ${svgHeight - paddingY} Z`
    : "";

  const durationHours = hourlyData.filter(d => d.pm25 >= 150).length;

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
          {areaD && <path d={areaD} fill="url(#curveGradient)" />}

          {/* Line stroke */}
          {pathD && <path d={pathD} fill="none" stroke="#f97316" strokeWidth="2.5" />}

          {/* Points */}
          {points.map((p, i) => (
            <circle
              key={i}
              cx={p.x}
              cy={p.y}
              r={i === peakIdx ? "5" : "3.5"}
              fill={i === peakIdx ? "#ef4444" : "#f97316"}
              stroke="#fff"
              strokeWidth="1.5"
            />
          ))}

          {/* Dynamic Peak Callout Badge */}
          {points[peakIdx] && (
            <g transform={`translate(${Math.max(paddingX, Math.min(svgWidth - 95, points[peakIdx].x - 45))}, ${Math.max(5, points[peakIdx].y - 32)})`}>
              <rect width="90" height="24" rx="4" fill="#ef4444" />
              <text x="45" y="12" fill="#ffffff" fontSize="9" fontWeight="bold" textAnchor="middle" dominantBaseline="middle">
                Peak: {peakVal} µg/m³
              </text>
              <text x="45" y="21" fill="#fecaca" fontSize="7" textAnchor="middle">
                {points[peakIdx].rawTime} IST
              </text>
            </g>
          )}

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
          <span className="value">{currentVal} µg/m³ <small>(Moderate)</small></span>
        </div>
        <div className="bottom-metric-item">
          <span className="label">7-day Avg</span>
          <span className="value">82 µg/m³</span>
        </div>
        <div className="bottom-metric-item">
          <span className="dot dot-red"></span>
          <span className="label">Predicted Peak</span>
          <span className="value text-red">{peakVal} µg/m³ <small>(Severe)</small></span>
        </div>
        <div className="bottom-metric-item">
          <span className="label">Duration</span>
          <span className="value">{Math.max(2, durationHours)}–{Math.max(4, durationHours + 2)} hours <small>(&gt; 150 µg/m³)</small></span>
        </div>
      </div>
    </div>
  );
};

