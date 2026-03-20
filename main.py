from machine import Pin, I2C
import time

# ===== LCD =====
LCD_ADDR = 39
i2c = I2C(0, sda=Pin(8), scl=Pin(9), freq=400000)

def write_byte(val):
    i2c.writeto(LCD_ADDR, bytes([val]))

def pulse(data):
    write_byte(data | 0x04)
    time.sleep_us(1)
    write_byte(data & ~0x04)
    time.sleep_us(50)

def send(val, rs):
    high = val & 0xF0
    low = (val << 4) & 0xF0
    write_byte(high | rs | 0x08)
    pulse(high | rs | 0x08)
    write_byte(low | rs | 0x08)
    pulse(low | rs | 0x08)

def cmd(c):
    send(c, 0)

def data(d):
    send(d, 1)

def lcd_init():
    time.sleep_ms(20)
    cmd(0x33)
    cmd(0x32)
    cmd(0x28)
    cmd(0x0C)
    cmd(0x06)
    cmd(0x01)
    time.sleep_ms(5)

def lcd_clear():
    cmd(0x01)
    time.sleep_ms(5)

def lcd_print(line1="", line2=""):
    lcd_clear()
    for c in str(line1)[:16]:
        data(ord(c))
    cmd(0xC0)
    for c in str(line2)[:16]:
        data(ord(c))

# ===== IR receptor =====
IR_PIN = 15
ir = Pin(IR_PIN, Pin.IN)

lcd_init()
lcd_print("IR LISTO", "Esperando...")

def capture_once(timeout_ms=5000, max_edges=180):
    start = time.ticks_ms()
    last = ir.value()
    edges = []

    while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
        v = ir.value()
        if v != last:
            t = time.ticks_us()
            edges.append((t, v))
            last = v
            if len(edges) >= max_edges:
                break

    if len(edges) < 2:
        return []

    pulses = []
    for i in range(1, len(edges)):
        dt = time.ticks_diff(edges[i][0], edges[i-1][0])
        pulses.append(dt)

    return pulses

while True:
    lcd_print("Apunta control", "y presiona")
    time.sleep(1)

    raw = capture_once()

    if raw:
        print("CAPTURADO:")
        print(raw)
        lcd_print("IR capturado", str(len(raw)) + " pulsos")
        time.sleep(3)
    else:
        lcd_print("Sin senal", "reintenta")
        time.sleep(2)