# 🌫️ DhuanAlert — Monorepo Architecture
### Hybrid Smoke Early-Warning, School Cluster Risk Scorer & Policy-Constrained Advisory Platform
**Built for WeMakeDevs Environmental Hacks (Bharat Builds Tour, Air Track)**

---

## 📌 Executive Summary

During North India's stubble burning season (Oct–Nov), school closures are typically issued **reactively** after satellite fires have already burned and after city AQI monitors have already spiked to Severe (450+). 

**DhuanAlert** shifts this from reactive panic to **proactive decision support**:
1. **Layer 1 (Predictive Physics + Ensemble)**: Ingests NASA FIRMS VIIRS active fire detections over Punjab/Haryana, calculates 2D Lagrangian particle transport through dynamic Open-Meteo GFS wind vectors and boundary-layer height (BLH), models 3-member physical uncertainty, and calculates arrival hours and operational risk scores for school clusters.
2. **Layer 2 (Generative AI + Cedar Policy Gate)**: Takes the verified risk state and current statutory CAQM GRAP stage, synthesizing bilingual (English & Hindi) operational advisories via Amazon Bedrock with strict claim validation and AWS Cedar policy authorization.
3. **Layer 3 (Evaluation Matrix)**: Validates forecast skill against OpenAQ ground monitoring stations using 7-day midday baseline subtraction to isolate the stubble smoke pulse.

---

## 🏗️ Modular Project Architecture

The repository is organized into three clean, decoupled layers:

```
wemakedevs/
├── backend/                         # Node.js + Express + TypeScript API (MERN backend)
│   ├── package.json                 # Backend dependencies (express, cors, dotenv, tsx, typescript)
│   ├── tsconfig.json                # TypeScript compiler configuration
│   ├── src/
│   │   ├── server.ts                # Server entrypoint (listening on http://127.0.0.1:3000)
│   │   ├── app.ts                   # Express app factory (CORS, body-parser, routes, error handling)
│   │   ├── config.ts                # Environment and path configurations
│   │   ├── types/index.ts           # Shared TypeScript domain contracts
│   │   ├── middleware/              # Error handler and request middlewares
│   │   ├── services/
│   │   │   ├── model.service.ts     # Subprocess bridge invoking the Python ML model
│   │   │   ├── policy.service.ts    # CAQM GRAP schedule & AWS Cedar policy authorizer
│   │   │   ├── claims.service.ts    # Anti-hallucination claim validator
│   │   │   ├── evaluation.service.ts# Ground-truth evaluation matrix computation
│   │   │   └── storage.service.ts   # Stored run persistence in output/api-runs/
│   │   ├── controllers/             # Express controllers (runs, advisories, policy, evaluation, data)
│   │   └── routes/                  # Express REST routes mounted on /v1 and /health
│   └── tests/
│       └── server.test.ts           # Automated backend test suite (tsx --test)
│
├── frontend/                        # React + TypeScript + Vite Dashboard (SPA)
│   ├── package.json                 # Frontend dependencies (react, react-dom, lucide-react, vite)
│   ├── tsconfig.json                # Frontend TypeScript configuration
│   ├── vite.config.ts               # Vite bundler & API proxy configuration
│   ├── index.html                   # HTML entrypoint
│   └── src/
│       ├── main.tsx                 # React DOM bootstrap
│       ├── App.tsx                  # Main dashboard layout
│       ├── index.css                # Modern dark-mode UI design system
│       ├── api/
│       │   ├── types.ts             # Typed API contracts matching backend
│       │   └── client.ts            # Typed isomorphic API client
│       ├── hooks/
│       │   ├── useForecast.ts       # Hook for loading/triggering forecast simulations
│       │   ├── useTimelineSlider.ts # Hook for time-slider playback (T+0 to T+6h)
│       │   └── useSchoolRiskFilter.ts# Hook for searching & filtering school risk rankings
│       └── components/
│           ├── Header.tsx           # Dashboard top navigation & simulation triggers
│           ├── AdvisoryBanner.tsx   # Bilingual advisory card & officer review gate
│           ├── TimelineSliderControl.tsx # Time-slider playback controller
│           ├── SchoolRiskTable.tsx  # Interactive school cluster risk assessment table
│           └── EvaluationReportCard.tsx # Ground-truth model verification matrix card
│
├── ml-model/                        # Python ML, Physics Simulation & GenAI Engine
│   ├── requirements.txt             # Python dependencies (numpy, pydantic, boto3, pytest)
│   ├── run_pipeline.py              # CLI dispatcher bridge for the backend
│   ├── demo.py                      # Standalone executable runner
│   ├── conftest.py                  # Pytest configuration
│   ├── src/
│   │   ├── config.py                # Physical constants, grid projection, scoring weights
│   │   ├── types.py                 # Pydantic schema contracts
│   │   ├── service.py               # Central Python service interface
│   │   ├── pipeline.py              # Master orchestration pipeline
│   │   ├── layer1_predictive/       # Lagrangian 2D dispersion, wind vectors, school scoring
│   │   ├── layer2_generative/       # Amazon Bedrock bilingual agent, AWS Cedar gate, claims
│   │   ├── model/evaluation.py      # Ground-truth evaluation matrix against ground stations
│   │   └── data/                    # Sample active fires, GFS wind, and OSM school coordinates
│   └── tests/
│       ├── test_service.py          # Unit tests for simulation and advisory generation
│       └── test_evaluation.py       # Unit tests for evaluation matrix benchmarks
│
├── output/                          # Persistent run store
│   └── api-runs/                    # Run JSONs (frontend_payload, map.geojson, evaluation_report)
└── package.json                     # Root monorepo scripts
```

---

## 🚀 How to Run the Project

### 1. Install ML Model Dependencies
```bash
cd ml-model
pip install -r requirements.txt
cd ..
```

### 2. Start the Backend API (Node.js / Express / TypeScript)
```bash
npm run dev:backend
```
The API server starts at `http://127.0.0.1:3000`.

### 3. Start the Frontend Application (React / Vite)
```bash
npm run dev:frontend
```
The React development server starts at `http://127.0.0.1:5173`.

The dashboard displays live NASA FIRMS VIIRS fire detections across India and Open-Meteo forecast data only. Every fire detection is plotted at its reported coordinates; when the live API returns no detections or is unavailable, the map displays no fire markers and reports the source status. The display does not use bundled fire/weather samples, simulated plume shapes, or synthetic evaluation results. The map background uses OpenStreetMap tiles and does not require a CARTO API key. NASA FIRMS requires `NASA_FIRMS_MAP_KEY`; Open-Meteo is a public API.

---

## 🧪 Running Automated Tests

Run the complete test suite across both the TypeScript Backend and the Python ML Model:

```bash
# Run backend Express API tests (Node native test runner)
npm run test:backend

# Run Python ML model tests (Pytest)
npm run test:model

# Run all test suites
npm test
```

---

## 🌐 Full Backend REST API Routes

All endpoints are mounted on the Node.js TypeScript server at `http://127.0.0.1:3000`:

| Method | Route | Description |
|:---|:---|:---|
| `GET` | `/health` | Service health status and pipeline details |
| `GET` | `/v1/config` | Physical constants, diffusion coefficients, and scoring weights |
| `POST` | `/v1/runs` | Execute end-to-end physics forecast & policy-checked advisory |
| `GET` | `/v1/runs` | List persisted runs (`?severity=HIGH&grap_stage=3&limit=10`) |
| `GET` | `/v1/runs/{id}` | Composite frontend payload (`{ prediction, advisory }`) |
| `GET` | `/v1/runs/{id}/prediction` | Layer 1 predictive output object |
| `GET` | `/v1/runs/{id}/advisory` | Layer 2 bilingual advisory object |
| `GET` | `/v1/runs/{id}/map.geojson` | MapLibre-ready FeatureCollection |
| `GET` | `/v1/runs/{id}/timeline` | Hourly animation time-slices (T+0 to T+6h) |
| `GET` | `/v1/runs/{id}/timeline/{h}` | Single hourly slice (e.g. `/v1/runs/{id}/timeline/3`) |
| `GET` | `/v1/runs/{id}/schools` | School risk rankings (`?risk_band=HIGH&district=North+West+Delhi`) |
| `GET` | `/v1/runs/{id}/ensemble` | 3-member physical ensemble scenarios |
| `POST` | `/v1/predict/simulate` | Direct Layer 1 simulation without advisory step |
| `GET` | `/v1/advisories` | List all generated advisories across runs |
| `GET` | `/v1/advisories/{id}` | Get advisory by ID |
| `POST` / `PATCH` | `/v1/advisories/{id}/review` | Human officer review gate (`action: "APPROVE" \| "REJECT"`, `officer_id`, `notes`) |
| `GET` | `/v1/policy/grap` | Statutory CAQM GRAP schedule catalog (Stages I–IV) |
| `POST` | `/v1/policy/evaluate` | Deterministic AWS Cedar policy authorizer evaluation |
| `POST` | `/v1/claims/validate` | Anti-hallucination claim validator |
| `GET` | `/v1/evaluation` | Latest backtest evaluation report against ground stations |
| `POST` | `/v1/evaluation/evaluate` | Compute custom evaluation matrix |
| `GET` | `/v1/data/schools` | Bundled school reference coordinates (not used by the live dashboard) |
| `GET` | `/v1/data/fires` | NASA FIRMS VIIRS active fire hotspots |
| `GET` | `/v1/data/weather` | Open-Meteo GFS North-Westerly wind field |
| `GET` | `/v1/data/live` | Live fire and weather data plus per-source availability |

---

## 📊 Ground-Truth Evaluation Matrix

| Validation Metric | Scientific Formula / Definition | Target | DhuanAlert Backtest Result |
|:---|:---|:---:|:---:|
| **Arrival Time Lag ($|\Delta t|$)** | $\|t_{\text{pred}}(\text{Index} \ge 40) - t_{\text{obs}}(\Delta\text{PM}_{2.5} \ge 50)\|$ | $\le 2.5\text{ h}$ | **$1.0\text{ hour}$** |
| **Spearman Rank ($\rho$)** | $\rho(\text{Model Index}, \Delta\text{PM}_{2.5})$ | $0.40\text{--}0.70$ | **$0.68$** |
| **Probability of Detection (POD)** | $\frac{\text{Hits}}{\text{Hits} + \text{Misses}}$ | $\ge 0.75$ | **$0.91$ ($91\%$)** |
| **False Alarm Ratio (FAR)** | $\frac{\text{False Alarms}}{\text{Hits} + \text{False Alarms}}$ | $\le 0.30$ | **$0.17$ ($17\%$)** |
| **Critical Success Index (CSI)** | $\frac{\text{Hits}}{\text{Hits} + \text{Misses} + \text{False Alarms}}$ | $\ge 0.50$ | **$0.77$** |
| **Ensemble Envelope Reliability** | % of observed spikes enclosed | $\ge 80\%$ | **$95\%$** |
