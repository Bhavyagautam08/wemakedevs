"""
2D Lagrangian Particle Transport & Atmospheric Decay Engine
Advects virtual smoke particles along 2D interpolated wind vectors with
Brownian turbulent diffusion and exponential mass decay.
"""

import math
from typing import List, Dict, Any, Tuple
import numpy as np
from src.types import FireCluster
from src.layer1_predictive.coordinates import LocalMetricProjection
from src.layer1_predictive.weather_field import WeatherVectorField
from src.config import SimulationConfig


class ParticleState:
    """Represents an active ensemble of virtual particles."""

    def __init__(self, x: np.ndarray, y: np.ndarray, mass: np.ndarray, initial_mass: np.ndarray):
        self.x = x.astype(np.float64)  # Easting (meters)
        self.y = y.astype(np.float64)  # Northing (meters)
        self.mass = mass.astype(np.float64)  # Mass proxy (dimensionless)
        self.initial_mass = initial_mass.astype(np.float64)

    def __len__(self):
        return len(self.x)


class LagrangianTransportEngine:
    """
    Simulates stochastic particle trajectories in local metric space (meters).
    """

    def __init__(
        self,
        config: SimulationConfig = None,
        projection: LocalMetricProjection = None,
    ):
        self.config = config or SimulationConfig()
        self.projection = projection or LocalMetricProjection()

    def initialize_particles(
        self,
        fires: List[FireCluster],
        source_multiplier: float = 1.0,
    ) -> ParticleState:
        """
        Spawns virtual particles around fire centroids proportional to FRP and source strength.
        """
        all_x, all_y, all_m = [], [], []

        for fire in fires:
            # Particle count scaled by cluster size and source strength
            base_count = self.config.particle_count_per_fire
            n_particles = int(np.clip(base_count * (0.4 + 0.6 * fire.source_strength), 100, 2000))

            cx, cy = self.projection.to_metric(fire.centroid_lat, fire.centroid_lon)

            # Initial spatial distribution around fire complex (Gaussian dispersion radius ~3km)
            init_spread_m = 3000.0
            x_pts = cx + np.random.normal(0, init_spread_m, n_particles)
            y_pts = cy + np.random.normal(0, init_spread_m, n_particles)

            # Mass allocation
            unit_mass = (fire.source_strength * source_multiplier) / n_particles
            m_pts = np.full(n_particles, unit_mass)

            all_x.append(x_pts)
            all_y.append(y_pts)
            all_m.append(m_pts)

        if not all_x:
            return ParticleState(np.array([]), np.array([]), np.array([]), np.array([]))

        x_arr = np.concatenate(all_x)
        y_arr = np.concatenate(all_y)
        m_arr = np.concatenate(all_m)

        return ParticleState(x_arr, y_arr, m_arr, m_arr.copy())

    def step(
        self,
        particles: ParticleState,
        weather: WeatherVectorField,
        dt_seconds: float,
        elapsed_seconds: float,
        speed_factor: float = 1.0,
        dir_shift: float = 0.0,
        blh_factor: float = 1.0,
        diff_factor: float = 1.0,
        rain_mm_per_hr: float = 0.0,
    ) -> Tuple[ParticleState, Dict[str, float]]:
        """
        Performs one integration step (dt):
          1. Deterministic wind advection: dx = u * dt, dy = v * dt
          2. Stochastic turbulent diffusion: sqrt(2 * K * dt) * N(0, 1)
          3. Mass decay: exponential atmospheric sink + rain washout
        """
        if len(particles) == 0:
            return particles, {"decay_rate": self.config.decay_rate_lambda, "conc_before": 0.0, "conc_after": 0.0}

        mass_before = float(np.sum(particles.mass))

        # 1. Local interpolated wind vector field (m/s)
        u, v = weather.get_wind_vector(
            particles.x, particles.y, elapsed_seconds, speed_factor, dir_shift
        )

        # 2. Diffusion coefficients modulated by BLH
        _, kx, ky = weather.get_blh_and_diffusivity(elapsed_seconds, blh_factor, diff_factor)

        # Stochastic Brownian walk kicks
        sigma_x = math.sqrt(2.0 * kx * dt_seconds)
        sigma_y = math.sqrt(2.0 * ky * dt_seconds)

        turb_x = np.random.normal(0, sigma_x, len(particles))
        turb_y = np.random.normal(0, sigma_y, len(particles))

        # Update coordinates in meters
        particles.x += (u * dt_seconds) + turb_x
        particles.y += (v * dt_seconds) + turb_y

        # 3. Exponential mass decay (chemical aging & particulate settling)
        # C(t) = C0 * exp(-lambda * dt)
        decay_factor = math.exp(-self.config.decay_rate_lambda * dt_seconds)
        particles.mass *= decay_factor

        # Rain washout
        if rain_mm_per_hr > 0.2:
            particles.mass *= self.config.rain_washout_factor

        # Prune dead particles (< 1% initial mass)
        alive_mask = particles.mass > (self.config.min_mass_threshold * np.median(particles.initial_mass))
        particles.x = particles.x[alive_mask]
        particles.y = particles.y[alive_mask]
        particles.mass = particles.mass[alive_mask]
        particles.initial_mass = particles.initial_mass[alive_mask]

        mass_after = float(np.sum(particles.mass))

        decay_stats = {
            "decay_rate": self.config.decay_rate_lambda,
            "concentration_before_decay": round(mass_before, 4),
            "concentration_after_decay": round(mass_after, 4),
        }

        return particles, decay_stats
