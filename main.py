# =========================================
# ESP32 JC - Monitor Ambiental v10
# =========================================
# Requiere:
# - lcd.py con clase LCD
# - boot.py que conecte WiFi y opcionalmente actualice desde GitHub
#
# Hardware:
# - LCD I2C 1602 -> SDA=8, SCL=9, addr=0x27
# - DHT22 -> GPIO4
#
# Web:
#   /          Panel principal
#   /status    Estado técnico
#   /download  Descarga CSV
#   /read      Fuerza lectura inmediata
# =========================================

import time
import socket
import network
import dht
import os
import gc
from machine import Pin, I2C

# =========================================
# CONFIG
# =========================================
VERSION = "APP v10"

# LCD
LCD_SDA = 8
LCD_SCL = 9
LCD_ADDR = 0x27

# DHT22
DHT_PIN = 4

# Archivo
CSV_FILE = "temperaturas.csv"

# Tiempos
SAVE_INTERVAL = 600          # 10 min
WEB_TIMEOUT = 1
LCD_MSG_PAUSE = 1.2
SENSOR_RETRY_COUNT = 3
SENSOR_RETRY_DELAY = 1
WIFI_CHECK_INTERVAL = 15
WEB_REFRESH_SECONDS = 15

# =========================================
# ESTADO GLOBAL
# =========================================
start_time = time.time()
last_save = 0
last_wifi_check = 0
read_count = 0
save_count = 0
web_hits = 0

current_temp = None
current_hum = None
last_read_epoch = None

sensor_ok = False
sensor_error = "Sin lectura"
lcd_ok = False
lcd_error = "Ninguno"
server_ok = False
server_error = "Ninguno"

ip_addr = "Sin WiFi"

lcd = None
sensor = None
server = None

# =========================================
# HELPERS
# =========================================
def now_epoch():
    try:
        return int(time.time())
    except:
        return 0

def uptime_text():
    secs = max(0, int(time.time() - start_time))
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    return "{:02d}:{:02d}:{:02d}".format(h, m, s)

def fmt_temp():
    if current_temp is None:
        return "--.-"
    return "{:.1f}".format(current_temp)

def fmt_hum():
    if current_hum is None:
        return "--.-"
    return "{:.1f}".format(current_hum)

def safe_str(x, maxlen=16):
    try:
        return str(x)[:maxlen]
    except:
        return "?"

def file_exists(name):
    try:
        return name in os.listdir()
    except:
        return False

# =========================================
# LCD
# =========================================
def init_lcd():
    global lcd, lcd_ok, lcd_error

    try:
        from lcd import LCD
        i2c = I2C(0, sda=Pin(LCD_SDA), scl=Pin(LCD_SCL))
        lcd = LCD(i2c, LCD_ADDR)

        try:
            lcd.reinit()
        except:
            pass

        time.sleep_ms(150)
        lcd.clear()

        lcd_ok = True
        lcd_error = "Ninguno"
        return True

    except Exception as e:
        lcd = None
        lcd_ok = False
        lcd_error = str(e)
        print("LCD init error:", e)
        return False


def lcd_write(line1="", line2=""):
    global lcd_ok, lcd_error

    if lcd is None:
        return False

    try:
        lcd.clear()
        time.sleep_ms(5)
        lcd.move_to(0, 0)
        lcd.putstr(safe_str(line1, 16))
        lcd.move_to(0, 1)
        lcd.putstr(safe_str(line2, 16))
        lcd_ok = True
        lcd_error = "Ninguno"
        return True

    except Exception as e:
        lcd_ok = False
        lcd_error = str(e)
        print("LCD write error:", e)
        return False


def lcd_msg(line1="", line2="", pause=0):
    ok = lcd_write(line1, line2)
    if not ok:
        try:
            init_lcd()
            lcd_write(line1, line2)
        except:
            pass
    if pause > 0:
        time.sleep(pause)

# =========================================
# WIFI
# =========================================
def wifi_connected():
    try:
        wlan = network.WLAN(network.STA_IF)
        return wlan.isconnected()
    except:
        return False


def refresh_ip():
    global ip_addr
    try:
        wlan = network.WLAN(network.STA_IF)
        if wlan.isconnected():
            ip_addr = wlan.ifconfig()[0]
        else:
            ip_addr = "Sin WiFi"
    except:
        ip_addr = "Sin WiFi"


def periodic_wifi_check():
    global last_wifi_check
    now = now_epoch()
    if now - last_wifi_check >= WIFI_CHECK_INTERVAL:
        refresh_ip()
        last_wifi_check = now

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
    global sensor, current_temp, current_hum
    global sensor_ok, sensor_error, last_read_epoch, read_count

    if sensor is None:
        if not init_sensor():
            sensor_ok = False
            sensor_error = "No inicia sensor"
            return False

    for intento in range(1, SENSOR_RETRY_COUNT + 1):
        try:
            sensor.measure()
            current_temp = round(sensor.temperature(), 1)
            current_hum = round(sensor.humidity(), 1)
            last_read_epoch = now_epoch()
            read_count += 1
            sensor_ok = True
            sensor_error = "Ninguno"
            return True

        except Exception as e:
            sensor_ok = False
            sensor_error = "Intento {}: {}".format(intento, e)
            print("Sensor error:", sensor_error)
            time.sleep(SENSOR_RETRY_DELAY)

    return False

# =========================================
# CSV
# =========================================
def ensure_csv():
    try:
        if not file_exists(CSV_FILE):
            with open(CSV_FILE, "w") as f:
                f.write("epoch,temperatura,humedad\n")
    except Exception as e:
        print("CSV init error:", e)

def append_csv(temp, hum):
    global save_count
    try:
        with open(CSV_FILE, "a") as f:
            f.write("{},{:.1f},{:.1f}\n".format(now_epoch(), temp, hum))
        save_count += 1
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

def get_stats():
    stats = {
        "count": 0,
        "tmin": None,
        "tmax": None,
        "tavg": None,
        "hmin": None,
        "hmax": None,
        "havg": None,
    }

    try:
        with open(CSV_FILE, "r") as f:
            lines = f.readlines()

        temps = []
        hums = []

        for line in lines[1:]:
            parts = line.strip().split(",")
            if len(parts) != 3:
                continue
            try:
                temps.append(float(parts[1]))
                hums.append(float(parts[2]))
            except:
                pass

        if temps and hums:
            stats["count"] = len(temps)
            stats["tmin"] = min(temps)
            stats["tmax"] = max(temps)
            stats["tavg"] = sum(temps) / len(temps)
            stats["hmin"] = min(hums)
            stats["hmax"] = max(hums)
            stats["havg"] = sum(hums) / len(hums)

    except Exception as e:
        print("Stats error:", e)

    return stats

# =========================================
# WEB HTML
# =========================================
def build_main_page():
    stats = get_stats()

    def stat_fmt(v):
        return "--.-" if v is None else "{:.1f}".format(v)

    sensor_class = "ok" if sensor_ok else "bad"
    wifi_class = "ok" if wifi_connected() else "bad"

    return """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="{refresh}">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ESP32 JC v10</title>
<style>
body {{
    font-family: Arial, sans-serif;
    background: #0f172a;
    color: #f8fafc;
    margin: 0;
    padding: 16px;
}}
.wrap {{
    max-width: 980px;
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
.sub {{
    color: #94a3b8;
    font-size: 14px;
}}
.grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
}}
.grid3 {{
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 12px;
}}
.big {{
    font-size: 42px;
    font-weight: bold;
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
.btn2 {{
    background: #38bdf8;
    color: #082f49;
}}
.mono {{
    font-family: monospace;
    background: #020617;
    padding: 10px;
    border-radius: 10px;
}}
@media (max-width: 700px) {{
    .grid, .grid3 {{
        grid-template-columns: 1fr;
    }}
}}
</style>
</head>
<body>
<div class="wrap">

    <div class="card">
        <div class="title">ESP32 JC Monitor v10</div>
        <div class="sub">IP: {ip}</div>
        <div class="sub">Uptime: {uptime}</div>
        <div class="sub">Sensor: <span class="{sensor_class}">{sensor_state}</span></div>
        <div class="sub">WiFi: <span class="{wifi_class}">{wifi_state}</span></div>
        <div class="sub">Ultimo error sensor: {sensor_error}</div>
    </div>

    <div class="grid">
        <div class="card">
            <div class="sub">Temperatura actual</div>
            <div class="big">{temp} °C</div>
        </div>
        <div class="card">
            <div class="sub">Humedad actual</div>
            <div class="big">{hum} %</div>
        </div>
    </div>

    <div class="card">
        <div class="title" style="font-size:20px;">Estadisticas</div>
        <div class="grid3">
            <div class="mono">Temp min: {tmin}</div>
            <div class="mono">Temp max: {tmax}</div>
            <div class="mono">Temp prom: {tavg}</div>
            <div class="mono">Hum min: {hmin}</div>
            <div class="mono">Hum max: {hmax}</div>
            <div class="mono">Hum prom: {havg}</div>
        </div>
        <div class="sub" style="margin-top:10px;">Registros guardados: {count}</div>
    </div>

    <div class="card">
        <div class="title" style="font-size:20px;">Acciones</div>
        <a class="btn" href="/download">Descargar CSV</a>
        <a class="btn btn2" href="/read">Forzar lectura</a>
        <a class="btn btn2" href="/status">Estado tecnico</a>
    </div>

</div>
</body>
</html>
""".format(
        refresh=WEB_REFRESH_SECONDS,
        ip=ip_addr,
        uptime=uptime_text(),
        sensor_class=sensor_class,
        sensor_state="OK" if sensor_ok else "ERROR",
        wifi_class=wifi_class,
        wifi_state="Conectado" if wifi_connected() else "Sin WiFi",
        sensor_error=sensor_error,
        temp=fmt_temp(),
        hum=fmt_hum(),
        tmin=stat_fmt(stats["tmin"]),
        tmax=stat_fmt(stats["tmax"]),
        tavg=stat_fmt(stats["tavg"]),
        hmin=stat_fmt(stats["hmin"]),
        hmax=stat_fmt(stats["hmax"]),
        havg=stat_fmt(stats["havg"]),
        count=stats["count"],
    )

def build_status_page():
    return """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Estado tecnico</title>
<style>
body {{
    font-family: Arial, sans-serif;
    background: #0f172a;
    color: #f8fafc;
    padding: 16px;
}}
.card {{
    background: #111827;
    border: 1px solid #334155;
    border-radius: 16px;
    padding: 16px;
    margin-bottom: 16px;
}}
.mono {{
    font-family: monospace;
    background: #020617;
    padding: 10px;
    border-radius: 10px;
    margin: 6px 0;
}}
a {{
    color: #38bdf8;
}}
</style>
</head>
<body>
<div class="card">
    <h1>Estado tecnico</h1>
    <div class="mono">Version: {version}</div>
    <div class="mono">IP: {ip}</div>
    <div class="mono">Uptime: {uptime}</div>
    <div class="mono">LCD OK: {lcd_ok}</div>
    <div class="mono">LCD Error: {lcd_error}</div>
    <div class="mono">Sensor OK: {sensor_ok}</div>
    <div class="mono">Sensor Error: {sensor_error}</div>
    <div class="mono">Server OK: {server_ok}</div>
    <div class="mono">Server Error: {server_error}</div>
    <div class="mono">Lecturas: {reads}</div>
    <div class="mono">Guardados: {saves}</div>
    <div class="mono">Hits web: {hits}</div>
    <div class="mono">Ultima lectura epoch: {last_read}</div>
    <div class="mono">Archivo CSV: {csv}</div>
    <p><a href="/">Volver</a></p>
</div>
</body>
</html>
""".format(
        version=VERSION,
        ip=ip_addr,
        uptime=uptime_text(),
        lcd_ok=lcd_ok,
        lcd_error=lcd_error,
        sensor_ok=sensor_ok,
        sensor_error=sensor_error,
        server_ok=server_ok,
        server_error=server_error,
        reads=read_count,
        saves=save_count,
        hits=web_hits,
        last_read=last_read_epoch,
        csv=CSV_FILE
    )

# =========================================
# HTTP
# =========================================
def send_response(cl, body, ctype="text/html; charset=utf-8", code="200 OK", extra_headers=None):
    try:
        cl.send("HTTP/1.0 {}\r\n".format(code))
        cl.send("Content-Type: {}\r\n".format(ctype))
        if extra_headers:
            for h in extra_headers:
                cl.send(h + "\r\n")
        cl.send("\r\n")
        cl.send(body)
    except Exception as e:
        print("send_response error:", e)

def init_server():
    global server, server_ok, server_error
    try:
        addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
        server = socket.socket()
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(addr)
        server.listen(5)
        server.settimeout(WEB_TIMEOUT)
        server_ok = True
        server_error = "Ninguno"
        print("Servidor web listo")
        return True
    except Exception as e:
        server = None
        server_ok = False
        server_error = str(e)
        print("Server init error:", e)
        return False

def handle_web():
    global web_hits, server_ok, server_error

    if server is None:
        return

    try:
        cl, addr = server.accept()
    except OSError:
        return
    except Exception as e:
        server_ok = False
        server_error = str(e)
        print("accept error:", e)
        return

    web_hits += 1

    try:
        req = cl.recv(1024)
        req = str(req)

        if "GET /download " in req:
            data = read_csv_text()
            send_response(
                cl,
                data,
                ctype="text/plain",
                extra_headers=[
                    "Content-Disposition: attachment; filename={}".format(CSV_FILE)
                ]
            )

        elif "GET /status " in req:
            send_response(cl, build_status_page())

        elif "GET /read " in req:
            ok = read_sensor()
            if ok:
                lcd_msg("Lectura manual", "OK", 0)
            else:
                lcd_msg("Lectura manual", "ERROR", 0)
            send_response(cl, build_main_page())

        else:
            send_response(cl, build_main_page())

        server_ok = True
        server_error = "Ninguno"

    except Exception as e:
        server_ok = False
        server_error = str(e)
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
lcd_msg("ESP32 JC", VERSION, LCD_MSG_PAUSE)

lcd_msg("Iniciando", "sensor...", LCD_MSG_PAUSE)
init_sensor()

ensure_csv()
refresh_ip()
init_server()

lcd_msg("Web lista", safe_str(ip_addr, 16), LCD_MSG_PAUSE)

if read_sensor():
    lcd_msg("Temp {}C".format(fmt_temp()), "Hum {}%".format(fmt_hum()), LCD_MSG_PAUSE)
else:
    lcd_msg("Sensor Error", "sin lectura", LCD_MSG_PAUSE)

last_save = now_epoch()

# =========================================
# LOOP
# =========================================
while True:
    try:
        gc.collect()
        periodic_wifi_check()
        handle_web()

        now = now_epoch()

        if now - last_save >= SAVE_INTERVAL:
            if read_sensor():
                append_csv(current_temp, current_hum)
                lcd_msg("Temp {}C".format(fmt_temp()), "Hum {}%".format(fmt_hum()), 0)
            else:
                lcd_msg("Sensor Error", "reintentando", 0)

            last_save = now

        if current_temp is None or current_hum is None:
            if read_sensor():
                lcd_msg("Temp {}C".format(fmt_temp()), "Hum {}%".format(fmt_hum()), 0)
            else:
                lcd_msg("Esperando", "sensor...", 0)
                time.sleep(1)

        time.sleep(0.2)

    except Exception as e:
        print("Loop error:", e)
        lcd_msg("Loop Error", safe_str(e, 16), 2)