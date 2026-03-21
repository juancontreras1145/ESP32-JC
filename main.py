import machine
import time
from machine import Pin, I2C
import sys

# ==============================
# CONFIG
# ==============================

IR_PIN = 4
SDA_PIN = 8
SCL_PIN = 9

# ==============================
# LCD
# ==============================

def lcd_init():

    try:
        from lcd import LCD
        i2c = I2C(0, sda=Pin(SDA_PIN), scl=Pin(SCL_PIN))
        lcd = LCD(i2c, 0x27)
        lcd.clear()
        lcd.putstr("LCD OK")
        print("LCD OK")
        return lcd

    except Exception as e:
        print("LCD ERROR:", e)
        return None


lcd = lcd_init()

def lcd_print(l1="", l2=""):
    if lcd:
        lcd.clear()
        lcd.move_to(0,0)
        lcd.putstr(str(l1))
        lcd.move_to(0,1)
        lcd.putstr(str(l2))


# ==============================
# IR RECEIVER
# ==============================

try:
    ir = Pin(IR_PIN, Pin.IN)
    print("IR OK")
    lcd_print("IR SENSOR", "OK")
except Exception as e:
    print("IR ERROR:", e)
    lcd_print("IR ERROR", str(e))
    sys.exit()


# ==============================
# CAPTURA
# ==============================

lcd_print("Esperando", "senal IR")

pulsos = []

last = time.ticks_us()

while True:

    v = ir.value()

    now = time.ticks_us()
    dur = time.ticks_diff(now, last)

    if dur > 100:
        pulsos.append(dur)
        last = now

    if len(pulsos) > 0 and dur > 50000:

        lcd_print("Pulsos:", str(len(pulsos)))

        print("======== CAPTURA ========")
        print("Total pulsos:", len(pulsos))
        print(pulsos)

        try:
            f = open("ir_signal.txt","w")
            f.write(str(pulsos))
            f.close()

            lcd_print("Guardado", str(len(pulsos)))

        except:
            lcd_print("ERROR", "guardar")

        time.sleep(3)

        pulsos = []
        lcd_print("Esperando", "senal IR")