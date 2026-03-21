import machine
import time
import socket
from machine import Pin, I2C
import dht

VERSION = "APP v1.0"

# LCD
SDA = 8
SCL = 9
LCD_ADDR = 0x27

# SENSOR
sensor = dht.DHT22(Pin(4))

# ==============================
# LCD
# ==============================

from lcd import LCD

i2c = I2C(0, sda=Pin(SDA), scl=Pin(SCL))
lcd = LCD(i2c, LCD_ADDR)

def lcd_msg(l1="",l2=""):
    lcd.clear()
    lcd.move_to(0,0)
    lcd.putstr(str(l1))
    lcd.move_to(0,1)
    lcd.putstr(str(l2))

# ==============================
# LOG
# ==============================

FILE = "temperaturas.csv"

def log_temp(t,h):

    try:

        f = open(FILE,"a")
        f.write("{},{:.1f},{:.1f}\n".format(time.time(),t,h))
        f.close()

    except:
        pass

# ==============================
# WEB
# ==============================

def webpage(t,h):

    html = """\
    <html>
    <head>
    <title>ESP32 Monitor</title>
    <style>
    body{font-family:Arial;background:#111;color:white;text-align:center}
    .box{font-size:40px;margin:20px}
    a{color:#00ffcc}
    </style>
    </head>
    <body>

    <h1>ESP32 JC Monitor</h1>

    <div class="box">
    🌡 Temperatura: {} °C
    </div>

    <div class="box">
    💧 Humedad: {} %
    </div>

    <br>

    <a href="/download">Descargar CSV</a>

    </body>
    </html>
    """.format(t,h)

    return html

# ==============================
# SERVER
# ==============================

addr = socket.getaddrinfo('0.0.0.0',80)[0][-1]
s = socket.socket()
s.bind(addr)
s.listen(5)

print("Servidor web listo")

last = 0
t = 0
h = 0

while True:

    if time.time() - last > 600:

        sensor.measure()

        t = round(sensor.temperature(),1)
        h = round(sensor.humidity(),1)

        log_temp(t,h)

        lcd_msg("Temp {}C".format(t),"Hum {}%".format(h))

        last = time.time()

    try:

        cl, addr = s.accept()

        req = cl.recv(1024)

        req = str(req)

        if "/download" in req:

            f = open(FILE)

            data = f.read()

            cl.send("HTTP/1.0 200 OK\r\n")
            cl.send("Content-Type: text/plain\r\n\r\n")
            cl.send(data)

        else:

            response = webpage(t,h)

            cl.send("HTTP/1.0 200 OK\r\n")
            cl.send("Content-Type: text/html\r\n\r\n")
            cl.send(response)

        cl.close()

    except:

        pass
