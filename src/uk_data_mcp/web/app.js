"use strict";

(() => {
  const $ = (id) => document.getElementById(id);
  const tabs = ["overview", "investigations", "gaps", "sources"];
  const reviewStates = {
    unreviewed: "Unreviewed", relevant: "Relevant", not_relevant: "Not relevant",
    needs_review: "Needs further review",
  };
  const gapStates = { open: "Open", in_progress: "In progress", closed: "Closed" };
  const sourceStates = { ok: "Completed", partial: "Partial", empty: "Empty", error: "Error" };
  const developmentNames = {
    general: "General development", housing: "Housing", industrial: "Industrial / warehouse",
    solar_battery: "Solar / battery storage", basement: "Basement / excavation",
    corridor: "Road / utility corridor", brownfield: "Brownfield redevelopment",
  };
  let report = null;
  let activeTab = "overview";
  let busy = false;
  let dirty = false;

  function element(tag, className = "", text = null) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== null) node.textContent = String(text);
    return node;
  }
  function display(value, fallback = "Unknown") {
    if (value === null || value === undefined || value === "") return fallback;
    return typeof value === "object" ? JSON.stringify(value) : String(value);
  }
  function number(value, decimals = 0) {
    return typeof value === "number" && Number.isFinite(value)
      ? value.toLocaleString("en-GB", { maximumFractionDigits: decimals }) : "Unknown";
  }
  function safeURL(value) {
    if (typeof value !== "string" || value.length > 5000) return null;
    try {
      const url = new URL(value);
      return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password ? url.href : null;
    } catch (_) { return null; }
  }
  function externalLink(label, url) {
    const href = safeURL(url);
    if (!href) return element("span", "muted", label);
    const link = element("a", "", label);
    link.href = href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    return link;
  }
  function badge(status, label) {
    const known = Object.hasOwn(sourceStates, status) ? status : "empty";
    return element("span", `status-pill status-${known}`, label || sourceStates[known]);
  }
  function notify(message, style = "") {
    const node = $("notice");
    node.className = `notice ${style}`.trim();
    node.textContent = message;
    node.hidden = !message;
  }
  function dateText(value) {
    if (!value) return "Unknown date";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString("en-GB", {
      day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
      timeZone: "UTC",
    }) + " UTC";
  }
  function topicLabel(item) {
    if (typeof item.topic === "string" && item.topic) return item.topic.replaceAll("_", " ");
    return display(item.result?.source?.name, item.tool || "Source query");
  }
  function metadataItem(list, label, value, isNode = false) {
    list.append(element("dt", "", label));
    const dd = element("dd");
    if (isNode) dd.append(value); else dd.textContent = display(value);
    list.append(dd);
  }
  function jsonDetails(label, data) {
    const details = element("details", "raw-details");
    details.append(element("summary", "", label));
    const raw = JSON.stringify(data ?? null, null, 2);
    details.append(element("pre", "", raw.length > 120000
      ? raw.slice(0, 120000) + "\n… Display shortened. Save study JSON for the full evidence."
      : raw));
    return details;
  }
  function citations(ids, parent) {
    if (!Array.isArray(ids)) return;
    for (const id of ids) {
      const evidence = report?.evidence.find((item) => item.id === id);
      if (!evidence) continue;
      const button = element("button", "source-ref", `${id} ↗`);
      button.type = "button";
      button.title = `Inspect ${topicLabel(evidence)}`;
      button.addEventListener("click", () => {
        if ($("record-dialog").open) $("record-dialog").close();
        showTab("sources");
        const card = document.getElementById(`source-${id}`);
        if (card) { card.open = true; card.scrollIntoView({ block: "start", behavior: "smooth" }); }
      });
      parent.append(button);
    }
  }
  function checkReport(value) {
    const isObject = (item) => item !== null && typeof item === "object" && !Array.isArray(item);
    const mapping = (item, path) => {
      if (!isObject(item)) throw new Error(`${path} must be an object.`);
    };
    const records = (items, path, maximum = 2000) => {
      if (!Array.isArray(items) || items.length > maximum || items.some((item) => !isObject(item))) {
        throw new Error(`${path} must be a bounded array of objects.`);
      }
    };
    const strings = (items, path) => {
      if (!Array.isArray(items) || items.length > 10000 || items.some((item) => typeof item !== "string")) {
        throw new Error(`${path} must be an array of strings.`);
      }
    };
    // Validate all nested source data before changing the active workspace. Depth
    // and node budgets also keep arbitrary saved JSON safe to inspect as text.
    const pending = [[value, 0]];
    const seen = new Set();
    let visited = 0;
    while (pending.length) {
      const [item, depth] = pending.pop();
      visited += 1;
      if (depth > 64 || visited > 500000) throw new Error("The study JSON is too deeply nested or complex.");
      if (item === null || typeof item === "string" || typeof item === "boolean") continue;
      if (typeof item === "number" && Number.isFinite(item)) continue;
      if (typeof item !== "object" || seen.has(item)) throw new Error("The study must contain finite JSON data.");
      seen.add(item);
      for (const child of Object.values(item)) pending.push([child, depth + 1]);
    }
    if (!value || typeof value !== "object" || Array.isArray(value)
      || value.kind !== "geotechnical_desk_study" || value.schema_version !== "1.0") {
      throw new Error("Choose a Groundwork study JSON file with schema version 1.0.");
    }
    mapping(value.project, "project");
    mapping(value.site, "site");
    mapping(value.summary, "summary");
    if (typeof value.generated_at_utc !== "string" || typeof value.project.project_name !== "string"
      || value.project.project_name.length > 120) throw new Error("The study has an invalid project name or assembly date.");
    if (value.project.development_type !== undefined && !Object.hasOwn(developmentNames, value.project.development_type)) {
      throw new Error("The study has an unsupported development type.");
    }
    if (value.project.works_description !== undefined && typeof value.project.works_description !== "string") {
      throw new Error("Proposed works must be text.");
    }
    if (!["ok", "partial", "error"].includes(value.status)
      || !Number.isFinite(value.site.latitude) || !Number.isFinite(value.site.longitude)
      || value.site.latitude < 49 || value.site.latitude > 61.5
      || value.site.longitude < -9.5 || value.site.longitude > 2.5
      || !Number.isFinite(value.site.radius_km) || value.site.radius_km < 0.1 || value.site.radius_km > 20
      || !["England", "Scotland", "Wales", "Northern Ireland"].includes(value.site.nation)) {
      throw new Error("The study has invalid site coordinates, nation or execution status.");
    }
    for (const key of ["evidence", "investigations", "gaps", "groundwater"]) {
      records(value[key], key);
    }
    const evidenceIDs = new Set();
    for (const [index, item] of value.evidence.entries()) {
      const path = `evidence[${index}]`;
      if (typeof item.id !== "string" || item.id.length > 200 || evidenceIDs.has(item.id)
        || !Object.hasOwn(sourceStates, item.status)) throw new Error("Invalid source evidence in study.");
      evidenceIDs.add(item.id);
      mapping(item.result, `${path}.result`);
      mapping(item.arguments || {}, `${path}.arguments`);
      const result = item.result;
      if (result.status !== item.status || (result.error && item.status !== "error")) {
        throw new Error(`Evidence ${item.id} has inconsistent query and result statuses.`);
      }
      for (const key of ["source", "query", "pagination", "metadata", "error"]) {
        if (result[key] !== undefined && result[key] !== null) mapping(result[key], `${path}.result.${key}`);
      }
      if (result.source?.licence !== undefined && result.source.licence !== null) {
        mapping(result.source.licence, `${path}.result.source.licence`);
      }
      if (result.source?.limitations !== undefined) strings(result.source.limitations, `${path}.result.source.limitations`);
      records(result.provenance === undefined ? [] : result.provenance, `${path}.result.provenance`, 10000);
      strings(result.warnings === undefined ? [] : result.warnings, `${path}.result.warnings`);
      if (result.data !== undefined) {
        if (Array.isArray(result.data)) {
          records(result.data, `${path}.result.data`, 10000);
          for (const record of result.data) {
            if (record.properties !== undefined && record.properties !== null) mapping(record.properties, `${path}.result.data.properties`);
          }
        } else mapping(result.data, `${path}.result.data`);
      }
      if (result.metadata?.measure !== undefined && result.metadata.measure !== null) {
        mapping(result.metadata.measure, `${path}.result.metadata.measure`);
      }
    }
    const recordIDs = new Set();
    for (const item of value.investigations) {
      if (typeof item.id !== "string" || item.id.length > 300 || recordIDs.has(item.id)
        || !isObject(item.review)
        || !Object.hasOwn(reviewStates, item.review.status) || typeof item.review.notes !== "string"
        || item.review.notes.length > 20000) throw new Error("Invalid investigation review in study.");
      strings(item.evidence_ids, "investigation.evidence_ids");
      if (item.evidence_ids.some((id) => !evidenceIDs.has(id))) throw new Error("Investigation references missing evidence.");
      records(item.links, "investigation.links");
      recordIDs.add(item.id);
    }
    const gapIDs = new Set();
    for (const item of value.gaps) {
      if (typeof item.id !== "string" || item.id.length > 200 || gapIDs.has(item.id)
        || typeof item.title !== "string" || typeof item.reason !== "string"
        || !Object.hasOwn(gapStates, item.status) || typeof item.notes !== "string"
        || item.notes.length > 20000) throw new Error("Invalid GI gap task in study.");
      strings(item.actions, "gap.actions");
      strings(item.evidence_ids, "gap.evidence_ids");
      if (item.evidence_ids.some((id) => !evidenceIDs.has(id))) throw new Error("GI task references missing evidence.");
      gapIDs.add(item.id);
    }
    for (const item of value.groundwater) {
      if (!evidenceIDs.has(item.evidence_id)) throw new Error("Groundwater record references missing evidence.");
      if (item.measure !== undefined && item.measure !== null) mapping(item.measure, "groundwater.measure");
      records(item.readings === undefined ? [] : item.readings, "groundwater.readings", 10000);
      strings(item.warnings === undefined ? [] : item.warnings, "groundwater.warnings");
    }
    const designKeys = ["effective_stress_friction_angle_deg", "undrained_shear_strength_kPa", "soil_stiffness_MPa",
      "permeability_m_per_s", "design_groundwater_level_mAOD", "allowable_bearing_pressure_kPa", "buried_utility_clearance_m"];
    mapping(value.design_parameters, "design_parameters");
    if (designKeys.some((key) => !Object.hasOwn(value.design_parameters, key))
      || Object.values(value.design_parameters).some((item) => !isObject(item) || item.value !== null)) {
      throw new Error("Design parameters must remain unknown in this evidence workflow.");
    }
    strings(value.warnings, "warnings");
    strings(value.omitted_queries, "omitted_queries");
    if (value.workspace !== undefined && value.workspace !== null) mapping(value.workspace, "workspace");
    return value;
  }
  function markDirty() {
    dirty = true;
    $("unsaved-indicator").hidden = false;
    report.summary.open_gap_count = report.gaps.filter((gap) => gap.status !== "closed").length;
    report.workspace = { ...(report.workspace || {}), review_updated_at: new Date().toISOString() };
    renderMetrics();
    renderPriorities();
    updateNavigationCounts();
  }
  function updateNavigationCounts() {
    $("nav-records").textContent = report ? String(report.investigations.length) : "—";
    $("nav-gaps").textContent = report ? String(report.gaps.filter((gap) => gap.status !== "closed").length) : "—";
  }
  function showTab(tab) {
    if (!tabs.includes(tab)) return;
    activeTab = tab;
    for (const name of tabs) $("tab-" + name).hidden = name !== tab;
    document.querySelectorAll(".nav-item").forEach((button) => {
      const active = button.dataset.tab === tab;
      button.classList.toggle("active", active);
      if (active) button.setAttribute("aria-current", "page"); else button.removeAttribute("aria-current");
    });
    if (report) {
      if (tab === "investigations") renderCandidates();
      if (tab === "gaps") renderGaps();
    }
  }
  function populateForm() {
    const form = $("study-form");
    const inputs = { ...report.site, ...report.project };
    for (const key of ["project_name", "development_type", "works_description", "latitude", "longitude", "nation", "radius_km"]) {
      const input = form.elements.namedItem(key);
      if (input && inputs[key] !== undefined && inputs[key] !== null) input.value = inputs[key];
    }
  }
  async function validateWorkspace(value) {
    // The local Python validator is authoritative for imports and exports.
    // It recomputes summary counts, without provider calls or persistent storage.
    checkReport(value);
    const response = await fetch("/api/validate-report", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(value),
    });
    return checkReport(await responseJSON(response));
  }
  async function setReport(value, { demo = false, imported = false } = {}) {
    const validated = await validateWorkspace(value);
    report = validated;
    report.workspace = { ...(report.workspace || {}), demo: demo || Boolean(report.demo) || Boolean(imported && report.workspace?.demo) };
    dirty = false;
    $("unsaved-indicator").hidden = true;
    $("empty-state").hidden = true;
    $("workspace").hidden = false;
    $("study-toolbar").hidden = false;
    $("site-panel").open = false;
    const name = display(report.project.project_name, "Untitled project");
    $("page-title").textContent = name;
    $("breadcrumb-study").textContent = name.toUpperCase();
    $("page-description").textContent = `${display(developmentNames[report.project.development_type], "Development study")} · ${report.site.nation} · ${number(report.site.radius_km, 1)} km search area`;
    $("site-summary").textContent = `${number(report.site.latitude, 5)}, ${number(report.site.longitude, 5)} · ${report.site.nation} · ${number(report.site.radius_km, 1)} km`;
    $("study-timestamp").textContent = `Study assembled ${dateText(report.generated_at_utc)}`;
    const statusNode = $("query-status");
    statusNode.className = `status-pill status-${report.status}`;
    statusNode.textContent = report.status === "ok" ? "Queries completed" : report.status === "error" ? "Evidence unavailable" : "Partial evidence";
    $("demo-banner").hidden = !report.workspace.demo;
    $("demo-description").textContent = `Saved evidence assembled ${dateText(report.generated_at_utc)}. Source observations may be older. No fresh provider requests were made to load this demo.`;
    populateForm();
    renderMetrics();
    renderCoverage();
    renderPriorities();
    renderContext();
    renderCandidates();
    renderGaps();
    renderSources();
    renderLimitations();
    updateNavigationCounts();
    showTab("overview");
    notify(imported ? "Saved study opened. Review edits stay in this browser session until you save another JSON file."
      : demo ? "Dated Birmingham demonstration loaded. Inspect the saved sources and try the review workflow."
      : "Study assembled. Review failed and bounded queries, then assess the historic records and GI tasks.");
  }
  function renderMetrics() {
    if (!report) return;
    const metrics = $("metrics");
    metrics.replaceChildren();
    const failed = report.evidence.filter((item) => item.status === "error").length;
    const partial = report.evidence.filter((item) => item.status === "partial").length;
    const reviewed = report.investigations.filter((item) => item.review.status !== "unreviewed").length;
    const open = report.gaps.filter((item) => item.status !== "closed").length;
    const values = [
      ["Historic record candidates", report.investigations.length, `${reviewed} reviewed · relevance by you`, false],
      ["Source queries", report.evidence.length, `${failed} failed · ${partial} partial`, failed > 0],
      ["GI review tasks open", open, `${report.gaps.length} tasks in this register`, open > 0],
      ["Design values established", 0, "Additional investigation required", false],
    ];
    for (const [label, value, detail, attention] of values) {
      const card = element("div", `metric${attention ? " attention" : ""}`);
      card.append(element("div", "metric-label", label), element("div", "metric-value", number(value)), element("small", "", detail));
      metrics.append(card);
    }
  }
  function renderCoverage() {
    const container = $("coverage-list");
    container.replaceChildren();
    const groups = new Map();
    for (const item of report.evidence) {
      const key = item.result?.source_id || item.result?.source?.id || item.tool;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(item);
    }
    for (const items of groups.values()) {
      const first = items[0];
      const hasError = items.some((item) => item.status === "error");
      const status = hasError ? "error" : items.some((item) => item.status === "partial") ? "partial"
        : items.every((item) => item.status === "empty") ? "empty" : "ok";
      const row = element("div", "coverage-row");
      const description = element("div");
      description.append(element("strong", "", display(first.result?.source?.name, topicLabel(first))),
        element("small", "", `${items.length} ${items.length === 1 ? "query" : "queries"} · ${items.reduce((total, item) => total + (Array.isArray(item.result?.data) ? item.result.data.length : 0), 0)} records across returned pages`));
      row.append(description, badge(status));
      container.append(row);
    }
    if (!groups.size) container.append(element("div", "empty-inline", "No source queries are recorded in this study."));
  }
  function renderPriorities() {
    const container = $("priority-list");
    container.replaceChildren();
    const priorities = [...report.gaps].filter((item) => item.status !== "closed")
      .sort((a, b) => (a.priority === "high" ? 0 : 1) - (b.priority === "high" ? 0 : 1)).slice(0, 4);
    priorities.forEach((item, index) => {
      const row = element("div", "priority-item");
      const description = element("div");
      description.append(element("strong", "", item.title), element("p", "", item.reason));
      row.append(element("span", "priority-marker", String(index + 1).padStart(2, "0")), description);
      container.append(row);
    });
    if (!priorities.length) container.append(element("div", "empty-inline", "All review tasks are marked closed. This records workflow progress; design evidence still needs professional assessment."));
  }
  function renderContext() {
    const geology = $("geology-context");
    geology.replaceChildren();
    const mapped = report.evidence.filter((item) => ["bgsgeology625kbedrock", "bgsgeology625ksuperficial"].includes(item.arguments?.collection));
    for (const item of mapped) {
      const block = element("div", "geology-item");
      block.append(element("h3", "", item.arguments.collection.includes("superficial") ? "Superficial deposits" : "Bedrock"));
      if (item.status === "error") block.append(element("p", "", "Source query failed. Regional geological context remains a data gap."));
      else {
        const names = [...new Set((Array.isArray(item.result?.data) ? item.result.data : []).map((record) => {
          const p = record.properties || {};
          return [p.lex_d || p.name || p.lex_rcs, p.rcs_d].filter(Boolean).join(" — ");
        }).filter(Boolean))];
        block.append(element("p", "", names.length ? names.join("; ") : "No mapped records returned by this bounded query. This does not establish absence."));
      }
      citations([item.id], block);
      geology.append(block);
    }
    if (!mapped.length) geology.append(element("p", "", "No regional geological queries are available. See the source register and GI gaps."));
    const groundwater = $("groundwater-context");
    groundwater.replaceChildren();
    const acceptedReadings = new Set(report.groundwater.map((item) => item.evidence_id));
    const observed = report.evidence.filter((item) => item.tool === "hydrology_readings"
      && acceptedReadings.has(item.id) && item.groundwater_validation?.status !== "rejected");
    for (const item of observed) {
      const block = element("div", "groundwater-item");
      const measure = item.result?.metadata?.measure || {};
      block.append(element("strong", "", display(measure.label || measure.notation || item.arguments?.measure_id, "Groundwater series")));
      if (item.status === "error") block.append(element("p", "", "Reading request failed. No water level inferred."));
      else {
        const readings = Array.isArray(item.result?.data) ? item.result.data : [];
        const row = readings[0];
        if (row) {
          const unit = measure.unitName || measure.unit?.label || measure.unit?.notation || row.unitName;
          block.append(element("p", "", `Latest value: ${display(row.value)}${unit ? " " + display(unit) : " (unit in source metadata)"}`),
            element("div", "muted", `Observed: ${display(row.dateTime || row.date)} · Quality: ${display(row.quality)}`));
        } else block.append(element("p", "", "No reading returned by this query."));
      }
      citations([item.id], block);
      groundwater.append(block);
    }
    if (!observed.length) groundwater.append(element("p", "", "No groundwater reading follow-up is available. Station discovery and monitoring gaps remain in the source and GI registers."));
  }
  function renderLimitations() {
    const list = $("limitations-list");
    list.replaceChildren();
    const items = [...new Set([...report.warnings, ...report.omitted_queries].map((item) => display(item)))];
    for (const item of items) list.append(element("li", "", item));
  }
  function renderCandidates() {
    if (!report) return;
    const search = $("candidate-search").value.toLocaleLowerCase().trim();
    const collection = $("candidate-collection").value;
    const review = $("candidate-review").value;
    const records = report.investigations.filter((item) => {
      const match = `${display(item.reference, "")} ${display(item.name, "")} ${item.id}`.toLocaleLowerCase().includes(search);
      return match && (collection === "all" || item.collection === collection) && (review === "all" || item.review.status === review);
    });
    $("candidate-results").textContent = `${records.length} of ${report.investigations.length} candidates shown. Human relevance review is recorded separately from source evidence.`;
    const body = $("candidate-body");
    body.replaceChildren();
    if (!records.length) {
      const row = element("tr");
      const cell = element("td", "empty-inline", report.investigations.length ? "No candidates match these filters."
        : "No historic record candidates are available in this bounded retrieval. Check failed sources, search limits and the GI gaps before drawing conclusions.");
      cell.colSpan = 7;
      row.append(cell);
      body.append(row);
      return;
    }
    for (const item of records) {
      const row = element("tr");
      const identity = element("td");
      const open = element("button", "record-button", display(item.reference, item.id));
      open.type = "button";
      open.addEventListener("click", () => openCandidate(item));
      identity.append(open, element("span", "record-name", display(item.name, "Unnamed record")));
      const index = element("td");
      index.append(element("span", "index-badge", item.collection === "agsboreholeindex" ? "AGS" : item.collection === "onshoreboreholeindex" ? "SOBI" : display(item.collection)));
      const depth = element("td", "", typeof item.depth_m === "number" ? `${number(item.depth_m, 2)} m` : "Unknown");
      const year = element("td", "", display(item.year));
      const distance = element("td", "", typeof item.distance_m === "number" ? `${number(item.distance_m)} m${item.within_radius === false ? " · beyond radius" : ""}` : "Unknown");
      const status = element("td");
      status.append(element("span", `review-state ${item.review.status}`, reviewStates[item.review.status]));
      const action = element("td");
      const reviewButton = element("button", "text-button", "Review ↗");
      reviewButton.type = "button";
      reviewButton.setAttribute("aria-label", `Review ${display(item.reference, item.id)}`);
      reviewButton.addEventListener("click", () => openCandidate(item));
      action.append(reviewButton);
      row.append(identity, index, depth, year, distance, status, action);
      body.append(row);
    }
  }
  function makeSelect(values, current, id) {
    const select = element("select");
    if (id) select.id = id;
    for (const [value, label] of Object.entries(values)) {
      const option = element("option", "", label);
      option.value = value;
      option.selected = value === current;
      select.append(option);
    }
    return select;
  }
  function openCandidate(item) {
    $("record-title").textContent = display(item.reference, item.id);
    const content = $("record-details");
    content.replaceChildren();
    const metadata = element("dl", "metadata-grid");
    metadataItem(metadata, "Record name", item.name);
    metadataItem(metadata, "Source index", item.collection === "agsboreholeindex" ? "AGS borehole index" : "Single Onshore Borehole Index");
    metadataItem(metadata, "Recorded depth", typeof item.depth_m === "number" ? `${number(item.depth_m, 2)} m` : null);
    metadataItem(metadata, "Record year", item.year);
    metadataItem(metadata, "Record updated", item.updated_at);
    metadataItem(metadata, "Position precision", item.position_precision);
    metadataItem(metadata, "WGS84 position", typeof item.latitude === "number" && typeof item.longitude === "number" ? `${number(item.latitude, 6)}, ${number(item.longitude, 6)}` : null);
    metadataItem(metadata, "Distance from study point", typeof item.distance_m === "number" ? `${number(item.distance_m)} m (approximate)${item.within_radius === false ? "; beyond requested radius" : ""}` : null);
    content.append(metadata);
    const links = element("div", "record-links");
    for (const link of item.links) {
      if (safeURL(link.url)) links.append(externalLink(display(link.label, "Open provider record") + " ↗", link.url));
    }
    content.append(links);
    const refs = element("div");
    citations(item.evidence_ids, refs);
    content.append(refs, element("div", "record-caution", "This is an index candidate. Inspect the original log, its rights, date, location precision, depth and relevance to the proposed works. A nearby record does not establish conditions at the study point."));
    const review = element("section", "review-form");
    review.append(element("h3", "", "Your relevance review"), element("p", "", "Record an engineering review decision after checking the source. This does not change the retrieved evidence."));
    const statusLabel = element("label", "", "Review status");
    const select = makeSelect(reviewStates, item.review.status, "record-review-status");
    statusLabel.append(select);
    const notesLabel = element("label", "", "Review notes");
    const notes = element("textarea");
    notes.id = "record-review-notes";
    notes.rows = 4;
    notes.maxLength = 20000;
    notes.value = item.review.notes;
    notes.placeholder = "Record relevance, log limitations, strata questions, and any follow-up needed.";
    notesLabel.append(notes);
    select.addEventListener("change", () => { item.review.status = select.value; markDirty(); renderCandidates(); });
    notes.addEventListener("input", () => { item.review.notes = notes.value; markDirty(); });
    review.append(statusLabel, notesLabel, element("p", "human-edit-note", "Your notes stay in memory. Save study JSON to keep them and include them in exports."));
    content.append(review);
    $("record-dialog").showModal();
  }
  function renderGaps() {
    if (!report) return;
    const filter = $("gap-filter").value;
    const gaps = report.gaps.filter((item) => filter === "all" || item.status === filter);
    $("gap-results").textContent = `${gaps.length} of ${report.gaps.length} tasks shown`;
    const container = $("gap-list");
    container.replaceChildren();
    if (!gaps.length) { container.append(element("div", "empty-inline", "No review tasks match this filter.")); return; }
    for (const item of gaps) {
      const card = element("article", `gap-card${item.status === "closed" ? " closed" : ""}`);
      const top = element("div", "gap-card-top");
      const text = element("div");
      const tags = element("div", "gap-tags");
      tags.append(element("span", `priority-badge ${item.priority === "medium" ? "medium" : ""}`, item.priority === "medium" ? "Review" : "Priority"), element("span", "gap-id", item.id));
      text.append(tags, element("h3", "", item.title), element("p", "", item.reason));
      const stateLabel = element("label", "gap-state-label", "Review task status");
      const select = makeSelect(gapStates, item.status);
      select.setAttribute("aria-label", `Task status for ${item.title}`);
      stateLabel.append(select);
      top.append(text, stateLabel);
      card.append(top);
      const actions = element("ul", "gap-actions");
      for (const action of item.actions) actions.append(element("li", "", display(action)));
      card.append(actions);
      const refs = element("div");
      citations(item.evidence_ids, refs);
      card.append(refs);
      const detail = element("details");
      detail.open = Boolean(item.notes);
      detail.append(element("summary", "", "Review notes and follow-up"));
      const label = element("label", "sr-only", `Review notes for ${item.title}`);
      const notes = element("textarea");
      notes.rows = 2;
      notes.maxLength = 20000;
      notes.value = item.notes;
      notes.placeholder = "Record evidence obtained, review decisions, and outstanding actions.";
      notes.setAttribute("aria-label", `Review notes for ${item.title}`);
      notes.addEventListener("input", () => { item.notes = notes.value; markDirty(); });
      select.addEventListener("change", () => {
        item.status = select.value;
        card.classList.toggle("closed", item.status === "closed");
        markDirty();
        $("gap-results").textContent = `${report.gaps.filter((gap) => filter === "all" || gap.status === filter).length} of ${report.gaps.length} tasks match the selected filter`;
        if (filter !== "all") renderGaps();
      });
      detail.append(label, notes);
      card.append(detail);
      container.append(card);
    }
  }
  function renderSources() {
    const container = $("source-list");
    container.replaceChildren();
    for (const item of report.evidence) {
      const result = item.result || {};
      const source = result.source || {};
      const card = element("details", "source-card");
      card.id = `source-${item.id}`;
      const summary = element("summary");
      const title = element("div", "source-title");
      title.append(element("strong", "", topicLabel(item)), element("small", "", `${item.id} · ${display(source.provider, source.name || item.tool)} · ${display(item.tool)}`));
      const count = Array.isArray(result.data) ? result.data.length : result.pagination?.returned;
      summary.append(title, element("span", "source-count", `${number(count)} records`), badge(item.status), element("span", "summary-chevron", "⌄"));
      card.append(summary);
      const detail = element("div", "source-detail");
      const metadata = element("dl", "metadata-grid");
      metadataItem(metadata, "Retrieved", dateText(result.retrieved_at_utc || result.provenance?.at(-1)?.retrieved_at_utc));
      metadataItem(metadata, "Coverage", source.coverage);
      metadataItem(metadata, "Attribution", source.attribution);
      if (source.licence?.url) metadataItem(metadata, "Licence", externalLink(display(source.licence.name, "Provider terms"), source.licence.url), true);
      else metadataItem(metadata, "Licence", source.licence?.name || source.licence || "Unknown; review provider terms");
      metadataItem(metadata, "Licence scope", source.licence?.scope);
      metadataItem(metadata, "Pagination", result.pagination);
      if (source.documentation_url) metadataItem(metadata, "Provider documentation", externalLink("Read official source documentation ↗", source.documentation_url), true);
      for (const [index, provenance] of (Array.isArray(result.provenance) ? result.provenance : []).entries()) {
        metadataItem(metadata, `Request ${index + 1}`, externalLink(provenance.url || "Unknown URL", provenance.url), true);
        metadataItem(metadata, "Response timestamp", provenance.retrieved_at_utc);
        metadataItem(metadata, "SHA-256", provenance.response_sha256);
        metadataItem(metadata, "HTTP status", provenance.http_status);
      }
      detail.append(metadata);
      if (result.error) detail.append(element("div", "error-message", `${display(result.error.code, "Error")}: ${display(result.error.message, "Provider data unavailable.")}`));
      const warnings = [...new Set([...(Array.isArray(result.warnings) ? result.warnings : []), ...(Array.isArray(source.limitations) ? source.limitations : [])].map((warning) => display(warning)))];
      if (warnings.length) {
        const box = element("div", "source-warnings");
        const list = element("ul");
        for (const warning of warnings) list.append(element("li", "", warning));
        box.append(list);
        detail.append(box);
      }
      detail.append(jsonDetails("Query arguments", item.arguments || result.query), jsonDetails("Observation, units, datum and quality metadata", result.metadata), jsonDetails("Returned source records", result.data));
      card.append(detail);
      container.append(card);
    }
    if (!report.evidence.length) container.append(element("div", "empty-inline", "No query evidence was retained in this study."));
  }
  function filename(suffix) {
    const title = display(report?.project?.project_name, "groundwork-study").toLowerCase()
      .replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 70) || "groundwork-study";
    return `${title}-${suffix}`;
  }
  function download(data, name, type) {
    const blob = data instanceof Blob ? data : new Blob([data], { type });
    const url = URL.createObjectURL(blob);
    const link = element("a");
    link.href = url;
    link.download = name;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
  }
  function csvCell(value) {
    let text = value === null || value === undefined ? "" : String(value);
    if (!(typeof value === "number" && Number.isFinite(value)) && /^[\s]*[=+\-@\t\r]/.test(text)) text = "'" + text;
    return '"' + text.replaceAll('"', '""') + '"';
  }
  function csv(rows) { return "\uFEFF" + rows.map((row) => row.map(csvCell).join(",")).join("\r\n") + "\r\n"; }
  function exportCandidates() {
    if (!report) return;
    const rows = [["id", "index", "reference", "name", "depth_m", "year", "updated_at", "position_precision", "latitude", "longitude", "distance_m", "within_radius", "review_status", "review_notes", "evidence_ids", "source_links"]];
    for (const item of report.investigations) rows.push([item.id, item.collection, item.reference, item.name, item.depth_m, item.year, item.updated_at, item.position_precision, item.latitude, item.longitude, item.distance_m, item.within_radius, item.review.status, item.review.notes, item.evidence_ids.join("; "), item.links.filter((link) => safeURL(link.url)).map((link) => link.url).join("; ")]);
    download(csv(rows), filename("investigations.csv"), "text/csv;charset=utf-8");
  }
  function exportGaps() {
    if (!report) return;
    const rows = [["id", "priority", "topic", "title", "reason", "actions", "status", "review_notes", "evidence_ids"]];
    for (const item of report.gaps) rows.push([item.id, item.priority, item.topic, item.title, item.reason, item.actions.join("; "), item.status, item.notes, item.evidence_ids.join("; ")]);
    download(csv(rows), filename("gi-gaps.csv"), "text/csv;charset=utf-8");
  }
  function setBusy(value) {
    busy = value;
    for (const node of $("study-form").querySelectorAll("input,select,textarea,button")) node.disabled = value;
    $("load-demo").disabled = value;
    $("open-workspace").disabled = value;
    $("run-label").textContent = value ? "Gathering evidence…" : "Gather site evidence";
    $("run-icon").textContent = value ? "◌" : "→";
  }
  async function responseJSON(response) {
    let data;
    try { data = await response.json(); } catch (_) { throw new Error("The local service returned an unreadable response. Check that the Groundwork app is running."); }
    if (!response.ok) {
      const message = typeof data.error === "string" ? data.error : data.error?.message || data.detail || data.message;
      throw new Error(display(message, `The local service returned HTTP ${response.status}.`));
    }
    return data;
  }
  async function confirmReplace() {
    if (!dirty) return true;
    return window.confirm("This will replace your current study and its unsaved review notes. Save study JSON first if you want to keep them. Continue?");
  }
  $("study-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (busy || !$("study-form").reportValidity() || !await confirmReplace()) return;
    const data = new FormData($("study-form"));
    const args = Object.fromEntries(data.entries());
    for (const key of ["latitude", "longitude", "radius_km", "limit_per_source", "max_borehole_pages", "max_groundwater_measures"]) args[key] = Number(args[key]);
    const start = Date.now();
    setBusy(true);
    const message = () => notify(`Gathering official public evidence… ${Math.floor((Date.now() - start) / 1000)}s elapsed. Bounded pages and provider timeouts may make a study take a few minutes.`, "loading");
    message();
    const timer = setInterval(message, 1000);
    try {
      const response = await fetch("/api/desk-study", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(args) });
      const value = await responseJSON(response);
      clearInterval(timer);
      await setReport(value);
    } catch (error) { notify(`The study could not be assembled: ${error.message}. Any previous study is still available.`, "error"); }
    finally { clearInterval(timer); setBusy(false); }
  });
  $("load-demo").addEventListener("click", async () => {
    if (busy || !await confirmReplace()) return;
    setBusy(true);
    notify("Opening the saved public Birmingham demonstration…", "loading");
    try { await setReport(await responseJSON(await fetch("/api/demo")), { demo: true }); }
    catch (error) { notify(`Could not open the demonstration: ${error.message}`, "error"); }
    finally { setBusy(false); }
  });
  $("open-workspace").addEventListener("click", () => { if (!busy) $("workspace-file").click(); });
  $("workspace-file").addEventListener("change", async () => {
    const file = $("workspace-file").files[0];
    if (!file || busy) return;
    setBusy(true);
    try {
      if (file.size > 10_000_000) throw new Error("Study JSON files must be 10 MB or smaller.");
      const value = checkReport(JSON.parse(await file.text()));
      if (await confirmReplace()) await setReport(value, { imported: true });
    } catch (error) { notify(`Study file not opened: ${error.message}`, "error"); }
    finally { $("workspace-file").value = ""; setBusy(false); }
  });
  $("download-workspace").addEventListener("click", () => {
    if (!report) return;
    download(JSON.stringify(report, null, 2) + "\n", filename("study.json"), "application/json;charset=utf-8");
    dirty = false;
    $("unsaved-indicator").hidden = true;
    notify("Study JSON download prepared, including source evidence and your review notes. Check your browser’s downloads to keep the file.");
  });
  $("export-report").addEventListener("click", async () => {
    if (!report) return;
    const button = $("export-report");
    button.disabled = true;
    try {
      const response = await fetch("/api/export/report", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(report) });
      if (!response.ok) { await responseJSON(response); return; }
      download(await response.blob(), filename("report.html"), "text/html;charset=utf-8");
      notify("Printable report download prepared. Open the HTML file in a browser to read it or print to PDF.");
    } catch (error) { notify(`Report export failed: ${error.message}`, "error"); }
    finally { button.disabled = false; }
  });
  $("export-investigations").addEventListener("click", exportCandidates);
  $("export-gaps").addEventListener("click", exportGaps);
  $("candidate-search").addEventListener("input", renderCandidates);
  $("candidate-collection").addEventListener("change", renderCandidates);
  $("candidate-review").addEventListener("change", renderCandidates);
  $("gap-filter").addEventListener("change", renderGaps);
  $("close-record").addEventListener("click", () => $("record-dialog").close());
  document.querySelectorAll("[data-tab]").forEach((button) => button.addEventListener("click", () => showTab(button.dataset.tab)));
  window.addEventListener("beforeunload", (event) => { if (dirty) { event.preventDefault(); event.returnValue = ""; } });
  window.Groundwork = Object.freeze({ validateReport: checkReport, validateWorkspace, safeURL, csvCell, csv, getReport: () => report, showTab });
  showTab(activeTab);
})();
