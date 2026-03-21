# =========================================
# ESP32 JC - Monitor Ambiental v60
# Web profesional + logs + LCD + JSON
# =========================================

import time
import socket
import network
import dht
import os
import gc
import math
import machine
from machine import Pin, I2C

VERSION = "ESP32 JC Monitor v60"

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
TIMEOUT_WEB = 1
REFRESCO_WEB = 10
PAUSA_LCD_BOOT = 1.5
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

MAX_LOG_LINES = 200

# -----------------------------
# ESTADO GLOBAL
# -----------------------------
inicio_epoch = time.time()
ultimo_guardado = 0
ultima_lectura_epoch = None
ultimo_cambio_lcd = 0
indice_lcd = 0

temperatura_actual = None
humedad_actual = None
temperatura_prev = None
humedad_prev = None

sensor_ok = False
sensor_error = "Sin lectura"

lcd_ok = False
lcd_error = "Ninguno"

server_ok = False
server_error = "Ninguno"

wifi_ip = "Sin WiFi"

contador_lecturas = 0
contador_guardados = 0
contador_hits = 0
contador_errores_sensor = 0
contador_errores_lcd = 0
contador_errores_web = 0
contador_reinicios_logicos = 0

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

def local_dt():
    try:
        t = time.localtime(local_epoch())
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

def exists_file(name):
    try:
        return name in os.listdir()
    except:
        return False

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
# LCD
# -----------------------------
def init_lcd():
    global lcd, lcd_ok, lcd_error
    try:
        from lcd import LCD
        i2c = I2C(0, sda=Pin(LCD_SDA), scl=Pin(LCD_SCL))
        lcd = LCD(i2c, LCD_ADDR, cols=16, rows=2)
        try:
            lcd.reinit()
        except Exception as e:
            append_log("LCD reinit aviso: {}".format(e), "WARN")
        try:
            lcd.backlight_on()
        except Exception as e:
            append_log("LCD backlight aviso: {}".format(e), "WARN")
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
# SENSOR
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

# -----------------------------
# CSV
# -----------------------------
def ensure_csv():
    try:
        if not exists_file(CSV_FILE):
            with open(CSV_FILE, "w") as f:
                f.write("fecha,hora,epoch_local,temperatura,humedad,punto_rocio,confort,resfriado,tendencia_temp,tendencia_hum\n")
            append_log("CSV creado")
    except Exception as e:
        append_log("CSV init error: {}".format(e), "ERROR")

def save_csv(temp, hum):
    global contador_guardados

    if not guardado_activo:
        return False

    try:
        fecha, hora = local_dt()
        dp = dew_point(temp, hum)
        c = comfort(temp, hum)
        r = cold_state(temp, hum)
        tt = temp_trend()
        th = hum_trend()

        with open(CSV_FILE, "a") as f:
            f.write("{},{},{},{:.1f},{:.1f},{},{},{},{},{}\n".format(
                fecha,
                hora,
                local_epoch(),
                temp,
                hum,
                "" if dp is None else "{:.1f}".format(dp),
                c,
                r,
                tt,
                th
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
            if len(p) < 10:
                continue
            try:
                rows.append({
                    "fecha": p[0],
                    "hora": p[1],
                    "epoch": int(p[2]),
                    "temp": float(p[3]),
                    "hum": float(p[4]),
                    "rocio": None if p[5] == "" else float(p[5]),
                    "confort": p[6],
                    "resfriado": p[7],
                    "ttemp": p[8],
                    "thum": p[9],
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
# LCD ROTACION
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
        ("Temp {}C".format(fmt1(temperatura_actual)),
         "Hum  {}%".format(fmt1(humedad_actual))),

        ("Confort",
         comfort(temperatura_actual, humedad_actual)),

        ("Rocio {}C".format(fmt1(dew_point(temperatura_actual, humedad_actual))),
         "Hora " + hora_texto()),

        ("Resfriado",
         safe_str(cold_state(temperatura_actual, humedad_actual), 16)),

        ("WiFi " + ("OK" if wifi_conectado() else "OFF"),
         safe_str(wifi_ip, 16)),

        ("Alerta",
         safe_str(alerts(temperatura_actual, humedad_actual)[0], 16)),
    ]

    if indice_lcd >= len(screens):
        indice_lcd = 0

    a, b = screens[indice_lcd]

    if indice_lcd in (1, 3, 5):
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
    body {
        font-family: Arial, sans-serif;
        background: #07111f;
        color: #eef4ff;
        margin: 0;
        padding: 16px;
    }
    .wrap {
        max-width: 1100px;
        margin: auto;
    }
    .card {
        background: #0d1b2a;
        border: 1px solid #1f4f88;
        border-radius: 18px;
        padding: 18px;
        margin-bottom: 16px;
        box-shadow: 0 0 0 1px rgba(90,140,220,0.05);
    }
    .title {
        font-size: 30px;
        font-weight: bold;
        margin-bottom: 10px;
        color: #f2f7ff;
    }
    .sub {
        color: #b7c8e6;
        font-size: 14px;
        margin-bottom: 4px;
    }
    .grid2 {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
    }
    .grid3 {
        display: grid;
        grid-template-columns: 1fr 1fr 1fr;
        gap: 12px;
    }
    .big {
        font-size: 48px;
        font-weight: bold;
        color: #ffffff;
    }
    .ok { color: #66e3a3; font-weight: bold; }
    .bad { color: #ff7b7b; font-weight: bold; }
    .btn {
        display: inline-block;
        padding: 12px 16px;
        background: #295a96;
        color: #eef6ff;
        text-decoration: none;
        border-radius: 12px;
        font-weight: bold;
        margin-right: 8px;
        margin-top: 8px;
        border: 1px solid #4f86c6;
    }
    .btn2 {
        background: #162b45;
        color: #dfeaff;
    }
    .mono {
        font-family: monospace;
        background: #040b16;
        padding: 10px;
        border-radius: 10px;
        white-space: pre-wrap;
        overflow-wrap: break-word;
    }
    .pill {
        display: inline-block;
        margin: 4px 6px 0 0;
        padding: 8px 12px;
        border-radius: 999px;
        font-size: 13px;
        font-weight: bold;
    }
    .alert {
        background: #5f1d2a;
        color: #ffd5db;
    }
    .okpill {
        background: #153247;
        color: #cfe8ff;
    }
    @media (max-width: 700px) {
        .grid2, .grid3 {
            grid-template-columns: 1fr;
        }
    }
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

def page_home():
    st = stats()
    rows = parse_csv_rows()
    al = alerts(temperatura_actual, humedad_actual)
    rssi = wifi_rssi()

    alerts_html = "".join(
        '<div class="pill alert">{}</div>'.format(x) if x != "Ninguna"
        else '<div class="pill okpill">{}</div>'.format(x)
        for x in al
    )

    temps = [x["temp"] for x in rows]
    hums = [x["hum"] for x in rows]

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
        <div class="sub">Fecha: {fecha}</div>
        <div class="sub">Hora: {hora}</div>
        <div class="sub">Uptime: {uptime}</div>
        <div class="sub">Sensor: <span class="{sensor_class}">{sensor_state}</span></div>
        <div class="sub">WiFi: <span class="{wifi_class}">{wifi_state}</span></div>
        <div class="sub">RSSI: {rssi}</div>
        <div class="sub">Ultimo error sensor: {sensor_error}</div>
        <div class="sub">Ultima lectura local: {ultima}</div>
    </div>

    <div class="grid2">
        <div class="card">
            <div class="sub">Temperatura actual</div>
            <div class="big">{temp} °C</div>
            <div class="sub">Tendencia: {tt}</div>
        </div>
        <div class="card">
            <div class="sub">Humedad actual</div>
            <div class="big">{hum} %</div>
            <div class="sub">Tendencia: {th}</div>
        </div>
    </div>

    <div class="grid2">
        <div class="card">
            <div class="sub">Confort ambiental</div>
            <div class="big" style="font-size:34px;">{icon} {comfort}</div>
        </div>
        <div class="card">
            <div class="sub">Punto de rocio</div>
            <div class="big" style="font-size:34px;">{dp} °C</div>
        </div>
    </div>

    <div class="card">
        <div class="sub">Como viene para resfriado</div>
        <div class="big" style="font-size:34px;">{cold}</div>
    </div>

    <div class="card">
        <div class="title" style="font-size:22px;">Alertas</div>
        {alerts}
    </div>

    <div class="card">
        <div class="title" style="font-size:22px;">Estadisticas</div>
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

    {svg1}
    {svg2}

    <div class="card">
        <div class="title" style="font-size:22px;">Acciones</div>
        <a class="btn" href="/leer">Forzar lectura</a>
        <a class="btn btn2" href="/descargar">Descargar CSV</a>
        <a class="btn btn2" href="/estado">Estado tecnico</a>
        <a class="btn btn2" href="/logs">Ver logs</a>
        <a class="btn btn2" href="/json">JSON</a>
        <a class="btn btn2" href="/lcd_on">LCD ON</a>
        <a class="btn btn2" href="/lcd_off">LCD OFF</a>
        <a class="btn btn2" href="/toggle_log">{log_text}</a>
        <a class="btn btn2" href="/borrar_csv">Borrar CSV</a>
        <a class="btn btn2" href="/borrar_logs">Borrar logs</a>
        <a class="btn btn2" href="/reiniciar">Reiniciar</a>
    </div>
</div>
</body>
</html>
""".format(
        version=VERSION,
        refresh=REFRESCO_WEB,
        style=style_base(),
        ip=wifi_ip,
        fecha=fecha_texto(),
        hora=hora_texto(),
        uptime=uptime_texto(),
        sensor_class="ok" if sensor_ok else "bad",
        sensor_state="OK" if sensor_ok else "ERROR",
        wifi_class="ok" if wifi_conectado() else "bad",
        wifi_state="Conectado" if wifi_conectado() else "Sin WiFi",
        rssi="{} dBm".format(rssi) if rssi is not None else "N/D",
        sensor_error=sensor_error,
        ultima=ultima_lectura_epoch,
        temp=fmt1(temperatura_actual),
        hum=fmt1(humedad_actual),
        tt=temp_trend(),
        th=hum_trend(),
        icon=comfort_icon(),
        comfort=comfort(temperatura_actual, humedad_actual),
        dp=fmt1(dew_point(temperatura_actual, humedad_actual)),
        cold=cold_state(temperatura_actual, humedad_actual),
        alerts=alerts_html,
        tmin=fmt1(st["tmin"]),
        tmax=fmt1(st["tmax"]),
        tavg=fmt1(st["tavg"]),
        hmin=fmt1(st["hmin"]),
        hmax=fmt1(st["hmax"]),
        havg=fmt1(st["havg"]),
        count=st["count"],
        svg1=svg_series(temps, "Grafico temperatura"),
        svg2=svg_series(hums, "Grafico humedad", "#68d2ff"),
        log_text="Desactivar guardado" if guardado_activo else "Activar guardado",
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
        <a class="btn" href="/">Volver</a>
        <a class="btn btn2" href="/borrar_logs">Borrar logs</a>
    </div>
</div>
</body>
</html>
""".format(style=style_base(), logs=read_logs())

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
        <div class="mono">Fecha: {fecha}</div>
        <div class="mono">Hora: {hora}</div>
        <div class="mono">Uptime: {uptime}</div>
        <div class="mono">RAM libre: {ram}</div>
        <div class="mono">RSSI: {rssi}</div>
        <div class="mono">LCD OK: {lcd_ok}</div>
        <div class="mono">LCD error: {lcd_error}</div>
        <div class="mono">Sensor OK: {sensor_ok}</div>
        <div class="mono">Sensor error: {sensor_error}</div>
        <div class="mono">Servidor OK: {server_ok}</div>
        <div class="mono">Servidor error: {server_error}</div>
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
        <a class="btn" href="/">Volver</a>
    </div>
</div>
</body>
</html>
""".format(
        style=style_base(),
        version=VERSION,
        ip=wifi_ip,
        fecha=fecha_texto(),
        hora=hora_texto(),
        uptime=uptime_texto(),
        ram=mem_free(),
        rssi="{} dBm".format(rssi) if rssi is not None else "N/D",
        lcd_ok=lcd_ok,
        lcd_error=lcd_error,
        sensor_ok=sensor_ok,
        sensor_error=sensor_error,
        server_ok=server_ok,
        server_error=server_error,
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
        lcd_activo=lcd_activo
    )

def json_status():
    rssi = wifi_rssi()
    return """{{
  "version": "{version}",
  "ip": "{ip}",
  "fecha": "{fecha}",
  "hora": "{hora}",
  "temperatura": "{temp}",
  "humedad": "{hum}",
  "punto_rocio": "{dp}",
  "confort": "{comfort}",
  "resfriado": "{cold}",
  "tendencia_temp": "{tt}",
  "tendencia_hum": "{th}",
  "sensor_ok": {sensor_ok},
  "wifi_ok": {wifi_ok},
  "rssi": "{rssi}",
  "uptime": "{uptime}",
  "ultima_lectura_local": "{ultima}"
}}""".format(
        version=VERSION,
        ip=wifi_ip,
        fecha=fecha_texto(),
        hora=hora_texto(),
        temp=fmt1(temperatura_actual),
        hum=fmt1(humedad_actual),
        dp=fmt1(dew_point(temperatura_actual, humedad_actual)),
        comfort=comfort(temperatura_actual, humedad_actual),
        cold=cold_state(temperatura_actual, humedad_actual),
        tt=temp_trend(),
        th=hum_trend(),
        sensor_ok="true" if sensor_ok else "false",
        wifi_ok="true" if wifi_conectado() else "false",
        rssi="{} dBm".format(rssi) if rssi is not None else "N/D",
        uptime=uptime_texto(),
        ultima=ultima_lectura_epoch
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

    contador_hits += 1

    try:
        req = cl.recv(1024)
        req = str(req)

        if "GET /descargar " in req:
            data = read_csv()
            respond(
                cl,
                data,
                ctype="text/plain",
                extras=["Content-Disposition: attachment; filename={}".format(CSV_FILE)]
            )

        elif "GET /logs " in req:
            respond(cl, page_logs())

        elif "GET /estado " in req:
            respond(cl, page_status())

        elif "GET /json " in req:
            respond(cl, json_status(), ctype="application/json; charset=utf-8")

        elif "GET /leer " in req:
            ok = read_sensor()
            if ok:
                rotate_lcd(True)
                append_log("Lectura manual OK")
            else:
                lcd_msg("Lectura manual", "ERROR", 0, True)
                append_log("Lectura manual FAIL", "WARN")
            respond(cl, page_home())

        elif "GET /borrar_csv " in req:
            ok, msg = clear_csv()
            append_log("Accion borrar_csv: {}".format(msg))
            rotate_lcd(True)
            respond(cl, "<html><body><h1>{}</h1><p><a href='/'>Volver</a></p></body></html>".format(msg))

        elif "GET /borrar_logs " in req:
            ok, msg = clear_logs()
            respond(cl, "<html><body><h1>{}</h1><p><a href='/'>Volver</a></p></body></html>".format(msg))

        elif "GET /toggle_log " in req:
            guardado_activo = not guardado_activo
            append_log("Guardado activo => {}".format(guardado_activo))
            rotate_lcd(True)
            respond(cl, page_home())

        elif "GET /lcd_on " in req:
            lcd_on_total()
            rotate_lcd(True)
            respond(cl, page_home())

        elif "GET /lcd_off " in req:
            lcd_off_total()
            respond(cl, page_home())

        elif "GET /reiniciar " in req:
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
            respond(cl, page_home())

        server_ok = True
        server_error = "Ninguno"

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
lcd_msg("ESP32 JC", VERSION, PAUSA_LCD_BOOT, True)
lcd_msg("Iniciando", "sensor / web", PAUSA_LCD_BOOT, True)

init_sensor()
ensure_csv()
refresh_ip()
init_server()

lcd_msg("Web lista", safe_str(wifi_ip, 16), PAUSA_LCD_BOOT, True)

if read_sensor():
    append_log("Primera lectura sensor OK")
    rotate_lcd(True)
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
            if read_sensor():
                save_csv(temperatura_actual, humedad_actual)
                rotate_lcd(True)
            else:
                append_log("Lectura programada fallo", "WARN")
                lcd_msg("Sensor error", "Reintentando", 1, True)

            ultimo_guardado = ahora

        if temperatura_actual is None or humedad_actual is None:
            if read_sensor():
                rotate_lcd(True)
            else:
                lcd_msg("Esperando", "sensor...", 1, True)

        time.sleep(0.2)

    except Exception as e:
        contador_reinicios_logicos += 1
        append_log("Loop error: {}".format(e), "ERROR")
        if lcd_activo:
            lcd_msg("Loop error", safe_str(e, 16), 2, True)
        time.sleep(1)