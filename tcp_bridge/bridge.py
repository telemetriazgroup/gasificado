"""
Puente TCP para gasificadores.
Escucha conexiones en el puerto 9970, parsea telemetría y la envía al backend.
Expone API interna para enviar comandos al dispositivo conectado.
"""

import asyncio
import datetime
import os
import re
import socket
import threading
from contextlib import asynccontextmanager
from zoneinfo import ZoneInfo

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

LOCAL_TZ = ZoneInfo("America/Bogota")

HOST = os.getenv("TCP_HOST", "0.0.0.0")
PORT = int(os.getenv("TCP_PORT", "9970"))
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
HTTP_PORT = int(os.getenv("HTTP_PORT", "8081"))
LEGACY_API_URL = os.getenv("LEGACY_API_URL", "")
LEGACY_API_URL2 = os.getenv("LEGACY_API_URL2", "")

SENSOR_PATTERN = re.compile(
    r"I:(?P<imei>\d+),P:(?P<ip>[\d.]+),(?P<temp>\d+),(?P<ppm>\d+)"
)


class ConnectionRegistry:
    def __init__(self):
        self._by_imei: dict[str, socket.socket] = {}
        self._imei_by_addr: dict[tuple, str] = {}
        self._conn_by_addr: dict[tuple, socket.socket] = {}
        self._lock = threading.Lock()

    def register_pending(self, addr, conn):
        with self._lock:
            self._conn_by_addr[addr] = conn

    def register(self, addr, conn, imei: str):
        with self._lock:
            old = self._by_imei.get(imei)
            if old and old is not conn:
                try:
                    old.close()
                except OSError:
                    pass
            self._by_imei[imei] = conn
            self._imei_by_addr[addr] = imei
            self._conn_by_addr[addr] = conn

    def unregister(self, addr, conn):
        with self._lock:
            imei = self._imei_by_addr.pop(addr, None)
            self._conn_by_addr.pop(addr, None)
            if imei and self._by_imei.get(imei) is conn:
                del self._by_imei[imei]
            return imei

    def get(self, imei: str):
        with self._lock:
            conn = self._by_imei.get(imei)
            if conn:
                return conn
            # Un solo socket TCP activo: usarlo aunque aún no llegó telemetría con IMEI
            if len(self._conn_by_addr) == 1:
                return next(iter(self._conn_by_addr.values()))
            return None

    def list_connected(self):
        with self._lock:
            return list(self._by_imei.keys())

    def active_sessions(self) -> int:
        with self._lock:
            return len(self._conn_by_addr)

    def can_send(self, imei: str) -> bool:
        return self.get(imei) is not None


registry = ConnectionRegistry()


def parse_chunks(text: str) -> list[dict]:
    results = []
    for line in re.split(r"[\r\n]+", text):
        line = line.strip()
        if not line:
            continue
        match = SENSOR_PATTERN.search(line)
        if match:
            results.append(
                {
                    "imei": match.group("imei"),
                    "ip": match.group("ip"),
                    "temperature": int(match.group("temp")) / 10.0,
                    "gas_ppm": int(match.group("ppm")),
                    "raw_message": line,
                    "message_type": "sensor",
                }
            )
            continue
        upper = line.upper()
        if "COMANDO OK" in upper:
            results.append(
                {
                    "imei": None,
                    "ip": None,
                    "temperature": None,
                    "gas_ppm": None,
                    "raw_message": "COMANDO EJECUTADO",
                    "message_type": "command_ack",
                }
            )
        else:
            results.append(
                {
                    "imei": None,
                    "ip": None,
                    "temperature": None,
                    "gas_ppm": None,
                    "raw_message": line,
                    "message_type": "raw",
                }
            )
    return results


def local_timestamp_iso():
    return datetime.datetime.now(LOCAL_TZ).isoformat()


def local_time_hms():
    return datetime.datetime.now(LOCAL_TZ).strftime("%H:%M:%S")


def post_sync(url: str, payload: dict):
    try:
        with httpx.Client(timeout=5) as client:
            return client.post(url, json=payload)
    except Exception as exc:
        print(f"Error POST {url}: {exc}")
        return None


def notify_backend_telemetry(parsed: dict, client_ip: str):
    payload = {
        **parsed,
        "client_ip": client_ip,
        "timestamp": local_timestamp_iso(),
    }
    if parsed.get("imei"):
        post_sync(
            f"{BACKEND_URL}/api/internal/connection",
            {
                "imei": parsed["imei"],
                "ip": parsed.get("ip") or client_ip,
                "connected": True,
            },
        )
    post_sync(f"{BACKEND_URL}/api/internal/telemetry", payload)


def notify_backend_terminal(imei: str | None, direction: str, message: str):
    post_sync(
        f"{BACKEND_URL}/api/internal/terminal",
        {
            "imei": imei,
            "direction": direction,
            "message": message,
            "timestamp": local_timestamp_iso(),
        },
    )


def notify_disconnect(imei: str | None, client_ip: str):
    if imei:
        post_sync(
            f"{BACKEND_URL}/api/internal/connection",
            {"imei": imei, "ip": client_ip, "connected": False},
        )
        notify_backend_terminal(imei, "SYS", f"[INFO] Dispositivo {imei} desconectado")


def send_to_legacy_apis(parsed: dict):
    if not parsed.get("imei") or parsed.get("message_type") != "sensor":
        return
    legacy = {
        "imei": parsed["imei"],
        "ip": parsed["ip"],
        "temperatura": parsed["temperature"],
        "gas_ppm": parsed["gas_ppm"],
        "raw": parsed["raw_message"],
    }
    if LEGACY_API_URL:
        post_sync(LEGACY_API_URL, legacy)
    if LEGACY_API_URL2:
        post_sync(LEGACY_API_URL2, legacy)


def handle_client(conn: socket.socket, addr):
    client_ip, client_port = addr
    print(f"Cliente conectado: {client_ip}:{client_port}")
    registry.register_pending(addr, conn)
    notify_backend_terminal(None, "SYS", f"[INFO] Cliente conectado {client_ip}:{client_port}")

    buffer = ""
    imei = None

    def process_text(text: str):
        nonlocal imei
        timestamp = local_time_hms()
        for parsed in parse_chunks(text):
            if parsed.get("imei"):
                imei = parsed["imei"]
                registry.register(addr, conn, imei)
            raw = parsed["raw_message"]
            notify_backend_terminal(imei, "RX", f"[{timestamp}] {raw}")
            notify_backend_telemetry({**parsed, "imei": parsed.get("imei") or imei}, client_ip)
            send_to_legacy_apis(parsed)

    try:
        while True:
            data = conn.recv(4096)
            if not data:
                break

            buffer += data.decode("utf-8", errors="replace")

            while True:
                for sep in ("\r\n", "\n", "\r"):
                    if sep in buffer:
                        line, buffer = buffer.split(sep, 1)
                        if line.strip():
                            process_text(line)
                        break
                else:
                    if buffer.strip() and SENSOR_PATTERN.search(buffer):
                        process_text(buffer)
                        buffer = ""
                    break

    except Exception as exc:
        print(f"Error cliente {client_ip}: {exc}")
        notify_backend_terminal(imei, "SYS", f"[ERROR] {exc}")
    finally:
        disconnected_imei = registry.unregister(addr, conn)
        notify_disconnect(disconnected_imei or imei, client_ip)
        conn.close()
        print(f"Conexión cerrada: {client_ip}")


def tcp_server_loop():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(10)
    print(f"TCP escuchando en {HOST}:{PORT}")
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()


class SendCommand(BaseModel):
    imei: str
    command: str
    append_newline: bool = True


@asynccontextmanager
async def lifespan(_app: FastAPI):
    post_sync(f"{BACKEND_URL}/api/internal/disconnect_all", {})
    threading.Thread(target=tcp_server_loop, daemon=True).start()
    yield


app = FastAPI(title="TCP Bridge", lifespan=lifespan)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "connected_devices": registry.list_connected(),
        "active_sessions": registry.active_sessions(),
    }


@app.get("/internal/status")
def status():
    return {
        "connected": registry.list_connected(),
        "active_sessions": registry.active_sessions(),
    }


@app.get("/internal/can_send")
def can_send(imei: str):
    return {
        "imei": imei,
        "ready": registry.can_send(imei),
        "connected": registry.list_connected(),
        "active_sessions": registry.active_sessions(),
    }


@app.post("/internal/send")
def send_command(body: SendCommand):
    conn = registry.get(body.imei)
    if not conn:
        raise HTTPException(
            status_code=409,
            detail=f"Dispositivo {body.imei} no conectado al puente TCP (sin sesión activa)",
        )

    payload = body.command + ("\n" if body.append_newline else "")
    try:
        conn.sendall(payload.encode("utf-8"))
        ts = local_time_hms()
        notify_backend_terminal(body.imei, "TX", f"[{ts}] {body.command}")
        return {"success": True, "message": "Comando enviado"}
    except OSError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=HTTP_PORT)
