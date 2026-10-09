import React from "react";

interface HeaderProps {
  fetchedAt?: string;
  onRefresh: () => void;
  isLoading: boolean;
}

export const Header: React.FC<HeaderProps> = ({ fetchedAt, onRefresh, isLoading }) => (
  <header className="header-container">
    <div className="header-brand">
      <div className="logo-icon">🌫️</div>
      <div>
        <h1>DhuanAlert</h1>
        <p className="subtitle">Live satellite fire detections and weather data</p>
        <p className="data-disclosure">
          Live provider data only. No replay snapshots, generated fire points, or synthetic evaluation results.
        </p>
      </div>
    </div>

    <div className="header-actions">
      {fetchedAt && (
        <div className="run-tag">
          Data fetched: {new Date(fetchedAt).toLocaleTimeString()}
        </div>
      )}
      <button className="btn btn-primary" onClick={onRefresh} disabled={isLoading}>
        {isLoading ? "Refreshing..." : "Refresh live data"}
      </button>
    </div>
  </header>
);
