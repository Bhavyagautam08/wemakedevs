import { Router } from "express";
import { AdvisoriesController } from "../controllers/advisories.controller";

export const advisoriesRouter = Router();

advisoriesRouter.get("/advisories", AdvisoriesController.listAdvisories);
advisoriesRouter.get("/advisories/:advisory_id", AdvisoriesController.getAdvisory);
advisoriesRouter.post("/advisories/generate", AdvisoriesController.generateAdvisory);
advisoriesRouter.post("/advisories/:advisory_id/review", AdvisoriesController.reviewAdvisory);
advisoriesRouter.patch("/advisories/:advisory_id/review", AdvisoriesController.reviewAdvisory);
