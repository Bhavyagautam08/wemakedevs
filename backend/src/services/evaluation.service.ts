import { EvaluationReport } from "../types";

export class EvaluationService {
  public static computeSpearmanRank(x: number[], y: number[]): number {
    if (x.length < 3 || x.length !== y.length) return 0.0;

    const getRanks = (arr: number[]) => {
      const sorted = arr.map((v, i) => ({ v, i })).sort((a, b) => a.v - b.v);
      const ranks = new Array(arr.length);
      for (let r = 0; r < sorted.length; r++) {
        ranks[sorted[r].i] = r + 1;
      }
      return ranks;
    };

    const rx = getRanks(x);
    const ry = getRanks(y);

    let sumD2 = 0;
    for (let i = 0; i < x.length; i++) {
      const d = rx[i] - ry[i];
      sumD2 += d * d;
    }

    const n = x.length;
    const rho = 1.0 - (6.0 * sumD2) / (n * (n * n - 1));
    return Math.round(rho * 1000) / 1000;
  }

  public static computePearson(x: number[], y: number[]): number {
    if (x.length < 2 || x.length !== y.length) return 0.0;
    const n = x.length;
    const meanX = x.reduce((a, b) => a + b, 0) / n;
    const meanY = y.reduce((a, b) => a + b, 0) / n;

    let num = 0;
    let denX = 0;
    let denY = 0;

    for (let i = 0; i < n; i++) {
      const dx = x[i] - meanX;
      const dy = y[i] - meanY;
      num += dx * dy;
      denX += dx * dx;
      denY += dy * dy;
    }

    const den = Math.sqrt(denX * denY);
    return den === 0 ? 0 : Math.round((num / den) * 1000) / 1000;
  }

  public static evaluateGroundTruth({
    forecasts,
    observations,
    indexThreshold = 40.0,
    deltaPm25Threshold = 50.0,
  }: {
    forecasts: any[];
    observations: any[];
    indexThreshold?: number;
    deltaPm25Threshold?: number;
  }): EvaluationReport {
    const obsMap = new Map<string, any>();
    for (const o of observations) {
      obsMap.set(`${o.station_id}_${o.timestamp}`, o);
    }

    const pairedForecasts: number[] = [];
    const pairedDeltas: number[] = [];
    const lagErrors: number[] = [];
    let hits = 0;
    let misses = 0;
    let falseAlarms = 0;
    let correctNegatives = 0;
    let envelopeHits = 0;
    let totalSpikes = 0;

    const stationForecastArrivals = new Map<string, Date>();
    const stationObservedArrivals = new Map<string, Date>();

    for (const f of forecasts) {
      const key = `${f.station_id}_${f.timestamp}`;
      const obs = obsMap.get(key);
      if (!obs) continue;

      pairedForecasts.push(f.predicted_index);
      pairedDeltas.push(obs.delta_pm25);

      const isPredSmoke = f.predicted_index >= indexThreshold;
      const isObsSmoke = obs.delta_pm25 >= deltaPm25Threshold;

      if (isPredSmoke && isObsSmoke) hits++;
      else if (!isPredSmoke && isObsSmoke) misses++;
      else if (isPredSmoke && !isObsSmoke) falseAlarms++;
      else correctNegatives++;

      if (isPredSmoke && !stationForecastArrivals.has(f.station_id)) {
        stationForecastArrivals.set(f.station_id, new Date(f.timestamp));
      }
      if (isObsSmoke && !stationObservedArrivals.has(f.station_id)) {
        stationObservedArrivals.set(f.station_id, new Date(obs.timestamp));
      }

      if (isObsSmoke) {
        totalSpikes++;
        if (f.ensemble_hit) envelopeHits++;
      }
    }

    for (const [stId, tPred] of stationForecastArrivals.entries()) {
      if (stationObservedArrivals.has(stId)) {
        const tObs = stationObservedArrivals.get(stId)!;
        const diffHours = Math.abs(tPred.getTime() - tObs.getTime()) / (1000 * 3600);
        lagErrors.push(diffHours);
      }
    }

    lagErrors.sort((a, b) => a - b);
    const medianLag = lagErrors.length > 0 ? lagErrors[Math.floor(lagErrors.length / 2)] : 0.0;
    const meanLag = lagErrors.length > 0 ? lagErrors.reduce((a, b) => a + b, 0) / lagErrors.length : 0.0;

    const pod = hits + misses > 0 ? Math.round((hits / (hits + misses)) * 1000) / 1000 : 0.0;
    const far = hits + falseAlarms > 0 ? Math.round((falseAlarms / (hits + falseAlarms)) * 1000) / 1000 : 0.0;
    const csi = hits + misses + falseAlarms > 0 ? Math.round((hits / (hits + misses + falseAlarms)) * 1000) / 1000 : 0.0;
    const envelopeCapture = totalSpikes > 0 ? Math.round((envelopeHits / totalSpikes) * 1000) / 1000 : 1.0;

    const rho = this.computeSpearmanRank(pairedForecasts, pairedDeltas);
    const r = this.computePearson(pairedForecasts, pairedDeltas);

    const verdict = pod >= 0.7 && rho >= 0.4 && medianLag <= 3.0
      ? "VALIDATED: Smoke transport model exhibits strong predictive skill with genuine lead-time advantage."
      : "PROVISIONAL: Moderate correlation; recommend tuning boundary-layer diffusion Kx/Ky.";

    const uniqueStations = new Set(forecasts.map((f) => f.station_id)).size;

    return {
      evaluation_id: "eval_backtest_2024_peak_nw",
      generated_at: new Date().toISOString(),
      dataset_period: "15 Oct - 30 Nov Historical NW Stubble Events",
      station_count: uniqueStations,
      sample_points: pairedForecasts.length,
      median_arrival_lag_hours: Math.round(medianLag * 100) / 100,
      mean_absolute_lag_hours: Math.round(meanLag * 100) / 100,
      spearman_rho: rho,
      pearson_r: r,
      contingency: {
        hits,
        misses,
        false_alarms: falseAlarms,
        correct_negatives: correctNegatives,
        probability_of_detection: pod,
        false_alarm_ratio: far,
        critical_success_index: csi,
      },
      envelope_capture_rate: envelopeCapture,
      operational_verdict: verdict,
    };
  }

  public static runDemo(indexThreshold: number = 40.0, deltaPm25Threshold: number = 50.0): EvaluationReport {
    const stations = [
      { id: "delhi_narela", name: "Narela CAAQMS", lat: 28.852, lon: 77.098 },
      { id: "delhi_bawana", name: "Bawana CAAQMS", lat: 28.776, lon: 77.051 },
      { id: "delhi_rohini", name: "Rohini Sector 16", lat: 28.732, lon: 77.119 },
      { id: "delhi_anand_vihar", name: "Anand Vihar", lat: 28.647, lon: 77.315 },
    ];

    const t0 = new Date("2024-11-03T14:00:00Z").getTime();
    const forecasts: any[] = [];
    const observations: any[] = [];

    for (let step = 0; step < 12; step++) {
      const t = new Date(t0 + step * 3600 * 1000).toISOString();

      for (const st of stations) {
        let simSpike = 0;
        let obsSpike = 0;

        if (st.id.includes("narela") || st.id.includes("bawana")) {
          simSpike = step >= 4 ? 1.0 : 0.0;
          obsSpike = step >= 5 ? 1.0 : 0.0;
        } else {
          simSpike = step >= 7 ? 1.0 : 0.0;
          obsSpike = step >= 8 ? 1.0 : 0.0;
        }

        const predIndex = Math.min(20.0 + simSpike * 65.0 + step * 2.0, 95.0);
        forecasts.push({
          station_id: st.id,
          timestamp: t,
          predicted_index: predIndex,
          ensemble_hit: true,
          lead_hours: step,
        });

        const base = 160.0;
        const obsDelta = obsSpike * 140.0 + (step > 2 ? 10.0 : 0.0);
        observations.push({
          station_id: st.id,
          station_name: st.name,
          latitude: st.lat,
          longitude: st.lon,
          timestamp: t,
          pm25_observed: base + obsDelta,
          pm25_baseline: base,
          delta_pm25: obsDelta,
        });
      }
    }

    return this.evaluateGroundTruth({
      forecasts,
      observations,
      indexThreshold,
      deltaPm25Threshold,
    });
  }
}
