import { useEffect, useMemo, useRef, useState } from "react";
import type L from "leaflet";
import { CloudFog, Satellite } from "lucide-react";
import { DhuanAlertClient } from "./api/client";
import { BasemapId, BASEMAPS, createBaseMap, setBasemap, urlView } from "./map/baseMap";
import { LiveView } from "./views/LiveView";
import { ForecastView } from "./views/ForecastView";

type View = "live" | "forecast";

function readView(): View {
  return new URLSearchParams(window.location.search).get("view") === "forecast" ? "forecast" : "live";
}

function BrandMark() {
  // Plume rising from a point source
  return (
    <svg className="brand-mark" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="6" cy="18" r="3" fill="#ff5c35" />
      <path d="M8.5 15.5c3-1 4.5-3.5 6.5-5.5s4-2.5 6-2" stroke="#f6b23e" strokeWidth="2" strokeLinecap="round" />
      <path d="M9 18.5c4 0 6-1.5 8-3.5s3.5-2.5 5-2.5" stroke="#7aa7ff" strokeWidth="2" strokeLinecap="round" opacity=".9" />
    </svg>
  );
}

export function App() {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:3000";
  const client = useMemo(() => new DhuanAlertClient(apiBaseUrl), [apiBaseUrl]);
  const stageRef = useRef<HTMLDivElement | null>(null);
  const [map, setMap] = useState<L.Map | null>(null);
  const [view, setView] = useState<View>(readView);
  const [basemap, setBasemapId] = useState<BasemapId>(() => {
    try {
      const saved = localStorage.getItem("dhuanalert.basemap") as BasemapId | null;
      return saved && saved in BASEMAPS ? saved : "streets";
    } catch {
      return "streets";
    }
  });

  useEffect(() => {
    if (!map) return;
    setBasemap(map, basemap);
    try {
      localStorage.setItem("dhuanalert.basemap", basemap);
    } catch {
      /* private mode: preference just isn't remembered */
    }
  }, [map, basemap]);

  // One map for the whole session; views add and remove their own layers.
  useEffect(() => {
    if (!stageRef.current) return;
    const m = createBaseMap(stageRef.current);
    const v = urlView();
    if (v) m.setView(v.center, v.zoom);
    // Shareable position: keep ?ll=lat,lng&z=zoom in the URL as the map moves
    const sync = () => {
      const c = m.getCenter();
      const params = new URLSearchParams(window.location.search);
      params.set("ll", `${c.lat.toFixed(4)},${c.lng.toFixed(4)}`);
      params.set("z", String(m.getZoom()));
      window.history.replaceState(null, "", `?${params.toString()}`);
    };
    m.on("moveend", sync);
    setMap(m);
    return () => {
      m.off("moveend", sync);
      m.remove();
      setMap(null);
    };
  }, []);

  const switchView = (v: View) => {
    setView(v);
    const params = new URLSearchParams(window.location.search);
    params.set("view", v);
    window.history.replaceState(null, "", `?${params.toString()}`);
  };

  return (
    <div className="app">
      <div className="map-stage" ref={stageRef} aria-label="Map" role="region" />
      <div className="map-vignette" />
      <div className="overlay">
        <header className="surface topbar">
          <div className="brand">
            <BrandMark />
            <span className="brand-name">DhuanAlert</span>
          </div>
          <nav className="segmented" aria-label="View">
            <button aria-pressed={view === "live"} onClick={() => switchView("live")}>
              <Satellite size={15} /> Live fires
            </button>
            <button aria-pressed={view === "forecast"} onClick={() => switchView("forecast")}>
              <CloudFog size={15} /> Smoke forecast
            </button>
          </nav>
        </header>

        {view === "live" ? (
          <LiveView map={map} client={client} basemap={basemap} onBasemap={setBasemapId} />
        ) : (
          <ForecastView map={map} client={client} apiBaseUrl={apiBaseUrl} basemap={basemap} onBasemap={setBasemapId} />
        )}
      </div>
    </div>
  );
}

export default App;
