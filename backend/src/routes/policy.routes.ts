import { Router } from "express";
import { PolicyController } from "../controllers/policy.controller";

export const policyRouter = Router();

policyRouter.get("/policy/grap", PolicyController.getGrapPolicy);
policyRouter.post("/policy/evaluate", PolicyController.evaluateCedar);
policyRouter.post("/claims/validate", PolicyController.validateClaims);
