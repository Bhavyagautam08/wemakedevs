"""
Layer 1 Predictive Pipeline Runner
Orchestrates raw data ingestion, fire source estimation, 2D Lagrangian ensemble advection,
school risk scoring, map GeoJSON synthesis, and timeline slice generation.
"""

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
from src.layer1_predictive.lagrangian_engine import LagrangianTransportEngine, ParticleState
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
        final_particles, ensemble_output, particle_snapshots = self.ensemble.run_ensemble(
            fires=clusters,
            weather_obs=weather,
            simulation_start_time=now,
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

        # 4. Generate timeline slices only within the configured forecast window.
        timeline_slices = self._generate_timeline_slices(
            now=now,
            particle_snapshots=particle_snapshots,
            assessed_schools=assessed_schools,
            horizon_hours=self.config.simulation.horizon_hours,
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

    @staticmethod
    def _combine_member_particles(member_states: List[ParticleState]) -> ParticleState:
        active_states = [state for state in member_states if len(state) > 0]
        if not active_states:
            return ParticleState(np.array([]), np.array([]), np.array([]), np.array([]))
        return ParticleState(
            x=np.concatenate([state.x for state in active_states]),
            y=np.concatenate([state.y for state in active_states]),
            mass=np.concatenate([state.mass for state in active_states]),
            initial_mass=np.concatenate([state.initial_mass for state in active_states]),
        )

    def _generate_timeline_slices(
        self,
        now: datetime,
        particle_snapshots: Dict[int, List[ParticleState]],
        assessed_schools: List[SchoolRiskAssessment],
        horizon_hours: int,
    ) -> List[TimelineSlice]:
        """Build map slices directly from the continuous ensemble particle evolution."""
        expected_hours = set(range(horizon_hours + 1))
        missing_hours = sorted(expected_hours - set(particle_snapshots))
        if missing_hours:
            raise ValueError(
                "PARTICLE_SNAPSHOT_ERROR: ensemble did not produce hourly snapshots for "
                f"T+{', T+'.join(str(hour) for hour in missing_hours)}h."
            )

        slices, corridor_coords = [], []
        for hour in range(horizon_hours + 1):
            particles = self._combine_member_particles(particle_snapshots[hour])
            if len(particles) == 0:
                raise ValueError(f"PARTICLE_SNAPSHOT_ERROR: T+{hour}h contains no active simulated particles.")

            center_x = float(np.average(particles.x, weights=particles.mass))
            center_y = float(np.average(particles.y, weights=particles.mass))
            center_lat, center_lon = self.projection.to_wgs84(
                np.array([center_x]), np.array([center_y])
            )
            center_latitude, center_longitude = float(center_lat[0]), float(center_lon[0])
            corridor_coords.append([round(center_longitude, 6), round(center_latitude, 6)])

            stride = max(1, int(np.ceil(len(particles) / 250)))
            sample_x, sample_y, sample_mass = (
                particles.x[::stride],
                particles.y[::stride],
                particles.mass[::stride],
            )
            scatter_lats, scatter_lons = self.projection.to_wgs84(sample_x, sample_y)
            max_mass = float(np.max(sample_mass))
            scatter = [
                [round(float(lat), 6), round(float(lon), 6), round(float(mass / max_mass), 4)]
                for lat, lon, mass in zip(scatter_lats, scatter_lons, sample_mass)
            ]
            intensity = float(np.max(particles.mass / particles.initial_mass))
            slice_time = now + timedelta(hours=hour)
            affected_schools = sum(
                1 for school in assessed_schools
                if school.predicted_arrival_time and school.predicted_arrival_time <= slice_time
            )
            slices.append(
                TimelineSlice(
                    horizon_offset_hours=hour,
                    timestamp=slice_time,
                    plume_center_lat=round(center_latitude, 6),
                    plume_center_lon=round(center_longitude, 6),
                    plume_area_sq_km=self.diffusion.plume_area_sq_km(particles),
                    affected_schools_count=affected_schools,
                    max_intensity=round(intensity, 4),
                    contour_geojson=self.diffusion.extract_contour_geojson(particles),
                    scatter_points=scatter,
                    corridor_geojson={"type": "LineString", "coordinates": corridor_coords.copy()},
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
