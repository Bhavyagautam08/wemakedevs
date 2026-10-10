import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import { CircleAlert, ExternalLink, Info, LoaderCircle, Play, Search, TriangleAlert } from "lucide-react";
import { DhuanAlertClient } from "../api/client";
import { useForecast } from "../hooks/useForecast";
import { useTimelineSlider } from "../hooks/useTimelineSlider";
import { MapControls, SwitchRow } from "../map/MapControls";
import { BasemapId, BASEMAPS, consumeUrlView, fitPadding, schoolLabel } from "../map/baseMap";
import { Panel } from "../components/Panel";
import { TimelineDock } from "./forecast/TimelineDock";
import { Legend } from "./forecast/Legend";
import { drawForecast, hoursAfter, LayerVisibility, runBounds, SMOKE_LEVELS } from "./forecast/forecastLayers";

type Mode = "live" | "replay";
type Tab = "schools" | "atmosphere" | "model";

const fmt = (v: number | undefined | null, d = 0) =>
  v === undefined || v === null || Number.isNaN(v) ? "—" : v.toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: d });
const compass = (deg: number) => ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][Math.round((((deg % 360) + 360) % 360) / 45) % 8];
const band = (v?: number) =>
  v === undefined ? "band-ok" : v >= 250 ? "band-severe" : v >= 121 ? "band-verypoor" : v >= 50 ? "band-poor" : v >= 15 ? "band-trace" : "band-ok";

const SCHOOL_PAGE = 120;

export function ForecastView({
  map,
  client,
  apiBaseUrl,
  basemap,
  onBasemap,
}: {
  map: L.Map | null;
  client: DhuanAlertClient;
  apiBaseUrl: string;
  basemap: BasemapId;
  onBasemap: (id: BasemapId) => void;
}) {
  const initialMode: Mode = new URLSearchParams(window.location.search).get("mode") === "replay" ? "replay" : "live";
  const [mode, setMode] = useState<Mode>(initialMode);
  const { data, currentRunId, loading, error, refreshForecast } = useForecast(client, undefined, initialMode);
  const prediction = data?.prediction;
  const timeline = prediction?.timeline ?? [];
  const slider = useTimelineSlider(timeline, 1100);
  const slice = slider.currentSlice;

  const [layers, setLayers] = useState<LayerVisibility>({ smoke: true, particles: true, tracks: true, fires: true, schools: true });
  const [smokeOpacity, setSmokeOpacity] = useState(0.9);
  const [tab, setTab] = useState<Tab>("schools");
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(SCHOOL_PAGE);
  const [selectedSchool, setSelectedSchool] = useState<string | null>(null);
  const [zoom, setZoom] = useState(7);

  const groupRef = useRef<L.LayerGroup | null>(null);
  const schoolMarkers = useRef(new Map<string, L.CircleMarker>());

  // ---- map layer lifecycle ----
  useEffect(() => {
    if (!map) return;
    const group = L.layerGroup().addTo(map);
    groupRef.current = group;
    const onZoom = () => setZoom(map.getZoom());
    map.on("zoomend", onZoom);
    setZoom(map.getZoom());
    return () => {
      map.off("zoomend", onZoom);
      group.remove();
      groupRef.current = null;
    };
  }, [map]);

  useEffect(() => {
    if (!map || !groupRef.current || !prediction) return;
    schoolMarkers.current = drawForecast({
      map,
      group: groupRef.current,
      prediction,
      slice,
      layers,
      smokeOpacity,
      zoom: Math.round(zoom),
      theme: BASEMAPS[basemap].theme,
      selectedSchoolId: selectedSchool,
      onSelectSchool: setSelectedSchool,
    });
  }, [map, prediction, slice, layers, smokeOpacity, zoom, selectedSchool, basemap]);

  const fit = useCallback(() => {
    const b = prediction ? runBounds(prediction) : null;
    if (!map || !b) return;
    map.fitBounds(b, {
      ...fitPadding(),
      maxZoom: 10,
    });
  }, [map, prediction]);

  // New run: fit the map and open on the first reported horizon (+3 h)
  const runId = prediction?.prediction_id;
  useEffect(() => {
    if (!runId || !prediction) return;
    if (!consumeUrlView()) fit();
    setSelectedSchool(null);
    setLimit(SCHOOL_PAGE);
    const first = prediction.simulation.forecast_horizons?.[0];
    const idx = timeline.findIndex((s) => s.horizon_offset_hours === first);
    if (idx >= 0) slider.setCurrentStep(idx);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  const run = () => {
    const params = new URLSearchParams(window.location.search);
    params.set("mode", mode);
    window.history.replaceState(null, "", `?${params.toString()}`);
    refreshForecast(3, mode);
  };

  const focusSchool = (id: string) => {
    const s = prediction?.schools.find((x) => x.school_id === id);
    if (!s || !map || s.latitude === undefined || s.longitude === undefined) return;
    setSelectedSchool(id);
    if (!layers.schools) setLayers((l) => ({ ...l, schools: true }));
    map.flyTo([s.latitude, s.longitude], Math.max(map.getZoom(), 10), { duration: 0.8 });
    window.setTimeout(() => schoolMarkers.current.get(id)?.openPopup(), 850);
  };

  const stats = useMemo(() => {
    if (!prediction) return null;
    const reached = prediction.schools.filter((s) => s.impact_probability > 0);
    const peak = prediction.timeline.reduce(
      (best, s) => ((s.peak_concentration_ugm3 ?? 0) > (best?.peak_concentration_ugm3 ?? -1) ? s : best),
      prediction.timeline[0],
    );
    return { reached, peak };
  }, [prediction]);

  const schools = useMemo(() => {
    const all = prediction?.schools ?? [];
    const q = query.trim().toLowerCase();
    return q ? all.filter((s) => s.name.toLowerCase().includes(q) || (s.district || "").toLowerCase().includes(q)) : all;
  }, [prediction, query]);

  const traceArea = slice?.heatmap_levels?.find((l) => l.level === "trace")?.area_sq_km;
  const hour = slice?.horizon_offset_hours ?? 0;

  // ---------------- panel header ----------------
  const head = (
    <>
      <div className="panel-title-row" style={{ paddingRight: 30 }}>
        <div>
          <p className="eyebrow">Smoke dispersion forecast</p>
          <h1 className="panel-title">
            {prediction ? `${prediction.simulation.fire_cluster_count} fire clusters · next 9 h` : "All active fires in India"}
          </h1>
          <p className="panel-sub num">
            {prediction
              ? `T0 ${new Date(prediction.valid_from).toLocaleString([], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })} · ${prediction.weather.station_count ?? 1} weather points · ${mode === "replay" ? "saved capture" : "live inputs"}`
              : "NASA FIRMS fires · Open-Meteo GFS · OpenStreetMap schools"}
          </p>
        </div>
      </div>

      <div style={{ display: "flex", gap: 8 }}>
        <div className="segmented" role="group" aria-label="Input data" style={{ flex: "none" }}>
          <button aria-pressed={mode === "live"} onClick={() => setMode("live")} disabled={loading} title="FIRMS last 24 h + forecast from now">
            Live
          </button>
          <button aria-pressed={mode === "replay"} onClick={() => setMode("replay")} disabled={loading} title="Saved capture of real FIRMS + GFS data">
            Replay
          </button>
        </div>
        <button className="btn btn-primary" style={{ flex: 1 }} onClick={run} disabled={loading}>
          {loading ? <LoaderCircle size={16} className="spin" /> : <Play size={14} fill="currentColor" />}
          {loading ? "Simulating…" : "Run simulation"}
        </button>
      </div>

      {prediction ? (
        <div className="kpis panel-optional">
          <div className="kpi">
            <span className="kpi-label">Peak smoke · +{hour} h</span>
            <span className={`kpi-value banded num ${band(slice?.peak_concentration_ugm3)}`}>
              {fmt(slice?.peak_concentration_ugm3)}
              <small>µg/m³</small>
            </span>
            <span className="kpi-foot">run max {fmt(stats?.peak?.peak_concentration_ugm3)} at +{stats?.peak?.horizon_offset_hours} h</span>
          </div>
          <div className="kpi">
            <span className="kpi-label">Schools reached · +{hour} h</span>
            <span className="kpi-value num">
              {slice?.affected_schools_count ?? 0}
              <small>/ {prediction.schools.length}</small>
            </span>
            <span className="kpi-foot">{stats?.reached.length} within 9 h (≥ 50 µg/m³)</span>
          </div>
          <div className="kpi">
            <span className="kpi-label">Area ≥ 50 µg/m³ · +{hour} h</span>
            <span className="kpi-value num">
              {fmt(slice?.plume_area_sq_km)}
              <small>km²</small>
            </span>
            <span className="kpi-foot">{fmt(traceArea)} km² above 15 µg/m³</span>
          </div>
          <div className="kpi">
            <span className="kpi-label">PM2.5 emission</span>
            <span className="kpi-value num">
              {fmt(prediction.simulation.total_emission_rate_kg_s, 2)}
              <small>kg/s</small>
            </span>
            <span className="kpi-foot">Cₑ × FRP, {prediction.simulation.emission_duration_hours} h burn</span>
          </div>
        </div>
      ) : (
        loading && (
          <div className="kpis" aria-hidden="true">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="kpi">
                <span className="skeleton" style={{ height: 10, width: "60%" }} />
                <span className="skeleton" style={{ height: 22, width: "45%", marginTop: 6 }} />
              </div>
            ))}
          </div>
        )
      )}
    </>
  );

  return (
    <>
      <Panel label="Forecast" head={head}>
        {loading && <div className="progress"><span /></div>}

        {error && (
          <div className="panel-section">
            <div className="callout error" role="alert">
              <CircleAlert size={16} />
              <div>
                <b>Simulation failed.</b> {error}
                <div style={{ marginTop: 6 }}>
                  <button className="link" style={{ background: "none", border: 0, padding: 0, cursor: "pointer" }} onClick={run}>
                    Try again
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {loading && !prediction && (
          <div className="panel-section faint" style={{ fontSize: 12 }}>
            Fetching fires, a weather grid and schools, then advecting particles for 9 hours. Live runs take 10–20 s.
          </div>
        )}

        {prediction && stats && (
          <>
            {stats.reached.length === 0 && (
              <div className="panel-section">
                <div className="callout">
                  <Info size={16} />
                  <div>
                    No school crosses {prediction.simulation.impact_threshold_ugm3} µg/m³ within 9 h. Peak modelled smoke is{" "}
                    <b>{fmt(stats.peak?.peak_concentration_ugm3)} µg/m³</b> at +{stats.peak?.horizon_offset_hours} h; the strongest
                    cluster was detected {fmt(prediction.fire.source_freshness_hours, 1)} h before T0.
                  </div>
                </div>
              </div>
            )}

            <div className="tabs" role="tablist" aria-label="Forecast details">
              <button className="tab" role="tab" aria-selected={tab === "schools"} onClick={() => setTab("schools")}>
                Schools <span className="count num">{stats.reached.length}/{prediction.schools.length}</span>
              </button>
              <button className="tab" role="tab" aria-selected={tab === "atmosphere"} onClick={() => setTab("atmosphere")}>
                Atmosphere
              </button>
              <button className="tab" role="tab" aria-selected={tab === "model"} onClick={() => setTab("model")}>
                Model
              </button>
            </div>

            {tab === "schools" && (
              <section className="panel-section" role="tabpanel">
                <label className="search">
                  <Search size={14} />
                  <span className="sr-only">Search schools</span>
                  <input
                    type="search"
                    placeholder={`Search ${prediction.schools.length} schools`}
                    value={query}
                    onChange={(e) => {
                      setQuery(e.target.value);
                      setLimit(SCHOOL_PAGE);
                    }}
                  />
                </label>
                <p className="faint" style={{ fontSize: 11, margin: "8px 0 4px" }}>
                  OpenStreetMap schools where modelled smoke exceeds 15 µg/m³, ranked by risk.
                </p>
                {schools.length === 0 ? (
                  <div className="empty">{query ? "No schools match your search." : "No schools inside the smoke footprint."}</div>
                ) : (
                  <ul className="list">
                    {schools.slice(0, limit).map((s) => (
                      <li key={s.school_id}>
                        <button className="list-item" aria-current={selectedSchool === s.school_id} onClick={() => focusSchool(s.school_id)}>
                          <span className={`risk-dot risk-${s.risk_band}`} title={s.risk_band.replace("_", " ")} />
                          <span style={{ minWidth: 0 }}>
                            <span className="name" style={{ display: "block" }} title={schoolLabel(s.name).detail ?? s.name}>
                              {schoolLabel(s.name).label}
                            </span>
                            <span className="meta" style={{ display: "block" }}>
                              {s.district ? `${s.district} · ` : ""}
                              {s.distance_to_fire_km.toFixed(0)} km from fire · {Math.round(s.impact_probability * 100)}% of scenarios
                            </span>
                          </span>
                          <span className="val num">
                            {s.peak_concentration.toFixed(0)}
                            <small>
                              {s.predicted_arrival_time ? `+${hoursAfter(prediction.valid_from, s.predicted_arrival_time).toFixed(1)} h` : "µg/m³"}
                            </small>
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                {schools.length > limit && (
                  <button className="btn btn-block" style={{ marginTop: 8 }} onClick={() => setLimit((l) => l + SCHOOL_PAGE)}>
                    Show {Math.min(SCHOOL_PAGE, schools.length - limit)} more
                  </button>
                )}
              </section>
            )}

            {tab === "atmosphere" && (
              <section className="panel-section" role="tabpanel">
                <p className="faint" style={{ fontSize: 11.5, marginBottom: 10 }}>
                  Mean of {prediction.weather.station_count ?? 1} GFS grid points. The model interpolates between them in space
                  and hour by hour in time.
                </p>
                <table className="table num">
                  <thead>
                    <tr>
                      <th>Hour</th>
                      <th>Wind from</th>
                      <th className="r">m/s</th>
                      <th className="r">BLH m</th>
                      <th className="r">Rain</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(prediction.weather.at_horizons ?? []).map((w) => (
                      <tr key={w.horizon_hours} className={hour === w.horizon_hours ? "active" : ""}>
                        <td>+{w.horizon_hours} h</td>
                        <td>
                          <span className="wind-arrow" style={{ transform: `rotate(${w.wind_direction_deg + 180}deg)` }} aria-hidden="true">↑</span>{" "}
                          {compass(w.wind_direction_deg)} {fmt(w.wind_direction_deg)}°
                        </td>
                        <td className="r">{fmt(w.wind_speed_mps, 1)}</td>
                        <td className="r">{fmt(w.boundary_layer_height_m)}</td>
                        <td className="r">{fmt(w.precipitation_mm, 1)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="faint" style={{ fontSize: 11, marginTop: 10 }}>
                  A shallow boundary layer (BLH) traps smoke near the ground and raises concentration.
                </p>
              </section>
            )}

            {tab === "model" && (
              <>
                <section className="panel-section" role="tabpanel">
                  <div className="section-head">
                    <h2 className="eyebrow">Chained plume state</h2>
                  </div>
                  <table className="table num">
                    <thead>
                      <tr>
                        <th>Hour</th>
                        <th className="r">Particles</th>
                        <th className="r">Mass kg</th>
                        <th className="r">Mixing m</th>
                      </tr>
                    </thead>
                    <tbody>
                      {prediction.simulation.horizon_states.map((h) => (
                        <tr key={h.horizon_hours} className={hour === h.horizon_hours ? "active" : ""}>
                          <td>+{h.horizon_hours} h</td>
                          <td className="r">{h.particle_count.toLocaleString()}</td>
                          <td className="r">{Math.round(h.total_mass_kg).toLocaleString()}</td>
                          <td className="r">{fmt(h.mixing_height_m)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="faint" style={{ fontSize: 11, marginTop: 8 }}>
                    One continuous run: +6 h continues from the +3 h particles.
                  </p>
                </section>
                <section className="panel-section">
                  <div className="section-head">
                    <h2 className="eyebrow">Ensemble peak at +9 h</h2>
                  </div>
                  {prediction.ensemble.members.map((m) => (
                    <div key={m.member_id} className="member">
                      <div className="member-head">
                        <span className="muted">{m.name}</span>
                        <b className="num">{fmt(m.peak_concentration)} µg/m³</b>
                      </div>
                      <div className="bar">
                        <span style={{ width: `${Math.min(100, (m.peak_concentration / 250) * 100)}%` }} />
                      </div>
                    </div>
                  ))}
                  <p className="faint" style={{ fontSize: 11, marginTop: 8 }}>Bar relative to CPCB “Severe”, 250 µg/m³.</p>
                </section>
                <section className="panel-section">
                  <div className="callout caveat">
                    <TriangleAlert size={16} />
                    <div>
                      Modelled smoke PM2.5 increment, not total AQI. Not yet validated against CAAQMS/OpenAQ stations. Burn
                      duration and fire persistence are assumptions.
                    </div>
                  </div>
                  {currentRunId && (
                    <p style={{ marginTop: 12 }}>
                      <a className="link" href={`${apiBaseUrl}/v1/runs/${currentRunId}/prediction`} target="_blank" rel="noreferrer">
                        Raw prediction JSON <ExternalLink size={12} />
                      </a>
                    </p>
                  )}
                </section>
              </>
            )}
          </>
        )}
      </Panel>

      <MapControls
        map={map}
        onFit={prediction ? fit : undefined}
        fitLabel="Fit to plume"
        basemap={basemap}
        onBasemap={onBasemap}
        layers={
          <>
            <div className="group">
              <h3>Layers</h3>
              <SwitchRow
                label="Smoke density"
                checked={layers.smoke}
                onChange={(v) => setLayers((l) => ({ ...l, smoke: v }))}
                swatch={<span className="swatch" style={{ background: `linear-gradient(90deg, ${SMOKE_LEVELS.trace.color}, ${SMOKE_LEVELS.core.color})` }} />}
              />
              <SwitchRow label="Particles" checked={layers.particles} onChange={(v) => setLayers((l) => ({ ...l, particles: v }))} swatch={<i className="key-particle" style={{ margin: "0 4px" }} />} />
              <SwitchRow label="Plume tracks" checked={layers.tracks} onChange={(v) => setLayers((l) => ({ ...l, tracks: v }))} swatch={<i className="key-track" />} />
              <SwitchRow label="Fire clusters" checked={layers.fires} onChange={(v) => setLayers((l) => ({ ...l, fires: v }))} swatch={<i className="key-fire" style={{ margin: "0 2px" }} />} />
              <SwitchRow label="Schools" checked={layers.schools} onChange={(v) => setLayers((l) => ({ ...l, schools: v }))} swatch={<i className="key-school" style={{ margin: "0 2px" }} />} />
            </div>
            <div className="group">
              <label style={{ display: "grid", gap: 4 }}>
                <span style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                  <span>Smoke opacity</span>
                  <span className="faint num">{Math.round(smokeOpacity * 100)}%</span>
                </span>
                <input
                  className="range"
                  type="range"
                  min={0.2}
                  max={1}
                  step={0.05}
                  value={smokeOpacity}
                  style={{ ["--fill" as string]: `${((smokeOpacity - 0.2) / 0.8) * 100}%` }}
                  onChange={(e) => setSmokeOpacity(Number(e.target.value))}
                />
              </label>
            </div>
            <div className="group legend-in-popover">
              <Legend floating={false} />
            </div>
          </>
        }
      />

      {prediction && <Legend />}

      <TimelineDock
        timeline={timeline}
        step={slider.currentStep}
        playing={slider.isPlaying}
        keyHours={prediction?.simulation.forecast_horizons ?? [3, 6, 9]}
        onStep={slider.setCurrentStep}
        onToggle={slider.togglePlay}
        onPrev={slider.prevStep}
        onNext={slider.nextStep}
      />

      {loading && (
        <div className="surface toast" role="status">
          <LoaderCircle size={15} className="spin" style={{ color: "var(--accent)" }} />
          {mode === "live" ? "Running live simulation…" : "Running replay simulation…"}
        </div>
      )}
    </>
  );
}
