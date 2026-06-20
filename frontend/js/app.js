const BASE = (document.querySelector("base")?.getAttribute("href") || "/gasificado/").replace(/\/$/, "");
const API = `${window.location.origin}${BASE}`;
const TZ = "America/Bogota";

const auth = {
  token: sessionStorage.getItem("gas_token"),
  role: sessionStorage.getItem("gas_role"),
  username: sessionStorage.getItem("gas_user"),
};

function authHeaders() {
  return auth.token ? { Authorization: `Bearer ${auth.token}` } : {};
}

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(options.headers || {}),
    },
  });
  if (res.status === 401) {
    logout();
    throw new Error("Sesión expirada");
  }
  return res;
}

function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-CO", { timeZone: TZ });
}

function logout() {
  sessionStorage.clear();
  if (adminState.ws) adminState.ws.close();
  if (clientState.ws) clientState.ws.close();
  location.reload();
}

function showLoginError(msg) {
  const el = document.getElementById("loginError");
  el.textContent = msg;
  el.classList.remove("hidden");
}

/* ---------- LOGIN ---------- */
document.getElementById("loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  document.getElementById("loginError").classList.add("hidden");
  const username = document.getElementById("loginUser").value.trim();
  const password = document.getElementById("loginPass").value;
  try {
    const res = await fetch(`${API}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json();
    if (!res.ok) {
      showLoginError(data.detail || "Error de acceso");
      return;
    }
    sessionStorage.setItem("gas_token", data.token);
    sessionStorage.setItem("gas_role", data.role);
    sessionStorage.setItem("gas_user", data.username);
    auth.token = data.token;
    auth.role = data.role;
    auth.username = data.username;
    bootApp();
  } catch (err) {
    showLoginError(err.message);
  }
});

function bootApp() {
  document.getElementById("loginScreen").classList.add("hidden");
  if (auth.role === "admin") {
    document.getElementById("adminApp").classList.remove("hidden");
    document.getElementById("adminUser").textContent = auth.username;
    initAdmin();
  } else {
    document.getElementById("clientApp").classList.remove("hidden");
    document.getElementById("clientUser").textContent = auth.username;
    initClient();
  }
}

/* ---------- ADMIN ---------- */
const adminState = {
  ws: null,
  commandHistory: [],
  historyIndex: -1,
  tempChart: null,
  gasChart: null,
};

function initAdmin() {
  document.getElementById("logoutAdmin").addEventListener("click", logout);
  document.getElementById("refreshDevices").addEventListener("click", adminLoadDevices);
  document.getElementById("clearTerminal").addEventListener("click", () => {
    document.getElementById("terminal").innerHTML = "";
  });
  document.getElementById("clearInput").addEventListener("click", () => {
    document.getElementById("commandInput").value = "";
  });
  document.getElementById("sendCommand").addEventListener("click", () => {
    adminSendCommand(document.getElementById("commandInput").value);
    document.getElementById("commandInput").value = "";
  });
  document.querySelectorAll("#adminApp .quick-cmd").forEach((btn) => {
    btn.addEventListener("click", () => adminSendCommand(btn.dataset.cmd));
  });
  document.getElementById("loadChart").addEventListener("click", adminLoadChart);
  document.getElementById("deviceSelect").addEventListener("change", () => {
    adminRefreshLatest();
    adminLoadChart();
  });
  document.getElementById("commandInput").addEventListener("keydown", adminCommandKeydown);

  adminInitCharts();
  adminConnectWs();
  setDefaultDateRange("fromDate", "toDate");
  adminLoadDevices().then(() => {
    adminRefreshLatest();
    adminLoadChart();
  });
  setInterval(adminRefreshLatest, 15000);
}

function adminAppendTerminal(text, cls = "rx") {
  const terminal = document.getElementById("terminal");
  const line = document.createElement("div");
  line.className = cls;
  line.textContent = text;
  terminal.appendChild(line);
  terminal.scrollTop = terminal.scrollHeight;
}

function adminConnectWs() {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  adminState.ws = new WebSocket(`${proto}://${window.location.host}${BASE}/ws/terminal?token=${auth.token}`);
  adminState.ws.onmessage = (ev) => {
    const data = JSON.parse(ev.data);
    adminHandleWs(data);
  };
  adminState.ws.onclose = () => setTimeout(adminConnectWs, 3000);
}

function adminHandleWs(data) {
  const { type, payload } = data;
  if (type === "terminal") {
    const cls = payload.direction === "TX" ? "tx" : payload.direction === "SYS" ? "sys" : "rx";
    adminAppendTerminal(payload.message, cls);
    return;
  }
  if (type === "telemetry") {
    if (payload.message_type === "sensor") adminUpdateDashboard(payload);
    adminAppendTerminal(payload.raw_message, payload.message_type === "command_ack" ? "sys" : "rx");
    adminRefreshLatest();
    return;
  }
  if (type === "connection") {
    const msg = payload.connected
      ? `[INFO] Conectado IMEI ${payload.imei} (${payload.ip})`
      : `[INFO] Desconectado IMEI ${payload.imei}`;
    adminAppendTerminal(msg, payload.connected ? "sys" : "err");
    adminLoadDevices();
    adminRefreshLatest();
  }
}

function adminUpdateDashboard(payload) {
  if (payload.temperature != null) document.getElementById("valTemp").textContent = `${payload.temperature.toFixed(1)} °C`;
  if (payload.gas_ppm != null) document.getElementById("valGas").textContent = `${payload.gas_ppm}`;
  if (payload.imei) document.getElementById("valImei").textContent = payload.imei;
}

async function adminLoadDevices() {
  const res = await apiFetch("/api/devices");
  const devices = await res.json();
  const sel = document.getElementById("deviceSelect");
  const current = sel.value;
  sel.innerHTML = '<option value="">— seleccionar —</option>';
  devices.forEach((d) => {
    const opt = document.createElement("option");
    opt.value = d.imei;
    opt.textContent = `${d.imei} ${d.is_connected ? "(conectado)" : ""}`;
    sel.appendChild(opt);
  });
  if (current) sel.value = current;
  else if (devices.length === 1) sel.value = devices[0].imei;
  adminUpdateConnectionBadge();
}

function adminSelectedImei() {
  return document.getElementById("deviceSelect").value || null;
}

function adminUpdateConnectionBadge() {
  const imei = adminSelectedImei();
  const badge = document.getElementById("connectionStatus");
  if (!imei) {
    badge.textContent = "● Sin dispositivo";
    badge.className = "status-dot disconnected";
    return;
  }
  apiFetch(`/api/latest?imei=${encodeURIComponent(imei)}`)
    .then((r) => r.json())
    .then((data) => {
      const ok = data.device?.is_connected;
      badge.textContent = ok ? `● Conectado (${imei})` : `● Desconectado (${imei})`;
      badge.className = `status-dot ${ok ? "connected" : "disconnected"}`;
    });
}

async function adminRefreshLatest() {
  const imei = adminSelectedImei();
  const url = imei ? `/api/latest?imei=${encodeURIComponent(imei)}` : "/api/latest";
  const res = await apiFetch(url);
  const data = await res.json();
  if (data.latest_reading) adminUpdateDashboard(data.latest_reading);
  if (data.device) {
    document.getElementById("valLastSeen").textContent = fmtDate(data.device.last_seen_at);
    document.getElementById("valImei").textContent = data.device.imei;
    adminUpdateConnectionBadge();
  }
}

async function adminSendCommand(cmd) {
  const imei = adminSelectedImei();
  if (!imei) {
    adminAppendTerminal("[ERROR] Seleccione un dispositivo", "err");
    return;
  }
  if (!cmd.trim()) return;
  adminState.commandHistory.unshift(cmd);
  adminState.historyIndex = -1;
  try {
    const res = await apiFetch("/api/commands", {
      method: "POST",
      body: JSON.stringify({
        imei,
        command: cmd.trim(),
        append_newline: document.getElementById("appendNewline").checked,
      }),
    });
    const data = await res.json();
    if (!res.ok) adminAppendTerminal(`[ERROR] ${data.detail || "Error"}`, "err");
  } catch (e) {
    adminAppendTerminal(`[ERROR] ${e.message}`, "err");
  }
}

function adminCommandKeydown(e) {
  const input = document.getElementById("commandInput");
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    adminSendCommand(input.value);
    input.value = "";
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    if (adminState.commandHistory.length) {
      adminState.historyIndex = Math.min(adminState.historyIndex + 1, adminState.commandHistory.length - 1);
      input.value = adminState.commandHistory[adminState.historyIndex];
    }
  } else if (e.key === "ArrowDown") {
    e.preventDefault();
    adminState.historyIndex = Math.max(adminState.historyIndex - 1, -1);
    input.value = adminState.historyIndex >= 0 ? adminState.commandHistory[adminState.historyIndex] : "";
  }
}

function adminInitCharts() {
  const opts = { responsive: true, scales: { x: { ticks: { maxTicksLimit: 8 } } } };
  adminState.tempChart = new Chart(document.getElementById("tempChart"), {
    type: "line",
    data: { labels: [], datasets: [{ label: "°C", data: [], borderColor: "#e74c3c", tension: 0.2 }] },
    options: opts,
  });
  adminState.gasChart = new Chart(document.getElementById("gasChart"), {
    type: "line",
    data: { labels: [], datasets: [{ label: "PPM", data: [], borderColor: "#3498db", tension: 0.2 }] },
    options: opts,
  });
}

async function adminLoadChart() {
  const imei = adminSelectedImei();
  if (!imei) return;
  const from = document.getElementById("fromDate").value;
  const to = document.getElementById("toDate").value;
  let url = `/api/chart?imei=${encodeURIComponent(imei)}`;
  if (from) url += `&from=${encodeURIComponent(new Date(from).toISOString())}`;
  if (to) url += `&to=${encodeURIComponent(new Date(to).toISOString())}`;
  const res = await apiFetch(url);
  const data = await res.json();
  updateCharts(adminState.tempChart, adminState.gasChart, data.points);
}

/* ---------- CLIENT ---------- */
const clientState = { ws: null, histTempChart: null, histGasChart: null };

function initClient() {
  document.getElementById("logoutClient").addEventListener("click", logout);
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => clientSwitchTab(tab.dataset.tab));
  });
  document.getElementById("histSearch").addEventListener("click", clientLoadHistory);
  document.getElementById("spSave").addEventListener("click", clientSaveSetpoints);
  document.getElementById("clientDeviceSelect").addEventListener("change", () => {
    clientRefreshLatest();
  });
  document.getElementById("spDeviceSelect").addEventListener("change", clientLoadSetpoints);

  clientInitHistCharts();
  setDefaultDateRange("histFrom", "histTo");
  clientLoadDevices().then(() => {
    clientRefreshLatest();
    clientLoadSetpoints();
  });
  clientConnectWs();
  setInterval(clientRefreshLatest, 10000);
}

function clientSwitchTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  document.getElementById("tabRealtime").classList.toggle("hidden", name !== "realtime");
  document.getElementById("tabHistory").classList.toggle("hidden", name !== "history");
  document.getElementById("tabSetpoints").classList.toggle("hidden", name !== "setpoints");
  if (name === "history") clientLoadHistory();
}

async function clientLoadDevices() {
  const res = await apiFetch("/api/devices");
  const devices = await res.json();
  ["clientDeviceSelect", "histDeviceSelect", "spDeviceSelect"].forEach((id) => {
    const sel = document.getElementById(id);
    const current = sel.value;
    sel.innerHTML = '<option value="">— seleccionar —</option>';
    devices.forEach((d) => {
      const opt = document.createElement("option");
      opt.value = d.imei;
      opt.textContent = `${d.imei} ${d.is_connected ? "(conectado)" : ""}`;
      sel.appendChild(opt);
    });
    if (current) sel.value = current;
    else if (devices.length === 1) sel.value = devices[0].imei;
  });
}

function clientImei() {
  return document.getElementById("clientDeviceSelect").value || null;
}

function clientConnectWs() {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  clientState.ws = new WebSocket(`${proto}://${window.location.host}${BASE}/ws/realtime?token=${auth.token}`);
  clientState.ws.onmessage = (ev) => {
    const data = JSON.parse(ev.data);
    if (data.type === "telemetry" && data.payload.message_type === "sensor") {
      clientUpdateLive(data.payload);
      clientRefreshLatest();
    }
    if (data.type === "connection") {
      clientLoadDevices();
      clientRefreshLatest();
    }
  };
  clientState.ws.onclose = () => setTimeout(clientConnectWs, 3000);
}

function clientUpdateLive(payload) {
  if (payload.temperature != null) document.getElementById("liveTemp").textContent = `${payload.temperature.toFixed(1)} °C`;
  if (payload.gas_ppm != null) document.getElementById("liveGas").textContent = `${payload.gas_ppm}`;
  if (payload.imei) document.getElementById("liveImei").textContent = payload.imei;
  document.getElementById("liveUpdated").textContent = fmtDate(new Date().toISOString());
}

async function clientRefreshLatest() {
  const imei = clientImei();
  if (!imei) return;
  const res = await apiFetch(`/api/latest?imei=${encodeURIComponent(imei)}`);
  const data = await res.json();
  if (data.latest_reading) {
    clientUpdateLive(data.latest_reading);
    document.getElementById("liveUpdated").textContent = fmtDate(data.latest_reading.received_at);
  }
  const badge = document.getElementById("clientConnectionStatus");
  const ok = data.device?.is_connected;
  badge.textContent = ok ? `● Conectado (${imei})` : `● Desconectado (${imei})`;
  badge.className = `status-dot ${ok ? "connected" : "disconnected"}`;
  await clientLoadSetpointsDisplay(imei);
}

async function clientLoadSetpointsDisplay(imei) {
  const res = await apiFetch(`/api/setpoints?imei=${encodeURIComponent(imei)}`);
  const sp = await res.json();
  if (!sp || !sp.imei) {
    document.getElementById("liveTempSp").textContent = "— °C";
    document.getElementById("liveGasSp").textContent = "— PPM";
    return;
  }
  document.getElementById("liveTempSp").textContent = `${sp.temperature.toFixed(1)} °C`;
  document.getElementById("liveGasSp").textContent = `${sp.gas_ppm} PPM`;
  document.getElementById("spTemp").value = sp.temperature;
  document.getElementById("spGas").value = sp.gas_ppm;
}

async function clientLoadSetpoints() {
  const imei = document.getElementById("spDeviceSelect").value || clientImei();
  if (!imei) return;
  document.getElementById("spDeviceSelect").value = imei;
  await clientLoadSetpointsDisplay(imei);
}

async function clientSaveSetpoints() {
  const imei = document.getElementById("spDeviceSelect").value;
  const msg = document.getElementById("spMsg");
  if (!imei) {
    msg.textContent = "Seleccione un dispositivo";
    return;
  }
  const body = {
    imei,
    temperature: parseFloat(document.getElementById("spTemp").value),
    gas_ppm: parseInt(document.getElementById("spGas").value, 10),
    apply_to_device: document.getElementById("spApply").checked,
  };
  try {
    const res = await apiFetch("/api/setpoints", { method: "POST", body: JSON.stringify(body) });
    const data = await res.json();
    if (!res.ok) {
      msg.textContent = data.detail || "Error al guardar";
      return;
    }
    msg.textContent = data.applied
      ? "Set points guardados y enviados al dispositivo"
      : "Set points guardados (dispositivo no conectado o no enviado)";
    clientLoadSetpointsDisplay(imei);
  } catch (e) {
    msg.textContent = e.message;
  }
}

function clientInitHistCharts() {
  const opts = { responsive: true, scales: { x: { ticks: { maxTicksLimit: 8 } } } };
  clientState.histTempChart = new Chart(document.getElementById("histTempChart"), {
    type: "line",
    data: { labels: [], datasets: [{ label: "°C", data: [], borderColor: "#e74c3c", tension: 0.2 }] },
    options: opts,
  });
  clientState.histGasChart = new Chart(document.getElementById("histGasChart"), {
    type: "line",
    data: { labels: [], datasets: [{ label: "PPM", data: [], borderColor: "#3498db", tension: 0.2 }] },
    options: opts,
  });
}

async function clientLoadHistory() {
  const imei = document.getElementById("histDeviceSelect").value || clientImei();
  if (!imei) return;
  const from = document.getElementById("histFrom").value;
  const to = document.getElementById("histTo").value;
  let chartUrl = `/api/chart?imei=${encodeURIComponent(imei)}`;
  let readUrl = `/api/readings?imei=${encodeURIComponent(imei)}&message_type=sensor&limit=200`;
  if (from) {
    const iso = new Date(from).toISOString();
    chartUrl += `&from=${encodeURIComponent(iso)}`;
    readUrl += `&from=${encodeURIComponent(iso)}`;
  }
  if (to) {
    const iso = new Date(to).toISOString();
    chartUrl += `&to=${encodeURIComponent(iso)}`;
    readUrl += `&to=${encodeURIComponent(iso)}`;
  }
  const [chartRes, readRes] = await Promise.all([apiFetch(chartUrl), apiFetch(readUrl)]);
  const chartData = await chartRes.json();
  const rows = await readRes.json();
  updateCharts(clientState.histTempChart, clientState.histGasChart, chartData.points);
  const tbody = document.getElementById("histTableBody");
  tbody.innerHTML = "";
  rows.forEach((r) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${fmtDate(r.received_at)}</td><td>${r.temperature ?? "—"}</td><td>${r.gas_ppm ?? "—"}</td><td>${r.ip ?? "—"}</td>`;
    tbody.appendChild(tr);
  });
}

/* ---------- SHARED ---------- */
function updateCharts(tempChart, gasChart, points) {
  const labels = points.map((p) => fmtDate(p.timestamp));
  tempChart.data.labels = labels;
  tempChart.data.datasets[0].data = points.map((p) => p.temperature);
  tempChart.update();
  gasChart.data.labels = labels;
  gasChart.data.datasets[0].data = points.map((p) => p.gas_ppm);
  gasChart.update();
}

function setDefaultDateRange(fromId, toId) {
  const now = new Date();
  const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);
  document.getElementById(fromId).value = yesterday.toISOString().slice(0, 16);
  document.getElementById(toId).value = now.toISOString().slice(0, 16);
}

if (auth.token && auth.role) {
  bootApp();
}
