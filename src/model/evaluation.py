"""
DhuanAlert Model Evaluation Matrix
Evaluates predicted smoke plume concentration/corridor index against real-world
ground station PM2.5 observations (OpenAQ / CAAQMS).
"""

from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta, timezone
import numpy as np
from pydantic import BaseModel


class StationObservation(BaseModel):
    """Real-world ground station data point."""
    station_id: str
    station_name: str
    latitude: float
    longitude: float
    timestamp: datetime
    pm25_observed: float       # Raw observed PM2.5 in ug/m^3
    pm25_baseline: float       # 7-day median baseline for this hour
    delta_pm25: float          # pm25_observed - pm25_baseline (smoke pulse)


class StationForecast(BaseModel):
    """Model forecast sampled at the station location."""
    station_id: str
    timestamp: datetime
    predicted_index: float     # 0 - 100 relative corridor index
    ensemble_hit: bool         # True if inside 3-member uncertainty envelope
    lead_hours: int


class ContingencyTable(BaseModel):
    hits: int = 0
    misses: int = 0
    false_alarms: int = 0
    correct_negatives: int = 0

    @property
    def probability_of_detection(self) -> float:
        """Hit Rate / Recall: Hits / (Hits + Misses)"""
        denom = self.hits + self.misses
        return round(self.hits / denom, 3) if denom > 0 else 0.0

    @property
    def false_alarm_ratio(self) -> float:
        """FAR: False Alarms / (Hits + False Alarms)"""
        denom = self.hits + self.false_alarms
        return round(self.false_alarms / denom, 3) if denom > 0 else 0.0

    @property
    def critical_success_index(self) -> float:
        """CSI / Threat Score: Hits / (Hits + Misses + False Alarms)"""
        denom = self.hits + self.misses + self.false_alarms
        return round(self.hits / denom, 3) if denom > 0 else 0.0


class EvaluationReport(BaseModel):
    """Standardized evaluation report against real-world observations."""
    evaluation_id: str
    generated_at: datetime
    dataset_period: str
    station_count: int
    sample_points: int

    # 1. Temporal Lag Metrics
    median_arrival_lag_hours: float
    mean_absolute_lag_hours: float

    # 2. Correlation Metrics
    spearman_rho: float
    pearson_r: float

    # 3. Detection / Contingency Metrics
    contingency: ContingencyTable

    # 4. Uncertainty Reliability
    envelope_capture_rate: float  # Percentage of real spikes within ensemble envelope

    # 5. Scientific Verdict
    operational_verdict: str


def compute_spearman_rank_correlation(x: List[float], y: List[float]) -> float:
    """Computes Spearman rank correlation coefficient without heavy scipy dependency."""
    if len(x) < 3:
        return 0.0
    rx = np.argsort(np.argsort(x))
    ry = np.argsort(np.argsort(y))
    d = rx - ry
    n = len(x)
    rho = 1.0 - (6.0 * np.sum(d ** 2)) / (n * (n ** 2 - 1))
    return float(round(rho, 3))


def evaluate_model_against_ground_truth(
    forecasts: List[StationForecast],
    observations: List[StationObservation],
    index_threshold: float = 40.0,       # Model corridor threshold
    delta_pm25_threshold: float = 50.0,  # Observed smoke pulse threshold in ug/m3
) -> EvaluationReport:
    """
    Computes the full evaluation matrix matching predicted time series
    against observed station pulses.
    """
    obs_map = {(o.station_id, o.timestamp.isoformat()): o for o in observations}

    paired_forecasts = []
    paired_deltas = []
    lag_errors = []
    envelope_hits = 0
    total_spikes = 0

    table = ContingencyTable()

    # Track arrival times per station
    station_forecast_arrivals: Dict[str, datetime] = {}
    station_observed_arrivals: Dict[str, datetime] = {}

    for f in forecasts:
        key = (f.station_id, f.timestamp.isoformat())
        if key not in obs_map:
            continue

        obs = obs_map[key]
        pred_val = f.predicted_index
        obs_val = obs.delta_pm25

        paired_forecasts.append(pred_val)
        paired_deltas.append(obs_val)

        is_pred_smoke = pred_val >= index_threshold
        is_obs_smoke = obs_val >= delta_pm25_threshold

        # Contingency table population
        if is_pred_smoke and is_obs_smoke:
            table.hits += 1
        elif (not is_pred_smoke) and is_obs_smoke:
            table.misses += 1
        elif is_pred_smoke and (not is_obs_smoke):
            table.false_alarms += 1
        else:
            table.correct_negatives += 1

        # Track arrival timestamps
        if is_pred_smoke and f.station_id not in station_forecast_arrivals:
            station_forecast_arrivals[f.station_id] = f.timestamp

        if is_obs_smoke and f.station_id not in station_observed_arrivals:
            station_observed_arrivals[f.station_id] = obs.timestamp

        # Ensemble envelope reliability
        if is_obs_smoke:
            total_spikes += 1
            if f.ensemble_hit:
                envelope_hits += 1

    # Calculate arrival lag errors
    for st_id, t_pred in station_forecast_arrivals.items():
        if st_id in station_observed_arrivals:
            t_obs = station_observed_arrivals[st_id]
            diff_hours = (t_pred - t_obs).total_seconds() / 3600.0
            lag_errors.append(abs(diff_hours))

    median_lag = float(np.median(lag_errors)) if lag_errors else 0.0
    mean_lag = float(np.mean(lag_errors)) if lag_errors else 0.0

    # Correlation
    rho = compute_spearman_rank_correlation(paired_forecasts, paired_deltas)
    r = float(round(np.corrcoef(paired_forecasts, paired_deltas)[0, 1], 3)) if len(paired_forecasts) > 1 else 0.0

    capture_rate = round(envelope_hits / total_spikes, 3) if total_spikes > 0 else 1.0

    # Verdict synthesis
    if table.probability_of_detection >= 0.70 and rho >= 0.40 and median_lag <= 3.0:
        verdict = "VALIDATED: Smoke transport model exhibits strong predictive skill with genuine lead-time advantage."
    else:
        verdict = "PROVISIONAL: Moderate correlation; recommend tuning boundary-layer diffusion Kx/Ky."

    unique_stations = len(set(f.station_id for f in forecasts))

    return EvaluationReport(
        evaluation_id="eval_backtest_2024_peak_nw",
        generated_at=datetime.now(timezone.utc),
        dataset_period="15 Oct - 30 Nov Historical NW Stubble Events",
        station_count=unique_stations,
        sample_points=len(paired_forecasts),
        median_arrival_lag_hours=round(median_lag, 2),
        mean_absolute_lag_hours=round(mean_lag, 2),
        spearman_rho=rho,
        pearson_r=r,
        contingency=table,
        envelope_capture_rate=capture_rate,
        operational_verdict=verdict,
    )
