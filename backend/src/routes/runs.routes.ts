import { Router } from "express";
import { RunsController } from "../controllers/runs.controller";

export const runsRouter = Router();

runsRouter.post("/runs", RunsController.createRun);
runsRouter.get("/runs", RunsController.listRuns);
runsRouter.get("/runs/:run_id", RunsController.getRun);
runsRouter.get("/runs/:run_id/prediction", RunsController.getPrediction);
runsRouter.get("/runs/:run_id/advisory", RunsController.getAdvisory);
runsRouter.get("/runs/:run_id/map.geojson", RunsController.getMap);
runsRouter.get("/runs/:run_id/timeline", RunsController.getTimeline);
runsRouter.get("/runs/:run_id/timeline/:hour", RunsController.getTimelineHour);
runsRouter.get("/runs/:run_id/schools", RunsController.getSchools);
runsRouter.get("/runs/:run_id/ensemble", RunsController.getEnsemble);

runsRouter.post("/predict/simulate", RunsController.simulate);
