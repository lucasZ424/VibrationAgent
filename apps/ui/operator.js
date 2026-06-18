const form = document.querySelector("#queryForm");
const clearButton = document.querySelector("#clearButton");
const statusBadge = document.querySelector("#apiStatus");
const answerStatus = document.querySelector("#answerStatus");
const answer = document.querySelector("#answer");
const taskId = document.querySelector("#taskId");
const chain = document.querySelector("#chain");
const citations = document.querySelector("#citations");
const warnings = document.querySelector("#warnings");
const supervisor = document.querySelector("#supervisor");
const cost = document.querySelector("#cost");
const diagnostics = document.querySelector("#diagnostics");
const rawOutput = document.querySelector("#rawOutput");

function setStatus(text, state = "") {
  statusBadge.textContent = text;
  statusBadge.className = `status-pill ${state}`.trim();
}

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function text(value, fallback = "") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  return String(value);
}

function clearElement(element, emptyText) {
  element.innerHTML = "";
  if (emptyText) {
    element.classList.add("empty");
    element.textContent = emptyText;
  } else {
    element.classList.remove("empty");
  }
}

function renderList(element, rows, emptyText, renderRow) {
  clearElement(element, "");
  if (!rows.length) {
    clearElement(element, emptyText);
    return;
  }
  element.classList.remove("empty");
  rows.forEach((row) => {
    const item = document.createElement("div");
    item.className = "item";
    renderRow(item, row);
    element.appendChild(item);
  });
}

function addText(parent, tag, value) {
  const node = document.createElement(tag);
  node.textContent = value;
  parent.appendChild(node);
  return node;
}

function renderFacts(element, rows, emptyText) {
  element.innerHTML = "";
  if (!rows.length) {
    element.classList.add("empty");
    element.textContent = emptyText;
    return;
  }
  element.classList.remove("empty");
  rows.forEach(([label, value]) => {
    addText(element, "dt", label);
    addText(element, "dd", text(value, "none"));
  });
}

function costRows(structured, output) {
  const rows = [];
  const costData = structured.cost || output.cost;
  const supervisorCost = structured.supervisor_cost;
  const tokenCost = structured.token_cost;
  const supervisorTokenCost = structured.supervisor_token_cost;
  if (tokenCost !== undefined && tokenCost !== null) {
    rows.push(["token_cost", tokenCost]);
  }
  if (costData && typeof costData === "object") {
    Object.entries(costData).forEach(([key, value]) => rows.push([`cost.${key}`, value]));
  }
  if (supervisorTokenCost !== undefined && supervisorTokenCost !== null) {
    rows.push(["supervisor_token_cost", supervisorTokenCost]);
  }
  if (supervisorCost && typeof supervisorCost === "object") {
    Object.entries(supervisorCost).forEach(([key, value]) => rows.push([`supervisor_cost.${key}`, value]));
  }
  return rows;
}

function renderPayload(payload) {
  const output = payload.output || {};
  const structured = output.structured_result || {};
  const answerText = structured.answer || output.summary || "";
  answerStatus.textContent = `${payload.status || output.status || "unknown"}`;
  answer.textContent = answerText || "No answer text returned.";
  answer.classList.toggle("empty", !answerText);
  taskId.textContent = payload.task_id ? `task: ${payload.task_id}` : "";

  renderList(chain, asArray(structured.chain), "No chain steps.", (item, row) => {
    addText(item, "strong", text(row.skill, "unknown skill"));
    addText(item, "p", `${text(row.status, "unknown")} - ${text(row.summary, "no summary")}`);
  });

  renderList(citations, asArray(output.citations), "No citations.", (item, row) => {
    addText(item, "strong", `${text(row.chunk_id, "unknown chunk")} / ${text(row.doc_id, "unknown doc")}`);
    addText(item, "p", `pages: ${asArray(row.pages).join(", ") || "unknown"}; evidence: ${text(row.evidence_type, "documented")}`);
  });

  renderList(warnings, asArray(output.warnings), "No warnings.", (item, row) => {
    item.classList.add("warning");
    addText(item, "strong", text(row, "warning"));
  });

  renderFacts(supervisor, [
    ["status", structured.supervisor_status],
    ["invocations", structured.supervisor_invocations],
    ["action", structured.supervisor_action],
    ["corrections", structured.supervisor_corrections],
  ], "No supervisor metadata.");

  renderFacts(cost, costRows(structured, output), "No cost metadata.");
  rawOutput.textContent = JSON.stringify(payload, null, 2);
  rawOutput.classList.remove("empty");
}

function renderDiagnostics(payload) {
  const dependencies = payload.dependencies || {};
  const local = payload.diagnostics || {};
  const rows = [
    ["status", payload.status],
    ["workspace", payload.workspace],
    ["external_probe", local.external_dependency_probe],
    ["redaction", local.redaction],
    ["operator_ui", local.operator_ui],
    ["postgres", dependencies.postgres && dependencies.postgres.status],
    ["qdrant", dependencies.qdrant && dependencies.qdrant.status],
    ["llm_live", local.llm_live_enabled],
    ["embeddings", local.embedding_provider_enabled],
  ];
  renderFacts(diagnostics, rows, "No diagnostics.");
}

async function loadDiagnostics(headers = {}) {
  try {
    const response = await fetch("/health", {headers});
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(JSON.stringify(payload));
    }
    renderDiagnostics(payload);
  } catch (error) {
    renderFacts(diagnostics, [["status", "unavailable"], ["reason", error.message]], "No diagnostics.");
  }
}

function requestBody(formData) {
  const constraints = {};
  const difficulty = formData.get("difficulty");
  if (difficulty) {
    constraints.difficulty = difficulty;
  }
  const body = {
    query: formData.get("query"),
    user_mode: formData.get("userMode") || "engineering",
    constraints,
  };
  const chunksJsonl = text(formData.get("chunksJsonl")).trim();
  if (chunksJsonl) {
    body.chunks_jsonl = chunksJsonl.split(",").map((item) => item.trim()).filter(Boolean);
  }
  const chunksDir = text(formData.get("chunksDir")).trim();
  if (chunksDir) {
    body.chunks_dir = chunksDir;
  }
  const topK = Number(formData.get("topK"));
  if (Number.isInteger(topK) && topK > 0) {
    body.top_k = topK;
  }
  return body;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(form);
  const token = text(formData.get("apiToken")).trim();
  const headers = {"Content-Type": "application/json"};
  if (token) {
    headers["x-api-key"] = token;
  }
  const diagnosticsHeaders = token ? {"x-api-key": token} : {};
  setStatus("Running");
  form.querySelector("button[type='submit']").disabled = true;
  try {
    await loadDiagnostics(diagnosticsHeaders);
    const response = await fetch("/query", {
      method: "POST",
      headers,
      body: JSON.stringify(requestBody(formData)),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(JSON.stringify(payload));
    }
    renderPayload(payload);
    setStatus(payload.status || "Done", payload.status === "ok" ? "ok" : "fail");
  } catch (error) {
    answerStatus.textContent = "Request failed";
    answer.textContent = error.message;
    answer.classList.remove("empty");
    rawOutput.textContent = "{}";
    setStatus("Failed", "fail");
  } finally {
    form.querySelector("button[type='submit']").disabled = false;
  }
});

clearButton.addEventListener("click", () => {
  answerStatus.textContent = "No run yet";
  answer.textContent = "Results appear here after a local query.";
  answer.classList.add("empty");
  taskId.textContent = "";
  clearElement(chain, "No chain steps.");
  clearElement(citations, "No citations.");
  clearElement(warnings, "No warnings.");
  renderFacts(supervisor, [], "No supervisor metadata.");
  renderFacts(cost, [], "No cost metadata.");
  renderFacts(diagnostics, [], "No diagnostics.");
  rawOutput.textContent = "{}";
  rawOutput.classList.add("empty");
  setStatus("Idle");
});

loadDiagnostics();
