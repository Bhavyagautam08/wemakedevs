"""
Unit tests for Python DhuanAlert Model Service and Core Pipeline
"""

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


def test_layer1_simulation(service):
    pred: PredictiveOutput = service.simulate_layer1()
    assert pred.prediction_id.startswith("pred_")
    assert len(pred.timeline) == 7
    assert len(pred.schools) > 0
    assert pred.ensemble.member_count == 3
    assert pred.map_geojson["type"] == "FeatureCollection"


def test_layer2_advisory_generation_and_review(service):
    pred = service.simulate_layer1()
    adv: AdvisoryOutput = service.generate_advisory(prediction=pred, grap_stage=3, human_approved=False)

    assert adv.advisory_id.startswith("adv_")
    assert adv.headline.en is not None
    assert adv.validation.publication_status in ["DRAFT", "MANUAL_REVIEW_REQUIRED"]

    # Officer review
    reviewed = service.review_advisory(adv, action="APPROVE", officer_id="Officer_Test")
    assert reviewed.validation.publication_status == "APPROVED"


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
