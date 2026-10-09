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

    def extract_contour_geojson(
        self,
        particles: ParticleState,
        threshold: float = 0.25,
        horizon_hours: int = 3,
    ) -> Dict[str, Any]:
        """
        Extracts a convex/envelope polygon around active plume particles for map display.
        """
        if len(particles) < 5:
            return {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": []}, "properties": {}}

        # Sample particle envelope
        step = max(1, len(particles) // 200)
        sample_x = particles.x[::step]
        sample_y = particles.y[::step]

        # Convert boundary particles back to WGS84
        lats, lons = self.projection.to_wgs84(sample_x, sample_y)

        # Compute simple bounding envelope
        min_lon, max_lon = float(np.min(lons)), float(np.max(lons))
        min_lat, max_lat = float(np.min(lats)), float(np.max(lats))

        # Add polygon coordinates
        coords = [
            [round(min_lon, 4), round(min_lat, 4)],
            [round(max_lon, 4), round(min_lat, 4)],
            [round(max_lon, 4), round(max_lat, 4)],
            [round(min_lon, 4), round(max_lat, 4)],
            [round(min_lon, 4), round(min_lat, 4)],
        ]

        return {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [coords],
            },
            "properties": {
                "layer_type": "plume_contour",
                "horizon_hours": horizon_hours,
                "particle_count": len(particles),
                "threshold": threshold,
            },
        }
