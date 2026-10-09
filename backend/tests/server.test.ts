import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { after, before, test } from "node:test";
import { createApp } from "../src/app";

let server: any;
let baseUrl: string;

const predictionId = "pred_20261009_193647123456_delhincr";
const advisoryId = `adv_20261009_${predictionId}`;

before(async () => {
  const app = createApp();
  await new Promise<void>((resolve) => {
    server = app.listen(0, "127.0.0.1", () => resolve());
  });
  baseUrl = `http://127.0.0.1:${server.address().port}`;
});

after(async () => {
  await new Promise<void>((resolve, reject) => {
    server.close((err: any) => (err ? reject(err) : resolve()));
  });
});

test("GET /health reports service status", async () => {
  const response = await fetch(`${baseUrl}/health`);
  assert.equal(response.status, 200);
  const data = (await response.json()) as any;
  assert.equal(data.status, "ok");
  assert.equal(data.service, "dhuanalert-api");
});

test("GET /v1/config returns system parameters", async () => {
  const response = await fetch(`${baseUrl}/v1/config`);
  assert.equal(response.status, 200);
  const data = (await response.json()) as any;
  assert.ok(data.simulation);
  assert.ok(data.risk_weights);
});

test("GET /v1/policy/grap serves statutory GRAP stages", async () => {
  const response = await fetch(`${baseUrl}/v1/policy/grap`);
  assert.equal(response.status, 200);
  const data = (await response.json()) as any;
  assert.ok(data.stages);
});

test("POST /v1/policy/evaluate evaluates Cedar authorization rules", async () => {
  const allowResp = await fetch(`${baseUrl}/v1/policy/evaluate`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      action_id: "discontinue_primary_physical_classes",
      risk_band: "HIGH",
      grap_stage: 3,
      human_approved: true,
    }),
  });
  assert.equal(allowResp.status, 200);
  assert.equal(((await allowResp.json()) as any).decision, "ALLOW");

  const denyResp = await fetch(`${baseUrl}/v1/policy/evaluate`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      action_id: "discontinue_primary_physical_classes",
      risk_band: "HIGH",
      grap_stage: 2,
      human_approved: true,
    }),
  });
  assert.equal(denyResp.status, 200);
  assert.equal(((await denyResp.json()) as any).decision, "DENY");
});

test("POST /v1/claims/validate classifies factual statements", async () => {
  const safeResp = await fetch(`${baseUrl}/v1/claims/validate`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      text: "Stubble smoke plume arrival projected in 3 hours under GRAP III.",
    }),
  });
  assert.equal(safeResp.status, 200);
  assert.equal(((await safeResp.json()) as any).is_valid, true);

  const unsafeResp = await fetch(`${baseUrl}/v1/claims/validate`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      text: "Section 144 curfew is declared immediately.",
    }),
  });
  assert.equal(unsafeResp.status, 200);
  assert.equal(((await unsafeResp.json()) as any).is_valid, false);
});

test("GET /v1/evaluation returns evaluation report", async () => {
  const response = await fetch(`${baseUrl}/v1/evaluation`);
  assert.equal(response.status, 200);
  const data = (await response.json()) as any;
  assert.equal(data.station_count, 4);
  assert.ok(data.spearman_rho >= 0.4);
});

test("GET /v1/data/* serves reference datasets", async () => {
  const [schools, fires, weather] = await Promise.all([
    fetch(`${baseUrl}/v1/data/schools`).then((r) => r.json() as Promise<any[]>),
    fetch(`${baseUrl}/v1/data/fires`).then((r) => r.json() as Promise<any[]>),
    fetch(`${baseUrl}/v1/data/weather`).then((r) => r.json() as Promise<any[]>),
  ]);
  assert.ok(schools.length > 0);
  assert.ok(fires.length > 0);
  assert.ok(weather.length > 0);
});
