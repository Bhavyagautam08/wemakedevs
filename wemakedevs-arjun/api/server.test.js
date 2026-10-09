"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const { after, before, test } = require("node:test");
const { createServer } = require("./server");

let server;
let baseUrl;
let runsDir;

const predictionId = "pred_20261009_193647123456_delhincr";
const advisoryId = `adv_20261009_${predictionId}`;
const payload = {
  prediction: {
    prediction_id: predictionId,
    generated_at: "2026-10-09T14:06:47.123456Z",
    valid_until: "2026-10-09T20:06:47.123456Z",
    schools: [{ school_id: "school-1" }],
  },
  advisory: {
    advisory_id: advisoryId,
    severity: "MODERATE",
    validation: { publication_status: "MANUAL_REVIEW_REQUIRED" },
  },
};
const evaluation = { evaluation_id: "eval-replay" };
const map = { type: "FeatureCollection", features: [] };

before(async () => {
  runsDir = await fs.mkdtemp(path.join(os.tmpdir(), "dhuanalert-api-test-"));
  server = createServer({
    runsDir,
    allowedOrigin: "http://localhost:5173",
    runForecast: async () => ({ payload, prediction: payload.prediction, advisory: payload.advisory, evaluation, map }),
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  baseUrl = `http://127.0.0.1:${server.address().port}`;
});

after(async () => {
  await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  await fs.rm(runsDir, { recursive: true, force: true });
});

test("health check reports the connected Python replay engine", async () => {
  const response = await fetch(`${baseUrl}/health`);
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), {
    status: "ok",
    service: "dhuanalert-api",
    pipeline: "python-replay",
  });
});

test("run endpoint persists and serves forecast, map, advisory, and evaluation", async () => {
  const createResponse = await fetch(`${baseUrl}/v1/runs`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ mode: "replay", snapshot_id: "sample", grap_stage: 3 }),
  });
  assert.equal(createResponse.status, 201);
  const created = await createResponse.json();
  assert.equal(created.run_id, predictionId);
  assert.deepEqual(created.payload, payload);

  const [runResponse, mapResponse, advisoryResponse, evaluationResponse, listResponse] = await Promise.all([
    fetch(`${baseUrl}/v1/runs/${predictionId}`),
    fetch(`${baseUrl}/v1/runs/${predictionId}/map.geojson`),
    fetch(`${baseUrl}/v1/advisories/${advisoryId}`),
    fetch(`${baseUrl}/v1/evaluation`),
    fetch(`${baseUrl}/v1/runs`),
  ]);
  assert.deepEqual(await runResponse.json(), payload);
  assert.deepEqual(await mapResponse.json(), map);
  assert.deepEqual(await advisoryResponse.json(), payload.advisory);
  assert.deepEqual(await evaluationResponse.json(), evaluation);
  assert.equal((await listResponse.json()).runs[0].run_id, predictionId);
});

test("run endpoint rejects unsupported snapshots and invalid stages", async () => {
  for (const body of [
    { snapshot_id: "not-available" },
    { grap_stage: 5 },
  ]) {
    const response = await fetch(`${baseUrl}/v1/runs`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    assert.equal(response.status, 422);
  }
});

test("unknown runs return a structured 404", async () => {
  const response = await fetch(`${baseUrl}/v1/runs/pred_missing_delhincr`);
  assert.equal(response.status, 404);
  assert.equal((await response.json()).error.code, "RUN_NOT_FOUND");
});

test("CORS only allows the configured frontend origin", async () => {
  const allowed = await fetch(`${baseUrl}/health`, { headers: { origin: "http://localhost:5173" } });
  const rejected = await fetch(`${baseUrl}/health`, { headers: { origin: "https://untrusted.example" } });
  assert.equal(allowed.headers.get("access-control-allow-origin"), "http://localhost:5173");
  assert.equal(rejected.headers.get("access-control-allow-origin"), null);
});
