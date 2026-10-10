# DhuanAlert — Systems Engineering Fix Brief

**Paste this entire document as your first message to Antigravity / Codex / Cursor / Claude Code / any coding
agent working in this repository.** It is pre-researched: every claim below was verified by reading the actual
file at the stated line, in this repo, at commit `be67ba80d5f089cfb288d5415f14926391f14147`, on 2026-10-10. Do
not re-derive the system's state from vibes or from a prior agent's summary — verify each cited line yourself
(one read is enough, you don't need to re-audit the whole tree), then act. Previous agent sessions on this repo
produced confident-sounding but wrong or fabricated output (a README claiming validated backtest numbers that
are actually a hardcoded test fixture; a frontend disconnected from a working backend while both sides looked
individually "done"). That failure mode is the thing to avoid this time, more than any individual bug below.

---

## 0. Your role and operating rules for this session

You are acting as a **systems engineer doing a diagnosis-then-repair pass**, not a feature-building agent and
not a report-only auditor. Think from first principles: for every component, ask "what physical or logical
quantity is this supposed to compute, and does the code actually compute it from its stated inputs, or does it
substitute something else?" Specifically:

1. **No silent fallback, anywhere, ever again.** If live data, a file, a config value, or a prior pipeline stage
   is missing or invalid, the code must raise/throw with a specific, structured error message and the caller
   must surface it (HTTP 4xx/5xx with a machine-readable `status` field, or a CLI non-zero exit with the reason
   on stderr) — never silently substitute a hardcoded number, a bundled sample file, or a synthetic value and
   continue as if nothing happened. Section 5.2 names the exact files that still violate this and the exact
   files that already do it correctly — copy the pattern from the latter.
2. **Don't rewrite what already works.** This codebase is not uniformly broken. Section 2 tells you precisely
   which modules are solid and should be edited surgically (a few lines) versus which are fabricating data and
   need a real implementation. Rewriting a working file from scratch is how this project got into its current
   state (orphaned, duplicated, half-finished components) — don't repeat that.
3. **Verify by running, not by reading.** After each phase in Section 6, actually execute the verification
   command listed and look at the real output. "I edited the function so it should now work" is not acceptable
   evidence. Paste real command output into your fix log (Section 8).
4. **Cite file:line for every claim you make in your own output**, exactly as this document does for you. If you
   assert something is fixed, cite the diff. If you assert something is still broken, cite the line.
5. **Stay in scope.** Section 7 lists what is explicitly deferred. Do not touch Layer 2 (GenAI/Bedrock/Cedar
   advisory generation), do not attempt AWS deployment, do not restyle the UI. The only goal this pass: the
   physics simulation runs on real, time-varying inputs, produces real (not fabricated) output at +3h/+6h/+9h,
   and that real output is what the frontend actually renders.

---

## 1. What this system is supposed to do (one paragraph, so every fix is judged against it)

Given active-fire detections (NASA FIRMS) and a wind/boundary-layer forecast (Open-Meteo) for Punjab/Haryana,
estimate a relative smoke-source strength per fire cluster, release virtual particles from each cluster, advect
them forward through a time-varying 2D wind field with stochastic turbulent diffusion and mass decay, snapshot
the particle cloud at +3h/+6h/+9h (each snapshot continuing from the previous one's particle positions, not
restarting), turn each snapshot into a concentration field, sample that field at school coordinates to produce
a risk score and a real (not distance/speed-estimated) arrival time, and ship all of that — fire points, the
three time-sliced plume snapshots, and school risk — to a frontend that animates it on a map. Evaluation against
real OpenAQ/CAAQMS ground stations is a separate, honest validation step that must be clearly distinguished from
this forward simulation and must never run on synthetic stand-in data without saying so.

---

## 2. Verified state of the repository, by component

### 2.1 Data ingestion — `ml-model/src/data_sources/` — **mostly already correct, use as the template**

- `nasa_firms.py` (`fetch_active_fires`, lines 34–62) and `open_meteo.py` (`fetch_forecast`, lines 33–63): **this
  is the fail-loud pattern you should replicate everywhere else.** Live calls raise `RuntimeError` on missing
  API key, HTTP error, timeout, or malformed response — they do **not** fall back to `load_fallback_*()`. Keep
  this. `load_fallback_fires()` / `load_fallback_weather()` still exist as explicit, separately-invoked methods
  for `mode="replay"` — that's fine, an explicit opt-in replay mode is not the same as a silent fallback, as
  long as nothing calls it automatically when live mode fails (confirm this stays true after your changes).
- `open_meteo.py` lines 20–21: `DEFAULT_LAT = 28.6139, DEFAULT_LON = 77.2090` (Safdarjung, central Delhi) is
  still the default argument to `fetch_forecast()`, and `service.py` line 82 (`get_live_weather`) calls it with
  **no arguments**, so weather is always queried at a fixed point in Delhi regardless of where the fires
  actually are. Fix: thread the fire cluster centroid (or a small grid around it) into the weather fetch call.
- `open_meteo.py` `_parse_response` (lines 65–116) **already returns every hourly observation Open-Meteo gives
  it** (confirmed: it loops over the full `hourly.time` array), not just one point. This matters for Section
  2.2 — the data is already there, the physics layer just isn't using it yet.
- `osm_schools.py`, `openaq_waqi.py`: not re-audited in this pass (out of scope — see Section 7). If you touch
  them, apply the same fail-loud rule.

### 2.2 Coordinate system — `ml-model/src/layer1_predictive/coordinates.py` — **correct, already fixed, leave alone**

A proper local equirectangular projection (`LocalMetricProjection`, lines 13–45) converts lat/lon to meters
around an origin near `29.5°N, 76.5°E` and back. The Lagrangian engine and diffusion field both already do all
particle math in meters and only convert to WGS84 for output. This was flagged as missing in an earlier audit;
it has since been built correctly. Nothing to do here.

### 2.3 Lagrangian particle engine — `ml-model/src/layer1_predictive/lagrangian_engine.py` — **core loop is real, but 2D and static-wind**

`ParticleState` (lines 16–27) holds `x, y, mass, initial_mass` only — **no `z` coordinate, confirmed**. `step()`
(lines 81–147) does real work: wind advection, `sqrt(2*K*dt)` Brownian turbulent kicks, exponential mass decay,
rain washout, and pruning of particles below 1% of initial median mass. This is a legitimate, if simplified,
stochastic transport step — not fabricated. The problems are elsewhere (2.4) and in what happens to its output
afterward (2.6).

**Direct answer to "where do we get the z-axis":** you don't have one, and the honest short-term fix is not to
invent one. `weather_field.py` line 79–80 already documents the intended simplification correctly: *"The model
is strictly 2D... BLH modulates horizontal confinement (inversion lid effect), not 3D vertical coordinates."*
That is a legitimate, standard simplification (a "well-mixed box" approximation) **provided it is actually
implemented as a box model** — i.e., ground concentration should scale as `mass / (horizontal_area × BLH)`, so
a lower BLH traps the same mass into a shallower layer and raises surface concentration. Verify in Section 2.5
below: right now BLH only rescales the horizontal diffusion coefficient, it never divides concentration by BLH.
Fix that relationship (Section 6, Phase 8) rather than adding a fake `z` coordinate with no vertical wind data
to drive it — Open-Meteo's free tier does not give you a vertical wind profile, so a "3D" engine with no real
vertical input would just be a more elaborate fabrication.

### 2.4 Wind field — `ml-model/src/layer1_predictive/weather_field.py` — **THE central physics bug**

- `__init__` (lines 26–29): `self.baseline = observations[0]` **unconditionally**, regardless of whether 1 or
  48 observations were passed in. Confirmed: there is no code path that uses `observations[1:]`.
- `get_wind_vector()` (lines 31–68): takes a `time_elapsed_seconds` parameter and **never references it in the
  function body**. Confirmed by reading the full function — wind direction/speed come only from
  `self.baseline`. This is why the user's own testing showed wind "going in a straight line": it is, literally,
  because the same wind vector is reused for every single timestep across the whole 3/6/9-hour run.
- Lines 62–63: `spatial_shear_u = 0.0000005 * y_meters`, `spatial_shear_v = -0.0000003 * x_meters` — uncalibrated
  constants invented to fake spatial variation; no cited source, no units derivation.
- `get_blh_and_diffusivity()` (lines 70–93): same issue, `time_elapsed_seconds` unused; BLH also comes from a
  single static `self.baseline` value, never the time-matched hourly BLH.

**This is the one fix that matters most.** Section 2.1 already confirmed Open-Meteo gives you the full hourly
series. The fix is almost entirely in `weather_field.py`: store the full observation list, and at a given
`time_elapsed_seconds`, find the two bracketing hourly observations and linearly interpolate `u`, `v`, and `BLH`
between them (temporal interpolation — this is explicitly called for in the project's own earlier design
notes: *"spatial wind interpolation, temporal wind interpolation"* were listed as required engine capabilities).
Spatial interpolation across a wind grid is a reasonable stretch goal but temporal interpolation from the
single point you already fetch is the higher-value, lower-effort fix — do that first.

### 2.5 Diffusion field — `ml-model/src/layer1_predictive/diffusion_field.py` — **two of three methods are real but unused**

- `sample_point_concentration()` (lines 52–85): **real, in active use.** Does a proper Gaussian-kernel-weighted
  sum of particle mass within a search radius of a target point, scaled to `[0, 1]`. This is what feeds school
  risk scoring (2.6) and is legitimate.
- `compute_gaussian_spread()` (lines 30–50) and `extract_contour_geojson()` (lines 87–132): **fully implemented,
  mathematically reasonable, and never called from anywhere else in the codebase** (confirmed via grep — zero
  call sites outside this file). `extract_contour_geojson` takes a real `ParticleState` and produces a real
  bounding polygon in WGS84. This is the function that should be feeding the frontend's plume contours — see
  Phase 4 in Section 6. You do not need to write a new contour function; you need to call this existing one.
- BLH-to-concentration relationship: confirmed **not implemented** anywhere in this file — `sample_point_
  concentration` does not divide by BLH. See Section 2.3's note on the box-model fix.

### 2.6 Multi-scenario ensemble — `ml-model/src/layer1_predictive/ensemble.py` — **no horizon chaining exists**

- `run_ensemble()` (lines 36–125): for each of 3 members, steps particles forward `total_steps` times (derived
  from a single `horizon_hours`, default 6) and keeps **only the final state**. There is no snapshotting at
  intermediate hours, no return of a +3h state, and nothing resembling "the +3h output seeds the +6h run" — the
  entire run is one undifferentiated forward pass to a single horizon. This is the direct cause of the user's
  complaint: *"I need the 6th hr prediction based on the points given by the 3rd hr prediction."* It currently
  does not exist in any form. Section 6 Phase 3 specifies the fix.
- Lines 119–122: `affected_area_intersection_geojson = union_poly  # MVP approximation` — the "intersection" of
  the ensemble envelope is still literally set equal to the union, confirmed unchanged. Low priority (Section 6
  Phase 8) — it doesn't block the simulation from running, it just makes the reported uncertainty envelope
  slightly wrong.
- `evaluate_location_impact()` (lines 127–155): real logic — counts how many of the ensemble members exceed a
  concentration threshold at a target point and returns `affected/total` as `impact_probability`. Legitimate.

**Direct answer to "is the fire clustering/source-strength model scientifically feasible":** see
`fire_source.py` (lines 103–127). It blends log-saturated total FRP, hotspot density, detection confidence, and
a recency decay into a dimensionless `[0.05, 1.0]` number, and its own docstring correctly calls this "a
relative source/emission strength proxy," not a physical emission rate. That is a defensible, honestly-labeled
simplification for an MVP — the problem is not that it's "made up," it's that nothing downstream ever converts
it into a real unit (kg/s of PM2.5, via something like `E ≈ C_e × FRP_MW` with a literature emission factor).
That conversion is a real scientific upgrade you can make later (Section 7), not a bug to panic-fix now. The
clustering itself (lines 37–51) groups each unclustered hotspot against *all* other unclustered hotspots within
12 km — note this is still a greedy star-cluster (each group only checks distance to its first/seed point, not
transitively through members already added), so result can depend on input order. Low priority (Section 6
Phase 8).

### 2.7 School risk scoring — `ml-model/src/layer1_predictive/school_scorer.py` — **internally inconsistent**

`assess_schools()` (lines 31–115): `impact_probability`, `peak_concentration`, and `uncertainty` (lines 56–61)
are correctly derived from the real ensemble particle cloud via `sample_point_concentration`. But
`predicted_arrival_time` (lines 63–68) is computed from a **flat, hardcoded 18 km/h straight-line advection
speed**, completely decoupled from the actual simulated particle positions. Result: a school can show a high,
physics-derived `impact_probability` next to an arrival time that has nothing to do with the simulation that
produced that probability — these two numbers can visibly contradict each other on the frontend. Fix (Section 6
Phase 6): derive arrival time from the same particle/concentration data already being sampled — e.g., re-run
`sample_point_concentration` (or reuse per-horizon snapshots from Phase 3) at each horizon boundary and record
the first horizon at which concentration crosses the impact threshold at that school's location.

### 2.8 Timeline slices (what the frontend would animate) — `ml-model/src/layer1_predictive/pipeline.py` — **100% fabricated, confirmed**

`_generate_timeline_slices()` (lines 165–273): **does not take `final_particles` as a parameter at all** —
confirmed by reading the full function signature and body. It recomputes plume position from scratch using a
straight-line hourly displacement (`dx_deg_per_hr`, `dy_deg_per_hr`, lines 178–180) derived from a single static
weather point, then calls `np.random.seed(42 + h)` (line 203) before generating 35–55 scatter points per hour
and three hand-shaped rectangle polygons (`heatmap_levels`, lines 213–250) with fixed offset multipliers. None
of this reads from the real `ParticleState` the Lagrangian engine actually computed one function call earlier
in `pipeline.py` line 79. **This is the single biggest reason the frontend "isn't simulating anything."** The
real simulation runs, produces real particle positions, and then is thrown away in favor of a seeded-random
decoy before the data ever reaches the API. Fix (Section 6 Phase 4): this function needs the actual particle
snapshots (which will exist once Phase 3 is done) and should call the already-existing, already-correct
`diffusion_field.extract_contour_geojson()` (Section 2.5) instead of drawing rectangles, and should emit real
particle sample positions (subsampled, with real mass as weight) instead of `np.random.normal`.

### 2.9 Evaluation / "ground truth" — **confirmed fabricated on every call path, in two independent places**

**Direct answer to "what IS the so-called ground truth, since we obviously can't see the future":** you're
right, and the honest answer is that this system is not supposed to validate itself against the future — it's
supposed to validate itself against the *past*. Pick a historical day when a real smoke event happened (e.g. a
high-FRP day in Nov 2024), freeze the fire/weather data that would have been available at that day's T0, run
the forecast forward as if it were live, and then compare that forecast against what OpenAQ/CAAQMS stations
*actually measured* hours later that same historical day. That's "hindcasting" — nothing about it requires
seeing the actual future, because by the time you run the comparison, the "future" (hours after a 2024 day) is
already in the past. **This system does not currently do that, anywhere:**
- `ml-model/src/service.py` line 39: `from tests.test_evaluation import run_evaluation_demo` — **a production
  service module imports a function out of the test directory.** That's a structural red flag by itself.
- `ml-model/src/service.py` line 164, inside `create_run()` (the function behind every `POST /v1/runs` call):
  `evaluation_report: EvaluationReport = run_evaluation_demo()` — called unconditionally on **every** run,
  live or replay, regardless of what fires/weather were actually simulated.
- `ml-model/tests/test_evaluation.py` lines 14–69: `run_evaluation_demo()` fabricates 4 fixed stations and 12
  hourly steps using hardcoded step functions (`sim_spike = 1.0 if step >= 4 else 0.0`, etc.) — not derived from
  any real OpenAQ pull or any real simulation output.
- **The Node backend independently re-implements the same fabrication**, not a proxy of the Python one:
  `backend/src/services/evaluation.service.ts` lines 160–217, `runDemo()`, hardcodes the **same four stations**
  and the **same step-function spike logic** in TypeScript. `backend/src/controllers/evaluation.controller.ts`
  lines 6–17 (`getLatestEvaluation`) and lines 19–41 (`evaluateCustom`) both fall back to `EvaluationService.
  runDemo()` whenever no stored report or explicit forecasts/observations are supplied — and nothing in this
  codebase currently supplies real ones.
- The scoring math itself is **not** the problem and should be kept: `evaluateGroundTruth()` in
  `evaluation.service.ts` (lines 52–158) and `evaluate_model_against_ground_truth` in `ml-model/src/model/
  evaluation.py` correctly compute POD, FAR, CSI, Spearman ρ, Pearson r, and median arrival lag from whatever
  forecast/observation pairs they're given. The bug is 100% in what feeds them, not in the metric math.
- **The README's claimed backtest numbers (arrival lag 1.0h, POD 0.91, FAR 0.17, CSI 0.77, envelope reliability
  95%) are, as far as this repo's code shows, the deterministic output of the fabricated fixture above, not a
  real historical validation.** Fix this immediately and separately from the physics work (Section 6 Phase 7)
  — it is actively misrepresenting the project's validation status to anyone reading the README, including
  hackathon judges.

### 2.10 Node backend (`backend/`) — **genuinely solid, do not rewrite, only wire up real data**

This layer did not exist in an earlier audit of this project and represents real, completed engineering:
`backend/src/services/model.service.ts` correctly shells out to `ml-model/run_pipeline.py` as a subprocess and
parses its JSON output (lines 19–110); `backend/src/controllers/runs.controller.ts` implements a complete,
sensible REST surface (`POST /v1/runs`, `GET /v1/runs/:id`, `/timeline`, `/schools`, `/ensemble`, `/map.geojson`
— lines 8–213) with real input validation (lines 15–23) and real disk-backed persistence via `backend/src/
services/storage.service.ts` (atomic pending-dir-then-rename writes under `output/api-runs/`). **Nothing here
needs rewriting.** The only backend change required is Section 6 Phase 7 (stop defaulting evaluation to the
fabricated demo).

### 2.11 Frontend — **orphaned, not broken — this is the cheapest high-impact fix in the whole repo**

`frontend/src/App.tsx` (104 lines, read in full) renders exactly two things: a live-source status grid and
`<LiveMap data={data} />`, sourced only from `useLiveData` → `GET /v1/data/live` (raw FIRMS points + current
weather, no simulation). **Confirmed by reading every import in the file: it does not import `PlumeMap`,
`TimelineSliderControl`, `SchoolRiskTable`, `AdvisoryBanner`, `EvaluationReportCard`, `SidebarControls`,
`TopNavbar`, `BottomTelemetryBar`, `useForecast`, `useTimelineSlider`, or `useSchoolRiskFilter` — every one of
these files exists in the repo and is never imported by anything.** This is exactly why the user sees "just fire
points" and nothing simulated.

Critically, these orphaned files are **not stubs** — they were read and are complete, working implementations:
- `frontend/src/components/PlumeMap.tsx` (376 lines, read in full): a real Leaflet map component that renders a
  fire marker, a corridor polyline, multi-level heatmap polygons from `TimelineSlice.heatmap_levels`, particle
  scatter circles from `TimelineSlice.scatter_points`, and school risk pins with color-coded risk bands and
  popups — all driven by props (`prediction`, `currentSlice`, `schools`) that match the backend's actual JSON
  shape exactly. It even already has an honest disclosure string baked in (line 274): *"Sample plume outlines
  and particle scatter are illustrative model visualizations."* This component needs **zero rewriting** — once
  Phase 4 makes the backend's `TimelineSlice` data real instead of fabricated, this component will render real
  data with no changes to itself.
- `frontend/src/api/client.ts` (lines 39–68): already has `createRun()`, `getRun()`, `getRunMap()`,
  `getRunTimeline()`, `getRunSchools()`, `reviewAdvisory()`, `getEvaluation()` — the full method surface needed,
  matching the backend routes exactly.
- `frontend/src/hooks/useForecast.ts` (45 lines, read in full): a complete, working hook that calls
  `client.createRun()` or `client.getRun()` and manages loading/error state correctly.

**Fix (Section 6 Phase 5) is primarily composition, not construction:** wire these existing, working pieces
into `App.tsx` (or a new route/tab alongside the current live-FIRMS view, your call) so `POST /v1/runs` actually
gets triggered and its response actually reaches `PlumeMap`. This is low-risk, high-visible-impact work — do it
early so you have a visual way to confirm Phases 2–4 are producing real output, not just trust test assertions.

### 2.12 Tests — `ml-model/tests/`

**Direct answer to "what is the test folder doing":** two different things, and they should not be confused.
`test_live_data_sources.py` (72 lines, read) is a **legitimate, well-written unit test suite** — it mocks
`urlopen` and checks CSV/JSON parsing edge cases (empty responses, column schema, bbox defaults). Keep and
extend this; it's a model for how to test the rest of the ingestion layer. `test_evaluation.py`, by contrast,
contains `run_evaluation_demo()` — not a test in the pytest sense (it has no `test_` prefix function wrapping
it, no assertions) but a **fixture-generating function that production code imports and calls live** (Section
2.9). That is the part to fix.

### 2.13 "Human-in-the-loop" — `ml-model/src/service.py` lines 215–264, `review_advisory()`

**Direct answer:** this is Layer 2 (advisory/policy), out of scope for this pass (Section 7), but since it was
asked: the function takes an already-generated bilingual advisory plus an officer's `APPROVE`/`REJECT` decision,
re-runs each recommended action through the Cedar policy authorizer with `human_approved` set accordingly, keeps
only actions that come back `ALLOW`ed (or keeps everything if rejecting, since a rejected advisory's actions
don't need to be individually re-validated), and stamps the advisory `APPROVED`/`REJECTED` with a reviewer ID,
timestamp, and optional notes. It's a real (if Layer-2-scope) implementation, not fabricated — just not this
pass's concern.

---

## 3. The core insight: two separate gaps that look like one

The user's framing — "the frontend isn't simulating anything, it's all dummy dead code" — is close but not
exactly right, and the distinction matters for how you fix it:

- **Gap A — disconnection:** real, working frontend components (Section 2.11) are never mounted by `App.tsx`.
- **Gap B — fabrication:** even if you fixed Gap A today by wiring everything up, what the user would see is
  still fake, because the backend's `TimelineSlice` data (Section 2.8) is seeded-random, not derived from the
  real particle engine (Section 2.3), which itself is being fed a time-invariant wind field (Section 2.4).

**Fixing only Gap A produces a working-looking demo that is still a lie** — exactly the trap that likely
produced this repo's current state (a README confidently citing backtest numbers that are a test fixture).
**Fix Gap B first or in lockstep with Gap A**, and verify with real printed numbers/logs at each phase, not by
eyeballing whether the map looks like it's animating.

---

## 4. Non-negotiable rules, restated as acceptance criteria

1. Every function that currently has a silent fallback path (falls back to a hardcoded value or bundled sample
   file without the caller being told) must instead raise/throw with a specific message, and the HTTP layer
   must surface a structured error (status code + machine-readable reason), not a 200 with quietly-substituted
   data. Log the raw exception server-side either way.
2. No function may claim a quantity is "live," "real-time," "validated," or "historical" in its output or in
   the README unless you can point to the exact code path that makes it true. If you can't make it true this
   pass, the status field must say so honestly (e.g. `"evaluation_status": "NOT_YET_VALIDATED"` rather than
   printing fabricated numbers).
3. Every new/changed code path must be exercised by actually running it (Section 6's verification steps), with
   real output pasted into your fix log — not just "should work now."

---

## 5. Fix plan — phases, in order

Do these roughly in order; later phases depend on earlier ones. Each phase lists: objective, files, approach,
and a concrete verification step you must actually run.

### Phase 0 — Sanity pass (no code changes)

Confirm Section 2's claims still hold (things may have drifted since this brief was written) by opening each
cited file and line once. If something has already changed, note it in your fix log and adjust the plan — don't
silently proceed on a stale assumption either.

### Phase 1 — Kill remaining silent fallbacks

Audit every `except` block and every `load_fallback_*` / `*_demo` / default-value call site across
`ml-model/src/` and `backend/src/`. For each one, decide: is this an explicit, caller-requested replay/demo mode
(keep, but make sure it's never reached implicitly), or is it a silent substitution on failure (fix per Section
4 rule 1). `nasa_firms.py` / `open_meteo.py`'s live-fetch functions (Section 2.1) are your reference
implementation of "fail loud correctly." Pay particular attention to `get_sample_*` call sites in `service.py`
(lines 69–76) being invoked by `mode != "live"` branches — that's fine (explicit replay mode) — versus anything
that catches an exception from a live call and quietly returns fallback data instead of re-raising.

**Verify:** force a failure (unset `NASA_FIRMS_MAP_KEY`, point `OPEN_METEO_BASE_URL` at a bad host) and confirm
`POST /v1/runs {"mode":"live"}` returns a non-200 with a specific error message, with the real exception logged
server-side — not a 200 full of sample data.

### Phase 2 — Time-varying wind field

In `weather_field.py`: store the full `observations` list (not just `observations[0]`). In `get_wind_vector()`
and `get_blh_and_diffusivity()`, use `time_elapsed_seconds` (plus the run's `now` timestamp) to find the two
observations bracketing that moment and linearly interpolate `u`, `v`, `boundary_layer_height_m` between them.
If `time_elapsed_seconds` falls outside the fetched range, fail loud (Section 4 rule 1) rather than silently
clamping to the nearest edge forever — a clear error here ("forecast horizon exceeds available weather data")
is much more useful than quietly simulating on stale wind. Remove or clearly justify-and-cite the uncalibrated
`spatial_shear_*` constants (lines 62–63) — if you keep a spatial variation term, derive it from something real
(e.g. actual spatial gradient between two nearby Open-Meteo grid points) rather than an unexplained constant.

**Verify:** log the resolved `(u, v)` at `elapsed_seconds = 0`, `10800` (+3h), `21600` (+6h), `32400` (+9h) for a
single run and confirm they differ (today they're identical by construction). Print this as part of your fix
log.

### Phase 3 — Multi-horizon chaining (+3h / +6h / +9h)

In `ensemble.py`'s `run_ensemble()` (and/or `lagrangian_engine.py`), change the time-stepping loop so it
**returns a snapshot of `ParticleState` at each requested horizon boundary**, not only the final one. Concretely:
accept a list of horizon hours (`[3, 6, 9]`) instead of a single `horizon_hours` int; step through in `dt_seconds`
increments as today, but every time `elapsed_seconds` crosses a requested horizon boundary, deep-copy the
current `ParticleState` into a `{horizon_hours: ParticleState}` dict, and **keep stepping the same particle
array forward** (don't reinitialize) for the next horizon. This directly implements the user's own requirement:
*"the 6th hr prediction, based on the points given by the 3rd hr prediction... so we can use the 6th hr
prediction to map for the 9th hr prediction."* Update `config.py`'s `SimulationConfig` to carry a list of
horizons instead of (or in addition to) a single `horizon_hours`. Update `PredictiveOutput`/`EnsembleOutput`
types (`ml-model/src/types.py`) to carry per-horizon particle/ensemble summaries rather than one flat set.

**Verify:** run once and confirm (by printing, not assuming) that the +6h particle positions are the +3h
particle positions advected forward (not independently regenerated), and that total mass only decreases
monotonically across the chain (consistent with decay + pruning, no resets).

### Phase 4 — Real timeline slices

Rewrite `_generate_timeline_slices()` in `pipeline.py` to take the per-horizon `ParticleState` snapshots from
Phase 3 as an argument (it currently takes none of the simulation's real output — Section 2.8). For each
horizon: call the already-existing `diffusion_field.extract_contour_geojson()` (Section 2.5) to get a real
contour polygon instead of the hand-offset rectangles; convert a subsample of real particle `(x, y, mass)` back
to `(lat, lon, normalized_mass)` via `projection.to_wgs84()` for `scatter_points`, instead of `np.random.normal`
with a seeded RNG; derive `plume_center_lat/lon` from the real particle centroid (mass-weighted mean), not a
straight-line extrapolation. Delete the `np.random.seed(42 + h)` line and everything downstream of it in this
function.

**Verify:** run the same fire/weather input twice and confirm the scatter points differ between runs (since the
engine's turbulence term is unseeded) while remaining physically plausible (centered near the real plume,
spreading outward with time) — today they are *identical* between runs (because of the seed) and *don't* grow
from real spread. Also confirm visually once Phase 5 is done.

### Phase 5 — Reconnect the frontend

In `frontend/src/App.tsx` (or a new view/tab if you'd rather not disturb the current live-FIRMS-only view),
import and mount `PlumeMap`, `TimelineSliderControl`, `SchoolRiskTable` using `useForecast` to call
`client.createRun({mode: "live"})` (or `"replay"` for an offline/no-API-key demo path) and feed the resulting
`FrontendPayload.prediction` into `PlumeMap`. Use `useTimelineSlider` to drive which `TimelineSlice` is "current"
and pass it to `PlumeMap`'s `currentSlice` prop. None of these components need their internals changed — this is
wiring, confirmed in Section 2.11. Do not delete the existing live-FIRMS-only view; add the simulation view
alongside or behind a tab, since the "no fallback, live-only" honesty property of the current `LiveMap` view is
worth keeping as-is.

**Verify:** open the running app, trigger a run, move the horizon slider, and confirm the heatmap/scatter/
corridor visibly change shape between +3h/+6h/+9h and that the numbers in the telemetry overlay match what the
API actually returned (cross-check one value by hand against the JSON response).

### Phase 6 — Fix school arrival time

In `school_scorer.py`, replace the flat `18.0 km/h` straight-line estimate (lines 63–65) with a derivation from
the real per-horizon data now available from Phase 3/4: for each school, sample concentration at that school's
coordinates at each available horizon snapshot (reusing `sample_point_concentration`) and record the first
horizon at which it crosses the impact threshold as the arrival time, interpolating between the two bracketing
horizons if you want finer resolution than 3h buckets. If a school's concentration never crosses threshold
within the simulated horizons, `predicted_arrival_time` must be `null`, not a distance/speed guess — that's
consistent with how `impact_probability` already fails safe.

**Verify:** confirm `impact_probability > 0` and `predicted_arrival_time is not None` are now consistent for the
same school in the same run (today they can disagree because they come from unrelated calculations).

### Phase 7 — Honest evaluation

Stop `ml-model/src/service.py` line 39/164 from importing and auto-calling `run_evaluation_demo()` inside
`create_run()`. `POST /v1/runs` should return `evaluation: null` (or omit the field) with a clear
`evaluation_status` unless real forecast/observation pairs are supplied. Do the mirrored fix in
`backend/src/controllers/evaluation.controller.ts` (`getLatestEvaluation`, `evaluateCustom`) — `GET /v1/evaluation`
should return a clear `"status": "NO_VALIDATED_BACKTEST_AVAILABLE"` (or equivalent) rather than silently calling
`EvaluationService.runDemo()`. Keep `run_evaluation_demo()` / `runDemo()` themselves as what they actually are —
rename them if useful (e.g. `run_evaluation_fixture_for_tests()`) and only call them from actual test files, not
from any production/service code path. Then **fix the README**: either remove the backtest results table
(Section 2.9) or replace it with an honest statement that no historical backtest has been run yet, since as far
as this repo's code shows, none has.

**Verify:** `GET /v1/evaluation` on a fresh run with no real historical data supplied returns an honest "not yet
validated" response, not numbers. Grep the whole repo for `run_evaluation_demo` and `runDemo` afterward and
confirm every remaining call site is inside a test file.

### Phase 8 — Lower-priority correctness improvements (do only if Phases 1–7 are solid and verified)

- `fire_source.py` clustering (Section 2.6): make it a real connected-component/single-linkage merge instead of
  a seed-point-only star grouping, so cluster membership doesn't depend on input array order.
- `ensemble.py` line 121: compute a real polygon intersection (e.g. via `shapely`) instead of `union_poly`.
- BLH → concentration box-model relationship (Section 2.3/2.5): make `sample_point_concentration` (or a
  wrapper) divide effective concentration by `boundary_layer_height_m` so a lower BLH genuinely raises surface
  concentration, matching the physical relationship your own docstrings already describe, instead of only
  rescaling the horizontal diffusion coefficient.
- Convert `source_strength` toward a physically-grounded `kg/s` PM2.5 emission estimate using an FRP-based
  emission factor from the literature, if you want this to be more than an honestly-labeled relative proxy.

---

## 6. Explicitly out of scope this pass

- Layer 2: `layer2_generative/` (Bedrock agent, Cedar guardrail, claim validator, GRAP policy, bilingual
  advisory generation). Not touched, not re-audited in this pass.
- AWS deployment (EventBridge/Lambda/S3/CloudFront) — this repo currently runs as local Node + Python processes;
  that's fine for this pass's goal.
- Visual polish / design system work on the frontend — get real data flowing through the existing components
  first (per the user's own instruction: "forget about how pretty it looks for now").
- Adding a real 3D vertical transport model — Section 2.3 explains why that would currently just be a more
  elaborate fabrication given the available data sources; the BLH box-model fix in Phase 8 is the right-sized
  improvement for now.

---

## 7. What your fix log must contain when you're done

Produce a `FIXLOG.md` (or equivalent) in the repo root with, for each phase you completed:
1. The objective (one line).
2. Exact files and line ranges changed (before → after, or a diff reference).
3. The actual command you ran to verify it, and the actual output (not a paraphrase) — including, where
   relevant, real printed numbers (wind vectors at different horizons, particle counts/mass at each horizon
   snapshot, a school's probability vs. arrival-time consistency check).
4. Anything from Section 6 you could not complete, and why — an honest "not done, here's why" is strictly
   better than a claimed fix you didn't verify. This document's own existence is proof that confident-but-wrong
   status claims are this project's recurring failure mode — do not add another one.
