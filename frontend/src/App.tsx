import { useState, useMemo } from "react";
import { DhuanAlertClient } from "./api/client";
import { useForecast } from "./hooks/useForecast";
import { useTimelineSlider } from "./hooks/useTimelineSlider";
import { TopNavbar } from "./components/TopNavbar";
import { SidebarControls } from "./components/SidebarControls";
import { PlumeMap } from "./components/PlumeMap";
import { AdvisoryPanel } from "./components/AdvisoryPanel";
import { SchoolRiskTable } from "./components/SchoolRiskTable";
import { LocationForecastChart } from "./components/LocationForecastChart";
import { ModelEvaluationChart } from "./components/ModelEvaluationChart";
import { BottomTelemetryBar } from "./components/BottomTelemetryBar";

export function App() {
  const client = useMemo(
    () => new DhuanAlertClient(import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:3000"),
    [],
  );
  const { data, setData, loading, error, refreshForecast } = useForecast(client);

  // Navigation & Location state
  const [activeTab, setActiveTab] = useState("dashboard");
  const [selectedLocation, setSelectedLocation] = useState("all");

  // Forecast configuration state
  const [forecastDate, setForecastDate] = useState("2026-10-09");
  const [forecastTime, setForecastTime] = useState("14:00");
  const [horizonHours, setHorizonHours] = useState(6);
  const [activeMode, setActiveMode] = useState<"live" | "replay">("live");

  // Layer toggles
  const [showFires, setShowFires] = useState(true);
  const [showPlume, setShowPlume] = useState(true);
  const [showWind, setShowWind] = useState(true);
  const [showSchools, setShowSchools] = useState(true);
  const [showOpenAq, setShowOpenAq] = useState(true);
  const [showBoundaries, setShowBoundaries] = useState(true);

  // Overlay option
  const [overlayOption, setOverlayOption] = useState("pm25");

  // School table filters
  const [schoolSearch, setSchoolSearch] = useState("");
  const [selectedDistrict, setSelectedDistrict] = useState("ALL");

  // Time Slider Hook
  const {
    currentStep,
    setCurrentStep,
    currentSlice,
    isPlaying,
    togglePlay,
  } = useTimelineSlider(data?.prediction.timeline || [], 1400);

  // Handle Officer Review
  const handleReview = async (action: "APPROVE" | "REJECT", notes: string) => {
    if (!data?.advisory) return;
    const res = await client.reviewAdvisory(data.advisory.advisory_id, action, "District_Education_Officer", notes);
    setData({
      ...data,
      advisory: res.advisory,
    });
  };

  // Run New Forecast Trigger
  const handleRunForecast = async (mode: "live" | "replay") => {
    setActiveMode(mode);
    await refreshForecast(3, mode);
  };

  return (
    <div className="dhuanalert-app-root">
      {/* 1. Top Navbar Header */}
      <TopNavbar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        selectedLocation={selectedLocation}
        onLocationChange={setSelectedLocation}
        isLive={activeMode === "live"}
      />

      {/* 2. Main Dashboard View */}
      <main className="dashboard-main-area">
        {loading && (
          <div className="fullscreen-loading-overlay">
            <div className="loading-spinner"></div>
            <p>Ingesting real-time NASA FIRMS active fires & Open-Meteo GFS wind fields...</p>
          </div>
        )}

        {error && (
          <div className="dashboard-error-banner">
            <span className="error-icon">⚠️</span>
            <div>
              <h4>Forecast Pipeline Connection Error</h4>
              <p>{error}</p>
            </div>
            <button className="btn-retry-conn" onClick={() => handleRunForecast("live")}>
              Retry Live Ingestion
            </button>
          </div>
        )}

        {data && (
          <div className="dashboard-layout-container">
            {/* Top 3-Column Section: Sidebar | Center Map | Right Advisory */}
            <div className="primary-dashboard-row">
              {/* Left Column: Sidebar Controls */}
              <div className="col-sidebar">
                <SidebarControls
                  date={forecastDate}
                  onDateChange={setForecastDate}
                  time={forecastTime}
                  onTimeChange={setForecastTime}
                  horizonHours={horizonHours}
                  onHorizonChange={setHorizonHours}
                  onRunForecast={handleRunForecast}
                  isLoading={loading}
                  activeMode={activeMode}
                  showFires={showFires}
                  onToggleFires={setShowFires}
                  showPlume={showPlume}
                  onTogglePlume={setShowPlume}
                  showWind={showWind}
                  onToggleWind={setShowWind}
                  showSchools={showSchools}
                  onToggleSchools={setShowSchools}
                  showOpenAq={showOpenAq}
                  onToggleOpenAq={setShowOpenAq}
                  showBoundaries={showBoundaries}
                  onToggleBoundaries={setShowBoundaries}
                  overlayOption={overlayOption}
                  onOverlayOptionChange={setOverlayOption}
                />
              </div>

              {/* Center Column: Interactive Plume & Wind Vector Map */}
              <div className="col-center-map">
                <PlumeMap
                  prediction={data.prediction}
                  timeline={data.prediction.timeline}
                  currentStep={currentStep}
                  currentSlice={currentSlice}
                  isPlaying={isPlaying}
                  onTogglePlay={togglePlay}
                  onStepChange={setCurrentStep}
                  schools={data.prediction.schools}
                  showFires={showFires}
                  showPlume={showPlume}
                  showWind={showWind}
                  showSchools={showSchools}
                  showOpenAq={showOpenAq}
                />
              </div>

              {/* Right Column: Advisory & Action Summary */}
              <div className="col-advisory">
                <AdvisoryPanel
                  advisory={data.advisory}
                  prediction={data.prediction}
                  onReview={handleReview}
                />
              </div>
            </div>

            {/* Middle Section: Top 10 Schools Risk Table | PM2.5 Forecast Chart | Model Evaluation */}
            <div className="secondary-dashboard-row">
              <div className="col-schools-table">
                <SchoolRiskTable
                  schools={data.prediction.schools}
                  search={schoolSearch}
                  onSearchChange={setSchoolSearch}
                  selectedDistrict={selectedDistrict}
                  onDistrictChange={setSelectedDistrict}
                />
              </div>

              <div className="col-forecast-curve">
                <LocationForecastChart
                  timeline={data.prediction.timeline}
                  schools={data.prediction.schools}
                />
              </div>

              <div className="col-eval-curve">
                <ModelEvaluationChart />
              </div>
            </div>

            {/* Bottom Section: 4 Status Telemetry Tiles */}
            <div className="telemetry-bar-row">
              <BottomTelemetryBar
                prediction={data.prediction}
                grapStage={3}
              />
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
