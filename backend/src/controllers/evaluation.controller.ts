import { Request, Response, NextFunction } from "express";
import { EvaluationService } from "../services/evaluation.service";
import { StorageService } from "../services/storage.service";
import { ApiError } from "../middleware/errorHandler";

const NO_BACKTEST = "NO_VALIDATED_BACKTEST_AVAILABLE";

export class EvaluationController {
  public static async getLatestEvaluation(req: Request, res: Response, next: NextFunction) {
    try {
      // Runs store {status, report}; only a non-null report is backed by real observations.
      // Older stored files without that envelope were produced by the synthetic demo fixture.
      const stored: any = await StorageService.getRunEvaluation();
      if (stored && stored.report) {
        return res.status(200).json({ status: "VALIDATED", report: stored.report });
      }
      return res.status(404).json({
        status: NO_BACKTEST,
        message: "No forecast has been evaluated against real station observations yet.",
      });
    } catch (err) {
      next(err);
    }
  }

  public static async evaluateCustom(req: Request, res: Response, next: NextFunction) {
    try {
      const body = req.body || {};
      if (!Array.isArray(body.forecasts) || !Array.isArray(body.observations)) {
        throw new ApiError(400, NO_BACKTEST, "Evaluation requires 'forecasts' and 'observations' arrays.");
      }
      const report = EvaluationService.evaluateGroundTruth({
        forecasts: body.forecasts,
        observations: body.observations,
        indexThreshold: body.index_threshold || 40.0,
        deltaPm25Threshold: body.delta_pm25_threshold || 50.0,
      });
      return res.status(200).json(report);
    } catch (err) {
      next(err);
    }
  }
}
