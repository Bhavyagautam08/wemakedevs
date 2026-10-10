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
from src.config import SimulationConfig


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
        config: SimulationConfig = None,
    ):
        self.projection = projection or LocalMetricProjection()
        self.config = config or SimulationConfig()
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

    def _mixing_height(self, particles: ParticleState) -> np.ndarray:
        """Per-particle mixing height (m), floored at min_mixing_height_m."""
        if particles.mixing_height_m is None:
            raise ValueError("ParticleState has no mixing_height_m; concentration needs the BLH at that time.")
        h = np.broadcast_to(np.asarray(particles.mixing_height_m, dtype=float), particles.x.shape)
        return np.maximum(h, self.config.min_mixing_height_m)

    def _volume_grid(self, particles: ParticleState):
        """Cell-mean concentration grid (ug/m^3): sum(m_i / H_i) / cell_area."""
        res = self.grid_res_m
        x_edges, y_edges, _ = self.concentration_grid(particles)
        grid, _, _ = np.histogram2d(particles.x, particles.y, bins=[x_edges, y_edges],
                                    weights=particles.mass / self._mixing_height(particles))
        return x_edges, y_edges, grid / (res * res)

    def sample_point_concentration(
        self,
        target_lat: float,
        target_lon: float,
        particles: ParticleState,
    ) -> float:
        """
        Surface PM2.5 smoke increment (ug/m^3) at a point, 2D box model:
        C = sum(m_i * exp(-r_i^2 / 2s^2) / (2*pi*s^2)) / H
        with s = kernel_sigma_m and H = mixing height of the snapshot.
        """
        if len(particles) == 0:
            return 0.0

        tx, ty = self.projection.to_metric(target_lat, target_lon)
        sigma = self.config.kernel_sigma_m
        dist_sq = (particles.x - tx) ** 2 + (particles.y - ty) ** 2
        near = dist_sq < (4.0 * sigma) ** 2
        if not np.any(near):
            return 0.0

        per_volume = particles.mass[near] / self._mixing_height(particles)[near]
        conc = float(np.sum(per_volume * np.exp(-dist_sq[near] / (2.0 * sigma ** 2)))) / (2.0 * math.pi * sigma ** 2)
        return round(conc, 2)

    def sample_concentrations(
        self,
        lats: np.ndarray,
        lons: np.ndarray,
        particles: ParticleState,
        chunk: int = 64,
    ) -> np.ndarray:
        """
        Vectorised sample_point_concentration for many points (ug/m^3), same kernel and box model.
        Points are processed in spatially compact chunks; each chunk only sees particles inside
        its bounding box grown by the kernel cutoff (4 sigma), which is exact for this kernel.
        """
        lats, lons = np.asarray(lats, dtype=float), np.asarray(lons, dtype=float)
        out = np.zeros(len(lats))
        if len(particles) == 0 or len(lats) == 0:
            return out
        tx, ty = self.projection.to_metric(lats, lons)
        sigma = self.config.kernel_sigma_m
        cutoff = (4.0 * sigma) ** 2
        norm = 1.0 / (2.0 * math.pi * sigma ** 2)
        per_volume = particles.mass / self._mixing_height(particles)
        reach = 4.0 * sigma
        order = np.lexsort((ty, np.floor(tx / 50_000.0)))  # 50 km strips, sorted north-south
        px, py = particles.x, particles.y
        for k in range(0, len(order), chunk):
            idx = order[k:k + chunk]
            cx, cy = tx[idx], ty[idx]
            near = (px > cx.min() - reach) & (px < cx.max() + reach) & (py > cy.min() - reach) & (py < cy.max() + reach)
            if not np.any(near):
                continue
            d2 = (cx[:, None] - px[near][None, :]) ** 2 + (cy[:, None] - py[near][None, :]) ** 2
            w = np.where(d2 < cutoff, np.exp(-d2 / (2.0 * sigma ** 2)), 0.0)
            out[idx] = (w @ per_volume[near]) * norm
        return np.round(out, 2)

    def impact_cells(self, particles: ParticleState, threshold_ugm3: float) -> set:
        """Global grid cell indices (ix, iy) whose cell-mean concentration >= threshold."""
        if len(particles) == 0:
            return set()
        x_edges, y_edges, grid = self._volume_grid(particles)
        res = self.grid_res_m
        ox, oy = int(round(x_edges[0] / res)), int(round(y_edges[0] / res))
        ix, iy = np.nonzero(grid >= threshold_ugm3)
        return {(int(a) + ox, int(b) + oy) for a, b in zip(ix, iy)}

    @staticmethod
    def _blobs(cells: set) -> List[List[Tuple[int, int]]]:
        """Splits grid cells into 8-connected components."""
        remaining, blobs = set(cells), []
        while remaining:
            stack = [remaining.pop()]
            blob = []
            while stack:
                c = stack.pop()
                blob.append(c)
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        n = (c[0] + dx, c[1] + dy)
                        if n in remaining:
                            remaining.remove(n)
                            stack.append(n)
            blobs.append(blob)
        return blobs

    def cells_to_bboxes(self, cells: set, pad_cells: int = 1) -> List[Tuple[float, float, float, float]]:
        """
        Groups grid cells into 8-connected blobs and returns one WGS84 bbox
        (min_lat, min_lon, max_lat, max_lon) per blob, padded by pad_cells.
        """
        res = self.grid_res_m
        boxes = []
        for blob in self._blobs(cells):
            xs = [c[0] for c in blob]
            ys = [c[1] for c in blob]
            x0, x1 = (min(xs) - pad_cells) * res, (max(xs) + 1 + pad_cells) * res
            y0, y1 = (min(ys) - pad_cells) * res, (max(ys) + 1 + pad_cells) * res
            lats, lons = self.projection.to_wgs84(np.array([x0, x1, x0, x1]), np.array([y0, y0, y1, y1]))
            boxes.append((float(np.min(lats)), float(np.min(lons)), float(np.max(lats)), float(np.max(lons))))
        return boxes

    def concentration_grid(
        self,
        particles: ParticleState,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Deposits particle mass onto a regular metric grid (cell size = grid_resolution_km).
        Returns (x_edges, y_edges, mass_per_cell) with mass_per_cell indexed [ix, iy].
        """
        if len(particles) == 0:
            raise ValueError("Cannot grid an empty particle cloud.")
        res = self.grid_res_m
        x0 = math.floor(float(np.min(particles.x)) / res) * res
        y0 = math.floor(float(np.min(particles.y)) / res) * res
        nx = max(1, int(math.ceil((float(np.max(particles.x)) - x0) / res)) + 1)
        ny = max(1, int(math.ceil((float(np.max(particles.y)) - y0) / res)) + 1)
        x_edges = x0 + res * np.arange(nx + 1)
        y_edges = y0 + res * np.arange(ny + 1)
        grid, _, _ = np.histogram2d(particles.x, particles.y, bins=[x_edges, y_edges], weights=particles.mass)
        return x_edges, y_edges, grid

    @staticmethod
    def _convex_hull(points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """Andrew's monotone chain. Returns hull vertices counter-clockwise, closed."""
        pts = sorted(set(points))
        if len(pts) < 3:
            return pts + pts[:1]

        def cross(o, a, b):
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

        lower, upper = [], []
        for p in pts:
            while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
                lower.pop()
            lower.append(p)
        for p in reversed(pts):
            while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
                upper.pop()
            upper.append(p)
        hull = lower[:-1] + upper[:-1]
        return hull + hull[:1]

    def extract_density_levels(
        self,
        particles: ParticleState,
        level_thresholds: List[Tuple[str, float]],
    ) -> Dict[str, Any]:
        """
        Grids the particle cloud into cell-mean concentration (ug/m^3, box model) and, for each
        (name, threshold_ugm3) level, returns one convex-hull ring (WGS84 [lon, lat]) per
        8-connected blob of cells at or above the threshold ("polygons", largest first),
        plus the summed area of those cells in km^2.
        """
        x_edges, y_edges, grid = self._volume_grid(particles)
        res = self.grid_res_m
        peak = float(np.max(grid))
        cell_area_km2 = (res / 1000.0) ** 2
        levels = {}
        for name, threshold in level_thresholds:
            ix, iy = np.nonzero(grid >= threshold)
            polygons = []
            for blob in sorted(self._blobs(set(zip(ix.tolist(), iy.tolist()))), key=len, reverse=True):
                corners = []
                for a, b in blob:
                    cx, cy = x_edges[a], y_edges[b]
                    corners += [(cx, cy), (cx + res, cy), (cx + res, cy + res), (cx, cy + res)]
                hull = self._convex_hull(corners)
                lats, lons = self.projection.to_wgs84(
                    np.array([p[0] for p in hull]), np.array([p[1] for p in hull])
                )
                polygons.append([[round(float(lo), 4), round(float(la), 4)] for la, lo in zip(lats, lons)])
            levels[name] = {
                "polygons": polygons,
                "cell_count": int(len(ix)),
                "area_sq_km": round(len(ix) * cell_area_km2, 1),
            }
        return {"peak_cell_ugm3": round(peak, 2), "levels": levels}

    def extract_contour_geojson(
        self,
        particles: ParticleState,
        threshold: float = 50.0,
        horizon_hours: int = 3,
    ) -> Dict[str, Any]:
        """
        Convex hull of grid cells with concentration >= threshold (ug/m^3), for map display.
        """
        if len(particles) < 5:
            return {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": []}, "properties": {}}

        result = self.extract_density_levels(particles, [("plume", threshold)])
        polygons = result["levels"]["plume"]["polygons"]
        return {
            "type": "Feature",
            "geometry": {"type": "MultiPolygon", "coordinates": [[ring] for ring in polygons]},
            "properties": {
                "layer_type": "plume_contour",
                "horizon_hours": horizon_hours,
                "particle_count": len(particles),
                "threshold_ugm3": threshold,
                "area_sq_km": result["levels"]["plume"]["area_sq_km"],
            },
        }
