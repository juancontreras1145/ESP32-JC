import network
import time

SSID = "S25"
PASSWORD = "12345678"

def connect():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        print("Conectando WiFi...")
        wlan.connect(SSID, PASSWORD)

        timeout = 15
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1

    if wlan.isconnected():
        print("WiFi conectado:", wlan.ifconfig()[0])
    else:
        print("WiFi fallo")
