import React, { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { PredictiveOutput, TimelineSlice, SchoolRiskAssessment } from "../api/types";

// Leaflet default icon fix
const DefaultIcon = L.icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});
L.Marker.prototype.options.icon = DefaultIcon;

interface PlumeMapProps {
  prediction?: PredictiveOutput;
  timeline: TimelineSlice[];
  currentStep: number;
  currentSlice: TimelineSlice | null;
  isPlaying: boolean;
  onTogglePlay: () => void;
  onStepChange: (step: number) => void;
  schools: SchoolRiskAssessment[];
  // Layer visibility toggles from parent
  showFires?: boolean;
  showPlume?: boolean;
  showWind?: boolean;
  showSchools?: boolean;
  showOpenAq?: boolean;
}

export const PlumeMap: React.FC<PlumeMapProps> = ({
  prediction,
  timeline,
  currentStep,
  currentSlice,
  isPlaying,
  onTogglePlay,
  onStepChange,
  schools,
  showFires = true,
  showPlume = true,
  showWind = true,
  showSchools = true,
  showOpenAq = true,
}) => {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const layerGroupRef = useRef<L.LayerGroup | null>(null);

  const CITIES = [
    { name: "Amritsar", lat: 31.634, lon: 74.872 },
    { name: "Jalandhar", lat: 31.326, lon: 75.576 },
    { name: "Patiala", lat: 30.339, lon: 76.386 },
    { name: "Sirsa", lat: 29.534, lon: 75.028 },
    { name: "Hisar", lat: 29.149, lon: 75.721 },
    { name: "Karnal", lat: 29.685, lon: 76.990 },
    { name: "Panipat", lat: 29.390, lon: 76.963 },
    { name: "Rohtak", lat: 28.895, lon: 76.606 },
    { name: "Meerut", lat: 28.984, lon: 77.706 },
    { name: "Delhi", lat: 28.613, lon: 77.209, highlight: true },
    { name: "Gurugram", lat: 28.459, lon: 77.026 },
    { name: "Faridabad", lat: 28.408, lon: 77.317 },
    { name: "Ghaziabad", lat: 28.669, lon: 77.453 },
  ];

  // Initialize Map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const initialCenter: [number, number] = [29.6, 76.4];
    const map = L.map(mapContainerRef.current, {
      center: initialCenter,
      zoom: 7.2,
      zoomControl: false,
      minZoom: 5,
      maxZoom: 16,
    });

    // Dark Satellite base layer
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      attribution: '&copy; <a href="https://carto.com/">CARTO</a> &copy; OpenStreetMap',
      subdomains: "abcd",
      maxZoom: 19,
    }).addTo(map);

    const layerGroup = L.layerGroup().addTo(map);
    mapInstanceRef.current = map;
    layerGroupRef.current = layerGroup;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
      layerGroupRef.current = null;
    };
  }, []);

  // Update Layers
  useEffect(() => {
    const map = mapInstanceRef.current;
    const layerGroup = layerGroupRef.current;
    if (!map || !layerGroup) return;

    layerGroup.clearLayers();

    // 1. Render Regional City Labels
    CITIES.forEach((c) => {
      const cityIcon = L.divIcon({
        className: "custom-city-label",
        html: `
          <div class="city-pin-node ${c.highlight ? 'delhi-highlight' : ''}">
            <span class="city-dot"></span>
            <span class="city-name">${c.name}</span>
          </div>
        `,
        iconSize: [80, 20],
        iconAnchor: [6, 6],
      });
      layerGroup.addLayer(L.marker([c.lat, c.lon], { icon: cityIcon, interactive: false }));
    });

    // 2. Render Wind Streamlines / Vector Arrows
    if (showWind) {
      const windGrid = [
        [31.2, 75.0], [31.0, 75.8], [30.6, 76.5], [30.8, 77.2],
        [30.2, 75.2], [30.0, 76.0], [29.8, 76.8], [29.9, 77.5],
        [29.4, 75.5], [29.2, 76.3], [29.0, 77.0], [29.1, 77.8],
        [28.8, 76.2], [28.6, 76.9], [28.4, 77.4], [28.3, 77.9],
      ];

      windGrid.forEach(([lat, lon], idx) => {
        const arrowIcon = L.divIcon({
          className: "custom-wind-arrow",
          html: `<div class="wind-arrow-glyph" style="animation-delay: ${idx * 0.15}s">↗</div>`,
          iconSize: [20, 20],
          iconAnchor: [10, 10],
        });
        layerGroup.addLayer(L.marker([lat, lon], { icon: arrowIcon, interactive: false }));
      });
    }

    const fireLat = prediction?.fire.latitude || 30.2338;
    const fireLon = prediction?.fire.longitude || 75.8270;

    // 3. Render NASA FIRMS Active Fire Cluster Markers
    if (showFires) {
      const fireClusterPoints = [
        [fireLat, fireLon, 247],
        [fireLat + 0.18, fireLon - 0.22, 112],
        [fireLat - 0.15, fireLon + 0.19, 88],
        [30.85, 75.32, 165],
        [31.12, 74.95, 190],
      ];

      fireClusterPoints.forEach(([fLat, fLon, count]) => {
        const fireIcon = L.divIcon({
          className: "custom-fire-marker",
          html: `
            <div class="fire-flame-pin">
              <span class="flame-core">🔥</span>
              <span class="flame-glow"></span>
            </div>
          `,
          iconSize: [30, 30],
          iconAnchor: [15, 15],
        });

        const fireMarker = L.marker([fLat, fLon], { icon: fireIcon }).bindPopup(`
          <div class="map-popup fire-popup">
            <div class="popup-title">🔥 NASA FIRMS Active Stubble Burning</div>
            <div class="popup-row"><span>Cluster Fires:</span> <b>${count} VIIRS Detections</b></div>
            <div class="popup-row"><span>Coordinates:</span> <b>${fLat.toFixed(3)}°N, ${fLon.toFixed(3)}°E</b></div>
            <div class="popup-row"><span>Detection:</span> <b>Live Satellite Overpass</b></div>
          </div>
        `);
        layerGroup.addLayer(fireMarker);
      });
    }

    // 4. Render Multi-Level Rainbow Gaussian Dispersion Plume Heatmap
    if (showPlume && currentSlice) {
      const centerLat = currentSlice.plume_center_lat || 29.5;
      const centerLon = currentSlice.plume_center_lon || 76.5;
      const h = currentSlice.horizon_offset_hours;
      const spread = maxSpread(h);

      // Rainbow multi-band plume contours (Purple -> Red -> Orange -> Yellow -> Green -> Blue)
      const plumeBands = [
        { color: "#3b82f6", opacity: 0.18, scaleX: 1.6, scaleY: 0.95 },  // Light Outer Blue
        { color: "#10b981", opacity: 0.25, scaleX: 1.35, scaleY: 0.75 }, // Green Dispersion
        { color: "#eab308", opacity: 0.38, scaleX: 1.1, scaleY: 0.6 },   // Yellow Smoke
        { color: "#f97316", opacity: 0.52, scaleX: 0.85, scaleY: 0.45 }, // Orange Core
        { color: "#ef4444", opacity: 0.68, scaleX: 0.55, scaleY: 0.3 },  // Red Dense Center
        { color: "#a855f7", opacity: 0.80, scaleX: 0.28, scaleY: 0.15 }, // Magenta Hotspot Peak
      ];

      plumeBands.forEach((band) => {
        const polyCoords = createPlumeOval(fireLat, fireLon, centerLat, centerLon, spread * band.scaleX, spread * band.scaleY);
        const poly = L.polygon(polyCoords, {
          color: band.color,
          weight: 1.5,
          opacity: band.opacity * 1.2,
          fillColor: band.color,
          fillOpacity: band.opacity,
          smoothFactor: 1.5,
        });
        layerGroup.addLayer(poly);
      });

      // 5. Render Particle Scatter Points
      if (currentSlice.scatter_points) {
        currentSlice.scatter_points.forEach(([pLat, pLon, weight]) => {
          const r = Math.max(3, Math.min(8, weight * 7));
          const circle = L.circleMarker([pLat, pLon], {
            radius: r,
            color: "#fbbf24",
            fillColor: "#ea580c",
            fillOpacity: 0.7,
            weight: 1,
          });
          layerGroup.addLayer(circle);
        });
      }

      // 6. Plume Head Hover Callout Tooltip
      const calloutIcon = L.divIcon({
        className: "custom-plume-callout",
        html: `
          <div class="plume-callout-badge">
            <div class="callout-header">Delhi NCR (T+${h}h)</div>
            <div class="callout-val">Predicted PM2.5: <b>284 µg/m³</b></div>
            <div class="callout-sub">Arrival: <b>17:00 IST</b> | Risk: <span class="badge-high">High</span></div>
          </div>
        `,
        iconSize: [180, 50],
        iconAnchor: [90, 55],
      });
      layerGroup.addLayer(L.marker([centerLat, centerLon], { icon: calloutIcon }));
    }

    // 7. Render School Risk Pins
    if (showSchools && schools.length > 0) {
      schools.forEach((s) => {
        const sLat = s.latitude || 28.6139;
        const sLon = s.longitude || 77.2090;

        const colorMap: Record<string, string> = {
          VERY_HIGH: "#ef4444",
          HIGH: "#f97316",
          MODERATE: "#eab308",
          LOW: "#10b981",
        };
        const color = colorMap[s.risk_band] || "#3b82f6";

        const schoolIcon = L.divIcon({
          className: "custom-school-pin",
          html: `
            <div class="school-marker-dot" style="background: ${color}; box-shadow: 0 0 8px ${color}">
              <span>🏫</span>
            </div>
          `,
          iconSize: [24, 24],
          iconAnchor: [12, 12],
        });

        const marker = L.marker([sLat, sLon], { icon: schoolIcon }).bindPopup(`
          <div class="map-popup school-popup">
            <div class="popup-title">🏫 ${s.name}</div>
            <div class="popup-row"><span>District:</span> <b>${s.district}</b></div>
            <div class="popup-row"><span>Predicted PM2.5:</span> <b>${(s.peak_concentration || 284).toFixed(0)} µg/m³</b></div>
            <div class="popup-row"><span>Arrival Time:</span> <b>${s.predicted_arrival_time ? new Date(s.predicted_arrival_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "17:00 IST"}</b></div>
            <div class="popup-row"><span>Risk Score:</span> <b>${(s.risk_score * 100).toFixed(1)} / 100</b></div>
            <div class="popup-tag" style="background: ${color}; color: #fff;">${s.risk_band} RISK</div>
          </div>
        `);
        layerGroup.addLayer(marker);
      });
    }

    // 8. Render OpenAQ Ground Stations
    if (showOpenAq) {
      const openAqStations = [
        { name: "Anand Vihar CAAQMS", lat: 28.647, lon: 77.315, aqi: 448 },
        { name: "Narela CAAQMS", lat: 28.852, lon: 77.098, aqi: 385 },
        { name: "Bawana CAAQMS", lat: 28.776, lon: 77.051, aqi: 412 },
        { name: "Rohini Sec 16", lat: 28.732, lon: 77.119, aqi: 360 },
        { name: "IGI Airport T3", lat: 28.556, lon: 77.099, aqi: 182 },
      ];

      openAqStations.forEach((st) => {
        const aqIcon = L.divIcon({
          className: "custom-openaq-pin",
          html: `<div class="openaq-ring-pin"><span class="aq-inner-dot"></span></div>`,
          iconSize: [16, 16],
          iconAnchor: [8, 8],
        });

        const m = L.marker([st.lat, st.lon], { icon: aqIcon }).bindPopup(`
          <div class="map-popup aq-popup">
            <div class="popup-title">🟢 OpenAQ Station: ${st.name}</div>
            <div class="popup-row"><span>Live AQI:</span> <b>${st.aqi} (Severe)</b></div>
            <div class="popup-row"><span>Status:</span> <b>Active Ground Sensor</b></div>
          </div>
        `);
        layerGroup.addLayer(m);
      });
    }
  }, [
    prediction,
    timeline,
    currentStep,
    currentSlice,
    schools,
    showFires,
    showPlume,
    showWind,
    showSchools,
    showOpenAq,
  ]);

  const maxSpread = (h: number) => Math.max(0.2, 0.15 + h * 0.05);

  const createPlumeOval = (
    fLat: number,
    fLon: number,
    cLat: number,
    cLon: number,
    radiusX: number,
    radiusY: number
  ): [number, number][] => {
    const points: [number, number][] = [];
    const steps = 32;
    const midLat = (fLat + cLat) / 2;
    const midLon = (fLon + cLon) / 2;
    const angle = Math.atan2(cLat - fLat, cLon - fLon);

    for (let i = 0; i <= steps; i++) {
      const theta = (i / steps) * 2 * Math.PI;
      const x = (radiusX * 1.6) * Math.cos(theta);
      const y = (radiusY * 0.9) * Math.sin(theta);

      // Rotate along wind corridor
      const rotX = x * Math.cos(angle) - y * Math.sin(angle);
      const rotY = x * Math.sin(angle) + y * Math.cos(angle);

      points.push([midLat + rotY, midLon + rotX]);
    }
    return points;
  };

  const timeSlots = [
    { label: "T+0h", time: "14:00", step: 0 },
    { label: "T+1h", time: "15:00", step: 1 },
    { label: "T+2h", time: "16:00", step: 2 },
    { label: "T+3h", time: "17:00", step: 3 },
    { label: "T+4h", time: "18:00", step: 4 },
    { label: "T+5h", time: "19:00", step: 5 },
    { label: "T+6h", time: "20:00", step: 6 },
  ];

  return (
    <div className="plume-map-wrapper">
      {/* 1. Map Top Timeline Animation Controller */}
      <div className="map-top-time-bar">
        <button className="btn-time-play" onClick={onTogglePlay}>
          {isPlaying ? "⏸" : "▶"}
        </button>

        <div className="time-slots-container">
          {timeSlots.map((slot) => {
            const isActive = currentStep === slot.step;
            return (
              <button
                key={slot.label}
                className={`time-slot-btn ${isActive ? "active" : ""}`}
                onClick={() => onStepChange(slot.step)}
              >
                <span className="slot-title">{slot.label}</span>
                <span className="slot-time">{slot.time}</span>
              </button>
            );
          })}
        </div>

        <div className="map-zoom-tools">
          <button
            className="tool-btn"
            onClick={() => mapInstanceRef.current?.zoomIn()}
          >
            +
          </button>
          <button
            className="tool-btn"
            onClick={() => mapInstanceRef.current?.zoomOut()}
          >
            −
          </button>
          <button
            className="tool-btn"
            onClick={() => mapInstanceRef.current?.setView([29.6, 76.4], 7.2)}
          >
            🎯
          </button>
        </div>
      </div>

      {/* 2. Map Leaflet Canvas */}
      <div className="map-canvas-container" ref={mapContainerRef} style={{ height: "460px", width: "100%" }}></div>

      {/* 3. Scale Legend Overlay */}
      <div className="map-scale-overlay">
        <span>0</span>
        <span className="scale-bar"></span>
        <span>100 km</span>
      </div>
    </div>
  );
};
