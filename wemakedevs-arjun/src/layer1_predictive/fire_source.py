"""
Fire Source & Hotspot Clustering Model
Clusters NASA FIRMS / VIIRS active fire hotspots into discrete fire events and
calculates a relative source/emission strength proxy [0.0 - 1.0].
"""

import math
from typing import List, Dict, Any
from datetime import datetime
import numpy as np
from src.types import Hotspot, FireCluster
from src.layer1_predictive.coordinates import LocalMetricProjection


class FireSourceModel:
    """
    Groups raw satellite detections into coherent fire complexes and estimates
    relative smoke emission strength. Pluggable for future ML calibration.
    """

    def __init__(self, cluster_radius_km: float = 12.0, projection: LocalMetricProjection = None):
        self.cluster_radius_km = cluster_radius_km
        self.projection = projection or LocalMetricProjection()

    def cluster_hotspots(self, hotspots: List[Hotspot], current_time: datetime = None) -> List[FireCluster]:
        """
        Clusters hotspots within geographic radius and computes cluster attributes.
        """
        if not hotspots:
            return []

        now = current_time or datetime.utcnow()
        clusters: List[List[Hotspot]] = []
        visited = set()

        # Spatial clustering via neighborhood grouping
        for i, h1 in enumerate(hotspots):
            if i in visited:
                continue
            current_group = [h1]
            visited.add(i)

            for j, h2 in enumerate(hotspots):
                if j in visited:
                    continue
                d = self.projection.distance_km(h1.latitude, h1.longitude, h2.latitude, h2.longitude)
                if d <= self.cluster_radius_km:
                    current_group.append(h2)
                    visited.add(j)

            clusters.append(current_group)

        # Synthesize FireCluster objects
        result: List[FireCluster] = []
        for idx, group in enumerate(clusters):
            count = len(group)
            total_frp = sum(h.frp for h in group)
            avg_conf = sum(h.confidence for h in group) / count
            latest_time = max(h.acq_timestamp for h in group)

            # Simple centroid
            mean_lat = sum(h.latitude for h in group) / count
            mean_lon = sum(h.longitude for h in group) / count

            # FRP-weighted centroid (reflects fire core)
            if total_frp > 0:
                w_lat = sum(h.latitude * h.frp for h in group) / total_frp
                w_lon = sum(h.longitude * h.frp for h in group) / total_frp
            else:
                w_lat, w_lon = mean_lat, mean_lon

            now_naive = now.replace(tzinfo=None)
            latest_naive = latest_time.replace(tzinfo=None)
            freshness_hours = max(0.0, (now_naive - latest_naive).total_seconds() / 3600.0)

            # Estimate source strength [0.0 - 1.0]
            # Combination of total FRP, hotspot density, confidence, and freshness decay
            source_strength = self.estimate_source_strength(
                hotspot_count=count,
                total_frp=total_frp,
                confidence=avg_conf,
                freshness_hours=freshness_hours,
            )

            result.append(
                FireCluster(
                    fire_id=f"fire_cluster_{idx+1:03d}",
                    centroid_lat=round(mean_lat, 4),
                    centroid_lon=round(mean_lon, 4),
                    hotspot_count=count,
                    weighted_centroid={"lat": round(w_lat, 4), "lon": round(w_lon, 4)},
                    latest_detection_time=latest_time,
                    confidence_summary=round(avg_conf, 1),
                    frp_summary=round(total_frp, 1),
                    source_strength=round(source_strength, 3),
                    source_freshness_hours=round(freshness_hours, 2),
                    status="ACTIVE" if freshness_hours < 12.0 else "AGED",
                )
            )

        return sorted(result, key=lambda c: c.source_strength, reverse=True)

    def estimate_source_strength(
        self, hotspot_count: int, total_frp: float, confidence: float, freshness_hours: float
    ) -> float:
        """
        Calculates a relative source emission strength proxy.
        Formula:
          - FRP scaling: logarithmic saturation (500 MW ~ 0.7, 2000 MW ~ 0.95)
          - Confidence scaling: 0.5 to 1.0 multiplier
          - Recency decay: e^(-0.15 * hours)
        """
        # 1. Base FRP proxy
        frp_factor = 1.0 - math.exp(-total_frp / 600.0)

        # 2. Hotspot cluster density factor
        density_factor = min(1.0, 0.2 + (hotspot_count * 0.05))

        # 3. Confidence weighting
        conf_factor = max(0.5, confidence / 100.0)

        # 4. Temporal freshness decay
        recency_factor = math.exp(-0.10 * freshness_hours)

        raw_strength = 0.60 * frp_factor + 0.40 * density_factor
        adjusted = raw_strength * conf_factor * recency_factor
        return float(np.clip(adjusted, 0.05, 1.0))
