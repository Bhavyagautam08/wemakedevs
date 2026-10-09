import React from "react";
import { PredictiveOutput } from "../api/types";

interface BottomTelemetryBarProps {
  prediction?: PredictiveOutput;
  grapStage?: number;
}

function getCompassHeading(deg: number): string {
  const directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
  const idx = Math.round(deg / 22.5) % 16;
  return directions[idx] || "NW";
}

export const BottomTelemetryBar: React.FC<BottomTelemetryBarProps> = ({
  prediction,
  grapStage = 3,
}) => {
  const fireCount = prediction?.fire?.hotspot_count || 247;
  const fireFrp = prediction?.fire?.total_frp_mw;

  const windSpeedMps = prediction?.weather?.wind_speed_mps;
  const windDirDeg = prediction?.weather?.wind_direction_deg ?? 315;
  const windSpeedKmh = windSpeedMps ? Math.round(windSpeedMps * 3.6) : 16;
  const compassFrom = getCompassHeading(windDirDeg);
  const compassTo = getCompassHeading((windDirDeg + 180) % 360);

  return (
    <div className="bottom-telemetry-grid">
      {/* 1. NASA FIRMS Active Fires Tile */}
      <div className="telemetry-tile-card">
        <div className="tile-header">
          <h4>Active Fire Sources (NASA FIRMS)</h4>
        </div>
        <div className="tile-content-row">
          <div className="fire-stat-box">
            <span className="flame-big-icon">🔥</span>
            <div>
              <span className="big-stat-number">{fireCount}</span>
              <span className="sub-stat-text">
                {fireFrp ? `${Math.round(fireFrp)} MW Radiative Power` : "Active Fire Detections"}
              </span>
            </div>
          </div>
          <div className="mini-map-preview">
            <div className="satellite-thumb">
              <span className="cluster-dot-1"></span>
              <span className="cluster-dot-2"></span>
              <span className="cluster-dot-3"></span>
            </div>
          </div>
        </div>
        <button className="tile-footer-action">View on Map ›</button>
      </div>

      {/* 2. OpenAQ Current Air Quality Tile */}
      <div className="telemetry-tile-card">
        <div className="tile-header">
          <h4>Current Air Quality (OpenAQ)</h4>
          <button className="tile-link-action">View All Stations ›</button>
        </div>
        <div className="aqi-stations-list">
          <div className="aqi-station-row">
            <span className="station-name"><span className="dot dot-red"></span> Delhi (IGI)</span>
            <span className="station-val">182</span>
            <span className="status-pill status-unhealthy">Unhealthy</span>
          </div>
          <div className="aqi-station-row">
            <span className="station-name"><span className="dot dot-orange"></span> Gurugram</span>
            <span className="station-val">146</span>
            <span className="status-pill status-sg">Unhealthy (SG)</span>
          </div>
          <div className="aqi-station-row">
            <span className="station-name"><span className="dot dot-orange"></span> Noida</span>
            <span className="station-val">128</span>
            <span className="status-pill status-sg">Unhealthy (SG)</span>
          </div>
          <div className="aqi-station-row">
            <span className="station-name"><span className="dot dot-yellow"></span> Faridabad</span>
            <span className="station-val">110</span>
            <span className="status-pill status-sg">Unhealthy (SG)</span>
          </div>
        </div>
      </div>

      {/* 3. Open-Meteo Wind Conditions Tile */}
      <div className="telemetry-tile-card">
        <div className="tile-header">
          <h4>Wind Conditions (Open-Meteo)</h4>
        </div>
        <div className="wind-telemetry-body">
          <div className="wind-icon-box">
            <span className="wind-wave-symbol">💨</span>
          </div>
          <div className="wind-details">
            <span className="label">Prevailing Wind</span>
            <span className="direction-heading">{compassFrom} → {compassTo} ({Math.round(windDirDeg)}°)</span>
            <span className="speed-heading">{windSpeedKmh} km/h</span>
          </div>
        </div>
        <button className="tile-footer-action">View Wind Forecast ›</button>
      </div>

      {/* 4. CAQM GRAP Status Tile */}
      <div className="telemetry-tile-card">
        <div className="tile-header">
          <h4>CAQM GRAP Status</h4>
          <button className="tile-link-action">View Guidelines ›</button>
        </div>
        <div className="grap-status-body">
          <div className="grap-badge-row">
            <span className="grap-stage-icon">⚡</span>
            <div>
              <span className="grap-stage-title">Stage {grapStage === 4 ? "IV" : grapStage === 3 ? "III" : grapStage === 2 ? "II" : "I"}</span>
              <span className="grap-stage-sub">
                {grapStage === 4 ? "Severe+ (> 450 AQI)" : grapStage === 3 ? "Severe (401–450 AQI)" : "Very Poor"}
              </span>
            </div>
          </div>
          <div className="grap-measures-list">
            <span className="measures-heading">Key Measures for Schools:</span>
            <ul>
              <li>Consider temporary closure or shift to online classes for Primary/Middle.</li>
              <li>Discontinue outdoor sports and morning assemblies.</li>
              <li>Strictly adhere to district administration notifications.</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};
