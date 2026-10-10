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

  public static getConfig(req: Request, res: Response) {
    return res.status(200).json({
      projection: { origin_lat: 29.5, origin_lon: 76.5 },
      simulation: {
        timestep_seconds: 900,
        horizon_hours: 9,
        particle_count_per_fire: 500,
        base_diffusion_kx: 250.0,
        base_diffusion_ky: 250.0,
        initial_sigma_meters: 2000.0,
        decay_rate_lambda: 3.2e-5,
        rain_washout_factor: 0.70,
        min_mass_threshold: 0.01,
      },
      risk_weights: {
        w1_concentration: 0.40,
        w2_plume_probability: 0.30,
        w3_exposure_duration: 0.20,
        w4_uncertainty: 0.10,
        low_threshold: 0.25,
        moderate_threshold: 0.50,
        high_threshold: 0.75,
      },
      ensemble_members: [
        { member_id: "member_1", name: "Lower Wind / East Drift / Reduced Emissions" },
        { member_id: "member_2", name: "Nominal GFS Forecast / Baseline Emissions" },
        { member_id: "member_3", name: "Higher Wind / West Drift / Elevated Emissions" },
      ],
    });
  }
}
