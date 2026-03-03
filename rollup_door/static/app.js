const ACCESS_KEY_STORAGE = "rollup_access_key_id";
const ACCESS_SECRET_STORAGE = "rollup_access_key_secret";

const tabButtons = Array.from(document.querySelectorAll(".tab-btn"));
const tabContents = Array.from(document.querySelectorAll(".tab-content"));

const accessKeyInput = document.getElementById("accessKeyId");
const accessSecretInput = document.getElementById("accessKeySecret");
const accessStatus = document.getElementById("accessStatus");

const intakeForm = document.getElementById("intakeForm");
const intakeResult = document.getElementById("intakeResult");

const calculatorForm = document.getElementById("calculatorForm");
const calculatorResult = document.getElementById("calculatorResult");

const knowledgeForm = document.getElementById("knowledgeForm");
const knowledgeResults = document.getElementById("knowledgeResults");

const analyticsForm = document.getElementById("analyticsForm");
const analyticsCards = document.getElementById("analyticsCards");
const analyticsResult = document.getElementById("analyticsResult");
const refreshAnalyticsBtn = document.getElementById("refreshAnalyticsBtn");

function setAccessStatus(message, isError = false) {
  accessStatus.textContent = message;
  accessStatus.classList.toggle("error", isError);
}

function loadAccessConfig() {
  accessKeyInput.value = localStorage.getItem(ACCESS_KEY_STORAGE) || "";
  accessSecretInput.value = localStorage.getItem(ACCESS_SECRET_STORAGE) || "";
}

function saveAccessConfig() {
  localStorage.setItem(ACCESS_KEY_STORAGE, accessKeyInput.value.trim());
  localStorage.setItem(ACCESS_SECRET_STORAGE, accessSecretInput.value.trim());
  setAccessStatus("บันทึก Access Key แล้ว");
}

function clearAccessConfig() {
  localStorage.removeItem(ACCESS_KEY_STORAGE);
  localStorage.removeItem(ACCESS_SECRET_STORAGE);
  accessKeyInput.value = "";
  accessSecretInput.value = "";
  setAccessStatus("ล้างค่าเรียบร้อย");
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
    card.innerHTML = `
      <p><strong>หัวข้อ:</strong> ${item.topic || "-"}</p>
      <p><strong>Q:</strong> ${item.question || "-"}</p>
      <p><strong>A:</strong> ${item.answer || "-"}</p>
      <p><strong>Tags:</strong> ${item.tags || "-"}</p>
    `;
    fragment.appendChild(card);
  }
  knowledgeResults.appendChild(fragment);
}

function renderAnalyticsCards(summary) {
  analyticsCards.innerHTML = "";
  const cards = [
    ["Total Cases", summary.total_cases ?? 0],
    ["Avg Margin (%)", summary.avg_margin_pct ?? 0],
    ["Loss Risk Cases", summary.loss_risk_cases ?? 0],
    ["Top Driver", summary.top_cost_drivers?.[0]?.driver || "-"],
  ];

  cards.forEach(([label, value]) => {
    const card = document.createElement("article");
    card.className = "metric-card";
    card.innerHTML = `<p class="metric-label">${label}</p><p class="metric-value">${value}</p>`;
    analyticsCards.appendChild(card);
  });
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
    setAccessStatus("บันทึกเคสสำเร็จ");
  } catch (err) {
    intakeResult.textContent = `เกิดข้อผิดพลาด: ${err.message}`;
    setAccessStatus(`เรียก API ไม่สำเร็จ: ${err.message}`, true);
  }
}

async function onCalculatorSubmit(e) {
  e.preventDefault();
  calculatorResult.textContent = "กำลังคำนวณ...";

  try {
    const raw = collectForm(calculatorForm);
    const payload = {
      material_cost: asNumber(raw.material_cost),
      labor_cost: asNumber(raw.labor_cost),
      travel_cost: asNumber(raw.travel_cost),
      risk_level: raw.risk_level,
      warranty_months: asNumber(raw.warranty_months),
      target_margin_pct: asNumber(raw.target_margin_pct),
    };

    const data = await signedFetch("POST", "/api/v1/calculator/estimate", payload);
    calculatorResult.textContent = toPrettyJson(data);
  } catch (err) {
    calculatorResult.textContent = `เกิดข้อผิดพลาด: ${err.message}`;
    setAccessStatus(`เรียก API ไม่สำเร็จ: ${err.message}`, true);
  }
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
  }
}

async function onRefreshAnalytics() {
  refreshAnalyticsBtn.disabled = true;
  refreshAnalyticsBtn.textContent = "กำลังรีเฟรช...";
  try {
    const data = await signedFetch("POST", "/api/v1/analytics/refresh", {});
    analyticsResult.textContent = toPrettyJson(data);
  } catch (err) {
    analyticsResult.textContent = `เกิดข้อผิดพลาด: ${err.message}`;
  } finally {
    refreshAnalyticsBtn.disabled = false;
    refreshAnalyticsBtn.textContent = "รีเฟรช analytics_daily";
  }
}

function bindEvents() {
  document.getElementById("saveAccessBtn").addEventListener("click", saveAccessConfig);
  document.getElementById("clearAccessBtn").addEventListener("click", clearAccessConfig);

  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });

  intakeForm.addEventListener("submit", onIntakeSubmit);
  calculatorForm.addEventListener("submit", onCalculatorSubmit);
  knowledgeForm.addEventListener("submit", onKnowledgeSubmit);
  analyticsForm.addEventListener("submit", onAnalyticsSubmit);
  refreshAnalyticsBtn.addEventListener("click", onRefreshAnalytics);
}

function registerServiceWorker() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      // Keep app functional even when SW registration fails.
    });
  }
}

function init() {
  if (!window.crypto?.subtle) {
    setAccessStatus("เบราว์เซอร์ไม่รองรับ Web Crypto", true);
  }
  loadAccessConfig();
  bindEvents();
  registerServiceWorker();
}

init();
