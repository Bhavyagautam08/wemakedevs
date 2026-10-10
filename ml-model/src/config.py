"""
DhuanAlert Configuration Module
Contains all physical constants, spatial grid settings, ensemble scenario definitions,
and configurable risk scoring weights.
"""

import os
from typing import Dict, Any
from pydantic import BaseModel, Field


def _load_root_env():
    """Loads key-value pairs from centralised root .env into os.environ."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_env_path = os.path.abspath(os.path.join(current_dir, "..", "..", ".env"))
    if os.path.exists(root_env_path):
        with open(root_env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v


_load_root_env()


class ProjectionConfig(BaseModel):
    """Local metric coordinate system (East/North in meters) projection origin."""
    origin_lat: float = 29.5   # Center between Punjab/Haryana fires and Delhi-NCR
    origin_lon: float = 76.5


class SimulationConfig(BaseModel):
    """2D Lagrangian particle transport & diffusion parameters."""
    timestep_seconds: int = 900          # 15 minutes (dt)
    horizon_hours: int = 9               # T+3h, T+6h, and T+9h forecast checkpoints
    particle_count_per_fire: int = 500   # Scalable virtual particles
    base_diffusion_kx: float = 250.0     # Horizontal diffusivity m^2/s
    base_diffusion_ky: float = 250.0     # Horizontal diffusivity m^2/s
    initial_sigma_meters: float = 2000.0 # Initial Gaussian plume spread (2 km)
    decay_rate_lambda: float = 3.2e-5    # ~6-hour half-life (ln(2) / (6 * 3600))
    rain_washout_factor: float = 0.70    # Multiplier applied if rain > 0.2 mm/h
    min_mass_threshold: float = 0.01     # Drop particles with < 1% initial mass


class RiskScoringWeights(BaseModel):
    """
    Configurable school operational risk scoring formula:
    risk_score = w1 * norm_conc + w2 * plume_prob + w3 * norm_exposure + w4 * uncertainty
    """
    w1_concentration: float = 0.40
    w2_plume_probability: float = 0.30
    w3_exposure_duration: float = 0.20
    w4_uncertainty: float = 0.10

    # Risk band thresholds [0.0 - 1.0]
    low_threshold: float = 0.25
    moderate_threshold: float = 0.50
    high_threshold: float = 0.75


class EnsembleMemberConfig(BaseModel):
    """Definition for an ensemble perturbation scenario."""
    member_id: str
    name: str
    wind_speed_multiplier: float
    wind_direction_shift_deg: float
    diffusion_multiplier: float
    source_strength_multiplier: float
    blh_multiplier: float


class Config(BaseModel):
    projection: ProjectionConfig = Field(default_factory=ProjectionConfig)
    simulation: SimulationConfig = Field(default_factory=SimulationConfig)
    risk_weights: RiskScoringWeights = Field(default_factory=RiskScoringWeights)

    # 3 Physically Plausible Ensemble Scenarios
    ensemble_members: list[EnsembleMemberConfig] = [
        EnsembleMemberConfig(
            member_id="member_1",
            name="Lower Wind / East Drift / Reduced Emissions",
            wind_speed_multiplier=0.85,
            wind_direction_shift_deg=+15.0,
            diffusion_multiplier=0.80,
            source_strength_multiplier=0.80,
            blh_multiplier=0.85,
        ),
        EnsembleMemberConfig(
            member_id="member_2",
            name="Nominal GFS Forecast / Baseline Emissions",
            wind_speed_multiplier=1.00,
            wind_direction_shift_deg=0.0,
            diffusion_multiplier=1.00,
            source_strength_multiplier=1.00,
            blh_multiplier=1.00,
        ),
        EnsembleMemberConfig(
            member_id="member_3",
            name="Higher Wind / West Drift / Elevated Emissions",
            wind_speed_multiplier=1.20,
            wind_direction_shift_deg=-15.0,
            diffusion_multiplier=1.25,
            source_strength_multiplier=1.25,
            blh_multiplier=1.15,
        ),
    ]

    # Amazon Bedrock Settings
    bedrock_model_id: str = "amazon.nova-micro-v1:0"
    bedrock_region: str = "us-east-1"
    offline_fallback_mode: bool = True  # Allows running tests offline without active AWS credentials


# Global default configuration instance
DEFAULT_CONFIG = Config()
