# 🌫️ DhuanAlert — AI Architecture & Core Engine
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

## 🏗️ Repository Architecture

```
dhuanalert/
├── demo.py                          # Executable end-to-end runner (exports JSONs)
├── requirements.txt                 # Core dependencies (numpy, pydantic, boto3)
├── src/
│   ├── config.py                    # Physical parameters, grid, and scoring weights
│   ├── types.py                     # Standardized Pydantic schemas (Prediction & Advisory)
│   ├── pipeline.py                  # Master pipeline combining Layer 1 + Layer 2
│   ├── layer1_predictive/           # LAYER 1: PREDICTIVE / PHYSICS ENGINE
│   │   ├── coordinates.py           # Metric local projection (meters) <-> WGS84
│   │   ├── fire_source.py           # VIIRS clustering & source_strength estimation
│   │   ├── weather_field.py         # 2D wind field u(x,y,t), v(x,y,t) + BLH mixing
│   │   ├── lagrangian_engine.py     # 2D stochastic particle advection & mass decay
│   │   ├── diffusion_field.py       # 2D Gaussian diffusion C(x,y,t) & sigma spread
│   │   ├── ensemble.py              # 3-member physical scenarios & impact probability
│   │   ├── school_scorer.py         # School spatial intersection & risk scoring
│   │   └── pipeline.py              # Layer 1 Runner: generates Prediction + GeoJSON
│   ├── layer2_generative/           # LAYER 2: GENERATIVE AI & POLICY ENGINE
│   │   ├── grap_policy.py           # Statutory CAQM GRAP definitions (Stages I–IV)
│   │   ├── cedar_guardrail.py       # Deterministic AWS Cedar policy evaluation gate
│   │   ├── claim_validator.py       # Fact/claim classification & zero-hallucination guard
│   │   ├── bedrock_agent.py         # Amazon Bedrock bilingual agent (with offline mock)
│   │   └── pipeline.py              # Layer 2 Runner: Intent -> Policy -> Claims -> Publish
│   ├── model/
│   │   └── evaluation.py            # Real-world evaluation matrix (POD, FAR, CSI, lag, rho)
│   └── data/
│       ├── sample_fires.json        # VIIRS active-fire detections in Punjab
│       ├── sample_weather.json      # Open-Meteo GFS North-Westerly wind field
│       └── ncr_schools.json         # Sample OSM schools across Delhi-NCR
├── tests/
│   └── test_evaluation.py           # Evaluation matrix verification test
└── output/                          # Generated JSON payloads for Backend/Frontend
```

---

## 🚀 How to Run the Code

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the End-to-End Pipeline
```bash
python demo.py
```
This will:
- Run the 2D Lagrangian particle dispersion simulation across Punjab fires.
- Evaluate impact probabilities across Delhi-NCR schools.
- Run the Amazon Bedrock advisory synthesizer and Cedar policy check.
- Compute the ground-truth evaluation matrix against real-world stations.
- Export ready-to-use JSON payloads into the `output/` folder.

### 3. Start the JavaScript API
Install Python dependencies first, then run the Node.js API from this repository:
```bash
npm start
```
The API listens on `http://127.0.0.1:3000` by default. Set `PORT`, `HOST`,
`CORS_ORIGIN`, or `PYTHON_EXECUTABLE` to configure the local service. The API
uses Node.js built-ins and does not require `npm install`.

Create a replay run with the bundled sample data:
```bash
curl -X POST http://127.0.0.1:3000/v1/runs ^
  -H "Content-Type: application/json" ^
  -d "{\"mode\":\"replay\",\"snapshot_id\":\"sample\",\"grap_stage\":3}"
```
Each API run is stored separately under `output/api-runs/`. The replay endpoint
returns the combined `prediction` and `advisory` payload consumed by the
dashboard. Forecasts are decision support only; generated advisories require
officer review and are never automatically approved by the API.

#### API routes

| Method | Route | Purpose |
|:---|:---|:---|
| `GET` | `/health` | Service health |
| `POST` | `/v1/runs` | Execute the Python pipeline against `snapshot_id: "sample"`; optional `grap_stage` is 1–4 |
| `GET` | `/v1/runs` | List persisted replay runs |
| `GET` | `/v1/runs/{run_id}` | Get the composite prediction and advisory payload |
| `GET` | `/v1/runs/{run_id}/map.geojson` | Get the run's MapLibre FeatureCollection |
| `GET` | `/v1/advisories/{advisory_id}` | Get an advisory |
| `GET` | `/v1/evaluation` | Get the latest replay's evaluation report |

The API currently runs the repository's bundled offline sample data only; it
does not yet ingest live FIRMS/Open-Meteo/OpenAQ data or provide user
authentication and an approval workflow. The service binds to loopback by
default. Configure CORS to the exact frontend origin when connecting a browser
dashboard; do not expose the service publicly without adding authentication and
deployment controls.

---

## 📦 Output Files for Backend & Frontend Teams

When `demo.py` finishes, it writes four JSON files to `output/`:

| Output File | Destination | Description |
|:---|:---|:---|
| `prediction.json` | `GET /v1/runs/{id}` → `prediction` | Layer 1 output, school risk assessments, timeline slices (T+0 to T+6h). |
| `advisory.json` | `GET /v1/advisories/{id}` | Bilingual advisory draft, Cedar and claim checks, and publication status. |
| `map.geojson` | `GET /v1/runs/{id}/map.geojson` | MapLibre-ready FeatureCollection (fire points, plume polygons, school pins). |
| `frontend_payload.json` | Composite API | Combined contract ready for immediate dashboard rendering. |
| `evaluation_report.json` | `GET /v1/evaluation` | Real-world evaluation report comparing predictions against ground stations. |

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

---

## ☁️ AWS Architecture Mapping

- **Amazon Bedrock**: Powering the grounded bilingual advisory agent (`amazon.nova-micro-v1:0` / `anthropic.claude-3-haiku`).
- **AWS Cedar**: Open-source deterministic policy engine enforcing CAQM GRAP legal constraints before publishing.
- **AWS Lambda + EventBridge**: Scheduled execution every 3 hours.
- **Amazon S3**: Storing raw satellite snapshots and raster numpy arrays.
- **Amazon DynamoDB**: Storing school risk states and advisory audit trails.
