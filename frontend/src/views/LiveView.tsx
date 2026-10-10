import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import { CircleAlert, Flame, RefreshCw, Wind } from "lucide-react";
import { DhuanAlertClient } from "../api/client";
import { LiveDataSnapshot } from "../api/types";
import { useLiveData } from "../hooks/useLiveData";
import { BasemapId, confidenceName, consumeUrlView, fireIcon, fitPadding, popupContent, satelliteName } from "../map/baseMap";
import { MapControls } from "../map/MapControls";
import { Panel } from "../components/Panel";

type Fire = LiveDataSnapshot["fires"][number];

const compass = (deg: number) => ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][Math.round((((deg % 360) + 360) % 360) / 45) % 8];
const fireSize = (frp: number) => Math.max(8, Math.min(22, 7 + Math.sqrt(Math.max(frp, 0)) * 2.2));

function ageLabel(iso: string) {
  const h = (Date.now() - new Date(iso).getTime()) / 3.6e6;
  return h < 1 ? `${Math.max(1, Math.round(h * 60))} min ago` : `${h.toFixed(h < 10 ? 1 : 0)} h ago`;
}

export function LiveView({
  map,
  client,
  basemap,
  onBasemap,
}: {
  map: L.Map | null;
  client: DhuanAlertClient;
  basemap: BasemapId;
  onBasemap: (id: BasemapId) => void;
}) {
  const { data, loading, error, refresh } = useLiveData(client);
  const layerRef = useRef<L.LayerGroup | null>(null);
  const markers = useRef(new Map<string, L.Marker>());
  const [selected, setSelected] = useState<string | null>(null);

  const fires = useMemo(
    () => (data?.sources.fires.status === "ok" ? [...data.fires].sort((a, b) => b.frp - a.frp) : []),
    [data],
  );

  const fit = useCallback(() => {
    if (!map || fires.length === 0) return;
    map.fitBounds(L.latLngBounds(fires.map((f) => [f.latitude, f.longitude] as [number, number])), {
      ...fitPadding(),
      maxZoom: 8,
    });
  }, [map, fires]);

  // Layer lifecycle: owned by this view, removed when switching away.
  useEffect(() => {
    if (!map) return;
    const group = L.layerGroup().addTo(map);
    layerRef.current = group;
    return () => {
      group.remove();
      layerRef.current = null;
    };
  }, [map]);

  useEffect(() => {
    const group = layerRef.current;
    if (!group) return;
    group.clearLayers();
    markers.current.clear();
    for (const f of fires) {
      if (!Number.isFinite(f.latitude) || !Number.isFinite(f.longitude)) continue;
      const m = L.marker([f.latitude, f.longitude], { icon: fireIcon(fireSize(f.frp)), pane: "points", keyboard: false })
        .bindPopup(
          popupContent("Active fire · NASA FIRMS", [
            ["Detected", `${new Date(f.acq_timestamp).toLocaleString()} (${ageLabel(f.acq_timestamp)})`],
            ["Fire radiative power", `${f.frp} MW`],
            ["Confidence", confidenceName(f.confidence_class, f.confidence)],
            ["Satellite", `VIIRS · ${satelliteName(f.satellite)}`],
            ["Location", `${f.latitude.toFixed(3)}°N, ${f.longitude.toFixed(3)}°E`],
          ]),
        )
        .on("click", () => setSelected(f.detection_id));
      group.addLayer(m);
      markers.current.set(f.detection_id, m);
    }
    if (fires.length && !consumeUrlView()) fit();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fires, map]);

  const focus = (f: Fire) => {
    setSelected(f.detection_id);
    map?.flyTo([f.latitude, f.longitude], Math.max(map.getZoom(), 10), { duration: 0.8 });
    markers.current.get(f.detection_id)?.openPopup();
  };

  const weather = useMemo(() => {
    if (!data || data.weather.length === 0) return null;
    const now = Date.now();
    return data.weather.find((w) => new Date(w.forecast_timestamp).getTime() >= now) ?? data.weather[data.weather.length - 1];
  }, [data]);

  const totalFrp = fires.reduce((s, f) => s + f.frp, 0);
  const latest = fires.reduce<string | null>((l, f) => (!l || f.acq_timestamp > l ? f.acq_timestamp : l), null);

  const head = (
    <>
      <div className="panel-title-row" style={{ paddingRight: 30 }}>
        <div>
          <p className="eyebrow">Live satellite feed</p>
          <h1 className="panel-title">Active fires · India</h1>
          <p className="panel-sub">
            {data ? `Updated ${new Date(data.fetched_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} · refreshes every 5 min` : "Connecting to NASA FIRMS…"}
          </p>
        </div>
      </div>
      <div className="kpis">
        <div className="kpi">
          <span className="kpi-label">Detections (24 h)</span>
          <span className="kpi-value num">{data ? fires.length : "—"}</span>
          <span className="kpi-foot">VIIRS, India only</span>
        </div>
        <div className="kpi">
          <span className="kpi-label">Total fire power</span>
          <span className="kpi-value num">
            {data ? Math.round(totalFrp).toLocaleString() : "—"}
            <small>MW</small>
          </span>
          <span className="kpi-foot">sum of FRP</span>
        </div>
      </div>
      <button className="btn btn-block" onClick={() => void refresh()} disabled={loading}>
        <RefreshCw size={15} className={loading ? "spin" : undefined} />
        {loading ? "Refreshing…" : "Refresh now"}
      </button>
    </>
  );

  return (
    <>
      <Panel label="Live data" head={head}>
        {loading && <div className="progress"><span /></div>}
        {error && (
          <div className="panel-section">
            <div className="callout error" role="alert">
              <CircleAlert size={16} />
              <div>
                <b>Live data API unavailable.</b> {error}
              </div>
            </div>
          </div>
        )}

        {data && (
          <>
            <section className="panel-section">
              <div className="section-head">
                <h2 className="eyebrow">Sources</h2>
              </div>
              {(["fires", "weather"] as const).map((k) => {
                const s = data.sources[k];
                return (
                  <div key={k} style={{ display: "flex", alignItems: "center", gap: 10, padding: "6px 0" }}>
                    <span className={`dot ${s.status === "ok" ? "ok" : "err"}`} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: 600 }}>{s.name}</div>
                      <div className="faint" style={{ fontSize: 11.5 }}>
                        {s.status === "ok" ? `${s.count} records` : s.error}
                      </div>
                    </div>
                  </div>
                );
              })}
            </section>

            {weather && (
              <section className="panel-section">
                <div className="section-head">
                  <h2 className="eyebrow">Weather at strongest fire</h2>
                  <span className="faint" style={{ fontSize: 11 }}>
                    {new Date(weather.forecast_timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <span
                    className="wind-arrow"
                    style={{ transform: `rotate(${weather.wind_direction_deg + 180}deg)`, fontSize: 22 }}
                    aria-hidden="true"
                  >
                    ↑
                  </span>
                  <div>
                    <div style={{ fontSize: 18, fontWeight: 650 }} className="num">
                      {(weather.wind_speed_mps * 3.6).toFixed(0)} km/h <span className="muted" style={{ fontSize: 13 }}>from {compass(weather.wind_direction_deg)} ({Math.round(weather.wind_direction_deg)}°)</span>
                    </div>
                    <div className="faint" style={{ fontSize: 11.5 }}>
                      {weather.temperature_c}°C · boundary layer {Math.round(weather.boundary_layer_height_m)} m
                    </div>
                  </div>
                  <Wind size={16} className="faint" style={{ marginLeft: "auto" }} />
                </div>
              </section>
            )}

            <section className="panel-section">
              <div className="section-head">
                <h2 className="eyebrow">Detections by fire power</h2>
                {latest && <span className="faint" style={{ fontSize: 11 }}>latest {ageLabel(latest)}</span>}
              </div>
              {fires.length === 0 ? (
                <div className="empty">
                  <Flame size={18} style={{ opacity: 0.6 }} />
                  <p style={{ marginTop: 6 }}>
                    {data.sources.fires.status === "ok"
                      ? "NASA FIRMS reports no active fires in India in the last 24 h."
                      : "Fire source unavailable."}
                  </p>
                </div>
              ) : (
                <ul className="list">
                  {fires.map((f) => (
                    <li key={f.detection_id}>
                      <button className="list-item" aria-current={selected === f.detection_id} onClick={() => focus(f)}>
                        <span className="risk-dot" style={{ background: "var(--fire)" }} />
                        <span style={{ minWidth: 0 }}>
                          <span className="name" style={{ display: "block" }}>
                            {f.latitude.toFixed(3)}°N, {f.longitude.toFixed(3)}°E
                          </span>
                          <span className="meta" style={{ display: "block" }}>
                            {satelliteName(f.satellite)} · {ageLabel(f.acq_timestamp)} · {confidenceName(f.confidence_class, f.confidence)} confidence
                          </span>
                        </span>
                        <span className="val num">
                          {f.frp.toFixed(1)}
                          <small>MW</small>
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </>
        )}
      </Panel>
      <MapControls map={map} onFit={fit} fitLabel="Fit to detections" basemap={basemap} onBasemap={onBasemap} />
    </>
  );
}
