# updater simple para GitHub

import urequests

BASE_URL = "https://raw.githubusercontent.com/juancontreras1145/ESP32-JC/main/"

FILES = [
    "main.py",
    "sensor.py",
    "lcd.py",
    "wifi.py"
]

def update():
    for f in FILES:
        try:
            url = BASE_URL + f
            r = urequests.get(url)
            if r.status_code == 200:
                with open(f, "w") as file:
                    file.write(r.content)
                print("Actualizado:", f)
        except Exception as e:
            print("Error update:", f, e)
