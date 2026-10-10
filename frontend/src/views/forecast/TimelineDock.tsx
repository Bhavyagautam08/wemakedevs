import { KeyboardEvent } from "react";
import { Pause, Play, SkipBack, SkipForward } from "lucide-react";
import { TimelineSlice } from "../../api/types";

interface TimelineDockProps {
  timeline: TimelineSlice[];
  step: number;
  playing: boolean;
  keyHours: number[];
  onStep: (i: number) => void;
  onToggle: () => void;
  onPrev: () => void;
  onNext: () => void;
}

const bandColor = (peak?: number) =>
  peak === undefined ? "var(--surface-3)"
    : peak >= 250 ? "var(--smoke-core)"
    : peak >= 121 ? "var(--smoke-dispersing)"
    : peak >= 50 ? "var(--smoke-fringe)"
    : peak >= 15 ? "var(--smoke-trace)"
    : "var(--surface-3)";

/**
 * Bottom timeline. Each hour is a button whose bar height is the smoke area above the WHO
 * 15 µg/m³ level and whose colour is that hour's peak band. ←/→ step, Space plays.
 */
export function TimelineDock({ timeline, step, playing, keyHours, onStep, onToggle, onPrev, onNext }: TimelineDockProps) {
  const area = (s: TimelineSlice) => s.heatmap_levels?.find((l) => l.level === "trace")?.area_sq_km ?? s.plume_area_sq_km;
  const maxArea = Math.max(1, ...timeline.map(area));
  const current = timeline[step];
  const disabled = timeline.length === 0;

  const onKey = (e: KeyboardEvent) => {
    if (e.key === "ArrowLeft") {
      e.preventDefault();
      onPrev();
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      onNext();
    } else if (e.key === " " && (e.target as HTMLElement).tagName !== "BUTTON") {
      e.preventDefault();
      onToggle();
    }
  };

  return (
    <div className="dock" onKeyDown={onKey}>
      <div className="surface dock-inner" role="group" aria-label="Forecast timeline">
        <div className="dock-transport">
          <button className="icon-btn" onClick={onPrev} disabled={disabled} aria-label="Previous hour" title="Previous hour (←)">
            <SkipBack size={16} />
          </button>
          <button className="play" onClick={onToggle} disabled={disabled} aria-label={playing ? "Pause" : "Play"} title={playing ? "Pause" : "Play animation"}>
            {playing ? <Pause size={18} fill="currentColor" /> : <Play size={18} fill="currentColor" style={{ marginLeft: 2 }} />}
          </button>
          <button className="icon-btn" onClick={onNext} disabled={disabled} aria-label="Next hour" title="Next hour (→)">
            <SkipForward size={16} />
          </button>
        </div>
        <div className="dock-time" aria-live="polite">
          <b className="num">+{current?.horizon_offset_hours ?? 0} h</b>
          <span className="num">
            {current
              ? new Date(current.timestamp).toLocaleString([], { weekday: "short", hour: "2-digit", minute: "2-digit" })
              : "No run yet"}
          </span>
        </div>
        <div className="hours">
          {timeline.map((s, i) => {
            const h = s.horizon_offset_hours;
            const pct = (area(s) / maxArea) * 100;
            return (
              <button
                key={h}
                className={`hour${keyHours.includes(h) ? " key" : ""}${i < step ? " past" : ""}`}
                aria-pressed={i === step}
                aria-label={`+${h} hours: smoke above 15 µg/m³ over ${Math.round(area(s))} km², peak ${Math.round(s.peak_concentration_ugm3 ?? 0)} µg/m³`}
                title={`+${h} h · ${Math.round(area(s))} km² · peak ${Math.round(s.peak_concentration_ugm3 ?? 0)} µg/m³`}
                onClick={() => onStep(i)}
              >
                <span
                  className="col"
                  style={{ height: `${Math.max(3, pct * 0.24)}px`, background: bandColor(s.peak_concentration_ugm3) }}
                />
                <span className="lbl num">{keyHours.includes(h) ? `+${h}h` : h}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
