from machine import Pin, I2C
import time

# Pines I2C
SDA_PIN = 8
SCL_PIN = 9

i2c = I2C(0, sda=Pin(SDA_PIN), scl=Pin(SCL_PIN), freq=400000)
addr = 39

def write_byte(val):
    i2c.writeto(addr, bytes([val]))

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

# inicializar LCD
time.sleep_ms(20)
cmd(0x33)
cmd(0x32)
cmd(0x28)
cmd(0x0C)
cmd(0x06)
cmd(0x01)
time.sleep_ms(5)

# linea 1
for c in "ESP32 OK":
    data(ord(c))

# linea 2
cmd(0xC0)

for c in "LCD FUNCIONA":
    data(ord(c))

while True:
    time.sleep(1)