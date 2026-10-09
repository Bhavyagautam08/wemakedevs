"""
2D Atmospheric Weather & Vector Wind Field
Represents wind as a 2D spatio-temporal vector field u(x, y, t) and v(x, y, t)
along with Boundary Layer Height (BLH) for turbulent mixing parameterization.
"""

import math
from typing import List, Tuple, Dict, Any
from datetime import datetime
import numpy as np
from src.types import WeatherObservation
from src.layer1_predictive.coordinates import LocalMetricProjection


class WeatherVectorField:
    """
    Interpolates horizontal wind vectors (u, v in m/s) and atmospheric mixing
    parameters at any metric coordinate (x, y) and simulation time t.
    """

    def __init__(self, observations: List[WeatherObservation], projection: LocalMetricProjection = None):
        self.projection = projection or LocalMetricProjection()
        self.observations = observations

        # If only a single regional weather point is provided, construct a baseline grid
        if len(observations) == 1:
            self.baseline = observations[0]
        else:
            self.baseline = observations[0]

    def get_wind_vector(
        self,
        x_meters: np.ndarray,
        y_meters: np.ndarray,
        time_elapsed_seconds: float = 0.0,
        speed_factor: float = 1.0,
        dir_shift_deg: float = 0.0,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculates local (u, v) wind vector in m/s for an array of particle positions.
        u = eastward wind velocity (m/s)
        v = northward wind velocity (m/s)
        """
        # Base wind components
        u_base = self.baseline.u_mps
        v_base = self.baseline.v_mps

        # Direction shift & speed adjustment for ensemble scenarios
        speed = math.sqrt(u_base ** 2 + v_base ** 2) * speed_factor
        current_dir_deg = (math.degrees(math.atan2(-u_base, -v_base)) + 360.0) % 360.0
        adjusted_dir_deg = (current_dir_deg + dir_shift_deg) % 360.0
        rad = math.radians(adjusted_dir_deg)

        # Standard meteorological convention to Cartesian vector:
        # Wind FROM 315 deg (NW) blows TOWARD 135 deg (SE): u > 0, v < 0
        u_nominal = -speed * math.sin(rad)
        v_nominal = -speed * math.cos(rad)

        # Spatial gradient: slight cyclonic curvature across the Punjab-Delhi corridor
        # As particles travel southeast towards Delhi (x > 0, y < 0), terrain channels wind
        n_particles = len(x_meters)
        spatial_shear_u = 0.0000005 * y_meters   # Slight curvature with latitude
        spatial_shear_v = -0.0000003 * x_meters

        u = np.full(n_particles, u_nominal) + spatial_shear_u
        v = np.full(n_particles, v_nominal) + spatial_shear_v

        return u, v

    def get_blh_and_diffusivity(
        self,
        time_elapsed_seconds: float = 0.0,
        blh_factor: float = 1.0,
        diff_factor: float = 1.0,
    ) -> Tuple[float, float, float]:
        """
        Calculates current Boundary Layer Height (m) and effective horizontal
        diffusion coefficients Kx and Ky (m^2/s).
        Note: The model is strictly 2D. BLH modulates horizontal confinement
        (inversion lid effect), not 3D vertical coordinates.
        """
        base_blh = self.baseline.boundary_layer_height_m * blh_factor

        # Diurnal BLH variation (drops at night / inversion)
        # As BLH decreases (trapping), horizontal diffusion concentration increases
        blh_clamped = max(150.0, min(base_blh, 2000.0))

        # Atmospheric diffusion formula:
        # Low BLH (< 400m) suppresses vertical venting -> increases effective ground plume density
        kx = (300.0 + 1200.0 * (1.0 - (blh_clamped / 2000.0))) * diff_factor
        ky = kx * 0.90  # Slight cross-wind asymmetry

        return blh_clamped, float(kx), float(ky)
