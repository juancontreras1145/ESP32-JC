from machine import Pin, PWM
import time

print("IR EMISOR 38kHz INICIADO")

# ===== CONFIG =====
IR_PIN = 5
CARRIER = 38000
DUTY = 512   # 50%

# ===== PWM IR =====
pwm = PWM(Pin(IR_PIN))
pwm.freq(CARRIER)
pwm.duty(DUTY)

# ===== SEÑAL CAPTURADA (TU BOTON) =====
signal = [
240,35,75,3319,215,7634,219,1994,197,1958,389,2034,156,1795,403,750,
477,970,212,1722,443,840,348,696,423,724,485,872,280,1823,443,1748,
497,1795,457,641,498,1747,593,1646,484,1769,498,1733,484,799
]

def mark(t):
    pwm.duty(DUTY)
    time.sleep_us(t)

def space(t):
    pwm.duty(0)
    time.sleep_us(t)

def send_ir(data):

    mark_state = True

    for t in data:

        if mark_state:
            mark(t)
        else:
            space(t)

        mark_state = not mark_state

    pwm.duty(0)


while True:

    print("Enviando señal IR")

    # repetir 3 veces
    send_ir(signal)
    time.sleep_ms(40)
    send_ir(signal)
    time.sleep_ms(40)
    send_ir(signal)

    print("Señal enviada")

    time.sleep(5)