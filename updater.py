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
CHUNK_SIZE = 512
MIN_VALID_SIZE = 16


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


# Compatibilidad con distintas versiones/puertos de MicroPython
# Algunos urequests exponen r.raw.read(), otros no.
def _read_chunk(resp, size):
    try:
        return resp.raw.read(size)
    except:
        return None


def download_to_temp(url, filename):
    if requests is None:
        raise Exception("urequests no disponible")

    newf = temp_name(filename)
    remove_if_exists(newf)

    resp = None
    total = 0
    try:
        resp = requests.get(url)
        status = getattr(resp, "status_code", None)
        if status != 200:
            raise Exception("HTTP {}".format(status))

        with open(newf, "wb") as f:
            # Intento preferente: lectura por bloques desde socket/raw
            used_stream = False
            while True:
                chunk = _read_chunk(resp, CHUNK_SIZE)
                if chunk is None:
                    break
                used_stream = True
                if not chunk:
                    break
                if isinstance(chunk, str):
                    chunk = chunk.encode("utf-8")
                f.write(chunk)
                total += len(chunk)
                gc.collect()

            # Fallback para puertos que no expongan raw.read()
            if not used_stream:
                data = None
                try:
                    data = resp.content
                except:
                    try:
                        txt = resp.text
                        data = txt.encode("utf-8")
                    except:
                        data = None

                if data is None:
                    raise Exception("sin contenido")

                f.write(data)
                total += len(data)
                del data
                gc.collect()

        if total < MIN_VALID_SIZE:
            raise Exception("archivo muy pequeno")

        # Validacion simple: evitar grabar HTML/error en vez de .py
        with open(newf, "rb") as f:
            head = f.read(120)
        low = head.lower()
        if (b"<html" in low) or (b"<!doctype" in low):
            raise Exception("respuesta HTML invalida")

        return total
    except:
        remove_if_exists(newf)
        raise
    finally:
        try:
            if resp:
                resp.close()
        except:
            pass


def safe_commit(filename):
    newf = temp_name(filename)
    bakf = backup_name(filename)

    if newf not in os.listdir():
        raise Exception("temp faltante")

    remove_if_exists(bakf)

    had_old = filename in os.listdir()
    if had_old:
        try:
            os.rename(filename, bakf)
        except Exception as e:
            raise Exception("backup fallo: {}".format(e))

    try:
        os.rename(newf, filename)
        remove_if_exists(bakf)
    except Exception as e:
        # rollback
        try:
            remove_if_exists(filename)
        except:
            pass
        try:
            if bakf in os.listdir():
                os.rename(bakf, filename)
        except:
            pass
        try:
            remove_if_exists(newf)
        except:
            pass
        raise Exception("commit fallo: {}".format(e))


def update_file(filename):
    url = BASE_URL + filename
    log("Descargando {}".format(filename))
    lcd_msg("Actualizando", filename)
    size = download_to_temp(url, filename)
    safe_commit(filename)
    log("OK {} ({} bytes)".format(filename, size))


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
            time.sleep(0.4)
        except Exception as e:
            msg = "{} -> {}".format(f, e)
            log("FAIL " + msg)
            fail.append(msg)
            gc.collect()
            time.sleep(0.4)

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
        "fail": fail,
    }
