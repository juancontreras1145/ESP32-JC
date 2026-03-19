from machine import Pin, I2C
import dht
import time

# =========================
# LCD I2C
# =========================
SDA_PIN = 8
SCL_PIN = 9
ADDR = 39   # 0x27

i2c = I2C(0, sda=Pin(SDA_PIN), scl=Pin(SCL_PIN), freq=400000)

def write_byte(val):
    i2c.writeto(ADDR, bytes([val]))

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

# =========================
# SENSOR DHT22
# =========================
sensor = dht.DHT22(Pin(4))

lcd_init()
lcd_print("Probando DHT22", "Espera...")
time.sleep(2)

while True:
    try:
        sensor.measure()
        temp = sensor.temperature()
        hum = sensor.humidity()

        print("Temp:", temp)
        print("Hum:", hum)

        lcd_print("Temp: {} C".format(temp), "Hum: {} %".format(hum))

    except Exception as e:
        print("Error:", e)
        lcd_print("Error sensor", str(e)[:16])

    time.sleep(3)