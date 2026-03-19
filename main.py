from machine import Pin, I2C, RTC
import dht
import time
import ntptime
import os

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
# SENSOR
# =========================
sensor = dht.DHT22(Pin(4))

# =========================
# HORA NTP
# =========================
def sync_time_chile():
    try:
        ntptime.settime()
        return True
    except Exception as e:
        print("Error NTP:", e)
        return False

def now_chile():
    rtc = RTC()
    y, m, d, wd, hh, mm, ss, sub = rtc.datetime()

    # Ajuste simple Chile continental UTC-3
    hh -= 3
    if hh < 0:
        hh += 24
        d -= 1

    return y, m, d, hh, mm, ss

def fecha_hora_texto():
    y, m, d, hh, mm, ss = now_chile()
    fecha = "{:02d}/{:02d}".format(d, m)
    hora = "{:02d}:{:02d}".format(hh, mm)
    return fecha, hora

# =========================
# CSV
# =========================
CSV_FILE = "temperaturas.csv"

def init_csv():
    if CSV_FILE not in os.listdir():
        with open(CSV_FILE, "w") as f:
            f.write("fecha,hora,temp,hum\n")

def guardar_registro(fecha, hora, temp, hum):
    with open(CSV_FILE, "a") as f:
        f.write("{},{},{},{}\n".format(fecha, hora, temp, hum))

# =========================
# CONTROL REGISTRO 10 MIN
# =========================
ultimo_minuto_guardado = -1

def toca_guardar(minuto):
    global ultimo_minuto_guardado

    # guardar solo en 00,10,20,30,40,50
    if minuto % 10 == 0 and minuto != ultimo_minuto_guardado:
        ultimo_minuto_guardado = minuto
        return True
    return False

# =========================
# MAIN
# =========================
lcd_init()
lcd_print("Iniciando...", "DHT22 logger")
time.sleep(2)

sync_ok = sync_time_chile()
init_csv()

if sync_ok:
    fecha, hora = fecha_hora_texto()
    lcd_print("Hora sincroniz.", "{} {}".format(fecha, hora))
else:
    lcd_print("Sin hora NTP", "seguira igual")
time.sleep(2)

while True:
    try:
        sensor.measure()
        temp = round(sensor.temperature(), 1)
        hum = round(sensor.humidity(), 1)

        fecha, hora = fecha_hora_texto()
        _, _, _, hh, mm, ss = now_chile()

        # Pantalla normal
        lcd_print("T:{}C H:{}%".format(temp, hum), "{} {}".format(fecha, hora))

        print("Temp:", temp)
        print("Hum:", hum)
        print("Fecha:", fecha, "Hora:", hora)

        # Guardado cada 10 minutos
        if toca_guardar(mm):
            guardar_registro(fecha, hora, temp, hum)
            print("Guardado en CSV")
            lcd_print("Guardado OK", "{} {}".format(fecha, hora))
            time.sleep(2)

    except Exception as e:
        print("Error:", e)
        lcd_print("Error sensor", str(e)[:16])

    time.sleep(5)