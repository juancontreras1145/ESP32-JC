from machine import Pin
import time

print("IR EMISOR INICIADO")

# LED IR conectado al GPIO5
ir_led = Pin(5, Pin.OUT)

# señal capturada (ejemplo de la tuya)
signal = [240,35,75,3319,215,7634,219,1994,197,1958,389,2034]

def send_ir(data):
    print("Enviando señal IR")
    
    state = 1
    
    for t in data:
        ir_led.value(state)
        time.sleep_us(t)
        state = 1 - state
        
    ir_led.value(0)
    print("Señal enviada")

while True:
    
    send_ir(signal)
    
    time.sleep(5)