import { Router } from "express";
import { runsRouter } from "./runs.routes";
import { advisoriesRouter } from "./advisories.routes";
import { policyRouter } from "./policy.routes";
import { evaluationRouter } from "./evaluation.routes";
import { dataRouter } from "./data.routes";

export const apiRouter = Router();

// Health endpoints
apiRouter.get("/health", (req, res) => {
  res.status(200).json({
    status: "ok",
    service: "dhuanalert-api",
    pipeline: "express-typescript-mern",
    version: "1.0.0",
    timestamp: new Date().toISOString(),
  });
});

// Mounted v1 routes
apiRouter.use("/v1", runsRouter);
apiRouter.use("/v1", advisoriesRouter);
apiRouter.use("/v1", policyRouter);
apiRouter.use("/v1", evaluationRouter);
apiRouter.use("/v1", dataRouter);
