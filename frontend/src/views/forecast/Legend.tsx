import { SMOKE_LEVELS } from "./forecastLayers";

/** Smoke scale (CPCB/WHO thresholds) and map keys. */
export function Legend({ floating = true }: { floating?: boolean }) {
  const order = ["trace", "fringe", "dispersing", "core"];
  return (
    <div className={floating ? "surface legend" : undefined} aria-label="Legend">
      <h3>Smoke PM2.5 increment, µg/m³</h3>
      <div className="scale" aria-hidden="true">
        {order.map((k) => (
          <span key={k} style={{ background: SMOKE_LEVELS[k].color }} />
        ))}
      </div>
      <div className="scale-labels num">
        <span>15+</span>
        <span>50+</span>
        <span>121+</span>
        <span>250+</span>
      </div>
      <div className="scale-labels" style={{ fontSize: 10 }}>
        <span>WHO</span>
        <span>Impact</span>
        <span>V. poor</span>
        <span>Severe</span>
      </div>
      <div className="legend-keys">
        <span><i className="key-fire" /> Fire cluster</span>
        <span><i className="key-particle" /> Particle</span>
        <span><i className="key-track" /> Plume track</span>
        <span><i className="key-school" /> School</span>
      </div>
    </div>
  );
}
