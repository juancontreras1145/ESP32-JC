
# =========================================
# ESP32 JC - MAIN RECOVERY
# =========================================

import time
import socket
import gc
from machine import Pin, I2C
import dht
import network

VERSION = "RECOVERY v1"

LCD_SDA = 8
LCD_SCL = 9
LCD_ADDR = 0x27
DHT_PIN = 4

lcd = None
sensor = None
wifi_ip = "Sin WiFi"


def log(msg):
    print("[RECOVERY]", msg)


def init_lcd():
    global lcd
    from lcd import LCD
    i2c = I2C(0, sda=Pin(LCD_SDA), scl=Pin(LCD_SCL))
    lcd = LCD(i2c, LCD_ADDR, cols=16, rows=2)
    try:
        lcd.reinit()
    except:
        pass
    try:
        lcd.backlight_on()
    except:
        pass
    lcd.clear()


def lcd_msg(a="", b=""):
    global lcd
    if lcd is None:
        return
    try:
        lcd.message(str(a), str(b))
    except Exception as e:
        print("LCD error:", e)


def init_sensor():
    global sensor
    sensor = dht.DHT22(Pin(DHT_PIN))


def get_wifi_ip():
    try:
        wlan = network.WLAN(network.STA_IF)
        if wlan.isconnected():
            return wlan.ifconfig()[0]
    except:
        pass
    return "Sin WiFi"


def leer_sensor():
    global sensor
    try:
        sensor.measure()
        t = round(sensor.temperature(), 1)
        h = round(sensor.humidity(), 1)
        return t, h, None
    except Exception as e:
        return None, None, str(e)


def html(ip, temp, hum, err):
    return """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="10">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Recovery ESP32</title>
<style>
body {{
    font-family: Arial, sans-serif;
    background: #08111f;
    color: #eef4ff;
    padding: 16px;
}}
.card {{
    background: #0d1b2a;
    border: 1px solid #1f4f88;
    border-radius: 16px;
    padding: 16px;
    margin-bottom: 16px;
}}
.big {{
    font-size: 34px;
    font-weight: bold;
}}
</style>
</head>
<body>
<div class="card">
    <h1>ESP32 Recovery</h1>
    <p>Version: {version}</p>
    <p>IP: {ip}</p>
</div>

<div class="card">
    <p>Temperatura</p>
    <div class="big">{temp}</div>
</div>

<div class="card">
    <p>Humedad</p>
    <div class="big">{hum}</div>
</div>

<div class="card">
    <p>Error</p>
    <div>{err}</div>
</div>
</body>
</html>
""".format(
        version=VERSION,
        ip=ip,
        temp="--.- °C" if temp is None else "{} °C".format(temp),
        hum="--.- %" if hum is None else "{} %".format(hum),
        err="Ninguno" if err is None else err
    )


log("Iniciando recovery")
gc.collect()

init_lcd()
lcd_msg("ESP32 RECOVERY", VERSION)
time.sleep(2)

wifi_ip = get_wifi_ip()
lcd_msg("WiFi", wifi_ip)
time.sleep(2)

init_sensor()
lcd_msg("Sensor", "Inicializado")
time.sleep(2)

addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(addr)
s.listen(2)
s.settimeout(1)

log("Servidor web listo")
lcd_msg("Web lista", wifi_ip)
time.sleep(2)

while True:
    try:
        gc.collect()

        wifi_ip = get_wifi_ip()
        temp, hum, err = leer_sensor()

        if err is None:
            lcd_msg("T {}C".format(temp), "H {}%".format(hum))
        else:
            lcd_msg("Sensor error", str(err)[:16])

        try:
            cl, addr = s.accept()
            req = cl.recv(1024)
            body = html(wifi_ip, temp, hum, err)
            cl.send("HTTP/1.0 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n\r\n")
            cl.send(body)
            cl.close()
        except OSError:
            pass

        time.sleep(2)

    except Exception as e:
        log("Loop error: {}".format(e))
        lcd_msg("Loop error", str(e)[:16])
        time.sleep(2)
