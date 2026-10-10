# DhuanAlert Repair Status

Last verified: 2026-10-10

## Repairs completed

### 1. Time-varying weather field

- Wind components (`u`, `v`) and boundary-layer height are linearly interpolated across timestamped forecast observations.
- The simulation run timestamp is passed into the ensemble and weather field.
- Uncalibrated spatial wind shear was removed.
- Empty, duplicate, timezone-naive, negative-time, and out-of-coverage weather requests fail with `WEATHER_COVERAGE_ERROR`.
- Forecast coverage is checked for the full simulation horizon before particles are initialized.

### 2. Explicit data contract and error propagation

- Live weather has no Delhi default: it is requested at the strongest detected fire-cluster centroid.
- FIRMS defaults to the Punjab–Haryana–Delhi corridor rather than all India.
- Custom/direct simulations require explicit non-empty fires, weather, and schools; no bundled input is inserted silently.
- Malformed Open-Meteo hourly arrays fail with `OPEN_METEO_SCHEMA_ERROR`; malformed records are not skipped.
- CLI failures emit JSON to stderr and exit non-zero.
- The Node API maps known model-input failures to a machine-readable HTTP `422` response, including `WEATHER_COVERAGE_ERROR`.

### 3. Continuous particle timeline (+3h, +6h, +9h)

- Each ensemble member is stepped continuously from T+0 through T+9; no horizon is restarted from the source.
- Independent particle checkpoints are retained every hour, including T+3, T+6, and T+9.
- Timeline scatter points are direct samples of checkpoint particle coordinates and their normalized mass; no seeded scatter is used.
- Timeline centreline, footprint area, and remaining-mass intensity are computed from checkpoint particle states.
- Rectangle plume geometry and `heatmap_levels` are removed from the emitted timeline payload.
- The plume polygon is a mass-weighted 90% particle-cloud convex hull, not an axis-aligned bounding box.
- The frontend map renders the particle-cloud hull and does not render legacy rectangle heatmaps.

## Verification completed

| Check | Result |
| --- | --- |
| Python model tests | 24 passed |
| Backend TypeScript build | passed |
| Backend API tests | 8 passed |
| Frontend production build | passed |
| Live input diagnostic | 75 corridor FIRMS detections and 48 Open-Meteo observations returned successfully |
| Nine-hour Layer 1 fixture | Returns T+0 through T+9, with particle-hull contours at T+3/T+6/T+9 and no legacy heatmaps |

## Expected failures that are now visible

| Condition | Returned error | Why it is correct |
| --- | --- | --- |
| No input supplied to direct simulation | `MISSING_SIMULATION_INPUT` | The service no longer loads bundled data invisibly. |
| Bundled replay snapshot | `WEATHER_COVERAGE_ERROR` | The repository only contains one stale weather timestamp, which cannot cover a 9-hour run. |
| Missing fire location for live weather | `WEATHER_LOCATION_REQUIRED` | Live weather is never substituted with a fixed Delhi location. |

## Remaining repair work

1. **Replay dataset** — supply a real, immutable replay bundle with a recorded run timestamp, matching FIRMS fires, and at least 9 hours of timestamped weather. The present sample data intentionally fails instead of being stretched.
2. **School arrival and exposure** — replace the hardcoded 18 km/h arrival estimate with the first hourly particle-snapshot concentration threshold crossing.
3. **Concentration representation** — replace the current particle hull with a gridded concentration field and isolines/raster. The current hull is real particle-derived geometry, but it is an envelope rather than a concentration isoline.
4. **Ensemble footprint semantics** — calculate a true overlap/intersection footprint; the current reported intersection remains the union approximation.
5. **Frontend integration** — mount the forecast dashboard (`PlumeMap`, timeline, risks) in `App.tsx`; it currently remains disconnected from the live-data-only view.
6. **Evaluation integrity** — remove demo/test evaluation from production calls and return `NOT_VALIDATED` until a real hindcast dataset is supplied.
7. **School source integrity** — replace the bundled school file with an explicit verified source or clearly designate it as a replay-only dataset.
8. **Physical calibration** — convert the fire source proxy to an emission-rate model and implement BLH dilution in the concentration calculation.
