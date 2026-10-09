"use strict";

const http = require("node:http");
const fs = require("node:fs/promises");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { randomUUID } = require("node:crypto");

const PROJECT_ROOT = path.resolve(__dirname, "..");
const API_RUNS_DIR = path.join(PROJECT_ROOT, "output", "api-runs");
const MAX_BODY_BYTES = 64 * 1024;
const MAX_PROCESS_OUTPUT_BYTES = 64 * 1024;
const RUN_ID_PATTERN = /^pred_[a-zA-Z0-9_-]+_delhincr$/;

class ApiError extends Error {
  constructor(statusCode, code, message) {
    super(message);
    this.statusCode = statusCode;
    this.code = code;
  }
}

function sendJson(response, statusCode, value, headers = {}) {
  response.writeHead(statusCode, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
    ...headers,
  });
  response.end(JSON.stringify(value));
}

function sendError(response, error, headers = {}) {
  if (error instanceof ApiError) {
    sendJson(response, error.statusCode, {
      error: { code: error.code, message: error.message },
    }, headers);
    return;
  }

  console.error("Unhandled API error:", error);
  sendJson(response, 500, {
    error: { code: "INTERNAL_ERROR", message: "An unexpected server error occurred." },
  }, headers);
}

async function readJsonBody(request) {
  const contentType = request.headers["content-type"] || "";
  if (!contentType.toLowerCase().startsWith("application/json")) {
    throw new ApiError(415, "UNSUPPORTED_MEDIA_TYPE", "Send a JSON request body.");
  }

  const chunks = [];
  let size = 0;
  for await (const chunk of request) {
    size += chunk.length;
    if (size > MAX_BODY_BYTES) {
      throw new ApiError(413, "BODY_TOO_LARGE", "Request body exceeds 64 KiB.");
    }
    chunks.push(chunk);
  }

  if (size === 0) {
    return {};
  }

  try {
    const value = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    if (value === null || Array.isArray(value) || typeof value !== "object") {
      throw new Error("Expected a JSON object.");
    }
    return value;
  } catch {
    throw new ApiError(400, "INVALID_JSON", "Request body must be a valid JSON object.");
  }
}

function validateRunRequest(body) {
  const mode = body.mode === undefined ? "replay" : body.mode;
  const snapshotId = body.snapshot_id === undefined ? "sample" : body.snapshot_id;
  const grapStage = body.grap_stage === undefined ? 3 : body.grap_stage;

  if (mode !== "replay") {
    throw new ApiError(422, "UNSUPPORTED_MODE", "Only mode 'replay' is currently available.");
  }
  if (snapshotId !== "sample") {
    throw new ApiError(
      422,
      "UNKNOWN_SNAPSHOT",
      "Only snapshot_id 'sample' is available in this repository.",
    );
  }
  if (!Number.isInteger(grapStage) || grapStage < 1 || grapStage > 4) {
    throw new ApiError(422, "INVALID_GRAP_STAGE", "grap_stage must be an integer from 1 to 4.");
  }

  return { mode, snapshotId, grapStage };
}

function captureProcessOutput(stream, onData) {
  let capturedBytes = 0;
  stream.on("data", (chunk) => {
    if (capturedBytes < MAX_PROCESS_OUTPUT_BYTES) {
      const available = MAX_PROCESS_OUTPUT_BYTES - capturedBytes;
      onData(chunk.subarray(0, available).toString("utf8"));
      capturedBytes += Math.min(chunk.length, available);
    }
  });
}

async function runPythonReplay(grapStage) {
  const workingOutputDir = path.join(PROJECT_ROOT, "output", `.api-work-${randomUUID()}`);
  await fs.mkdir(workingOutputDir, { recursive: true });

  const pythonExecutable = process.env.PYTHON_EXECUTABLE || "python";
  const stdout = [];
  const stderr = [];
  try {
    await new Promise((resolve, reject) => {
      const child = spawn(pythonExecutable, [path.join(PROJECT_ROOT, "demo.py")], {
        cwd: PROJECT_ROOT,
        env: {
          ...process.env,
          PYTHONUTF8: "1",
          PYTHONIOENCODING: "utf-8",
          DHUANALERT_GRAP_STAGE: String(grapStage),
          DHUANALERT_OUTPUT_DIR: workingOutputDir,
        },
        windowsHide: true,
      });

      captureProcessOutput(child.stdout, (text) => stdout.push(text));
      captureProcessOutput(child.stderr, (text) => stderr.push(text));
      child.once("error", reject);
      child.once("close", (code) => {
        if (code === 0) {
          resolve();
        } else {
          const detail = stderr.join("").trim() || stdout.join("").trim();
          reject(new Error(`Python replay exited with code ${code}: ${detail}`));
        }
      });
    });

    const [payload, map, evaluation] = await Promise.all([
      readJsonFile(path.join(workingOutputDir, "frontend_payload.json")),
      readJsonFile(path.join(workingOutputDir, "map.geojson")),
      readJsonFile(path.join(workingOutputDir, "evaluation_report.json")),
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

async function readJsonFile(filePath) {
  return JSON.parse(await fs.readFile(filePath, "utf8"));
}

function validatePipelineResult(result) {
  if (
    !result ||
    !result.payload ||
    !result.payload.prediction ||
    !result.payload.advisory ||
    !result.map ||
    result.map.type !== "FeatureCollection" ||
    !result.evaluation
  ) {
    throw new ApiError(502, "INVALID_PIPELINE_OUTPUT", "Forecast engine returned an invalid payload.");
  }

  const runId = result.payload.prediction.prediction_id;
  if (typeof runId !== "string" || !RUN_ID_PATTERN.test(runId)) {
    throw new ApiError(502, "INVALID_PIPELINE_OUTPUT", "Forecast engine returned an invalid run ID.");
  }
  return runId;
}

async function persistRun(runsDir, result, grapStage) {
  const runId = validatePipelineResult(result);
  const runDirectory = path.join(runsDir, runId);
  const pendingDirectory = path.join(runsDir, `.pending-${randomUUID()}`);
  await fs.mkdir(pendingDirectory, { recursive: true });

  try {
    await Promise.all([
      fs.writeFile(path.join(pendingDirectory, "frontend_payload.json"), JSON.stringify(result.payload, null, 2)),
      fs.writeFile(path.join(pendingDirectory, "map.geojson"), JSON.stringify(result.map, null, 2)),
      fs.writeFile(path.join(pendingDirectory, "evaluation_report.json"), JSON.stringify(result.evaluation, null, 2)),
      fs.writeFile(path.join(pendingDirectory, "metadata.json"), JSON.stringify({
        run_id: runId,
        mode: "replay",
        snapshot_id: "sample",
        grap_stage: grapStage,
        generated_at: result.payload.prediction.generated_at,
      }, null, 2)),
    ]);
    await fs.rename(pendingDirectory, runDirectory);
  } catch (error) {
    await fs.rm(pendingDirectory, { recursive: true, force: true });
    if (error.code === "EEXIST" || error.code === "ENOTEMPTY") {
      throw new ApiError(409, "RUN_ALREADY_EXISTS", "A run with this ID already exists.");
    }
    throw error;
  }
  return runId;
}

async function listRuns(runsDir) {
  let entries;
  try {
    entries = await fs.readdir(runsDir, { withFileTypes: true });
  } catch (error) {
    if (error.code === "ENOENT") {
      return [];
    }
    throw error;
  }

  const runs = [];
  for (const entry of entries) {
    if (!entry.isDirectory() || !RUN_ID_PATTERN.test(entry.name)) {
      continue;
    }
    const metadata = await readJsonFile(path.join(runsDir, entry.name, "metadata.json"));
    const payload = await readJsonFile(path.join(runsDir, entry.name, "frontend_payload.json"));
    runs.push({
      run_id: metadata.run_id,
      generated_at: metadata.generated_at,
      valid_until: payload.prediction.valid_until,
      school_count: payload.prediction.schools.length,
      severity: payload.advisory.severity,
      mode: metadata.mode,
      snapshot_id: metadata.snapshot_id,
    });
  }
  runs.sort((a, b) => b.generated_at.localeCompare(a.generated_at));
  return runs;
}

async function findRunByAdvisoryId(runsDir, advisoryId) {
  const runs = await listRuns(runsDir);
  for (const run of runs) {
    const payload = await readJsonFile(
      path.join(runsDir, run.run_id, "frontend_payload.json"),
    );
    if (payload.advisory.advisory_id === advisoryId) {
      return run.run_id;
    }
  }
  return null;
}

function createServer(options = {}) {
  const runsDir = options.runsDir || API_RUNS_DIR;
  const runForecast = options.runForecast || runPythonReplay;
  const allowedOrigin = options.allowedOrigin || process.env.CORS_ORIGIN || "http://localhost:5173";

  return http.createServer(async (request, response) => {
    const origin = request.headers.origin;
    const corsHeaders = origin === allowedOrigin
      ? {
          "access-control-allow-origin": allowedOrigin,
          "access-control-allow-methods": "GET, POST, OPTIONS",
          "access-control-allow-headers": "content-type",
          vary: "Origin",
        }
      : {};

    if (request.method === "OPTIONS") {
      response.writeHead(204, corsHeaders);
      response.end();
      return;
    }

    try {
      const url = new URL(request.url, "http://localhost");
      const pathname = url.pathname;

      if (request.method === "GET" && pathname === "/health") {
        sendJson(response, 200, {
          status: "ok",
          service: "dhuanalert-api",
          pipeline: "python-replay",
        }, corsHeaders);
        return;
      }

      if (request.method === "GET" && pathname === "/v1/runs") {
        sendJson(response, 200, { runs: await listRuns(runsDir) }, corsHeaders);
        return;
      }

      if (request.method === "POST" && pathname === "/v1/runs") {
        const runRequest = validateRunRequest(await readJsonBody(request));
        let result;
        try {
          result = await runForecast(runRequest.grapStage);
        } catch (error) {
          console.error("Forecast pipeline failed:", error);
          throw new ApiError(502, "PIPELINE_FAILED", "Forecast pipeline failed; inspect server logs.");
        }
        const runId = await persistRun(runsDir, result, runRequest.grapStage);
        sendJson(response, 201, {
          run_id: runId,
          mode: runRequest.mode,
          snapshot_id: runRequest.snapshotId,
          links: {
            self: `/v1/runs/${runId}`,
            map: `/v1/runs/${runId}/map.geojson`,
            advisory: `/v1/advisories/${result.advisory.advisory_id}`,
          },
          payload: result.payload,
        }, corsHeaders);
        return;
      }

      const runMatch = pathname.match(/^\/v1\/runs\/([^/]+)(?:\/(map\.geojson))?$/);
      if (request.method === "GET" && runMatch) {
        const runId = decodeURIComponent(runMatch[1]);
        if (!RUN_ID_PATTERN.test(runId)) {
          throw new ApiError(404, "RUN_NOT_FOUND", "Run was not found.");
        }
        const baseDir = path.join(runsDir, runId);
        const fileName = runMatch[2] ? "map.geojson" : "frontend_payload.json";
        let value;
        try {
          value = await readJsonFile(path.join(baseDir, fileName));
        } catch (error) {
          if (error.code === "ENOENT") {
            throw new ApiError(404, "RUN_NOT_FOUND", "Run was not found.");
          }
          throw error;
        }
        sendJson(response, 200, value, corsHeaders);
        return;
      }

      const advisoryMatch = pathname.match(/^\/v1\/advisories\/([^/]+)$/);
      if (request.method === "GET" && advisoryMatch) {
        const advisoryId = decodeURIComponent(advisoryMatch[1]);
        const runId = await findRunByAdvisoryId(runsDir, advisoryId);
        if (!runId) {
          throw new ApiError(404, "ADVISORY_NOT_FOUND", "Advisory was not found.");
        }
        const payload = await readJsonFile(
          path.join(runsDir, runId, "frontend_payload.json"),
        );
        sendJson(response, 200, payload.advisory, corsHeaders);
        return;
      }

      if (request.method === "GET" && pathname === "/v1/evaluation") {
        const runs = await listRuns(runsDir);
        if (runs.length === 0) {
          throw new ApiError(404, "EVALUATION_NOT_FOUND", "No replay evaluation is available yet.");
        }
        const evaluation = await readJsonFile(
          path.join(runsDir, runs[0].run_id, "evaluation_report.json"),
        );
        sendJson(response, 200, evaluation, corsHeaders);
        return;
      }

      if (!["GET", "POST", "OPTIONS"].includes(request.method)) {
        sendJson(response, 405, {
          error: { code: "METHOD_NOT_ALLOWED", message: "This HTTP method is not supported." },
        }, { ...corsHeaders, allow: "GET, POST, OPTIONS" });
        return;
      }
      throw new ApiError(404, "NOT_FOUND", "Endpoint was not found.");
    } catch (error) {
      sendError(response, error, corsHeaders);
    }
  });
}

if (require.main === module) {
  const port = Number.parseInt(process.env.PORT || "3000", 10);
  const host = process.env.HOST || "127.0.0.1";
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    console.error("PORT must be an integer between 1 and 65535.");
    process.exitCode = 1;
  } else {
    const server = createServer();
    server.listen(port, host, () => {
      console.log(`DhuanAlert API listening at http://${host}:${port}`);
    });
  }
}

module.exports = { createServer, validateRunRequest };
