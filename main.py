VERSION = 1.0
from machine import Pin, I2C
import time
import network
import dht
import socket

# -------- LCD I2C --------
from lcd_api import LcdApi
from i2c_lcd import I2cLcd

I2C_ADDR = 0x27
I2C_NUM_ROWS = 2
I2C_NUM_COLS = 16

i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)
lcd = I2cLcd(i2c, I2C_ADDR, I2C_NUM_ROWS, I2C_NUM_COLS)

# -------- Sensor DHT --------
sensor = dht.DHT11(Pin(4))

# -------- WIFI --------
ssid = "TU_WIFI"
password = "TU_PASSWORD"

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(ssid, password)

lcd.clear()
lcd.putstr("Conectando WiFi")

timeout = 10
while not wlan.isconnected() and timeout > 0:
    time.sleep(1)
    timeout -= 1

if wlan.isconnected():
    ip = wlan.ifconfig()[0]
else:
    ip = "No WiFi"

# -------- LOOP --------
while True:

    lcd.clear()

    # linea 1 IP
    lcd.move_to(0,0)
    lcd.putstr("IP:")
    lcd.putstr(ip)

    # temperatura / humedad
    try:
        sensor.measure()
        t = sensor.temperature()
        h = sensor.humidity()

        lcd.move_to(0,1)
        lcd.putstr("T:{}C H:{}%".format(t,h))

    except:
        lcd.move_to(0,1)
        lcd.putstr("Sensor error")

    time.sleep(5)