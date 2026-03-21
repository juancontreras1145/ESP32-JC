# =========================================
# ESP32 JC - DEBUG MAIN
# =========================================

import gc
import os
import time

DEBUG_FILE = "debug.log"

def dlog(msg):
    txt = "[DEBUG] " + str(msg)
    print(txt)
    try:
        with open(DEBUG_FILE, "a") as f:
            f.write(txt + "\n")
    except:
        pass

def limpiar_debug():
    try:
        if DEBUG_FILE in os.listdir():
            os.remove(DEBUG_FILE)
    except:
        pass

limpiar_debug()
dlog("Inicio debug main")

lcd = None
sensor = None
server = None
wifi_ip = "Sin WiFi"

# -------------------------------------------------
# 1. IMPORTS BASE
# -------------------------------------------------
try:
    import socket
    import network
    import dht
    import math
    import machine
    from machine import Pin, I2C
    dlog("OK 1 imports base")
except Exception as e:
    dlog("FALLO 1 imports base -> {}".format(e))
    raise

# -------------------------------------------------
# 2. LCD
# -------------------------------------------------
try:
    from lcd import LCD
    i2c = I2C(0, sda=Pin(8), scl=Pin(9))
    lcd = LCD(i2c, 0x27, cols=16, rows=2)
    try:
        lcd.reinit()
    except Exception as e:
        dlog("LCD reinit aviso -> {}".format(e))

    try:
        lcd.backlight_on()
    except Exception as e:
        dlog("LCD backlight aviso -> {}".format(e))

    lcd.clear()
    lcd.message("DEBUG MAIN", "OK LCD")
    dlog("OK 2 lcd")
    time.sleep(2)

except Exception as e:
    dlog("FALLO 2 lcd -> {}".format(e))
    raise

# -------------------------------------------------
# helper LCD seguro
# -------------------------------------------------
def lcd_show(a="", b=""):
    global lcd
    try:
        if lcd is not None:
            lcd.message(str(a), str(b))
    except Exception as e:
        dlog("LCD_SHOW fallo -> {}".format(e))

# -------------------------------------------------
# 3. SENSOR
# -------------------------------------------------
try:
    sensor = dht.DHT22(Pin(4))
    dlog("OK 3 sensor init")
    lcd_show("DEBUG SENSOR", "iniciado")
    time.sleep(2)
except Exception as e:
    dlog("FALLO 3 sensor init -> {}".format(e))
    lcd_show("FALLO SENSOR", str(e)[:16])
    raise

# -------------------------------------------------
# 4. WIFI / IP
# -------------------------------------------------
try:
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if wlan.isconnected():
        wifi_ip = wlan.ifconfig()[0]
    else:
        wifi_ip = "Sin WiFi"

    dlog("OK 4 wifi/ip -> {}".format(wifi_ip))
    lcd_show("DEBUG WIFI", wifi_ip[:16])
    time.sleep(2)

except Exception as e:
    dlog("FALLO 4 wifi/ip -> {}".format(e))
    lcd_show("FALLO WIFI", str(e)[:16])
    raise

# -------------------------------------------------
# 5. CSV
# -------------------------------------------------
try:
    with open("temperaturas.csv", "a") as f:
        if f.tell() == 0:
            f.write("debug\n")
    dlog("OK 5 csv")
    lcd_show("DEBUG CSV", "OK")
    time.sleep(2)
except Exception as e:
    dlog("FALLO 5 csv -> {}".format(e))
    lcd_show("FALLO CSV", str(e)[:16])
    raise

# -------------------------------------------------
# 6. LECTURA SENSOR REAL
# -------------------------------------------------
try:
    sensor.measure()
    t = sensor.temperature()
    h = sensor.humidity()
    dlog("OK 6 lectura sensor -> T={} H={}".format(t, h))
    lcd_show("T:{} H:{}".format(t, h), "lectura OK")
    time.sleep(3)
except Exception as e:
    dlog("FALLO 6 lectura sensor -> {}".format(e))
    lcd_show("FALLO LECT", str(e)[:16])
    raise

# -------------------------------------------------
# 7. SERVIDOR WEB SIMPLE
# -------------------------------------------------
try:
    addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(addr)
    server.listen(2)
    server.settimeout(1)

    dlog("OK 7 server web")
    lcd_show("DEBUG WEB", "OK")
    time.sleep(2)
except Exception as e:
    dlog("FALLO 7 server web -> {}".format(e))
    lcd_show("FALLO WEB", str(e)[:16])
    raise

# -------------------------------------------------
# 8. LOOP DEBUG
# -------------------------------------------------
contador = 0
dlog("Entrando loop debug")
lcd_show("DEBUG LOOP", "iniciando")
time.sleep(2)

while True:
    try:
        gc.collect()
        contador += 1

        # lectura sensor
        try:
            sensor.measure()
            t = sensor.temperature()
            h = sensor.humidity()
            dlog("LOOP sensor OK -> T={} H={}".format(t, h))
        except Exception as e:
            t = None
            h = None
            dlog("LOOP sensor FAIL -> {}".format(e))

        # pantalla
        try:
            if contador % 3 == 1:
                lcd_show("Paso {}".format(contador), "Sensor OK" if t is not None else "Sensor FAIL")
            elif contador % 3 == 2:
                lcd_show("Temp {}".format(t), "Hum {}".format(h))
            else:
                lcd_show("IP", wifi_ip[:16])
        except Exception as e:
            dlog("LOOP lcd FAIL -> {}".format(e))

        # web simple
        try:
            cl, addr = server.accept()
            req = cl.recv(1024)
            body = """<html><body>
<h1>DEBUG ESP32</h1>
<p>Contador: {}</p>
<p>IP: {}</p>
<p>Temp: {}</p>
<p>Hum: {}</p>
<p>Archivo debug.log: OK</p>
</body></html>""".format(contador, wifi_ip, t, h)

            cl.send("HTTP/1.0 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n\r\n")
            cl.send(body)
            cl.close()
            dlog("LOOP web request OK")
        except OSError:
            pass
        except Exception as e:
            dlog("LOOP web FAIL -> {}".format(e))

        time.sleep(2)

    except Exception as e:
        dlog("FALLO LOOP GENERAL -> {}".format(e))
        lcd_show("FALLO LOOP", str(e)[:16])
        time.sleep(3)