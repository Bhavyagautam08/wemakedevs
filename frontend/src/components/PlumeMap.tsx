import React, { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { PredictiveOutput, TimelineSlice, SchoolRiskAssessment } from "../api/types";

// Fix standard Leaflet default icon issues in bundled React
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
  currentSlice: TimelineSlice | null;
  schools: SchoolRiskAssessment[];
  currentStep: number;
  onSelectHorizon?: (hours: number) => void;
}

export const PlumeMap: React.FC<PlumeMapProps> = ({
  prediction,
  currentSlice,
  schools,
  currentStep,
  onSelectHorizon,
}) => {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const layerGroupRef = useRef<L.LayerGroup | null>(null);

  // Layer visibility toggles
  const [showHeatmap, setShowHeatmap] = useState(true);
  const [showScatter, setShowScatter] = useState(true);
  const [showSchools, setShowSchools] = useState(true);
  const [showCorridor, setShowCorridor] = useState(true);
  const [showHotspots, setShowHotspots] = useState(true);

  // Initialize Map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    // Center on Northern India / Delhi-NCR (Punjab to Delhi corridor)
    const initialCenter: [number, number] = [29.5, 76.5];
    const map = L.map(mapContainerRef.current, {
      center: initialCenter,
      zoom: 7.5,
      zoomControl: true,
      minZoom: 5,
      maxZoom: 16,
    });

    // Dark-themed CartoDB tile layer for high-contrast smoke visualization
    L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
      {
        attribution: '&copy; <a href="https://carto.com/">CARTO</a> &copy; OpenStreetMap contributors',
        subdomains: "abcd",
        maxZoom: 19,
      }
    ).addTo(map);

    const layerGroup = L.layerGroup().addTo(map);
    mapInstanceRef.current = map;
    layerGroupRef.current = layerGroup;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
      layerGroupRef.current = null;
    };
  }, []);

  // Update Layers on Data or Timeline Slice Change
  useEffect(() => {
    const map = mapInstanceRef.current;
    const layerGroup = layerGroupRef.current;
    if (!map || !layerGroup) return;

    layerGroup.clearLayers();

    const fireLat = prediction?.fire.latitude || 30.2338;
    const fireLon = prediction?.fire.longitude || 75.8270;
    const frp = prediction?.fire.total_frp_mw || 1023.1;
    const hotspotCount = prediction?.fire.hotspot_count || 4;

    // 1. Render NASA FIRMS Fire Origin Marker
    if (showHotspots) {
      const fireIcon = L.divIcon({
        className: "custom-fire-marker",
        html: `
          <div class="fire-pulse-pin">
            <span class="fire-emoji">🔥</span>
            <span class="fire-ripple"></span>
          </div>
        `,
        iconSize: [36, 36],
        iconAnchor: [18, 18],
      });

      const fireMarker = L.marker([fireLat, fireLon], { icon: fireIcon }).bindPopup(`
        <div class="map-popup fire-popup">
          <div class="popup-title">🔥 NASA FIRMS Active Fire Complex</div>
          <div class="popup-row"><span>Source Strength:</span> <b>${frp.toFixed(0)} MW (FRP)</b></div>
          <div class="popup-row"><span>Satellite Clusters:</span> <b>${hotspotCount} Hotspots (VIIRS)</b></div>
          <div class="popup-row"><span>Location:</span> <b>${fireLat.toFixed(3)}°N, ${fireLon.toFixed(3)}°E</b></div>
          <div class="popup-tag">Primary Emission Origin</div>
        </div>
      `);
      layerGroup.addLayer(fireMarker);
    }

    // 2. Render Trajectory Corridor Track
    if (showCorridor && currentSlice?.corridor_geojson?.coordinates) {
      const lineCoords: [number, number][] = currentSlice.corridor_geojson.coordinates.map(
        (c: number[]) => [c[1], c[0]]
      );
      const corridorLine = L.polyline(lineCoords, {
        color: "#6366f1",
        weight: 3,
        dashArray: "6, 8",
        opacity: 0.85,
      }).bindTooltip("Estimated 2D Advection Centerline", { sticky: true });
      layerGroup.addLayer(corridorLine);
    }

    // 3. Render Multi-Level Plume Heatmap Contours
    if (showHeatmap && currentSlice) {
      if (currentSlice.heatmap_levels && currentSlice.heatmap_levels.length > 0) {
        // Render from outermost fringe to core
        [...currentSlice.heatmap_levels].reverse().forEach((level) => {
          const latLngs: [number, number][] = level.coordinates.map((coord: number[]) => [
            coord[1],
            coord[0],
          ]);

          const opacity =
            level.level === "core" ? 0.65 : level.level === "dispersing" ? 0.45 : 0.25;
          const fillOpacity =
            level.level === "core" ? 0.45 : level.level === "dispersing" ? 0.28 : 0.15;

          const poly = L.polygon(latLngs, {
            color: level.color,
            weight: 2,
            opacity,
            fillColor: level.color,
            fillOpacity,
            smoothFactor: 1.5,
          }).bindPopup(`
            <div class="map-popup plume-popup">
              <div class="popup-title">🌫️ Smoke Plume (${level.level.toUpperCase()})</div>
              <div class="popup-row"><span>Forecast Horizon:</span> <b>T+${currentSlice.horizon_offset_hours} Hours</b></div>
              <div class="popup-row"><span>Plume Footprint:</span> <b>${Math.round(currentSlice.plume_area_sq_km)} km²</b></div>
              <div class="popup-row"><span>Max Intensity:</span> <b>${(currentSlice.max_intensity * 100).toFixed(0)}%</b></div>
              <div class="popup-tag" style="background: ${level.color}; color: #fff;">${level.intensity.toUpperCase()} DENSITY</div>
            </div>
          `);
          layerGroup.addLayer(poly);
        });
      } else if (currentSlice.contour_geojson?.coordinates) {
        // Fallback polygon
        const latLngs: [number, number][] = currentSlice.contour_geojson.coordinates[0].map(
          (c: number[]) => [c[1], c[0]]
        );
        const poly = L.polygon(latLngs, {
          color: "#f97316",
          weight: 2,
          fillColor: "#f97316",
          fillOpacity: 0.35,
        });
        layerGroup.addLayer(poly);
      }
    }

    // 4. Render Particle Scatter Cloud
    if (showScatter && currentSlice?.scatter_points) {
      currentSlice.scatter_points.forEach(([lat, lon, weight]) => {
        const radius = Math.max(3, Math.min(8, weight * 7));
        const circle = L.circleMarker([lat, lon], {
          radius,
          color: "#ea580c",
          fillColor: "#fbbf24",
          fillOpacity: 0.65,
          weight: 1,
        }).bindTooltip(`Particle Intensity: ${(weight * 100).toFixed(0)}%`, {
          direction: "top",
          opacity: 0.85,
        });
        layerGroup.addLayer(circle);
      });
    }

    // 5. Render School Risk Markers
    if (showSchools) {
      schools.forEach((s) => {
        const lat = s.latitude || 28.6139;
        const lon = s.longitude || 77.2090;

        const colorMap: Record<string, string> = {
          VERY_HIGH: "#ef4444",
          HIGH: "#f97316",
          MODERATE: "#eab308",
          LOW: "#10b981",
        };
        const color = colorMap[s.risk_band] || "#3b82f6";

        const schoolIcon = L.divIcon({
          className: "custom-school-marker",
          html: `
            <div class="school-pin-badge" style="background-color: ${color};">
              <span class="school-emoji">🏫</span>
            </div>
          `,
          iconSize: [28, 28],
          iconAnchor: [14, 14],
        });

        const arrivalText = s.predicted_arrival_time
          ? new Date(s.predicted_arrival_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
          : "No Direct Pulse";

        const schoolMarker = L.marker([lat, lon], { icon: schoolIcon }).bindPopup(`
          <div class="map-popup school-popup">
            <div class="popup-title">🏫 ${s.name}</div>
            <div class="popup-row"><span>District:</span> <b>${s.district}</b></div>
            <div class="popup-row"><span>Risk Score:</span> <b>${(s.risk_score * 100).toFixed(1)} / 100</b></div>
            <div class="popup-row"><span>Impact Probability:</span> <b>${(s.impact_probability * 100).toFixed(0)}%</b></div>
            <div class="popup-row"><span>Predicted Arrival:</span> <b>${arrivalText}</b></div>
            <div class="popup-tag" style="background: ${color}; color: #fff;">${s.risk_band} RISK</div>
          </div>
        `);
        layerGroup.addLayer(schoolMarker);
      });
    }
  }, [
    prediction,
    currentSlice,
    schools,
    currentStep,
    showHeatmap,
    showScatter,
    showSchools,
    showCorridor,
    showHotspots,
  ]);

  const windSpeedKmh = prediction?.weather ? Math.round(prediction.weather.wind_speed_mps * 3.6) : 17;
  const windDirDeg = prediction?.weather ? Math.round(prediction.weather.wind_direction_deg) : 315;

  return (
    <div className="plume-map-wrapper">
      {/* Map Header Controls */}
      <div className="map-toolbar">
        <div className="toolbar-left">
          <div className="map-badge">
            <span className="live-pulse"></span>
            <b>Interactive Lagrangian Smoke Corridor Map</b>
          </div>

          {/* Quick Horizon Buttons */}
          <div className="horizon-pills">
            {[0, 3, 6, 12, 24].map((h) => {
              const isActive = currentSlice?.horizon_offset_hours === h;
              return (
                <button
                  key={h}
                  className={`horizon-btn ${isActive ? "active" : ""}`}
                  onClick={() => onSelectHorizon && onSelectHorizon(h)}
                >
                  {h === 0 ? "Current (T+0)" : `+${h} Hours`}
                </button>
              );
            })}
          </div>
        </div>

        {/* Layer Visibility Toggles */}
        <div className="layer-toggles">
          <label className="toggle-chip">
            <input
              type="checkbox"
              checked={showHotspots}
              onChange={(e) => setShowHotspots(e.target.checked)}
            />
            🔥 Fires
          </label>
          <label className="toggle-chip">
            <input
              type="checkbox"
              checked={showHeatmap}
              onChange={(e) => setShowHeatmap(e.target.checked)}
            />
            🌫️ Plume Heatmap
          </label>
          <label className="toggle-chip">
            <input
              type="checkbox"
              checked={showScatter}
              onChange={(e) => setShowScatter(e.target.checked)}
            />
            ✨ Particle Scatter
          </label>
          <label className="toggle-chip">
            <input
              type="checkbox"
              checked={showCorridor}
              onChange={(e) => setShowCorridor(e.target.checked)}
            />
            🛤️ Corridor Track
          </label>
          <label className="toggle-chip">
            <input
              type="checkbox"
              checked={showSchools}
              onChange={(e) => setShowSchools(e.target.checked)}
            />
            🏫 School Pins
          </label>
        </div>
      </div>

      {/* Map Leaflet Container */}
      <div className="map-canvas-container" ref={mapContainerRef} style={{ height: "460px", width: "100%" }}></div>

      {/* Floating Map Legend & Atmospheric Telemetry */}
      <div className="map-telemetry-overlay">
        <div className="telemetry-card">
          <div className="telemetry-item">
            <span className="label">Forecast Horizon:</span>
            <span className="value highlight">T+{currentSlice?.horizon_offset_hours || 0}h</span>
          </div>
          <div className="telemetry-item">
            <span className="label">Plume Footprint:</span>
            <span className="value">{Math.round(currentSlice?.plume_area_sq_km || 150)} km²</span>
          </div>
          <div className="telemetry-item">
            <span className="label">Wind Vector:</span>
            <span className="value">
              {windSpeedKmh} km/h @ {windDirDeg}° (NW)
            </span>
          </div>
          <div className="telemetry-item">
            <span className="label">Impacted Schools:</span>
            <span className="value text-warning">
              {currentSlice?.affected_schools_count || 0} / {schools.length}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
