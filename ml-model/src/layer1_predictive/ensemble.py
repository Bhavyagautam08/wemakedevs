"""
Multi-Member Scenario Ensemble & Plume Uncertainty Modeler
Executes physically plausible scenario perturbations (wind speed, wind direction,
BLH trapping, emission strength) and computes scenario overlap probabilities.
"""

from typing import List, Dict, Any, Tuple
from datetime import datetime
import numpy as np
from src.types import (
    FireCluster,
    WeatherObservation,
    EnsembleMemberSummary,
    EnsembleOutput,
)
from src.config import EnsembleMemberConfig, DEFAULT_CONFIG
from src.layer1_predictive.lagrangian_engine import LagrangianTransportEngine, ParticleState
from src.layer1_predictive.weather_field import WeatherVectorField
from src.layer1_predictive.diffusion_field import GaussianDiffusionField


class ScenarioEnsembleRunner:
    """
    Simulates N physically perturbed scenarios to provide honest uncertainty bounds.
    """

    def __init__(
        self,
        engine: LagrangianTransportEngine = None,
        diffusion_field: GaussianDiffusionField = None,
        members_config: List[EnsembleMemberConfig] = None,
    ):
        self.engine = engine or LagrangianTransportEngine()
        self.diffusion_field = diffusion_field or GaussianDiffusionField()
        self.members_config = members_config or DEFAULT_CONFIG.ensemble_members

    def run_ensemble(
        self,
        fires: List[FireCluster],
        weather_obs: List[WeatherObservation],
        start_time: datetime,
        horizon_hours: int = 9,
        dt_seconds: int = 900,
    ) -> Tuple[Dict[int, List[ParticleState]], EnsembleOutput]:
        """
        Runs every ensemble member as ONE continuous integration from t=0 to horizon_hours.
        The cloud is snapshotted (deep-copied) at every whole hour and stepping continues on
        the same particle arrays, so the +6h state is the +3h state advected for 3 more hours.

        Returns ({hour: [member states]}, EnsembleOutput) with hours 0..horizon_hours.
        """
        weather_field = WeatherVectorField(
            weather_obs,
            start_time=start_time,
            projection=self.engine.projection,
            config=self.engine.config,
        )
        weather_field.require_coverage(horizon_hours * 3600)
        steps_per_hour = 3600 // dt_seconds

        snapshots: Dict[int, List[ParticleState]] = {h: [] for h in range(horizon_hours + 1)}
        emission_hours = self.engine.config.emission_duration_hours

        def snapshot(state: ParticleState, hour: int, m_cfg) -> ParticleState:
            snap = state.copy()
            snap.mixing_height_m = weather_field.get_blh_at(snap.x, snap.y, hour * 3600.0, m_cfg.blh_multiplier)
            return snap

        for m_cfg in self.members_config:
            # Hourly release batches: batch k carries the emissions of hour [k, k+1)
            p_state = self.engine.release_batch(fires, 3600.0, m_cfg.source_strength_multiplier)
            snapshots[0].append(snapshot(p_state, 0, m_cfg))

            for step in range(horizon_hours * steps_per_hour):
                p_state, _ = self.engine.step(
                    particles=p_state,
                    weather=weather_field,
                    dt_seconds=dt_seconds,
                    elapsed_seconds=step * dt_seconds,
                    speed_factor=m_cfg.wind_speed_multiplier,
                    dir_shift=m_cfg.wind_direction_shift_deg,
                    blh_factor=m_cfg.blh_multiplier,
                    diff_factor=m_cfg.diffusion_multiplier,
                )
                if (step + 1) % steps_per_hour == 0:
                    hour = (step + 1) // steps_per_hour
                    if hour < emission_hours:
                        p_state.extend(self.engine.release_batch(fires, 3600.0, m_cfg.source_strength_multiplier))
                    snapshots[hour].append(snapshot(p_state, hour, m_cfg))

        final_states = snapshots[horizon_hours]
        member_summaries: List[EnsembleMemberSummary] = []
        boxes = []
        for m_cfg, p_state in zip(self.members_config, final_states):
            peak_c, mean_c = 0.0, 0.0
            if len(p_state) > 0:
                lats, lons = self.engine.projection.to_wgs84(p_state.x, p_state.y)
                boxes.append((float(np.min(lons)), float(np.min(lats)), float(np.max(lons)), float(np.max(lats))))
                # Concentration index at the densest grid cell and at the mass-weighted centroid
                x_edges, y_edges, grid = self.diffusion_field.concentration_grid(p_state)
                ix, iy = np.unravel_index(int(np.argmax(grid)), grid.shape)
                res = self.diffusion_field.grid_res_m
                plat, plon = self.engine.projection.to_wgs84(
                    np.array([x_edges[ix] + res / 2]), np.array([y_edges[iy] + res / 2])
                )
                peak_c = self.diffusion_field.sample_point_concentration(float(plat[0]), float(plon[0]), p_state)
                cx, cy = p_state.centroid()
                clat, clon = self.engine.projection.to_wgs84(np.array([cx]), np.array([cy]))
                mean_c = self.diffusion_field.sample_point_concentration(float(clat[0]), float(clon[0]), p_state)

            member_summaries.append(
                EnsembleMemberSummary(
                    member_id=m_cfg.member_id,
                    name=m_cfg.name,
                    wind_speed_factor=m_cfg.wind_speed_multiplier,
                    wind_dir_shift=m_cfg.wind_direction_shift_deg,
                    peak_concentration=round(peak_c, 3),
                    mean_concentration=round(mean_c, 3),
                )
            )

        # Union = bounding box of all members; intersection = overlap of member bounding boxes
        def ring(b):
            x0, y0, x1, y1 = (round(v, 4) for v in b)
            return [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]

        union_poly, inter_poly = [], []
        if boxes:
            union_poly = ring((min(b[0] for b in boxes), min(b[1] for b in boxes),
                               max(b[2] for b in boxes), max(b[3] for b in boxes)))
            ib = (max(b[0] for b in boxes), max(b[1] for b in boxes),
                  min(b[2] for b in boxes), min(b[3] for b in boxes))
            if len(boxes) == len(final_states) and ib[0] < ib[2] and ib[1] < ib[3]:
                inter_poly = ring(ib)

        ensemble_output = EnsembleOutput(
            member_count=len(self.members_config),
            members=member_summaries,
            affected_area_union_geojson={"type": "Polygon", "coordinates": union_poly},
            affected_area_intersection_geojson={"type": "Polygon", "coordinates": inter_poly},
        )

        return snapshots, ensemble_output

    def evaluate_location_impact(
        self,
        lat: float,
        lon: float,
        ensemble_particles: List[ParticleState],
        threshold: float = None,
    ) -> Tuple[int, float, float, float]:
        """
        Calculates impact probability across ensemble members at a target point.
        Returns:
          - members_affected
          - impact_probability (members_affected / total_members)
          - max_concentration (ug/m^3)
          - spread_uncertainty (max - min, ug/m^3)
        """
        if threshold is None:
            threshold = self.engine.config.impact_threshold_ugm3
        concentrations = []
        for p_state in ensemble_particles:
            c = self.diffusion_field.sample_point_concentration(lat, lon, p_state)
            concentrations.append(c)

        total_members = len(ensemble_particles)
        affected = sum(1 for c in concentrations if c >= threshold)
        prob = round(affected / total_members, 3) if total_members > 0 else 0.0

        max_c = max(concentrations) if concentrations else 0.0
        min_c = min(concentrations) if concentrations else 0.0
        spread = round(max_c - min_c, 3)

        return affected, prob, max_c, spread
