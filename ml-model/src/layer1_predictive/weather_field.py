"""
2D Atmospheric Weather & Vector Wind Field
Represents wind as a 2D spatio-temporal vector field u(x, y, t) and v(x, y, t)
along with Boundary Layer Height (BLH) for turbulent mixing parameterization.
"""

import math
from bisect import bisect_right
from datetime import datetime, timedelta, timezone
from typing import List, Tuple
import numpy as np
from src.types import WeatherObservation
from src.layer1_predictive.coordinates import LocalMetricProjection


class WeatherVectorField:
    """
    Interpolates horizontal wind vectors (u, v in m/s) and atmospheric mixing
    parameters at any metric coordinate (x, y) and simulation time t.
    """

    def __init__(
        self,
        observations: List[WeatherObservation],
        simulation_start_time: datetime,
        projection: LocalMetricProjection = None,
    ):
        self.projection = projection or LocalMetricProjection()
        if not observations:
            raise ValueError("WEATHER_COVERAGE_ERROR: at least one weather observation is required.")
        if simulation_start_time.tzinfo is None:
            raise ValueError("WEATHER_COVERAGE_ERROR: simulation_start_time must be timezone-aware.")

        normalized_observations = []
        for observation in observations:
            if observation.forecast_timestamp.tzinfo is None:
                raise ValueError(
                    "WEATHER_COVERAGE_ERROR: weather observation timestamps must be timezone-aware."
                )
            normalized_observations.append(observation)

        self.observations = sorted(
            normalized_observations,
            key=lambda observation: observation.forecast_timestamp.astimezone(timezone.utc),
        )
        self.simulation_start_time = simulation_start_time.astimezone(timezone.utc)
        self._timestamps = [
            observation.forecast_timestamp.astimezone(timezone.utc)
            for observation in self.observations
        ]
        if len(set(self._timestamps)) != len(self._timestamps):
            raise ValueError(
                "WEATHER_COVERAGE_ERROR: duplicate forecast timestamps make interpolation ambiguous."
            )

    def _interpolate_weather(self, time_elapsed_seconds: float) -> Tuple[float, float, float]:
        """Return linearly interpolated u, v, and BLH at a simulation offset."""
        if not math.isfinite(time_elapsed_seconds) or time_elapsed_seconds < 0:
            raise ValueError(
                "WEATHER_COVERAGE_ERROR: time_elapsed_seconds must be a finite, non-negative value."
            )

        requested_timestamp = self.simulation_start_time + timedelta(seconds=time_elapsed_seconds)
        first_timestamp = self._timestamps[0]
        last_timestamp = self._timestamps[-1]
        if requested_timestamp < first_timestamp or requested_timestamp > last_timestamp:
            raise ValueError(
                "WEATHER_COVERAGE_ERROR: simulation timestamp "
                f"{requested_timestamp.isoformat()} is outside supplied forecast coverage "
                f"[{first_timestamp.isoformat()}, {last_timestamp.isoformat()}]."
            )

        upper_index = bisect_right(self._timestamps, requested_timestamp)
        if upper_index == 0:
            observation = self.observations[0]
            return observation.u_mps, observation.v_mps, observation.boundary_layer_height_m
        if upper_index == len(self.observations):
            observation = self.observations[-1]
            return observation.u_mps, observation.v_mps, observation.boundary_layer_height_m

        lower_index = upper_index - 1
        lower = self.observations[lower_index]
        upper = self.observations[upper_index]
        span_seconds = (self._timestamps[upper_index] - self._timestamps[lower_index]).total_seconds()
        fraction = (requested_timestamp - self._timestamps[lower_index]).total_seconds() / span_seconds

        u_mps = lower.u_mps + ((upper.u_mps - lower.u_mps) * fraction)
        v_mps = lower.v_mps + ((upper.v_mps - lower.v_mps) * fraction)
        blh_m = lower.boundary_layer_height_m + (
            (upper.boundary_layer_height_m - lower.boundary_layer_height_m) * fraction
        )
        return u_mps, v_mps, blh_m

    def ensure_coverage(self, duration_seconds: float) -> None:
        """Fail before simulation when the supplied forecast cannot span its horizon."""
        self._interpolate_weather(0.0)
        self._interpolate_weather(duration_seconds)

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
        u_base, v_base, _ = self._interpolate_weather(time_elapsed_seconds)

        # Direction shift & speed adjustment for ensemble scenarios
        speed = math.sqrt(u_base ** 2 + v_base ** 2) * speed_factor
        current_dir_deg = (math.degrees(math.atan2(-u_base, -v_base)) + 360.0) % 360.0
        adjusted_dir_deg = (current_dir_deg + dir_shift_deg) % 360.0
        rad = math.radians(adjusted_dir_deg)

        # Standard meteorological convention to Cartesian vector:
        # Wind FROM 315 deg (NW) blows TOWARD 135 deg (SE): u > 0, v < 0
        u_nominal = -speed * math.sin(rad)
        v_nominal = -speed * math.cos(rad)

        # This field contains temporal interpolation only. A spatial wind gradient must
        # come from an observed gridded forecast, not uncalibrated synthetic shear.
        n_particles = len(x_meters)
        u = np.full(n_particles, u_nominal)
        v = np.full(n_particles, v_nominal)

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
        _, _, interpolated_blh = self._interpolate_weather(time_elapsed_seconds)
        base_blh = interpolated_blh * blh_factor

        # Diurnal BLH variation (drops at night / inversion)
        # As BLH decreases (trapping), horizontal diffusion concentration increases
        blh_clamped = max(150.0, min(base_blh, 2000.0))

        # Atmospheric diffusion formula:
        # Low BLH (< 400m) suppresses vertical venting -> increases effective ground plume density
        kx = (300.0 + 1200.0 * (1.0 - (blh_clamped / 2000.0))) * diff_factor
        ky = kx * 0.90  # Slight cross-wind asymmetry

        return blh_clamped, float(kx), float(ky)
