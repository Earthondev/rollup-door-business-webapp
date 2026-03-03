const ACCESS_KEY_STORAGE = "rollup_access_key_id";
const ACCESS_SECRET_STORAGE = "rollup_access_key_secret";

const CURRENCY_FMT = new Intl.NumberFormat("th-TH", {
  style: "currency",
  currency: "THB",
  maximumFractionDigits: 2,
});

const NUMBER_FMT = new Intl.NumberFormat("th-TH", { maximumFractionDigits: 2 });

const tabButtons = Array.from(document.querySelectorAll(".tab-btn"));
const tabContents = Array.from(document.querySelectorAll(".tab-content"));
const tabShortcutButtons = Array.from(document.querySelectorAll("[data-switch-tab]"));

const accessKeyInput = document.getElementById("accessKeyId");
const accessSecretInput = document.getElementById("accessKeySecret");
const accessStatus = document.getElementById("accessStatus");
const healthBadge = document.getElementById("healthBadge");

const heroTotalCases = document.getElementById("heroTotalCases");
const heroAvgMargin = document.getElementById("heroAvgMargin");
const heroLossRisk = document.getElementById("heroLossRisk");

const intakeForm = document.getElementById("intakeForm");
const intakePreviewBtn = document.getElementById("intakePreviewBtn");
const intakePreviewCards = document.getElementById("intakePreviewCards");
const intakeSummary = document.getElementById("intakeSummary");
const intakeWarnings = document.getElementById("intakeWarnings");
const intakeResult = document.getElementById("intakeResult");

const calculatorForm = document.getElementById("calculatorForm");
const calculatorSummary = document.getElementById("calculatorSummary");
const calculatorResult = document.getElementById("calculatorResult");
const copyToIntakeBtn = document.getElementById("copyToIntakeBtn");

const knowledgeForm = document.getElementById("knowledgeForm");
const knowledgeResults = document.getElementById("knowledgeResults");
const knowledgeQuickTags = Array.from(document.querySelectorAll("#knowledgeQuickTags .chip-btn"));

const analyticsForm = document.getElementById("analyticsForm");
const analyticsCards = document.getElementById("analyticsCards");
const analyticsResult = document.getElementById("analyticsResult");
const topDriversList = document.getElementById("topDriversList");
const refreshAnalyticsBtn = document.getElementById("refreshAnalyticsBtn");
const analyticsQuickRanges = Array.from(document.querySelectorAll("#analyticsQuickRanges .chip-btn"));

function setHealthBadge(text, tone = "neutral") {
  healthBadge.textContent = text;
  healthBadge.className = `badge ${tone}`;
}

function setAccessStatus(message, tone = "neutral") {
  accessStatus.textContent = message;
  accessStatus.classList.remove("is-error", "is-success");

  if (tone === "error") {
    accessStatus.classList.add("is-error");
  }

  if (tone === "success") {
    accessStatus.classList.add("is-success");
  }
}

function loadAccessConfig() {
  accessKeyInput.value = localStorage.getItem(ACCESS_KEY_STORAGE) || "";
  accessSecretInput.value = localStorage.getItem(ACCESS_SECRET_STORAGE) || "";

  if (accessKeyInput.value && accessSecretInput.value) {
    setAccessStatus("พร้อมใช้งาน: พบ Access Key ในเครื่อง", "success");
  } else {
    setAccessStatus("ยังไม่ตั้ง Access Key", "neutral");
  }
}

function saveAccessConfig() {
  localStorage.setItem(ACCESS_KEY_STORAGE, accessKeyInput.value.trim());
  localStorage.setItem(ACCESS_SECRET_STORAGE, accessSecretInput.value.trim());
  setAccessStatus("บันทึก Access Key แล้ว", "success");
}

function clearAccessConfig() {
  localStorage.removeItem(ACCESS_KEY_STORAGE);
  localStorage.removeItem(ACCESS_SECRET_STORAGE);
  accessKeyInput.value = "";
  accessSecretInput.value = "";
  setAccessStatus("ล้างค่าเรียบร้อย", "neutral");
}

function getAccessConfig() {
  const keyId = localStorage.getItem(ACCESS_KEY_STORAGE) || "";
  const secret = localStorage.getItem(ACCESS_SECRET_STORAGE) || "";
  if (!keyId || !secret) {
    throw new Error("missing_access_key_config");
  }
  return { keyId, secret };
}

async function sha256Hex(text) {
  const data = new TextEncoder().encode(text);
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  return [...new Uint8Array(hashBuffer)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function hmacSha256Hex(secret, message) {
  const keyData = new TextEncoder().encode(secret);
  const cryptoKey = await crypto.subtle.importKey(
    "raw",
    keyData,
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign("HMAC", cryptoKey, new TextEncoder().encode(message));
  return [...new Uint8Array(signature)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function signedFetch(method, requestPath, bodyObj = null, signaturePath = null) {
  const { keyId, secret } = getAccessConfig();
  const timestamp = Math.floor(Date.now() / 1000).toString();
  const bodyText = bodyObj ? JSON.stringify(bodyObj) : "";
  const pathForSign = signaturePath || requestPath.split("?")[0];
  const bodyHash = await sha256Hex(bodyText);
  const message = `${timestamp}.${method.toUpperCase()}.${pathForSign}.${bodyHash}`;
  const signature = await hmacSha256Hex(secret, message);

  const headers = {
    "X-Access-Key": keyId,
    "X-Timestamp": timestamp,
    "X-Signature": signature,
  };

  if (bodyObj) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(requestPath, {
    method,
    headers,
    body: bodyObj ? bodyText : undefined,
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const err = payload.error || `http_${response.status}`;
    throw new Error(err);
  }

  return payload;
}

function asNumber(value) {
  if (value === "" || value === null || value === undefined) {
    return "";
  }
  const n = Number(value);
  return Number.isFinite(n) ? n : value;
}

function asBoolean(value) {
  if (typeof value === "boolean") {
    return value;
  }
  return String(value).trim().toLowerCase() === "true";
}

function collectForm(form) {
  const fd = new FormData(form);
  const obj = Object.fromEntries(fd.entries());

  for (const [k, v] of Object.entries(obj)) {
    if (typeof v === "string") {
      obj[k] = v.trim();
    }
  }

  form.querySelectorAll("input[type='checkbox']").forEach((el) => {
    obj[el.name] = el.checked;
  });

  return obj;
}

function toPrettyJson(data) {
  return JSON.stringify(data, null, 2);
}

function formatCurrency(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "-";
  }
  return CURRENCY_FMT.format(number);
}

function formatNumber(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "-";
  }
  return NUMBER_FMT.format(number);
}

function formatPct(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "-";
  }
  return `${NUMBER_FMT.format(number)}%`;
}

function switchTab(tabId) {
  tabButtons.forEach((btn) => btn.classList.toggle("active", btn.dataset.tab === tabId));
  tabContents.forEach((content) => content.classList.toggle("active", content.id === `tab-${tabId}`));

  signedFetch("POST", "/api/v1/events", {
    event_name: "tab_switch",
    page: tabId,
  }).catch(() => {
    // Non-blocking telemetry.
  });
}

function buildCalculatorPayload(raw) {
  return {
    material_cost: asNumber(raw.material_cost),
    labor_cost: asNumber(raw.labor_cost),
    travel_cost: asNumber(raw.travel_cost),
    risk_level: raw.risk_level,
    warranty_months: asNumber(raw.warranty_months),
    target_margin_pct: asNumber(raw.target_margin_pct),
  };
}

function renderInsightCards(container, estimate) {
  container.innerHTML = "";
  const cards = [
    ["ต้นทุนรวม (Direct Cost)", formatCurrency(estimate.direct_cost)],
    ["ราคาขายแนะนำ", formatCurrency(estimate.suggested_price)],
    ["กำไรขั้นต้น", formatCurrency(estimate.gross_profit)],
    ["Margin", formatPct(estimate.gross_margin_pct)],
  ];

  cards.forEach(([label, value]) => {
    const card = document.createElement("article");
    card.className = "insight-card";
    card.innerHTML = `<p class="metric-label">${label}</p><p class="metric-value">${value}</p>`;
    container.appendChild(card);
  });
}

function mapWarning(code) {
  const map = {
    margin_below_threshold: "Margin ต่ำกว่าเกณฑ์ที่ตั้งไว้",
    invalid_dimensions: "ขนาดประตูไม่ถูกต้อง",
    high_usage_heavy_duty_recommended: "แนะนำสเปก Heavy Duty เพราะใช้งานถี่",
  };
  return map[code] || code;
}

function renderWarnings(container, warnings) {
  container.innerHTML = "";
  if (!warnings || !warnings.length) {
    return;
  }

  warnings.forEach((warning) => {
    const chip = document.createElement("span");
    chip.className = "warning-chip";
    chip.textContent = mapWarning(warning);
    container.appendChild(chip);
  });
}

function renderIntakeSummary(data) {
  intakeSummary.classList.remove("empty");
  intakeSummary.innerHTML = `
    <p class="result-summary-title">บันทึกเคสสำเร็จ: ${data.case_id || "-"}</p>
    <div class="result-summary-grid">
      <div>
        <p>ราคาขายแนะนำ</p>
        <strong>${formatCurrency(data.suggested_price)}</strong>
      </div>
      <div>
        <p>Margin ที่คำนวณได้</p>
        <strong>${formatPct(data.gross_margin_pct)}</strong>
      </div>
      <div>
        <p>สถานะ</p>
        <strong>พร้อมติดตามงาน</strong>
      </div>
    </div>
  `;
}

function renderCalculatorSummary(data) {
  calculatorSummary.classList.remove("empty");
  calculatorSummary.innerHTML = `
    <p class="result-summary-title">ผลคำนวณราคาด่วน</p>
    <div class="result-summary-grid">
      <div>
        <p>ต้นทุนรวม</p>
        <strong>${formatCurrency(data.direct_cost)}</strong>
      </div>
      <div>
        <p>ราคาขายแนะนำ</p>
        <strong>${formatCurrency(data.suggested_price)}</strong>
      </div>
      <div>
        <p>กำไรขั้นต้น</p>
        <strong>${formatCurrency(data.gross_profit)}</strong>
      </div>
      <div>
        <p>Margin</p>
        <strong>${formatPct(data.gross_margin_pct)}</strong>
      </div>
    </div>
  `;
}

function renderKnowledge(items) {
  knowledgeResults.innerHTML = "";
  if (!items.length) {
    knowledgeResults.innerHTML = '<p class="hint">ไม่พบข้อมูลที่ตรงเงื่อนไข</p>';
    return;
  }

  const fragment = document.createDocumentFragment();
  for (const item of items) {
    const card = document.createElement("article");
    card.className = "knowledge-item";

    const tags = String(item.tags || "-")
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean)
      .join(" | ");

    card.innerHTML = `
      <h4>${item.topic || "หัวข้อทั่วไป"}</h4>
      <p><strong>Q:</strong> ${item.question || "-"}</p>
      <p><strong>A:</strong> ${item.answer || "-"}</p>
      <p><strong>Tags:</strong> ${tags || "-"}</p>
    `;

    fragment.appendChild(card);
  }
  knowledgeResults.appendChild(fragment);
}

function renderAnalyticsCards(summary) {
  analyticsCards.innerHTML = "";
  topDriversList.innerHTML = "";

  const cards = [
    ["จำนวนเคสทั้งหมด", formatNumber(summary.total_cases ?? 0), ""],
    ["กำไรเฉลี่ย (%)", formatPct(summary.avg_margin_pct ?? 0), ""],
    ["เคสเสี่ยงกำไรต่ำ", formatNumber(summary.loss_risk_cases ?? 0), "danger"],
    ["ช่วงวันที่", `${summary.date_range?.from || "-"} ถึง ${summary.date_range?.to || "-"}`, ""],
  ];

  cards.forEach(([label, value, extraClass]) => {
    const card = document.createElement("article");
    card.className = `metric-card ${extraClass}`.trim();
    card.innerHTML = `<p class="metric-label">${label}</p><p class="metric-value">${value}</p>`;
    analyticsCards.appendChild(card);
  });

  const drivers = summary.top_cost_drivers || [];
  if (!drivers.length) {
    const li = document.createElement("li");
    li.textContent = "ยังไม่มีข้อมูล cost driver ในช่วงนี้";
    topDriversList.appendChild(li);
  } else {
    drivers.forEach((driver) => {
      const li = document.createElement("li");
      li.textContent = `${driver.driver || "unknown"}: ${formatNumber(driver.count || 0)} เคส`;
      topDriversList.appendChild(li);
    });
  }

  heroTotalCases.textContent = formatNumber(summary.total_cases ?? 0);
  heroAvgMargin.textContent = formatPct(summary.avg_margin_pct ?? 0);
  heroLossRisk.textContent = formatNumber(summary.loss_risk_cases ?? 0);
}

function setQuickRange(rangeType) {
  const fromInput = analyticsForm.querySelector("input[name='from']");
  const toInput = analyticsForm.querySelector("input[name='to']");

  const toDate = new Date();
  const fromDate = new Date(toDate);

  if (rangeType === "today") {
    // Keep same day.
  } else {
    const days = Number(rangeType);
    if (Number.isFinite(days) && days > 0) {
      fromDate.setDate(toDate.getDate() - (days - 1));
    }
  }

  const toISO = toDate.toISOString().slice(0, 10);
  const fromISO = fromDate.toISOString().slice(0, 10);

  fromInput.value = fromISO;
  toInput.value = toISO;

  analyticsQuickRanges.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.range === rangeType);
  });
}

async function runIntakePreview() {
  intakePreviewCards.innerHTML = "";

  try {
    const raw = collectForm(intakeForm);
    const payload = buildCalculatorPayload(raw);

    const required = ["material_cost", "labor_cost", "travel_cost"];
    const missing = required.filter((field) => payload[field] === "");
    if (missing.length) {
      setAccessStatus("พรีวิวไม่ได้: ต้องกรอกค่าวัสดุ ค่าแรง ค่าเดินทาง", "error");
      return;
    }

    const data = await signedFetch("POST", "/api/v1/calculator/estimate", payload);
    renderInsightCards(intakePreviewCards, data);
    setAccessStatus("อัปเดตพรีวิวราคาแล้ว", "success");
  } catch (err) {
    setAccessStatus(`พรีวิวไม่สำเร็จ: ${err.message}`, "error");
    intakePreviewCards.innerHTML = "";
  }
}

async function onIntakeSubmit(e) {
  e.preventDefault();
  intakeResult.textContent = "กำลังบันทึก...";

  try {
    const raw = collectForm(intakeForm);
    const payload = {
      ...raw,
      width_mm: asNumber(raw.width_mm),
      height_mm: asNumber(raw.height_mm),
      usage_per_day: asNumber(raw.usage_per_day),
      urgent_flag: asBoolean(raw.urgent_flag),
      target_margin_pct: asNumber(raw.target_margin_pct),
      warranty_months: asNumber(raw.warranty_months),
      material_cost: asNumber(raw.material_cost),
      labor_cost: asNumber(raw.labor_cost),
      travel_cost: asNumber(raw.travel_cost),
      risk_buffer_cost: asNumber(raw.risk_buffer_cost),
      warranty_buffer_cost: asNumber(raw.warranty_buffer_cost),
      final_price: asNumber(raw.final_price),
    };

    if (payload.risk_buffer_cost === "") delete payload.risk_buffer_cost;
    if (payload.warranty_buffer_cost === "") delete payload.warranty_buffer_cost;
    if (payload.final_price === "") delete payload.final_price;

    const data = await signedFetch("POST", "/api/v1/cases", payload);
    intakeResult.textContent = toPrettyJson(data);
    renderIntakeSummary(data);
    renderWarnings(intakeWarnings, data.warnings || []);
    setAccessStatus("บันทึกเคสสำเร็จ", "success");

    signedFetch("POST", "/api/v1/events", {
      event_name: "case_saved",
      page: "intake",
      metadata: {
        case_id: data.case_id,
        margin: data.gross_margin_pct,
      },
    }).catch(() => {
      // Non-blocking telemetry.
    });
  } catch (err) {
    intakeResult.textContent = `เกิดข้อผิดพลาด: ${err.message}`;
    setAccessStatus(`เรียก API ไม่สำเร็จ: ${err.message}`, "error");
  }
}

async function onCalculatorSubmit(e) {
  e.preventDefault();
  calculatorResult.textContent = "กำลังคำนวณ...";

  try {
    const raw = collectForm(calculatorForm);
    const payload = buildCalculatorPayload(raw);
    const data = await signedFetch("POST", "/api/v1/calculator/estimate", payload);

    calculatorResult.textContent = toPrettyJson(data);
    renderCalculatorSummary(data);
    setAccessStatus("คำนวณราคาเรียบร้อย", "success");
  } catch (err) {
    calculatorResult.textContent = `เกิดข้อผิดพลาด: ${err.message}`;
    setAccessStatus(`เรียก API ไม่สำเร็จ: ${err.message}`, "error");
  }
}

function copyCalculatorToIntake() {
  const raw = collectForm(calculatorForm);
  const fields = [
    "material_cost",
    "labor_cost",
    "travel_cost",
    "risk_level",
    "warranty_months",
    "target_margin_pct",
  ];

  fields.forEach((name) => {
    const source = calculatorForm.querySelector(`[name='${name}']`);
    const target = intakeForm.querySelector(`[name='${name}']`);
    if (source && target) {
      target.value = source.value;
    }
  });

  switchTab("intake");
  setAccessStatus("คัดลอกข้อมูลไปหน้า Intake แล้ว", "success");
}

async function onKnowledgeSubmit(e) {
  e.preventDefault();
  knowledgeResults.innerHTML = '<p class="hint">กำลังค้นหา...</p>';

  try {
    const raw = collectForm(knowledgeForm);
    const params = new URLSearchParams();
    if (raw.q) params.set("q", raw.q);
    if (raw.tag) params.set("tag", raw.tag);

    const path = `/api/v1/knowledge/search${params.toString() ? `?${params.toString()}` : ""}`;
    const data = await signedFetch("GET", path, null, "/api/v1/knowledge/search");
    renderKnowledge(data.items || []);
  } catch (err) {
    knowledgeResults.innerHTML = `<p class="error">เกิดข้อผิดพลาด: ${err.message}</p>`;
  }
}

async function onAnalyticsSubmit(e) {
  e.preventDefault();
  analyticsResult.textContent = "กำลังโหลด...";

  try {
    const raw = collectForm(analyticsForm);
    const params = new URLSearchParams();
    if (raw.from) params.set("from", raw.from);
    if (raw.to) params.set("to", raw.to);

    const path = `/api/v1/analytics/summary${params.toString() ? `?${params.toString()}` : ""}`;
    const data = await signedFetch("GET", path, null, "/api/v1/analytics/summary");

    renderAnalyticsCards(data);
    analyticsResult.textContent = toPrettyJson(data);
  } catch (err) {
    analyticsResult.textContent = `เกิดข้อผิดพลาด: ${err.message}`;
    setAccessStatus(`โหลด analytics ไม่สำเร็จ: ${err.message}`, "error");
  }
}

async function onRefreshAnalytics() {
  refreshAnalyticsBtn.disabled = true;
  refreshAnalyticsBtn.textContent = "กำลังรีเฟรช...";
  try {
    const data = await signedFetch("POST", "/api/v1/analytics/refresh", {});
    analyticsResult.textContent = toPrettyJson(data);
    setAccessStatus("รีเฟรช analytics_daily แล้ว", "success");
  } catch (err) {
    analyticsResult.textContent = `เกิดข้อผิดพลาด: ${err.message}`;
    setAccessStatus(`รีเฟรช analytics ไม่สำเร็จ: ${err.message}`, "error");
  } finally {
    refreshAnalyticsBtn.disabled = false;
    refreshAnalyticsBtn.textContent = "รีเฟรช analytics_daily";
  }
}

async function loadHealthStatus() {
  try {
    const response = await fetch("/api/v1/health");
    const payload = await response.json();
    if (payload.ok) {
      setHealthBadge("ระบบพร้อมใช้งาน", "success");
      return;
    }
    setHealthBadge(`ต้องตรวจ config: ${(payload.errors || []).join(", ")}`, "error");
  } catch (_err) {
    setHealthBadge("ตรวจสุขภาพระบบไม่สำเร็จ", "error");
  }
}

function bindEvents() {
  document.getElementById("saveAccessBtn").addEventListener("click", saveAccessConfig);
  document.getElementById("clearAccessBtn").addEventListener("click", clearAccessConfig);

  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });

  tabShortcutButtons.forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.switchTab));
  });

  intakeForm.addEventListener("submit", onIntakeSubmit);
  intakePreviewBtn.addEventListener("click", runIntakePreview);

  calculatorForm.addEventListener("submit", onCalculatorSubmit);
  copyToIntakeBtn.addEventListener("click", copyCalculatorToIntake);

  knowledgeForm.addEventListener("submit", onKnowledgeSubmit);
  knowledgeQuickTags.forEach((btn) => {
    btn.addEventListener("click", () => {
      const tagInput = knowledgeForm.querySelector("input[name='tag']");
      tagInput.value = btn.dataset.tag || "";
      onKnowledgeSubmit(new Event("submit", { cancelable: true }));
    });
  });

  analyticsForm.addEventListener("submit", onAnalyticsSubmit);
  refreshAnalyticsBtn.addEventListener("click", onRefreshAnalytics);

  analyticsQuickRanges.forEach((btn) => {
    btn.addEventListener("click", () => {
      setQuickRange(btn.dataset.range || "30");
      analyticsForm.requestSubmit();
    });
  });
}

function registerServiceWorker() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      // Keep app functional even when SW registration fails.
    });
  }
}

async function bootstrapAnalyticsDefault() {
  setQuickRange("30");
  const hasAccess = Boolean(localStorage.getItem(ACCESS_KEY_STORAGE) && localStorage.getItem(ACCESS_SECRET_STORAGE));
  if (!hasAccess) {
    return;
  }

  try {
    await onAnalyticsSubmit(new Event("submit", { cancelable: true }));
  } catch (_err) {
    // Already handled in submit.
  }
}

function init() {
  if (!window.crypto?.subtle) {
    setAccessStatus("เบราว์เซอร์ไม่รองรับ Web Crypto", "error");
  }

  loadAccessConfig();
  bindEvents();
  registerServiceWorker();
  loadHealthStatus();
  bootstrapAnalyticsDefault();
}

init();
