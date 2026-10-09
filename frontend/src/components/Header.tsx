import React from "react";

interface HeaderProps {
  predictionId?: string;
  generatedAt?: string;
  onRunReplay: (grapStage: number) => void;
  isLoading: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  predictionId,
  generatedAt,
  onRunReplay,
  isLoading,
}) => {
  return (
    <header className="header-container">
      <div className="header-brand">
        <div className="logo-icon">🌫️</div>
        <div>
          <h1>DhuanAlert</h1>
          <p className="subtitle">
            Hybrid Lagrangian Smoke Early Warning & School Cluster Risk Engine
          </p>
        </div>
      </div>

      <div className="header-actions">
        {predictionId && (
          <div className="run-tag">
            <span className="dot online"></span>
            <span>
              Run: {predictionId.slice(0, 22)}... {generatedAt ? `(${new Date(generatedAt).toLocaleTimeString()})` : ""}
            </span>
          </div>
        )}

        <div className="stage-buttons">
          <button
            className="btn btn-stage"
            onClick={() => onRunReplay(2)}
            disabled={isLoading}
          >
            Stage II (Very Poor)
          </button>
          <button
            className="btn btn-primary"
            onClick={() => onRunReplay(3)}
            disabled={isLoading}
          >
            {isLoading ? "Simulating..." : "Simulate GRAP Stage III"}
          </button>
          <button
            className="btn btn-stage"
            onClick={() => onRunReplay(4)}
            disabled={isLoading}
          >
            Stage IV (Severe+)
          </button>
        </div>
      </div>
    </header>
  );
};
