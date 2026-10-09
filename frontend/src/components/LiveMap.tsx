import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { LiveDataSnapshot } from "../api/types";

const FIRMS_ICON = L.divIcon({
  className: "firms-detection-marker",
  html: "<span></span>",
  iconSize: [10, 10],
  iconAnchor: [5, 5],
});

interface LiveMapProps {
  data: LiveDataSnapshot;
}

function makePopup(fire: LiveDataSnapshot["fires"][number]): HTMLElement {
  const popup = document.createElement("div");
  popup.className = "map-popup fire-popup";

  const title = document.createElement("div");
  title.className = "popup-title";
  title.textContent = "NASA FIRMS VIIRS detection";
  popup.append(title);

  const rows: Array<[string, string]> = [
    ["Detected", new Date(fire.acq_timestamp).toLocaleString()],
    ["FRP", `${fire.frp} MW`],
    ["Confidence", fire.confidence_class || `${fire.confidence}%`],
    ["Satellite", fire.satellite],
    ["Coordinates", `${fire.latitude}, ${fire.longitude}`],
  ];

  for (const [label, value] of rows) {
    const row = document.createElement("div");
    row.className = "popup-row";
    const name = document.createElement("span");
    name.textContent = `${label}:`;
    const content = document.createElement("b");
    content.textContent = value;
    row.append(name, content);
    popup.append(row);
  }

  return popup;
}

export function LiveMap({ data }: LiveMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markersRef = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = L.map(containerRef.current, {
      center: [29.5, 76.5],
      zoom: 7,
      minZoom: 5,
      maxZoom: 16,
    });

    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19,
    }).addTo(map);

    mapRef.current = map;
    markersRef.current = L.layerGroup().addTo(map);

    return () => {
      map.remove();
      mapRef.current = null;
      markersRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const markers = markersRef.current;
    if (!map || !markers) return;

    markers.clearLayers();
    if (data.sources.fires.status !== "ok") return;

    const bounds: L.LatLngExpression[] = [];
    for (const fire of data.fires) {
      if (
        !Number.isFinite(fire.latitude)
        || !Number.isFinite(fire.longitude)
        || fire.latitude < -90
        || fire.latitude > 90
        || fire.longitude < -180
        || fire.longitude > 180
      ) continue;

      const marker = L.marker([fire.latitude, fire.longitude], { icon: FIRMS_ICON })
        .bindPopup(makePopup(fire));
      markers.addLayer(marker);
      bounds.push([fire.latitude, fire.longitude]);
    }

    if (bounds.length > 0) {
      map.fitBounds(L.latLngBounds(bounds), { padding: [32, 32], maxZoom: 9 });
    }
  }, [data]);

  const fireStatus = data.sources.fires;

  return (
    <section className="plume-map-wrapper live-map-card">
      <div className="map-toolbar live-map-toolbar">
        <div>
          <div className="map-badge">
            <span className={fireStatus.status === "ok" ? "live-pulse" : "source-indicator unavailable"} />
            <b>Live NASA FIRMS Active Fire Detections</b>
          </div>
          <small className="map-data-disclosure">
            Satellite-reported VIIRS detections only. No model-generated plume or sample fire markers.
          </small>
        </div>
        <span className="live-count">
          {fireStatus.status === "ok" ? `${data.fires.length} detections` : "Source unavailable"}
        </span>
      </div>
      <div className="map-canvas-container live-map-canvas" ref={containerRef} />
      {fireStatus.status === "error" ? (
        <p className="live-map-message source-error">{fireStatus.error}</p>
      ) : data.fires.length === 0 ? (
        <p className="live-map-message">NASA FIRMS returned no active fire detections for this area and time range.</p>
      ) : null}
    </section>
  );
}
