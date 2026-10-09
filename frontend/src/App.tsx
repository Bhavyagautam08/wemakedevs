import { useMemo } from "react";
import { DhuanAlertClient } from "./api/client";
import { useLiveData } from "./hooks/useLiveData";
import { Header } from "./components/Header";
import { LiveMap } from "./components/LiveMap";
import { LiveDataSnapshot } from "./api/types";

function getCurrentWeather(data: LiveDataSnapshot): LiveDataSnapshot["weather"][number] | null {
  if (data.weather.length === 0) return null;
  const now = Date.now();
  return data.weather.find((item) => new Date(item.forecast_timestamp).getTime() >= now)
    ?? data.weather[data.weather.length - 1];
}

export function App() {
  const client = useMemo(
    () => new DhuanAlertClient(import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:3000"),
    [],
  );
  const { data, loading, error, refresh } = useLiveData(client);
  const currentWeather = data ? getCurrentWeather(data) : null;

  return (
    <div className="app-layout">
      <Header fetchedAt={data?.fetched_at} onRefresh={refresh} isLoading={loading} />
      <main className="main-content live-dashboard">
        {loading && !data && (
          <div className="loading-state">
            <div className="spinner" />
            <p>Fetching live satellite fire and weather data...</p>
          </div>
        )}

        {error && (
          <div className="error-banner" role="alert">
            <h3>Live data API unavailable</h3>
            <p>{error}</p>
            <button className="btn btn-primary" onClick={refresh} disabled={loading}>
              Retry live data
            </button>
          </div>
        )}

        {data && (
          <>
            <div className="live-source-grid">
              <section className="live-source-card">
                <div className="live-source-heading">
                  <h2>{data.sources.fires.name}</h2>
                  <span className={`source-status ${data.sources.fires.status}`}>
                    {data.sources.fires.status === "ok" ? "Connected" : "Unavailable"}
                  </span>
                </div>
                {data.sources.fires.status === "ok" ? (
                  <p>
                    {data.fires.length === 0
                      ? "No active fire detections returned for this area and time range."
                      : `${data.fires.length} active detections returned by the live API.`}
                  </p>
                ) : (
                  <p className="source-error">{data.sources.fires.error}</p>
                )}
              </section>

              <section className="live-source-card">
                <div className="live-source-heading">
                  <h2>{data.sources.weather.name}</h2>
                  <span className={`source-status ${data.sources.weather.status}`}>
                    {data.sources.weather.status === "ok" ? "Connected" : "Unavailable"}
                  </span>
                </div>
                {data.sources.weather.status === "ok" && currentWeather ? (
                  <>
                    <p className="weather-values">
                      Wind {((currentWeather.wind_speed_mps * 3.6)).toFixed(1)} km/h
                      {" · "}{currentWeather.wind_direction_deg}°
                      {" · "}{currentWeather.temperature_c}°C
                    </p>
                    <p className="weather-timestamp">
                      Forecast for {new Date(currentWeather.forecast_timestamp).toLocaleString()}
                    </p>
                  </>
                ) : (
                  <p className="source-error">
                    {data.sources.weather.error || "No live weather forecast observations returned."}
                  </p>
                )}
              </section>
            </div>

            <LiveMap data={data} />
            <p className="live-data-note">
              Fire markers are individual NASA FIRMS detections. The map intentionally shows no fire marker
              when the live feed contains no detections or is unavailable.
            </p>
          </>
        )}
      </main>
    </div>
  );
}

export default App;
