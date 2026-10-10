// SYNTHETIC test fixture: hand-made step-function station data used only to exercise
// the metric math in tests. It is NOT observational data and must never back an API response.
export function buildSyntheticEvaluationFixture() {
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

  return { forecasts, observations };
}
