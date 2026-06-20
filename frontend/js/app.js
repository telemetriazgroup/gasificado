const API = window.location.origin;
const WS_URL = `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/ws/terminal`;

const terminal = document.getElementById("terminal");
const deviceSelect = document.getElementById("deviceSelect");
const connectionStatus = document.getElementById("connectionStatus");
const commandInput = document.getElementById("commandInput");
const showTime = document.getElementById("showTime");
const appendNewline = document.getElementById("appendNewline");

let commandHistory = [];
let historyIndex = -1;
let tempChart = null;
let gasChart = null;
let ws = null;

function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("es-AR");
}

function selectedImei() {
  return deviceSelect.value || null;
}

function appendTerminal(text, cls = "rx") {
  const line = document.createElement("div");
  line.className = cls;
  line.textContent = text;
  terminal.appendChild(line);
  terminal.scrollTop = terminal.scrollHeight;
}

function connectWs() {
  if (ws) ws.close();
  ws = new WebSocket(WS_URL);

  ws.onmessage = (ev) => {
    const data = JSON.parse(ev.data);
    handleWsEvent(data);
  };

  ws.onclose = () => {
    setTimeout(connectWs, 3000);
  };
}

function handleWsEvent(data) {
  const { type, payload } = data;

  if (type === "terminal") {
    const cls = payload.direction === "TX" ? "tx" : payload.direction === "SYS" ? "sys" : "rx";
    appendTerminal(payload.message, cls);
    return;
  }

  if (type === "telemetry") {
    if (payload.message_type === "sensor") {
      updateDashboardValues(payload);
      if (showTime.checked) {
        appendTerminal(payload.raw_message, "rx");
      } else {
        appendTerminal(payload.raw_message, "rx");
      }
    } else if (payload.message_type === "command_ack") {
      appendTerminal(payload.raw_message, "sys");
    } else {
      appendTerminal(payload.raw_message, "rx");
    }
    refreshLatest();
    return;
  }

  if (type === "connection") {
    const msg = payload.connected
      ? `[INFO] Conectado IMEI ${payload.imei} (${payload.ip})`
      : `[INFO] Desconectado IMEI ${payload.imei}`;
    appendTerminal(msg, payload.connected ? "sys" : "err");
    loadDevices();
    refreshLatest();
  }
}

function updateDashboardValues(payload) {
  if (payload.temperature != null) {
    document.getElementById("valTemp").textContent = `${payload.temperature.toFixed(1)} °C`;
  }
  if (payload.gas_ppm != null) {
    document.getElementById("valGas").textContent = `${payload.gas_ppm}`;
  }
  if (payload.imei) {
    document.getElementById("valImei").textContent = payload.imei;
  }
}

async function loadDevices() {
  const res = await fetch(`${API}/api/devices`);
  const devices = await res.json();
  const current = selectedImei();
  deviceSelect.innerHTML = '<option value="">— seleccionar —</option>';
  devices.forEach((d) => {
    const opt = document.createElement("option");
    opt.value = d.imei;
    opt.textContent = `${d.imei} ${d.is_connected ? "(conectado)" : ""}`;
    deviceSelect.appendChild(opt);
  });
  if (current) deviceSelect.value = current;
  else if (devices.length === 1) deviceSelect.value = devices[0].imei;
  updateConnectionBadge();
}

function updateConnectionBadge() {
  const imei = selectedImei();
  if (!imei) {
    connectionStatus.textContent = "● Sin dispositivo";
    connectionStatus.className = "status-dot disconnected";
    return;
  }
  fetch(`${API}/api/latest?imei=${encodeURIComponent(imei)}`)
    .then((r) => r.json())
    .then((data) => {
      const connected = data.device?.is_connected;
      connectionStatus.textContent = connected
        ? `● Conectado (${imei})`
        : `● Desconectado (${imei})`;
      connectionStatus.className = `status-dot ${connected ? "connected" : "disconnected"}`;
    });
}

async function refreshLatest() {
  const imei = selectedImei();
  const url = imei ? `${API}/api/latest?imei=${encodeURIComponent(imei)}` : `${API}/api/latest`;
  const res = await fetch(url);
  const data = await res.json();
  if (data.latest_reading) {
    updateDashboardValues(data.latest_reading);
  }
  if (data.device) {
    document.getElementById("valLastSeen").textContent = fmtDate(data.device.last_seen_at);
    document.getElementById("valImei").textContent = data.device.imei;
    updateConnectionBadge();
  }
}

async function sendCommand(cmd) {
  const imei = selectedImei();
  if (!imei) {
    appendTerminal("[ERROR] Seleccione un dispositivo", "err");
    return;
  }
  if (!cmd.trim()) return;

  commandHistory.unshift(cmd);
  historyIndex = -1;

  try {
    const res = await fetch(`${API}/api/commands`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        imei,
        command: cmd.trim(),
        append_newline: appendNewline.checked,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      appendTerminal(`[ERROR] ${data.detail || "Error al enviar"}`, "err");
    }
  } catch (e) {
    appendTerminal(`[ERROR] ${e.message}`, "err");
  }
}

function initCharts() {
  const common = {
    responsive: true,
    scales: {
      x: { ticks: { maxTicksLimit: 8 } },
    },
  };
  tempChart = new Chart(document.getElementById("tempChart"), {
    type: "line",
    data: { labels: [], datasets: [{ label: "°C", data: [], borderColor: "#e74c3c", tension: 0.2 }] },
    options: common,
  });
  gasChart = new Chart(document.getElementById("gasChart"), {
    type: "line",
    data: { labels: [], datasets: [{ label: "PPM", data: [], borderColor: "#3498db", tension: 0.2 }] },
    options: common,
  });
}

async function loadChartData() {
  const imei = selectedImei();
  if (!imei) return;

  const from = document.getElementById("fromDate").value;
  const to = document.getElementById("toDate").value;
  let url = `${API}/api/chart?imei=${encodeURIComponent(imei)}`;
  if (from) url += `&from=${encodeURIComponent(new Date(from).toISOString())}`;
  if (to) url += `&to=${encodeURIComponent(new Date(to).toISOString())}`;

  const res = await fetch(url);
  const data = await res.json();
  const labels = data.points.map((p) => new Date(p.timestamp).toLocaleTimeString("es-AR"));
  tempChart.data.labels = labels;
  tempChart.data.datasets[0].data = data.points.map((p) => p.temperature);
  tempChart.update();
  gasChart.data.labels = labels;
  gasChart.data.datasets[0].data = data.points.map((p) => p.gas_ppm);
  gasChart.update();
}

function setDefaultDateRange() {
  const now = new Date();
  const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);
  document.getElementById("fromDate").value = yesterday.toISOString().slice(0, 16);
  document.getElementById("toDate").value = now.toISOString().slice(0, 16);
}

document.getElementById("refreshDevices").addEventListener("click", loadDevices);
document.getElementById("clearTerminal").addEventListener("click", () => {
  terminal.innerHTML = "";
});
document.getElementById("clearInput").addEventListener("click", () => {
  commandInput.value = "";
});
document.getElementById("sendCommand").addEventListener("click", () => {
  sendCommand(commandInput.value);
  commandInput.value = "";
});
document.querySelectorAll(".quick-cmd").forEach((btn) => {
  btn.addEventListener("click", () => sendCommand(btn.dataset.cmd));
});
document.getElementById("loadChart").addEventListener("click", loadChartData);
deviceSelect.addEventListener("change", () => {
  refreshLatest();
  loadChartData();
});

commandInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendCommand(commandInput.value);
    commandInput.value = "";
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    if (commandHistory.length) {
      historyIndex = Math.min(historyIndex + 1, commandHistory.length - 1);
      commandInput.value = commandHistory[historyIndex];
    }
  } else if (e.key === "ArrowDown") {
    e.preventDefault();
    historyIndex = Math.max(historyIndex - 1, -1);
    commandInput.value = historyIndex >= 0 ? commandHistory[historyIndex] : "";
  }
});

setDefaultDateRange();
initCharts();
connectWs();
loadDevices().then(() => {
  refreshLatest();
  loadChartData();
});
setInterval(refreshLatest, 15000);
