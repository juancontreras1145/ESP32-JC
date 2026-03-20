from machine import Pin, PWM
import time

IR_PIN = 5
CARRIER = 38000

pwm = PWM(Pin(IR_PIN))
pwm.freq(CARRIER)

def send():
    pwm.duty(512)
    time.sleep_ms(100)
    pwm.duty(0)

while True:
    print("Enviando IR")
    send()
    time.sleep(5)
