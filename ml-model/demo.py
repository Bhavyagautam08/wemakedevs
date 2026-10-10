"""
DhuanAlert End-to-End Demo Script
Runs the entire pipeline (Layer 1 Physics + Layer 2 Policy-Gated GenAI + Evaluation Matrix)
and exports ready-to-use JSON files for the Backend and Frontend teams.
"""

import json
import os
import sys
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.types import Hotspot, WeatherObservation, School
from src.pipeline import DhuanAlertPipeline
from src.model.evaluation import evaluate_model_against_ground_truth
from tests.test_evaluation import run_evaluation_demo


def load_sample_data():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "src", "data")

    with open(os.path.join(data_dir, "sample_fires.json"), "r") as f:
        fires_raw = json.load(f)
    with open(os.path.join(data_dir, "sample_weather.json"), "r") as f:
        weather_raw = json.load(f)
    with open(os.path.join(data_dir, "ncr_schools.json"), "r") as f:
        schools_raw = json.load(f)

    hotspots = [Hotspot(**item) for item in fires_raw]
    weather = [WeatherObservation(**item) for item in weather_raw]
    schools = [School(**item) for item in schools_raw]

    return hotspots, weather, schools


def main():
    print("=" * 70)
    print("DHUANALERT: RUNNING HYBRID PREDICTIVE & GENERATIVE AI PIPELINE")
    print("=" * 70)

    # 1. Load Data
    hotspots, weather, schools = load_sample_data()
    print(f"[✓] Loaded {len(hotspots)} VIIRS active-fire hotspots from Punjab.")
    print(f"[✓] Loaded North-Westerly wind field: {weather[0].wind_speed_mps} m/s @ {weather[0].wind_direction_deg}°.")
    print(f"[✓] Loaded {len(schools)} Delhi-NCR school coordinates.")

    # 2. Execute Master Pipeline
    pipeline = DhuanAlertPipeline()
    now = datetime.now(timezone.utc)
    payload = pipeline.run(
        hotspots=hotspots,
        weather=weather,
        schools=schools,
        grap_stage=int(os.environ.get("DHUANALERT_GRAP_STAGE", "3")),
        human_approved=False,
        run_timestamp=now,
    )

    pred = payload.prediction
    adv = payload.advisory

    # 3. Print Results Summary
    print("\n" + "-" * 70)
    print("LAYER 1: PREDICTIVE / LAGRANGIAN ENSEMBLE RESULTS")
    print("-" * 70)
    print(f"Prediction ID     : {pred.prediction_id}")
    print(f"Simulated Smoke   : {pred.fire['hotspot_count']} hotspots -> Source Strength: {pred.fire['source_strength']}")
    print(f"Ensemble Members  : {pred.ensemble.member_count} physical scenarios evaluated")
    print(f"Timeline Slices   : {len(pred.timeline)} hourly animation steps generated (T+0 to T+6h)")
    print("\nAssessed Schools Risk Ranking:")
    for s in pred.schools:
        arr_str = s.predicted_arrival_time.strftime('%H:%M UTC') if s.predicted_arrival_time else "No Arrival"
        print(f"  • [{s.risk_band:<9}] {s.name:<42} | Arrival: {arr_str} | Prob: {s.impact_probability:.2f} | Score: {s.risk_score:.2f}")

    print("\n" + "-" * 70)
    print("LAYER 2: GENERATIVE AI & POLICY-GATED ADVISORY RESULTS")
    print("-" * 70)
    print(f"Advisory ID       : {adv.advisory_id}")
    print(f"Severity Band     : {adv.severity}")
    print(f"Headline (EN)     : {adv.headline.en}")
    print(f"Headline (HI)     : {adv.headline.hi}")
    print(f"Summary (EN)      : {adv.summary.en}")
    print(f"Summary (HI)      : {adv.summary.hi}")
    print("\nCedar-Authorized Recommended Actions:")
    for act in adv.recommended_actions:
        print(f"  [✓ ALLOWED] {act.en}")
        print(f"              Basis: {act.policy_basis}")
    print(f"\nCedar Policy Gate : {adv.validation.policy_check}")
    print(f"Claim Validation  : {adv.validation.claim_check}")
    print(f"Publication Status: {adv.validation.publication_status}")

    # 4. Run Real-World Evaluation Matrix
    print("\n" + "-" * 70)
    print("LAYER 3: REAL-WORLD GROUND TRUTH EVALUATION MATRIX")
    print("-" * 70)
    eval_report = run_evaluation_demo()
    print(f"Spearman Correlation (rho) : {eval_report.spearman_rho} (Strong signal)")
    print(f"Median Arrival Lag         : {eval_report.median_arrival_lag_hours} hours")
    print(f"Probability of Detection   : {eval_report.contingency.probability_of_detection * 100:.1f}%")
    print(f"False Alarm Ratio (FAR)    : {eval_report.contingency.false_alarm_ratio * 100:.1f}%")
    print(f"Critical Success Index     : {eval_report.contingency.critical_success_index:.3f}")
    print(f"Ensemble Capture Rate      : {eval_report.envelope_capture_rate * 100:.1f}%")
    print(f"Operational Verdict        : {eval_report.operational_verdict}")

    # 5. Export JSON Files for Backend and Frontend
    out_dir = os.environ.get(
        "DHUANALERT_OUTPUT_DIR",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "output"),
    )
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(out_dir, "prediction.json"), "w", encoding="utf-8") as f:
        f.write(pred.model_dump_json(indent=2))

    with open(os.path.join(out_dir, "advisory.json"), "w", encoding="utf-8") as f:
        f.write(adv.model_dump_json(indent=2))

    with open(os.path.join(out_dir, "map.geojson"), "w", encoding="utf-8") as f:
        json.dump(pred.map_geojson, f, indent=2)

    with open(os.path.join(out_dir, "frontend_payload.json"), "w", encoding="utf-8") as f:
        f.write(payload.model_dump_json(indent=2))

    with open(os.path.join(out_dir, "evaluation_report.json"), "w", encoding="utf-8") as f:
        f.write(eval_report.model_dump_json(indent=2))

    print("\n" + "=" * 70)
    print(f"[✓] SUCCESS! Exported complete JSON files to: {out_dir}")
    print("    - prediction.json        (Layer 1 Model output)")
    print("    - advisory.json          (Layer 2 Bilingual GenAI output)")
    print("    - map.geojson            (MapLibre FeatureCollection)")
    print("    - frontend_payload.json  (Combined API contract)")
    print("    - evaluation_report.json (Ground-truth evaluation metrics)")
    print("=" * 70)


if __name__ == "__main__":
    main()
