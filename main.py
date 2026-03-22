
# =========================================
# ESP32 JC Monitor v63
# Interior + exterior + analisis ambiental
# =========================================

import time, socket, network, dht, os, gc, math, machine, ntptime
from machine import Pin, I2C

VERSION = "ESP32 JC Monitor v63"

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
ROTACION_LCD_SEG = 3

UTC_OFFSET_HORAS = -3

LAT = -33.0475
LON = -71.4425
UBICACION = "Quilpue, Valparaiso"

WEB_TOKEN = "jc123"

# -----------------------------
# ESTADO GLOBAL
# -----------------------------
inicio_epoch = time.time()
temperatura_actual = None
humedad_actual = None
temperatura_prev = None
humedad_prev = None

temp_ext = None
hum_ext = None

sensor = None
server = None

# -----------------------------
# HELPERS
# -----------------------------
def now_epoch():
    return int(time.time())

def dew_point(temp, hum):
    try:
        a=17.27
        b=237.7
        alpha=((a*temp)/(b+temp))+math.log(hum/100.0)
        return round((b*alpha)/(a-alpha),1)
    except:
        return None

def fmt(x):
    if x is None:
        return "--"
    return str(round(x,1))

# -----------------------------
# ANALISIS AMBIENTAL
# -----------------------------
def fase_dia():
    h=time.localtime()[3]
    if 5<=h<8: return "amanecer"
    if 8<=h<12: return "mañana"
    if 12<=h<17: return "tarde"
    if 17<=h<20: return "atardecer"
    if 20<=h<23: return "noche"
    return "madrugada"

BASE=[
"Ambiente estable",
"Clima interior equilibrado",
"Microclima domestico OK",
"Condiciones normales",
"Lectura ambiental estable"
]

def analisis_ambiental():
    msgs=[]
    
    if temperatura_actual and temp_ext:
        if temp_ext<temperatura_actual-2:
            msgs.append("Exterior mas frio")
        elif temp_ext>temperatura_actual+2:
            msgs.append("Exterior mas calido")

    if humedad_actual:
        if humedad_actual>70:
            msgs.append("Humedad interior alta")
        elif humedad_actual<35:
            msgs.append("Ambiente seco")

    dp=dew_point(temperatura_actual,humedad_actual)
    if dp:
        if temperatura_actual-dp<2:
            msgs.append("Condensacion posible")

    fase=fase_dia()
    msgs.append("Momento: "+fase)

    msgs.append(BASE[now_epoch()%len(BASE)])

    return msgs[:3]

# -----------------------------
# SENSOR
# -----------------------------
def init_sensor():
    global sensor
    sensor=dht.DHT22(Pin(DHT_PIN))

def read_sensor():
    global temperatura_actual,humedad_actual
    try:
        sensor.measure()
        temperatura_actual=sensor.temperature()
        humedad_actual=sensor.humidity()
    except:
        pass

# -----------------------------
# EXTERIOR SIMPLE (mock)
# -----------------------------
def fetch_weather_outside():
    global temp_ext,hum_ext
    # placeholder simple
    temp_ext=18
    hum_ext=70

# -----------------------------
# WEB
# -----------------------------
def style():
    return """
<style>
body{font-family:Arial;background:#07111f;color:#eef4ff}
.card{background:#0d1b2a;padding:14px;margin:10px;border-radius:12px}
.big{font-size:28px;font-weight:bold}
</style>
"""

def page_home():
    analisis=analisis_ambiental()
    txt="<br>".join(analisis)

    return f"""
<html>
<head>{style()}</head>
<body>

<div class='card'>
<h2>{VERSION}</h2>
IP monitor
</div>

<div class='card'>
Interior<br>
<div class='big'>{fmt(temperatura_actual)} °C</div>
Humedad {fmt(humedad_actual)} %
</div>

<div class='card'>
Exterior<br>
<div class='big'>{fmt(temp_ext)} °C</div>
Humedad {fmt(hum_ext)} %
</div>

<div class='card'>
Analisis ambiental<br>
<div class='big'>{txt}</div>
</div>

</body>
</html>
"""

def respond(cl,body):
    cl.send("HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n")
    cl.send(body)

def init_server():
    global server
    addr=socket.getaddrinfo("0.0.0.0",80)[0][-1]
    server=socket.socket()
    server.bind(addr)
    server.listen(5)

def handle_web():
    try:
        cl,addr=server.accept()
    except:
        return

    req=cl.recv(1024)
    respond(cl,page_home())
    cl.close()

# -----------------------------
# ARRANQUE
# -----------------------------
init_sensor()
fetch_weather_outside()
init_server()

while True:

    read_sensor()
    handle_web()

    time.sleep(2)
