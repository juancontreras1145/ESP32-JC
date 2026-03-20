# updater.py
import urequests
import machine
import os
import time

BASE_URL = "https://raw.githubusercontent.com/juancontreras1145/ESP32-JC/main/"

FILES = [
    "main.py",
    "lcd.py",
    "dht_sensor.py",
    "updater.py"
]

def download_file(filename):
    url = BASE_URL + filename
    tmp_name = filename + ".new"

    print("Descargando:", url)
    r = urequests.get(url)

    if r.status_code != 200:
        r.close()
        raise Exception("HTTP {}".format(r.status_code))

    with open(tmp_name, "wb") as f:
        f.write(r.content)

    r.close()

    if filename in os.listdir():
        try:
            os.remove(filename)
        except:
            pass

    os.rename(tmp_name, filename)
    print("Actualizado:", filename)

def update(reboot=False):
    ok = []
    fail = []

    for f in FILES:
        try:
            download_file(f)
            ok.append(f)
        except Exception as e:
            print("Error update:", f, e)
            fail.append((f, str(e)))

    print("Listo.")
    print("OK:", ok)
    print("FAIL:", fail)

    if reboot and len(fail) == 0:
        print("Reiniciando...")
        time.sleep(1)
        machine.reset()
