# DhuanAlert repair summary

## What I understand

The repository already contains real physics and pipeline components, but several production paths are bypassing the real model and replacing it with synthetic or demo output.

The key issues are:

1. The Python predictive pipeline is building timeline slices from hard-coded, seeded synthetic scatter points and rectangle polygons instead of real particle-state output.
2. The weather vector field is effectively static because it ignores time and uses only the first weather observation; it does not vary over the forecast horizon as required.
3. The frontend app is mounted to the live FIRMS-only dashboard and never renders the real plume forecast view.
4. Production evaluation is calling a demo/test function (`run_evaluation_demo` / `runDemo`) instead of actual validation data.
5. The repo has the right architecture for a real forecast pipeline, but the actual live wiring is disconnected and some paths silently fall back to invented output.

This violates the project brief: real simulation only, no hallucination, no fake fallback, no silent substitute data.

## Real root cause

The real simulation machinery exists:

- `ml-model/src/layer1_predictive/lagrangian_engine.py` performs particle advection and decay.
- `ml-model/src/layer1_predictive/ensemble.py` runs multi-member scenarios.
- `ml-model/src/layer1_predictive/weather_field.py` is meant to provide time-varying meteorological forcing.
- `frontend/src/components/PlumeMap.tsx` is a legitimate map component for forecast visualization.
- `frontend/src/hooks/useForecast.ts` and `frontend/src/api/client.ts` already contain the expected forecast API integration.

The breakage is mainly in integration and honesty:

- the timeline generator is not using ensemble particle output;
- the weather forcing is not time-aware;
- the application does not mount the forecast dashboard;
- the service/controller layer is returning demo evaluations from test code.

## What I was going to fix, fast

### 1) Fix the physics pipeline

File(s):
- `ml-model/src/layer1_predictive/weather_field.py`
- `ml-model/src/layer1_predictive/pipeline.py`

Planned fix:
- store the complete weather observation sequence, not only the first item;
- use `time_elapsed_seconds` and the forecast timestamp window to interpolate wind and boundary-layer conditions through time;
- fail loudly when forecast data is missing or out of range;
- rewrite `_generate_timeline_slices()` to accept actual particle snapshots and build scatter/contours from real particle positions rather than deterministic synthetic rectangles.

### 2) Fix multi-horizon forecast continuity

File(s):
- `ml-model/src/layer1_predictive/ensemble.py`
- `ml-model/src/layer1_predictive/lagrangian_engine.py`

Planned fix:
- use the real particle state across the forecast chain instead of recomputing a fake visual plume each hour;
- preserve monotonic mass decay and physically plausible dispersion across +3h, +6h, +9h propagation;
- ensure each future slice comes from the same underlying particle evolution, not seeded random geometry.

### 3) Reconnect the frontend to the real forecast

File(s):
- `frontend/src/App.tsx`
- `frontend/src/components/PlumeMap.tsx`
- `frontend/src/hooks/useForecast.ts`

Planned fix:
- mount `PlumeMap` in the app root instead of only rendering `LiveMap`;
- feed the real `FrontendPayload.prediction` into the plume map and timeline slider flow;
- keep live FIRMS weather/fire data visible as a separate source, but do not hide or replace the real forecast overlay.

### 4) Remove demo evaluation from production

File(s):
- `ml-model/src/service.py`
- `backend/src/controllers/evaluation.controller.ts`
- `backend/src/services/evaluation.service.ts`
- `ml-model/tests/test_evaluation.py`

Planned fix:
- remove unconditional imports and invocations of `run_evaluation_demo()` in the live pipeline;
- return an explicit “not validated / no ground-truth dataset available” outcome instead of silently returning synthetic metrics;
- keep demo/test functions clearly marked as offline or test-only, not production default behavior.

### 5) Real runtime validation

Planned validation: not unit tests alone.
- run the actual model pipeline through the backend API;
- inspect the generated `prediction.timeline`, `map_geojson`, and forecast outputs;
- confirm the app renders real forecast slices and not the live FIRMS-only placeholder view;
- confirm no demo evaluation path is triggered by production requests.

## Final status

The underlying issue is not a missing model. The issue is that the actual model outputs are being bypassed or replaced with synthetic/demo behaviors in the live path.

The correct repair is to restore the real simulation flow, not to invent a fake fallback that looks good in screenshots.
