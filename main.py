
# =========================================
# ESP32 JC Monitor v70
# Interior + Exterior + Amanecer + Consejos
# =========================================

import time
import math
import random
import socket
import network
import dht
import machine
import ntptime
import gc
from machine import Pin

VERSION = "ESP32 JC Monitor v70"

# ---------------- CONFIG ----------------

DHT_PIN = 4
LAT = -33.0475
LON = -71.4425
UBICACION = "Quilpue, Valparaiso"

# ----------------------------------------

sensor = dht.DHT22(Pin(DHT_PIN))

temp_hist = []
hum_hist = []

temp_ext = None
hum_ext = None

# ---------- CONSEJOS TEMPERATURA --------

def consejo_temp(t):

    if t < 8:
        frases = [
        "Frio extremo",
        "Abrigo obligatorio",
        "Ambiente muy frio",
        "Calefaccion recomendada"
        ]

    elif t < 14:
        frases = [
        "Frio sostenido",
        "Ambiente frio",
        "Abrigo recomendado",
        "Clima frio moderado"
        ]

    elif t < 20:
        frases = [
        "Ambiente fresco",
        "Temperatura estable",
        "Clima agradable",
        "Condiciones neutrales"
        ]

    elif t < 26:
        frases = [
        "Ambiente templado",
        "Clima confortable",
        "Condiciones optimas",
        "Temperatura ideal"
        ]

    else:
        frases = [
        "Ambiente calido",
        "Calor moderado",
        "Ventilacion recomendada",
        "Alta temperatura"
        ]

    return random.choice(frases)


# ---------- CONFORT ---------------------

def confort(temp, hum):

    if temp < 14:
        return "Frio"

    if temp < 22 and hum < 70:
        return "Regular"

    if temp < 26 and hum < 60:
        return "Confortable"

    return "Caluroso"


# ---------- PUNTO ROCIO -----------------

def punto_rocio(t, h):

    a = 17.27
    b = 237.7

    alpha = ((a * t) / (b + t)) + math.log(h/100.0)
    dew = (b * alpha) / (a - alpha)

    return round(dew,1)


# ---------- AMANECER --------------------

def donde_amaneciendo(hora):

    if 18 <= hora <= 20:
        return "Nueva Zelanda"

    if 20 <= hora <= 22:
        return "Australia"

    if 22 <= hora <= 0:
        return "Indonesia"

    if 0 <= hora <= 2:
        return "India"

    if 2 <= hora <= 4:
        return "Medio Oriente"

    if 4 <= hora <= 6:
        return "Europa"

    if 6 <= hora <= 8:
        return "Africa"

    if 8 <= hora <= 10:
        return "Atlantico"

    if 10 <= hora <= 12:
        return "Sudamerica"

    return "Pacifico"


# ---------- SENSOR ----------------------

def leer_sensor():

    sensor.measure()
    t = round(sensor.temperature(),1)
    h = round(sensor.humidity(),1)

    temp_hist.append(t)
    hum_hist.append(h)

    if len(temp_hist) > 200:
        temp_hist.pop(0)
        hum_hist.pop(0)

    return t,h


# ---------- ESTADISTICAS ----------------

def stats():

    if len(temp_hist) == 0:
        return 0,0,0

    tmin = min(temp_hist)
    tmax = max(temp_hist)
    tavg = round(sum(temp_hist)/len(temp_hist),1)

    return tmin,tmax,tavg


# ---------- WEB SERVER ------------------

def pagina(t,h):

    dew = punto_rocio(t,h)
    conf = confort(t,h)
    consejo = consejo_temp(t)

    hora = time.localtime()[3]
    amanecer = donde_amaneciendo(hora)

    tmin,tmax,tavg = stats()

    html = f"""
    <html>
    <head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="10">
    </head>
    <body style="background:#0b1a2e;color:white;font-family:Arial">

    <h2>{VERSION}</h2>

    <p>Ubicacion: {UBICACION}</p>

    <h3>Interior</h3>
    <p>{t} C</p>
    <p>Humedad {h} %</p>

    <h3>Exterior</h3>
    <p>{temp_ext} C</p>
    <p>Humedad {hum_ext} %</p>

    <h3>Confort</h3>
    <p>{conf}</p>

    <h3>Punto de rocio</h3>
    <p>{dew} C</p>

    <h3>Consejo</h3>
    <p>{consejo}</p>

    <h3>Donde esta amaneciendo</h3>
    <p>{amanecer}</p>

    <h3>Estadisticas</h3>
    <p>Min {tmin} C</p>
    <p>Max {tmax} C</p>
    <p>Prom {tavg} C</p>

    </body>
    </html>
    """

    return html


# ---------- WIFI ------------------------

def conectar_wifi():

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        wlan.connect("S25","12345678")

        while not wlan.isconnected():
            time.sleep(1)

    return wlan.ifconfig()[0]


# ---------- SERVIDOR --------------------

def iniciar_server():

    addr = socket.getaddrinfo("0.0.0.0",80)[0][-1]

    s = socket.socket()
    s.bind(addr)
    s.listen(5)

    return s


# ---------- MAIN ------------------------

ip = conectar_wifi()

print("IP:",ip)

try:
    ntptime.settime()
except:
    pass

server = iniciar_server()

print("Servidor listo")

while True:

    try:

        t,h = leer_sensor()

        cl, addr = server.accept()

        req = cl.recv(1024)

        response = pagina(t,h)

        cl.send('HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n')
        cl.send(response)
        cl.close()

        gc.collect()

    except Exception as e:

        print("error:",e)
        time.sleep(2)
