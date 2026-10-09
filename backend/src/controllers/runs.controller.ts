import { Request, Response, NextFunction } from "express";
import { ModelService } from "../services/model.service";
import { StorageService } from "../services/storage.service";
import { ApiError } from "../middleware/errorHandler";
import { CreateRunRequest } from "../types";

export class RunsController {
  public static async createRun(req: Request, res: Response, next: NextFunction) {
    try {
      const body: CreateRunRequest = req.body || {};
      const mode = body.mode || "replay";
      const snapshotId = body.snapshot_id || "sample";
      const grapStage = body.grap_stage !== undefined ? body.grap_stage : 3;

      if (!["replay", "custom", "live"].includes(mode)) {
        throw new ApiError(422, "UNSUPPORTED_MODE", "Mode must be 'replay' or 'custom'.");
      }
      if (mode === "replay" && snapshotId !== "sample") {
        throw new ApiError(422, "UNKNOWN_SNAPSHOT", "Only snapshot_id 'sample' is available in this repository.");
      }
      if (!Number.isInteger(grapStage) || grapStage < 1 || grapStage > 4) {
        throw new ApiError(422, "INVALID_GRAP_STAGE", "grap_stage must be an integer from 1 to 4.");
      }

      const result = await ModelService.runForecast({
        mode,
        snapshot_id: snapshotId,
        grap_stage: grapStage,
        human_approved: body.human_approved,
        hotspots: body.hotspots,
        weather: body.weather,
        schools: body.schools,
      });

      const runId = await StorageService.persistRun(result, grapStage, mode, snapshotId);

      return res.status(201).json({
        run_id: runId,
        mode,
        snapshot_id: snapshotId,
        links: {
          self: `/v1/runs/${runId}`,
          prediction: `/v1/runs/${runId}/prediction`,
          advisory: `/v1/advisories/${result.advisory.advisory_id}`,
          map: `/v1/runs/${runId}/map.geojson`,
          timeline: `/v1/runs/${runId}/timeline`,
          schools: `/v1/runs/${runId}/schools`,
          ensemble: `/v1/runs/${runId}/ensemble`,
        },
        payload: result.payload,
      });
    } catch (err) {
      next(err);
    }
  }

  public static async listRuns(req: Request, res: Response, next: NextFunction) {
    try {
      const severity = req.query.severity as string | undefined;
      const grapStage = req.query.grap_stage ? Number(req.query.grap_stage) : undefined;
      const limit = req.query.limit ? Number(req.query.limit) : undefined;

      const runs = await StorageService.listRuns({ severity, grapStage, limit });
      return res.status(200).json({ runs });
    } catch (err) {
      next(err);
    }
  }

  public static async getRun(req: Request, res: Response, next: NextFunction) {
    try {
      const run_id = req.params.run_id as string;
      const payload = await StorageService.getRunPayload(run_id);
      if (!payload) {
        throw new ApiError(404, "RUN_NOT_FOUND", `Run '${run_id}' was not found.`);
      }
      return res.status(200).json(payload);
    } catch (err) {
      next(err);
    }
  }

  public static async getPrediction(req: Request, res: Response, next: NextFunction) {
    try {
      const run_id = req.params.run_id as string;
      const payload = await StorageService.getRunPayload(run_id);
      if (!payload || !payload.prediction) {
        throw new ApiError(404, "RUN_NOT_FOUND", `Prediction for run '${run_id}' was not found.`);
      }
      return res.status(200).json(payload.prediction);
    } catch (err) {
      next(err);
    }
  }

  public static async getAdvisory(req: Request, res: Response, next: NextFunction) {
    try {
      const run_id = req.params.run_id as string;
      const payload = await StorageService.getRunPayload(run_id);
      if (!payload || !payload.advisory) {
        throw new ApiError(404, "RUN_NOT_FOUND", `Advisory for run '${run_id}' was not found.`);
      }
      return res.status(200).json(payload.advisory);
    } catch (err) {
      next(err);
    }
  }

  public static async getMap(req: Request, res: Response, next: NextFunction) {
    try {
      const run_id = req.params.run_id as string;
      const map = await StorageService.getRunMap(run_id);
      if (!map) {
        throw new ApiError(404, "MAP_NOT_FOUND", `Map for run '${run_id}' was not found.`);
      }
      return res.status(200).json(map);
    } catch (err) {
      next(err);
    }
  }

  public static async getTimeline(req: Request, res: Response, next: NextFunction) {
    try {
      const run_id = req.params.run_id as string;
      const payload = await StorageService.getRunPayload(run_id);
      if (!payload || !payload.prediction) {
        throw new ApiError(404, "RUN_NOT_FOUND", `Run '${run_id}' was not found.`);
      }
      return res.status(200).json({
        run_id,
        slices_count: payload.prediction.timeline.length,
        timeline: payload.prediction.timeline,
      });
    } catch (err) {
      next(err);
    }
  }

  public static async getTimelineHour(req: Request, res: Response, next: NextFunction) {
    try {
      const run_id = req.params.run_id as string;
      const hour = req.params.hour as string;
      const hourNum = Number.parseInt(hour, 10);
      const payload = await StorageService.getRunPayload(run_id);
      if (!payload || !payload.prediction) {
        throw new ApiError(404, "RUN_NOT_FOUND", `Run '${run_id}' was not found.`);
      }

      const slice = payload.prediction.timeline.find((s) => s.horizon_offset_hours === hourNum);
      if (!slice) {
        throw new ApiError(404, "HOUR_NOT_FOUND", `Timeline slice T+${hour}h not found.`);
      }
      return res.status(200).json(slice);
    } catch (err) {
      next(err);
    }
  }

  public static async getSchools(req: Request, res: Response, next: NextFunction) {
    try {
      const run_id = req.params.run_id as string;
      const payload = await StorageService.getRunPayload(run_id);
      if (!payload || !payload.prediction) {
        throw new ApiError(404, "RUN_NOT_FOUND", `Run '${run_id}' was not found.`);
      }

      let schools = payload.prediction.schools;
      const riskBand = req.query.risk_band as string | undefined;
      const district = req.query.district as string | undefined;
      const minScore = req.query.min_score ? Number(req.query.min_score) : undefined;

      if (riskBand) {
        schools = schools.filter((s) => s.risk_band.toUpperCase() === riskBand.toUpperCase());
      }
      if (district) {
        schools = schools.filter((s) => s.district.toLowerCase().includes(district.toLowerCase()));
      }
      if (minScore !== undefined && !Number.isNaN(minScore)) {
        schools = schools.filter((s) => s.risk_score >= minScore);
      }

      return res.status(200).json({
        run_id,
        total_assessed: schools.length,
        schools,
      });
    } catch (err) {
      next(err);
    }
  }

  public static async getEnsemble(req: Request, res: Response, next: NextFunction) {
    try {
      const run_id = req.params.run_id as string;
      const payload = await StorageService.getRunPayload(run_id);
      if (!payload || !payload.prediction) {
        throw new ApiError(404, "RUN_NOT_FOUND", `Run '${run_id}' was not found.`);
      }
      return res.status(200).json(payload.prediction.ensemble);
    } catch (err) {
      next(err);
    }
  }

  public static async simulate(req: Request, res: Response, next: NextFunction) {
    try {
      const body = req.body || {};
      const pred = await ModelService.simulateLayer1(body);
      return res.status(200).json(pred);
    } catch (err) {
      next(err);
    }
  }
}
