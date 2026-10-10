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
        final_particles: List[ParticleState],
        sim_start_time: datetime,
        horizon_hours: int = 9,
    ) -> List[SchoolRiskAssessment]:
        """
        Assesses each school against the ensemble plume predictions.
        """
        assessments: List[SchoolRiskAssessment] = []

        # Reference primary fire centroid
        if fires:
            primary_fire = fires[0]
            f_lat, f_lon = primary_fire.centroid_lat, primary_fire.centroid_lon
        else:
            f_lat, f_lon = 30.2, 75.8

        for s in schools:
            dist_km = self.projection.distance_km(s.latitude, s.longitude, f_lat, f_lon)

            # Evaluate impact probability and peak concentration from ensemble
            members_aff, prob, peak_c, uncertainty = ensemble_runner.evaluate_location_impact(
                lat=s.latitude,
                lon=s.longitude,
                ensemble_particles=final_particles,
                threshold=0.20,
            )

            # Estimate arrival time based on distance and wind advection speed (~4.5 m/s ~= 16.2 km/h)
            avg_advection_speed_kmh = 18.0
            travel_hours = max(0.5, dist_km / avg_advection_speed_kmh)

            if prob > 0.0 and travel_hours <= horizon_hours:
                arrival_time = sim_start_time + timedelta(hours=travel_hours)
                exposure_duration = int(min(240, (horizon_hours - travel_hours + 1.0) * 60))
            else:
                arrival_time = None
                exposure_duration = 0

            # Compute configurable operational risk score:
            # risk_score = w1 * conc + w2 * prob + w3 * norm_exposure + w4 * uncertainty
            norm_exp = min(1.0, exposure_duration / 180.0)
            score = (
                self.weights.w1_concentration * peak_c
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
                    peak_concentration=round(peak_c, 3),
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
