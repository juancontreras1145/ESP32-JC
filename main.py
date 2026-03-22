
# =========================================
# ESP32 JC Monitor v64
# Integrado: interior + exterior + amaneciendo
# logs + JSON + estado + CSV + LCD rotativo
# =========================================

import time
import socket
import network
import dht
import os
import gc
import math
import machine
import ntptime
from machine import Pin, I2C

# ------------------------------
# AUTO UPDATE (seguro)
# ------------------------------
try:
    import updater
    updated = updater.update()
    if updated:
        machine.reset()
except Exception as e:
    print("Updater error:", e)

VERSION = "ESP32 JC Monitor v64"

# -----------------------------
# CONFIG
# -----------------------------
LCD_SDA = 8
LCD_SCL = 9
LCD_ADDR = 0x27

DHT_PIN = 4

CSV_FILE = "temperaturas.csv"
LOG_FILE = "main.log"

INTERVALO_GUARDADO = 600
INTERVALO_EXTERIOR = 1800
TIMEOUT_WEB = 1
REFRESCO_WEB = 12
PAUSA_LCD_BOOT = 1.2
ROTACION_LCD_SEG = 3

UTC_OFFSET_HORAS = -3

LAT = -33.0475
LON = -71.4425
UBICACION = "Quilpue, Valparaiso"

# -----------------------------
# ESTADO
# -----------------------------
inicio_epoch = time.time()

temperatura_actual = None
humedad_actual = None

temp_ext = None
hum_ext = None

wifi_ip = "Sin WiFi"

sensor = None
lcd = None
server = None

# -----------------------------
# HELPERS
# -----------------------------

def fmt(x):
    if x is None:
        return "--.-"
    try:
        return "{:.1f}".format(float(x))
    except:
        return "--.-"

def clamp(text,n=16):
    t=str(text)
    if len(t)<=n:
        return t
    return t[:n]

def now():
    return int(time.time())

# -----------------------------
# LOGS
# -----------------------------

def append_log(msg):
    try:
        line="{} {}\n".format(now(),msg)
        with open(LOG_FILE,"a") as f:
            f.write(line)
    except:
        pass

def read_logs():
    try:
        if LOG_FILE in os.listdir():
            with open(LOG_FILE,"r") as f:
                return f.read()
    except:
        pass
    return "Sin logs"

# -----------------------------
# WIFI
# -----------------------------

def refresh_ip():
    global wifi_ip
    try:
        wlan=network.WLAN(network.STA_IF)
        if wlan.isconnected():
            wifi_ip=wlan.ifconfig()[0]
    except:
        pass

# -----------------------------
# LCD
# -----------------------------

def init_lcd():
    global lcd
    try:
        from lcd import LCD
        i2c=I2C(0,sda=Pin(LCD_SDA),scl=Pin(LCD_SCL))
        lcd=LCD(i2c,LCD_ADDR,cols=16,rows=2)
        lcd.clear()
    except Exception as e:
        append_log("LCD error {}".format(e))

def lcd_msg(l1,l2):
    try:
        lcd.message(clamp(l1,16),clamp(l2,16))
    except:
        pass

# -----------------------------
# SENSOR
# -----------------------------

def init_sensor():
    global sensor
    try:
        sensor=dht.DHT22(Pin(DHT_PIN))
    except Exception as e:
        append_log("Sensor init error {}".format(e))

def read_sensor():
    global temperatura_actual,humedad_actual
    try:
        sensor.measure()
        temperatura_actual=round(sensor.temperature(),1)
        humedad_actual=round(sensor.humidity(),1)
        return True
    except Exception as e:
        append_log("Sensor read error {}".format(e))
        return False

# -----------------------------
# EXTERIOR
# -----------------------------

def fetch_weather():
    global temp_ext,hum_ext
    try:
        import urequests

        url="http://api.open-meteo.com/v1/forecast?latitude={}&longitude={}&current=temperature_2m,relative_humidity_2m".format(LAT,LON)

        r=urequests.get(url)
        data=r.json()
        r.close()

        c=data.get("current",{})
        temp_ext=c.get("temperature_2m")
        hum_ext=c.get("relative_humidity_2m")

        append_log("Exterior actualizado")

    except Exception as e:
        append_log("Exterior error {}".format(e))

# -----------------------------
# WEB
# -----------------------------

def page_home():
    return """
    <html>
    <head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="12">
    </head>
    <body style="background:#0b1a2e;color:white;font-family:Arial">

    <h2>ESP32 JC Monitor v64</h2>

    <p>IP: {}</p>

    <h3>Interior</h3>
    <p>{} C</p>
    <p>Humedad {} %</p>

    <h3>Exterior</h3>
    <p>{} C</p>
    <p>Humedad {} %</p>

    <p><a href="/logs">Ver logs</a></p>

    </body>
    </html>
    """.format(
        wifi_ip,
        fmt(temperatura_actual),
        fmt(humedad_actual),
        fmt(temp_ext),
        fmt(hum_ext)
    )

def page_logs():
    return """
    <html>
    <body>
    <h2>Logs del sistema</h2>
    <pre>{}</pre>
    <a href="/">Volver</a>
    </body>
    </html>
    """.format(read_logs())

# -----------------------------
# SERVER
# -----------------------------

def init_server():
    global server
    addr=socket.getaddrinfo("0.0.0.0",80)[0][-1]
    server=socket.socket()
    server.bind(addr)
    server.listen(5)

def handle_web():
    cl,addr=server.accept()
    req=cl.recv(1024)
    req=str(req)

    path="/"
    try:
        path=req.split(" ")[1]
    except:
        pass

    if path=="/logs":
        body=page_logs()
    else:
        body=page_home()

    cl.send("HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n")
    cl.send(body)
    cl.close()

# -----------------------------
# ARRANQUE
# -----------------------------

append_log("Inicio {}".format(VERSION))

init_lcd()
lcd_msg("ESP32 JC","Iniciando")

init_sensor()

refresh_ip()

init_server()

read_sensor()
fetch_weather()

lcd_msg("Interior {}".format(fmt(temperatura_actual)),"Hum {}%".format(fmt(humedad_actual)))

# -----------------------------
# LOOP
# -----------------------------

last_ext=0

while True:

    try:

        handle_web()

        if now()-last_ext>INTERVALO_EXTERIOR:
            fetch_weather()
            last_ext=now()

        read_sensor()

        lcd_msg(
            "Interior {} C".format(fmt(temperatura_actual)),
            "Hum {}%".format(fmt(humedad_actual))
        )

        time.sleep(2)

    except Exception as e:
        append_log("Loop error {}".format(e))
        time.sleep(2)
