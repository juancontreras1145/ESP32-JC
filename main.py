# main.py
# Programa principal

import time
import sensor
import lcd
import webserver

lcd.init()
lcd.print("Sistema", "Iniciando")

sensor.init()

webserver.start()

while True:
    try:
        t, h = sensor.read()
        lcd.print("Temp:{:.1f}".format(t), "Hum:{:.1f}".format(h))
        print("Temp:", t, "Hum:", h)
    except Exception as e:
        print("Sensor error:", e)

    time.sleep(5)
