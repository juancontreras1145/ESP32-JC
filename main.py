from machine import Pin
import time

ir = Pin(5, Pin.OUT)

while True:
    ir.value(1)
    time.sleep(1)
    ir.value(0)
    time.sleep(1)