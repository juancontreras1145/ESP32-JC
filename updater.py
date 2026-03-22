
# updater.py
# Actualizador simple seguro para ESP32

import urequests
import os

BASE_URL="https://raw.githubusercontent.com/juancontreras1145/ESP32-JC/main/"

FILES=["main.py"]

def download_file(name):
    url=BASE_URL+name
    r=urequests.get(url)
    data=r.text
    r.close()
    return data

def update():

    updated=False

    for f in FILES:

        try:

            new=download_file(f)

            if f in os.listdir():
                with open(f,"r") as file:
                    old=file.read()
            else:
                old=""

            if new!=old:
                with open(f,"w") as file:
                    file.write(new)
                updated=True

        except Exception as e:
            print("Update error",e)

    return updated
