"""
Layer 1 Predictive Pipeline Runner
Orchestrates raw data ingestion, fire source estimation, 2D Lagrangian ensemble advection,
school risk scoring, map GeoJSON synthesis, and timeline slice generation.
"""

import math
from typing import List, Dict, Any, Optional, Callable, Tuple
from datetime import datetime, timedelta, timezone
import numpy as np
from src.types import (
    Hotspot,
    WeatherObservation,
    School,
    SchoolRiskAssessment,
    PredictiveOutput,
    TimelineSlice,
)
from src.config import Config, DEFAULT_CONFIG
from src.layer1_predictive.coordinates import LocalMetricProjection
from src.layer1_predictive.fire_source import FireSourceModel
from src.layer1_predictive.lagrangian_engine import LagrangianTransportEngine, ParticleState
from src.layer1_predictive.weather_field import WeatherVectorField
from src.layer1_predictive.diffusion_field import GaussianDiffusionField
from src.layer1_predictive.ensemble import ScenarioEnsembleRunner
from src.layer1_predictive.school_scorer import SchoolRiskScorer


class Layer1PredictivePipeline:
    """
    Executes the entire physics & predictive workflow.
    """

    # Heatmap levels: (name, intensity, colour, SimulationConfig threshold field in ug/m^3)
    HEATMAP_LEVELS = [
        ("core", "high", "#ef4444", "severe_threshold_ugm3"),
        ("dispersing", "moderate", "#f97316", "very_poor_threshold_ugm3"),
        ("fringe", "low", "#eab308", "impact_threshold_ugm3"),
        ("trace", "trace", "#38bdf8", "trace_threshold_ugm3"),
    ]
    MAX_SCATTER_POINTS = 600

    def __init__(self, config: Config = None):
        self.config = config or DEFAULT_CONFIG
        self.projection = LocalMetricProjection(
            origin_lat=self.config.projection.origin_lat,
            origin_lon=self.config.projection.origin_lon,
        )
        self.source_model = FireSourceModel(projection=self.projection, config=self.config.simulation)
        self.engine = LagrangianTransportEngine(
            config=self.config.simulation,
            projection=self.projection,
        )
        self.diffusion = GaussianDiffusionField(projection=self.projection, config=self.config.simulation)
        self.ensemble = ScenarioEnsembleRunner(
            engine=self.engine,
            diffusion_field=self.diffusion,
            members_config=self.config.ensemble_members,
        )
        self.scorer = SchoolRiskScorer(
            weights=self.config.risk_weights,
            projection=self.projection,
        )

    def run(
        self,
        hotspots: List[Hotspot],
        weather: List[WeatherObservation],
        schools: Optional[List[School]] = None,
        run_timestamp: Optional[datetime] = None,
        school_provider: Optional[Callable[[List[Tuple[float, float, float, float]]], List[School]]] = None,
    ) -> PredictiveOutput:
        """
        Executes end-to-end forward simulation.
        Schools: if `schools` is given they are scored as-is. Otherwise the plume footprint
        (grid cells >= impact threshold for any member at any hour) is turned into search
        areas and `school_provider(bboxes)` (e.g. OpenStreetMap) supplies the schools there.
        """
        generated_at = datetime.now(timezone.utc)
        now = run_timestamp or generated_at  # simulation T0
        prediction_id = f"pred_{generated_at.strftime('%Y%m%d_%H%M%S%f')}_delhincr"
        sim = self.config.simulation

        # Fail-Safe Verification
        if not weather:
            raise ValueError("INSUFFICIENT_DATA: Weather observation vectors unavailable.")
        if not hotspots:
            raise ValueError("INSUFFICIENT_DATA: Active fire observation data unavailable.")

        # 1. Fire Clustering & Source Strength Estimation
        clusters = self.source_model.cluster_hotspots(hotspots, current_time=now)
        if not clusters:
            raise ValueError("INSUFFICIENT_DATA: Hotspots produced no fire clusters.")
        primary_fire = clusters[0]

        # 2. Run Scenario Ensemble: one continuous run, snapshotted every hour
        snapshots, ensemble_output = self.ensemble.run_ensemble(
            fires=clusters,
            weather_obs=weather,
            start_time=now,
            horizon_hours=sim.horizon_hours,
            dt_seconds=sim.timestep_seconds,
        )
        nominal_idx = self._nominal_member_index()

        # 3. Schools: explicit list, or every school inside the plume footprint
        footprint_cells = set()
        for h in snapshots:
            for st in snapshots[h]:
                # Search schools wherever smoke reaches the WHO guideline level, so low-exposure
                # schools are listed with their real values (impact itself still uses the 50 ug/m3 threshold)
                footprint_cells |= self.diffusion.impact_cells(st, sim.trace_threshold_ugm3)
        search_areas = self.diffusion.cells_to_bboxes(footprint_cells)
        if schools is not None:
            school_source = "caller_supplied"
        else:
            if school_provider is None:
                raise ValueError("CONFIG_ERROR: no schools and no school_provider supplied.")
            schools = school_provider(search_areas) if search_areas else []
            school_source = "openstreetmap_overpass_in_plume_footprint"

        assessed_schools = self.scorer.assess_schools(
            schools=schools,
            fires=clusters,
            ensemble_runner=self.ensemble,
            snapshots=snapshots,
            sim_start_time=now,
            threshold=sim.impact_threshold_ugm3,
            normalisation_ugm3=sim.severe_threshold_ugm3,
        )

        # 4. Timeline slices derived from the nominal member's real particle snapshots
        timeline_slices = self._generate_timeline_slices(
            now=now,
            snapshots=snapshots,
            member_index=nominal_idx,
            assessed_schools=assessed_schools,
        )

        # 5. Synthesize Map-Ready GeoJSON
        map_geojson = self._synthesize_map_geojson(
            clusters=clusters,
            ensemble_output=ensemble_output,
            assessed_schools=assessed_schools,
        )

        # 6. Weather actually used: interpolated at run start and at each reported horizon
        wf = WeatherVectorField(weather, start_time=now, projection=self.projection, config=sim)
        weather_at = []
        for h in [0] + sim.forecast_horizons:
            t = h * 3600.0
            blh, _, _ = wf.get_blh_and_diffusivity(t)
            # Station means (the field itself varies in space; see weather.stations)
            u = float(np.mean(wf._station_values("u", t)))
            v = float(np.mean(wf._station_values("v", t)))
            weather_at.append({
                "horizon_hours": h,
                "u_mps": round(u, 3),
                "v_mps": round(v, 3),
                "wind_speed_mps": round(math.hypot(u, v), 3),
                "wind_direction_deg": round((math.degrees(math.atan2(-u, -v)) + 360.0) % 360.0, 1),
                "boundary_layer_height_m": round(blh, 1),
                "precipitation_mm": round(wf.get_precipitation(t), 2),
            })
        w0 = weather_at[0]

        # Per-horizon chained-state summaries (nominal member) for audit/verification
        horizon_states = []
        for h in sim.forecast_horizons:
            st = snapshots[h][nominal_idx]
            entry = {
                "horizon_hours": h,
                "particle_count": len(st),
                "total_mass_kg": round(float(np.sum(st.mass)) / 1e9, 3),
                "mixing_height_m": round(float(np.average(np.broadcast_to(st.mixing_height_m, st.x.shape), weights=st.mass)), 1)
                if len(st) else None,
            }
            if len(st) > 0:
                cx, cy = st.centroid()
                clat, clon = self.projection.to_wgs84(np.array([cx]), np.array([cy]))
                entry.update({"centroid_lat": round(float(clat[0]), 4), "centroid_lon": round(float(clon[0]), 4)})
            horizon_states.append(entry)

        # 7. Assemble Standardized Predictive Output Object
        valid_until = now + timedelta(hours=sim.horizon_hours)

        output = PredictiveOutput(
            prediction_id=prediction_id,
            generated_at=generated_at,
            valid_from=now,
            valid_until=valid_until,
            model={
                "type": "lagrangian_smoke_transport_2d",
                "version": "1.2.0",
                "mode": "physics_only",
            },
            fire={
                "fire_id": primary_fire.fire_id,
                "latitude": primary_fire.centroid_lat,
                "longitude": primary_fire.centroid_lon,
                "hotspot_count": primary_fire.hotspot_count,
                "total_frp_mw": primary_fire.frp_summary,
                "source_strength": primary_fire.source_strength,
                "emission_rate_kg_s": primary_fire.emission_rate_kg_s,
                "source_freshness_hours": primary_fire.source_freshness_hours,
                "status": primary_fire.status,
            },
            weather={
                "wind_speed_mps": w0["wind_speed_mps"],
                "wind_direction_deg": w0["wind_direction_deg"],
                "u_mps": w0["u_mps"],
                "v_mps": w0["v_mps"],
                "boundary_layer_height_m": w0["boundary_layer_height_m"],
                "observation_count": len(weather),
                "station_count": wf.station_count,
                "stations": [[s["lat"], s["lon"]] for s in wf.stations if s["lat"] is not None],
                "spatial_interpolation": "inverse-distance (p=2) between stations" if wf.station_count > 1 else "uniform",
                "at_horizons": weather_at,
            },
            simulation={
                "timestep_seconds": sim.timestep_seconds,
                "horizon_hours": sim.horizon_hours,
                "forecast_horizons": sim.forecast_horizons,
                "particle_count": len(snapshots[sim.horizon_hours][nominal_idx]),
                "diffusion_kx": sim.base_diffusion_kx,
                "diffusion_ky": sim.base_diffusion_ky,
                "decay_rate": sim.decay_rate_lambda,
                "fire_cluster_count": len(clusters),
                "total_emission_rate_kg_s": round(sum(c.emission_rate_kg_s for c in clusters), 3),
                "emission_coefficient_kg_per_mj": sim.smoke_emission_coefficient_kg_per_mj,
                "emission_duration_hours": sim.emission_duration_hours,
                "concentration_units": "ug/m3 PM2.5 smoke increment (2D box model)",
                "impact_threshold_ugm3": sim.impact_threshold_ugm3,
                "horizon_states": horizon_states,
                "school_source": school_source,
                "schools_assessed": len(assessed_schools),
                "footprint_area_sq_km": round(len(footprint_cells) * (self.diffusion.grid_res_m / 1000.0) ** 2, 1),
                "school_search_areas": [[round(v, 4) for v in b] for b in search_areas],
            },
            ensemble=ensemble_output,
            schools=assessed_schools,
            timeline=timeline_slices,
            map_geojson=map_geojson,
            provenance={
                "fire_source": hotspots[0].satellite,
                "weather_source": "Open-Meteo_GFS",
                "school_dataset": school_source,
                "policy_source": "CAQM_GRAP_Schedule_2025_11_21",
            },
        )

        return output

    def _nominal_member_index(self) -> int:
        """Index of the unperturbed ensemble member (all multipliers 1, no shift)."""
        for i, m in enumerate(self.config.ensemble_members):
            if (m.wind_speed_multiplier, m.wind_direction_shift_deg, m.diffusion_multiplier,
                    m.source_strength_multiplier, m.blh_multiplier) == (1.0, 0.0, 1.0, 1.0, 1.0):
                return i
        raise ValueError("CONFIG_ERROR: ensemble has no nominal (unperturbed) member to render.")

    def _generate_timeline_slices(
        self,
        now: datetime,
        snapshots: Dict[int, List[ParticleState]],
        member_index: int,
        assessed_schools: List[SchoolRiskAssessment],
    ) -> List[TimelineSlice]:
        """
        Builds one slice per simulated hour from the nominal member's particle snapshot:
        centre = mass-weighted centroid of all smoke, heatmap levels = one convex hull per
        connected blob of grid cells above the level, scatter = subsample of real particles
        weighted by mass, corridor = one centroid track per fire cluster (MultiLineString). Levels are absolute ug/m^3 thresholds from SimulationConfig;
        max_intensity = peak cell concentration / severe threshold, capped at 1.
        """
        slices = []
        tracks: Dict[int, List[List[float]]] = {}
        sim = self.config.simulation
        levels_cfg = [(n, i, c, getattr(sim, field)) for n, i, c, field in self.HEATMAP_LEVELS]

        for h in sorted(snapshots):
            st = snapshots[h][member_index]
            t_slice = now + timedelta(hours=h)
            aff_count = sum(
                1 for s in assessed_schools
                if s.predicted_arrival_time and s.predicted_arrival_time <= t_slice
            )

            if len(st) == 0:
                slices.append(TimelineSlice(
                    horizon_offset_hours=h, timestamp=t_slice, plume_center_lat=0.0, plume_center_lon=0.0,
                    plume_area_sq_km=0.0, affected_schools_count=aff_count, max_intensity=0.0,
                    contour_geojson={"type": "Polygon", "coordinates": []}, scatter_points=[],
                    heatmap_levels=[],
                    corridor_geojson={"type": "MultiLineString", "coordinates": [list(t) for t in tracks.values()]},
                ))
                continue

            cx, cy = st.centroid()
            clat, clon = self.projection.to_wgs84(np.array([cx]), np.array([cy]))
            center_lat, center_lon = round(float(clat[0]), 4), round(float(clon[0]), 4)
            for src in np.unique(st.source):
                sel = st.source == src
                w = st.mass[sel]
                tx, ty = float(np.sum(st.x[sel] * w) / np.sum(w)), float(np.sum(st.y[sel] * w) / np.sum(w))
                tlat, tlon = self.projection.to_wgs84(np.array([tx]), np.array([ty]))
                tracks.setdefault(int(src), []).append([round(float(tlon[0]), 4), round(float(tlat[0]), 4)])

            dens = self.diffusion.extract_density_levels(st, [(n, t) for n, _, _, t in levels_cfg])
            heatmap_levels = [
                {
                    "level": name,
                    "intensity": intensity,
                    "color": color,
                    "threshold_ugm3": thr,
                    "area_sq_km": dens["levels"][name]["area_sq_km"],
                    "polygons": dens["levels"][name]["polygons"],
                    "coordinates": dens["levels"][name]["polygons"][0] if dens["levels"][name]["polygons"] else [],
                }
                for name, intensity, color, thr in levels_cfg
            ]
            fringe = dens["levels"]["fringe"]

            stride = max(1, len(st) // self.MAX_SCATTER_POINTS)
            lats, lons = self.projection.to_wgs84(st.x[::stride], st.y[::stride])
            m = st.mass[::stride]
            m_max = float(np.max(m))
            scatter = [
                [round(float(la), 4), round(float(lo), 4), round(float(mm / m_max), 3)]
                for la, lo, mm in zip(lats, lons, m)
            ]

            slices.append(
                TimelineSlice(
                    horizon_offset_hours=h,
                    timestamp=t_slice,
                    plume_center_lat=center_lat,
                    plume_center_lon=center_lon,
                    plume_area_sq_km=fringe["area_sq_km"],
                    affected_schools_count=aff_count,
                    max_intensity=round(min(1.0, dens["peak_cell_ugm3"] / sim.severe_threshold_ugm3), 3),
                    peak_concentration_ugm3=dens["peak_cell_ugm3"],
                    particle_count=len(st),
                    contour_geojson={
                        "type": "MultiPolygon",
                        "coordinates": [[ring] for ring in fringe["polygons"]],
                    },
                    scatter_points=scatter,
                    heatmap_levels=heatmap_levels,
                    corridor_geojson={"type": "MultiLineString", "coordinates": [list(t) for t in tracks.values()]},
                )
            )
        return slices

    def _synthesize_map_geojson(
        self,
        clusters: List[Any],
        ensemble_output: Any,
        assessed_schools: List[SchoolRiskAssessment],
    ) -> Dict[str, Any]:
        """Synthesizes standard GeoJSON FeatureCollection with all map layers."""
        features = []

        # 1. Fire cluster points
        for fire in clusters:
            features.append({
                "type": "Feature",
                "id": fire.fire_id,
                "geometry": {
                    "type": "Point",
                    "coordinates": [fire.centroid_lon, fire.centroid_lat],
                },
                "properties": {
                    "layer_type": "fire_source",
                    "hotspot_count": fire.hotspot_count,
                    "total_frp_mw": fire.frp_summary,
                    "source_strength": fire.source_strength,
                },
            })

        # 2. Uncertainty Envelope Polygon
        if ensemble_output.affected_area_union_geojson.get("coordinates"):
            features.append({
                "type": "Feature",
                "id": "uncertainty_envelope",
                "geometry": ensemble_output.affected_area_union_geojson,
                "properties": {
                    "layer_type": "uncertainty_envelope",
                    "member_count": ensemble_output.member_count,
                    "stroke_style": "dashed",
                },
            })

        # 3. School Pins with exact geocoordinates
        for s in assessed_schools:
            features.append({
                "type": "Feature",
                "id": s.school_id,
                "geometry": {
                    "type": "Point",
                    "coordinates": [s.longitude, s.latitude],
                },
                "properties": {
                    "layer_type": "school_pin",
                    "name": s.name,
                    "district": s.district,
                    "risk_band": s.risk_band,
                    "risk_score": s.risk_score,
                    "impact_probability": s.impact_probability,
                    "predicted_arrival_time": s.predicted_arrival_time.isoformat() if s.predicted_arrival_time else None,
                },
            })

        return {"type": "FeatureCollection", "features": features}
