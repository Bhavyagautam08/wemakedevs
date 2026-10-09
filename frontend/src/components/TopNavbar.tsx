import React from "react";

interface TopNavbarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
  selectedLocation: string;
  onLocationChange: (loc: string) => void;
  isLive: boolean;
}

export const TopNavbar: React.FC<TopNavbarProps> = ({
  activeTab,
  onTabChange,
  selectedLocation,
  onLocationChange,
  isLive = true,
}) => {
  const tabs = [
    { id: "dashboard", label: "Dashboard" },
    { id: "schools", label: "Schools" },
    { id: "forecast", label: "Forecast" },
    { id: "advisories", label: "Advisories" },
    { id: "sources", label: "Data & Sources" },
    { id: "evaluation", label: "Evaluation" },
  ];

  return (
    <header className="top-navbar">
      <div className="navbar-brand">
        <div className="cloud-logo">☁️</div>
        <div>
          <h1 className="brand-title">DhuanAlert</h1>
          <p className="brand-subtitle">Real-time Smoke Forecasts for Safer Schools</p>
        </div>
      </div>

      <nav className="nav-tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={`nav-tab ${activeTab === tab.id ? "active" : ""}`}
            onClick={() => onTabChange(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <div className="navbar-right">
        <div className="location-select-wrapper">
          <select
            value={selectedLocation}
            onChange={(e) => onLocationChange(e.target.value)}
            className="location-select"
          >
            <option value="all">Punjab, Haryana, Delhi NCR</option>
            <option value="delhi">Delhi NCT</option>
            <option value="gurugram">Gurugram & Faridabad</option>
            <option value="noida">Noida & Ghaziabad</option>
            <option value="punjab">Punjab Stubble Zone</option>
          </select>
        </div>

        <div className="timestamp-badge">
          <span>{new Date().toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })}, 14:00 IST</span>
        </div>

        <div className="live-status-pill">
          <span className="live-dot"></span>
          <span>{isLive ? "Live Data" : "Replay Mode"}</span>
        </div>
      </div>
    </header>
  );
};
