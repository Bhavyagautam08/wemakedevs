import json
import subprocess
import sys
from pathlib import Path


def test_simulate_without_explicit_input_exits_nonzero_with_structured_error():
    model_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "run_pipeline.py", "simulate"],
        cwd=model_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    error = json.loads(result.stderr)
    assert error["status"] == "error"
    assert error["code"] == "MISSING_SIMULATION_INPUT"
