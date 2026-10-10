"""
2D Atmospheric Weather & Vector Wind Field
Represents wind u(x, y, t), v(x, y, t), Boundary Layer Height and precipitation from
hourly forecast series at one or more grid points ("stations").

Time:  linear interpolation between the bracketing hourly records of each station.
Space: inverse-distance weighting (power 2) between stations, precomputed on a 25 km
       raster and sampled bilinearly. Observations without latitude/longitude form a
       single station, i.e. a spatially uniform field.
"""

import math
from typing import List, Tuple, Dict
from datetime import datetime
import numpy as np
from src.types import WeatherObservation
from src.config import SimulationConfig
from src.layer1_predictive.coordinates import LocalMetricProjection


class WeatherDataRangeError(ValueError):
    """Raised when the simulation asks for weather outside the fetched forecast window."""


class WeatherVectorField:
    IDW_POWER = 2.0
    IDW_MIN_DISTANCE_M = 1000.0
    # With many stations the IDW field is precomputed on a raster and sampled bilinearly,
    # instead of computing particle-to-station distances every step.
    RASTER_RES_M = 25_000.0
    RASTER_MARGIN_M = 300_000.0

    def __init__(
        self,
        observations: List[WeatherObservation],
        start_time: datetime,
        projection: LocalMetricProjection = None,
        config: SimulationConfig = None,
    ):
        if not observations:
            raise ValueError("INSUFFICIENT_DATA: No weather observations supplied to the wind field.")
        if start_time.tzinfo is None:
            raise ValueError("start_time must be timezone-aware (UTC).")

        self.projection = projection or LocalMetricProjection()
        self.config = config or SimulationConfig()
        self.start_time = start_time

        groups: Dict[Tuple, List[WeatherObservation]] = {}
        for o in observations:
            key = (o.latitude, o.longitude) if o.latitude is not None and o.longitude is not None else (None, None)
            groups.setdefault(key, []).append(o)
        if (None, None) in groups and len(groups) > 1:
            raise ValueError("Weather observations mix located and unlocated records.")

        self.stations = []
        for (lat, lon), obs in groups.items():
            obs = sorted(obs, key=lambda o: o.forecast_timestamp)
            if lat is None:
                sx, sy = 0.0, 0.0
            else:
                sx, sy = self.projection.to_metric(lat, lon)
            self.stations.append({
                "lat": lat, "lon": lon, "x": float(sx), "y": float(sy),
                "first": obs[0].forecast_timestamp, "last": obs[-1].forecast_timestamp,
                "t": np.array([(o.forecast_timestamp - start_time).total_seconds() for o in obs]),
                "u": np.array([o.u_mps for o in obs]),
                "v": np.array([o.v_mps for o in obs]),
                "blh": np.array([o.boundary_layer_height_m for o in obs]),
                "precip": np.array([o.precipitation_mm or 0.0 for o in obs]),
            })
        self._sx = np.array([s["x"] for s in self.stations])
        self._sy = np.array([s["y"] for s in self.stations])
        # Kept for reporting (single-station callers)
        self.observations = sorted(observations, key=lambda o: o.forecast_timestamp)
        self._grid_cache: Dict[Tuple[str, float], np.ndarray] = {}
        self._raster = self._build_raster() if len(self.stations) > 1 else None

    def _build_raster(self):
        """IDW weights from every raster node to every station: grid_values = W @ station_values."""
        res, m = self.RASTER_RES_M, self.RASTER_MARGIN_M
        x0, y0 = self._sx.min() - m, self._sy.min() - m
        nx = int(np.ceil((self._sx.max() + m - x0) / res)) + 1
        ny = int(np.ceil((self._sy.max() + m - y0) / res)) + 1
        gx, gy = np.meshgrid(x0 + res * np.arange(nx), y0 + res * np.arange(ny), indexing="ij")
        gx, gy = gx.ravel(), gy.ravel()
        d = np.sqrt((gx[:, None] - self._sx[None, :]) ** 2 + (gy[:, None] - self._sy[None, :]) ** 2)
        w = 1.0 / np.maximum(d, self.IDW_MIN_DISTANCE_M) ** self.IDW_POWER
        w /= w.sum(axis=1, keepdims=True)
        return {"x0": x0, "y0": y0, "nx": nx, "ny": ny, "W": w.astype(np.float32)}

    @property
    def station_count(self) -> int:
        return len(self.stations)

    def coverage_seconds(self) -> Tuple[float, float]:
        """Window (relative to start_time) covered by EVERY station."""
        return max(float(s["t"][0]) for s in self.stations), min(float(s["t"][-1]) for s in self.stations)

    def require_coverage(self, horizon_seconds: float) -> None:
        """Fails loudly unless every station spans [0, horizon_seconds]."""
        lo, hi = self.coverage_seconds()
        if lo > 0.0 or hi < horizon_seconds:
            first = max(s["first"] for s in self.stations)
            last = min(s["last"] for s in self.stations)
            raise WeatherDataRangeError(
                f"WEATHER_RANGE_INSUFFICIENT: forecast covers {first.isoformat()} to {last.isoformat()}, "
                f"but the simulation needs {self.start_time.isoformat()} + {horizon_seconds / 3600.0:.1f}h."
            )

    def _station_values(self, key: str, t: float) -> np.ndarray:
        lo, hi = self.coverage_seconds()
        if t < lo or t > hi:
            raise WeatherDataRangeError(
                f"WEATHER_RANGE_INSUFFICIENT: t=+{t / 3600.0:.2f}h is outside the forecast window "
                f"[{lo / 3600.0:+.2f}h, {hi / 3600.0:+.2f}h] relative to run start."
            )
        return np.array([float(np.interp(t, s["t"], s[key])) for s in self.stations])

    def _field(self, key: str, t: float, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        """Field `key` at positions (x, y) and time t: IDW between stations, bilinear on the raster."""
        x, y = np.atleast_1d(np.asarray(x, dtype=float)), np.atleast_1d(np.asarray(y, dtype=float))
        if self._raster is None:
            return np.full(len(x), self._station_values(key, t)[0])
        r = self._raster
        grid = self._grid_cache.get((key, t))
        if grid is None:
            grid = (r["W"] @ self._station_values(key, t).astype(np.float32)).reshape(r["nx"], r["ny"]).astype(float)
            self._grid_cache[(key, t)] = grid
        fx = np.clip((x - r["x0"]) / self.RASTER_RES_M, 0, r["nx"] - 1.000001)
        fy = np.clip((y - r["y0"]) / self.RASTER_RES_M, 0, r["ny"] - 1.000001)
        i, j = fx.astype(int), fy.astype(int)
        ax, ay = fx - i, fy - j
        return (grid[i, j] * (1 - ax) * (1 - ay) + grid[i + 1, j] * ax * (1 - ay)
                + grid[i, j + 1] * (1 - ax) * ay + grid[i + 1, j + 1] * ax * ay)

    def get_wind_vector(
        self,
        x_meters: np.ndarray,
        y_meters: np.ndarray,
        time_elapsed_seconds: float = 0.0,
        speed_factor: float = 1.0,
        dir_shift_deg: float = 0.0,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        (u, v) wind in m/s at each particle position and time t. Ensemble perturbations scale
        the speed and rotate the direction the wind blows FROM by dir_shift_deg (clockwise).
        """
        u = self._field("u", time_elapsed_seconds, x_meters, y_meters) * speed_factor
        v = self._field("v", time_elapsed_seconds, x_meters, y_meters) * speed_factor
        if dir_shift_deg:
            # Rotating "from" direction clockwise by a rotates the vector clockwise by a
            a = math.radians(dir_shift_deg)
            u, v = u * math.cos(a) + v * math.sin(a), -u * math.sin(a) + v * math.cos(a)
        return u, v

    def get_blh_at(self, x_meters: np.ndarray, y_meters: np.ndarray, time_elapsed_seconds: float,
                   blh_factor: float = 1.0) -> np.ndarray:
        """Boundary layer height (m) at each position and time t."""
        return self._field("blh", time_elapsed_seconds, x_meters, y_meters) * blh_factor

    def get_precipitation_at(self, x_meters: np.ndarray, y_meters: np.ndarray, time_elapsed_seconds: float) -> np.ndarray:
        """Hourly precipitation (mm/h) at each position and time t."""
        return self._field("precip", time_elapsed_seconds, x_meters, y_meters)

    def get_blh_and_diffusivity(
        self,
        time_elapsed_seconds: float = 0.0,
        blh_factor: float = 1.0,
        diff_factor: float = 1.0,
    ) -> Tuple[float, float, float]:
        """
        Returns (station-mean BLH in m, Kx, Ky in m^2/s) at time t. Horizontal diffusivity
        comes from SimulationConfig scaled by the ensemble factor.
        """
        blh = float(np.mean(self._station_values("blh", time_elapsed_seconds))) * blh_factor
        kx = self.config.base_diffusion_kx * diff_factor
        ky = self.config.base_diffusion_ky * diff_factor
        return blh, float(kx), float(ky)

    def get_precipitation(self, time_elapsed_seconds: float = 0.0) -> float:
        """Station-mean precipitation (mm/h) at time t."""
        return float(np.mean(self._station_values("precip", time_elapsed_seconds)))
