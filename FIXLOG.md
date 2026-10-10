# DhuanAlert Fix Log — Layer 1 (ML model) + backend pass

Date: 2026-10-10. Base commit: `903aa58` + uncommitted FIRMS bbox change. Scope: brief Phases 0–4, 6, 7, and part of 1/8.
Frontend (Phase 5) was **not** touched in this pass.

## Phase 0 — Sanity pass
All cited lines in the brief were confirmed. Additional finding: `diffusion_field.extract_contour_geojson` was itself
only an axis-aligned bounding box, so "just calling it" would not have produced a real plume shape. `sample_weather.json`
contained a single hand-entered hour (NW wind toward Delhi), which cannot drive a time-varying run.

## Phase 1 — Silent fallbacks
- `open_meteo.py`: removed the Delhi `DEFAULT_LAT/LON`; `fetch_forecast(latitude, longitude, ...)` now requires a location.
  Added `precipitation` to the hourly request, plus an optional `start_date`/`end_date` window. Malformed rows are logged at WARNING.
- `service.py`: weather is fetched at the **strongest fire cluster centroid** (`primary_fire_location`). `create_run` modes are
  strict: `live` (FIRMS + Open-Meteo, T0 = now; zero fires raises `NO_ACTIVE_FIRES`), `replay` (bundled snapshot only,
  T0 = first recorded weather hour), `custom` (hotspots AND weather required). Unknown modes raise.
- `load_fallback_fires/weather`: raise `FileNotFoundError` instead of returning `[]`.
- `run_pipeline.py`: any exception exits 1 with a JSON line `{"status":"error","code",...}` on stderr.
- `backend/src/services/model.service.ts`: parses that line and maps it to an HTTP status (422 data, 502 upstream, 404 no backtest)
  and logs the raw stderr.

Verification (real output):
```
OPEN_METEO_BASE_URL=https://bad.invalid/v1 python run_pipeline.py run --mode live ...
{"status": "error", "code": "RuntimeError", "error_type": "RuntimeError", "message": "Open-Meteo request failed due to a network error or timeout."}  exit=1
NASA_FIRMS_MAP_KEY= python run_pipeline.py run --mode live ...
{"status": "error", "code": "RuntimeError", ... "message": "NASA_FIRMS_MAP_KEY is required to fetch live fire detections."}  exit=1
HTTP: POST /v1/runs {"mode":"live"} with bad weather host ->
502 {"error":{"code":"RuntimeError","message":"Open-Meteo request failed due to a network error or timeout."}}
```

## Phase 2 — Time-varying wind field (`weather_field.py`, rewritten)
- Takes `start_time`; stores the full sorted hourly series; linearly interpolates u, v, BLH, precipitation at
  `time_elapsed_seconds`. Outside the fetched window it raises `WeatherDataRangeError` (`WEATHER_RANGE_INSUFFICIENT`);
  `require_coverage()` checks the whole horizon before the run starts.
- Removed the uncalibrated `spatial_shear_*` constants. The field is now spatially uniform and documented as such.
- Removed the inverted BLH→K formula. K now comes from `SimulationConfig.base_diffusion_kx/ky` × the ensemble factor
  (the values the output already reported but never used).
- The engine now applies forecast precipitation to rain washout (previously never passed).
- The replay snapshot `sample_weather.json` was replaced with **real recorded GFS hourly data** (Open-Meteo, 30.249N 75.852E,
  2026-10-08 21:00Z → 2026-10-09 23:00Z, 27 hours).

Verification (replay, interpolated wind used by the engine):
```
h=0 u=-2.00 v=1.80 dir=132.0 BLH=50
h=3 u=-1.80 v=2.00 dir=138.0 BLH=55
h=6 u=-1.50 v=2.60 dir=150.0 BLH=350
h=9 u=-0.51 v=2.39 dir=168.0 BLH=1855
```
Live run (2026-10-10T17:33Z, 29 clusters): dir 101.6 → 95.3 → 110.4 → 120.5 deg, BLH 160 → 204 → 168 → 267 m.

## Phase 3 — Multi-horizon chaining (`ensemble.py`, `config.py`, `lagrangian_engine.py`)
- `SimulationConfig.horizon_hours = 9`, `forecast_horizons = [3, 6, 9]` (validated).
- `run_ensemble` runs each member as **one continuous integration**, deep-copying the cloud (`ParticleState.copy()`) at every
  whole hour → `{hour: [member states]}` for hours 0..9.
- Intersection envelope = real overlap of member bounding boxes (empty when members diverge), not a copy of the union.

Verification (replay, nominal member):
```
+3h particles=633 total_mass=0.552081 centroid=(30.4302, 75.6331)
+6h particles=633 total_mass=0.390760 centroid=(30.6509, 75.4694)
+9h particles=633 total_mass=0.276578 centroid=(30.9011, 75.3313)
mass ratio per 3h = 0.708 = exp(-3.2e-5 * 10800)
3h->6h per-particle check: expected advection (-15831 m, 24570 m), mean particle displacement (-15729 m, 24634 m),
std 2484 m vs sqrt(2K*3h) = 2324 m  -> same particles carried forward
```

## Phase 4 — Real timeline slices (`pipeline.py`, `diffusion_field.py`)
- Removed `np.random.seed(42 + h)`, the straight-line extrapolation and the hand-offset rectangles.
- One slice per hour (0..9) from the nominal member snapshot: centre = mass-weighted centroid; `heatmap_levels` = convex hulls
  of gridded (5.5 km) cells holding ≥60% / 25% / 5% of the peak cell mass; `scatter_points` = ≤150 real particles with
  mass-normalised weight; corridor = centroid track; `plume_area_sq_km` = area of cells above 5%.
- `prediction.weather.at_horizons` and `prediction.simulation.horizon_states` expose the numbers above in every run.
- The map GeoJSON now includes all fire clusters, not only the primary one.

Verification: replay centroids at +3h differ between two runs (30.4302 vs 30.4332): unseeded turbulence, same physics.

## Phase 6 — School arrival time (`school_scorer.py`)
- The flat 18 km/h estimate is gone. Concentration is sampled at every hourly snapshot for every member; arrival is the first
  time the ensemble-max crosses the threshold (linear interpolation between hours); exposure = number of hours above
  threshold; impact_probability = peak fraction of members above threshold.
- Verification: `test_replay_prediction_is_internally_consistent` asserts `(impact_probability > 0) == (arrival is not None)`.
  On both the replay and live inputs no Delhi school is reached within 9 h (the real winds blow NW/W, away from Delhi).

## Phase 7 — Honest evaluation
- `service.py` no longer imports `tests.test_evaluation`. `create_run` returns `evaluation: None`,
  `evaluation_status: "NOT_VALIDATED"`. `run_evaluation()` without real pairs raises `NO_VALIDATED_BACKTEST_AVAILABLE`.
- Backend: `runDemo()` was removed from `evaluation.service.ts` and moved into `backend/tests/evaluation.fixture.ts`, labelled
  synthetic. `GET /v1/evaluation` → `404 {"status":"NO_VALIDATED_BACKTEST_AVAILABLE"}`; `POST /v1/evaluation/evaluate`
  without `forecasts` + `observations` → 400.
- `demo.py` prints `NOT_VALIDATED` instead of fixture metrics. The README's backtest-results column was removed, with an explicit notice.
- `grep run_evaluation_demo|runDemo` → only `ml-model/tests/test_evaluation.py`.

## Tests
`ml-model`: 16 passed (5 new in `tests/test_layer1_physics.py`). `backend`: 9 passed (evaluation tests rewritten).

## Not done / known issues (honest list)
1. **Concentration index saturates.** `sample_point_concentration` scales by an arbitrary `×450`, so any point inside the
   plume reads 1.0 (all ensemble member peaks = 1.0). Thresholds (0.20 impact) are therefore effectively "any particle mass
   nearby". Fixing this needs the physical-units work below (Phase 8); it was not silently re-calibrated.
2. **BLH box model (Phase 8)** is not implemented. BLH is reported and interpolated but no longer affects concentration or K.
3. **Single weather point.** Live runs span ~29 clusters across 500 km but use the forecast at the strongest cluster only.
4. **Fire clustering** is still greedy star clustering (order-dependent), and `source_strength` is still a dimensionless proxy.
5. **Zero live fires** → `422 NO_ACTIVE_FIRES` (explicit failure, not a valid "nothing burning" forecast).
6. **Frontend (Phase 5)** not wired. Payload field names are unchanged, but `heatmap_levels[].coordinates` rings may now be empty
   when a level has no cells, and the 6 schools are still the bundled `ncr_schools.json`.
7. `openaq_waqi.py` / `osm_schools.py` were not audited (out of scope); `openaq_waqi.py` still has a silent fallback.

---

# Session 2 — physical units, clustering, API smoke test, frontend wiring (2026-10-10)

## Module 1: emissions + concentration (fixes "concentration index saturates")
- `config.py`: `smoke_emission_coefficient_kg_per_mj = 0.025` (Ichoku & Kaufman 2005; FEER v1), `emission_duration_hours = 3`
  (ASSUMPTION), `fire_persistence_efold_hours = 10` (ASSUMPTION), `kernel_sigma_m = 4000`, `min_mixing_height_m = 100`,
  thresholds 50 / 121 / 250 ug/m3 (CPCB PM2.5 breakpoints; 50 = the evaluation delta-PM2.5 threshold).
- `fire_source.py`: `emission_rate_kg_s = sum(Ce * FRP_i * exp(-age_i/10h))`; clusters are sorted by it.
- `lagrangian_engine.py`: particles carry PM2.5 mass in ug; `release_batch` emits one batch per cluster per hour for the
  first 3 h, instead of one puff at t=0.
- `diffusion_field.py`: **box model** `C = sum(m_i * K(r_i)) / H` with a normalised 2D Gaussian kernel and H = BLH at the
  snapshot hour (x ensemble factor, floor 100 m). Heatmap levels are absolute ug/m3 thresholds, not fractions of the peak.
- `school_scorer.py`: peak in ug/m3; risk score uses `peak / 250`; impact threshold 50 ug/m3.
- Replay result: emission 28.5 kg/s; near-source night-time concentrations of several hundred ug/m3; the >=250 core
  disappears at +9h when BLH reaches 1855 m. Member peaks 145 / 149 / 135 ug/m3 (previously all saturated at 1.0).

## Module 2: clustering
- Single-linkage connected components with a grid hash; input-order independent. Live clusters went from 29 to 20.

## Module 3: analytic control test (`tests/test_layer1_physics.py`)
- SYNTHETIC uniform 5 m/s westerly, school 60 km downwind: arrival must be 2.0–3.6 h (advection 3.33 h, minus the leading
  edge); a school 60 km upwind is never hit; +6h centroid is ~90 km east (batch ages 6/5/4 h). Passes.

## Module 4: backend
- New `npm run smoke` (`backend/scripts/smoke.ts`) calls all 30 routes. It found 2 real bugs, both fixed:
  1. Replay runs reused a T0-based prediction id, so a second replay run hit 500 EPERM on rename. Fix: id/`generated_at` use
     wall-clock time; `valid_from` = T0.
  2. `GET /v1/config` served a stale hand-copied config (`horizon_hours: 6`). It now returns the model's real config.
- Result: `ALL ROUTES OK` (30/30; live run 201, bad mode 422, missing run 404, evaluation 404, empty evaluate 400).

## Module 5: frontend
- New "Smoke forecast" tab (`ForecastView.tsx`) mounts the existing `PlumeMap`, `TimelineSliderControl` and `SchoolRiskTable`
  on `POST /v1/runs` (replay or live), with a **verification panel** of raw wind/BLH and centroid/mass per horizon, plus a
  link to the raw prediction JSON. The live tab is unchanged.
- Removed fabricated values from `SchoolRiskTable` (a hard-coded 10-school list, `342 - idx*22` PM2.5, fake arrival ranges,
  LOW shown as "Medium"). It now shows real ug/m3, arrival from T0, ensemble probability and the real band.
- `tsc` clean, `vite build` OK, and a cross-origin POST from http://localhost:5173 returns 201.

## Still not done
- Single weather point for all clusters; persistence/emission-duration constants are assumptions; still no hindcast
  validation; `openaq_waqi.py` silent fallback; the map was not inspected visually by me (no browser available in this session).

---

# Session 3 — "the map still looks hardcoded" (2026-10-10)

The user's screenshot showed only 6 Delhi schools and no plume. Root causes, all confirmed in code:
1. `PlumeMap.tsx` was pinned to a fixed view (29.5N 76.5E, zoom 7.5) and never moved to the data; the plume
   (Punjab, ~30-31N 73-76E) was off-screen. **Fixed:** fit bounds to fires + all particles + impacted schools on each run.
2. Schools were the 6-entry `ncr_schools.json` on every run. **Fixed:** `OsmSchoolClient.fetch_schools_in_bboxes` queries
   OpenStreetMap Overpass for `amenity=school` inside the plume footprint (cells >= 50 ug/m3 for any member at any hour,
   grouped into connected blobs). Retries the same server on 429/504; otherwise fails loudly. Replay run: 654-704 schools,
   ~67 reached. Scoring is vectorised. Distance is to the nearest cluster.
3. **`sample_fires.json` was hand-made:** 5 detections at 142-380 MW each, vs the real FIRMS median of 4.35 MW (max 19 MW).
   **Fixed:** `capture_replay_snapshot.py` captures real FIRMS + GFS data and writes `replay_snapshot_meta.json`. The current
   snapshot is 75 detections, 2026-10-10 07:24-09:07Z, T0 10:00Z.
4. Only the primary fire was drawn, one convex hull spanned all clusters (a polygon from Punjab to 27.6N), and the
   corridor was the centroid of all 20 clusters. **Fixed:** every cluster is drawn; there is one polygon per connected density
   blob (`heatmap_levels[].polygons`); particles carry a `source` cluster id and the corridor is a MultiLineString of
   per-cluster tracks.
5. The replay label still named the old 2026-10-08 data; the default is now live.

Independent check: `ml-model/plot_run.py` renders a stored run with matplotlib (`output/replay_run_plot.png`):
20 plumes advect WSW and curve as the wind veers 56 -> 113 deg; schools reached go 0 -> 23 -> 66 -> 68 at +0/+3/+6/+9 h.
Tests: ml 17/17, backend 9/9, smoke 30/30, tsc clean.
Known limit: one weather point for all clusters, so all tracks are parallel.

---

# Session 4 — Pakistan fires, uniform wind, double runs, restyle (2026-10-10)

1. **Fires in Pakistan.** The corridor bbox overlaps Pakistani Punjab; 61 of 75 live detections were there (Lahore, Kasur,
   Okara, Gujranwala). The FIRMS country API returns HTTP 400. **Fixed:** `points_in_india()` (ray casting against the Natural
   Earth 1:10m India boundary, `src/data/india_boundary_ne10m.json`, public domain) filters FIRMS detections and OSM schools.
   Checked on reference cities: Lahore, Kasur, Okara and Bahawalnagar are excluded; Amritsar, Fazilka, Sri Ganganagar,
   Ferozepur and Delhi are kept. Live: 75 -> 14 detections. Replay snapshot re-captured (14 detections, 8 clusters).
2. **One weather point for all fires** (plumes moved in parallel). **Fixed:** `fetch_forecast_points` gets GFS at a 1-degree grid
   around the fires (+1.5 deg margin) plus the strongest cluster centroids (71 points); `WeatherVectorField` interpolates
   in time per station and then by inverse distance (p=2) in space. BLH and rain are per particle, and concentration divides
   each particle's mass by its own mixing height. At T0 the replay stations span wind-from 62-296 deg and BLH 205-3730 m.
   New test: the field reproduces each station's wind at its own location and the average at the midpoint.
3. **Two runs per click/page load** (React StrictMode double effect). **Fixed** with a ref guard in `useForecast`.
4. **Quiet live days looked broken.** Added a WHO 15 ug/m3 "trace" level (drawn and used for the school search), per-slice
   `peak_concentration_ugm3`, and a banner stating the peak and fire age when no school crosses 50 ug/m3.
5. **Restyle:** new forecast view (`ForecastView.tsx` + scoped `forecast.css`): hero with Live/Replay switch, KPI strip for
   the selected hour, Esri dark basemap, sidebar (atmosphere, chained plume state, ensemble, caveats), styled school table,
   deep links `?view=forecast&mode=replay`. Verified with headless-Edge screenshots of live and replay.

Verification: `verify_run.py replay` chaining error 0.07 / 0.17 km with the spatial field; ml 18/18, backend 9/9, smoke 30/30.
Live runs take ~15-20 s (Overpass rate limits trigger retries).
