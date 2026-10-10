from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from src.layer1_predictive.weather_field import WeatherVectorField
from src.types import WeatherObservation


SIMULATION_START = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)


def weather_observation(offset_hours: int, u_mps: float, v_mps: float, blh_m: float) -> WeatherObservation:
    return WeatherObservation(
        wind_speed_mps=float(np.hypot(u_mps, v_mps)),
        wind_direction_deg=0.0,
        u_mps=u_mps,
        v_mps=v_mps,
        boundary_layer_height_m=blh_m,
        temperature_c=25.0,
        forecast_timestamp=SIMULATION_START + timedelta(hours=offset_hours),
    )


def test_weather_field_linearly_interpolates_components_and_blh_without_shear():
    field = WeatherVectorField(
        [
            weather_observation(1, 2.0, -4.0, 300.0),
            weather_observation(0, 0.0, -2.0, 100.0),
            weather_observation(2, 4.0, -6.0, 500.0),
        ],
        simulation_start_time=SIMULATION_START,
    )

    u, v = field.get_wind_vector(
        np.array([0.0, 50_000.0]),
        np.array([0.0, -50_000.0]),
        time_elapsed_seconds=30 * 60,
    )
    blh, _, _ = field.get_blh_and_diffusivity(time_elapsed_seconds=90 * 60)

    assert u == pytest.approx([1.0, 1.0])
    assert v == pytest.approx([-3.0, -3.0])
    assert blh == pytest.approx(400.0)


def test_weather_field_applies_ensemble_wind_adjustments_after_interpolation():
    field = WeatherVectorField(
        [
            weather_observation(0, 0.0, -4.0, 400.0),
            weather_observation(1, 4.0, 0.0, 400.0),
        ],
        simulation_start_time=SIMULATION_START,
    )

    u, v = field.get_wind_vector(
        np.array([0.0]),
        np.array([0.0]),
        time_elapsed_seconds=30 * 60,
        speed_factor=2.0,
    )

    assert u == pytest.approx([4.0])
    assert v == pytest.approx([-4.0])


@pytest.mark.parametrize("elapsed_seconds", [-1.0, 2 * 3600.0])
def test_weather_field_rejects_times_outside_forecast_coverage(elapsed_seconds):
    field = WeatherVectorField(
        [
            weather_observation(0, 1.0, 1.0, 300.0),
            weather_observation(1, 2.0, 2.0, 400.0),
        ],
        simulation_start_time=SIMULATION_START,
    )

    with pytest.raises(ValueError, match="WEATHER_COVERAGE_ERROR"):
        field.get_wind_vector(
            np.array([0.0]),
            np.array([0.0]),
            time_elapsed_seconds=elapsed_seconds,
        )


def test_weather_field_rejects_simulation_start_before_forecast_coverage():
    with pytest.raises(ValueError, match="outside supplied forecast coverage"):
        WeatherVectorField(
            [
                weather_observation(1, 1.0, 1.0, 300.0),
                weather_observation(2, 2.0, 2.0, 400.0),
            ],
            simulation_start_time=SIMULATION_START,
        ).get_blh_and_diffusivity()


def test_weather_field_rejects_forecasts_that_end_before_the_simulation_horizon():
    field = WeatherVectorField(
        [
            weather_observation(0, 1.0, 1.0, 300.0),
            weather_observation(1, 2.0, 2.0, 400.0),
        ],
        simulation_start_time=SIMULATION_START,
    )

    with pytest.raises(ValueError, match="WEATHER_COVERAGE_ERROR"):
        field.ensure_coverage(2 * 3600.0)
