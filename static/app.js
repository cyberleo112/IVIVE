// IVIVE web frontend — vanilla JS.
// Talks to the FastAPI backend at /api/*.

const API = {
  species: "/api/species",
  calculate: "/api/calculate",
  template: "/api/template",
  batch: "/api/batch",
  batchExport: "/api/batch/export",
  validation: "/api/validation",
};

const state = {
  species: [],
  speciesByKey: {},
  batchResults: null,
};

// ---------- Helpers ----------

function $(id) { return document.getElementById(id); }

function fmtNum(v, digits = 4) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  if (v === 0) return "0";
  const abs = Math.abs(v);
  if (abs >= 1000 || abs < 0.001) return v.toExponential(2);
  return Number(v).toPrecision(digits).replace(/\.?0+$/, "").replace(/\.$/, "");
}

function setHidden(el, hidden) {
  if (!el) return;
  if (hidden) el.setAttribute("hidden", "");
  else el.removeAttribute("hidden");
}

async function jsonOrError(resp) {
  if (resp.ok) return await resp.json();
  let detail;
  try { const j = await resp.json(); detail = j.detail || JSON.stringify(j); }
  catch (_) { detail = await resp.text(); }
  throw new Error(detail || `HTTP ${resp.status}`);
}

// ---------- Tabs ----------

function setupTabs() {
  document.querySelectorAll('[role="tab"]').forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.getAttribute("data-tab");
      document.querySelectorAll('[role="tab"]').forEach((b) => {
        const sel = b.getAttribute("data-tab") === target;
        b.setAttribute("aria-selected", sel ? "true" : "false");
      });
      ["single", "batch", "validation"].forEach((id) => {
        setHidden($("tab-" + id), id !== target);
      });
    });
  });
}

// ---------- Species ----------

async function loadSpecies() {
  const list = await jsonOrError(await fetch(API.species));
  state.species = list;
  state.speciesByKey = Object.fromEntries(list.map((s) => [s.key, s]));

  const sel = $("single-species");
  sel.innerHTML = "";
  list.forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s.key;
    opt.textContent = s.label;
    sel.appendChild(opt);
  });

  const tbody = $("species-table");
  tbody.innerHTML = list.map((s) => `
    <tr class="border-t border-slate-200">
      <td class="p-2 text-left">${s.label}</td>
      <td class="p-2 text-right">${fmtNum(s.liver_blood_flow_L_per_h)}</td>
      <td class="p-2 text-right">${fmtNum(s.liver_weight_g)}</td>
      <td class="p-2 text-right">${fmtNum(s.hepatocytes_million_per_g_liver)}</td>
      <td class="p-2 text-right">${fmtNum(s.microsomal_protein_mg_per_g_liver)}</td>
    </tr>
  `).join("");

  populateAdvancedFromSpecies();
}

function populateAdvancedFromSpecies() {
  const key = $("single-species").value;
  const s = state.speciesByKey[key];
  if (!s) return;
  $("adv-qh").value    = s.liver_blood_flow_L_per_h;
  $("adv-liver").value = s.liver_weight_g;
  $("adv-hpgl").value  = s.hepatocytes_million_per_g_liver;
  $("adv-mppgl").value = s.microsomal_protein_mg_per_g_liver;
}

// ---------- Single ----------

function updateClintUnitLabel() {
  const sys = $("single-system").value;
  $("single-clint-unit").textContent = sys === "microsome"
    ? "(uL/min/mg microsomal protein)"
    : "(uL/min/million cells)";
}

function readAdvOverride(id, defaultVal) {
  const el = $(id);
  const v = el.value;
  if (v === "" || v === null) return null;
  const n = parseFloat(v);
  if (Number.isNaN(n)) return null;
  // Only send as override if the value differs meaningfully from default.
  if (Math.abs(n - defaultVal) < 1e-12) return null;
  return n;
}

async function runSingleCalculation() {
  const errEl = $("single-error");
  setHidden(errEl, true);
  setHidden($("single-result"), true);
  setHidden($("single-empty"), true);

  const speciesKey = $("single-species").value;
  const sp = state.speciesByKey[speciesKey];
  const payload = {
    species: speciesKey,
    system: $("single-system").value,
    clint_in_vitro: parseFloat($("single-clint").value),
    fu_inc: parseFloat($("single-fuinc").value),
    fu_p: parseFloat($("single-fup").value),
    rbp: parseFloat($("single-rbp").value),
    liver_blood_flow_L_per_h: readAdvOverride("adv-qh",    sp.liver_blood_flow_L_per_h),
    liver_weight_g:           readAdvOverride("adv-liver", sp.liver_weight_g),
    hpgl:                     readAdvOverride("adv-hpgl",  sp.hepatocytes_million_per_g_liver),
    mppgl:                    readAdvOverride("adv-mppgl", sp.microsomal_protein_mg_per_g_liver),
  };

  try {
    const resp = await fetch(API.calculate, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await jsonOrError(resp);

    $("r-clp-lh").textContent    = fmtNum(data.hepatic_plasma_clearance_L_per_h, 4);
    $("r-clp-mlmin").textContent = fmtNum(data.hepatic_plasma_clearance_mL_per_min, 4);
    $("r-eh").textContent        = fmtNum(data.extraction_ratio_percent, 4);
    setClassBadge($("r-class"), data.clearance_classification);
    $("r-species").textContent   = data.species;
    $("r-system").textContent    = data.system;
    const u = data.inputs_used;
    $("r-qh").textContent    = fmtNum(u.liver_blood_flow_L_per_h);
    $("r-lw").textContent    = fmtNum(u.liver_weight_g);
    $("r-hpgl").textContent  = fmtNum(u.hpgl);
    $("r-mppgl").textContent = fmtNum(u.mppgl);

    setHidden($("single-result"), false);
  } catch (err) {
    errEl.textContent = err.message;
    setHidden(errEl, false);
    setHidden($("single-empty"), false);
  }
}

function clearSingle() {
  setHidden($("single-result"), true);
  setHidden($("single-error"), true);
  setHidden($("single-empty"), false);
}

function setupSingle() {
  $("single-species").addEventListener("change", () => {
    populateAdvancedFromSpecies();
  });
  $("single-system").addEventListener("change", updateClintUnitLabel);
  $("single-calc").addEventListener("click", runSingleCalculation);
  $("single-clear").addEventListener("click", clearSingle);
  $("adv-reset").addEventListener("click", populateAdvancedFromSpecies);
  updateClintUnitLabel();
}

// ---------- Batch ----------

function setupBatch() {
  $("dl-template").addEventListener("click", (e) => {
    e.preventDefault();
    window.location.href = API.template;
  });

  $("batch-file").addEventListener("change", (e) => {
    const f = e.target.files[0];
    $("upload-label").textContent = f ? f.name : "Choose file";
    $("run-batch").disabled = !f;
  });

  $("run-batch").addEventListener("click", runBatch);
  $("dl-xlsx").addEventListener("click", () => exportBatch("xlsx"));
  $("dl-csv").addEventListener("click", () => exportBatch("csv"));
}

async function runBatch() {
  const f = $("batch-file").files[0];
  if (!f) return;

  setHidden($("batch-error"), true);
  setHidden($("batch-results-wrap"), true);
  $("batch-summary").textContent = "Running...";

  const fd = new FormData();
  fd.append("file", f);

  try {
    const resp = await fetch(API.batch, { method: "POST", body: fd });
    const data = await jsonOrError(resp);
    state.batchResults = data;

    $("batch-summary").textContent =
      `${data.total_rows} rows — ${data.success_count} ok, ${data.error_count} error`;

    const tbody = $("batch-tbody");
    tbody.innerHTML = data.results.map((r) => {
      const okBadge = r.status === "ok"
        ? `<span class="badge-ok px-2 py-0.5 rounded text-xs font-medium">ok</span>`
        : `<span class="badge-err px-2 py-0.5 rounded text-xs font-medium" title="${escapeHtml(r.error_message || "")}">error</span>`;
      const res = r.result || {};
      return `
        <tr class="border-t border-slate-200">
          <td class="p-2 text-left">${r.row}</td>
          <td class="p-2 text-left">${escapeHtml(r.compound_id || "")}</td>
          <td class="p-2 text-left">${escapeHtml(r.species || "")}</td>
          <td class="p-2 text-left">${escapeHtml(r.system || "")}</td>
          <td class="p-2 text-right">${fmtNum(res.hepatic_plasma_clearance_L_per_h, 4)}</td>
          <td class="p-2 text-right">${fmtNum(res.hepatic_plasma_clearance_mL_per_min, 4)}</td>
          <td class="p-2 text-right">${fmtNum(res.extraction_ratio_percent, 4)}</td>
          <td class="p-2 text-left">${classificationBadgeHtml(res.clearance_classification)}</td>
          <td class="p-2 text-left">${okBadge}${r.error_message ? `<div class="text-xs text-red-700 mt-0.5">${escapeHtml(r.error_message)}</div>` : ""}</td>
        </tr>
      `;
    }).join("");

    setHidden($("batch-results-wrap"), false);
  } catch (err) {
    $("batch-summary").textContent = "";
    $("batch-error").textContent = err.message;
    setHidden($("batch-error"), false);
  }
}

async function exportBatch(format) {
  if (!state.batchResults) return;
  const resp = await fetch(`${API.batchExport}?format=${format}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ results: state.batchResults.results }),
  });
  if (!resp.ok) {
    alert("Export failed: " + resp.status);
    return;
  }
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = format === "csv" ? "ivive_results.csv" : "ivive_results.xlsx";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function classificationBadgeHtml(classification) {
  if (!classification) return "";
  const c = String(classification).toLowerCase();
  const cls = c === "low" ? "badge-low"
            : c === "high" ? "badge-high"
            : "badge-moderate";
  return `<span class="${cls} px-2 py-0.5 rounded text-xs font-semibold">${escapeHtml(classification)}</span>`;
}

function setClassBadge(el, classification) {
  if (!el) return;
  el.classList.remove("badge-low", "badge-moderate", "badge-high");
  if (!classification) {
    el.textContent = "—";
    return;
  }
  const c = String(classification).toLowerCase();
  const cls = c === "low" ? "badge-low"
            : c === "high" ? "badge-high"
            : "badge-moderate";
  el.classList.add(cls);
  el.textContent = classification;
}

// ---------- Validation ----------

function setupValidation() {
  $("run-validation").addEventListener("click", runValidation);
}

async function runValidation() {
  $("validation-summary").textContent = "Running...";
  setHidden($("validation-wrap"), true);
  try {
    const data = await jsonOrError(await fetch(API.validation));
    const tol = `tolerances: ±${data.clp_relative_tolerance_percent}% on CLp, ±${data.eh_absolute_tolerance_pp} pp on Eh`;
    const summaryClass = data.failed === 0 ? "text-emerald-700 font-semibold" : "text-amber-700 font-semibold";
    $("validation-summary").innerHTML =
      `<span class="${summaryClass}">${data.passed} / ${data.total} pass</span>
       <span class="text-slate-500"> · ${tol}</span>`;

    const tbody = $("validation-tbody");
    tbody.innerHTML = data.cases.map((c) => `
      <tr class="border-t border-slate-200">
        <td class="p-2 text-left">${c.case_id}</td>
        <td class="p-2 text-left">${escapeHtml(c.compound)}</td>
        <td class="p-2 text-left">${c.species}</td>
        <td class="p-2 text-left">${c.system}</td>
        <td class="p-2 text-right">${fmtNum(c.expected_clp_L_per_h, 4)}</td>
        <td class="p-2 text-right">${fmtNum(c.predicted_clp_L_per_h, 4)}</td>
        <td class="p-2 text-right">${fmtNum(c.clp_relative_error_percent, 3)}%</td>
        <td class="p-2 text-right">${fmtNum(c.expected_eh_percent, 4)}</td>
        <td class="p-2 text-right">${fmtNum(c.predicted_eh_percent, 4)}</td>
        <td class="p-2 text-right">${fmtNum(c.eh_absolute_error_pp, 3)}</td>
        <td class="p-2 text-left">
          <span class="${c.pass ? "badge-pass" : "badge-fail"} px-2 py-0.5 rounded text-xs font-medium">
            ${c.pass ? "PASS" : "FAIL"}
          </span>
        </td>
      </tr>
    `).join("");
    setHidden($("validation-wrap"), false);
  } catch (err) {
    $("validation-summary").textContent = "Error: " + err.message;
  }
}

// ---------- Init ----------

document.addEventListener("DOMContentLoaded", async () => {
  setupTabs();
  setupSingle();
  setupBatch();
  setupValidation();
  try {
    await loadSpecies();
  } catch (err) {
    $("single-error").textContent = "Failed to load species: " + err.message;
    setHidden($("single-error"), false);
  }
});
