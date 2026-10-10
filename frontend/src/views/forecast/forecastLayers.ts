import L from "leaflet";
import { PredictiveOutput, SchoolRiskAssessment, TimelineSlice } from "../../api/types";
import { fireIcon, popupContent, schoolLabel } from "../../map/baseMap";

export interface LayerVisibility {
  smoke: boolean;
  particles: boolean;
  tracks: boolean;
  fires: boolean;
  schools: boolean;
}

/** Sequential smoke palette (presentation only; thresholds come from the payload). */
export const SMOKE_LEVELS: Record<string, { color: string; fill: number; stroke: number; label: string }> = {
  trace: { color: "#f1dc96", fill: 0.16, stroke: 0.55, label: "WHO guideline" },
  fringe: { color: "#f6b23e", fill: 0.3, stroke: 0.8, label: "Impact" },
  dispersing: { color: "#ef7a2c", fill: 0.42, stroke: 0.9, label: "Very poor" },
  core: { color: "#dc3b42", fill: 0.55, stroke: 1, label: "Severe" },
};

export const RISK_COLORS: Record<string, string> = {
  LOW: "#64748b",
  MODERATE: "#f6b23e",
  HIGH: "#ef7a2c",
  VERY_HIGH: "#e5484d",
};

export function hoursAfter(t0: string, iso: string) {
  return (new Date(iso).getTime() - new Date(t0).getTime()) / 3.6e6;
}

// One canvas renderer per pane per map, reused across redraws (a renderer draws into its own pane).
const renderers = new WeakMap<L.Map, { smoke: L.Canvas; schools: L.Canvas }>();
function renderersFor(map: L.Map) {
  let r = renderers.get(map);
  if (!r) {
    r = { smoke: L.canvas({ pane: "smoke", padding: 0.3 }), schools: L.canvas({ pane: "schools", padding: 0.3 }) };
    renderers.set(map, r);
  }
  return r;
}

interface DrawArgs {
  map: L.Map;
  group: L.LayerGroup;
  prediction: PredictiveOutput;
  slice: TimelineSlice | null;
  layers: LayerVisibility;
  smokeOpacity: number;
  zoom: number;
  theme: "light" | "dark";
  selectedSchoolId: string | null;
  onSelectSchool: (id: string) => void;
}

/** Draws one timeline slice. Returns school markers keyed by id (for fly-to / popups). */
export function drawForecast({
  map,
  group,
  prediction,
  slice,
  layers,
  smokeOpacity,
  zoom,
  theme,
  selectedSchoolId,
  onSelectSchool,
}: DrawArgs): Map<string, L.CircleMarker> {
  group.clearLayers();
  const schoolMarkers = new Map<string, L.CircleMarker>();
  const { smoke: renderer, schools: schoolRenderer } = renderersFor(map);
  // Colours that read on the active basemap
  const ink = theme === "light"
    ? { particle: "#334155", track: "#4338ca", schoolRing: "#1f2937" }
    : { particle: "#e3e8f0", track: "#c7d2fe", schoolRing: "#ffffff" };

  // 1. Smoke density levels, outermost first, below map labels
  if (layers.smoke && slice?.heatmap_levels) {
    for (const level of [...slice.heatmap_levels].reverse()) {
      const base = SMOKE_LEVELS[level.level] ?? { color: level.color, fill: 0.2, stroke: 0.6, label: level.level };
      // Light street maps need denser fills and a deeper tone for the faintest level
      const style = theme === "light"
        ? { ...base, color: level.level === "trace" ? "#d9a514" : base.color, fill: Math.min(0.7, base.fill * 1.6), stroke: 1 }
        : base;
      const rings = level.polygons ?? (level.coordinates.length ? [level.coordinates] : []);
      for (const ring of rings) {
        const poly = L.polygon(
          ring.map((c) => [c[1], c[0]] as [number, number]),
          {
            pane: "smoke",
            renderer,
            color: style.color,
            weight: theme === "light" ? 1.75 : level.level === "trace" ? 1 : 1.25,
            opacity: style.stroke * smokeOpacity,
            fillColor: style.color,
            fillOpacity: style.fill * smokeOpacity,
            smoothFactor: 1,
          },
        ).bindTooltip(
          `Smoke PM2.5 ≥ ${level.threshold_ugm3 ?? "?"} µg/m³ · ${style.label} · ${level.area_sq_km ?? "?"} km²`,
          { sticky: true, className: "map-tip", direction: "top" },
        );
        group.addLayer(poly);
      }
    }
  }

  // 2. Per-cluster centroid tracks
  const corridor = slice?.corridor_geojson;
  if (layers.tracks && corridor?.coordinates) {
    const lines: number[][][] = corridor.type === "MultiLineString" ? corridor.coordinates : [corridor.coordinates];
    for (const line of lines) {
      if (line.length < 2) continue;
      group.addLayer(
        L.polyline(line.map((c) => [c[1], c[0]] as [number, number]), {
          pane: "smoke",
          renderer,
          color: ink.track,
          weight: 1.5,
          opacity: 0.65,
          dashArray: "3 5",
          interactive: false,
        }),
      );
    }
  }

  // 3. Particles: real model particles, sized gently with zoom
  if (layers.particles && slice?.scatter_points) {
    const base = Math.max(0.8, Math.min(2.6, 0.4 + (zoom - 5) * 0.4));
    for (const [lat, lon, w] of slice.scatter_points) {
      group.addLayer(
        L.circleMarker([lat, lon], {
          pane: "smoke",
          renderer,
          radius: base + w * 1.2,
          stroke: false,
          fillColor: ink.particle,
          fillOpacity: (0.16 + w * 0.24) * smokeOpacity,
          interactive: false,
        }),
      );
    }
  }

  // 4. Fire clusters
  if (layers.fires) {
    for (const f of prediction.map_geojson?.features ?? []) {
      if (f.properties?.layer_type !== "fire_source") continue;
      const [lon, lat] = f.geometry.coordinates;
      const p = f.properties;
      const size = Math.max(9, Math.min(20, 7 + Math.sqrt(p.total_frp_mw) * 1.6));
      group.addLayer(
        L.marker([lat, lon], { icon: fireIcon(size), pane: "points", keyboard: false }).bindPopup(
          popupContent("Fire cluster", [
            ["Detections", `${p.hotspot_count} (VIIRS)`],
            ["Fire radiative power", `${p.total_frp_mw.toFixed(1)} MW`],
            ["Location", `${lat.toFixed(3)}°N, ${lon.toFixed(3)}°E`],
          ]),
        ),
      );
    }
  }

  // 5. Schools: always drawn; size grows with zoom, reached schools stand out
  if (layers.schools) {
    const t0 = prediction.valid_from;
    for (const s of prediction.schools as SchoolRiskAssessment[]) {
      if (s.latitude === undefined || s.longitude === undefined) continue;
      const impacted = s.impact_probability > 0;
      const selected = s.school_id === selectedSchoolId;
      const color = RISK_COLORS[s.risk_band] ?? RISK_COLORS.LOW;
      const arrival = s.predicted_arrival_time ? `+${hoursAfter(t0, s.predicted_arrival_time).toFixed(1)} h after T0` : "Not within 9 h";
      const m = L.circleMarker([s.latitude, s.longitude], {
        pane: "schools",
        renderer: schoolRenderer,
        radius: selected ? 8 : impacted ? (zoom < 7 ? 4.5 : 6) : zoom < 7 ? 2.5 : zoom < 9 ? 3.5 : 4.5,
        color: selected || impacted ? ink.schoolRing : color,
        weight: selected ? 2.5 : impacted ? 1.25 : 0.5,
        fillColor: color,
        fillOpacity: impacted || selected ? 0.95 : 0.6,
      })
        .bindTooltip(`${schoolLabel(s.name).label} · ${s.peak_concentration.toFixed(0)} µg/m³`, { className: "map-tip", direction: "top", offset: [0, -6] })
        .bindPopup(
          popupContent(schoolLabel(s.name).label, [
            ["Peak smoke PM2.5", `${s.peak_concentration.toFixed(1)} µg/m³`],
            ["Ensemble probability", `${Math.round(s.impact_probability * 100)}%`],
            ["Arrival", arrival],
            ["Risk band", s.risk_band.replace("_", " ")],
            ["Nearest fire cluster", `${s.distance_to_fire_km.toFixed(1)} km`],
            ...(schoolLabel(s.name).detail ? [["Source", schoolLabel(s.name).detail!] as [string, string]] : []),
          ]),
        )
        .on("click", () => onSelectSchool(s.school_id));
      group.addLayer(m);
      schoolMarkers.set(s.school_id, m);
    }
  }

  return schoolMarkers;
}

/** Bounds of everything the run produced: fires, all particles over all hours, impacted schools. */
export function runBounds(prediction: PredictiveOutput): L.LatLngBounds | null {
  const pts: [number, number][] = [];
  for (const f of prediction.map_geojson?.features ?? []) {
    if (f.properties?.layer_type === "fire_source") pts.push([f.geometry.coordinates[1], f.geometry.coordinates[0]]);
  }
  for (const sl of prediction.timeline) for (const [lat, lon] of sl.scatter_points ?? []) pts.push([lat, lon]);
  for (const s of prediction.schools) {
    if (s.impact_probability > 0 && s.latitude !== undefined && s.longitude !== undefined) pts.push([s.latitude, s.longitude]);
  }
  return pts.length ? L.latLngBounds(pts) : null;
}
