import network
import time
import machine

# =========================
# CONFIG
# =========================
WIFI_SSID = "S25"
WIFI_PASS = "12345678"

AP_SSID = "ESP32-RESCATE"
AP_PASS = "12345678"

SAFE_PIN = 0          # boton BOOT
WIFI_TIMEOUT = 15

# LCD real del usuario: paralelo, no usar aquí.
# Este boot es recovery puro, sin depender del LCD.

def log(msg):
    print("[BOOT]", msg)

def start_webrepl():
    try:
        import webrepl
        webrepl.start()
        log("WebREPL OK")
        return True
    except Exception as e:
        log("WebREPL error: {}".format(e))
        return False

def connect_wifi():
    sta = network.WLAN(network.STA_IF)
    sta.active(True)

    if sta.isconnected():
        return True, sta.ifconfig()[0]

    try:
        sta.connect(WIFI_SSID, WIFI_PASS)
        for _ in range(WIFI_TIMEOUT):
            if sta.isconnected():
                return True, sta.ifconfig()[0]
            time.sleep(1)
    except Exception as e:
        log("WiFi error: {}".format(e))

    return False, "0.0.0.0"

def start_rescue_ap():
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid=AP_SSID, password=AP_PASS)
    ip = ap.ifconfig()[0]
    log("AP rescate: {}".format(ip))
    return ip

def safe_mode_requested():
    try:
        btn = machine.Pin(SAFE_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
        return btn.value() == 0
    except Exception as e:
        log("No se pudo leer BOOT: {}".format(e))
        return False

# =========================
# ARRANQUE
# =========================
log("Inicio boot")

if safe_mode_requested():
    log("Modo rescate por BOOT")
    ip = start_rescue_ap()
    start_webrepl()
    log("Conectate a {} y entra a ws://{}:8266".format(AP_SSID, ip))
else:
    ok, ip = connect_wifi()
    if ok:
        log("WiFi OK: {}".format(ip))
        start_webrepl()
    else:
        log("WiFi fallo, entrando a AP rescate")
        ip = start_rescue_ap()
        start_webrepl()
        log("Conectate a {} y entra a ws://{}:8266".format(AP_SSID, ip))

# =========================
# MAIN protegido
# =========================
try:
    import main
except Exception as e:
    log("main.py fallo: {}".format(e))
    log("ESP32 queda en modo seguro con WebREPL activo")
    while True:
        time.sleep(2)