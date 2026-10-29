/* Synthetic DOM harness: tests the actual validation code, not browser rendering. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../../src/uk_data_mcp/web/app.js"), "utf8");
const parameters = ["effective_stress_friction_angle_deg", "undrained_shear_strength_kPa",
  "soil_stiffness_MPa", "permeability_m_per_s", "design_groundwater_level_mAOD",
  "allowable_bearing_pressure_kPa", "buried_utility_clearance_m"];
function fixture() {
  return {
    kind: "geotechnical_desk_study", schema_version: "1.0", status: "ok",
    generated_at_utc: "2026-10-29T00:00:00Z", project: { project_name: "Synthetic study" },
    site: { latitude: 52.45, longitude: -1.93, nation: "England", radius_km: 1 }, summary: {},
    evidence: [{ id: "q1", tool: "bgs_features", status: "ok", arguments: {},
      result: { status: "ok", data: [], warnings: [], provenance: [] } }],
    investigations: [{ id: "i1", review: { status: "unreviewed", notes: "" }, evidence_ids: ["q1"], links: [] }],
    gaps: [{ id: "g1", title: "Review", reason: "Synthetic", status: "open", notes: "", actions: [], evidence_ids: ["q1"] }],
    groundwater: [{ evidence_id: "q1", readings: [], warnings: [] }],
    design_parameters: Object.fromEntries(parameters.map(key => [key, { value: null }])),
    warnings: [], omitted_queries: [],
  };
}
function harness(reply) {
  const calls = [];
  const nodes = new Map();
  const document = {
    getElementById(id) {
      if (!nodes.has(id)) nodes.set(id, { addEventListener() {}, querySelectorAll() { return []; } });
      return nodes.get(id);
    },
    querySelectorAll() { return []; },
  };
  const window = { addEventListener() {} };
  const context = vm.createContext({ document, window, URL, console,
    fetch: async (url, options) => {
      calls.push({ url, options });
      return reply ? reply(url, options) : { ok: true, json: async () => JSON.parse(options.body) };
    },
  });
  vm.runInContext(source, context, { timeout: 1000 });
  return { api: window.Groundwork, calls };
}

test("loading the application does not fetch providers or a saved workspace", () => {
  const { api, calls } = harness();
  assert.equal(calls.length, 0);
  assert.equal(api.getReport(), null);
});
test("valid synthetic source and human notes are retained by preflight", () => {
  const { api } = harness();
  const report = fixture();
  report.investigations[0].review.notes = "Human review, not a source measurement";
  assert.equal(api.validateReport(report), report);
});
for (const [name, change] of [
  ["coordinates", r => { r.site.latitude = 999; }],
  ["outer/result disagreement", r => { r.evidence[0].result.status = "error"; }],
  ["error payload under success", r => { r.evidence[0].result.error = { message: "Failed" }; }],
  ["investigation reference", r => { r.investigations[0].evidence_ids = ["missing"]; }],
  ["gap reference", r => { r.gaps[0].evidence_ids = ["missing"]; }],
  ["groundwater reference", r => { r.groundwater[0].evidence_id = "missing"; }],
  ["non-finite measurement", r => { r.groundwater[0].readings = [{ value: Infinity }]; }],
]) {
  test(`preflight rejects invalid ${name}`, () => {
    const { api, calls } = harness();
    const report = fixture(); change(report);
    assert.throws(() => api.validateReport(report));
    assert.equal(calls.length, 0);
    assert.equal(api.getReport(), null);
  });
}
test("workspace validation uses the local authoritative endpoint and returned summary", async () => {
  const { api, calls } = harness((_url, options) => {
    const report = JSON.parse(options.body);
    report.summary = { query_count: 1, investigation_count: 1, open_gap_count: 1 };
    return { ok: true, json: async () => report };
  });
  const result = await api.validateWorkspace(fixture());
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "/api/validate-report");
  assert.equal(calls[0].options.method, "POST");
  assert.equal(result.summary.query_count, 1);
  assert.equal(api.getReport(), null); // validation alone cannot replace the active workspace
});
test("backend semantic rejection cannot install a workspace", async () => {
  const { api } = harness(() => ({ ok: false, status: 400, json: async () => ({ error: "Invalid timestamp" }) }));
  const report = fixture(); report.generated_at_utc = "not-a-date";
  await assert.rejects(api.validateWorkspace(report), /Invalid timestamp/);
  assert.equal(api.getReport(), null);
});
test("backend output is checked again before use", async () => {
  const { api } = harness(() => {
    const report = fixture(); report.evidence[0].result.status = "error";
    return { ok: true, json: async () => report };
  });
  await assert.rejects(api.validateWorkspace(fixture()));
  assert.equal(api.getReport(), null);
});
