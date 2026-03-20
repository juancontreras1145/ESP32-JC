# ===== VERSION PARA VERIFICAR UPDATE =====
VERSION = "GITHUB 1.0 - 23:59"

from machine import Pin, I2C
import network
import time
import dht

# -------- LCD --------
from lcd_api import LcdApi
from i2c_lcd import I2cLcd

I2C_ADDR = 0x27
ROWS = 2
COLS = 16

i2c = I2C(0, scl=Pin(22), sda=Pin(21))
lcd = I2cLcd(i2c, I2C_ADDR, ROWS, COLS)

# -------- SENSOR --------
sensor = dht.DHT11(Pin(4))

# -------- WIFI --------
SSID = "TU_WIFI"
PASSWORD = "TU_PASSWORD"

wlan = network.WLAN(network.STA_IF)
wlan.active(True)

lcd.clear()
lcd.putstr("Conectando WiFi")

wlan.connect(SSID, PASSWORD)

timeout = 15

while not wlan.isconnected() and timeout > 0:
    time.sleep(1)
    timeout -= 1

if wlan.isconnected():
    ip = wlan.ifconfig()[0]
else:
    ip = "NO WIFI"

# -------- ARRANQUE --------

lcd.clear()
lcd.move_to(0,0)
lcd.putstr("VERSION:")
lcd.move_to(0,1)
lcd.putstr(VERSION)

print("=================================")
print("ESP32 ACTUALIZADO")
print("VERSION:", VERSION)
print("=================================")

time.sleep(4)

# -------- LOOP --------

while True:

    lcd.clear()

    lcd.move_to(0,0)
    lcd.putstr("IP:")
    lcd.putstr(ip)

    try:
        sensor.measure()
        t = sensor.temperature()
        h = sensor.humidity()

        lcd.move_to(0,1)
        lcd.putstr("T:{}C H:{}%".format(t,h))

    except:
        lcd.move_to(0,1)
        lcd.putstr("Sensor error")

    print("VERSION:", VERSION)
    print("IP:", ip)

    time.sleep(5)