"""
2D Gaussian Diffusion Field & Spatial Concentration Gridding
Transforms discrete particle clouds into a continuous 2D horizontal concentration field
C(x, y, t) and extracts contour polygons in GeoJSON format.
"""

import math
from typing import Dict, Any, List, Tuple
import numpy as np
from src.layer1_predictive.coordinates import LocalMetricProjection
from src.layer1_predictive.lagrangian_engine import ParticleState


class GaussianDiffusionField:
    """
    Evaluates 2D horizontal smoke concentration field C(x, y, t).
    Sigma spread follows: sigma^2(t) = sigma0^2 + 2 * K * t.
    """

    def __init__(
        self,
        projection: LocalMetricProjection = None,
        initial_sigma_m: float = 2000.0,
        grid_resolution_km: float = 5.5,  # 0.05 degree ~ 5.5 km
    ):
        self.projection = projection or LocalMetricProjection()
        self.initial_sigma_m = initial_sigma_m
        self.grid_res_m = grid_resolution_km * 1000.0

    def compute_gaussian_spread(
        self,
        t_seconds: float,
        kx: float,
        ky: float,
    ) -> Dict[str, float]:
        """
        Calculates theoretical Gaussian dispersion parameters over travel time:
        sigma_x^2(t) = sigma_0^2 + 2 * Kx * t
        """
        sig_x = math.sqrt((self.initial_sigma_m ** 2) + 2.0 * kx * t_seconds)
        sig_y = math.sqrt((self.initial_sigma_m ** 2) + 2.0 * ky * t_seconds)

        return {
            "sigma_x_meters": round(sig_x, 1),
            "sigma_y_meters": round(sig_y, 1),
            "kx_effective": round(kx, 1),
            "ky_effective": round(ky, 1),
            "initial_spread_meters": self.initial_sigma_m,
            "spread_ratio_over_time": round(sig_x / self.initial_sigma_m, 2),
        }

    def sample_point_concentration(
        self,
        target_lat: float,
        target_lon: float,
        particles: ParticleState,
        search_radius_m: float = 12000.0,
    ) -> float:
        """
        Evaluates concentration at an exact coordinate (e.g. school location)
        using Gaussian kernel density estimation over surrounding particles.
        """
        if len(particles) == 0:
            return 0.0

        tx, ty = self.projection.to_metric(target_lat, target_lon)

        # Distance from target to all particles
        dx = particles.x - tx
        dy = particles.y - ty
        dist_sq = (dx ** 2) + (dy ** 2)

        # Consider particles within radius
        in_radius = dist_sq < (search_radius_m ** 2)
        if not np.any(in_radius):
            return 0.0

        # Gaussian smoothing kernel
        sigma_m = 4000.0
        weights = particles.mass[in_radius] * np.exp(-dist_sq[in_radius] / (2.0 * (sigma_m ** 2)))
        raw_val = float(np.sum(weights))

        # Scaled to [0.0 - 1.0] relative index
        scaled = np.clip(raw_val * 450.0, 0.0, 1.0)
        return float(round(scaled, 3))

    def _coverage_hull(self, particles: ParticleState, coverage_fraction: float) -> np.ndarray:
        """Return the convex hull of the requested mass-weighted particle-cloud coverage."""
        if not 0.0 < coverage_fraction <= 1.0:
            raise ValueError("CONTOUR_CONFIGURATION_ERROR: coverage_fraction must be in (0, 1].")
        if len(particles) < 3 or float(np.sum(particles.mass)) <= 0.0:
            return np.empty((0, 2))

        center_x = float(np.average(particles.x, weights=particles.mass))
        center_y = float(np.average(particles.y, weights=particles.mass))
        radius_sq = (particles.x - center_x) ** 2 + (particles.y - center_y) ** 2
        radius_limit = float(np.quantile(radius_sq, coverage_fraction))
        selected = np.column_stack((particles.x[radius_sq <= radius_limit], particles.y[radius_sq <= radius_limit]))
        points = sorted({(float(x), float(y)) for x, y in selected})
        if len(points) < 3:
            return np.empty((0, 2))

        def cross(origin, point_a, point_b):
            return (
                (point_a[0] - origin[0]) * (point_b[1] - origin[1])
                - (point_a[1] - origin[1]) * (point_b[0] - origin[0])
            )

        lower, upper = [], []
        for point in points:
            while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
                lower.pop()
            lower.append(point)
        for point in reversed(points):
            while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
                upper.pop()
            upper.append(point)
        return np.asarray(lower[:-1] + upper[:-1], dtype=np.float64)

    def extract_contour_geojson(
        self,
        particles: ParticleState,
        coverage_fraction: float = 0.90,
    ) -> Dict[str, Any]:
        """Build a plume polygon from actual particle positions, never a bounding rectangle."""
        hull = self._coverage_hull(particles, coverage_fraction)
        if len(hull) < 3:
            return {"type": "Polygon", "coordinates": []}

        lats, lons = self.projection.to_wgs84(hull[:, 0], hull[:, 1])
        coordinates = [[round(float(lon), 6), round(float(lat), 6)] for lat, lon in zip(lats, lons)]
        coordinates.append(coordinates[0])
        return {"type": "Polygon", "coordinates": [coordinates]}

    def plume_area_sq_km(self, particles: ParticleState, coverage_fraction: float = 0.90) -> float:
        """Calculate the displayed particle-hull footprint in square kilometres."""
        hull = self._coverage_hull(particles, coverage_fraction)
        if len(hull) < 3:
            return 0.0
        x_coords, y_coords = hull[:, 0], hull[:, 1]
        area_m2 = 0.5 * abs(
            np.dot(x_coords, np.roll(y_coords, -1)) - np.dot(y_coords, np.roll(x_coords, -1))
        )
        return round(float(area_m2 / 1_000_000.0), 2)
