"""
NASA FIRMS (Fire Information for Resource Management System) Ingestion Module
Fetches real-time VIIRS / MODIS active fire detections with graceful fallback to cached snapshots.
"""

import os
import csv
import json
import logging
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import List, Optional
from src.types import Hotspot

logger = logging.getLogger("dhuanalert.firms")

# Default bounding box for North-West India (Punjab, Haryana, Delhi-NCR)
# Format: [min_lon, min_lat, max_lon, max_lat]
DEFAULT_NCR_BBOX = "73.5,27.5,78.5,32.5"
INDIA_BBOX = "68.0,6.0,97.0,37.0"


class NasaFirmsClient:
    """
    Client for NASA FIRMS Area API.
    API Docs: https://firms.modaps.eosdis.nasa.gov/api/area/
    """

    def __init__(self, map_key: Optional[str] = None):
        self.map_key = map_key or os.environ.get("NASA_FIRMS_MAP_KEY", "").strip()
        self.base_url = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"

    def fetch_active_fires(
        self,
        bbox: str = DEFAULT_NCR_BBOX,
        days: int = 1,
        source: str = "VIIRS_SNPP_NRT",
    ) -> List[Hotspot]:
        """
        Fetches live fires for the specified bounding box.
        If no MAP_KEY is configured or if network fails, falls back to local sample fires.
        """
        if not self.map_key or self.map_key.upper() in ("MOCK", "SAMPLE", "YOUR_NASA_FIRMS_MAP_KEY", ""):
            logger.info("NASA_FIRMS_MAP_KEY not configured. Falling back to local cached snapshot.")
            return self.load_fallback_fires()

        url = f"{self.base_url}/{self.map_key}/{source}/{bbox}/{days}"
        logger.info(f"Fetching live NASA FIRMS fires from: {self.base_url}/[KEY]/{source}/{bbox}/{days}")

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "DhuanAlert-EarlyWarning/1.0 (Environmental Hacks)"},
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read().decode("utf-8")

            return self._parse_csv_response(content)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, Exception) as e:
            logger.warning(f"Failed to fetch live NASA FIRMS data ({e}). Falling back to cached snapshot.")
            return self.load_fallback_fires()

    def _parse_csv_response(self, csv_text: str) -> List[Hotspot]:
        """Parses NASA FIRMS CSV response into Hotspot models."""
        hotspots: List[Hotspot] = []
        reader = csv.DictReader(csv_text.strip().splitlines())

        for idx, row in enumerate(reader):
            try:
                lat = float(row.get("latitude", 0.0))
                lon = float(row.get("longitude", 0.0))
                frp = float(row.get("frp", row.get("bright_ti4", 15.0)))
                conf = row.get("confidence", "nominal")
                acq_date = row.get("acq_date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
                acq_time = row.get("acq_time", "1200").zfill(4)

                dt_str = f"{acq_date}T{acq_time[:2]}:{acq_time[2:]}:00Z"
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))

                hotspots.append(
                    Hotspot(
                        hotspot_id=f"firms_live_{idx}_{row.get('track', '0')}",
                        latitude=lat,
                        longitude=lon,
                        frp=max(1.0, frp),
                        confidence=conf,
                        satellite=row.get("satellite", "VIIRS-SNPP"),
                        instrument="VIIRS",
                        acq_datetime=dt,
                    )
                )
            except Exception as parse_err:
                logger.debug(f"Skipping malformed CSV row: {parse_err}")
                continue

        if not hotspots:
            logger.warning("NASA FIRMS CSV returned 0 parsed records. Falling back to cached snapshot.")
            return self.load_fallback_fires()

        logger.info(f"Successfully ingested {len(hotspots)} active fire hotspots from NASA FIRMS API.")
        return hotspots

    @staticmethod
    def load_fallback_fires() -> List[Hotspot]:
        """Loads bundled reference dataset for offline / sample mode."""
        data_path = os.path.join(os.path.dirname(__file__), "..", "data", "sample_fires.json")
        if not os.path.exists(data_path):
            return []
        with open(data_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return [Hotspot(**h) for h in raw]
