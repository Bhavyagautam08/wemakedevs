"""
Local Metric Coordinate System (East/North in meters)
Converts WGS84 geographic coordinates (lat, lon) to a local planar metric CRS
and back. All physical particle advection and turbulent diffusion are calculated
strictly in meters to maintain physical fidelity.
"""

import math
from typing import Tuple, List, Union
import numpy as np


class LocalMetricProjection:
    """
    Local Equirectangular / Transverse projection centered around North India.
    1 degree latitude ~= 111,139 meters.
    1 degree longitude ~= 111,139 * cos(origin_lat) meters.
    """

    def __init__(self, origin_lat: float = 29.5, origin_lon: float = 76.5):
        self.origin_lat = origin_lat
        self.origin_lon = origin_lon
        self.rad_lat = math.radians(origin_lat)
        self.meters_per_deg_lat = 111139.0
        self.meters_per_deg_lon = 111139.0 * math.cos(self.rad_lat)

    def to_metric(self, lat: Union[float, np.ndarray], lon: Union[float, np.ndarray]) -> Tuple[Union[float, np.ndarray], Union[float, np.ndarray]]:
        """Converts (lat, lon) in degrees to (x, y) in meters relative to origin."""
        x = (lon - self.origin_lon) * self.meters_per_deg_lon
        y = (lat - self.origin_lat) * self.meters_per_deg_lat
        return x, y

    def to_wgs84(self, x: Union[float, np.ndarray], y: Union[float, np.ndarray]) -> Tuple[Union[float, np.ndarray], Union[float, np.ndarray]]:
        """Converts (x, y) in meters back to (lat, lon) in degrees WGS84."""
        lon = self.origin_lon + (x / self.meters_per_deg_lon)
        lat = self.origin_lat + (y / self.meters_per_deg_lat)
        return lat, lon

    def distance_km(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Computes Euclidean distance in kilometers between two points."""
        x1, y1 = self.to_metric(lat1, lon1)
        x2, y2 = self.to_metric(lat2, lon2)
        dist_m = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        return round(dist_m / 1000.0, 2)
