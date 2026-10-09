import React from "react";

export const BottomTelemetryBar: React.FC = () => {
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
              <span className="big-stat-number">247</span>
              <span className="sub-stat-text">Active Fire Detections</span>
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
            <span className="direction-heading">NW → SE</span>
            <span className="speed-heading">12–18 km/h</span>
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
              <span className="grap-stage-title">Stage III</span>
              <span className="grap-stage-sub">Very Poor (201–300 AQI)</span>
            </div>
          </div>
          <div className="grap-measures-list">
            <span className="measures-heading">Key Measures for Schools:</span>
            <ul>
              <li>Consider temporary closure or shift to online classes.</li>
              <li>Avoid outdoor activities & sports.</li>
              <li>Follow local administration orders.</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};
