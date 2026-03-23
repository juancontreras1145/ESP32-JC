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


def file_exists(filename):
    try:
        return filename in os.listdir()
    except:
        return False


def read_head(filename, n=400):
    try:
        with open(filename, "r") as f:
            return f.read(n)
    except:
        return ""


def validate_file(filename):
    head = read_head(filename, 400)

    if not head or len(head) < 10:
        raise Exception("archivo vacio o corto")

    if "<html" in head.lower() or "<!doctype" in head.lower():
        raise Exception("respuesta HTML invalida")

    if filename == "main.py":
        if "VERSION =" not in head and "import time" not in head:
            raise Exception("main.py invalido")

    if filename == "lcd.py":
        if "class LCD" not in head and "def " not in head:
            raise Exception("lcd.py invalido")

    if filename == "updater.py":
        if "def update(" not in head and "BASE_URL =" not in head:
            raise Exception("updater.py invalido")

    return True


def download_to_file(url, filename):
    if requests is None:
        raise Exception("urequests no disponible")

    tmp = temp_name(filename)
    bak = backup_name(filename)

    remove_if_exists(tmp)

    r = requests.get(url)
    try:
        if r.status_code != 200:
            raise Exception("HTTP {}".format(r.status_code))

        with open(tmp, "wb") as f:
            while True:
                chunk = r.raw.read(512)
                if not chunk:
                    break
                f.write(chunk)
    finally:
        try:
            r.close()
        except:
            pass

    validate_file(tmp)

    remove_if_exists(bak)

    if file_exists(filename):
        os.rename(filename, bak)

    os.rename(tmp, filename)
    remove_if_exists(bak)


def update_file(filename):
    url = BASE_URL + filename + "?v={}".format(time.time())
    log("Descargando {}".format(filename))
    lcd_msg("Actualizando", filename)

    download_to_file(url, filename)
    gc.collect()

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