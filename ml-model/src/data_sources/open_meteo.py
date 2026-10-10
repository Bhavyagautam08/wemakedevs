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
from typing import List, Optional, Tuple
from src.types import WeatherObservation

logger = logging.getLogger("dhuanalert.weather")

HOURLY_VARIABLES = (
    "wind_speed_10m,wind_direction_10m,boundary_layer_height,"
    "temperature_2m,relative_humidity_2m,precipitation"
)


class OpenMeteoClient:
    """
    Client for Open-Meteo GFS atmospheric forecast API.
    API Docs: https://open-meteo.com/en/docs
    """

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or os.environ.get("OPEN_METEO_BASE_URL", "https://api.open-meteo.com/v1/forecast")

    def fetch_forecast(
        self,
        latitude: float,
        longitude: float,
        forecast_days: int = 2,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[WeatherObservation]:
        """
        Fetches the hourly GFS time series at (latitude, longitude). The caller must pass
        the location of interest (normally the fire-cluster centroid); there is no default.
        start_date/end_date (YYYY-MM-DD) select a fixed window instead of forecast_days.
        Live requests never fall back to a bundled snapshot.
        """
        window = (
            f"&start_date={start_date}&end_date={end_date}"
            if start_date and end_date
            else f"&forecast_days={forecast_days}"
        )
        params = (
            f"?latitude={latitude}&longitude={longitude}"
            f"&hourly={HOURLY_VARIABLES}"
            f"{window}&models=gfs_seamless&timezone=UTC"
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

    POINTS_PER_REQUEST = 100
    CACHE_TTL_S = 30 * 60

    def fetch_forecast_points(
        self,
        points: List[Tuple[float, float]],
        forecast_days: int = 2,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[WeatherObservation]:
        """
        Fetches the hourly GFS series at many (lat, lon) points (batched requests). Every
        returned observation carries the grid-point latitude/longitude Open-Meteo resolved
        it to. Identical requests within CACHE_TTL_S are served from a local file cache to
        stay within the free API quota (each location counts as one call).
        """
        if not points:
            raise ValueError("fetch_forecast_points needs at least one point.")
        window = (
            f"&start_date={start_date}&end_date={end_date}"
            if start_date and end_date
            else f"&forecast_days={forecast_days}"
        )
        observations: List[WeatherObservation] = []
        for i in range(0, len(points), self.POINTS_PER_REQUEST):
            batch = points[i:i + self.POINTS_PER_REQUEST]
            lats = ",".join(f"{p[0]:.4f}" for p in batch)
            lons = ",".join(f"{p[1]:.4f}" for p in batch)
            url = (
                f"{self.base_url}?latitude={lats}&longitude={lons}&hourly={HOURLY_VARIABLES}"
                f"{window}&models=gfs_seamless&timezone=UTC"
            )
            items = self._get_json_cached(url)
            items = items if isinstance(items, list) else [items]
            if len(items) != len(batch):
                raise ValueError(f"Open-Meteo returned {len(items)} locations for {len(batch)} requested points.")
            for item in items:
                for obs in self._parse_response(item):
                    obs.latitude = float(item["latitude"])
                    obs.longitude = float(item["longitude"])
                    observations.append(obs)
        logger.info("Fetched Open-Meteo weather at %d points", len(points))
        return observations

    def _get_json_cached(self, url: str):
        import hashlib
        import time as _time
        cache_dir = os.environ.get(
            "DHUANALERT_CACHE_DIR",
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "output", "cache", "open_meteo"),
        )
        os.makedirs(cache_dir, exist_ok=True)
        path = os.path.join(cache_dir, hashlib.sha256(url.encode()).hexdigest()[:32] + ".json")
        if os.path.exists(path) and _time.time() - os.path.getmtime(path) < self.CACHE_TTL_S:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        req = urllib.request.Request(url, headers={"User-Agent": "DhuanAlert-EarlyWarning/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"Open-Meteo request failed with HTTP {error.code}.") from None
        except (urllib.error.URLError, TimeoutError):
            raise RuntimeError("Open-Meteo request failed due to a network error or timeout.") from None
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return data

    def _parse_response(self, data: dict) -> List[WeatherObservation]:
        """Parses Open-Meteo JSON into WeatherObservation vector objects."""
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        speeds = hourly.get("wind_speed_10m", [])
        dirs = hourly.get("wind_direction_10m", [])
        blhs = hourly.get("boundary_layer_height", [])
        temps = hourly.get("temperature_2m", [])
        rhs = hourly.get("relative_humidity_2m", [])
        precips = hourly.get("precipitation", [])

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
                precip = float(precips[i]) if i < len(precips) and precips[i] is not None else None

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
                        precipitation_mm=precip,
                    )
                )
            except (IndexError, TypeError, ValueError) as e:
                logger.warning("Skipping malformed Open-Meteo hourly record %s: %s", i, e)
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
            raise FileNotFoundError(f"Replay weather snapshot missing: {os.path.abspath(data_path)}")
        with open(data_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return [WeatherObservation(**w) for w in raw]
