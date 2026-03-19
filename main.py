from machine import Pin, I2C, RTC
import time
import ntptime
import network

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
# WIFI
# =========================

wlan = network.WLAN(network.STA_IF)
wlan.active(True)

def wifi_ip():
    if wlan.isconnected():
        return wlan.ifconfig()[0]
    return "Sin WiFi"

# =========================
# HORA NTP
# =========================

def obtener_fecha_hora_chile():
    try:
        ntptime.settime()
        rtc = RTC()
        y, m, d, wd, hh, mm, ss, sub = rtc.datetime()

        hh -= 3
        if hh < 0:
            hh += 24
            d -= 1

        return "{:02d}/{:02d}".format(d, m), "{:02d}:{:02d}".format(hh, mm)
    except Exception as e:
        print("Error NTP:", e)
        return "Sin fecha", "Sin hora"

# =========================
# MAIN
# =========================

lcd_init()

fecha, hora = obtener_fecha_hora_chile()

while True:
    lcd_print("Actualizado", "{} {}".format(fecha, hora))
    time.sleep(3)

    lcd_print("WiFi OK" if wlan.isconnected() else "Sin WiFi", wifi_ip())
    time.sleep(3)

    lcd_print("Camila Te Quie", "ro Mucho <3")
    time.sleep(3)