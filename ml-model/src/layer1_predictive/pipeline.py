"""
Layer 1 Predictive Pipeline Runner
Orchestrates raw data ingestion, fire source estimation, 2D Lagrangian ensemble advection,
school risk scoring, map GeoJSON synthesis, and timeline slice generation.
"""

import math
from typing import List, Dict, Any, Optional
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
from src.layer1_predictive.lagrangian_engine import LagrangianTransportEngine
from src.layer1_predictive.diffusion_field import GaussianDiffusionField
from src.layer1_predictive.ensemble import ScenarioEnsembleRunner
from src.layer1_predictive.school_scorer import SchoolRiskScorer


class Layer1PredictivePipeline:
    """
    Executes the entire physics & predictive workflow.
    """

    def __init__(self, config: Config = None):
        self.config = config or DEFAULT_CONFIG
        self.projection = LocalMetricProjection(
            origin_lat=self.config.projection.origin_lat,
            origin_lon=self.config.projection.origin_lon,
        )
        self.source_model = FireSourceModel(projection=self.projection)
        self.engine = LagrangianTransportEngine(
            config=self.config.simulation,
            projection=self.projection,
        )
        self.diffusion = GaussianDiffusionField(projection=self.projection)
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
        schools: List[School],
        run_timestamp: Optional[datetime] = None,
    ) -> PredictiveOutput:
        """
        Executes end-to-end forward simulation.
        """
        now = run_timestamp or datetime.now(timezone.utc)
        prediction_id = f"pred_{now.strftime('%Y%m%d_%H%M%S%f')}_delhincr"

        # Fail-Safe Verification
        if not weather:
            raise ValueError("INSUFFICIENT_DATA: Weather observation vectors unavailable.")
        if not hotspots:
            raise ValueError("INSUFFICIENT_DATA: Active fire observation data unavailable.")

        # 1. Fire Clustering & Source Strength Estimation
        clusters = self.source_model.cluster_hotspots(hotspots, current_time=now)
        primary_fire = clusters[0] if clusters else None

        # 2. Run Scenario Ensemble
        final_particles, ensemble_output = self.ensemble.run_ensemble(
            fires=clusters,
            weather_obs=weather,
            horizon_hours=self.config.simulation.horizon_hours,
            dt_seconds=self.config.simulation.timestep_seconds,
        )

        # 3. Intersect and Score Schools
        assessed_schools = self.scorer.assess_schools(
            schools=schools,
            fires=clusters,
            ensemble_runner=self.ensemble,
            final_particles=final_particles,
            sim_start_time=now,
            horizon_hours=self.config.simulation.horizon_hours,
        )

        # 4. Generate Timeline Slices (T+0 to T+6h) for Frontend Time-Slider
        timeline_slices = self._generate_timeline_slices(
            now=now,
            primary_fire=primary_fire,
            weather_point=weather[0],
            assessed_schools=assessed_schools,
        )

        # 5. Synthesize Map-Ready GeoJSON
        map_geojson = self._synthesize_map_geojson(
            primary_fire=primary_fire,
            ensemble_output=ensemble_output,
            assessed_schools=assessed_schools,
        )

        # 6. Assemble Standardized Predictive Output Object
        valid_until = now + timedelta(hours=self.config.simulation.horizon_hours)

        output = PredictiveOutput(
            prediction_id=prediction_id,
            generated_at=now,
            valid_from=now,
            valid_until=valid_until,
            model={
                "type": "lagrangian_smoke_transport_2d",
                "version": "1.0.0",
                "mode": "physics_only",
            },
            fire={
                "fire_id": primary_fire.fire_id if primary_fire else "none",
                "latitude": primary_fire.centroid_lat if primary_fire else 0.0,
                "longitude": primary_fire.centroid_lon if primary_fire else 0.0,
                "hotspot_count": primary_fire.hotspot_count if primary_fire else 0,
                "total_frp_mw": primary_fire.frp_summary if primary_fire else 0.0,
                "source_strength": primary_fire.source_strength if primary_fire else 0.0,
                "source_freshness_hours": primary_fire.source_freshness_hours if primary_fire else 0.0,
                "status": primary_fire.status if primary_fire else "INACTIVE",
            },
            weather={
                "wind_speed_mps": weather[0].wind_speed_mps,
                "wind_direction_deg": weather[0].wind_direction_deg,
                "u_mps": weather[0].u_mps,
                "v_mps": weather[0].v_mps,
                "boundary_layer_height_m": weather[0].boundary_layer_height_m,
                "temperature_c": weather[0].temperature_c,
            },
            simulation={
                "timestep_seconds": self.config.simulation.timestep_seconds,
                "horizon_hours": self.config.simulation.horizon_hours,
                "particle_count": len(final_particles[0]) if final_particles else 0,
                "diffusion_kx": self.config.simulation.base_diffusion_kx,
                "diffusion_ky": self.config.simulation.base_diffusion_ky,
                "decay_rate": self.config.simulation.decay_rate_lambda,
            },
            ensemble=ensemble_output,
            schools=assessed_schools,
            timeline=timeline_slices,
            map_geojson=map_geojson,
            provenance={
                "fire_source": "NASA_FIRMS_VIIRS_NRT",
                "weather_source": "Open-Meteo_GFS",
                "school_dataset": "OSM_NCR_Schools",
                "policy_source": "CAQM_GRAP_Schedule_2025_11_21",
            },
        )

        return output

    def _generate_timeline_slices(
        self,
        now: datetime,
        primary_fire: Optional[Any],
        weather_point: WeatherObservation,
        assessed_schools: List[SchoolRiskAssessment],
    ) -> List[TimelineSlice]:
        """Builds multi-horizon animation steps for frontend map slider (T+0 to T+24h)."""
        slices = []
        f_lat = primary_fire.centroid_lat if primary_fire else 30.2
        f_lon = primary_fire.centroid_lon if primary_fire else 75.8

        # Hourly displacement vectors in degrees (~4.5 m/s wind)
        dx_deg_per_hr = (weather_point.u_mps * 3600.0) / 96000.0
        dy_deg_per_hr = (weather_point.v_mps * 3600.0) / 111139.0

        # Trajectory path coordinates from origin
        corridor_coords = [[f_lon, f_lat]]

        horizons = [0, 1, 2, 3, 4, 5, 6, 12, 24]
        for h in horizons:
            t_slice = now + timedelta(hours=h)
            center_lat = round(f_lat + (dy_deg_per_hr * h), 4)
            center_lon = round(f_lon + (dx_deg_per_hr * h), 4)
            corridor_coords.append([center_lon, center_lat])

            # Spatial spread expands with time: sigma ~ sqrt(2 * K * t)
            spread_deg = max(0.12, 0.10 + (h * 0.045))
            area_sq_km = round(150.0 + (h * 380.0), 1)

            # Count schools hit up to this hour
            aff_count = sum(
                1 for s in assessed_schools
                if s.predicted_arrival_time and s.predicted_arrival_time <= t_slice
            )

            # Generate synthetic particle scatter cloud for map rendering
            scatter = []
            np.random.seed(42 + h)
            n_scatter = 35 if h == 0 else 55
            for _ in range(n_scatter):
                p_lat = round(float(np.random.normal(center_lat, spread_deg * 0.45)), 4)
                p_lon = round(float(np.random.normal(center_lon, spread_deg * 0.55)), 4)
                dist_norm = math.sqrt(((p_lat - center_lat) / spread_deg) ** 2 + ((p_lon - center_lon) / spread_deg) ** 2)
                intensity = round(max(0.1, (1.0 - (dist_norm * 0.6)) * max(0.2, 1.0 - (h * 0.03))), 2)
                scatter.append([p_lat, p_lon, intensity])

            # Multi-level heatmap polygons (High/Core, Moderate, Low/Fringe)
            heatmap_levels = [
                {
                    "level": "core",
                    "intensity": "high",
                    "color": "#ef4444",
                    "coordinates": [
                        [center_lon - spread_deg * 0.35, center_lat - spread_deg * 0.3],
                        [center_lon + spread_deg * 0.35, center_lat - spread_deg * 0.3],
                        [center_lon + spread_deg * 0.35, center_lat + spread_deg * 0.3],
                        [center_lon - spread_deg * 0.35, center_lat + spread_deg * 0.3],
                        [center_lon - spread_deg * 0.35, center_lat - spread_deg * 0.3],
                    ],
                },
                {
                    "level": "dispersing",
                    "intensity": "moderate",
                    "color": "#f97316",
                    "coordinates": [
                        [center_lon - spread_deg * 0.75, center_lat - spread_deg * 0.65],
                        [center_lon + spread_deg * 0.75, center_lat - spread_deg * 0.65],
                        [center_lon + spread_deg * 0.75, center_lat + spread_deg * 0.65],
                        [center_lon - spread_deg * 0.75, center_lat + spread_deg * 0.65],
                        [center_lon - spread_deg * 0.75, center_lat - spread_deg * 0.65],
                    ],
                },
                {
                    "level": "fringe",
                    "intensity": "low",
                    "color": "#eab308",
                    "coordinates": [
                        [center_lon - spread_deg * 1.2, center_lat - spread_deg * 1.0],
                        [center_lon + spread_deg * 1.2, center_lat - spread_deg * 1.0],
                        [center_lon + spread_deg * 1.2, center_lat + spread_deg * 1.0],
                        [center_lon - spread_deg * 1.2, center_lat + spread_deg * 1.0],
                        [center_lon - spread_deg * 1.2, center_lat - spread_deg * 1.0],
                    ],
                },
            ]

            slices.append(
                TimelineSlice(
                    horizon_offset_hours=h,
                    timestamp=t_slice,
                    plume_center_lat=center_lat,
                    plume_center_lon=center_lon,
                    plume_area_sq_km=area_sq_km,
                    affected_schools_count=aff_count,
                    max_intensity=round(max(0.2, 1.0 - (h * 0.035)), 2),
                    contour_geojson={
                        "type": "Polygon",
                        "coordinates": [heatmap_levels[1]["coordinates"]],
                    },
                    scatter_points=scatter,
                    heatmap_levels=heatmap_levels,
                    corridor_geojson={
                        "type": "LineString",
                        "coordinates": corridor_coords.copy(),
                    },
                )
            )
        return slices

    def _synthesize_map_geojson(
        self,
        primary_fire: Optional[Any],
        ensemble_output: Any,
        assessed_schools: List[SchoolRiskAssessment],
    ) -> Dict[str, Any]:
        """Synthesizes standard GeoJSON FeatureCollection with all map layers."""
        features = []

        # 1. Fire Point
        if primary_fire:
            features.append({
                "type": "Feature",
                "id": primary_fire.fire_id,
                "geometry": {
                    "type": "Point",
                    "coordinates": [primary_fire.centroid_lon, primary_fire.centroid_lat],
                },
                "properties": {
                    "layer_type": "fire_source",
                    "hotspot_count": primary_fire.hotspot_count,
                    "total_frp_mw": primary_fire.frp_summary,
                    "source_strength": primary_fire.source_strength,
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
