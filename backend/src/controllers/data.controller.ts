import { Request, Response, NextFunction } from "express";
import fs from "node:fs/promises";
import path from "node:path";
import { CONFIG } from "../config";

export class DataController {
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
      const data = JSON.parse(await fs.readFile(path.join(CONFIG.dataDir, "sample_fires.json"), "utf8"));
      return res.status(200).json(data);
    } catch (err) {
      next(err);
    }
  }

  public static async getWeather(req: Request, res: Response, next: NextFunction) {
    try {
      const latitude = req.query.latitude ? parseFloat(req.query.latitude as string) : 28.6139;
      const longitude = req.query.longitude ? parseFloat(req.query.longitude as string) : 77.2090;
      const hourly = (req.query.hourly as string) || "wind_speed_10m,wind_direction_10m,temperature_2m,relative_humidity_2m";
      const forecastDays = req.query.forecast_days ? parseInt(req.query.forecast_days as string, 10) : 2;

      const openMeteoUrl = `https://api.open-meteo.com/v1/forecast?latitude=${latitude}&longitude=${longitude}&hourly=${hourly}&forecast_days=${forecastDays}`;

      try {
        const response = await fetch(openMeteoUrl, {
          headers: { "User-Agent": "DhuanAlert-EarlyWarning/1.0" },
          signal: AbortSignal.timeout(5000),
        });
        if (response.ok) {
          const liveData: any = await response.json();
          if (req.query.raw === "true") {
            return res.status(200).json({ source: "Open-Meteo_GFS_Live", ...liveData });
          }
          const times: string[] = liveData.hourly?.time || [];
          const speeds: number[] = liveData.hourly?.wind_speed_10m || [];
          const dirs: number[] = liveData.hourly?.wind_direction_10m || [];
          const temps: number[] = liveData.hourly?.temperature_2m || [];
          const rhs: number[] = liveData.hourly?.relative_humidity_2m || [];

          const parsed = times.map((t: string, i: number) => {
            const ws_kmh = speeds[i] ?? 16.0;
            const ws_mps = Math.round((ws_kmh / 3.6) * 100) / 100;
            const wdir_deg = dirs[i] ?? 315.0;
            const rad = (wdir_deg * Math.PI) / 180;
            const u = Math.round(-ws_mps * Math.sin(rad) * 100) / 100;
            const v = Math.round(-ws_mps * Math.cos(rad) * 100) / 100;
            return {
              forecast_timestamp: `${t}:00Z`,
              wind_speed_mps: ws_mps,
              wind_direction_deg: wdir_deg,
              u_mps: u,
              v_mps: v,
              boundary_layer_height_m: 780.0,
              temperature_c: temps[i] ?? 23.5,
              relative_humidity_pct: rhs[i] ?? 55.0,
            };
          });

          if (parsed.length > 0) {
            return res.status(200).json(parsed);
          }
        }
      } catch {
        // Network timeout or error - continue to fallback
      }

      const data = JSON.parse(await fs.readFile(path.join(CONFIG.dataDir, "sample_weather.json"), "utf8"));
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
        horizon_hours: 6,
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
