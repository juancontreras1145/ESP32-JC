# =========================================
# ESP32 JC - Monitor ambiental robusto
# =========================================
# Requisitos:
# - lcd.py compatible con clase LCD
# - LCD I2C en SDA=8, SCL=9
# - DHT22 en GPIO4
# - WiFi ya conectado desde boot.py
#
# Funciones:
# - Lee temperatura y humedad
# - Muestra datos en LCD
# - Mantiene servidor web activo
# - Guarda CSV local
# - Permite descargar CSV
# - No se cae si el sensor falla
# - Reintenta y muestra errores
# =========================================

import time
import socket
import network
import dht
import os
import gc

from machine import Pin, I2C

# =========================================
# CONFIG GENERAL
# =========================================
VERSION = "APP v3.0"

# LCD
LCD_SDA = 8
LCD_SCL = 9
LCD_ADDR = 0x27

# Sensor
DHT_PIN = 4

# Archivo CSV
CSV_FILE = "temperaturas.csv"

# Tiempos
SAVE_INTERVAL = 600          # cada 10 min
LCD_BOOT_DELAY = 2           # segundos
WEB_TIMEOUT = 1              # accept timeout
SENSOR_RETRY_DELAY = 2       # segundos
WIFI_RETRY_INTERVAL = 15     # segundos

# =========================================
# VARIABLES DE ESTADO
# =========================================
start_time = time.time()
last_save = 0
last_wifi_retry = 0

current_temp = None
current_hum = None

sensor_ok = False
sensor_error = "Sin lectura"

ip_addr = "Sin WiFi"

lcd = None
server = None
sensor = None

# =========================================
# LCD
# =========================================
def init_lcd():
    global lcd
    try:
        from lcd import LCD

        i2c = I2C(0, sda=Pin(LCD_SDA), scl=Pin(LCD_SCL))
        lcd = LCD(i2c, LCD_ADDR)

        # Si tu lcd.py tiene reinit(), úsalo
        try:
            lcd.reinit()
        except:
            pass

        time.sleep_ms(200)
        lcd.clear()
        return True

    except Exception as e:
        print("LCD init error:", e)
        lcd = None
        return False


def lcd_msg(line1="", line2=""):
    global lcd

    if lcd is None:
        return

    try:
        lcd.clear()
        time.sleep_ms(5)
        lcd.move_to(0, 0)
        lcd.putstr(str(line1)[:16])
        lcd.move_to(0, 1)
        lcd.putstr(str(line2)[:16])

    except Exception as e:
        print("LCD error:", e)

        # Reintento automático si el LCD se corrompe
        try:
            init_lcd()
            if lcd:
                lcd.clear()
                lcd.move_to(0, 0)
                lcd.putstr(str(line1)[:16])
                lcd.move_to(0, 1)
                lcd.putstr(str(line2)[:16])
        except Exception as e2:
            print("LCD recovery error:", e2)


# =========================================
# WIFI
# =========================================
def wifi_status():
    wlan = network.WLAN(network.STA_IF)
    return wlan.isconnected()


def wifi_ip():
    wlan = network.WLAN(network.STA_IF)
    if wlan.isconnected():
        return wlan.ifconfig()[0]
    return "Sin WiFi"


def wifi_recheck():
    global ip_addr, last_wifi_retry

    now = time.time()

    if now - last_wifi_retry < WIFI_RETRY_INTERVAL:
        return

    last_wifi_retry = now
    ip_addr = wifi_ip()


# =========================================
# SENSOR
# =========================================
def init_sensor():
    global sensor
    try:
        sensor = dht.DHT22(Pin(DHT_PIN))
        return True
    except Exception as e:
        print("Sensor init error:", e)
        sensor = None
        return False


def read_sensor():
    global current_temp, current_hum, sensor_ok, sensor_error, sensor

    if sensor is None:
        if not init_sensor():
            sensor_ok = False
            sensor_error = "No inicia sensor"
            return False

    try:
        sensor.measure()
        current_temp = round(sensor.temperature(), 1)
        current_hum = round(sensor.humidity(), 1)

        sensor_ok = True
        sensor_error = "Ninguno"
        return True

    except Exception as e:
        sensor_ok = False
        sensor_error = str(e)
        print("Sensor read error:", e)
        return False


# =========================================
# CSV
# =========================================
def ensure_csv():
    try:
        if CSV_FILE not in os.listdir():
            with open(CSV_FILE, "w") as f:
                f.write("epoch,temperatura,humedad\n")
    except Exception as e:
        print("CSV init error:", e)


def save_csv(temp, hum):
    try:
        with open(CSV_FILE, "a") as f:
            f.write("{},{:.1f},{:.1f}\n".format(time.time(), temp, hum))
        return True
    except Exception as e:
        print("CSV save error:", e)
        return False


def read_csv_text():
    try:
        with open(CSV_FILE, "r") as f:
            return f.read()
    except Exception as e:
        return "Error leyendo CSV: {}".format(e)


# =========================================
# INFO SISTEMA
# =========================================
def uptime_text():
    secs = int(time.time() - start_time)
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    return "{:02d}:{:02d}:{:02d}".format(h, m, s)


def sensor_state_text():
    return "OK" if sensor_ok else "ERROR"


def fmt_temp():
    if current_temp is None:
        return "--.-"
    return "{:.1f}".format(current_temp)


def fmt_hum():
    if current_hum is None:
        return "--.-"
    return "{:.1f}".format(current_hum)


# =========================================
# WEB
# =========================================
def build_web():
    status_class = "ok" if sensor_ok else "bad"

    return """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta http-equiv="refresh" content="15">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>ESP32 JC Monitor</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            background: #0f172a;
            color: #f8fafc;
            margin: 0;
            padding: 16px;
        }}
        .wrap {{
            max-width: 960px;
            margin: auto;
        }}
        .card {{
            background: #111827;
            border: 1px solid #334155;
            border-radius: 16px;
            padding: 16px;
            margin-bottom: 16px;
        }}
        .title {{
            font-size: 28px;
            font-weight: bold;
            margin-bottom: 8px;
        }}
        .muted {{
            color: #94a3b8;
            font-size: 14px;
            margin-bottom: 4px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
        }}
        .big {{
            font-size: 40px;
            font-weight: bold;
            margin-top: 8px;
        }}
        .ok {{
            color: #22c55e;
            font-weight: bold;
        }}
        .bad {{
            color: #ef4444;
            font-weight: bold;
        }}
        .btn {{
            display: inline-block;
            padding: 12px 16px;
            background: #22c55e;
            color: #052e16;
            text-decoration: none;
            border-radius: 10px;
            font-weight: bold;
            margin-right: 8px;
            margin-top: 8px;
        }}
        .mono {{
            font-family: monospace;
            background: #020617;
            padding: 10px;
            border-radius: 10px;
            overflow-x: auto;
        }}
        @media (max-width: 700px) {{
            .grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="wrap">

        <div class="card">
            <div class="title">ESP32 JC Monitor</div>
            <div class="muted">Version: {version}</div>
            <div class="muted">IP: {ip}</div>
            <div class="muted">Uptime: {uptime}</div>
            <div class="muted">Estado sensor: <span class="{status_class}">{sensor_state}</span></div>
            <div class="muted">Ultimo error sensor: {sensor_error}</div>
        </div>

        <div class="grid">
            <div class="card">
                <div class="muted">Temperatura actual</div>
                <div class="big">{temp} °C</div>
            </div>

            <div class="card">
                <div class="muted">Humedad actual</div>
                <div class="big">{hum} %</div>
            </div>
        </div>

        <div class="card">
            <div class="title" style="font-size:20px;">Acciones</div>
            <a class="btn" href="/download">Descargar CSV</a>
            <a class="btn" href="/">Actualizar pagina</a>
        </div>

        <div class="card">
            <div class="title" style="font-size:20px;">Archivo local</div>
            <div class="mono">{csv}</div>
        </div>

    </div>
</body>
</html>
""".format(
        version=VERSION,
        ip=ip_addr,
        uptime=uptime_text(),
        status_class=status_class,
        sensor_state=sensor_state_text(),
        sensor_error=sensor_error,
        temp=fmt_temp(),
        hum=fmt_hum(),
        csv=CSV_FILE
    )


def init_server():
    global server

    try:
        addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
        server = socket.socket()
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(addr)
        server.listen(5)
        server.settimeout(WEB_TIMEOUT)
        print("Servidor web listo")
        return True

    except Exception as e:
        print("Server init error:", e)
        server = None
        return False


def handle_web():
    global server

    if server is None:
        return

    try:
        cl, addr = server.accept()
    except OSError:
        return
    except Exception as e:
        print("accept error:", e)
        return

    try:
        req = cl.recv(1024)
        req = str(req)

        if "/download" in req:
            data = read_csv_text()
            cl.send("HTTP/1.0 200 OK\r\n")
            cl.send("Content-Type: text/plain\r\n")
            cl.send("Content-Disposition: attachment; filename={}\r\n\r\n".format(CSV_FILE))
            cl.send(data)
        else:
            response = build_web()
            cl.send("HTTP/1.0 200 OK\r\n")
            cl.send("Content-Type: text/html\r\n\r\n")
            cl.send(response)

    except Exception as e:
        print("web handler error:", e)

    try:
        cl.close()
    except:
        pass


# =========================================
# ARRANQUE
# =========================================
gc.collect()

init_lcd()
lcd_msg("ESP32 JC", VERSION)
time.sleep(LCD_BOOT_DELAY)

lcd_msg("Iniciando", "sensor...")
time.sleep(LCD_BOOT_DELAY)

init_sensor()
ensure_csv()
wifi_recheck()
init_server()

lcd_msg("Web lista", ip_addr[:16])
time.sleep(LCD_BOOT_DELAY)

# lectura inicial
if read_sensor():
    lcd_msg("Temp {}C".format(fmt_temp()), "Hum {}%".format(fmt_hum()))
else:
    lcd_msg("Sensor Error", "sin lectura")

time.sleep(LCD_BOOT_DELAY)

last_save = time.time()

# =========================================
# LOOP PRINCIPAL
# =========================================
while True:
    try:
        gc.collect()

        # Mantener IP actualizada
        wifi_recheck()

        # Atender web siempre
        handle_web()

        # Guardado periódico
        now = time.time()
        if now - last_save >= SAVE_INTERVAL:
            if read_sensor():
                save_csv(current_temp, current_hum)
                lcd_msg("Temp {}C".format(fmt_temp()), "Hum {}%".format(fmt_hum()))
            else:
                lcd_msg("Sensor Error", "reintentando")

            last_save = now

        # Si no hay dato todavía, intentar leer cada vuelta sin guardar
        if current_temp is None or current_hum is None:
            if read_sensor():
                lcd_msg("Temp {}C".format(fmt_temp()), "Hum {}%".format(fmt_hum()))
            else:
                lcd_msg("Sensor Error", "esperando")
                time.sleep(SENSOR_RETRY_DELAY)

        time.sleep(0.2)

    except Exception as e:
        print("Loop error:", e)
        lcd_msg("Loop Error", str(e)[:16])
        time.sleep(2)