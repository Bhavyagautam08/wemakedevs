"""
Multi-Member Scenario Ensemble & Plume Uncertainty Modeler
Executes physically plausible scenario perturbations (wind speed, wind direction,
BLH trapping, emission strength) and computes scenario overlap probabilities.
"""

from datetime import datetime
from typing import List, Dict, Any, Tuple
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
        simulation_start_time: datetime,
        horizon_hours: int = 9,
        dt_seconds: int = 900,
    ) -> Tuple[List[ParticleState], EnsembleOutput, Dict[int, List[ParticleState]]]:
        """
        Runs all ensemble members forward through time to the forecast horizon.
        """
        weather_field = WeatherVectorField(
            weather_obs,
            simulation_start_time=simulation_start_time,
            projection=self.engine.projection,
        )
        total_steps = int((horizon_hours * 3600) / dt_seconds)
        weather_field.ensure_coverage(horizon_hours * 3600)

        final_particles: List[ParticleState] = []
        particle_snapshots: Dict[int, List[ParticleState]] = {
            hour: [] for hour in range(horizon_hours + 1)
        }
        member_summaries: List[EnsembleMemberSummary] = []

        all_lats, all_lons = [], []

        for m_cfg in self.members_config:
            # 1. Initialize particles for this scenario
            p_state = self.engine.initialize_particles(
                fires=fires,
                source_multiplier=m_cfg.source_strength_multiplier,
            )
            particle_snapshots[0].append(p_state.copy())

            # 2. Time-step simulation
            for step in range(total_steps):
                elapsed = step * dt_seconds
                p_state, _ = self.engine.step(
                    particles=p_state,
                    weather=weather_field,
                    dt_seconds=dt_seconds,
                    elapsed_seconds=elapsed,
                    speed_factor=m_cfg.wind_speed_multiplier,
                    dir_shift=m_cfg.wind_direction_shift_deg,
                    blh_factor=m_cfg.blh_multiplier,
                    diff_factor=m_cfg.diffusion_multiplier,
                )
                completed_seconds = (step + 1) * dt_seconds
                if completed_seconds % 3600 == 0:
                    particle_snapshots[completed_seconds // 3600].append(p_state.copy())

            final_particles.append(p_state)

            # 3. Calculate summary stats
            if len(p_state) > 0:
                lats, lons = self.engine.projection.to_wgs84(p_state.x, p_state.y)
                all_lats.extend(lats)
                all_lons.extend(lons)
                peak_m = float(np.max(p_state.mass) * 1000.0)
                mean_m = float(np.mean(p_state.mass) * 1000.0)
            else:
                peak_m, mean_m = 0.0, 0.0

            member_summaries.append(
                EnsembleMemberSummary(
                    member_id=m_cfg.member_id,
                    name=m_cfg.name,
                    wind_speed_factor=m_cfg.wind_speed_multiplier,
                    wind_dir_shift=m_cfg.wind_direction_shift_deg,
                    peak_concentration=round(peak_m, 3),
                    mean_concentration=round(mean_m, 3),
                )
            )

        # 4. Generate Union and Intersection Footprints
        if all_lats:
            union_poly = [
                [
                    [round(float(np.min(all_lons)), 4), round(float(np.min(all_lats)), 4)],
                    [round(float(np.max(all_lons)), 4), round(float(np.min(all_lats)), 4)],
                    [round(float(np.max(all_lons)), 4), round(float(np.max(all_lats)), 4)],
                    [round(float(np.min(all_lons)), 4), round(float(np.max(all_lats)), 4)],
                    [round(float(np.min(all_lons)), 4), round(float(np.min(all_lats)), 4)],
                ]
            ]
        else:
            union_poly = []

        ensemble_output = EnsembleOutput(
            member_count=len(self.members_config),
            members=member_summaries,
            affected_area_union_geojson={
                "type": "Polygon",
                "coordinates": union_poly,
            },
            affected_area_intersection_geojson={
                "type": "Polygon",
                "coordinates": union_poly,  # MVP approximation
            },
        )

        return final_particles, ensemble_output, particle_snapshots

    def evaluate_location_impact(
        self,
        lat: float,
        lon: float,
        ensemble_particles: List[ParticleState],
        threshold: float = 0.20,
    ) -> Tuple[int, float, float, float]:
        """
        Calculates impact probability across ensemble members at a target point.
        Returns:
          - members_affected
          - impact_probability (members_affected / total_members)
          - max_concentration
          - spread_uncertainty (max - min)
        """
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
