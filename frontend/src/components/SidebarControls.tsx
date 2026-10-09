import React from "react";

interface SidebarControlsProps {
  date: string;
  onDateChange: (d: string) => void;
  time: string;
  onTimeChange: (t: string) => void;
  horizonHours: number;
  onHorizonChange: (h: number) => void;
  onRunForecast: (mode: "live" | "replay") => void;
  isLoading: boolean;
  activeMode: "live" | "replay";
  // Layer Toggles
  showFires: boolean;
  onToggleFires: (v: boolean) => void;
  showPlume: boolean;
  onTogglePlume: (v: boolean) => void;
  showWind: boolean;
  onToggleWind: (v: boolean) => void;
  showSchools: boolean;
  onToggleSchools: (v: boolean) => void;
  showOpenAq: boolean;
  onToggleOpenAq: (v: boolean) => void;
  showBoundaries: boolean;
  onToggleBoundaries: (v: boolean) => void;
  // Overlay mode
  overlayOption: string;
  onOverlayOptionChange: (opt: string) => void;
}

export const SidebarControls: React.FC<SidebarControlsProps> = ({
  date,
  onDateChange,
  time,
  onTimeChange,
  horizonHours,
  onHorizonChange,
  onRunForecast,
  isLoading,
  activeMode,
  showFires,
  onToggleFires,
  showPlume,
  onTogglePlume,
  showWind,
  onToggleWind,
  showSchools,
  onToggleSchools,
  showOpenAq,
  onToggleOpenAq,
  showBoundaries,
  onToggleBoundaries,
  overlayOption,
  onOverlayOptionChange,
}) => {
  return (
    <aside className="sidebar-controls-panel">
      {/* 1. Forecast Configuration */}
      <div className="control-card">
        <h3 className="card-section-title">Forecast Configuration</h3>

        <div className="datetime-row">
          <div className="input-field-group">
            <label>Date (IST)</label>
            <div className="input-icon-box">
              <span className="icon">📅</span>
              <input
                type="date"
                value={date}
                onChange={(e) => onDateChange(e.target.value)}
                className="custom-datetime-input"
              />
            </div>
          </div>

          <div className="input-field-group">
            <label>Time (IST)</label>
            <div className="input-icon-box">
              <span className="icon">🕒</span>
              <input
                type="text"
                value={time}
                onChange={(e) => onTimeChange(e.target.value)}
                className="custom-datetime-input"
              />
            </div>
          </div>
        </div>

        <div className="slider-control-group">
          <div className="slider-header">
            <label>Forecast Horizon</label>
            <span className="slider-value-pill">{horizonHours} hours</span>
          </div>
          <input
            type="range"
            min="1"
            max="24"
            step="1"
            value={horizonHours}
            onChange={(e) => onHorizonChange(Number(e.target.value))}
            className="horizon-range-slider"
          />
          <div className="slider-ticks-row">
            <span>0h</span>
            <span>1h</span>
            <span>2h</span>
            <span>3h</span>
            <span>4h</span>
            <span>5h</span>
            <span>6h</span>
            <span>12h</span>
            <span>24h</span>
          </div>
        </div>

        <div className="mode-selection-row">
          <button
            className={`mode-btn ${activeMode === "live" ? "active" : ""}`}
            onClick={() => onRunForecast("live")}
            disabled={isLoading}
          >
            {isLoading ? "Fetching Live..." : "▶ Run Live Ingestion"}
          </button>
          <button
            className={`mode-btn ${activeMode === "replay" ? "active" : ""}`}
            onClick={() => onRunForecast("replay")}
            disabled={isLoading}
          >
            Replay Snapshot
          </button>
        </div>
      </div>

      {/* 2. Map Layers Toggles */}
      <div className="control-card">
        <h3 className="card-section-title">Map Layers</h3>
        <div className="layer-list">
          <label className="layer-item">
            <input
              type="checkbox"
              checked={showFires}
              onChange={(e) => onToggleFires(e.target.checked)}
            />
            <span className="layer-legend-dot fire-dot">🔴</span>
            <span className="layer-name">NASA FIRMS Active Fires</span>
            <span className="chevron-icon">›</span>
          </label>

          <label className="layer-item">
            <input
              type="checkbox"
              checked={showPlume}
              onChange={(e) => onTogglePlume(e.target.checked)}
            />
            <span className="layer-legend-dot plume-dot">🌫️</span>
            <span className="layer-name">Smoke Plume (Model)</span>
            <span className="chevron-icon">›</span>
          </label>

          <label className="layer-item">
            <input
              type="checkbox"
              checked={showWind}
              onChange={(e) => onToggleWind(e.target.checked)}
            />
            <span className="layer-legend-dot wind-dot">↗️</span>
            <span className="layer-name">Wind Vectors (Open-Meteo)</span>
            <span className="chevron-icon">›</span>
          </label>

          <label className="layer-item">
            <input
              type="checkbox"
              checked={showSchools}
              onChange={(e) => onToggleSchools(e.target.checked)}
            />
            <span className="layer-legend-dot school-dot">🔵</span>
            <span className="layer-name">School Locations</span>
            <span className="chevron-icon">›</span>
          </label>

          <label className="layer-item">
            <input
              type="checkbox"
              checked={showOpenAq}
              onChange={(e) => onToggleOpenAq(e.target.checked)}
            />
            <span className="layer-legend-dot aqi-dot">🟢</span>
            <span className="layer-name">OpenAQ Stations</span>
            <span className="chevron-icon">›</span>
          </label>

          <label className="layer-item">
            <input
              type="checkbox"
              checked={showBoundaries}
              onChange={(e) => onToggleBoundaries(e.target.checked)}
            />
            <span className="layer-legend-dot boundary-dot">🌐</span>
            <span className="layer-name">City / District Boundaries</span>
            <span className="chevron-icon">›</span>
          </label>
        </div>
      </div>

      {/* 3. Overlay Options */}
      <div className="control-card">
        <h3 className="card-section-title">Overlay Options</h3>
        <div className="radio-options-list">
          <label className="radio-option">
            <input
              type="radio"
              name="overlay"
              value="pm25"
              checked={overlayOption === "pm25"}
              onChange={(e) => onOverlayOptionChange(e.target.value)}
            />
            <span>PM2.5 Concentration</span>
          </label>

          <label className="radio-option">
            <input
              type="radio"
              name="overlay"
              value="aqi"
              checked={overlayOption === "aqi"}
              onChange={(e) => onOverlayOptionChange(e.target.value)}
            />
            <span>Air Quality Index (AQI)</span>
          </label>

          <label className="radio-option">
            <input
              type="radio"
              name="overlay"
              value="arrival"
              checked={overlayOption === "arrival"}
              onChange={(e) => onOverlayOptionChange(e.target.value)}
            />
            <span>Plume Arrival Time</span>
          </label>

          <label className="radio-option">
            <input
              type="radio"
              name="overlay"
              value="risk"
              checked={overlayOption === "risk"}
              onChange={(e) => onOverlayOptionChange(e.target.value)}
            />
            <span>Risk Level (Schools)</span>
          </label>
        </div>

        {/* PM2.5 Color Scale Legend */}
        <div className="gradient-legend-box">
          <span className="legend-label">PM2.5 (µg/m³)</span>
          <div className="gradient-bar"></div>
          <div className="gradient-ticks">
            <span>0</span>
            <span>50</span>
            <span>100</span>
            <span>200</span>
            <span>300</span>
            <span>500+</span>
          </div>
        </div>
      </div>
    </aside>
  );
};
