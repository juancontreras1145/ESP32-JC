from machine import Pin, I2C
import time
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
# WIFI SCAN
# =========================

wlan = network.WLAN(network.STA_IF)
wlan.active(True)

def limpiar_ssid(ssid_bytes):
    try:
        ssid = ssid_bytes.decode("utf-8").strip()
        if ssid == "":
            return "<Oculta>"
        return ssid
    except:
        return "<SSID?>"

def escanear_redes():
    try:
        redes = wlan.scan()
        # scan devuelve:
        # (ssid, bssid, channel, RSSI, security, hidden)
        redes_limpias = []

        for r in redes:
            ssid = limpiar_ssid(r[0])
            canal = r[2]
            rssi = r[3]
            redes_limpias.append((ssid, canal, rssi))

        # ordenar por mejor señal
        redes_limpias.sort(key=lambda x: x[2], reverse=True)
        return redes_limpias

    except Exception as e:
        print("Error scan:", e)
        return []

# =========================
# MAIN
# =========================

lcd_init()
lcd_print("Escaneando...", "WiFi cercanas")
time.sleep(2)

while True:
    redes = escanear_redes()

    if not redes:
        lcd_print("Sin redes", "detectadas")
        time.sleep(3)
        continue

    total = len(redes)

    for i, red in enumerate(redes):
        ssid, canal, rssi = red

        # linea 1: nombre
        linea1 = ssid[:16]

        # linea 2: rssi y canal
        linea2 = "{} {}dBm C{}".format(i + 1, rssi, canal)

        lcd_print(linea1, linea2)

        print("Red:", ssid, "RSSI:", rssi, "Canal:", canal)

        time.sleep(3)