import os
import time
import machine
import gc

try:
    import urequests as requests
except:
    requests = None

BASE_URL = "https://raw.githubusercontent.com/juancontreras1145/ESP32-JC/main/"

FILES = [
    "main.py",
    "lcd.py",
    "updater.py",
]

LOG_FILE = "update.log"


def log(msg):
    print("[UPDATER]", msg)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(msg + "\n")
    except:
        pass


def lcd_msg(l1="", l2=""):
    try:
        from lcd import LCD
        from machine import I2C, Pin
        i2c = I2C(0, sda=Pin(8), scl=Pin(9))
        lcd = LCD(i2c, 0x27)
        lcd.clear()
        lcd.move_to(0, 0)
        lcd.putstr(str(l1)[:16])
        lcd.move_to(0, 1)
        lcd.putstr(str(l2)[:16])
    except:
        pass


def fetch_text(url):
    if requests is None:
        raise Exception("urequests no disponible")

    r = requests.get(url)
    try:
        if r.status_code != 200:
            raise Exception("HTTP {}".format(r.status_code))
        return r.text
    finally:
        try:
            r.close()
        except:
            pass


def backup_name(filename):
    return filename + ".bak"


def temp_name(filename):
    return filename + ".new"


def remove_if_exists(filename):
    try:
        if filename in os.listdir():
            os.remove(filename)
    except:
        pass


def safe_replace(filename, content):
    newf = temp_name(filename)
    bakf = backup_name(filename)

    remove_if_exists(newf)
    remove_if_exists(bakf)

    with open(newf, "w", encoding="utf-8") as f:
        f.write(content)

    if filename in os.listdir():
        os.rename(filename, bakf)

    os.rename(newf, filename)

    remove_if_exists(bakf)


def update_file(filename):
    url = BASE_URL + filename
    log("Descargando {}".format(filename))
    lcd_msg("Actualizando", filename)

    content = fetch_text(url)

    if not content or len(content) < 5:
        raise Exception("archivo vacio o invalido")

    safe_replace(filename, content)
    log("OK {}".format(filename))


def update(reboot=False):
    gc.collect()

    ok = []
    fail = []

    log("=== INICIO UPDATE ===")
    lcd_msg("GitHub Update", "iniciando")

    for f in FILES:
        try:
            update_file(f)
            ok.append(f)
            gc.collect()
            time.sleep(0.3)
        except Exception as e:
            msg = "{} -> {}".format(f, e)
            log("FAIL " + msg)
            fail.append(msg)

    if fail:
        lcd_msg("Update FAIL", str(len(fail)) + " errores")
        log("Errores: " + str(fail))
    else:
        lcd_msg("Update OK", str(len(ok)) + " archivos")
        log("Todo actualizado")

    log("=== FIN UPDATE ===")

    if reboot and not fail:
        log("Reiniciando...")
        lcd_msg("Reiniciando", "ESP32")
        time.sleep(2)
        machine.reset()

    return {
        "ok": ok,
        "fail": fail
    }
