from machine import Pin
import time

ir = Pin(15, Pin.IN)

last = ir.value()

print("Esperando señal IR...")

while True:
    v = ir.value()
    
    if v != last:
        print(time.ticks_us(), v)
        last = v