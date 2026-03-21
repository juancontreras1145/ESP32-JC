import machine
import time
import network
from machine import Pin, I2C

VERSION = "ESP32 JC v1.0"

# WIFI
SSID = "S25"
PASSWORD = "12345678"

# LCD
SDA = 8
SCL = 9
LCD_ADDR = 0x27

# RESCUE PIN (botón BOOT)
SAFE_PIN = 0

# ==============================
# LCD
# ==============================

lcd = None

def lcd_init():
    global lcd
    try:
        from lcd import LCD
        i2c = I2C(0, sda=Pin(SDA), scl=Pin(SCL))
        lcd = LCD(i2c, LCD_ADDR)
        lcd.clear()
        return True
    except:
        lcd = None
        return False

def lcd_msg(l1="", l2=""):
    print(l1, l2)
    if lcd:
        lcd.clear()
        lcd.move_to(0,0)
        lcd.putstr(str(l1))
        lcd.move_to(0,1)
        lcd.putstr(str(l2))
    time.sleep(2)

# ==============================
# INICIO
# ==============================

lcd_init()

lcd_msg("Sistema", VERSION)

# ==============================
# RESCATE
# ==============================

safe = Pin(SAFE_PIN, Pin.IN)

if safe.value() == 0:

    lcd_msg("MODO RESCATE","BOOT")

    import os

    try:
        os.remove("main.py")
        lcd_msg("main.py","ELIMINADO")
    except:
        lcd_msg("Sin main.py","continuando")

    lcd_msg("Reiniciando","...")
    machine.reset()

# ==============================
# WIFI
# ==============================

lcd_msg("Iniciando","WiFi")

wlan = network.WLAN(network.STA_IF)
wlan.active(True)

wlan.connect(SSID, PASSWORD)

timeout = 10

while timeout > 0:

    if wlan.isconnected():
        break

    timeout -= 1
    time.sleep(1)

if wlan.isconnected():

    ip = wlan.ifconfig()[0]

    lcd_msg("WiFi conectado",ip)

else:

    lcd_msg("WiFi","NO conectado")

# ==============================
# WEBREPL
# ==============================

try:

    import webrepl
    webrepl.start()

    lcd_msg("WebREPL","activo")

except:

    lcd_msg("WebREPL","no activo")

# ==============================
# FIN BOOT
# ==============================

lcd_msg("Boot OK","Ejecutando app")
