import { Router } from "express";
import { DataController } from "../controllers/data.controller";

export const dataRouter = Router();

dataRouter.get("/config", DataController.getConfig);
dataRouter.get("/data/schools", DataController.getSchools);
dataRouter.get("/data/fires", DataController.getFires);
dataRouter.get("/data/weather", DataController.getWeather);
