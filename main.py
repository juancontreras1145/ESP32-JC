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
# WIFI INFO
# =========================

wlan = network.WLAN(network.STA_IF)

def wifi_ip():
    if wlan.isconnected():
        return wlan.ifconfig()[0]
    return "Sin WiFi"

def wifi_rssi():
    try:
        return wlan.status("rssi")
    except:
        return None

def wifi_calidad():
    rssi = wifi_rssi()
    if rssi is None:
        return "Sin dato"
    if rssi >= -55:
        return "Excelente"
    elif rssi >= -67:
        return "Buena"
    elif rssi >= -75:
        return "Regular"
    else:
        return "Debil"

# =========================
# HORA NTP
# =========================

def obtener_fecha_hora_chile():
    try:
        ntptime.settime()
        rtc = RTC()
        y, m, d, wd, hh, mm, ss, sub = rtc.datetime()

        # Ajuste Chile continental aprox UTC-3
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

# Pantalla inicial de actualización
lcd_print("Actualizado", "{} {}".format(fecha, hora))
time.sleep(4)

while True:
    # Pantalla 1: IP
    lcd_print("WiFi OK" if wlan.isconnected() else "Sin WiFi", wifi_ip())
    time.sleep(3)

    # Pantalla 2: Calidad/RSSI
    rssi = wifi_rssi()
    if rssi is None:
        lcd_print("Conexion", "Sin dato RSSI")
    else:
        lcd_print("WiFi: {}".format(wifi_calidad()), "RSSI: {} dBm".format(rssi))
    time.sleep(3)

    # Pantalla 3: Fecha/hora última sync
    lcd_print("Actualizado", "{} {}".format(fecha, hora))
    time.sleep(3)