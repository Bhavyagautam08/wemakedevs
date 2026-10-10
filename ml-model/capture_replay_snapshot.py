"""
Captures a REAL replay snapshot from the live providers so offline/replay runs use
recorded data, never hand-made values.

  python capture_replay_snapshot.py

Writes src/data/sample_fires.json (NASA FIRMS detections, last 24 h, India),
src/data/sample_weather.json (Open-Meteo GFS hourly series on a grid around
the fires plus the strongest cluster centroids, from T0 onward) and src/data/replay_snapshot_meta.json (provenance).
T0 = first whole UTC hour after the latest fire detection.
"""

import json
import os
from datetime import datetime, timedelta, timezone

from src.service import DhuanAlertService

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "data")


def main():
    svc = DhuanAlertService()
    fires = svc.get_live_fires()
    if not fires:
        raise SystemExit("NO_ACTIVE_FIRES: nothing to capture.")
    latest = max(f.acq_timestamp for f in fires)
    t0 = latest.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    points = svc.weather_points_for(fires, t0)
    end = t0 + timedelta(hours=svc.config.simulation.horizon_hours + 2)
    weather = svc.weather_client.fetch_forecast_points(
        points, start_date=t0.date().isoformat(), end_date=end.date().isoformat()
    )
    weather = [w for w in weather if w.forecast_timestamp >= t0]

    with open(os.path.join(DATA_DIR, "sample_fires.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump([h.model_dump(mode="json") for h in fires], f, indent=2)
    with open(os.path.join(DATA_DIR, "sample_weather.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump([w.model_dump(mode="json") for w in weather], f, indent=2)
    meta = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "t0": t0.isoformat(),
        "fires": {"source": "NASA FIRMS VIIRS_SNPP_NRT area API, 1 day, India bbox 68.0,6.5,97.5,37.5, "
                            "filtered to India (Natural Earth 1:10m boundary)", "count": len(fires),
                  "acq_range": [min(f.acq_timestamp for f in fires).isoformat(), latest.isoformat()]},
        "weather": {"source": "Open-Meteo gfs_seamless hourly", "points": len(points), "records": len(weather)},
    }
    with open(os.path.join(DATA_DIR, "replay_snapshot_meta.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(meta, f, indent=2)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
