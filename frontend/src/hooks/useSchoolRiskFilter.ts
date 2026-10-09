import { useState, useMemo } from "react";
import { SchoolRiskAssessment } from "../api/types";

export function useSchoolRiskFilter(schools: SchoolRiskAssessment[] = []) {
  const [search, setSearch] = useState<string>("");
  const [selectedRiskBand, setSelectedRiskBand] = useState<string>("ALL");
  const [sortBy, setSortBy] = useState<"score_desc" | "score_asc" | "arrival_asc">("score_desc");

  const filteredSchools = useMemo(() => {
    let result = [...schools];

    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        (s) =>
          s.name.toLowerCase().includes(q) ||
          s.district.toLowerCase().includes(q),
      );
    }

    if (selectedRiskBand !== "ALL") {
      result = result.filter((s) => s.risk_band === selectedRiskBand);
    }

    if (sortBy === "score_desc") {
      result.sort((a, b) => b.risk_score - a.risk_score);
    } else if (sortBy === "score_asc") {
      result.sort((a, b) => a.risk_score - b.risk_score);
    } else if (sortBy === "arrival_asc") {
      result.sort((a, b) => {
        if (!a.predicted_arrival_time) return 1;
        if (!b.predicted_arrival_time) return -1;
        return a.predicted_arrival_time.localeCompare(b.predicted_arrival_time);
      });
    }

    return result;
  }, [schools, search, selectedRiskBand, sortBy]);

  return {
    search,
    setSearch,
    selectedRiskBand,
    setSelectedRiskBand,
    sortBy,
    setSortBy,
    filteredSchools,
    totalCount: schools.length,
    matchCount: filteredSchools.length,
  };
}
