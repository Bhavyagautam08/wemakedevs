import { useState, useEffect, useCallback } from "react";
import { DhuanAlertClient } from "../api/client";
import { FrontendPayload } from "../api/types";

export function useForecast(client: DhuanAlertClient, initialRunId?: string) {
  const [currentRunId, setCurrentRunId] = useState<string | undefined>(initialRunId);
  const [data, setData] = useState<FrontendPayload | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadOrCreateForecast = useCallback(async (runId?: string, stage: number = 3) => {
    setLoading(true);
    setError(null);
    try {
      if (runId) {
        const payload = await client.getRun(runId);
        setData(payload);
        setCurrentRunId(runId);
      } else {
        const res = await client.createRun({ grap_stage: stage });
        setData(res.payload);
        setCurrentRunId(res.run_id);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load forecast data.");
    } finally {
      setLoading(false);
    }
  }, [client]);

  useEffect(() => {
    loadOrCreateForecast(initialRunId);
  }, [loadOrCreateForecast, initialRunId]);

  return {
    data,
    setData,
    currentRunId,
    loading,
    error,
    refreshForecast: (stage?: number) => loadOrCreateForecast(undefined, stage),
    loadSpecificRun: (runId: string) => loadOrCreateForecast(runId),
  };
}
