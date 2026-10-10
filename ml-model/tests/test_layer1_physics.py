from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from src.layer1_predictive.weather_field import WeatherVectorField, WeatherDataRangeError
from src.service import DhuanAlertService, EvaluationUnavailableError
from src.types import WeatherObservation

T0 = datetime(2026, 10, 8, 21, tzinfo=timezone.utc)


def _obs(hour, u, v, blh):
    return WeatherObservation(
        wind_speed_mps=float(np.hypot(u, v)), wind_direction_deg=0.0, u_mps=u, v_mps=v,
        boundary_layer_height_m=blh, temperature_c=20.0, forecast_timestamp=T0 + timedelta(hours=hour),
    )


def test_wind_field_interpolates_in_time():
    wf = WeatherVectorField([_obs(0, 0.0, 0.0, 100.0), _obs(2, 4.0, -2.0, 300.0)], start_time=T0)
    u, v = wf.get_wind_vector(np.zeros(3), np.zeros(3), 3600.0)
    assert np.allclose(u, 2.0) and np.allclose(v, -1.0)
    assert wf.get_blh_and_diffusivity(3600.0)[0] == pytest.approx(200.0)


def test_wind_field_fails_loud_outside_forecast_window():
    wf = WeatherVectorField([_obs(0, 1.0, 1.0, 100.0), _obs(2, 1.0, 1.0, 100.0)], start_time=T0)
    with pytest.raises(WeatherDataRangeError):
        wf.get_wind_vector(np.zeros(1), np.zeros(1), 3 * 3600.0)
    with pytest.raises(WeatherDataRangeError):
        wf.require_coverage(9 * 3600.0)


def test_horizons_are_chained_from_one_continuous_run():
    service = DhuanAlertService()
    hotspots, weather, t0 = service.get_replay_inputs()
    l1 = service.layer1
    clusters = l1.source_model.cluster_hotspots(hotspots, current_time=t0)
    snapshots, _ = l1.ensemble.run_ensemble(clusters, weather, t0, horizon_hours=9, dt_seconds=900)

    assert sorted(snapshots) == list(range(10))
    for m in range(len(l1.config.ensemble_members)):
        masses = [float(np.sum(snapshots[h][m].mass)) for h in (3, 6, 9)]
        assert masses[0] > masses[1] > masses[2] > 0.0

    # Same particles carried forward: mean 3h->6h displacement equals the wind field integrated
    # at the particles' own positions (taken from the hourly snapshots in between)
    a, b = snapshots[3][1], snapshots[6][1]
    wf = WeatherVectorField(weather, start_time=t0, projection=l1.projection)
    expected_dx = 0.0
    for hr in range(3, 6):
        st = snapshots[hr][1]
        for t in np.arange(hr * 3600, (hr + 1) * 3600, 900):
            expected_dx += float(np.mean(wf.get_wind_vector(st.x, st.y, t)[0])) * 900
    assert len(a) == len(b)
    assert float(np.mean(b.x - a.x)) == pytest.approx(expected_dx, abs=1000.0)


def test_spatial_wind_interpolation_reproduces_station_values():
    """With two located stations the field equals each station's wind at its own location."""
    obs = []
    for lat, lon, u in ((30.0, 75.0, 4.0), (30.0, 76.0, -2.0)):
        for h in range(3):
            o = _obs(h, u, 0.0, 300.0)
            o.latitude, o.longitude = lat, lon
            obs.append(o)
    wf = WeatherVectorField(obs, start_time=T0)
    xs = np.array([s["x"] for s in wf.stations])
    ys = np.array([s["y"] for s in wf.stations])
    u, _ = wf.get_wind_vector(xs, ys, 3600.0)
    # IDW is precomputed on a 25 km raster and sampled bilinearly: ~0.1 m/s smoothing near stations
    assert u == pytest.approx([4.0, -2.0], abs=0.15)
    mid_u, _ = wf.get_wind_vector(np.array([xs.mean()]), np.array([ys.mean()]), 3600.0)
    assert mid_u[0] == pytest.approx(1.0, abs=0.15)  # equidistant -> average


def test_replay_prediction_is_internally_consistent():
    svc = DhuanAlertService()
    pred = svc.simulate_layer1(schools=svc.get_sample_schools())
    assert [t.horizon_offset_hours for t in pred.timeline] == list(range(10))
    winds = [(w["u_mps"], w["v_mps"]) for w in pred.weather["at_horizons"]]
    assert len(set(winds)) > 1  # wind varies over the run
    for s in pred.schools:
        assert (s.impact_probability > 0) == (s.predicted_arrival_time is not None)


def test_analytic_control_case_arrival_matches_distance_over_wind_speed():
    """
    SYNTHETIC control case (not real weather): a uniform 5 m/s wind from the west carries
    the plume to a school 60 km due east. Advection alone predicts arrival at 60e3/5 s = 3.33 h.
    A school 60 km upwind (west) must never be impacted.
    """
    from src.layer1_predictive.pipeline import Layer1PredictivePipeline
    from src.types import Hotspot, School

    fire_lat, fire_lon = 30.0, 75.5
    km_per_deg_lon = 111.32 * np.cos(np.radians(fire_lat))
    hotspots = [
        Hotspot(detection_id=f"syn_{i}", latitude=fire_lat + 0.01 * i, longitude=fire_lon, acq_timestamp=T0,
                confidence=90.0, frp=200.0)
        for i in range(3)
    ]
    # Wind FROM 270 deg (west) at 5 m/s -> u = +5, v = 0
    weather = [
        WeatherObservation(wind_speed_mps=5.0, wind_direction_deg=270.0, u_mps=5.0, v_mps=0.0,
                           boundary_layer_height_m=500.0, temperature_c=20.0,
                           forecast_timestamp=T0 + timedelta(hours=h))
        for h in range(12)
    ]
    schools = [
        School(school_id="downwind", name="Downwind 60 km", district="x",
               latitude=fire_lat + 0.01, longitude=fire_lon + 60.0 / km_per_deg_lon),
        School(school_id="upwind", name="Upwind 60 km", district="x",
               latitude=fire_lat + 0.01, longitude=fire_lon - 60.0 / km_per_deg_lon),
    ]
    pred = Layer1PredictivePipeline().run(hotspots, weather, schools, run_timestamp=T0)
    by_id = {s.school_id: s for s in pred.schools}

    down, up = by_id["downwind"], by_id["upwind"]
    assert down.predicted_arrival_time is not None and down.impact_probability > 0
    arrival_h = (down.predicted_arrival_time - T0).total_seconds() / 3600.0
    # Leading edge arrives before the centroid (initial 3 km spread + diffusion + 4 km kernel)
    assert 2.0 <= arrival_h <= 3.6, arrival_h
    assert up.predicted_arrival_time is None and up.impact_probability == 0.0
    # Plume centroid moves east at 5 m/s. Equal-mass batches released at 0, 1, 2 h are 6, 5, 4 h old
    # at +6h, so the centroid sits at 5 m/s * ~5 h = ~90 km (decay weights younger batches slightly).
    h6 = next(h for h in pred.simulation["horizon_states"] if h["horizon_hours"] == 6)
    east_km = (h6["centroid_lon"] - fire_lon) * km_per_deg_lon
    assert east_km == pytest.approx(90.0, abs=5.0)


def test_evaluation_requires_real_data():
    with pytest.raises(EvaluationUnavailableError):
        DhuanAlertService().run_evaluation()
