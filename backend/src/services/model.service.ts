import { spawn } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";
import { randomUUID } from "node:crypto";
import { CONFIG, PROJECT_ROOT } from "../config";
import { CreateRunRequest, FrontendPayload, EvaluationReport, PredictiveOutput, AdvisoryOutput, LiveDataSnapshot } from "../types";

export interface ModelPipelineResult {
  payload: FrontendPayload;
  map: any;
  evaluation: EvaluationReport;
  prediction: PredictiveOutput;
  advisory: AdvisoryOutput;
}

export class ModelRunnerError extends Error {
  constructor(
    public readonly statusCode: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ModelRunnerError";
  }
}

export class ModelService {
  private static MAX_BUFFER = 1024 * 1024 * 4; // 4 MiB

  public static async executeRunner(args: string[], envOverrides: Record<string, string> = {}): Promise<string> {
    const pythonExecutable = CONFIG.pythonExecutable;
    const stdout: string[] = [];
    const stderr: string[] = [];

    return new Promise((resolve, reject) => {
      const child = spawn(
        pythonExecutable,
        [path.join(CONFIG.mlModelDir, "run_pipeline.py"), ...args],
        {
          cwd: CONFIG.mlModelDir,
          env: {
            ...process.env,
            PYTHONUTF8: "1",
            PYTHONIOENCODING: "utf-8",
            ...envOverrides,
          },
          windowsHide: true,
        },
      );

      child.stdout.on("data", (chunk) => stdout.push(chunk.toString("utf8")));
      child.stderr.on("data", (chunk) => stderr.push(chunk.toString("utf8")));
      child.once("error", reject);
      child.once("close", (code) => {
        if (code === 0) {
          resolve(stdout.join("").trim());
        } else {
          const detail = stderr.join("").trim() || stdout.join("").trim();
          reject(this.toRunnerError(code, detail));
        }
      });
    });
  }

  private static toRunnerError(exitCode: number | null, detail: string): Error {
    try {
      const structured = JSON.parse(detail) as { status?: string; code?: string; message?: string };
      if (structured.status === "error" && structured.code && structured.message) {
        const clientInputCodes = new Set([
          "MISSING_SIMULATION_INPUT",
          "UNSUPPORTED_MODE",
          "WEATHER_LOCATION_REQUIRED",
          "WEATHER_LOCATION_INVALID",
          "WEATHER_COVERAGE_ERROR",
          "OPEN_METEO_SCHEMA_ERROR",
          "LIVE_FIRE_DATA_EMPTY",
        ]);
        return new ModelRunnerError(
          clientInputCodes.has(structured.code) ? 422 : 502,
          structured.code,
          structured.message,
        );
      }
    } catch {
      // Non-JSON stderr is preserved below as a diagnostic, not replaced.
    }

    return new ModelRunnerError(
      502,
      "MODEL_RUNNER_FAILED",
      `ML Model engine exited with code ${exitCode}: ${detail}`,
    );
  }

  public static async runForecast(request: CreateRunRequest): Promise<ModelPipelineResult> {
    const workingOutputDir = path.join(PROJECT_ROOT, "output", `.api-work-${randomUUID()}`);
    await fs.mkdir(workingOutputDir, { recursive: true });

    const mode = request.mode || "replay";
    const snapshotId = request.snapshot_id || "sample";
    const grapStage = request.grap_stage || 3;
    const humanApproved = request.human_approved || false;

    const args = [
      "run",
      "--mode", mode,
      "--snapshot", snapshotId,
      "--grap-stage", String(grapStage),
      "--output-dir", workingOutputDir,
    ];

    if (humanApproved) {
      args.push("--human-approved");
    }

    if (request.hotspots || request.weather || request.schools) {
      const tempInputFile = path.join(workingOutputDir, "custom_input.json");
      await fs.writeFile(
        tempInputFile,
        JSON.stringify({
          hotspots: request.hotspots,
          weather: request.weather,
          schools: request.schools,
        }),
      );
      args.push("--input-file", tempInputFile);
    }

    try {
      await this.executeRunner(args, {
        DHUANALERT_GRAP_STAGE: String(grapStage),
        DHUANALERT_OUTPUT_DIR: workingOutputDir,
      });

      const [payload, map, evaluation] = await Promise.all([
        fs.readFile(path.join(workingOutputDir, "frontend_payload.json"), "utf8").then(JSON.parse),
        fs.readFile(path.join(workingOutputDir, "map.geojson"), "utf8").then(JSON.parse),
        fs.readFile(path.join(workingOutputDir, "evaluation_report.json"), "utf8").then(JSON.parse),
      ]);

      return {
        payload,
        map,
        evaluation,
        prediction: payload.prediction,
        advisory: payload.advisory,
      };
    } finally {
      await fs.rm(workingOutputDir, { recursive: true, force: true });
    }
  }

  public static async getLiveDataSnapshot(): Promise<LiveDataSnapshot> {
    const output = await this.executeRunner(["data", "--type", "live"]);
    return JSON.parse(output) as LiveDataSnapshot;
  }

  public static async getLiveFires(): Promise<LiveDataSnapshot["fires"]> {
    const output = await this.executeRunner(["data", "--type", "live-fires"]);
    return JSON.parse(output) as LiveDataSnapshot["fires"];
  }

  public static async getLiveWeather(): Promise<LiveDataSnapshot["weather"]> {
    const output = await this.executeRunner(["data", "--type", "live-weather"]);
    return JSON.parse(output) as LiveDataSnapshot["weather"];
  }

  public static async simulateLayer1(data: { hotspots?: any[]; weather?: any[]; schools?: any[] } = {}): Promise<PredictiveOutput> {
    const tempDir = path.join(PROJECT_ROOT, "output", `.sim-${randomUUID()}`);
    await fs.mkdir(tempDir, { recursive: true });
    const inputFile = path.join(tempDir, "input.json");
    const outputFile = path.join(tempDir, "pred.json");
    await fs.writeFile(inputFile, JSON.stringify(data));

    try {
      await this.executeRunner(["simulate", "--input-file", inputFile, "--output-file", outputFile]);
      const content = await fs.readFile(outputFile, "utf8");
      return JSON.parse(content);
    } finally {
      await fs.rm(tempDir, { recursive: true, force: true });
    }
  }

  public static async generateAdvisory(
    prediction: PredictiveOutput,
    grapStage: number = 3,
    humanApproved: boolean = false,
  ): Promise<AdvisoryOutput> {
    const tempDir = path.join(PROJECT_ROOT, "output", `.genadv-${randomUUID()}`);
    await fs.mkdir(tempDir, { recursive: true });
    const predFile = path.join(tempDir, "pred.json");
    const advFile = path.join(tempDir, "adv.json");

    await fs.writeFile(predFile, JSON.stringify(prediction));
    const args = [
      "advisory",
      "--prediction-file", predFile,
      "--grap-stage", String(grapStage),
      "--output-file", advFile,
    ];
    if (humanApproved) {
      args.push("--human-approved");
    }

    try {
      await this.executeRunner(args);
      const content = await fs.readFile(advFile, "utf8");
      return JSON.parse(content);
    } finally {
      await fs.rm(tempDir, { recursive: true, force: true });
    }
  }
}
