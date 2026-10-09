import { Request, Response, NextFunction } from "express";
import { PolicyService } from "../services/policy.service";
import { ClaimsService } from "../services/claims.service";
import { ApiError } from "../middleware/errorHandler";

export class PolicyController {
  public static getGrapPolicy(req: Request, res: Response) {
    return res.status(200).json(PolicyService.getGrapCatalog());
  }

  public static evaluateCedar(req: Request, res: Response, next: NextFunction) {
    try {
      const body = req.body || {};
      if (!body.action_id || !body.risk_band || body.grap_stage === undefined) {
        throw new ApiError(422, "MISSING_PARAMETERS", "action_id, risk_band, and grap_stage are required.");
      }

      const decision = PolicyService.evaluateCedar({
        action_id: body.action_id,
        risk_band: body.risk_band,
        grap_stage: body.grap_stage,
        human_approved: body.human_approved !== undefined ? body.human_approved : true,
        principal_role: body.principal_role,
        n_schools_affected: body.n_schools_affected,
      });

      return res.status(200).json(decision);
    } catch (err) {
      next(err);
    }
  }

  public static validateClaims(req: Request, res: Response, next: NextFunction) {
    try {
      const body = req.body || {};
      if (!body.text) {
        throw new ApiError(422, "EMPTY_TEXT", "text field is required.");
      }

      const result = ClaimsService.validate(body.text);
      return res.status(200).json(result);
    } catch (err) {
      next(err);
    }
  }
}
