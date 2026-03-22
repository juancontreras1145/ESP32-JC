import time
import socket
import network
import dht
import machine
import ntptime
import json
from machine import Pin, I2C

from lcd import LCD

VERSION = "ESP32 CLIMA SOL v1"

# WIFI
SSID = "S25"
PASSWORD = "12345678"

# SENSOR
DHT_PIN = 4

# LCD
LCD_SDA = 8
LCD_SCL = 9
LCD_ADDR = 0x27

# UBICACION FIJA
LAT = -33.0475
LON = -71.4425
CIUDAD = "Quilpue"

# ARCHIVOS
LOG = "log.txt"

sensor = None
lcd = None
ip = "0.0.0.0"

temp = None
hum = None

def log(msg):
    print(msg)
    try:
        f=open(LOG,"a")
        f.write(msg+"\n")
        f.close()
    except:
        pass

def wifi():
    global ip
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID,PASSWORD)

    lcd.message("Conectando","WiFi")

    for i in range(15):
        if wlan.isconnected():
            ip = wlan.ifconfig()[0]
            lcd.message("WiFi OK",ip)
            log("WiFi OK "+ip)
            return True
        time.sleep(1)

    lcd.message("WiFi","ERROR")
    log("WiFi fallo")
    return False

def ntp():
    try:
        ntptime.settime()
        log("NTP OK")
    except:
        log("NTP error")

def init_sensor():
    global sensor
    sensor = dht.DHT22(Pin(DHT_PIN))

def leer():
    global temp,hum
    try:
        sensor.measure()
        temp = round(sensor.temperature(),1)
        hum = round(sensor.humidity(),1)
    except:
        pass

def amanecer_global():
    hora = time.localtime()[3]

    zonas = [
        "Pacifico",
        "Nueva Zelanda",
        "Australia",
        "Indonesia",
        "China",
        "India",
        "Medio Oriente",
        "Europa",
        "Africa",
        "Atlantico",
        "Sudamerica",
        "Pacifico"
    ]

    return zonas[int(hora/2)]

def clima_exterior():
    try:
        host="api.open-meteo.com"
        path="/v1/forecast?latitude="+str(LAT)+"&longitude="+str(LON)+"&current_weather=true"

        addr = socket.getaddrinfo(host,80)[0][-1]
        s=socket.socket()
        s.connect(addr)

        req="GET "+path+" HTTP/1.0\r\nHost:"+host+"\r\n\r\n"
        s.send(req)

        data=s.recv(4096)
        s.close()

        txt=str(data)

        i=txt.find("temperature")
        t=txt[i+13:i+17]

        return t
    except:
        return "?"

def pagina():

    ext = clima_exterior()
    sol = amanecer_global()

    html = """
    <html>
    <head>
    <meta name="viewport" content="width=device-width">
    <style>
    body{background:#08111f;color:white;font-family:Arial}
    .box{background:#0d1b2a;padding:20px;margin:10px;border-radius:10px}
    </style>
    </head>
    <body>

    <div class="box">
    <h2>ESP32 CLIMA</h2>
    Version: """+VERSION+"""<br>
    IP: """+ip+"""
    </div>

    <div class="box">
    <h3>Interior</h3>
    Temp: """+str(temp)+""" C<br>
    Hum: """+str(hum)+""" %
    </div>

    <div class="box">
    <h3>Exterior</h3>
    Temp: """+str(ext)+""" C
    </div>

    <div class="box">
    <h3>Donde esta amaneciendo</h3>
    """+sol+"""
    </div>

    </body>
    </html>
    """

    return html

def servidor():

    addr = socket.getaddrinfo("0.0.0.0",80)[0][-1]
    s = socket.socket()
    s.bind(addr)
    s.listen(5)

    lcd.message("Servidor",ip)

    while True:

        leer()

        lcd.message(
            "Temp "+str(temp)+"C",
            "Hum "+str(hum)+"%"
        )

        cl,addr = s.accept()
        req = cl.recv(1024)

        res = pagina()

        cl.send("HTTP/1.0 200 OK\r\nContent-type:text/html\r\n\r\n")
        cl.send(res)
        cl.close()

# BOOT

i2c = I2C(0,sda=Pin(LCD_SDA),scl=Pin(LCD_SCL))
lcd = LCD(i2c,LCD_ADDR)

lcd.message("ESP32","Iniciando")

wifi()
ntp()

init_sensor()

lcd.message("Sistema","Listo")

servidor()