/**
 * Endpoint smoke test: starts the API in-process and calls every route once.
 * Prints status, expected status, and a one-line summary of the body.
 * Usage (from backend/):  npx tsx scripts/smoke.ts
 * Exit code 1 if any route returns an unexpected status.
 */
import { createApp } from "../src/app";

type Check = { name: string; method?: string; path: string; body?: any; expect: number[]; summary?: (d: any) => string };

const server: any = createApp().listen(0, "127.0.0.1", async () => {
  const base = `http://127.0.0.1:${server.address().port}`;
  let failures = 0;

  const call = async (c: Check) => {
    const t = Date.now();
    const res = await fetch(`${base}${c.path}`, {
      method: c.method || "GET",
      headers: { "Content-Type": "application/json" },
      body: c.body ? JSON.stringify(c.body) : undefined,
    });
    const text = await res.text();
    let data: any = text;
    try {
      data = JSON.parse(text);
    } catch {}
    const ok = c.expect.includes(res.status);
    if (!ok) failures++;
    let info = "";
    try {
      info = c.summary && ok && res.status < 300 ? c.summary(data) : JSON.stringify(data).slice(0, 140);
    } catch (e: any) {
      info = `summary failed: ${e.message}`;
    }
    console.log(`${ok ? "PASS" : "FAIL"} ${res.status} (expect ${c.expect.join("/")}) ${c.method || "GET"} ${c.path} [${Date.now() - t}ms] ${info}`);
    return data;
  };

  await call({ name: "health", path: "/health", expect: [200], summary: (d) => d.status });
  await call({ name: "config", path: "/v1/config", expect: [200], summary: (d) => `horizons=${d.simulation.forecast_horizons} Ce=${d.simulation.smoke_emission_coefficient_kg_per_mj}` });
  await call({ name: "schools", path: "/v1/data/schools", expect: [200], summary: (d) => `${d.length} schools` });
  await call({ name: "fires", path: "/v1/data/fires", expect: [200], summary: (d) => `${d.length} live fires` });
  await call({ name: "weather", path: "/v1/data/weather", expect: [200], summary: (d) => `${d.length} live weather hours` });
  await call({
    name: "live",
    path: "/v1/data/live",
    expect: [200],
    summary: (d) => Object.entries(d.sources).map(([k, v]: any) => `${k}:${v.status}(${v.count})`).join(" "),
  });
  await call({ name: "grap", path: "/v1/policy/grap", expect: [200], summary: (d) => `${Object.keys(d.stages).length} stages` });
  await call({ name: "evaluation", path: "/v1/evaluation", expect: [404], summary: (d) => d.status });
  await call({ name: "evaluate-empty", method: "POST", path: "/v1/evaluation/evaluate", body: {}, expect: [400] });

  const runSummary = (d: any) => {
    const p = d.payload.prediction;
    const hs = p.simulation.horizon_states.map((h: any) => `+${h.horizon_hours}h@(${h.centroid_lat},${h.centroid_lon})`).join(" ");
    return `run_id=${d.run_id} clusters=${p.simulation.fire_cluster_count} E=${p.simulation.total_emission_rate_kg_s}kg/s ${hs}`;
  };
  const replay = await call({ name: "run-replay", method: "POST", path: "/v1/runs", body: { mode: "replay" }, expect: [201], summary: runSummary });
  await call({ name: "run-live", method: "POST", path: "/v1/runs", body: { mode: "live" }, expect: [201, 422, 502], summary: runSummary });
  await call({ name: "run-bad-mode", method: "POST", path: "/v1/runs", body: { mode: "nope" }, expect: [422] });

  const id = replay?.run_id;
  if (id) {
    await call({ name: "runs", path: "/v1/runs", expect: [200], summary: (d) => `${(d.runs || d).length} stored runs` });
    await call({ name: "run", path: `/v1/runs/${id}`, expect: [200], summary: () => "ok" });
    await call({ name: "prediction", path: `/v1/runs/${id}/prediction`, expect: [200], summary: (d) => d.prediction_id });
    await call({ name: "advisory", path: `/v1/runs/${id}/advisory`, expect: [200], summary: (d) => d.advisory_id });
    await call({ name: "map", path: `/v1/runs/${id}/map.geojson`, expect: [200], summary: (d) => `${d.features.length} features` });
    await call({ name: "timeline", path: `/v1/runs/${id}/timeline`, expect: [200], summary: (d) => `${(d.timeline || d).length} slices` });
    await call({ name: "timeline-6", path: `/v1/runs/${id}/timeline/6`, expect: [200], summary: (d) => `+6h centre (${d.plume_center_lat},${d.plume_center_lon})` });
    await call({ name: "schools", path: `/v1/runs/${id}/schools`, expect: [200], summary: (d) => `${(d.schools || d).length} schools` });
    await call({ name: "ensemble", path: `/v1/runs/${id}/ensemble`, expect: [200], summary: (d) => `${d.member_count} members` });
    await call({ name: "missing-run", path: `/v1/runs/run_does_not_exist`, expect: [404] });
    const adv = await call({ name: "advisories", path: "/v1/advisories", expect: [200], summary: (d) => `${(d.advisories || d).length} advisories` });
    const advId = replay.payload?.advisory?.advisory_id;
    if (advId) {
      await call({ name: "advisory-get", path: `/v1/advisories/${advId}`, expect: [200], summary: (d) => d.validation?.publication_status });
      await call({ name: "review", method: "POST", path: `/v1/advisories/${advId}/review`, body: { action: "REJECT", notes: "smoke test" }, expect: [200], summary: (d) => d.validation?.publication_status });
    }
    await call({ name: "advisory-generate", method: "POST", path: "/v1/advisories/generate", body: { prediction_id: id }, expect: [200, 201], summary: (d) => d.advisory_id || "ok" });
    void adv;
  }
  await call({ name: "simulate", method: "POST", path: "/v1/predict/simulate", body: {}, expect: [200, 201], summary: (d) => `${d.timeline.length} slices` });
  await call({
    name: "cedar",
    method: "POST",
    path: "/v1/policy/evaluate",
    body: { action_id: "discontinue_primary_physical_classes", risk_band: "HIGH", grap_stage: 3, human_approved: true },
    expect: [200],
    summary: (d) => d.decision,
  });
  await call({ name: "claims", method: "POST", path: "/v1/claims/validate", body: { text: "Smoke expected in 3 hours." }, expect: [200], summary: (d) => `valid=${d.is_valid}` });
  await call({ name: "aws", path: "/v1/aws/status", expect: [200], summary: (d) => JSON.stringify(d).slice(0, 80) });

  console.log(failures ? `\n${failures} route(s) FAILED` : "\nALL ROUTES OK");
  server.close();
  process.exitCode = failures ? 1 : 0;
});
