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

    def __init__(self, x: np.ndarray, y: np.ndarray, mass: np.ndarray, initial_mass: np.ndarray,
                 mixing_height_m: float = None, source: np.ndarray = None):
        self.x = x.astype(np.float64)  # Easting (meters)
        self.y = y.astype(np.float64)  # Northing (meters)
        self.mass = mass.astype(np.float64)  # PM2.5 mass per particle (micrograms)
        self.initial_mass = initial_mass.astype(np.float64)
        # Well-mixed layer depth (m) per particle (or scalar) valid for this state; set at snapshots
        self.mixing_height_m = mixing_height_m
        # Index of the fire cluster that emitted each particle
        self.source = (source if source is not None else np.zeros(len(self.x))).astype(np.int32)

    def __len__(self):
        return len(self.x)

    def copy(self) -> "ParticleState":
        """Deep copy, used to snapshot the cloud at a horizon without stopping the run."""
        mh = self.mixing_height_m.copy() if isinstance(self.mixing_height_m, np.ndarray) else self.mixing_height_m
        return ParticleState(self.x.copy(), self.y.copy(), self.mass.copy(), self.initial_mass.copy(),
                             mh, self.source.copy())

    def extend(self, other: "ParticleState") -> "ParticleState":
        """Appends newly released particles (in place) and returns self."""
        self.x = np.concatenate([self.x, other.x])
        self.y = np.concatenate([self.y, other.y])
        self.mass = np.concatenate([self.mass, other.mass])
        self.initial_mass = np.concatenate([self.initial_mass, other.initial_mass])
        self.source = np.concatenate([self.source, other.source])
        return self

    def centroid(self) -> Tuple[float, float]:
        """Mass-weighted centroid (x, y) in meters."""
        total = float(np.sum(self.mass))
        if total <= 0.0:
            raise ValueError("Cannot compute centroid of an empty particle cloud.")
        return float(np.sum(self.x * self.mass) / total), float(np.sum(self.y * self.mass) / total)


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

    def particles_per_batch(self, fire: FireCluster) -> int:
        """Particle count for one hourly release batch of a cluster."""
        total = np.clip(self.config.particle_count_per_fire * (0.4 + 0.6 * fire.source_strength), 100, 2000)
        return max(50, int(total // max(1, self.config.emission_duration_hours)))

    def release_batch(
        self,
        fires: List[FireCluster],
        release_seconds: float = 3600.0,
        source_multiplier: float = 1.0,
    ) -> ParticleState:
        """
        Releases one batch of particles per cluster carrying the PM2.5 mass emitted over
        `release_seconds`: mass = emission_rate_kg_s * release_seconds * 1e9 ug/kg.
        """
        all_x, all_y, all_m, all_src = [], [], [], []

        for idx, fire in enumerate(fires):
            n_particles = self.particles_per_batch(fire)
            cx, cy = self.projection.to_metric(fire.centroid_lat, fire.centroid_lon)

            # Initial spatial distribution around fire complex (Gaussian radius ~3km)
            init_spread_m = 3000.0
            x_pts = cx + np.random.normal(0, init_spread_m, n_particles)
            y_pts = cy + np.random.normal(0, init_spread_m, n_particles)

            batch_mass_ug = fire.emission_rate_kg_s * release_seconds * 1e9 * source_multiplier
            m_pts = np.full(n_particles, batch_mass_ug / n_particles)

            all_x.append(x_pts)
            all_y.append(y_pts)
            all_m.append(m_pts)
            all_src.append(np.full(n_particles, idx))

        if not all_x:
            return ParticleState(np.array([]), np.array([]), np.array([]), np.array([]))

        m_arr = np.concatenate(all_m)
        return ParticleState(np.concatenate(all_x), np.concatenate(all_y), m_arr, m_arr.copy(),
                             source=np.concatenate(all_src))

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
        rain_mm_per_hr: float = None,
    ) -> Tuple[ParticleState, Dict[str, float]]:
        """
        Performs one integration step (dt):
          1. Deterministic wind advection: dx = u * dt, dy = v * dt
          2. Stochastic turbulent diffusion: sqrt(2 * K * dt) * N(0, 1)
          3. Mass decay: exponential atmospheric sink + rain washout
        Rain defaults to the forecast precipitation at elapsed_seconds.
        """
        if len(particles) == 0:
            return particles, {"decay_rate": self.config.decay_rate_lambda, "conc_before": 0.0, "conc_after": 0.0}

        mass_before = float(np.sum(particles.mass))
        if rain_mm_per_hr is None:
            rain_mm_per_hr = weather.get_precipitation_at(particles.x, particles.y, elapsed_seconds)

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

        # Rain washout where local precipitation exceeds 0.2 mm/h
        raining = np.asarray(rain_mm_per_hr) > 0.2
        particles.mass = np.where(raining, particles.mass * self.config.rain_washout_factor, particles.mass)

        # Prune dead particles (< 1% initial mass)
        alive_mask = particles.mass > (self.config.min_mass_threshold * np.median(particles.initial_mass))
        particles.x = particles.x[alive_mask]
        particles.y = particles.y[alive_mask]
        particles.mass = particles.mass[alive_mask]
        particles.initial_mass = particles.initial_mass[alive_mask]
        particles.source = particles.source[alive_mask]

        mass_after = float(np.sum(particles.mass))

        decay_stats = {
            "decay_rate": self.config.decay_rate_lambda,
            "concentration_before_decay": round(mass_before, 4),
            "concentration_after_decay": round(mass_after, 4),
        }

        return particles, decay_stats
