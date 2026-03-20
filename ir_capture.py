from machine import Pin
import time

ir = Pin(15, Pin.IN)

print("IR capture listo")

while True:
    if ir.value() == 0:
        print("Señal IR detectada")
        time.sleep(0.2)
