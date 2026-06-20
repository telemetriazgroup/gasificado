mport socket
import threading
import datetime
import os
import json
import requests

# --- Configuración ---
HOST = '0.0.0.0'
PORT = 9970

API_URL  = "http://161.132.53.51:9050/TermoKing/"      # API principal
API_URL2 = "http://161.132.206.104:9050/Datos/"        # API adicional

def guardar_en_archivo(mensaje, timestamp):
    fecha_actual = timestamp.strftime("%d_%m_%Y")
    nombre_archivo = f"gas_{fecha_actual}.txt"
    hora = timestamp.strftime("%H:%M:%S")
    linea = f"[{hora}] {mensaje}\n"
    with open(nombre_archivo, "a", encoding="utf-8") as archivo:
        archivo.write(linea)

def procesar_json(mensaje_json, conn):
    """
    Envía el JSON a API_URL y API_URL2.
    Responde al cliente solo con API_URL.
    """

    # ---- 1. Enviar a API principal (TermoKing) ----
    respuesta_api1 = "sin envio"

    try:
        response = requests.post(API_URL, json=mensaje_json, timeout=5)
        print(f"🌐 API 1 (TermoKing) respondió: {response.text}")
        respuesta_api1 = response.text
    except Exception as e:
        print(f"❌ Error enviando a API 1: {e}")

    # ---- 2. Enviar a API secundaria (Datos) ----
    try:
        response2 = requests.post(API_URL2, json=mensaje_json, timeout=5)
        print(f"📡 API 2 (Datos) respondió: {response2.text}")
    except Exception as e:
        print(f"❌ Error enviando a API 2: {e}")

    # ---- 3. Enviar al cliente SOLO lo de la API 1 ----
    try:
        conn.sendall(respuesta_api1.encode('utf-8'))
    except:
        print("⚠️ No se pudo devolver respuesta al cliente.")


def handle_client(conn, addr):
    client_ip, client_port = addr
    print(f"✅ Cliente conectado: {client_ip}:{client_port}")

    buffer = ""
    timestamp_inicio = datetime.datetime.now()

    try:
        while True:
            data = conn.recv(1024)

            if not data:
                print(f"🔌 Cliente {client_ip}:{client_port} desconectado.")
                break

            chunk = data.decode('utf-8', errors='replace')
            timestamp = datetime.datetime.now()
            guardar_en_archivo(chunk, timestamp)

            buffer += chunk

            # ---- Procesar múltiples JSON si vienen juntos ----
            while "{" in buffer and "}" in buffer:
                inicio = buffer.index("{")
                fin = buffer.index("}") + 1

                json_str = buffer[inicio:fin]

                try:
                    mensaje_json = json.loads(json_str)
                    print("📦 JSON válido:", mensaje_json)

                    # Procesar el JSON → enviar a ambas APIs
                    procesar_json(mensaje_json, conn)

                except json.JSONDecodeError:
                    print("⚠ JSON inválido:", json_str)

                # Limpiar buffer
                buffer = buffer[fin:]

    except Exception as e:
        print(f"❌ Error inesperado {client_ip}:{client_port}: {e}")

    finally:
        conn.close()
        print(f"📤 Conexión cerrada ({client_ip}) — Sesión iniciada en {timestamp_inicio}")


def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    print(f" Servidor escuchando en {HOST}:{PORT}")
    while True:
        conn, addr = server_socket.accept()
        threading.Thread(target=handle_client, args=(conn, addr)).start()


if __name__ == "__main__":
    start_server()
