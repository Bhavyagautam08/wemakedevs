import { Request, Response, NextFunction } from "express";
import { EvaluationService } from "../services/evaluation.service";
import { StorageService } from "../services/storage.service";

export class EvaluationController {
  public static async getLatestEvaluation(req: Request, res: Response, next: NextFunction) {
    try {
      const storedReport = await StorageService.getRunEvaluation();
      if (storedReport) {
        return res.status(200).json(storedReport);
      }
      const demoReport = EvaluationService.runDemo();
      return res.status(200).json(demoReport);
    } catch (err) {
      next(err);
    }
  }

  public static async evaluateCustom(req: Request, res: Response, next: NextFunction) {
    try {
      const body = req.body || {};
      const indexThreshold = body.index_threshold || 40.0;
      const deltaPm25Threshold = body.delta_pm25_threshold || 50.0;

      let report;
      if (body.forecasts && body.observations) {
        report = EvaluationService.evaluateGroundTruth({
          forecasts: body.forecasts,
          observations: body.observations,
          indexThreshold,
          deltaPm25Threshold,
        });
      } else {
        report = EvaluationService.runDemo(indexThreshold, deltaPm25Threshold);
      }

      return res.status(200).json(report);
    } catch (err) {
      next(err);
    }
  }
}
