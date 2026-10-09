import React from "react";
import { TimelineSlice } from "../api/types";

interface TimelineSliderControlProps {
  timeline: TimelineSlice[];
  currentStep: number;
  currentSlice: TimelineSlice | null;
  isPlaying: boolean;
  onTogglePlay: () => void;
  onStepChange: (step: number) => void;
  onNext: () => void;
  onPrev: () => void;
}

export const TimelineSliderControl: React.FC<TimelineSliderControlProps> = ({
  timeline,
  currentStep,
  currentSlice,
  isPlaying,
  onTogglePlay,
  onStepChange,
  onNext,
  onPrev,
}) => {
  if (!timeline || timeline.length === 0) return null;

  return (
    <div className="timeline-card">
      <div className="timeline-header">
        <div>
          <h3>Hourly Plume Advection & School Impact</h3>
          <p className="subtext">
            Returned forecast slices: T+{timeline[0].horizon_offset_hours}h to T+
            {timeline[timeline.length - 1].horizon_offset_hours}h
          </p>
        </div>

        <div className="slice-info">
          <span className="hour-badge">
            {currentSlice ? `T+${currentSlice.horizon_offset_hours} Hours` : "Forecast unavailable"}
          </span>
          <span className="schools-hit-badge">
            {currentSlice ? `${currentSlice.affected_schools_count} Schools Impacted` : "Impact unavailable"}
          </span>
        </div>
      </div>

      <div className="slider-row">
        <button className="btn btn-icon" onClick={onTogglePlay}>
          {isPlaying ? "⏸ Pause" : "▶ Play Animation"}
        </button>
        <button className="btn btn-icon" onClick={onPrev}>
          ⏮
        </button>

        <input
          type="range"
          min="0"
          max={timeline.length - 1}
          value={currentStep}
          onChange={(e) => onStepChange(Number(e.target.value))}
          className="time-range-input"
        />

        <button className="btn btn-icon" onClick={onNext}>
          ⏭
        </button>
      </div>

      <div className="slider-ticks">
        {timeline.map((s, idx) => (
          <div
            key={s.horizon_offset_hours}
            className={`tick-item ${idx === currentStep ? "active" : ""}`}
            onClick={() => onStepChange(idx)}
          >
            <span className="tick-label">T+{s.horizon_offset_hours}h</span>
            <span className="tick-area">{Math.round(s.plume_area_sq_km)} km²</span>
          </div>
        ))}
      </div>
    </div>
  );
};
