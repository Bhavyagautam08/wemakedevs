import { FrontendPayload, EvaluationReport, AdvisoryOutput, TimelineSlice, SchoolRiskAssessment } from "./types";

export class DhuanAlertClient {
  private baseUrl: string;

  constructor(baseUrl: string = "http://127.0.0.1:3000") {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
    });

    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json") ? await response.json() : await response.text();

    if (!response.ok) {
      const errorMsg = data && data.error ? data.error.message : `HTTP ${response.status}`;
      throw new Error(errorMsg);
    }

    return data as T;
  }

  async getHealth(): Promise<{ status: string; service: string }> {
    return this.request("/health");
  }

  async createRun(options: { mode?: string; snapshot_id?: string; grap_stage?: number } = {}): Promise<{ run_id: string; payload: FrontendPayload }> {
    return this.request("/v1/runs", {
      method: "POST",
      body: JSON.stringify({ mode: "replay", snapshot_id: "sample", grap_stage: 3, ...options }),
    });
  }

  async listRuns(): Promise<{ runs: any[] }> {
    return this.request("/v1/runs");
  }

  async getRun(runId: string): Promise<FrontendPayload> {
    return this.request(`/v1/runs/${encodeURIComponent(runId)}`);
  }

  async getRunMap(runId: string): Promise<any> {
    return this.request(`/v1/runs/${encodeURIComponent(runId)}/map.geojson`);
  }

  async getRunTimeline(runId: string): Promise<{ run_id: string; slices_count: number; timeline: TimelineSlice[] }> {
    return this.request(`/v1/runs/${encodeURIComponent(runId)}/timeline`);
  }

  async getRunSchools(runId: string, filters: { riskBand?: string; district?: string } = {}): Promise<{ run_id: string; schools: SchoolRiskAssessment[] }> {
    const params = new URLSearchParams();
    if (filters.riskBand) params.set("risk_band", filters.riskBand);
    if (filters.district) params.set("district", filters.district);
    const qs = params.toString();
    return this.request(`/v1/runs/${encodeURIComponent(runId)}/schools${qs ? `?${qs}` : ""}`);
  }

  async reviewAdvisory(advisoryId: string, action: "APPROVE" | "REJECT", officerId: string = "District_Education_Officer", notes: string = ""): Promise<{ advisory: AdvisoryOutput; publication_status: string }> {
    return this.request(`/v1/advisories/${encodeURIComponent(advisoryId)}/review`, {
      method: "POST",
      body: JSON.stringify({ action, officer_id: officerId, notes }),
    });
  }

  async getEvaluation(): Promise<EvaluationReport> {
    return this.request("/v1/evaluation");
  }

  async getWeather(params: { latitude?: number; longitude?: number; hourly?: string; forecast_days?: number } = {}): Promise<any> {
    const search = new URLSearchParams();
    if (params.latitude !== undefined) search.set("latitude", params.latitude.toString());
    if (params.longitude !== undefined) search.set("longitude", params.longitude.toString());
    if (params.hourly) search.set("hourly", params.hourly);
    if (params.forecast_days !== undefined) search.set("forecast_days", params.forecast_days.toString());
    const qs = search.toString();
    return this.request(`/v1/data/weather${qs ? `?${qs}` : ""}`);
  }
}

