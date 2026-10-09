import { Request, Response, NextFunction } from "express";
import { StorageService } from "../services/storage.service";
import { ModelService } from "../services/model.service";
import { ApiError } from "../middleware/errorHandler";

export class AdvisoriesController {
  public static async listAdvisories(req: Request, res: Response, next: NextFunction) {
    try {
      const runs = await StorageService.listRuns();
      const advisories = [];
      for (const run of runs) {
        const payload = await StorageService.getRunPayload(run.run_id);
        if (payload && payload.advisory) {
          advisories.push({
            advisory_id: payload.advisory.advisory_id,
            run_id: run.run_id,
            severity: payload.advisory.severity,
            headline: payload.advisory.headline,
            publication_status: payload.advisory.validation.publication_status,
          });
        }
      }
      return res.status(200).json({ advisories });
    } catch (err) {
      next(err);
    }
  }

  public static async getAdvisory(req: Request, res: Response, next: NextFunction) {
    try {
      const advisory_id = req.params.advisory_id as string;
      const found = await StorageService.findRunByAdvisoryId(advisory_id);
      if (!found || !found.payload.advisory) {
        throw new ApiError(404, "ADVISORY_NOT_FOUND", `Advisory '${advisory_id}' was not found.`);
      }
      return res.status(200).json(found.payload.advisory);
    } catch (err) {
      next(err);
    }
  }

  public static async generateAdvisory(req: Request, res: Response, next: NextFunction) {
    try {
      const body = req.body || {};
      const grapStage = body.grap_stage || 3;
      const humanApproved = body.human_approved || false;

      let prediction = body.prediction;
      if (!prediction && body.prediction_id) {
        const payload = await StorageService.getRunPayload(body.prediction_id);
        if (!payload) {
          throw new ApiError(404, "PREDICTION_NOT_FOUND", `Prediction '${body.prediction_id}' was not found.`);
        }
        prediction = payload.prediction;
      } else if (!prediction) {
        prediction = await ModelService.simulateLayer1();
      }

      const advisory = await ModelService.generateAdvisory(prediction, grapStage, humanApproved);
      return res.status(200).json(advisory);
    } catch (err) {
      next(err);
    }
  }

  public static async reviewAdvisory(req: Request, res: Response, next: NextFunction) {
    try {
      const advisory_id = req.params.advisory_id as string;
      const body = req.body || {};
      const action = (body.action || "APPROVE").toUpperCase();
      const officerId = body.officer_id || "District_Education_Officer_1";
      const notes = body.notes || "";

      if (!["APPROVE", "REJECT"].includes(action)) {
        throw new ApiError(422, "INVALID_ACTION", "Action must be 'APPROVE' or 'REJECT'.");
      }

      const found = await StorageService.findRunByAdvisoryId(advisory_id);
      if (!found) {
        throw new ApiError(404, "ADVISORY_NOT_FOUND", `Advisory '${advisory_id}' was not found.`);
      }

      const isApprove = action === "APPROVE";
      const newStatus = isApprove ? "APPROVED" : "REJECTED";

      const updatedAdvisory = {
        ...found.payload.advisory,
        validation: {
          ...found.payload.advisory.validation,
          publication_status: newStatus as any,
          policy_check: isApprove ? ("PASSED" as const) : ("FAILED" as const),
          rejection_reason: isApprove ? null : notes || "Rejected by reviewing officer.",
        },
        model_metadata: {
          ...found.payload.advisory.model_metadata,
          reviewed_by: officerId,
          reviewed_at: new Date().toISOString(),
          ...(notes ? { review_notes: notes } : {}),
        },
      };

      await StorageService.updateAdvisory(found.runId, updatedAdvisory);

      return res.status(200).json({
        advisory_id,
        publication_status: newStatus,
        advisory: updatedAdvisory,
      });
    } catch (err) {
      next(err);
    }
  }
}
