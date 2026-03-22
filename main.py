# =========================================
# ESP32 JC Monitor v64
# Integrado: interior + exterior + amaneciendo
# logs + JSON + estado + CSV + LCD rotativo
# =========================================

import time
import socket
import network
import dht
import os
import gc
import math
import machine
import ntptime
from machine import Pin, I2C

# ------------------------------
# AUTO UPDATE
# ------------------------------
def _updated_result(res):
    try:
        if res is True or res == 1:
            return True
        if isinstance(res, dict):
            return bool(res.get("updated") or res.get("ok"))
    except:
        pass
    return False

try:
    import updater
    if _updated_result(updater.update()):
        time.sleep(0.5)
        machine.reset()
except Exception as e:
    print("Updater error:", e)

VERSION = "ESP32 JC Monitor v64"

# -----------------------------
# CONFIG
# -----------------------------
LCD_SDA = 8
LCD_SCL = 9
LCD_ADDR = 0x27

DHT_PIN = 4

CSV_FILE = "temperaturas.csv"
LOG_FILE = "main.log"

INTERVALO_GUARDADO = 600
INTERVALO_EXTERIOR = 1800
TIMEOUT_WEB = 1
REFRESCO_WEB = 12
PAUSA_LCD_BOOT = 1.2
ROTACION_LCD_SEG = 3

REINTENTOS_SENSOR = 3
DELAY_REINTENTO_SENSOR = 1

UTC_OFFSET_HORAS = -3

TEMP_OFFSET = 0.0
HUM_OFFSET = 0.0

TEMP_BAJA = 18.0
TEMP_ALTA = 28.0
HUM_BAJA = 40.0
HUM_ALTA = 70.0

MAX_LOG_LINES = 220
MAX_CSV_LINES = 1440
WEB_TOKEN = "jc123"
ENABLE_FULL_HOME = False

# Ubicacion fija por defecto
LAT = -33.0475
LON = -71.4425
UBICACION = "Quilpue, Valparaiso"

# -----------------------------
# ESTADO GLOBAL
# -----------------------------
inicio_epoch = time.time()
ultimo_guardado = 0
ultimo_cambio_lcd = 0
indice_lcd = 0

temperatura_actual = None
humedad_actual = None
temperatura_prev = None
humedad_prev = None
ultima_lectura_epoch = None

temp_ext = None
hum_ext = None
wind_ext = None
rain_ext = None
cloud_ext = None
weather_code_ext = None
sunrise_ext = "--:--"
sunset_ext = "--:--"
last_ext_update = 0
ext_error = "Sin datos"

sensor_ok = False
sensor_error = "Sin lectura"

lcd_ok = False
lcd_error = "Ninguno"

server_ok = False
server_error = "Ninguno"

wifi_ip = "Sin WiFi"
ntp_ok = False
ntp_error = "Sin sincronizar"

contador_lecturas = 0
contador_guardados = 0
contador_hits = 0
contador_errores_sensor = 0
contador_errores_lcd = 0
contador_errores_web = 0

guardado_activo = True
lcd_activo = True

sensor = None
lcd = None
server = None

# cache de consejos / amanecer
ultimo_consejo = ""
consejo_lcd_cache = ""
sunrise_places_cache = ""
sunrise_label_cache = ""
jornada_cache = ""

# -----------------------------
# HELPERS
# -----------------------------
def safe_str(x, n=16):
    try:
        return str(x)[:n]
    except:
        return "?"

def mem_free():
    try:
        gc.collect()
        return gc.mem_free()
    except:
        return -1

def now_epoch():
    try:
        return int(time.time())
    except:
        return 0

def local_epoch():
    return now_epoch() + (UTC_OFFSET_HORAS * 3600)

def local_tuple():
    try:
        return time.localtime(local_epoch())
    except:
        return (2000,1,1,0,0,0,0,0)

def local_dt():
    try:
        t = local_tuple()
        fecha = "{:04d}-{:02d}-{:02d}".format(t[0], t[1], t[2])
        hora = "{:02d}:{:02d}:{:02d}".format(t[3], t[4], t[5])
        return fecha, hora
    except:
        return "----/--/--", "--:--:--"

def fecha_texto():
    return local_dt()[0]

def hora_texto():
    return local_dt()[1]

def uptime_texto():
    seg = max(0, int(time.time() - inicio_epoch))
    h = seg // 3600
    m = (seg % 3600) // 60
    s = seg % 60
    return "{:02d}:{:02d}:{:02d}".format(h, m, s)

def fmt1(x):
    if x is None:
        return "--.-"
    try:
        return "{:.1f}".format(float(x))
    except:
        return "--.-"

def fmt1c(x):
    try:
        return fmt1(x)
    except:
        return "--.-"

def fmt_int(x):
    if x is None:
        return "--"
    try:
        return str(int(round(float(x), 0)))
    except:
        return "--"

def exists_file(name):
    try:
        return name in os.listdir()
    except:
        return False

def clamp_text(text, n=16):
    s = str(text)
    if len(s) <= n:
        return s
    return s[:n]

def html_escape(s):
    try:
        s = str(s)
        s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
        return s
    except:
        return ""

def json_escape(s):
    try:
        s = str(s)
        s = s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ').replace('\r', ' ')
        return s
    except:
        return ""

def to_bool_text(v):
    return "true" if v else "false"

def to_json_number(v):
    if v is None:
        return "null"
    try:
        return str(round(float(v), 1))
    except:
        return "null"

def route_path(req):
    try:
        line = req.split("\r\n")[0]
        parts = line.split(" ")
        if len(parts) >= 2:
            return parts[1]
    except:
        pass
    return "/"

def split_path_query(path):
    try:
        if "?" in path:
            p, q = path.split("?", 1)
        else:
            p, q = path, ""
        args = {}
        if q:
            for pair in q.split("&"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                else:
                    k, v = pair, ""
                args[k] = v
        return p, args
    except:
        return path, {}

def auth_ok(args):
    if WEB_TOKEN == "":
        return True
    try:
        return args.get("token", "") == WEB_TOKEN
    except:
        return False

def protected_path(path):
    return path in (
        "/leer", "/actualizar_exterior", "/sync_time", "/borrar_csv",
        "/borrar_logs", "/toggle_log", "/lcd_on", "/lcd_off", "/reiniciar"
    )

def maybe_rotate_csv():
    try:
        if not exists_file(CSV_FILE):
            return
        with open(CSV_FILE, "r") as f:
            lines = f.readlines()
        if len(lines) <= MAX_CSV_LINES:
            return
        fecha = fecha_texto().replace("-", "")
        backup = "temperaturas_" + fecha + ".csv"
        i = 1
        while exists_file(backup):
            backup = "temperaturas_" + fecha + "_" + str(i) + ".csv"
            i += 1
        with open(backup, "w") as fb:
            for line in lines:
                fb.write(line)
        ensure_csv()
        append_log("CSV rotado a " + backup)
    except Exception as e:
        append_log("CSV rotate error: {}".format(e), "WARN")

def detect_condensation_risk():
    dp_in = dew_point(temperatura_actual, humedad_actual)
    dp_out = dew_point(temp_ext, hum_ext)
    if dp_in is None:
        return "Sin datos"
    try:
        if dp_in >= 18:
            return "Alto"
        if dp_out is not None and dp_out + 1 < dp_in and hum_ext is not None and hum_ext < 75:
            return "Baja al ventilar"
        if dp_in >= 15:
            return "Medio"
        return "Bajo"
    except:
        return "Sin datos"

def compact_series(values, n=18):
    if not values:
        return []
    if len(values) <= n:
        return values
    step = len(values) / float(n)
    out = []
    i = 0.0
    while int(i) < len(values) and len(out) < n:
        out.append(values[int(i)])
        i += step
    return out[:n]

# -----------------------------
# LOGS
# -----------------------------
def append_log(msg, level="INFO"):
    fecha, hora = local_dt()
    line = "[{} {}][{}] {}".format(fecha, hora, level, msg)
    print(line)

    try:
        lines = []
        if exists_file(LOG_FILE):
            with open(LOG_FILE, "r") as f:
                lines = f.readlines()

        lines.append(line + "\n")

        if len(lines) > MAX_LOG_LINES:
            lines = lines[-MAX_LOG_LINES:]

        with open(LOG_FILE, "w") as f:
            for l in lines:
                f.write(l)
    except Exception as e:
        print("[LOG_FAIL]", e)

def read_logs():
    try:
        if exists_file(LOG_FILE):
            with open(LOG_FILE, "r") as f:
                return f.read()
    except Exception as e:
        return "Error leyendo logs: {}".format(e)
    return "Sin logs"

def clear_logs():
    try:
        if exists_file(LOG_FILE):
            os.remove(LOG_FILE)
        append_log("Logs reiniciados")
        return True, "Logs reiniciados"
    except Exception as e:
        return False, str(e)

# -----------------------------
# RED / NTP
# -----------------------------
def wifi_conectado():
    try:
        return network.WLAN(network.STA_IF).isconnected()
    except:
        return False

def wifi_rssi():
    try:
        wlan = network.WLAN(network.STA_IF)
        if wlan.isconnected():
            return wlan.status("rssi")
    except:
        pass
    return None

def refresh_ip():
    global wifi_ip
    try:
        wlan = network.WLAN(network.STA_IF)
        if wlan.isconnected():
            wifi_ip = wlan.ifconfig()[0]
        else:
            wifi_ip = "Sin WiFi"
    except:
        wifi_ip = "Sin WiFi"

def sync_time_ntp():
    global ntp_ok, ntp_error
    try:
        ntptime.settime()
        ntp_ok = True
        ntp_error = "Ninguno"
        append_log("Hora NTP sincronizada")
        return True
    except Exception as e:
        ntp_ok = False
        ntp_error = str(e)
        append_log("NTP error: {}".format(e), "WARN")
        return False

# -----------------------------
# LCD
# -----------------------------
def init_lcd():
    global lcd, lcd_ok, lcd_error
    try:
        from lcd import LCD
        i2c = I2C(0, sda=Pin(LCD_SDA), scl=Pin(LCD_SCL))
        lcd = LCD(i2c, LCD_ADDR, cols=16, rows=2)
        try:
            lcd.backlight_on()
        except:
            pass
        lcd.clear()
        lcd_ok = True
        lcd_error = "Ninguno"
        append_log("LCD inicializado")
        return True
    except Exception as e:
        lcd = None
        lcd_ok = False
        lcd_error = str(e)
        append_log("LCD init error: {}".format(e), "ERROR")
        return False

def lcd_msg(l1="", l2="", pausa=0, centrado=False, scroll_row=None, scroll_delay=170, scroll_loops=1):
    global lcd_ok, lcd_error, contador_errores_lcd

    if not lcd_activo or lcd is None:
        return

    try:
        if centrado:
            lcd.message_centered(str(l1), str(l2))
        else:
            lcd.message(str(l1), str(l2))

        if scroll_row == 0 and len(str(l1)) > 16:
            lcd.scroll_text(str(l1), row=0, delay_ms=scroll_delay, loops=scroll_loops)
        elif scroll_row == 1 and len(str(l2)) > 16:
            lcd.scroll_text(str(l2), row=1, delay_ms=scroll_delay, loops=scroll_loops)
        elif scroll_row == 2:
            if len(str(l1)) > 16:
                lcd.scroll_text(str(l1), row=0, delay_ms=scroll_delay, loops=scroll_loops)
            if len(str(l2)) > 16:
                lcd.scroll_text(str(l2), row=1, delay_ms=scroll_delay, loops=scroll_loops)

        lcd_ok = True
        lcd_error = "Ninguno"
    except Exception as e:
        contador_errores_lcd += 1
        lcd_ok = False
        lcd_error = str(e)
        append_log("LCD write error: {}".format(e), "ERROR")

    if pausa > 0:
        time.sleep(pausa)

def lcd_off_total():
    global lcd_activo
    lcd_activo = False
    try:
        if lcd is not None:
            lcd.clear()
            lcd.backlight_off()
    except:
        pass
    append_log("LCD apagado")

def lcd_on_total():
    global lcd_activo
    lcd_activo = True
    init_lcd()
    try:
        if lcd is not None:
            lcd.backlight_on()
    except:
        pass
    append_log("LCD encendido")

# -----------------------------
# SENSOR INTERIOR
# -----------------------------
def init_sensor():
    global sensor
    try:
        sensor = dht.DHT22(Pin(DHT_PIN))
        append_log("Sensor DHT22 inicializado")
        return True
    except Exception as e:
        sensor = None
        append_log("Sensor init error: {}".format(e), "ERROR")
        return False

def read_sensor():
    global temperatura_actual, humedad_actual, temperatura_prev, humedad_prev
    global ultima_lectura_epoch, sensor_ok, sensor_error
    global contador_lecturas, contador_errores_sensor

    if sensor is None:
        if not init_sensor():
            sensor_ok = False
            sensor_error = "No inicia sensor"
            contador_errores_sensor += 1
            return False

    for intento in range(1, REINTENTOS_SENSOR + 1):
        try:
            sensor.measure()

            t = round(sensor.temperature() + TEMP_OFFSET, 1)
            h = round(sensor.humidity() + HUM_OFFSET, 1)

            if h < 0:
                h = 0.0
            if h > 100:
                h = 100.0

            temperatura_prev = temperatura_actual
            humedad_prev = humedad_actual

            temperatura_actual = t
            humedad_actual = h
            ultima_lectura_epoch = local_epoch()

            sensor_ok = True
            sensor_error = "Ninguno"
            contador_lecturas += 1
            return True

        except Exception as e:
            sensor_ok = False
            sensor_error = "Intento {}: {}".format(intento, e)
            contador_errores_sensor += 1
            append_log("Sensor lectura error: {}".format(sensor_error), "WARN")
            time.sleep(DELAY_REINTENTO_SENSOR)

    return False

# -----------------------------
# EXTERIOR / CLIMA
# -----------------------------
def _find_json_body(raw_text):
    i = raw_text.find("{")
    if i >= 0:
        return raw_text[i:]
    return raw_text

def _parse_number_after(key, txt):
    i = txt.find(key)
    if i < 0:
        return None
    j = i + len(key)
    num = ""
    allowed = "-0123456789."
    while j < len(txt) and txt[j] in allowed:
        num += txt[j]
        j += 1
    try:
        return float(num)
    except:
        return None

def _parse_first_from_array(key, txt):
    i = txt.find(key)
    if i < 0:
        return None
    j = i + len(key)
    out = ""
    while j < len(txt):
        ch = txt[j]
        if ch == '"' or ch == "," or ch == "]":
            break
        out += ch
        j += 1
    return out

def fetch_weather_outside():
    global temp_ext, hum_ext, wind_ext, rain_ext, cloud_ext
    global weather_code_ext, sunrise_ext, sunset_ext
    global last_ext_update, ext_error

    if not wifi_conectado():
        ext_error = "Sin WiFi"
        return False

    try:
        import urequests
    except Exception as e:
        ext_error = "Sin urequests"
        append_log("Exterior: sin urequests {}".format(e), "WARN")
        return False

    url = (
        "https://api.open-meteo.com/v1/forecast"
        "?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation,cloud_cover,weather_code"
        "&daily=sunrise,sunset"
        "&timezone=auto"
    ).format(lat=LAT, lon=LON)

    try:
        r = urequests.get(url)
        txt = None
        try:
            data = r.json()
        except:
            data = None
            try:
                txt = r.text
            except:
                txt = ""
        finally:
            try:
                r.close()
            except:
                pass

        if data is None:
            txt = _find_json_body(txt)
            temp_ext = _parse_number_after('"temperature_2m":', txt)
            hum_ext = _parse_number_after('"relative_humidity_2m":', txt)
            wind_ext = _parse_number_after('"wind_speed_10m":', txt)
            rain_ext = _parse_number_after('"precipitation":', txt)
            cloud_ext = _parse_number_after('"cloud_cover":', txt)
            weather_code_ext = _parse_number_after('"weather_code":', txt)
            sr = _parse_first_from_array('"sunrise":["', txt)
            ss = _parse_first_from_array('"sunset":["', txt)
        else:
            current = data.get("current", {})
            daily = data.get("daily", {})
            temp_ext = current.get("temperature_2m")
            hum_ext = current.get("relative_humidity_2m")
            wind_ext = current.get("wind_speed_10m")
            rain_ext = current.get("precipitation")
            cloud_ext = current.get("cloud_cover")
            weather_code_ext = current.get("weather_code")
            sr_arr = daily.get("sunrise", [])
            ss_arr = daily.get("sunset", [])
            sr = sr_arr[0] if sr_arr else None
            ss = ss_arr[0] if ss_arr else None

        if sr and "T" in str(sr):
            sunrise_ext = str(sr).split("T")[1][:5]
        elif sr:
            sunrise_ext = str(sr)[:5]
        else:
            sunrise_ext = "--:--"

        if ss and "T" in str(ss):
            sunset_ext = str(ss).split("T")[1][:5]
        elif ss:
            sunset_ext = str(ss)[:5]
        else:
            sunset_ext = "--:--"

        last_ext_update = now_epoch()
        ext_error = "Ninguno"
        append_log("Clima exterior actualizado")
        return True

    except Exception as e:
        ext_error = str(e)
        append_log("Clima exterior error: {}".format(e), "WARN")
        return False

# -----------------------------
# CALCULOS
# -----------------------------
def dew_point(temp, hum):
    try:
        if temp is None or hum is None or hum <= 0:
            return None
        a = 17.27
        b = 237.7
        alpha = ((a * temp) / (b + temp)) + math.log(hum / 100.0)
        dp = (b * alpha) / (a - alpha)
        return round(dp, 1)
    except:
        return None

def comfort(temp, hum):
    if temp is None or hum is None:
        return "Sin datos"
    if 20 <= temp <= 24 and 40 <= hum <= 60:
        return "Bueno"
    if 18 <= temp <= 27 and 35 <= hum <= 70:
        return "Regular"
    return "Malo"

def cold_state(temp, hum):
    if temp is None or hum is None:
        return "Sin datos"
    if 20 <= temp <= 22 and 45 <= hum <= 60:
        return "Muy bueno"
    if 19 <= temp <= 24 and 40 <= hum <= 70:
        return "Aceptable"
    return "Poco favorable"

def trend(curr, prev):
    if curr is None or prev is None:
        return "Sin ref."
    dif = round(curr - prev, 2)
    if dif > 0.2:
        return "Sube"
    if dif < -0.2:
        return "Baja"
    return "Estable"

def temp_trend():
    return trend(temperatura_actual, temperatura_prev)

def hum_trend():
    return trend(humedad_actual, humedad_prev)

def alerts(temp, hum):
    out = []
    if temp is None or hum is None:
        return ["Sin sensor"]

    if temp < TEMP_BAJA:
        out.append("Temperatura baja")
    if temp > TEMP_ALTA:
        out.append("Temperatura alta")
    if hum < HUM_BAJA:
        out.append("Humedad baja")
    if hum > HUM_ALTA:
        out.append("Humedad alta")

    dp = dew_point(temp, hum)
    if dp is not None and dp > 16:
        out.append("Riesgo de condensacion")

    if not out:
        out.append("Ninguna")
    return out

def comfort_icon():
    c = comfort(temperatura_actual, humedad_actual)
    if c == "Bueno":
        return "🟢"
    if c == "Regular":
        return "🟡"
    return "🔴"

def compare_inside_outside():
    if temperatura_actual is None or temp_ext is None:
        return "Sin comparacion"

    diff = round(temperatura_actual - temp_ext, 1)
    dp_in = dew_point(temperatura_actual, humedad_actual)
    dp_out = dew_point(temp_ext, hum_ext)

    if temp_ext + 1 < temperatura_actual and hum_ext is not None and hum_ext <= 75:
        if dp_in is not None and dp_out is not None and dp_out + 1 < dp_in:
            return "Conviene ventilar"
        return "Ventilar con revision"
    if temp_ext > temperatura_actual + 1:
        return "Afuera mas calido"
    if hum_ext is not None and hum_ext > 80:
        return "Afuera muy humedo"
    if abs(diff) <= 1:
        return "Ambiente parecido"
    return "Evaluar ventana"

def jornada_actual():
    try:
        h = local_tuple()[3]
    except:
        h = 0

    if 5 <= h <= 7:
        return "Amaneciendo"
    if 8 <= h <= 11:
        return "Manana"
    if 12 <= h <= 14:
        return "Mediodia"
    if 15 <= h <= 18:
        return "Tarde"
    if 19 <= h <= 22:
        return "Noche"
    return "Madrugada"

def sunrise_places():
    try:
        h = time.localtime(now_epoch())[3]
    except:
        h = 0

    fr = [
        ("Pacifico Este", "Samoa, Tonga, Kiribati, Fiji"),
        ("Oceania", "Auckland, Wellington, Fiji, Samoa"),
        ("NZ / Pacifico", "Nueva Zelanda, Chatham, Fiji, Tonga"),
        ("Australia Este", "Sydney, Melbourne, Brisbane, Hobart"),
        ("Australia", "Canberra, Gold Coast, Adelaide, Darwin"),
        ("Asia Sur-Este", "Papua, Guam, Japon Sur, Filipinas"),
        ("Asia Oriental", "Tokio, Osaka, Seul, Taipei"),
        ("China / Japon", "Shanghai, Beijing, Hong Kong, Okinawa"),
        ("Sudeste Asiatico", "Bangkok, Hanoi, Manila, Kuala Lumpur"),
        ("SE Asia", "Singapur, Yakarta, Bali, Ho Chi Minh"),
        ("Asia del Sur", "Calcuta, Daca, Katmandu, Colombo"),
        ("India / Centro Asia", "Nueva Delhi, Karachi, Lahore, Kabul"),
        ("Medio Oriente", "Dubai, Abu Dhabi, Mascate, Teheran"),
        ("Arabia / Africa Este", "Riad, Doha, Kuwait, Nairobi"),
        ("Europa Este", "Atenas, Bucarest, Sofia, Estambul"),
        ("Europa Central", "Roma, Berlin, Viena, Praga"),
        ("Europa Oeste", "Madrid, Paris, Lisboa, Londres"),
        ("Africa Oeste", "Casablanca, Dakar, Accra, Abiyan"),
        ("Atlantico", "Azores, Cabo Verde, Madeira, Canarias"),
        ("Sudamerica Este", "Sao Paulo, Rio, Montevideo, Buenos Aires"),
        ("Cono Sur", "Santiago, Valparaiso, Mendoza, Cordoba"),
        ("Andes / Caribe", "Lima, Quito, Bogota, La Paz"),
        ("Norteamerica Este", "Miami, Nueva York, Toronto, Montreal"),
        ("Norteamerica", "Chicago, Dallas, Ciudad de Mexico, Denver"),
    ]
    return fr[h % 24]

def sunrise_region():
    return sunrise_places()[0]

def sunrise_places_text(max_len=None):
    txt = sunrise_places()[1]
    if max_len is not None:
        return clamp_text(txt, max_len)
    return txt

def line_for_lcd(label, value, unit=""):
    if value is None:
        if label == "Exterior":
            return "Exterior s/dato"
        if label == "Interior":
            return "Interior s/dato"
        if label == "Humedad":
            return "Humedad s/dato"
        return clamp_text(label + " s/dato", 16)

    valor = fmt1c(value)
    txt = "{} {}{}".format(label, valor, (" " + unit) if unit else "")
    if len(txt) <= 16:
        return txt

    if unit == "%":
        txt = "{} {} %".format(label, fmt1c(value))
        if len(txt) <= 16:
            return txt

    valor = fmt_int(value)
    txt = "{} {}{}".format(label, valor, (" " + unit) if unit else "")
    if len(txt) <= 16:
        return txt

    if label == "Exterior":
        txt = "Ext {}{}".format(fmt1c(value), (" " + unit) if unit else "")
    elif label == "Interior":
        txt = "Int {}{}".format(fmt1c(value), (" " + unit) if unit else "")
    elif label == "Humedad":
        txt = "Hum {} %".format(fmt1c(value))
    else:
        txt = "{} {}{}".format(label[:4], fmt1c(value), (" " + unit) if unit else "")
    return clamp_text(txt, 16)

def consejo_lcd(texto):
    s = str(texto).strip()
    if len(s) <= 16:
        return s
    s = s.replace("temperatura", "temp")
    s = s.replace("interior", "int")
    s = s.replace("exterior", "ext")
    s = s.replace("humedad", "hum")
    s = s.replace("ventilacion", "ventila")
    s = s.replace("hidratarse", "hidratar")
    s = s.replace("descansa", "descanso")
    s = s.replace("aprovecha", "usa")
    s = s.replace("mantener", "mant")
    s = s.replace("revisar", "revisa")
    return clamp_text(s, 16)

def construir_consejos():
    jornada = jornada_actual()

    consejos_base = {
        "Madrugada": [
            "Hora de descanso y silencio",
            "Evita luz fuerte antes de dormir",
            "Abriga si baja la temperatura",
            "Ventila solo si afuera esta seco",
            "Ideal para dejar todo listo",
            "Momento de calma y orden",
            "Baja el brillo de pantallas",
            "Toma agua antes de dormir",
            "Revisa si hay condensacion",
            "Mantener ambiente estable ayuda",
            "Si hace frio, cierra ventanas",
            "Buena hora para descansar el cuerpo",
            "Evita corrientes de aire frias",
            "Ajusta ropa de cama segun clima",
            "Cuida ruido y luz del espacio",
            "Deja listo lo de la manana",
            "No sobrecalientes la pieza",
            "Evita humedad atrapada",
            "Respira aire limpio y tranquilo",
            "Descanso primero, pantalla despues",
        ],
        "Amaneciendo": [
            "Empieza el dia con aire fresco",
            "Buena hora para ventilar breve",
            "Activa el cuerpo con calma",
            "Revisa como amanecio la humedad",
            "Luz natural ayuda a despertar",
            "Aprovecha el aire de la manana",
            "Ideal para ordenar el espacio",
            "Buen momento para hidratarte",
            "Ajusta ropa segun temperatura",
            "Si afuera esta seco, ventila",
            "Abre cortinas y deja entrar luz",
            "Temperatura suave, arranque tranquilo",
            "Una revision rapida del clima sirve",
            "Rutina corta y constante funciona",
            "Evita encierro si el aire esta pesado",
            "Renueva el ambiente unos minutos",
            "Observa si hay rocio o humedad",
            "Comienza con ritmo parejo",
            "Despierta con menos pantalla",
            "Mueve el cuerpo aunque sea poco",
        ],
        "Manana": [
            "Buena hora para tareas clave",
            "Mantener orden ayuda al foco",
            "Hidratarse mejora la jornada",
            "Aprovecha la luz natural",
            "Si hay humedad alta, ventila",
            "Hora ideal para moverse un poco",
            "Revisa confort antes de seguir",
            "Evita calor acumulado temprano",
            "Un ambiente fresco rinde mejor",
            "Mantener aire limpio suma energia",
            "Ajusta ventanas segun exterior",
            "Haz pausas cortas cada cierto rato",
            "Si el sol pega fuerte, modera entrada",
            "Buena hora para avanzar fuerte",
            "Evita ropa muy abrigada si ya sube",
            "Controla temperatura antes del mediodia",
            "Confort estable, mejor rendimiento",
            "Ideal para comenzar tareas largas",
            "Una mesa ordenada rinde mas",
            "Menos calor, mas enfoque",
        ],
        "Mediodia": [
            "Hora de pausa y recarga",
            "Evita encierro con calor acumulado",
            "Hidratarse ahora es clave",
            "Si sube mucho la temperatura, baja actividad",
            "Busca sombra o aire fresco",
            "Revisa si conviene ventilar",
            "Comer liviano ayuda al confort",
            "No te olvides del agua",
            "El calor del dia ya se nota",
            "Buena hora para resetear el ambiente",
            "Ajusta cortinas si entra mucho sol",
            "Evita humedad atrapada al almuerzo",
            "Pausa corta, energia mejor",
            "Respira y afloja el ritmo",
            "Si hay bochorno, mueve aire",
            "Revisa interior versus exterior",
            "No acumules calor innecesario",
            "Manten circulacion de aire",
            "Temperatura controlada, mejor descanso",
            "Momento justo para una pausa",
        ],
        "Tarde": [
            "Buen tramo para cerrar pendientes",
            "Revisa si conviene ventilar otra vez",
            "Si el ambiente carga, renuevalo",
            "Mantener confort evita cansancio",
            "Haz una pausa breve si baja energia",
            "Controla calor acumulado de la tarde",
            "El aire fresco ayuda a seguir",
            "Buen momento para ordenar",
            "Cierra el dia con ambiente comodo",
            "Si afuera mejora, aprovecha ventilacion",
            "Baja humedad si el exterior acompana",
            "No dejes que el calor se quede",
            "Revisa ventanas antes de anochecer",
            "Estabilidad ambiental suma foco",
            "Termina fuerte, pero sin sobrecarga",
            "Acomoda el espacio para la noche",
            "Evita encierro innecesario",
            "Una vuelta de aire puede servir",
            "Confort bueno, tarde mas liviana",
            "Hora de afinar detalles",
        ],
        "Noche": [
            "Baja el ritmo y ordena el ambiente",
            "Ideal para dejar todo listo",
            "Evita exceso de pantallas",
            "Si hay humedad alta, ventila con criterio",
            "Una temperatura templada ayuda",
            "Hora de cerrar ventanas si enfria",
            "Prepara un descanso comodo",
            "Ambiente estable mejora la noche",
            "No dejes calor encerrado",
            "Menos ruido, mejor descanso",
            "Revisa si se formo condensacion",
            "Mantener calma ayuda a dormir",
            "Luz tenue favorece el descanso",
            "Ventila breve si afuera esta seco",
            "No sobrecargues la pieza de calor",
            "Ropa ligera si el interior esta tibio",
            "Abriga si cae la temperatura",
            "Una ultima revision del clima sirve",
            "Momento de soltar la jornada",
            "Respira profundo y baja cambios",
        ],
    }

    extras_temp_frio = [
        "Hace frio: abrigo liviano ayuda",
        "Frio interior: mejor cerrar corrientes",
        "Temperatura baja: evita piso frio",
        "Si baja mas, suma una capa",
        "Frio marcado: no ventiles mucho",
        "Ambiente fresco: abriga pies y manos",
        "Frio + humedad: cuidado con el cuerpo",
        "Abriga sin encerrar humedad",
        "No dejes ventanas abiertas de mas",
        "Si el aire corta, cierra parcial",
        "Templar un poco puede ayudar",
        "Revisa si la sensacion es menor al dato",
        "Con frio, una bebida tibia suma",
        "Evita cambios bruscos de temperatura",
        "Pieza fresca: confort puede caer",
        "Controla corrientes cercanas",
        "Frio temprano: parte con calma",
        "Ajusta ropa antes de salir",
        "Si el exterior esta peor, conserva calor",
        "Frio sostenido: busca estabilidad",
    ]

    extras_temp_calor = [
        "Hace calor: agua y aire fresco",
        "Calor interior: baja esfuerzo un rato",
        "Temperatura alta: busca sombra",
        "Si afuera esta mejor, ventila",
        "Calor + humedad: ambiente pesado",
        "Bochorno: mover aire ayuda",
        "Evita calor acumulado adentro",
        "Ropa liviana mejora el confort",
        "No cierres todo si falta aire",
        "Calor fuerte: pausas cortas sirven",
        "Revisa si pega sol directo",
        "Ambiente caluroso: baja carga",
        "Ventilar puede aliviar rapido",
        "Calor seco: hidratarse mas",
        "Calor humedo: prioriza aire",
        "Si sube demasiado, baja actividad",
        "Controla entrada de sol",
        "No esperes a sentirte agotado",
        "El confort cae con bochorno",
        "En calor, menos encierro",
    ]

    extras_hum_baja = [
        "Humedad baja: toma agua",
        "Ambiente seco: cuida garganta",
        "Puede resecar nariz y ojos",
        "Ventila con moderacion si seca mas",
        "El aire seco fatiga mas",
        "Un pano humedo cerca puede ayudar",
        "Evita resequedad prolongada",
        "Controla labios y garganta",
        "Humedad baja: confort irregular",
        "No abuses de aire muy seco",
        "Seco adentro: hidrata y descansa",
        "Puede sentirse frio mas facil",
        "Ambiente seco pide mas agua",
        "Revisa si la ventilacion seca de mas",
        "La resequedad tambien molesta",
        "Mantener equilibrio ayuda",
        "Poca humedad no siempre es mejor",
        "Ojo con polvo en ambiente seco",
        "Puede irritar si dura mucho",
        "Compensa con hidratacion",
    ]

    extras_hum_alta = [
        "Humedad alta: ojo con bochorno",
        "Ambiente humedo: ventila si se puede",
        "Puede aparecer condensacion",
        "Humedo adentro: revisa ventanas",
        "Si afuera esta seco, aprovecha",
        "Humedad alta baja el confort",
        "No dejes aire estancado",
        "Ventilar corto puede ayudar",
        "Exceso de humedad pesa en el cuerpo",
        "Observa paredes y vidrios",
        "Humedo y tibio: combinacion pesada",
        "Conviene mover aire",
        "No cierres todo si ya esta cargado",
        "Revisa punto de rocio",
        "Ambiente humedo: menos comodidad",
        "Si hay olor a encierro, renueva",
        "Humedo constante requiere control",
        "Ojo con ropa y telas humedas",
        "Puede sentirse mas calor del real",
        "No ignores la humedad alta",
    ]

    extras_compare = [
        "Interior mejor que exterior: conserva",
        "Exterior mejor: podria convenir ventilar",
        "Ambientes parecidos: sin apuro",
        "Afuera muy humedo: ventilar con criterio",
        "Afuera mas fresco: revisa ventana",
        "Afuera mas calido: evita meter calor",
        "Compara antes de abrir todo",
        "Unos minutos pueden bastar",
        "Si afuera ayuda, aprovecha",
        "Si afuera empeora, espera",
        "Ventilar no siempre mejora",
        "Primero compara, luego decide",
        "El exterior manda la estrategia",
        "Abrir de mas puede jugar en contra",
        "Busca equilibrio, no extremos",
        "Con diferencia minima, no apures",
        "El punto de rocio tambien importa",
        "Interior y exterior deben leerse juntos",
        "No te guies solo por temperatura",
        "La humedad cambia la jugada",
    ]

    extras_riesgo = [
        "Riesgo bajo: ambiente controlado",
        "Riesgo medio: revisa ventilacion",
        "Riesgo alto: ojo con condensacion",
        "Si ves vidrio empanado, actua",
        "El punto de rocio orienta bien",
        "Condensacion puede aparecer sin aviso",
        "Mejor prevenir que encerrar humedad",
        "Riesgo alto pide revision rapida",
        "Observa rincones frios",
        "Ambiente estable reduce riesgo",
        "Menos humedad, menos problema",
        "El calor con humedad complica",
        "Si enfria de golpe, revisa",
        "Riesgo medio no conviene ignorarlo",
        "Unos minutos de aire pueden salvar",
        "No subestimes el rocio interior",
        "Control fino evita sorpresas",
        "Ventana correcta, mejor resultado",
        "El clima exterior cambia el riesgo",
        "Mira el confort junto al rocio",
    ]

    base = list(consejos_base.get(jornada, []))

    try:
        if temperatura_actual is not None:
            if temperatura_actual < 18:
                base.extend(extras_temp_frio)
            elif temperatura_actual > 27:
                base.extend(extras_temp_calor)
            else:
                base.extend(extras_temp_frio[:10])
                base.extend(extras_temp_calor[:10])
    except:
        pass

    try:
        if humedad_actual is not None:
            if humedad_actual < 40:
                base.extend(extras_hum_baja)
            elif humedad_actual > 70:
                base.extend(extras_hum_alta)
            else:
                base.extend(extras_hum_baja[:10])
                base.extend(extras_hum_alta[:10])
    except:
        pass

    base.extend(extras_compare)
    base.extend(extras_riesgo)

    try:
        reg, lugares = sunrise_places()
        base.append("Amaneciendo en {}".format(reg))
        base.append("Pista solar: {}".format(lugares))
    except:
        pass

    base.append("Jornada actual: {}".format(jornada))
    return base

def consejo_actual():
    consejos = construir_consejos()
    if not consejos:
        return "Sin consejo"
    try:
        idx = (local_epoch() // ROTACION_LCD_SEG) % len(consejos)
    except:
        idx = 0
    return consejos[int(idx)]

# -----------------------------
# CSV
# -----------------------------
def ensure_csv():
    try:
        if not exists_file(CSV_FILE):
            with open(CSV_FILE, "w") as f:
                f.write("fecha,hora,epoch_local,temperatura,humedad,temp_ext,hum_ext,punto_rocio,confort,resfriado,comparacion\n")
            append_log("CSV creado")
    except Exception as e:
        append_log("CSV init error: {}".format(e), "ERROR")

def save_csv(temp, hum):
    global contador_guardados

    if not guardado_activo:
        return False

    try:
        maybe_rotate_csv()
        fecha, hora = local_dt()
        dp = dew_point(temp, hum)
        c = comfort(temp, hum)
        r = cold_state(temp, hum)
        comp = compare_inside_outside()

        with open(CSV_FILE, "a") as f:
            f.write("{},{},{},{:.1f},{:.1f},{},{},{},{},{},{}\n".format(
                fecha,
                hora,
                local_epoch(),
                temp,
                hum,
                "" if temp_ext is None else "{:.1f}".format(temp_ext),
                "" if hum_ext is None else "{:.1f}".format(hum_ext),
                "" if dp is None else "{:.1f}".format(dp),
                c,
                r,
                comp
            ))

        contador_guardados += 1
        append_log("Registro CSV guardado")
        return True
    except Exception as e:
        append_log("CSV save error: {}".format(e), "ERROR")
        return False

def read_csv():
    try:
        with open(CSV_FILE, "r") as f:
            return f.read()
    except Exception as e:
        return "Error leyendo CSV: {}".format(e)

def clear_csv():
    try:
        if exists_file(CSV_FILE):
            os.remove(CSV_FILE)
        ensure_csv()
        append_log("CSV reiniciado")
        return True, "CSV reiniciado"
    except Exception as e:
        return False, str(e)

def parse_csv_rows():
    rows = []
    try:
        with open(CSV_FILE, "r") as f:
            lines = f.readlines()[1:]

        for line in lines:
            p = line.strip().split(",")
            if len(p) < 11:
                continue
            try:
                rows.append({
                    "fecha": p[0],
                    "hora": p[1],
                    "epoch": int(p[2]),
                    "temp": float(p[3]),
                    "hum": float(p[4]),
                    "temp_ext": None if p[5] == "" else float(p[5]),
                    "hum_ext": None if p[6] == "" else float(p[6]),
                })
            except:
                pass
    except:
        pass
    return rows

def stats():
    data = {
        "count": 0,
        "tmin": None, "tmax": None, "tavg": None,
        "hmin": None, "hmax": None, "havg": None,
    }

    rows = parse_csv_rows()
    if not rows:
        return data

    temps = [x["temp"] for x in rows]
    hums = [x["hum"] for x in rows]

    data["count"] = len(temps)
    data["tmin"] = min(temps)
    data["tmax"] = max(temps)
    data["tavg"] = sum(temps) / len(temps)
    data["hmin"] = min(hums)
    data["hmax"] = max(hums)
    data["havg"] = sum(hums) / len(hums)
    return data

# -----------------------------
# LCD ROTATIVO
# -----------------------------
def rotate_lcd(force=False):
    global ultimo_cambio_lcd, indice_lcd
    global ultimo_consejo, consejo_lcd_cache, sunrise_places_cache, sunrise_label_cache, jornada_cache

    if not lcd_activo or lcd is None:
        return

    ahora = now_epoch()
    if not force and (ahora - ultimo_cambio_lcd < ROTACION_LCD_SEG):
        return

    ultimo_cambio_lcd = ahora
    ultimo_consejo = consejo_actual()
    consejo_lcd_cache = consejo_lcd(ultimo_consejo)
    sunrise_label_cache = sunrise_region()
    sunrise_places_cache = sunrise_places_text()
    jornada_cache = jornada_actual()

    exterior_line = line_for_lcd("Exterior", temp_ext, "C")
    hum_ext_line = line_for_lcd("Humedad", hum_ext, "%")

    screens = [
        {"l1": line_for_lcd("Interior", temperatura_actual, "C"), "l2": line_for_lcd("Humedad", humedad_actual, "%")},
        {"l1": exterior_line, "l2": hum_ext_line},
        {"l1": "Confort", "l2": comfort(temperatura_actual, humedad_actual), "center": True, "scroll": 1},
        {"l1": "Comparacion", "l2": compare_inside_outside(), "center": True, "scroll": 1},
        {"l1": "Amaneciendo", "l2": sunrise_places_cache, "center": True, "scroll": 1},
        {"l1": "Jornada", "l2": jornada_cache, "center": True},
        {"l1": "Consejo", "l2": ultimo_consejo, "center": True, "scroll": 1},
        {"l1": "Hora " + hora_texto()[:8], "l2": wifi_ip, "scroll": 1},
    ]

    if indice_lcd >= len(screens):
        indice_lcd = 0

    scr = screens[indice_lcd]
    lcd_msg(
        scr.get("l1", ""),
        scr.get("l2", ""),
        0,
        scr.get("center", False),
        scr.get("scroll", None),
        160,
        1
    )

    indice_lcd += 1
    if indice_lcd >= len(screens):
        indice_lcd = 0

# -----------------------------
# WEB
# -----------------------------
def style_base():
    return """
    <style>
    body{font-family:Arial,sans-serif;background:#07111f;color:#eef4ff;margin:0;padding:12px}
    .wrap{max-width:980px;margin:auto}
    .card{background:#0d1b2a;border:1px solid #1f4f88;border-radius:14px;padding:14px;margin-bottom:12px}
    .title{font-size:24px;font-weight:bold;margin-bottom:8px;color:#f2f7ff}
    .sub{color:#b7c8e6;font-size:14px;margin-bottom:4px}
    .grid2,.grid3{display:grid;gap:12px}
    .grid2{grid-template-columns:1fr 1fr}
    .grid3{grid-template-columns:1fr 1fr 1fr}
    .big{font-size:34px;font-weight:bold;color:#ffffff}
    .ok{color:#66e3a3;font-weight:bold}
    .bad{color:#ff7b7b;font-weight:bold}
    .btn{display:inline-block;padding:10px 12px;background:#295a96;color:#eef6ff;text-decoration:none;border-radius:10px;font-weight:bold;margin-right:6px;margin-top:6px;border:1px solid #4f86c6}
    .btn2{background:#162b45;color:#dfeaff}
    .mono{font-family:monospace;background:#040b16;padding:8px;border-radius:10px;white-space:pre-wrap;overflow-wrap:break-word}
    .pill{display:inline-block;margin:4px 6px 0 0;padding:7px 10px;border-radius:999px;font-size:13px;font-weight:bold}
    .alert{background:#5f1d2a;color:#ffd5db}
    .okpill{background:#153247;color:#cfe8ff}
    @media (max-width:700px){.grid2,.grid3{grid-template-columns:1fr}}
    </style>
    """

def svg_series(values, title="Serie", color="#79afff", alto=180, ancho=800):
    if not values:
        return "<div class='mono'>Sin datos para grafico</div>"

    vals = values[-30:]
    if len(vals) < 2:
        vals = vals + vals

    vmin = min(vals)
    vmax = max(vals)
    if vmax == vmin:
        vmax += 1

    points = []
    for i, v in enumerate(vals):
        x = int(i * (ancho - 40) / (len(vals) - 1)) + 20
        y = int((alto - 40) - ((v - vmin) / (vmax - vmin)) * (alto - 80)) + 20
        points.append("{},{}".format(x, y))

    poly = " ".join(points)

    return """
    <div class="card">
        <div class="title" style="font-size:20px;">{title}</div>
        <svg width="100%" viewBox="0 0 {ancho} {alto}" preserveAspectRatio="none">
            <rect x="0" y="0" width="{ancho}" height="{alto}" fill="#07101d" rx="14"/>
            <polyline fill="none" stroke="{color}" stroke-width="4" points="{poly}" />
            <text x="20" y="20" fill="#b7c8e6" font-size="14">Min: {vmin}</text>
            <text x="{tx}" y="20" fill="#b7c8e6" font-size="14">Max: {vmax}</text>
        </svg>
    </div>
    """.format(
        title=title,
        ancho=ancho,
        alto=alto,
        color=color,
        poly=poly,
        vmin=round(vmin, 1),
        vmax=round(vmax, 1),
        tx=ancho - 140
    )

def page_home(full=False):
    st = stats()
    rows = parse_csv_rows()
    al = alerts(temperatura_actual, humedad_actual)
    rssi = wifi_rssi()

    alerts_html = "".join(
        '<div class="pill alert">{}</div>'.format(html_escape(x)) if x != "Ninguna"
        else '<div class="pill okpill">{}</div>'.format(html_escape(x))
        for x in al
    )

    temps = compact_series([x["temp"] for x in rows], 18)
    hums = compact_series([x["hum"] for x in rows], 18)
    graphs = ""
    if full or ENABLE_FULL_HOME:
        graphs = svg_series(temps, "Grafico temperatura") + svg_series(hums, "Grafico humedad", "#68d2ff")

    token_q = "?token={}".format(WEB_TOKEN) if WEB_TOKEN else ""
    full_url = "/?full=1"
    if WEB_TOKEN:
        full_url += "&token={}".format(WEB_TOKEN)
    lock_txt = "Activo" if WEB_TOKEN else "No configurado"

    return """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="{refresh}">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{version}</title>
{style}
</head>
<body>
<div class="wrap">
    <div class="card">
        <div class="title">{version}</div>
        <div class="sub">IP: {ip}</div>
        <div class="sub">Ubicacion base: {ubic}</div>
        <div class="sub">Fecha: {fecha}</div>
        <div class="sub">Hora: {hora}</div>
        <div class="sub">Uptime: {uptime}</div>
        <div class="sub">NTP: <span class="{ntp_class}">{ntp_state}</span></div>
        <div class="sub">Sensor: <span class="{sensor_class}">{sensor_state}</span></div>
        <div class="sub">WiFi: <span class="{wifi_class}">{wifi_state}</span></div>
        <div class="sub">RSSI: {rssi}</div>
        <div class="sub">Seguridad token: {lock_txt}</div>
        <div class="sub">Ultimo error sensor: {sensor_error}</div>
        <div class="sub">Ultimo error exterior: {ext_error}</div>
    </div>

    <div class="grid2">
        <div class="card">
            <div class="sub">Interior</div>
            <div class="big">{temp} C</div>
            <div class="sub">Humedad: {hum} %</div>
            <div class="sub">Tendencia T: {tt}</div>
            <div class="sub">Tendencia H: {th}</div>
        </div>
        <div class="card">
            <div class="sub">Exterior</div>
            <div class="big">{temp_ext} C</div>
            <div class="sub">Humedad: {hum_ext} %</div>
            <div class="sub">Viento: {wind} km/h</div>
            <div class="sub">Lluvia: {rain} mm</div>
            <div class="sub">Nubosidad: {cloud} %</div>
        </div>
    </div>

    <div class="grid2">
        <div class="card">
            <div class="sub">Confort ambiental</div>
            <div class="big">{icon} {comfort}</div>
        </div>
        <div class="card">
            <div class="sub">Condensacion</div>
            <div class="big">{cond}</div>
            <div class="sub">Punto de rocio interior: {dp} C</div>
        </div>
    </div>

    <div class="grid2">
        <div class="card">
            <div class="sub">Comparacion interior vs exterior</div>
            <div class="big">{compare}</div>
        </div>
        <div class="card">
            <div class="sub">Como viene para resfriado</div>
            <div class="big">{cold}</div>
        </div>
    </div>

    <div class="grid2">
        <div class="card">
            <div class="sub">Donde esta amaneciendo</div>
            <div class="big">{sun_region}</div>
            <div class="sub">{sun_places}</div>
        </div>
        <div class="card">
            <div class="sub">Sol local</div>
            <div class="big">↑ {sunrise} / ↓ {sunset}</div>
        </div>
    </div>

    <div class="card">
        <div class="title" style="font-size:20px;">Consejo del momento</div>
        <div class="big">{advice}</div>
        <div class="sub">Jornada: {jornada}</div>
    </div>

    <div class="card">
        <div class="title" style="font-size:20px;">Alertas</div>
        {alerts}
    </div>

    <div class="card">
        <div class="title" style="font-size:20px;">Estadisticas</div>
        <div class="grid3">
            <div class="mono">Temp min: {tmin}</div>
            <div class="mono">Temp max: {tmax}</div>
            <div class="mono">Temp prom: {tavg}</div>
            <div class="mono">Hum min: {hmin}</div>
            <div class="mono">Hum max: {hmax}</div>
            <div class="mono">Hum prom: {havg}</div>
        </div>
        <div class="sub" style="margin-top:10px;">Registros guardados: {count}</div>
    </div>

    {graphs}

    <div class="card">
        <div class="title" style="font-size:20px;">Acciones</div>
        <a class="btn" href="/leer{token_q}">Forzar lectura</a>
        <a class="btn btn2" href="/actualizar_exterior{token_q}">Actualizar exterior</a>
        <a class="btn btn2" href="/descargar{token_q}">Descargar CSV</a>
        <a class="btn btn2" href="/estado{token_q}">Estado tecnico</a>
        <a class="btn btn2" href="/logs{token_q}">Ver logs</a>
        <a class="btn btn2" href="/json{token_q}">JSON</a>
        <a class="btn btn2" href="/lcd_on{token_q}">LCD ON</a>
        <a class="btn btn2" href="/lcd_off{token_q}">LCD OFF</a>
        <a class="btn btn2" href="/toggle_log{token_q}">{log_text}</a>
        <a class="btn btn2" href="/sync_time{token_q}">Sincronizar hora</a>
        <a class="btn btn2" href="/borrar_csv{token_q}">Borrar CSV</a>
        <a class="btn btn2" href="/borrar_logs{token_q}">Borrar logs</a>
        <a class="btn btn2" href="/reiniciar{token_q}">Reiniciar</a>
        <a class="btn btn2" href="{full_url}">Vista completa</a>
    </div>
</div>
</body>
</html>
""".format(
        version=html_escape(VERSION),
        refresh=REFRESCO_WEB,
        style=style_base(),
        ip=html_escape(wifi_ip),
        ubic=html_escape(UBICACION),
        fecha=html_escape(fecha_texto()),
        hora=html_escape(hora_texto()),
        uptime=html_escape(uptime_texto()),
        ntp_class="ok" if ntp_ok else "bad",
        ntp_state="Sincronizado" if ntp_ok else "No sincronizado",
        sensor_class="ok" if sensor_ok else "bad",
        sensor_state="OK" if sensor_ok else "ERROR",
        wifi_class="ok" if wifi_conectado() else "bad",
        wifi_state="Conectado" if wifi_conectado() else "Sin WiFi",
        rssi=html_escape("{} dBm".format(rssi) if rssi is not None else "N/D"),
        lock_txt=html_escape(lock_txt),
        sensor_error=html_escape(sensor_error),
        ext_error=html_escape(ext_error),
        temp=html_escape(fmt1(temperatura_actual).replace('.', ',')),
        hum=html_escape(fmt1(humedad_actual).replace('.', ',')),
        temp_ext=html_escape(fmt1(temp_ext).replace('.', ',')),
        hum_ext=html_escape(fmt1(hum_ext).replace('.', ',')),
        wind=html_escape(fmt1(wind_ext).replace('.', ',')),
        rain=html_escape(fmt1(rain_ext).replace('.', ',')),
        cloud=html_escape(fmt1(cloud_ext).replace('.', ',')),
        tt=html_escape(temp_trend()),
        th=html_escape(hum_trend()),
        icon=comfort_icon(),
        comfort=html_escape(comfort(temperatura_actual, humedad_actual)),
        dp=html_escape(fmt1(dew_point(temperatura_actual, humedad_actual)).replace('.', ',')),
        cond=html_escape(detect_condensation_risk()),
        compare=html_escape(compare_inside_outside()),
        cold=html_escape(cold_state(temperatura_actual, humedad_actual)),
        sun_region=html_escape(sunrise_region()),
        sun_places=html_escape(sunrise_places_text()),
        advice=html_escape(consejo_actual()),
        jornada=html_escape(jornada_actual()),
        sunrise=html_escape(sunrise_ext),
        sunset=html_escape(sunset_ext),
        alerts=alerts_html,
        tmin=html_escape(fmt1(st["tmin"]).replace('.', ',')),
        tmax=html_escape(fmt1(st["tmax"]).replace('.', ',')),
        tavg=html_escape(fmt1(st["tavg"]).replace('.', ',')),
        hmin=html_escape(fmt1(st["hmin"]).replace('.', ',')),
        hmax=html_escape(fmt1(st["hmax"]).replace('.', ',')),
        havg=html_escape(fmt1(st["havg"]).replace('.', ',')),
        count=st["count"],
        graphs=graphs,
        log_text="Desactivar guardado" if guardado_activo else "Activar guardado",
        token_q=token_q,
        full_url=full_url,
    )

def page_logs():
    token_q = "?token={}".format(WEB_TOKEN) if WEB_TOKEN else ""
    return """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="12">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Logs</title>
{style}
</head>
<body>
<div class="wrap">
    <div class="card">
        <div class="title">Logs del sistema</div>
        <div class="mono">{logs}</div>
        <a class="btn" href="/{token_q}">Volver</a>
        <a class="btn btn2" href="/borrar_logs{token_q}">Borrar logs</a>
    </div>
</div>
</body>
</html>
""".format(style=style_base(), logs=html_escape(read_logs()), token_q=token_q)

def page_status():
    rssi = wifi_rssi()
    token_q = "?token={}".format(WEB_TOKEN) if WEB_TOKEN else ""
    return """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Estado tecnico</title>
{style}
</head>
<body>
<div class="wrap">
    <div class="card">
        <div class="title">Estado tecnico</div>
        <div class="mono">Version: {version}</div>
        <div class="mono">IP: {ip}</div>
        <div class="mono">Ubicacion: {ubic}</div>
        <div class="mono">Fecha: {fecha}</div>
        <div class="mono">Hora: {hora}</div>
        <div class="mono">Uptime: {uptime}</div>
        <div class="mono">RAM libre: {ram}</div>
        <div class="mono">RSSI: {rssi}</div>
        <div class="mono">NTP OK: {ntp_ok}</div>
        <div class="mono">NTP error: {ntp_error}</div>
        <div class="mono">LCD OK: {lcd_ok}</div>
        <div class="mono">LCD error: {lcd_error}</div>
        <div class="mono">Sensor OK: {sensor_ok}</div>
        <div class="mono">Sensor error: {sensor_error}</div>
        <div class="mono">Servidor OK: {server_ok}</div>
        <div class="mono">Servidor error: {server_error}</div>
        <div class="mono">Exterior temp: {temp_ext}</div>
        <div class="mono">Exterior error: {ext_error}</div>
        <div class="mono">Lecturas: {lecturas}</div>
        <div class="mono">Guardados: {guardados}</div>
        <div class="mono">Hits web: {hits}</div>
        <div class="mono">Errores sensor: {es}</div>
        <div class="mono">Errores LCD: {el}</div>
        <div class="mono">Errores web: {ew}</div>
        <div class="mono">Ultima lectura local: {ultima}</div>
        <div class="mono">CSV: {csv}</div>
        <div class="mono">LOG: {logf}</div>
        <div class="mono">Guardado activo: {log_activo}</div>
        <div class="mono">LCD activo: {lcd_activo}</div>
        <a class="btn" href="/{token_q}">Volver</a>
    </div>
</div>
</body>
</html>
""".format(
        style=style_base(),
        version=VERSION,
        ip=wifi_ip,
        ubic=UBICACION,
        fecha=fecha_texto(),
        hora=hora_texto(),
        uptime=uptime_texto(),
        ram=mem_free(),
        rssi="{} dBm".format(rssi) if rssi is not None else "N/D",
        ntp_ok=ntp_ok,
        ntp_error=ntp_error,
        lcd_ok=lcd_ok,
        lcd_error=lcd_error,
        sensor_ok=sensor_ok,
        sensor_error=sensor_error,
        server_ok=server_ok,
        server_error=server_error,
        temp_ext=fmt1(temp_ext),
        ext_error=ext_error,
        lecturas=contador_lecturas,
        guardados=contador_guardados,
        hits=contador_hits,
        es=contador_errores_sensor,
        el=contador_errores_lcd,
        ew=contador_errores_web,
        ultima=ultima_lectura_epoch,
        csv=CSV_FILE,
        logf=LOG_FILE,
        log_activo=guardado_activo,
        lcd_activo=lcd_activo,
        token_q=token_q
    )

def json_status():
    rssi = wifi_rssi()
    dp_in = dew_point(temperatura_actual, humedad_actual)
    dp_out = dew_point(temp_ext, hum_ext)
    return """{{
  "version": "{version}",
  "device": {{
    "ip": "{ip}",
    "ubicacion": "{ubic}",
    "fecha": "{fecha}",
    "hora": "{hora}",
    "uptime": "{uptime}",
    "rssi_dbm": "{rssi}"
  }},
  "inside": {{
    "temperature_c": {temp_in},
    "humidity_pct": {hum_in},
    "dew_point_c": {dp_in},
    "comfort": "{comfort}",
    "cold_state": "{cold}"
  }},
  "outside": {{
    "temperature_c": {temp_out},
    "humidity_pct": {hum_out},
    "dew_point_c": {dp_out},
    "wind_kmh": {wind},
    "rain_mm": {rain},
    "cloud_pct": {cloud},
    "weather_code": {weather_code},
    "sunrise": "{sunrise}",
    "sunset": "{sunset}"
  }},
  "analysis": {{
    "compare": "{compare}",
    "condensation_risk": "{cond}",
    "sunrise_region": "{sun_region}",
    "sunrise_places": "{sun_places}",
    "jornada": "{jornada}",
    "advice": "{advice}"
  }},
  "status": {{
    "sensor_ok": {sensor_ok},
    "wifi_ok": {wifi_ok},
    "ntp_ok": {ntp_ok},
    "lcd_ok": {lcd_ok},
    "server_ok": {server_ok},
    "ultima_lectura_local": "{ultima}"
  }}
}}""".format(
        version=json_escape(VERSION),
        ip=json_escape(wifi_ip),
        ubic=json_escape(UBICACION),
        fecha=json_escape(fecha_texto()),
        hora=json_escape(hora_texto()),
        uptime=json_escape(uptime_texto()),
        rssi=json_escape("{} dBm".format(rssi) if rssi is not None else "N/D"),
        temp_in=to_json_number(temperatura_actual),
        hum_in=to_json_number(humedad_actual),
        dp_in=to_json_number(dp_in),
        comfort=json_escape(comfort(temperatura_actual, humedad_actual)),
        cold=json_escape(cold_state(temperatura_actual, humedad_actual)),
        temp_out=to_json_number(temp_ext),
        hum_out=to_json_number(hum_ext),
        dp_out=to_json_number(dp_out),
        wind=to_json_number(wind_ext),
        rain=to_json_number(rain_ext),
        cloud=to_json_number(cloud_ext),
        weather_code=to_json_number(weather_code_ext),
        sunrise=json_escape(sunrise_ext),
        sunset=json_escape(sunset_ext),
        compare=json_escape(compare_inside_outside()),
        cond=json_escape(detect_condensation_risk()),
        sun_region=json_escape(sunrise_region()),
        sun_places=json_escape(sunrise_places_text()),
        jornada=json_escape(jornada_actual()),
        advice=json_escape(consejo_actual()),
        sensor_ok=to_bool_text(sensor_ok),
        wifi_ok=to_bool_text(wifi_conectado()),
        ntp_ok=to_bool_text(ntp_ok),
        lcd_ok=to_bool_text(lcd_ok),
        server_ok=to_bool_text(server_ok),
        ultima=json_escape(ultima_lectura_epoch)
    )

# -----------------------------
# HTTP
# -----------------------------
def respond(cl, body, ctype="text/html; charset=utf-8", code="200 OK", extras=None):
    try:
        cl.send("HTTP/1.0 {}\r\n".format(code))
        cl.send("Content-Type: {}\r\n".format(ctype))
        if extras:
            for h in extras:
                cl.send(h + "\r\n")
        cl.send("\r\n")
        cl.send(body)
    except Exception as e:
        append_log("send_response error: {}".format(e), "ERROR")

def init_server():
    global server, server_ok, server_error
    try:
        addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
        server = socket.socket()
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(addr)
        server.listen(5)
        server.settimeout(TIMEOUT_WEB)
        server_ok = True
        server_error = "Ninguno"
        append_log("Servidor web listo")
        return True
    except Exception as e:
        server = None
        server_ok = False
        server_error = str(e)
        append_log("Server init error: {}".format(e), "ERROR")
        return False

def handle_web():
    global contador_hits, server_ok, server_error, contador_errores_web
    global guardado_activo

    if server is None:
        return

    try:
        cl, addr = server.accept()
    except OSError:
        return
    except Exception as e:
        server_ok = False
        server_error = str(e)
        contador_errores_web += 1
        append_log("accept error: {}".format(e), "ERROR")
        return

    try:
        contador_hits += 1
        req = cl.recv(1536)
        req = str(req)
        raw_path = route_path(req)
        path, args = split_path_query(raw_path)
        full = args.get("full", "") == "1"

        if protected_path(path) and not auth_ok(args):
            respond(cl, "<html><body><h1>401 token requerido</h1></body></html>", code="401 Unauthorized")
            return

        if path == "/descargar":
            respond(cl, read_csv(), ctype="text/plain", extras=["Content-Disposition: attachment; filename={}".format(CSV_FILE)])
        elif path == "/logs":
            respond(cl, page_logs())
        elif path == "/estado":
            respond(cl, page_status())
        elif path == "/json":
            if WEB_TOKEN and not auth_ok(args):
                respond(cl, '{"error":"token requerido"}', ctype="application/json; charset=utf-8", code="401 Unauthorized")
            else:
                respond(cl, json_status(), ctype="application/json; charset=utf-8")
        elif path == "/leer":
            ok = read_sensor()
            append_log("Lectura manual {}".format("OK" if ok else "FAIL"))
            rotate_lcd(True)
            respond(cl, page_home(full))
        elif path == "/actualizar_exterior":
            ok = fetch_weather_outside()
            append_log("Actualizar exterior {}".format("OK" if ok else "FAIL"))
            rotate_lcd(True)
            respond(cl, page_home(full))
        elif path == "/sync_time":
            ok = sync_time_ntp()
            append_log("Sincronizacion manual NTP => {}".format(ok))
            rotate_lcd(True)
            respond(cl, page_home(full))
        elif path == "/borrar_csv":
            ok, msg = clear_csv()
            append_log("Accion borrar_csv: {}".format(msg))
            rotate_lcd(True)
            respond(cl, "<html><body><h1>{}</h1><p><a href='/?token={}'>Volver</a></p></body></html>".format(html_escape(msg), WEB_TOKEN))
        elif path == "/borrar_logs":
            ok, msg = clear_logs()
            respond(cl, "<html><body><h1>{}</h1><p><a href='/?token={}'>Volver</a></p></body></html>".format(html_escape(msg), WEB_TOKEN))
        elif path == "/toggle_log":
            guardado_activo = not guardado_activo
            append_log("Guardado activo => {}".format(guardado_activo))
            rotate_lcd(True)
            respond(cl, page_home(full))
        elif path == "/lcd_on":
            lcd_on_total()
            rotate_lcd(True)
            respond(cl, page_home(full))
        elif path == "/lcd_off":
            lcd_off_total()
            respond(cl, page_home(full))
        elif path == "/reiniciar":
            append_log("Reinicio solicitado desde web", "WARN")
            respond(cl, "<html><body><h1>Reiniciando ESP32...</h1></body></html>")
            try:
                cl.close()
            except:
                pass
            time.sleep(1)
            machine.reset()
            return
        else:
            respond(cl, page_home(full))

        server_ok = True
        server_error = "Ninguno"

    except OSError as e:
        if "104" not in str(e):
            server_ok = False
            server_error = str(e)
            contador_errores_web += 1
            append_log("web handler OSError: {}".format(e), "ERROR")

    except Exception as e:
        server_ok = False
        server_error = str(e)
        contador_errores_web += 1
        append_log("web handler error: {}".format(e), "ERROR")

    try:
        cl.close()
    except:
        pass

# -----------------------------
# ARRANQUE
# -----------------------------
append_log("Inicio main.py {}".format(VERSION))
gc.collect()

init_lcd()
lcd_msg("ESP32 JC", "Iniciando", PAUSA_LCD_BOOT, True)
lcd_msg("Clima + Sol", VERSION[-3:], PAUSA_LCD_BOOT, True)

init_sensor()
ensure_csv()
refresh_ip()

if wifi_conectado():
    sync_time_ntp()
    refresh_ip()
    fetch_weather_outside()

init_server()

lcd_msg("Web lista", safe_str(wifi_ip, 16), PAUSA_LCD_BOOT, True)

if read_sensor():
    append_log("Primera lectura sensor OK")
else:
    append_log("Primera lectura sensor FAIL", "WARN")
    lcd_msg("Sensor error", "Sin lectura", PAUSA_LCD_BOOT, True)

ultimo_guardado = now_epoch()

# -----------------------------
# LOOP
# -----------------------------
while True:
    try:
        gc.collect()
        refresh_ip()
        handle_web()
        rotate_lcd(False)

        ahora = now_epoch()

        if ahora - ultimo_guardado >= INTERVALO_GUARDADO:
            if wifi_conectado() and not ntp_ok:
                sync_time_ntp()

            if read_sensor():
                save_csv(temperatura_actual, humedad_actual)
            else:
                append_log("Lectura programada fallo", "WARN")

            if wifi_conectado() and (ahora - last_ext_update >= INTERVALO_EXTERIOR):
                fetch_weather_outside()

            rotate_lcd(True)
            ultimo_guardado = ahora

        if temperatura_actual is None or humedad_actual is None:
            if read_sensor():
                rotate_lcd(True)

        time.sleep(0.2)

    except Exception as e:
        append_log("Loop error: {}".format(e), "ERROR")
        if lcd_activo:
            lcd_msg("Loop error", safe_str(e, 16), 2, True)
        time.sleep(1)
