import React from "react";
import { SchoolRiskAssessment } from "../api/types";

interface SchoolRiskTableProps {
  schools: SchoolRiskAssessment[];
  search: string;
  onSearchChange: (val: string) => void;
  selectedRiskBand: string;
  onRiskBandChange: (val: string) => void;
  sortBy: string;
  onSortChange: (val: any) => void;
  totalCount: number;
}

export const SchoolRiskTable: React.FC<SchoolRiskTableProps> = ({
  schools,
  search,
  onSearchChange,
  selectedRiskBand,
  onRiskBandChange,
  sortBy,
  onSortChange,
  totalCount,
}) => {
  return (
    <div className="table-card">
      <div className="table-controls">
        <div className="search-box">
          <input
            type="text"
            placeholder="Search school name or district..."
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            className="search-input"
          />
        </div>

        <div className="filter-group">
          <select
            value={selectedRiskBand}
            onChange={(e) => onRiskBandChange(e.target.value)}
            className="select-input"
          >
            <option value="ALL">All Risk Bands</option>
            <option value="VERY_HIGH">Very High</option>
            <option value="HIGH">High</option>
            <option value="MODERATE">Moderate</option>
            <option value="LOW">Low</option>
          </select>

          <select
            value={sortBy}
            onChange={(e) => onSortChange(e.target.value)}
            className="select-input"
          >
            <option value="score_desc">Highest Risk Score</option>
            <option value="score_asc">Lowest Risk Score</option>
            <option value="arrival_asc">Earliest Arrival</option>
          </select>
        </div>
      </div>

      <div className="table-scroll">
        <table className="risk-table">
          <thead>
            <tr>
              <th>School Name</th>
              <th>District</th>
              <th>Risk Band</th>
              <th>Impact Probability</th>
              <th>Predicted Arrival</th>
              <th>Risk Score</th>
            </tr>
          </thead>
          <tbody>
            {schools.length > 0 ? (
              schools.map((s) => (
                <tr key={s.school_id}>
                  <td className="school-name">{s.name}</td>
                  <td className="district">{s.district}</td>
                  <td>
                    <span className={`risk-pill band-${s.risk_band.toLowerCase()}`}>
                      {s.risk_band}
                    </span>
                  </td>
                  <td>{(s.impact_probability * 100).toFixed(0)}%</td>
                  <td>
                    {s.predicted_arrival_time
                      ? new Date(s.predicted_arrival_time).toLocaleTimeString()
                      : "No Impact"}
                  </td>
                  <td className="score-val">{(s.risk_score * 100).toFixed(1)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={6} className="empty-row">
                  No schools matching the criteria.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="table-footer">
        Showing {schools.length} of {totalCount} monitored schools across Delhi-NCR.
      </div>
    </div>
  );
};
