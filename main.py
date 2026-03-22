
# =========================================
# ESP32 JC Monitor v62
# Integrado: interior + exterior + amaneciendo
# logs + JSON + estado + CSV + LCD rotativo
# + gestor de archivos web (ver / descargar / subir / borrar)
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

VERSION = "ESP32 JC Monitor v62"

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

MAX_UPLOAD_SIZE = 12288
ARCHIVOS_OCULTOS = ("System Volume Information",)

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
        return (2000, 1, 1, 0, 0, 0, 0, 0)

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
        s = s.replace('\\', '\\\\').replace('"', '\"').replace('\n', ' ').replace('\r', ' ')
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

def decode_req(b):
    try:
        return b.decode("utf-8")
    except:
        try:
            return b.decode("latin-1")
        except:
            return str(b)

def route_path(req_text):
    try:
        line = req_text.split("\r\n")[0]
        parts = line.split(" ")
        if len(parts) >= 2:
            return parts[1]
    except:
        pass
    return "/"

def request_method(req_text):
    try:
        line = req_text.split("\r\n")[0]
        parts = line.split(" ")
        if len(parts) >= 1:
            return parts[0]
    except:
        pass
    return "GET"

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
        "/borrar_logs", "/toggle_log", "/lcd_on", "/lcd_off", "/reiniciar",
        "/files", "/upload", "/upload_file", "/download_file", "/delete_file"
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

def file_size_text(name):
    try:
        size = os.stat(name)[6]
        if size < 1024:
            return "{} B".format(size)
        if size < 1024 * 1024:
            return "{:.1f} KB".format(size / 1024.0)
        return "{:.2f} MB".format(size / (1024.0 * 1024.0))
    except:
        return "N/D"

def file_ok_name(name):
    try:
        if not name:
            return False
        if "/" in name or "\\" in name or ".." in name or ":" in name:
            return False
        if name.startswith("."):
            return False
        return True
    except:
        return False

def list_files_sorted():
    out = []
    try:
        items = os.listdir()
        items.sort()
        for name in items:
            if name in ARCHIVOS_OCULTOS:
                continue
            try:
                st = os.stat(name)
                out.append((name, st[6]))
            except:
                out.append((name, 0))
    except:
        pass
    return out

def parse_content_length(req_text):
    try:
        for line in req_text.split("\r\n"):
            low = line.lower()
            if low.startswith("content-length:"):
                return int(line.split(":", 1)[1].strip())
    except:
        pass
    return 0

def parse_boundary(req_text):
    try:
        for line in req_text.split("\r\n"):
            low = line.lower()
            if low.startswith("content-type:") and "boundary=" in line:
                return line.split("boundary=", 1)[1].strip()
    except:
        pass
    return None

def parse_filename_from_part(body_bytes):
    try:
        marker = b'filename="'
        i = body_bytes.find(marker)
        if i < 0:
            return None
        j = i + len(marker)
        k = body_bytes.find(b'"', j)
        if k < 0:
            return None
        name = body_bytes[j:k].decode("utf-8")
        if file_ok_name(name):
            return name
    except:
        pass
    return None

def parse_multipart_file(body_bytes, boundary):
    try:
        bnd = b"--" + boundary.encode()
        header_end = body_bytes.find(b"\r\n\r\n")
        if header_end < 0:
            return None, None
        part_header = body_bytes[:header_end]
        filename = parse_filename_from_part(part_header)
        data_start = header_end + 4

        end_marker = b"\r\n" + bnd
        data_end = body_bytes.find(end_marker, data_start)
        if data_end < 0:
            data_end = len(body_bytes)

        data = body_bytes[data_start:data_end]
        return filename, data
    except:
        return None, None

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

def lcd_msg(l1="", l2="", pausa=0, centrado=False):
    global lcd_ok, lcd_error, contador_errores_lcd

    if not lcd_activo or lcd is None:
        return

    try:
        if centrado:
            lcd.message_centered(str(l1), str(l2))
        else:
            lcd.message(str(l1), str(l2))
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
        "http://api.open-meteo.com/v1/forecast"
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

def sunrise_region():
    try:
        t_utc = time.gmtime(now_epoch())
        h = t_utc[3]
    except:
        h = 0

    zonas = [
        "Pacifico", "Nueva Zelanda", "Australia", "Indonesia",
        "China", "India", "Medio Oriente", "Europa",
        "Africa", "Atlantico", "Sudamerica", "Pacifico",
    ]

    idx = int(h / 2)
    if idx < 0:
        idx = 0
    if idx >= len(zonas):
        idx = len(zonas) - 1
    return zonas[idx]

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

    if not lcd_activo or lcd is None:
        return

    ahora = now_epoch()
    if not force and (ahora - ultimo_cambio_lcd < ROTACION_LCD_SEG):
        return

    ultimo_cambio_lcd = ahora

    screens = [
        ("Interior {} C".format(fmt1(temperatura_actual)),
         "Humedad {} %".format(fmt1(humedad_actual))),

        ("Exterior {} C".format(fmt1(temp_ext)),
         "Humedad {} %".format(fmt1(hum_ext))),

        ("Confort",
         comfort(temperatura_actual, humedad_actual)),

        ("Comparacion",
         clamp_text(compare_inside_outside(), 16)),

        ("Amaneciendo",
         clamp_text(sunrise_region(), 16)),

        ("Hora " + hora_texto()[:8],
         clamp_text(wifi_ip, 16)),
    ]

    if indice_lcd >= len(screens):
        indice_lcd = 0

    a, b = screens[indice_lcd]
    a = clamp_text(a, 16)
    b = clamp_text(b, 16)

    if indice_lcd in (2, 3, 4):
        lcd_msg(a, b, 0, True)
    else:
        lcd_msg(a, b)

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
    .table{width:100%;border-collapse:collapse}
    .table td,.table th{padding:8px;border-bottom:1px solid #22466f;text-align:left}
    input[type=file],input[type=submit]{margin-top:8px}
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
        </div>
        <div class="card">
            <div class="sub">Sol local</div>
            <div class="big">↑ {sunrise} / ↓ {sunset}</div>
        </div>
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
        <a class="btn btn2" href="/files{token_q}">Archivos</a>
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
        temp=html_escape(fmt1(temperatura_actual)),
        hum=html_escape(fmt1(humedad_actual)),
        temp_ext=html_escape(fmt1(temp_ext)),
        hum_ext=html_escape(fmt1(hum_ext)),
        wind=html_escape(fmt1(wind_ext)),
        rain=html_escape(fmt1(rain_ext)),
        cloud=html_escape(fmt1(cloud_ext)),
        tt=html_escape(temp_trend()),
        th=html_escape(hum_trend()),
        icon=comfort_icon(),
        comfort=html_escape(comfort(temperatura_actual, humedad_actual)),
        dp=html_escape(fmt1(dew_point(temperatura_actual, humedad_actual))),
        cond=html_escape(detect_condensation_risk()),
        compare=html_escape(compare_inside_outside()),
        cold=html_escape(cold_state(temperatura_actual, humedad_actual)),
        sun_region=html_escape(sunrise_region()),
        sunrise=html_escape(sunrise_ext),
        sunset=html_escape(sunset_ext),
        alerts=alerts_html,
        tmin=html_escape(fmt1(st["tmin"])),
        tmax=html_escape(fmt1(st["tmax"])),
        tavg=html_escape(fmt1(st["tavg"])),
        hmin=html_escape(fmt1(st["hmin"])),
        hmax=html_escape(fmt1(st["hmax"])),
        havg=html_escape(fmt1(st["havg"])),
        count=st["count"],
        graphs=graphs,
        log_text="Desactivar guardado" if guardado_activo else "Activar guardado",
        token_q=token_q,
        full_url=full_url,
    )

def page_logs():
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
        <a class="btn" href="/?token={token}">Volver</a>
        <a class="btn btn2" href="/borrar_logs?token={token}">Borrar logs</a>
    </div>
</div>
</body>
</html>
""".format(style=style_base(), logs=html_escape(read_logs()), token=WEB_TOKEN)

def page_status():
    rssi = wifi_rssi()
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
        <a class="btn" href="/?token={token}">Volver</a>
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
        token=WEB_TOKEN
    )

def page_files():
    token_q = "?token={}".format(WEB_TOKEN) if WEB_TOKEN else ""
    rows = []
    for name, size in list_files_sorted():
        dl = "/download_file?name={}&token={}".format(name, WEB_TOKEN)
        rm = "/delete_file?name={}&token={}".format(name, WEB_TOKEN)
        rows.append(
            "<tr><td>{}</td><td>{}</td><td>"
            "<a class='btn btn2' href='{}'>Descargar</a>"
            "<a class='btn btn2' href='{}'>Borrar</a>"
            "</td></tr>".format(
                html_escape(name),
                html_escape(file_size_text(name)),
                html_escape(dl),
                html_escape(rm)
            )
        )
    rows_html = "".join(rows) if rows else "<tr><td colspan='3'>Sin archivos</td></tr>"

    return """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Archivos</title>
{style}
</head>
<body>
<div class="wrap">
    <div class="card">
        <div class="title">Gestor de archivos</div>
        <div class="sub">Límite de subida: {max_size} bytes</div>
        <a class="btn" href="/?token={token}">Volver</a>
    </div>

    <div class="card">
        <div class="title" style="font-size:20px;">Subir archivo</div>
        <form action="/upload_file?token={token}" method="post" enctype="multipart/form-data">
            <input type="file" name="file">
            <br>
            <input class="btn" type="submit" value="Subir al ESP32">
        </form>
    </div>

    <div class="card">
        <div class="title" style="font-size:20px;">Archivos actuales</div>
        <table class="table">
            <tr><th>Nombre</th><th>Tamaño</th><th>Acciones</th></tr>
            {rows}
        </table>
    </div>
</div>
</body>
</html>
""".format(style=style_base(), token=WEB_TOKEN, rows=rows_html, max_size=MAX_UPLOAD_SIZE)

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
    "sunrise_region": "{sun_region}"
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
        if isinstance(body, bytes):
            body_bytes = body
        else:
            body_bytes = body.encode("utf-8")

        headers = [
            "HTTP/1.0 {}".format(code),
            "Content-Type: {}".format(ctype),
            "Content-Length: {}".format(len(body_bytes)),
        ]
        if extras:
            for h in extras:
                headers.append(h)

        cl.send("\r\n".join(headers))
        cl.send("\r\n\r\n")
        cl.send(body_bytes)
    except Exception as e:
        append_log("send_response error: {}".format(e), "ERROR")

def send_file_response(cl, filename):
    try:
        if not file_ok_name(filename) or not exists_file(filename):
            respond(cl, "<html><body><h1>Archivo no encontrado</h1></body></html>", code="404 Not Found")
            return

        size = os.stat(filename)[6]
        headers = [
            "HTTP/1.0 200 OK",
            "Content-Type: application/octet-stream",
            "Content-Length: {}".format(size),
            "Content-Disposition: attachment; filename={}".format(filename),
        ]
        cl.send("\r\n".join(headers))
        cl.send("\r\n\r\n")

        with open(filename, "rb") as f:
            while True:
                chunk = f.read(512)
                if not chunk:
                    break
                cl.send(chunk)
    except Exception as e:
        append_log("download error: {}".format(e), "ERROR")
        try:
            respond(cl, "<html><body><h1>Error al descargar</h1></body></html>", code="500 Internal Server Error")
        except:
            pass

def handle_upload_request(cl, req_text, body_start):
    try:
        boundary = parse_boundary(req_text)
        content_length = parse_content_length(req_text)

        if not boundary:
            respond(cl, "<html><body><h1>Boundary no encontrado</h1></body></html>", code="400 Bad Request")
            return

        if content_length <= 0:
            respond(cl, "<html><body><h1>Content-Length invalido</h1></body></html>", code="400 Bad Request")
            return

        if content_length > MAX_UPLOAD_SIZE + 2048:
            respond(cl, "<html><body><h1>Archivo demasiado grande</h1></body></html>", code="413 Payload Too Large")
            return

        body = body_start
        while len(body) < content_length:
            chunk = cl.recv(512)
            if not chunk:
                break
            body += chunk
            if len(body) > MAX_UPLOAD_SIZE + 2048:
                respond(cl, "<html><body><h1>Archivo excede limite</h1></body></html>", code="413 Payload Too Large")
                return

        filename, data = parse_multipart_file(body, boundary)
        if not filename or data is None:
            respond(cl, "<html><body><h1>No se pudo extraer el archivo</h1></body></html>", code="400 Bad Request")
            return

        if len(data) > MAX_UPLOAD_SIZE:
            respond(cl, "<html><body><h1>Archivo supera el limite permitido</h1></body></html>", code="413 Payload Too Large")
            return

        if not file_ok_name(filename):
            respond(cl, "<html><body><h1>Nombre de archivo no permitido</h1></body></html>", code="400 Bad Request")
            return

        with open(filename, "wb") as f:
            f.write(data)

        append_log("Archivo subido: {} ({})".format(filename, len(data)))
        respond(cl, "<html><body><h1>Archivo guardado: {}</h1><p><a href='/files?token={}'>Volver a archivos</a></p></body></html>".format(html_escape(filename), WEB_TOKEN))
    except Exception as e:
        append_log("upload error: {}".format(e), "ERROR")
        respond(cl, "<html><body><h1>Error al subir archivo</h1></body></html>", code="500 Internal Server Error")

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
        req_bytes = cl.recv(1536)
        if not req_bytes:
            try:
                cl.close()
            except:
                pass
            return

        req_text = decode_req(req_bytes)
        method = request_method(req_text)
        raw_path = route_path(req_text)
        path, args = split_path_query(raw_path)
        full = args.get("full", "") == "1"

        header_end = req_bytes.find(b"\r\n\r\n")
        if header_end >= 0:
            body_start = req_bytes[header_end + 4:]
        else:
            body_start = b""

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
            respond(cl, json_status(), ctype="application/json; charset=utf-8")
        elif path == "/files":
            respond(cl, page_files())
        elif path == "/download_file":
            send_file_response(cl, args.get("name", ""))
        elif path == "/delete_file":
            name = args.get("name", "")
            if not file_ok_name(name):
                respond(cl, "<html><body><h1>Nombre no permitido</h1></body></html>", code="400 Bad Request")
            elif not exists_file(name):
                respond(cl, "<html><body><h1>Archivo no existe</h1></body></html>", code="404 Not Found")
            else:
                try:
                    os.remove(name)
                    append_log("Archivo borrado: {}".format(name))
                    respond(cl, "<html><body><h1>Archivo borrado: {}</h1><p><a href='/files?token={}'>Volver</a></p></body></html>".format(html_escape(name), WEB_TOKEN))
                except Exception as e:
                    append_log("delete file error: {}".format(e), "ERROR")
                    respond(cl, "<html><body><h1>No se pudo borrar</h1></body></html>", code="500 Internal Server Error")
        elif path == "/upload":
            respond(cl, page_files())
        elif path == "/upload_file" and method == "POST":
            handle_upload_request(cl, req_text, body_start)
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
