from datetime import datetime, timedelta, timezone

import numpy as np

from src.layer1_predictive.diffusion_field import GaussianDiffusionField
from src.layer1_predictive.ensemble import ScenarioEnsembleRunner
from src.layer1_predictive.lagrangian_engine import ParticleState
from src.types import FireCluster, WeatherObservation


SIMULATION_START = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)


def weather_series():
    return [
        WeatherObservation(
            wind_speed_mps=float(np.hypot(2.0, -1.0)),
            wind_direction_deg=0.0,
            u_mps=2.0,
            v_mps=-1.0,
            boundary_layer_height_m=500.0,
            temperature_c=25.0,
            forecast_timestamp=SIMULATION_START + timedelta(hours=offset),
        )
        for offset in range(10)
    ]


def fire_cluster():
    return FireCluster(
        fire_id="test_fire",
        centroid_lat=30.2,
        centroid_lon=75.8,
        hotspot_count=1,
        weighted_centroid={"lat": 30.2, "lon": 75.8},
        latest_detection_time=SIMULATION_START,
        confidence_summary=90.0,
        frp_summary=200.0,
        source_strength=0.5,
        source_freshness_hours=0.0,
    )


def test_ensemble_snapshots_are_continuous_and_include_three_six_and_nine_hours():
    final_particles, ensemble, snapshots = ScenarioEnsembleRunner().run_ensemble(
        fires=[fire_cluster()],
        weather_obs=weather_series(),
        simulation_start_time=SIMULATION_START,
        horizon_hours=9,
        dt_seconds=900,
    )

    assert set(snapshots) == set(range(10))
    assert ensemble.member_count == 3
    assert len(final_particles) == 3
    assert all(len(snapshots[hour]) == ensemble.member_count for hour in (3, 6, 9))
    assert snapshots[3][0] is not snapshots[6][0]
    assert np.sum(snapshots[3][0].mass) > np.sum(snapshots[6][0].mass) > np.sum(snapshots[9][0].mass)


def test_particle_contour_is_a_hull_of_real_points_not_an_axis_aligned_box():
    particles = ParticleState(
        x=np.array([0.0, 4_000.0, 7_000.0, 2_000.0, -2_000.0]),
        y=np.array([0.0, 1_000.0, 6_000.0, 8_000.0, 4_000.0]),
        mass=np.ones(5),
        initial_mass=np.ones(5),
    )

    contour = GaussianDiffusionField().extract_contour_geojson(particles, coverage_fraction=1.0)
    coordinates = contour["coordinates"][0]

    assert contour["type"] == "Polygon"
    assert len(coordinates) == 6
    assert coordinates[0] == coordinates[-1]
