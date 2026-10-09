import { Router } from "express";
import { EvaluationController } from "../controllers/evaluation.controller";

export const evaluationRouter = Router();

evaluationRouter.get("/evaluation", EvaluationController.getLatestEvaluation);
evaluationRouter.post("/evaluation/evaluate", EvaluationController.evaluateCustom);
