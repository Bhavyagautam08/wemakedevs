"""
DhuanAlert ML Model Pipeline CLI Bridge
Invoked by the backend Node.js service to execute physics simulation and GenAI advisories.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MODEL_ROOT = os.path.dirname(os.path.abspath(__file__))
if MODEL_ROOT not in sys.path:
    sys.path.insert(0, MODEL_ROOT)

from src.service import DhuanAlertService
from src.types import Hotspot, WeatherObservation, School, PredictiveOutput, AdvisoryOutput


def main():
    parser = argparse.ArgumentParser(description="DhuanAlert ML Model CLI Bridge")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. RUN (Full pipeline)
    p_run = subparsers.add_parser("run", help="Run end-to-end forecast pipeline")
    p_run.add_argument("--mode", default="replay")
    p_run.add_argument("--snapshot", default="sample")
    p_run.add_argument("--grap-stage", type=int, default=3)
    p_run.add_argument("--human-approved", action="store_true", default=False)
    p_run.add_argument("--input-file", help="Path to custom JSON input payload")
    p_run.add_argument("--output-dir", help="Path to export output JSON files")

    # 2. SIMULATE (Layer 1 only)
    p_sim = subparsers.add_parser("simulate", help="Run Layer 1 simulation")
    p_sim.add_argument("--input-file", help="Path to JSON containing hotspots/weather/schools")
    p_sim.add_argument("--output-file", help="Path to write PredictiveOutput JSON")

    # 3. ADVISORY (Layer 2 only)
    p_adv = subparsers.add_parser("advisory", help="Generate Layer 2 advisory")
    p_adv.add_argument("--prediction-file", required=True)
    p_adv.add_argument("--grap-stage", type=int, default=3)
    p_adv.add_argument("--human-approved", action="store_true", default=False)
    p_adv.add_argument("--output-file")

    # 4. EVALUATION (Layer 3)
    p_eval = subparsers.add_parser("evaluation", help="Run evaluation matrix")
    p_eval.add_argument("--index-threshold", type=float, default=40.0)
    p_eval.add_argument("--delta-threshold", type=float, default=50.0)
    p_eval.add_argument("--output-file")

    # 5. DATA (Reference files)
    p_data = subparsers.add_parser("data", help="Get reference data")
    p_data.add_argument(
        "--type",
        choices=["schools", "fires", "weather", "live", "live-fires", "live-weather", "grap", "config"],
        required=True,
    )

    args = parser.parse_args()
    service = DhuanAlertService()

    if args.command == "run":
        hotspots = None
        weather = None
        schools = None

        if args.input_file and os.path.exists(args.input_file):
            with open(args.input_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "hotspots" in data and data["hotspots"]:
                hotspots = [Hotspot(**h) for h in data["hotspots"]]
            if "weather" in data and data["weather"]:
                weather = [WeatherObservation(**w) for w in data["weather"]]
            if "schools" in data and data["schools"]:
                schools = [School(**s) for s in data["schools"]]

        result = service.create_run(
            mode=args.mode,
            snapshot_id=args.snapshot,
            grap_stage=args.grap_stage,
            human_approved=args.human_approved,
            hotspots=hotspots,
            weather=weather,
            schools=schools,
        )

        out_dir = args.output_dir or os.environ.get("DHUANALERT_OUTPUT_DIR")
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
            with open(os.path.join(out_dir, "prediction.json"), "w", encoding="utf-8") as f:
                f.write(result["prediction"].model_dump_json(indent=2))
            with open(os.path.join(out_dir, "advisory.json"), "w", encoding="utf-8") as f:
                f.write(result["advisory"].model_dump_json(indent=2))
            with open(os.path.join(out_dir, "map.geojson"), "w", encoding="utf-8") as f:
                json.dump(result["map"], f, indent=2)
            with open(os.path.join(out_dir, "frontend_payload.json"), "w", encoding="utf-8") as f:
                f.write(result["payload"].model_dump_json(indent=2))
            with open(os.path.join(out_dir, "evaluation_report.json"), "w", encoding="utf-8") as f:
                f.write(result["evaluation"].model_dump_json(indent=2))
            print(f"[OK] Exported run files to {out_dir}")
        else:
            print(result["payload"].model_dump_json())

    elif args.command == "simulate":
        hotspots = None
        weather = None
        schools = None
        if args.input_file and os.path.exists(args.input_file):
            with open(args.input_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "hotspots" in data and data["hotspots"]:
                hotspots = [Hotspot(**h) for h in data["hotspots"]]
            if "weather" in data and data["weather"]:
                weather = [WeatherObservation(**w) for w in data["weather"]]
            if "schools" in data and data["schools"]:
                schools = [School(**s) for s in data["schools"]]

        pred = service.simulate_layer1(hotspots, weather, schools)
        if args.output_file:
            with open(args.output_file, "w", encoding="utf-8") as f:
                f.write(pred.model_dump_json(indent=2))
        else:
            print(pred.model_dump_json())

    elif args.command == "advisory":
        with open(args.prediction_file, "r", encoding="utf-8") as f:
            pred_data = json.load(f)
        pred = PredictiveOutput(**pred_data)
        adv = service.generate_advisory(pred, grap_stage=args.grap_stage, human_approved=args.human_approved)
        if args.output_file:
            with open(args.output_file, "w", encoding="utf-8") as f:
                f.write(adv.model_dump_json(indent=2))
        else:
            print(adv.model_dump_json())

    elif args.command == "evaluation":
        report = service.run_evaluation(
            index_threshold=args.index_threshold,
            delta_pm25_threshold=args.delta_threshold,
        )
        if args.output_file:
            with open(args.output_file, "w", encoding="utf-8") as f:
                f.write(report.model_dump_json(indent=2))
        else:
            print(report.model_dump_json())

    elif args.command == "data":
        if args.type == "schools":
            schools = service.get_sample_schools()
            print(json.dumps([s.model_dump() for s in schools], indent=2))
        elif args.type == "fires":
            fires = service.get_sample_fires()
            print(json.dumps([f.model_dump(mode="json") for f in fires], indent=2))
        elif args.type == "weather":
            weather = service.get_sample_weather()
            print(json.dumps([w.model_dump(mode="json") for w in weather], indent=2))
        elif args.type == "live":
            print(json.dumps(service.get_live_data_snapshot(), indent=2))
        elif args.type == "live-fires":
            print(json.dumps([fire.model_dump(mode="json") for fire in service.get_live_fires()], indent=2))
        elif args.type == "live-weather":
            fires = service.get_live_fires()
            print(json.dumps([item.model_dump(mode="json") for item in service.get_live_weather(fires)], indent=2))
        elif args.type == "grap":
            print(json.dumps(service.get_grap_catalog(), indent=2))
        elif args.type == "config":
            print(json.dumps(service.get_config_dict(), indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, TypeError, KeyError, IndexError) as error:
        message = str(error)
        error_code = message.split(":", 1)[0] if ":" in message else "PIPELINE_INPUT_ERROR"
        print(
            json.dumps({"status": "error", "code": error_code, "message": message}),
            file=sys.stderr,
        )
        raise SystemExit(2)
