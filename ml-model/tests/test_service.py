"""Unit tests for the Python DhuanAlert model service and core pipeline."""

from datetime import timedelta

import pytest
from src.service import DhuanAlertService
from src.types import PredictiveOutput, AdvisoryOutput


@pytest.fixture
def service():
    return DhuanAlertService()


def test_reference_data_loading(service):
    schools = service.get_sample_schools()
    fires = service.get_sample_fires()
    weather = service.get_sample_weather()
    grap = service.get_grap_catalog()

    assert len(schools) > 0
    assert len(fires) > 0
    assert len(weather) > 0
    assert "stages" in grap


def complete_simulation_inputs(service):
    """A test-only, complete hourly series; production code never creates this data."""
    base_weather = service.get_sample_weather()[0]
    weather = [
        base_weather.model_copy(
            update={"forecast_timestamp": base_weather.forecast_timestamp + timedelta(hours=offset)}
        )
        for offset in range(10)
    ]
    return service.get_sample_fires(), weather, service.get_sample_schools(), base_weather.forecast_timestamp


def test_layer1_simulation(service):
    hotspots, weather, schools, run_timestamp = complete_simulation_inputs(service)
    pred: PredictiveOutput = service.simulate_layer1(
        hotspots=hotspots,
        weather=weather,
        schools=schools,
        run_timestamp=run_timestamp,
    )
    assert pred.prediction_id.startswith("pred_")
    assert len(pred.timeline) == 10
    assert pred.timeline[-1].horizon_offset_hours == pred.simulation["horizon_hours"]
    assert all(slice_.horizon_offset_hours <= pred.simulation["horizon_hours"] for slice_ in pred.timeline)
    assert {3, 6, 9}.issubset({slice_.horizon_offset_hours for slice_ in pred.timeline})
    assert len(pred.timeline[0].scatter_points) > 0
    assert all(slice_.heatmap_levels is None for slice_ in pred.timeline)
    assert all(slice_.contour_geojson["type"] == "Polygon" for slice_ in pred.timeline)
    assert len(pred.schools) > 0
    assert pred.ensemble.member_count == 3
    assert pred.map_geojson["type"] == "FeatureCollection"


def test_layer2_advisory_generation_and_review(service):
    hotspots, weather, schools, run_timestamp = complete_simulation_inputs(service)
    pred = service.simulate_layer1(
        hotspots=hotspots,
        weather=weather,
        schools=schools,
        run_timestamp=run_timestamp,
    )
    adv: AdvisoryOutput = service.generate_advisory(prediction=pred, grap_stage=3, human_approved=False)

    assert adv.advisory_id.startswith("adv_")
    assert adv.headline.en is not None
    assert adv.validation.publication_status in ["DRAFT", "MANUAL_REVIEW_REQUIRED"]

    # Officer review
    reviewed = service.review_advisory(adv, action="APPROVE", officer_id="Officer_Test")
    assert reviewed.validation.publication_status == "APPROVED"


def test_layer1_simulation_rejects_missing_inputs_instead_of_loading_samples(service):
    with pytest.raises(ValueError, match="MISSING_SIMULATION_INPUT"):
        service.simulate_layer1()


def test_live_weather_uses_the_detected_fire_cluster_location(service, monkeypatch):
    captured = {}

    def fetch_forecast(*, latitude, longitude, forecast_days=2):
        captured["latitude"] = latitude
        captured["longitude"] = longitude
        return []

    monkeypatch.setattr(service.weather_client, "fetch_forecast", fetch_forecast)

    assert service.get_live_weather(service.get_sample_fires()) == []
    assert 30.1 < captured["latitude"] < 30.4
    assert 75.7 < captured["longitude"] < 76.0


def test_cedar_policy_evaluator(service):
    dec_allow = service.evaluate_cedar_policy(
        action_id="discontinue_primary_physical_classes",
        risk_band="HIGH",
        grap_stage=3,
        human_approved=True,
    )
    assert dec_allow.decision == "ALLOW"

    dec_deny = service.evaluate_cedar_policy(
        action_id="discontinue_primary_physical_classes",
        risk_band="HIGH",
        grap_stage=2,
        human_approved=True,
    )
    assert dec_deny.decision == "DENY"


def test_claims_validator(service):
    res_safe = service.validate_claims("Smoke arrival in 3 hours under GRAP III.")
    assert res_safe.is_valid is True

    res_unsafe = service.validate_claims("Section 144 curfew declared immediately.")
    assert res_unsafe.is_valid is False
