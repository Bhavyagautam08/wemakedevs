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
from src.config import SimulationConfig
from src.layer1_predictive.coordinates import LocalMetricProjection


class FireSourceModel:
    """
    Groups raw satellite detections into coherent fire complexes and estimates
    relative smoke emission strength. Pluggable for future ML calibration.
    """

    def __init__(
        self,
        cluster_radius_km: float = 12.0,
        projection: LocalMetricProjection = None,
        config: SimulationConfig = None,
    ):
        self.cluster_radius_km = cluster_radius_km
        self.projection = projection or LocalMetricProjection()
        self.config = config or SimulationConfig()

    def _single_linkage_groups(self, hotspots: List[Hotspot]) -> List[List[int]]:
        """
        Connected components of the graph linking hotspots <= cluster_radius_km apart
        (single linkage). Independent of input order. Uses a grid hash so only
        neighbouring cells are compared.
        """
        r = self.cluster_radius_km * 1000.0
        xs, ys = self.projection.to_metric(
            np.array([h.latitude for h in hotspots]), np.array([h.longitude for h in hotspots])
        )
        parent = list(range(len(hotspots)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        cells: Dict[tuple, List[int]] = {}
        for i, (x, y) in enumerate(zip(xs, ys)):
            cells.setdefault((int(x // r), int(y // r)), []).append(i)
        for (cx, cy), members in cells.items():
            neighbours = [j for dx in (-1, 0, 1) for dy in (-1, 0, 1) for j in cells.get((cx + dx, cy + dy), [])]
            for i in members:
                for j in neighbours:
                    if j > i and (xs[i] - xs[j]) ** 2 + (ys[i] - ys[j]) ** 2 <= r * r:
                        parent[find(i)] = find(j)

        groups: Dict[int, List[int]] = {}
        for i in range(len(hotspots)):
            groups.setdefault(find(i), []).append(i)
        # Deterministic order: by earliest detection id within each group
        return sorted(groups.values(), key=lambda g: min(hotspots[i].detection_id for i in g))

    def cluster_hotspots(self, hotspots: List[Hotspot], current_time: datetime = None) -> List[FireCluster]:
        """
        Clusters hotspots within geographic radius and computes cluster attributes.
        """
        if not hotspots:
            return []

        now = current_time or datetime.utcnow()
        clusters = [[hotspots[i] for i in g] for g in self._single_linkage_groups(hotspots)]

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
                    emission_rate_kg_s=round(self.estimate_emission_rate(group, now), 4),
                    source_freshness_hours=round(freshness_hours, 2),
                    status="ACTIVE" if freshness_hours < 12.0 else "AGED",
                )
            )

        return sorted(result, key=lambda c: c.emission_rate_kg_s, reverse=True)

    def estimate_emission_rate(self, group: List[Hotspot], now: datetime) -> float:
        """
        PM2.5 emission rate at T0 in kg/s: sum over detections of
        Ce * FRP_i * exp(-age_i / fire_persistence_efold_hours).
        """
        ce = self.config.smoke_emission_coefficient_kg_per_mj
        tau = self.config.fire_persistence_efold_hours
        now_naive = now.replace(tzinfo=None)
        total = 0.0
        for h in group:
            age_h = max(0.0, (now_naive - h.acq_timestamp.replace(tzinfo=None)).total_seconds() / 3600.0)
            total += ce * h.frp * math.exp(-age_h / tau)
        return total

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
