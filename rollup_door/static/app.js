const ACCESS_KEY_STORAGE = "rollup_access_key_id";
const ACCESS_SECRET_STORAGE = "rollup_access_key_secret";
const OWNER_NAME_STORAGE = "rollup_owner_name";

const tabButtons = Array.from(document.querySelectorAll(".tab-btn"));
const tabContents = Array.from(document.querySelectorAll(".tab-content"));

const accessKeyInput = document.getElementById("accessKeyId");
const accessSecretInput = document.getElementById("accessKeySecret");
const accessStatus = document.getElementById("accessStatus");

const dailyForm = document.getElementById("dailyForm");
const dailySummary = document.getElementById("dailySummary");
const dailyResult = document.getElementById("dailyResult");

const taskForm = document.getElementById("taskForm");
const taskSummary = document.getElementById("taskSummary");
const taskResult = document.getElementById("taskResult");

const endDayForm = document.getElementById("endDayForm");
const endDaySummary = document.getElementById("endDaySummary");
const endDayResult = document.getElementById("endDayResult");

const searchForm = document.getElementById("searchForm");
const historyForm = document.getElementById("historyForm");
const searchNotesResults = document.getElementById("searchNotesResults");
const dailyHistoryResults = document.getElementById("dailyHistoryResults");
const taskHistoryResults = document.getElementById("taskHistoryResults");
const searchRawResult = document.getElementById("searchRawResult");

const weeklyForm = document.getElementById("weeklyForm");
const weeklySummary = document.getElementById("weeklySummary");
const weeklyResult = document.getElementById("weeklyResult");

function setAccessStatus(message, tone = "neutral") {
  accessStatus.textContent = message;
  accessStatus.classList.remove("error", "success");
  if (tone === "error") accessStatus.classList.add("error");
  if (tone === "success") accessStatus.classList.add("success");
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
  setAccessStatus("ล้างค่าเรียบร้อย");
}

function loadAccessConfig() {
  accessKeyInput.value = localStorage.getItem(ACCESS_KEY_STORAGE) || "";
  accessSecretInput.value = localStorage.getItem(ACCESS_SECRET_STORAGE) || "";
  if (accessKeyInput.value && accessSecretInput.value) {
    setAccessStatus("พร้อมใช้งาน", "success");
  }
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
    if (payload.fields?.length) {
      throw new Error(`${err}: ${payload.fields.join(", ")}`);
    }
    throw new Error(err);
  }
  return payload;
}

function collectForm(form) {
  const fd = new FormData(form);
  const raw = Object.fromEntries(fd.entries());
  Object.keys(raw).forEach((key) => {
    if (typeof raw[key] === "string") {
      raw[key] = raw[key].trim();
    }
  });
  return raw;
}

function toPrettyJson(payload) {
  return JSON.stringify(payload, null, 2);
}

function switchTab(tabId) {
  tabButtons.forEach((btn) => btn.classList.toggle("active", btn.dataset.tab === tabId));
  tabContents.forEach((content) => content.classList.toggle("active", content.id === `tab-${tabId}`));

  signedFetch("POST", "/api/v1/events", {
    event_name: "tab_switch",
    page: tabId,
  }).catch(() => {
    // Non-blocking telemetry
  });
}

function withSubmitLock(button, loadingLabel) {
  button.disabled = true;
  button.dataset.originalLabel = button.textContent;
  button.textContent = loadingLabel;
}

function releaseSubmitLock(button) {
  button.disabled = false;
  button.textContent = button.dataset.originalLabel || button.textContent;
}

function isHttpsUrl(value) {
  return value.startsWith("https://");
}

function validateDriveLinksCommaSeparated(value, fieldName) {
  const links = value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

  if (!links.length) return;
  if (links.some((link) => !isHttpsUrl(link))) {
    throw new Error(`invalid_${fieldName}`);
  }
}

function renderSummary(element, lines) {
  element.classList.remove("empty");
  element.innerHTML = lines.map((line) => `<p>${line}</p>`).join("");
}

function renderCards(element, items, builder) {
  element.innerHTML = "";
  if (!items.length) {
    element.innerHTML = '<p class="meta">ไม่พบข้อมูล</p>';
    return;
  }

  const fragment = document.createDocumentFragment();
  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = "output-card";
    card.innerHTML = builder(item);
    fragment.appendChild(card);
  });
  element.appendChild(fragment);
}

async function submitDaily(payload, targetResultEl, targetSummaryEl, submitButton) {
  withSubmitLock(submitButton, "กำลังบันทึก...");
  targetResultEl.textContent = "กำลังบันทึก...";

  try {
    validateDriveLinksCommaSeparated(payload.photo_drive_links || "", "photo_drive_links");
    const data = await signedFetch("POST", "/api/v1/study/daily", payload);
    targetResultEl.textContent = toPrettyJson(data);

    renderSummary(targetSummaryEl, [
      `บันทึกสำเร็จ: ${data.daily_id}`,
      `วันที่: ${payload.log_date || "-"}`,
      `พี่เลี้ยง: ${payload.mentor_name || "-"}`,
    ]);

    const dailyIdInput = taskForm.querySelector("input[name='daily_id']");
    if (dailyIdInput) {
      dailyIdInput.value = data.daily_id;
    }

    localStorage.setItem(OWNER_NAME_STORAGE, payload.owner_name || "ตี๋");
    setAccessStatus("บันทึกข้อมูลรายวันสำเร็จ", "success");
  } catch (err) {
    targetResultEl.textContent = `เกิดข้อผิดพลาด: ${err.message}`;
    setAccessStatus(`บันทึกไม่สำเร็จ: ${err.message}`, "error");
  } finally {
    releaseSubmitLock(submitButton);
  }
}

async function onDailySubmit(event) {
  event.preventDefault();
  const submitButton = dailyForm.querySelector("button[type='submit']");
  const raw = collectForm(dailyForm);

  const payload = {
    ...raw,
    owner_name: raw.owner_name || "ตี๋",
    safety_briefing_done: raw.safety_briefing_done === "true",
  };

  await submitDaily(payload, dailyResult, dailySummary, submitButton);
}

async function onTaskSubmit(event) {
  event.preventDefault();
  const submitButton = taskForm.querySelector("button[type='submit']");
  const raw = collectForm(taskForm);

  if (raw.photo_drive_link && !isHttpsUrl(raw.photo_drive_link)) {
    taskResult.textContent = "เกิดข้อผิดพลาด: invalid_photo_drive_link";
    setAccessStatus("ลิงก์รูปต้องขึ้นต้น https://", "error");
    return;
  }

  withSubmitLock(submitButton, "กำลังบันทึก...");
  taskResult.textContent = "กำลังบันทึก...";

  try {
    const payload = {
      ...raw,
      difficulty_score: raw.difficulty_score || "",
      confidence_after_task: raw.confidence_after_task || "",
    };

    const data = await signedFetch("POST", "/api/v1/study/tasks", payload);
    taskResult.textContent = toPrettyJson(data);

    renderSummary(taskSummary, [
      `บันทึกงานย่อยสำเร็จ: ${data.task_id}`,
      `Daily ID: ${raw.daily_id || "-"}`,
      `หมวดงาน: ${raw.task_category || "-"}`,
    ]);

    setAccessStatus("บันทึกงานย่อยสำเร็จ", "success");
  } catch (err) {
    taskResult.textContent = `เกิดข้อผิดพลาด: ${err.message}`;
    setAccessStatus(`บันทึกไม่สำเร็จ: ${err.message}`, "error");
  } finally {
    releaseSubmitLock(submitButton);
  }
}

async function onEndDaySubmit(event) {
  event.preventDefault();
  const submitButton = endDayForm.querySelector("button[type='submit']");
  const raw = collectForm(endDayForm);

  const ownerName = localStorage.getItem(OWNER_NAME_STORAGE) || "ตี๋";

  const payload = {
    log_date: raw.log_date,
    owner_name: ownerName,
    mentor_name: raw.mentor_name,
    shop_or_site_name: "",
    district: "",
    start_time: "",
    end_time: "",
    today_goal: raw.today_goal,
    job_types_seen: "",
    customer_types_seen: "",
    safety_briefing_done: false,
    tools_prepared: "",
    questions_to_ask: "",
    lesson_summary: raw.lesson_summary,
    mistakes_or_risks_observed: raw.mistakes_or_risks_observed,
    next_day_focus: raw.next_day_focus,
    photo_drive_links: raw.photo_drive_links,
  };

  await submitDaily(payload, endDayResult, endDaySummary, submitButton);
}

async function onSearchSubmit(event) {
  event.preventDefault();
  const submitButton = searchForm.querySelector("button[type='submit']");
  const raw = collectForm(searchForm);
  withSubmitLock(submitButton, "กำลังค้นหา...");
  searchRawResult.textContent = "กำลังค้นหา...";

  try {
    const qParams = new URLSearchParams();
    if (raw.q) qParams.set("q", raw.q);

    const searchData = await signedFetch(
      "GET",
      `/api/v1/study/search${qParams.toString() ? `?${qParams.toString()}` : ""}`,
      null,
      "/api/v1/study/search",
    );

    renderCards(searchNotesResults, searchData.items || [], (item) => {
      if (item.source === "study_daily") {
        return `
          <p class="meta">${item.source} | ${item.id || "-"} | ${item.log_date || "-"}</p>
          <p><strong>บทเรียน:</strong> ${item.lesson_summary || "-"}</p>
          <p><strong>สิ่งที่เสี่ยง/พลาด:</strong> ${item.mistakes_or_risks_observed || "-"}</p>
          <p><strong>คำถาม:</strong> ${item.question || "-"}</p>
        `;
      }
      return `
        <p class="meta">${item.source} | ${item.id || "-"} | Daily ${item.daily_id || "-"}</p>
        <p><strong>อาการ:</strong> ${item.symptom_or_requirement || "-"}</p>
        <p><strong>คำแนะนำจากอา:</strong> ${item.mentor_tip || "-"}</p>
        <p><strong>คำถามค้าง:</strong> ${item.open_question || "-"}</p>
      `;
    });

    if (raw.daily_id) {
      const taskParams = new URLSearchParams({ daily_id: raw.daily_id });
      const taskData = await signedFetch(
        "GET",
        `/api/v1/study/tasks?${taskParams.toString()}`,
        null,
        "/api/v1/study/tasks",
      );

      renderCards(taskHistoryResults, taskData.items || [], (item) => `
        <p class="meta">${item.task_id || "-"} | ${item.task_category || "-"}</p>
        <p><strong>อาการ:</strong> ${item.symptom_or_requirement || "-"}</p>
        <p><strong>ขั้นตอน:</strong> ${item.step_notes || "-"}</p>
        <p><strong>คำแนะนำ:</strong> ${item.mentor_tip || "-"}</p>
      `);
    } else {
      taskHistoryResults.innerHTML = '<p class="meta">กรอก Daily ID เพื่อดูงานย่อยของวันนั้น</p>';
    }

    searchRawResult.textContent = toPrettyJson(searchData);
  } catch (err) {
    searchRawResult.textContent = `เกิดข้อผิดพลาด: ${err.message}`;
    setAccessStatus(`ค้นหาไม่สำเร็จ: ${err.message}`, "error");
  } finally {
    releaseSubmitLock(submitButton);
  }
}

async function onHistorySubmit(event) {
  event.preventDefault();
  const submitButton = historyForm.querySelector("button[type='submit']");
  const raw = collectForm(historyForm);
  withSubmitLock(submitButton, "กำลังโหลด...");

  try {
    const params = new URLSearchParams();
    if (raw.from) params.set("from", raw.from);
    if (raw.to) params.set("to", raw.to);

    const dailyData = await signedFetch(
      "GET",
      `/api/v1/study/daily${params.toString() ? `?${params.toString()}` : ""}`,
      null,
      "/api/v1/study/daily",
    );

    renderCards(dailyHistoryResults, dailyData.items || [], (item) => `
      <p class="meta">${item.daily_id || "-"} | ${item.log_date || "-"}</p>
      <p><strong>พี่เลี้ยง:</strong> ${item.mentor_name || "-"}</p>
      <p><strong>เป้าหมาย:</strong> ${item.today_goal || "-"}</p>
      <p><strong>บทเรียน:</strong> ${item.lesson_summary || "-"}</p>
    `);

    searchRawResult.textContent = toPrettyJson(dailyData);
  } catch (err) {
    searchRawResult.textContent = `เกิดข้อผิดพลาด: ${err.message}`;
    setAccessStatus(`โหลดย้อนหลังไม่สำเร็จ: ${err.message}`, "error");
  } finally {
    releaseSubmitLock(submitButton);
  }
}

async function onWeeklySubmit(event) {
  event.preventDefault();
  const submitButton = weeklyForm.querySelector("button[type='submit']");
  const raw = collectForm(weeklyForm);
  withSubmitLock(submitButton, "กำลังบันทึก...");
  weeklyResult.textContent = "กำลังบันทึก...";

  try {
    const payload = {
      ...raw,
      week_no: Number(raw.week_no),
    };

    const data = await signedFetch("POST", "/api/v1/study/weekly-review", payload);
    weeklyResult.textContent = toPrettyJson(data);

    renderSummary(weeklySummary, [
      `บันทึกสรุปรายสัปดาห์สำเร็จ: ${data.review_id}`,
      `ช่วงวันที่: ${raw.from_date || "-"} ถึง ${raw.to_date || "-"}`,
      `สัปดาห์ที่: ${raw.week_no || "-"}`,
    ]);

    setAccessStatus("บันทึกสรุปรายสัปดาห์สำเร็จ", "success");
  } catch (err) {
    weeklyResult.textContent = `เกิดข้อผิดพลาด: ${err.message}`;
    setAccessStatus(`บันทึกไม่สำเร็จ: ${err.message}`, "error");
  } finally {
    releaseSubmitLock(submitButton);
  }
}

function bindEvents() {
  document.getElementById("saveAccessBtn").addEventListener("click", saveAccessConfig);
  document.getElementById("clearAccessBtn").addEventListener("click", clearAccessConfig);

  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });

  dailyForm.addEventListener("submit", onDailySubmit);
  taskForm.addEventListener("submit", onTaskSubmit);
  endDayForm.addEventListener("submit", onEndDaySubmit);
  searchForm.addEventListener("submit", onSearchSubmit);
  historyForm.addEventListener("submit", onHistorySubmit);
  weeklyForm.addEventListener("submit", onWeeklySubmit);
}

function registerServiceWorker() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      // Keep app usable when SW registration fails.
    });
  }
}

function setDefaultDates() {
  const today = new Date().toISOString().slice(0, 10);
  dailyForm.querySelector("input[name='log_date']").value = today;
  endDayForm.querySelector("input[name='log_date']").value = today;

  const ownerInput = dailyForm.querySelector("input[name='owner_name']");
  ownerInput.value = localStorage.getItem(OWNER_NAME_STORAGE) || "ตี๋";
}

function init() {
  if (!window.crypto?.subtle) {
    setAccessStatus("เบราว์เซอร์ไม่รองรับ Web Crypto", "error");
  }

  loadAccessConfig();
  setDefaultDates();
  bindEvents();
  registerServiceWorker();
}

init();
