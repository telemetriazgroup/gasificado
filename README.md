# Gasificado - Monitor TCP

Sistema dockerizado para recibir telemetría de gasificadores por TCP (puerto 9970), almacenar datos, consultar históricos y enviar comandos desde una interfaz web tipo terminal serial.

## Arquitectura

```
Dispositivo ──TCP:9970──► tcp_bridge ──HTTP──► backend ──► PostgreSQL
                              │                    ▲
                              │                    │
                              └──── WebSocket ─────┘
                                        ▲
                                   frontend:8087
```

## Formato de datos

Telemetría: `I:866029036991554,P:100.66.34.12,397,0`

| Campo | Significado |
|-------|-------------|
| I: | IMEI del dispositivo |
| P: | IP de comunicación |
| 397 | Temperatura ×10 (39.7 °C) |
| 0 | Gas en PPM |

Respuestas de comando: `COMANDO OK` → registrado como `COMANDO EJECUTADO`

## Comandos disponibles

| Comando | Descripción |
|---------|-------------|
| EVAPORADOR_ON | Activar ventilación interna |
| EVAPORADOR_OFF | Apagar ventilación interna |
| DOOR_CLOSE | Cerrar evacuación de gases |
| DOOR_OPEN | Abrir evacuación de gases |
| DOOR_STOP | Detener evacuación de gases |
| INYECCION | Inyección de gas a la cámara |
| GET_DATA | Solicitar lectura de sensores |

## Inicio rápido

```bash
cp .env.example .env   # opcional: APIs legacy
docker compose up -d --build
```

- **Web UI:** http://localhost:8087
- **Backend API:** http://localhost:9070
- **TCP dispositivos:** puerto 9970
- **API REST (vía web):** http://localhost:8087/api/
- **API REST (directa):** http://localhost:9070/api/

## Endpoints API

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/devices` | Lista dispositivos |
| GET | `/api/latest?imei=` | Último dato y conexión |
| GET | `/api/readings?imei=&from=&to=` | Histórico por rango |
| GET | `/api/chart?imei=&from=&to=` | Datos para gráficas |
| POST | `/api/commands` | Enviar comando al dispositivo |
| WS | `/ws/terminal` | Terminal en tiempo real |

## Servicios

- `tcp_bridge` — Reemplaza `tcp_g9070.py`. Escucha TCP, parsea datos y reenvía al backend.
- `backend` — API FastAPI + PostgreSQL + WebSocket.
- `frontend` — Interfaz web con terminal, botones de comando y gráficas.
- `db` — PostgreSQL para trazabilidad.

## Nota sobre tcp_g9070.py

El script original sigue en el repositorio como referencia. En producción usar `tcp_bridge` dentro de Docker, que conserva el envío opcional a las APIs legacy configuradas en `.env`.
# gasificado
