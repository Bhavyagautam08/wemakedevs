"""
NASA FIRMS (Fire Information for Resource Management System) Ingestion Module
Fetches real-time VIIRS / MODIS active fire detections. Live requests never use cached snapshots.
"""

import csv
import os
import json
import logging
import urllib.request
import urllib.error
from datetime import datetime
from typing import List, Optional
from src.types import Hotspot

logger = logging.getLogger("dhuanalert.firms")

# Default bounding box for India
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
        bbox: str = INDIA_BBOX,
        days: int = 1,
        source: str = "VIIRS_SNPP_NRT",
    ) -> List[Hotspot]:
        """
        Fetches live fires for the specified bounding box.
        Live requests never fall back to a bundled snapshot.
        """
        if not self.map_key or self.map_key.upper() in ("MOCK", "SAMPLE", "YOUR_NASA_FIRMS_MAP_KEY", ""):
            raise RuntimeError("NASA_FIRMS_MAP_KEY is required to fetch live fire detections.")

        url = f"{self.base_url}/{self.map_key}/{source}/{bbox}/{days}"
        logger.info(f"Fetching live NASA FIRMS fires from: {self.base_url}/[KEY]/{source}/{bbox}/{days}")

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "DhuanAlert-EarlyWarning/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                content = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"NASA FIRMS request failed with HTTP {error.code}.") from None
        except (urllib.error.URLError, TimeoutError) as error:
            raise RuntimeError("NASA FIRMS request failed due to a network error or timeout.") from None

        return self._parse_csv_response(content)

    def _parse_csv_response(self, csv_text: str) -> List[Hotspot]:
        """Parses NASA FIRMS CSV response into Hotspot models."""
        hotspots: List[Hotspot] = []
        reader = csv.DictReader(csv_text.strip().splitlines())

        if not reader.fieldnames or not {"latitude", "longitude", "confidence", "acq_date", "acq_time", "frp"}.issubset(reader.fieldnames):
            raise ValueError("NASA FIRMS returned an unexpected CSV schema.")

        for idx, row in enumerate(reader):
            try:
                lat = float(row["latitude"])
                lon = float(row["longitude"])
                frp = float(row["frp"])
                confidence_class = row["confidence"].strip().lower()
                confidence_values = {"l": 30.0, "n": 60.0, "h": 90.0}
                confidence = float(confidence_class) if confidence_class.replace(".", "", 1).isdigit() else confidence_values[confidence_class]
                acq_date = row["acq_date"]
                acq_time = row["acq_time"].zfill(4)

                dt_str = f"{acq_date}T{acq_time[:2]}:{acq_time[2:]}:00Z"
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))

                hotspots.append(
                    Hotspot(
                        detection_id=f"firms_{row.get('satellite', 'viirs')}_{acq_date}_{acq_time}_{idx}",
                        latitude=lat,
                        longitude=lon,
                        frp=frp,
                        confidence=confidence,
                        confidence_class=confidence_class,
                        satellite=row.get("satellite") or "VIIRS_NRT",
                        acq_timestamp=dt,
                    )
                )
            except (KeyError, ValueError) as parse_err:
                logger.warning("Skipping malformed NASA FIRMS CSV row %s: %s", idx + 1, parse_err)
                continue

        if csv_text.strip().splitlines()[1:] and not hotspots:
            raise ValueError("NASA FIRMS returned records, but none matched the expected data schema.")

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
