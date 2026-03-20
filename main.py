from machine import Pin
import time

print("MODO CAPTURA IR")

ir = Pin(15, Pin.IN)

while True:

    last = ir.value()
    pulses = []
    start = time.ticks_us()

    while time.ticks_diff(time.ticks_us(), start) < 500000:

        v = ir.value()

        if v != last:
            now = time.ticks_us()
            pulses.append(time.ticks_diff(now, start))
            start = now
            last = v

    if len(pulses) > 20:
        print("CAPTURADO:")
        print(pulses)