import time
import socket
import network
import dht
from machine import Pin, I2C

# ==============================
# CONFIG
# ==============================
VERSION = "APP v2.0"

# LCD I2C
SDA = 8
SCL = 9
LCD_ADDR = 0x27

# SENSOR DHT22
DHT_PIN = 4

# CSV
FILE = "temperaturas.csv"

# CADA CUÁNTO GUARDAR (segundos)
SAVE_INTERVAL = 600   # 10 min

# ==============================
# LCD
# ==============================
from lcd import LCD

i2c = I2C(0, sda=Pin(SDA), scl=Pin(SCL))
lcd = LCD(i2c, LCD_ADDR)

def lcd_msg(l1="", l2=""):
    try:
        lcd.clear()
        lcd.move_to(0, 0)
        lcd.putstr(str(l1)[:16])
        lcd.move_to(0, 1)
        lcd.putstr(str(l2)[:16])
    except Exception as e:
        print("LCD error:", e)

# ==============================
# WIFI
# ==============================
wlan = network.WLAN(network.STA_IF)

def wifi_info():
    if wlan.isconnected():
        return wlan.ifconfig()[0]
    return "Sin WiFi"

# ==============================
# SENSOR
# ==============================
sensor = dht.DHT22(Pin(DHT_PIN))

# ==============================
# ESTADO GLOBAL
# ==============================
t = None
h = None
sensor_ok = False
sensor_error = "Sin lectura"
start_time = time.time()
last_save = 0

# ==============================
# ARCHIVO CSV
# ==============================
def ensure_file():
    try:
        files = []
        try:
            import os
            files = os.listdir()
        except:
            pass

        if FILE not in files:
            f = open(FILE, "w")
            f.write("epoch,temperatura,humedad\n")
            f.close()
    except Exception as e:
        print("Error creando CSV:", e)

def log_temp(temp, hum):
    try:
        f = open(FILE, "a")
        f.write("{},{:.1f},{:.1f}\n".format(time.time(), temp, hum))
        f.close()
        return True
    except Exception as e:
        print("Error guardando CSV:", e)
        return False

# ==============================
# INFO SISTEMA
# ==============================
def uptime():
    s = int(time.time() - start_time)
    h_ = s // 3600
    m_ = (s % 3600) // 60
    s_ = s % 60
    return "{:02d}:{:02d}:{:02d}".format(h_, m_, s_)

def sensor_status():
    if sensor_ok:
        return "OK"
    return "ERROR"

# ==============================
# WEB
# ==============================
def webpage():
    temp_txt = "--.-" if t is None else "{:.1f}".format(t)
    hum_txt = "--.-" if h is None else "{:.1f}".format(h)

    html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta http-equiv="refresh" content="15">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>ESP32 Monitor</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            background: #0f172a;
            color: #f8fafc;
            margin: 0;
            padding: 16px;
        }}
        .wrap {{
            max-width: 900px;
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
            margin-bottom: 10px;
        }}
        .muted {{
            color: #94a3b8;
            font-size: 14px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
        }}
        .big {{
            font-size: 38px;
            font-weight: bold;
            margin-top: 10px;
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
            <div class="muted">Estado sensor: <span class="{status_class}">{sensor_status}</span></div>
            <div class="muted">Ultimo error: {sensor_error}</div>
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
            <div class="title" style="font-size:20px;">Descargas</div>
            <a class="btn" href="/download">Descargar CSV</a>
        </div>

        <div class="card">
            <div class="title" style="font-size:20px;">Archivo local</div>
            <div class="mono">{file}</div>
        </div>
    </div>
</body>
</html>
""".format(
        version=VERSION,
        ip=wifi_info(),
        uptime=uptime(),
        sensor_status=sensor_status(),
        sensor_error=sensor_error,
        temp=temp_txt,
        hum=hum_txt,
        file=FILE,
        status_class="ok" if sensor_ok else "bad"
    )
    return html

# ==============================
# SERVER
# ==============================
def start_server():
    addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(5)
    print("Servidor web listo")
    return s

# ==============================
# LECTURA ROBUSTA DEL SENSOR
# ==============================
def read_sensor():
    global t, h, sensor_ok, sensor_error

    try:
        sensor.measure()
        t = round(sensor.temperature(), 1)
        h = round(sensor.humidity(), 1)
        sensor_ok = True
        sensor_error = "Ninguno"
        return True

    except Exception as e:
        sensor_ok = False
        sensor_error = str(e)
        print("Sensor error:", e)
        return False

# ==============================
# ARRANQUE
# ==============================
lcd_msg("ESP32 JC", VERSION)
time.sleep(2)

lcd_msg("Iniciando", "sensor/web")
time.sleep(2)

ensure_file()

s = start_server()

lcd_msg("Web lista", wifi_info())
time.sleep(2)

# lectura inicial
ok = read_sensor()
if ok:
    lcd_msg("Temp {}C".format(t), "Hum {}%".format(h))
else:
    lcd_msg("Sensor Error", "sin lectura")
time.sleep(2)

# ==============================
# LOOP
# ==============================
while True:

    # leer y guardar cada 10 min
    now = time.time()
    if now - last_save > SAVE_INTERVAL:
        ok = read_sensor()

        if ok:
            log_temp(t, h)
            lcd_msg("Temp {}C".format(t), "Hum {}%".format(h))
        else:
            lcd_msg("Sensor Error", "reintentando")

        last_save = now

    # web siempre viva
    try:
        cl, addr = s.accept()
        req = cl.recv(1024)
        req = str(req)

        if "/download" in req:
            try:
                f = open(FILE)
                data = f.read()
                f.close()

                cl.send("HTTP/1.0 200 OK\r\n")
                cl.send("Content-Type: text/plain\r\n")
                cl.send("Content-Disposition: attachment; filename={}\r\n\r\n".format(FILE))
                cl.send(data)
            except Exception as e:
                cl.send("HTTP/1.0 500 OK\r\nContent-Type: text/plain\r\n\r\n")
                cl.send("Error descargando archivo: {}".format(e))
        else:
            response = webpage()
            cl.send("HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n")
            cl.send(response)

        cl.close()

    except Exception:
        pass

    time.sleep(1)