"""
OpenAQ / WAQI Air Quality Observation Ingestion Module
Provides real-time PM2.5 monitoring data for ground-truth validation and AQI context.
"""

import os
import json
import logging
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

logger = logging.getLogger("dhuanalert.openaq")


class OpenAqWaqiClient:
    """
    Client for OpenAQ and WAQI (World Air Quality Index) live stations.
    """

    def __init__(self, openaq_key: Optional[str] = None, waqi_token: Optional[str] = None):
        self.openaq_key = openaq_key or os.environ.get("OPENAQ_API_KEY", "").strip()
        self.waqi_token = waqi_token or os.environ.get("WAQI_API_TOKEN", "").strip()

    def fetch_delhi_stations(self) -> List[Dict[str, Any]]:
        """
        Fetches current PM2.5 readings across Delhi-NCR monitoring stations.
        Falls back to local baseline dataset if offline.
        """
        if self.waqi_token and self.waqi_token.upper() not in ("MOCK", "SAMPLE", "YOUR_WAQI_API_TOKEN", ""):
            url = f"https://api.waqi.info/map/bounds/?latlng=28.3,76.8,28.9,77.4&token={self.waqi_token}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "DhuanAlert/1.0"})
                with urllib.request.urlopen(req, timeout=8) as res:
                    data = json.loads(res.read().decode("utf-8"))
                if data.get("status") == "ok":
                    return data.get("data", [])
            except Exception as e:
                logger.warning(f"WAQI API fetch failed: {e}. Using local station references.")

        return self.load_fallback_stations()

    @staticmethod
    def load_fallback_stations() -> List[Dict[str, Any]]:
        """Returns verified reference CAAQMS stations in Delhi-NCR."""
        return [
            {"station_id": "delhi_narela", "name": "Narela CAAQMS", "lat": 28.852, "lon": 77.098, "aqi": 385, "pm25": 242.0},
            {"station_id": "delhi_bawana", "name": "Bawana CAAQMS", "lat": 28.776, "lon": 77.051, "aqi": 412, "pm25": 278.0},
            {"station_id": "delhi_rohini", "name": "Rohini Sector 16", "lat": 28.732, "lon": 77.119, "aqi": 360, "pm25": 215.0},
            {"station_id": "delhi_anand_vihar", "name": "Anand Vihar", "lat": 28.647, "lon": 77.315, "aqi": 448, "pm25": 310.0},
            {"station_id": "delhi_punjabi_bagh", "name": "Punjabi Bagh", "lat": 28.674, "lon": 77.131, "aqi": 340, "pm25": 195.0},
            {"station_id": "delhi_rk_puram", "name": "R.K. Puram", "lat": 28.563, "lon": 77.186, "aqi": 325, "pm25": 182.0},
        ]
