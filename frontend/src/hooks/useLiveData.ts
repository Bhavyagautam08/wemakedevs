import { useCallback, useEffect, useState } from "react";
import { DhuanAlertClient } from "../api/client";
import { LiveDataSnapshot } from "../api/types";

export function useLiveData(client: DhuanAlertClient) {
  const [data, setData] = useState<LiveDataSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await client.getLiveData());
    } catch (err: unknown) {
      setData(null);
      setError(err instanceof Error ? err.message : "Could not fetch live data.");
    } finally {
      setLoading(false);
    }
  }, [client]);

  useEffect(() => {
    void refresh();
    const interval = window.setInterval(() => void refresh(), 5 * 60 * 1000);
    return () => window.clearInterval(interval);
  }, [refresh]);

  return { data, loading, error, refresh };
}
