"""
OpenStreetMap School Ingestion Module
Fetches schools (amenity=school) from the OpenStreetMap Overpass API inside the areas a
forecast plume actually reaches. The bundled ncr_schools.json is only a small offline
reference list used by tests and the /v1/data/schools endpoint.
"""

import os
import json
import time
import logging
import urllib.parse
import urllib.request
import urllib.error
from typing import List, Tuple
from src.types import School

logger = logging.getLogger("dhuanalert.schools")

# (min_lat, min_lon, max_lat, max_lon)
BBox = Tuple[float, float, float, float]


class OsmSchoolClient:
    """
    Live school geodata from OpenStreetMap (Overpass API). Fails loudly on any error;
    there is no fallback to the bundled list.
    """

    # Overpass rejects heavy queries when busy; a modest server-side timeout is accepted more often.
    QUERY_TIMEOUT_S = 25
    RETRY_DELAYS_S = (5, 15)  # same server, on HTTP 429 / 504 only

    def __init__(self, base_url: str = None, timeout_s: int = 60):
        self.base_url = base_url or os.environ.get("OVERPASS_API_URL", "https://overpass-api.de/api/interpreter")
        self.timeout_s = timeout_s

    TILE_DEG = 0.5
    TILE_TTL_S = 7 * 24 * 3600   # schools rarely change; refresh weekly
    TILES_PER_QUERY = 40

    def _cache_dir(self) -> str:
        d = os.environ.get(
            "DHUANALERT_CACHE_DIR_OSM",
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "output", "cache", "osm_schools"),
        )
        os.makedirs(d, exist_ok=True)
        return d

    def fetch_schools_in_bboxes(self, bboxes: List[BBox], india_only: bool = True) -> List[School]:
        """
        Returns all OSM schools (nodes and ways/relations by centre) inside any of the bboxes;
        with india_only (default) schools outside India's boundary are dropped. Results are
        cached per 0.5-degree tile, so repeated runs only query tiles not seen recently.
        """
        if not bboxes:
            return []
        import math as _m
        t = self.TILE_DEG
        tiles = set()
        for (s_, w, n, e) in bboxes:
            for i in range(_m.floor(s_ / t), _m.floor(n / t) + 1):
                for j in range(_m.floor(w / t), _m.floor(e / t) + 1):
                    tiles.add((i, j))

        cache = self._cache_dir()
        by_tile = {}
        missing = []
        for tile in tiles:
            path = os.path.join(cache, f"{tile[0]}_{tile[1]}.json")
            if os.path.exists(path) and time.time() - os.path.getmtime(path) < self.TILE_TTL_S:
                with open(path, "r", encoding="utf-8") as f:
                    by_tile[tile] = [School(**x) for x in json.load(f)]
            else:
                missing.append(tile)

        missing.sort()
        for k in range(0, len(missing), self.TILES_PER_QUERY):
            chunk = missing[k:k + self.TILES_PER_QUERY]
            schools = self._query([(i * t, j * t, (i + 1) * t, (j + 1) * t) for i, j in chunk])
            fetched = {tile: [] for tile in chunk}
            for sc in schools:
                tile = (_m.floor(sc.latitude / t), _m.floor(sc.longitude / t))
                if tile in fetched:
                    fetched[tile].append(sc)
            for tile, lst in fetched.items():
                with open(os.path.join(cache, f"{tile[0]}_{tile[1]}.json"), "w", encoding="utf-8") as f:
                    json.dump([x.model_dump() for x in lst], f)
            by_tile.update(fetched)
        logger.info("OSM schools: %d tiles (%d from cache, %d fetched)", len(tiles), len(tiles) - len(missing), len(missing))

        def inside(sc: School) -> bool:
            return any(s_ <= sc.latitude <= n and w <= sc.longitude <= e for (s_, w, n, e) in bboxes)

        seen, schools = set(), []
        for lst in by_tile.values():
            for sc in lst:
                if sc.school_id not in seen and inside(sc):
                    seen.add(sc.school_id)
                    schools.append(sc)

        schools = self._merge_duplicates(schools)

        if india_only and schools:
            from src.data_sources.nasa_firms import points_in_india
            keep = points_in_india([sc.latitude for sc in schools], [sc.longitude for sc in schools])
            logger.info("Kept %d schools inside India, dropped %d outside.", int(keep.sum()), len(schools) - int(keep.sum()))
            schools = [sc for sc, k in zip(schools, keep) if k]
        return schools

    @staticmethod
    def _merge_duplicates(schools: List[School], within_m: float = 300.0) -> List[School]:
        """OSM often maps one school as both a node and a building way: keep one per name within 300 m."""
        import math as _m
        kept: List[School] = []
        by_name: dict = {}
        for sc in schools:
            key = sc.name.strip().lower()
            dup = False
            if not key.startswith("unnamed school"):
                for other in by_name.get(key, []):
                    dy = (sc.latitude - other.latitude) * 111_320.0
                    dx = (sc.longitude - other.longitude) * 111_320.0 * _m.cos(_m.radians(sc.latitude))
                    if dx * dx + dy * dy < within_m * within_m:
                        dup = True
                        break
            if not dup:
                kept.append(sc)
                by_name.setdefault(key, []).append(sc)
        return kept

    def _query(self, bboxes: List[BBox]) -> List[School]:
        """One Overpass request for amenity=school in the union of bboxes. Fails loudly."""
        parts = []
        for (s, w, n, e) in bboxes:
            box = f"({s:.4f},{w:.4f},{n:.4f},{e:.4f})"
            parts.append(f'nwr["amenity"="school"]{box};')
        query = f"[out:json][timeout:{self.QUERY_TIMEOUT_S}];({''.join(parts)});out center tags;"
        body = urllib.parse.urlencode({"data": query}).encode("utf-8")
        logger.info("Fetching OSM schools for %d areas from %s", len(bboxes), self.base_url)

        for attempt, delay in enumerate((0,) + self.RETRY_DELAYS_S):
            if delay:
                logger.warning("Overpass busy; retrying in %ss (attempt %d)", delay, attempt + 1)
                time.sleep(delay)
            req = urllib.request.Request(self.base_url, data=body, headers={"User-Agent": "DhuanAlert-EarlyWarning/1.0"})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_s) as response:
                    data = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as error:
                if error.code in (429, 504) and attempt < len(self.RETRY_DELAYS_S):
                    continue
                raise RuntimeError(f"OpenStreetMap Overpass request failed with HTTP {error.code}.") from None
            except (urllib.error.URLError, TimeoutError):
                raise RuntimeError("OpenStreetMap Overpass request failed due to a network error or timeout.") from None

        if "elements" not in data:
            raise ValueError("OpenStreetMap Overpass returned an unexpected response.")
        return self._parse_elements(data["elements"])

    @staticmethod
    def _parse_elements(elements: list) -> List[School]:
        schools: List[School] = []
        seen = set()
        for el in elements:
            lat = el.get("lat", el.get("center", {}).get("lat"))
            lon = el.get("lon", el.get("center", {}).get("lon"))
            key = (el.get("type"), el.get("id"))
            if lat is None or lon is None or key in seen:
                continue
            seen.add(key)
            tags = el.get("tags", {})
            name = tags.get("name:en") or tags.get("name") or f"Unnamed school (OSM {el['type']}/{el['id']})"
            schools.append(
                School(
                    school_id=f"osm_{el['type']}_{el['id']}",
                    name=name,
                    latitude=float(lat),
                    longitude=float(lon),
                    district=tags.get("addr:district") or tags.get("addr:city") or tags.get("is_in:district") or "",
                    state=tags.get("addr:state") or "",
                )
            )
        logger.info("Ingested %d schools from OpenStreetMap.", len(schools))
        return schools

    @staticmethod
    def load_ncr_schools() -> List[School]:
        """Bundled offline reference list (6 Delhi-NCR schools). Not used by forecast runs."""
        data_path = os.path.join(os.path.dirname(__file__), "..", "data", "ncr_schools.json")
        if not os.path.exists(data_path):
            raise FileNotFoundError(f"Bundled school list missing: {os.path.abspath(data_path)}")
        with open(data_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return [School(**s) for s in raw]
