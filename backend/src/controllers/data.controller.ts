import { Request, Response, NextFunction } from "express";
import fs from "node:fs/promises";
import path from "node:path";
import { CONFIG } from "../config";
import { ModelService } from "../services/model.service";

export class DataController {
  public static async getLiveData(req: Request, res: Response, next: NextFunction) {
    try {
      const data = await ModelService.getLiveDataSnapshot();
      return res.status(200).json(data);
    } catch (err) {
      next(err);
    }
  }

  public static async getSchools(req: Request, res: Response, next: NextFunction) {
    try {
      const data = JSON.parse(await fs.readFile(path.join(CONFIG.dataDir, "ncr_schools.json"), "utf8"));
      return res.status(200).json(data);
    } catch (err) {
      next(err);
    }
  }

  public static async getFires(req: Request, res: Response, next: NextFunction) {
    try {
      const data = await ModelService.getLiveFires();
      return res.status(200).json(data);
    } catch (err) {
      next(err);
    }
  }

  public static async getWeather(req: Request, res: Response, next: NextFunction) {
    try {
      const data = await ModelService.getLiveWeather();
      return res.status(200).json(data);
    } catch (err) {
      next(err);
    }
  }

  public static async getConfig(req: Request, res: Response, next: NextFunction) {
    try {
      // Single source of truth: the Python model's SimulationConfig / Config.
      return res.status(200).json(await ModelService.getModelConfig());
    } catch (err) {
      next(err);
    }
  }
}
