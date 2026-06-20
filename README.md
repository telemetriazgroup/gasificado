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
./start.sh             # recomendado: libera el puerto 9970 y levanta todo
```

Acceso web: **http://localhost:8087/gasificado/**

### Usuarios

| Rol | Usuario | Contraseña | Permisos |
|-----|---------|------------|----------|
| Administrador | `admin` | `ProyectoZtrack2026!` | Terminal serial, comandos TCP, gráficas |
| Cliente | `gasificado` | `gasificado2026` | Tiempo real, histórico, set points |

### Zona horaria

Los datos TCP se registran en **GMT-5 (America/Bogota)**. Las fechas en API e interfaz se muestran en esa zona.


El error `address already in use` en el puerto 9970 ocurre cuando ya hay otro proceso escuchando, por ejemplo:

- Un contenedor `tcp_bridge` anterior que no se detuvo
- El script legacy `tcp_g9070.py` ejecutándose fuera de Docker
- Un reinicio de Docker que dejó el puerto colgado

**Solución integrada:** antes de levantar `tcp_bridge`, el servicio `port_cleaner` ejecuta `scripts/free_port.sh`, que:

1. Detiene contenedores Docker que publican el puerto 9970
2. Termina procesos host como `tcp_g9070.py` o instancias sueltas de `bridge.py`
3. Libera el puerto con `fuser`/`lsof` si sigue ocupado
4. Espera hasta confirmar que el puerto quedó libre

Solo después de eso arranca `tcp_bridge`. Usar `./start.sh` aplica la misma limpieza también desde el host.

- **Web UI:** http://localhost:8087/gasificado/
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


Rol	Usuario	Contraseña	Qué ve
Administrador
admin
ProyectoZtrack2026!
Terminal serial, comandos TCP, gráficas
Cliente
gasificado
gasificado2026
Tiempo real, histórico, set points (sin serial)