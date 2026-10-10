"""
School Geospatial Risk Scorer & Impact Evaluator
Intersects forward smoke plume ensemble with school coordinates,
estimating arrival lead times, exposure durations, and operational risk bands.
"""

import math
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import numpy as np
from src.types import School, SchoolRiskAssessment, FireCluster
from src.config import RiskScoringWeights, DEFAULT_CONFIG
from src.layer1_predictive.coordinates import LocalMetricProjection
from src.layer1_predictive.ensemble import ScenarioEnsembleRunner
from src.layer1_predictive.lagrangian_engine import ParticleState


class SchoolRiskScorer:
    """
    Evaluates environmental smoke exposure risk at individual schools.
    """

    def __init__(
        self,
        weights: RiskScoringWeights = None,
        projection: LocalMetricProjection = None,
    ):
        self.weights = weights or DEFAULT_CONFIG.risk_weights
        self.projection = projection or LocalMetricProjection()

    def assess_schools(
        self,
        schools: List[School],
        fires: List[FireCluster],
        ensemble_runner: ScenarioEnsembleRunner,
        snapshots: Dict[int, List[ParticleState]],
        sim_start_time: datetime,
        threshold: float = 50.0,
        normalisation_ugm3: float = 250.0,
    ) -> List[SchoolRiskAssessment]:
        """
        Assesses each school against the hourly ensemble snapshots {hour: [member states]}.
        threshold: smoke PM2.5 increment (ug/m^3) that counts as impact. Concentration and
        ensemble spread enter the risk score divided by normalisation_ugm3 (CPCB "Severe").
        All outputs come from the same sampled concentrations, so impact_probability > 0
        if and only if predicted_arrival_time is set.
        """
        assessments: List[SchoolRiskAssessment] = []
        if not schools:
            return assessments
        hours = sorted(snapshots)
        diffusion = ensemble_runner.diffusion_field

        # Concentration cube C[hour, member, school] in ug/m^3
        lats = np.array([s.latitude for s in schools])
        lons = np.array([s.longitude for s in schools])
        cube = np.array([
            [diffusion.sample_concentrations(lats, lons, st) for st in snapshots[h]]
            for h in hours
        ])
        n_members = cube.shape[1]
        hit = cube >= threshold                       # [h, m, s]
        prob_h = hit.sum(axis=1) / n_members          # [h, s]
        max_h = cube.max(axis=1)                      # [h, s]
        spread_h = max_h - cube.min(axis=1)           # [h, s]

        # Distance is reported to the NEAREST fire cluster
        if fires:
            fx, fy = self.projection.to_metric(
                np.array([f.centroid_lat for f in fires]), np.array([f.centroid_lon for f in fires])
            )
            sx, sy = self.projection.to_metric(lats, lons)
            nearest_km = np.sqrt((sx[:, None] - fx[None, :]) ** 2 + (sy[:, None] - fy[None, :]) ** 2).min(axis=1) / 1000.0
        else:
            nearest_km = np.zeros(len(schools))

        for k, s in enumerate(schools):
            dist_km = round(float(nearest_km[k]), 2)
            col_max = max_h[:, k]
            peak_idx = int(np.lexsort((col_max, prob_h[:, k]))[-1])
            prob = round(float(prob_h[peak_idx, k]), 3)
            members_aff = int(hit[peak_idx, :, k].sum())
            peak_c = float(col_max.max())
            spread_ugm3 = float(spread_h[int(np.argmax(col_max)), k])
            norm_conc = min(1.0, peak_c / normalisation_ugm3)
            uncertainty = min(1.0, spread_ugm3 / normalisation_ugm3)

            # Arrival: first time the ensemble-max concentration crosses the threshold,
            # linearly interpolated between the bracketing hourly snapshots.
            arrival_time = None
            above = np.nonzero(col_max >= threshold)[0]
            if len(above):
                i = int(above[0])
                if i == 0:
                    t_hours = float(hours[0])
                else:
                    c_prev, c = float(col_max[i - 1]), float(col_max[i])
                    t_hours = hours[i - 1] + (hours[i] - hours[i - 1]) * (threshold - c_prev) / (c - c_prev)
                arrival_time = sim_start_time + timedelta(hours=t_hours)

            # Exposure: hours (at hourly resolution, after T0) in which any member is above threshold
            exposure_duration = 60 * int(np.sum(col_max[1:] >= threshold))

            # Compute configurable operational risk score:
            # risk_score = w1 * conc + w2 * prob + w3 * norm_exposure + w4 * uncertainty
            norm_exp = min(1.0, exposure_duration / 180.0)
            score = (
                self.weights.w1_concentration * norm_conc
                + self.weights.w2_plume_probability * prob
                + self.weights.w3_exposure_duration * norm_exp
                + self.weights.w4_uncertainty * (1.0 - uncertainty)
            )
            score = float(np.clip(score, 0.0, 1.0))

            # Categorize into risk band
            if score >= self.weights.high_threshold:
                band = "VERY_HIGH"
            elif score >= self.weights.moderate_threshold:
                band = "HIGH"
            elif score >= self.weights.low_threshold:
                band = "MODERATE"
            else:
                band = "LOW"

            assessments.append(
                SchoolRiskAssessment(
                    school_id=s.school_id,
                    name=s.name,
                    district=s.district,
                    latitude=s.latitude,
                    longitude=s.longitude,
                    distance_to_fire_km=dist_km,
                    predicted_arrival_time=arrival_time,
                    peak_concentration=round(peak_c, 2),
                    exposure_duration_minutes=exposure_duration,
                    ensemble_members_affected=members_aff,
                    impact_probability=prob,
                    uncertainty=round(uncertainty, 3),
                    risk_score=round(score, 3),
                    risk_band=band,
                )
            )

        # Sort descending by operational risk score
        return sorted(assessments, key=lambda a: a.risk_score, reverse=True)
