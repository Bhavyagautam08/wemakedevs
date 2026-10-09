"""
Open-Meteo GFS Weather Ingestion Module
Fetches real-time wind speed, wind direction, boundary-layer height (BLH),
temperature, and relative humidity for Lagrangian atmospheric transport.
"""

import os
import json
import math
import logging
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import List, Optional
from src.types import WeatherObservation

logger = logging.getLogger("dhuanalert.weather")

# Delhi-NCR Reference Coordinates (Safdarjung / Central NCR)
DEFAULT_LAT = 28.6139
DEFAULT_LON = 77.2090


class OpenMeteoClient:
    """
    Client for Open-Meteo GFS atmospheric forecast API.
    API Docs: https://open-meteo.com/en/docs
    """

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or os.environ.get("OPEN_METEO_BASE_URL", "https://api.open-meteo.com/v1/forecast")

    def fetch_forecast(
        self,
        latitude: float = DEFAULT_LAT,
        longitude: float = DEFAULT_LON,
        forecast_days: int = 2,
    ) -> List[WeatherObservation]:
        """
        Fetches hourly GFS meteorological vectors.
        Live requests never fall back to a bundled snapshot.
        """
        params = (
            f"?latitude={latitude}&longitude={longitude}"
            "&hourly=wind_speed_10m,wind_direction_10m,boundary_layer_height,temperature_2m,relative_humidity_2m"
            f"&forecast_days={forecast_days}&models=gfs_seamless&timezone=UTC"
        )
        url = f"{self.base_url}{params}"
        logger.info(f"Fetching live Open-Meteo weather from: {url}")

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "DhuanAlert-EarlyWarning/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"Open-Meteo request failed with HTTP {error.code}.") from None
        except (urllib.error.URLError, TimeoutError) as error:
            raise RuntimeError("Open-Meteo request failed due to a network error or timeout.") from None

        return self._parse_response(data)

    def _parse_response(self, data: dict) -> List[WeatherObservation]:
        """Parses Open-Meteo JSON into WeatherObservation vector objects."""
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        speeds = hourly.get("wind_speed_10m", [])
        dirs = hourly.get("wind_direction_10m", [])
        blhs = hourly.get("boundary_layer_height", [])
        temps = hourly.get("temperature_2m", [])
        rhs = hourly.get("relative_humidity_2m", [])

        observations: List[WeatherObservation] = []

        for i in range(len(times)):
            try:
                t_str = times[i]
                dt = datetime.fromisoformat(t_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                ws_kmh = float(speeds[i])
                ws_mps = round(ws_kmh / 3.6, 2)
                wdir_deg = float(dirs[i])
                blh = float(blhs[i])
                temp = float(temps[i])
                rh = float(rhs[i])

                # Compute meteorological u (eastward) and v (northward) vector components
                # Wind direction is where wind blows FROM.
                rad = math.radians(wdir_deg)
                u = round(-ws_mps * math.sin(rad), 2)
                v = round(-ws_mps * math.cos(rad), 2)

                observations.append(
                    WeatherObservation(
                        forecast_timestamp=dt,
                        wind_speed_mps=ws_mps,
                        wind_direction_deg=wdir_deg,
                        u_mps=u,
                        v_mps=v,
                        boundary_layer_height_m=blh,
                        temperature_c=temp,
                        relative_humidity_pct=rh,
                    )
                )
            except (IndexError, TypeError, ValueError) as e:
                logger.debug(f"Skipping malformed weather index {i}: {e}")
                continue

        if not observations:
            raise ValueError("Open-Meteo returned no valid hourly weather observations.")

        logger.info(f"Successfully ingested {len(observations)} hourly weather forecast vectors from Open-Meteo.")
        return observations

    @staticmethod
    def load_fallback_weather() -> List[WeatherObservation]:
        """Loads bundled reference dataset for offline / sample mode."""
        data_path = os.path.join(os.path.dirname(__file__), "..", "data", "sample_weather.json")
        if not os.path.exists(data_path):
            return []
        with open(data_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return [WeatherObservation(**w) for w in raw]
