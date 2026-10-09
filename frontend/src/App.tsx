import { useMemo } from "react";
import { DhuanAlertClient } from "./api/client";
import { useForecast } from "./hooks/useForecast";
import { useTimelineSlider } from "./hooks/useTimelineSlider";
import { useSchoolRiskFilter } from "./hooks/useSchoolRiskFilter";
import { Header } from "./components/Header";
import { AdvisoryBanner } from "./components/AdvisoryBanner";
import { PlumeMap } from "./components/PlumeMap";
import { TimelineSliderControl } from "./components/TimelineSliderControl";
import { SchoolRiskTable } from "./components/SchoolRiskTable";
import { EvaluationReportCard } from "./components/EvaluationReportCard";

export function App() {
  const client = useMemo(
    () => new DhuanAlertClient(import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:3000"),
    [],
  );
  const { data, setData, currentRunId, loading, error, refreshForecast } = useForecast(client);

  const {
    currentStep,
    setCurrentStep,
    currentSlice,
    isPlaying,
    togglePlay,
    nextStep,
    prevStep,
  } = useTimelineSlider(data?.prediction.timeline || [], 1400);

  const {
    search,
    setSearch,
    selectedRiskBand,
    setSelectedRiskBand,
    sortBy,
    setSortBy,
    filteredSchools,
    totalCount,
  } = useSchoolRiskFilter(data?.prediction.schools || []);

  const handleReview = async (action: "APPROVE" | "REJECT", notes: string) => {
    if (!data?.advisory) return;
    const res = await client.reviewAdvisory(data.advisory.advisory_id, action, "District_Education_Officer", notes);
    setData({
      ...data,
      advisory: res.advisory,
    });
  };

  const handleSelectHorizon = (hours: number) => {
    if (!data?.prediction.timeline) return;
    const idx = data.prediction.timeline.findIndex((s) => s.horizon_offset_hours === hours);
    if (idx !== -1) {
      setCurrentStep(idx);
    }
  };

  return (
    <div className="app-layout">
      <Header
        predictionId={currentRunId}
        generatedAt={data?.prediction.generated_at}
        onRunReplay={(stage) => refreshForecast(stage)}
        isLoading={loading}
      />

      <main className="main-content">
        {loading && (
          <div className="loading-state">
            <div className="spinner"></div>
            <p>Running 2D Lagrangian particle transport & Bedrock advisory engine...</p>
          </div>
        )}

        {error && (
          <div className="error-banner">
            <h3>Forecast Connection Error</h3>
            <p>{error}</p>
            <button className="btn btn-primary" onClick={() => refreshForecast()}>
              Retry Connection
            </button>
          </div>
        )}

        {!loading && data && (
          <>
            {/* Top Advisory Banner */}
            <AdvisoryBanner
              advisory={data.advisory}
              onReview={handleReview}
            />

            {/* Interactive Leaflet Plume Heatmap & Corridor Map */}
            <PlumeMap
              prediction={data.prediction}
              currentSlice={currentSlice}
              schools={data.prediction.schools}
              currentStep={currentStep}
              onSelectHorizon={handleSelectHorizon}
            />

            {/* Middle Section: Timeline Animation + School Risk Table */}
            <div className="dashboard-grid">
              <div className="left-column">
                <TimelineSliderControl
                  timeline={data.prediction.timeline}
                  currentStep={currentStep}
                  currentSlice={currentSlice}
                  isPlaying={isPlaying}
                  onTogglePlay={togglePlay}
                  onStepChange={setCurrentStep}
                  onNext={nextStep}
                  onPrev={prevStep}
                />

                <EvaluationReportCard client={client} />
              </div>

              <div className="right-column">
                <SchoolRiskTable
                  schools={filteredSchools}
                  search={search}
                  onSearchChange={setSearch}
                  selectedRiskBand={selectedRiskBand}
                  onRiskBandChange={setSelectedRiskBand}
                  sortBy={sortBy}
                  onSortChange={setSortBy}
                  totalCount={totalCount}
                />
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

export default App;
