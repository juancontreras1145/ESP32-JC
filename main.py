# =========================================
# ESP32 JC - Monitor Ambiental v41
# Negro + verde, todo en español
# =========================================
# Hardware:
# LCD I2C 1602 -> SDA=8, SCL=9, ADDR=0x27
# DHT22 -> GPIO4
#
# Rutas:
# /              Panel principal
# /estado        Estado técnico
# /acciones      Panel de acciones
# /leer          Fuerza lectura
# /descargar     Descarga CSV
# /borrar_csv    Reinicia CSV
# /toggle_log    Activa/desactiva guardado
# /lcd_on        Enciende LCD
# /lcd_off       Apaga LCD
# /json          Estado en JSON
# /reiniciar     Reinicia ESP32
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

# =========================================
# CONFIGURACIÓN
# =========================================
VERSION = "Monitor Ambiental v41"

LCD_SDA = 8
LCD_SCL = 9
LCD_ADDR = 0x27

DHT_PIN = 4
CSV_FILE = "temperaturas.csv"

INTERVALO_GUARDADO = 600
TIMEOUT_WEB = 1
REFRESCO_WEB = 10
PAUSA_LCD_BOOT = 1.5

REINTENTOS_SENSOR = 3
DELAY_REINTENTO_SENSOR = 1

TEMP_OFFSET = 0.0
HUM_OFFSET = 0.0

TEMP_BAJA = 18.0
TEMP_ALTA = 28.0
HUM_BAJA = 40.0
HUM_ALTA = 70.0

ROTACION_LCD_SEG = 2

# =========================================
# ESTADO GLOBAL
# =========================================
inicio_epoch = time.time()
ultimo_guardado = 0
ultima_lectura_epoch = None
ultimo_cambio_lcd = 0
indice_lcd = 0

temperatura_actual = None
humedad_actual = None

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

guardado_activo = True
lcd_activo = True

sensor = None
lcd = None
server = None

# =========================================
# HELPERS
# =========================================
def ahora_epoch():
    try:
        return int(time.time())
    except:
        return 0

def texto_seguro(x, n=16):
    try:
        return str(x)[:n]
    except:
        return "?"

def existe_archivo(nombre):
    try:
        return nombre in os.listdir()
    except:
        return False

def memoria_libre():
    try:
        gc.collect()
        return gc.mem_free()
    except:
        return -1

def uptime_texto():
    seg = max(0, int(time.time() - inicio_epoch))
    h = seg // 3600
    m = (seg % 3600) // 60
    s = seg % 60
    return "{:02d}:{:02d}:{:02d}".format(h, m, s)

def fmt1(x):
    if x is None:
        return "--.-"
    return "{:.1f}".format(x)

def estado_sensor():
    return "OK" if sensor_ok else "ERROR"

def estado_wifi():
    return "Conectado" if wifi_conectado() else "Sin WiFi"

def hora_actual_texto():
    try:
        t = time.localtime()
        return "{:02d}:{:02d}:{:02d}".format(t[3], t[4], t[5])
    except:
        return "--:--:--"

def fecha_actual_texto():
    try:
        t = time.localtime()
        return "{:04d}-{:02d}-{:02d}".format(t[0], t[1], t[2])
    except:
        return "----/--/--"

# =========================================
# LCD
# =========================================
def init_lcd():
    global lcd, lcd_ok, lcd_error
    try:
        from lcd import LCD
        i2c = I2C(0, sda=Pin(LCD_SDA), scl=Pin(LCD_SCL))
        lcd = LCD(i2c, LCD_ADDR)
        try:
            lcd.reinit()
        except:
            pass
        time.sleep_ms(150)
        lcd.clear()
        try:
            lcd.backlight_on()
        except:
            pass
        lcd_ok = True
        lcd_error = "Ninguno"
        return True
    except Exception as e:
        lcd = None
        lcd_ok = False
        lcd_error = str(e)
        print("LCD init error:", e)
        return False

def lcd_escribir(linea1="", linea2=""):
    global lcd_ok, lcd_error, contador_errores_lcd

    if not lcd_activo:
        return False

    if lcd is None:
        return False

    try:
        lcd.clear()
        time.sleep_ms(5)
        lcd.move_to(0, 0)
        lcd.putstr(texto_seguro(linea1, 16))
        lcd.move_to(0, 1)
        lcd.putstr(texto_seguro(linea2, 16))
        lcd_ok = True
        lcd_error = "Ninguno"
        return True
    except Exception as e:
        contador_errores_lcd += 1
        lcd_ok = False
        lcd_error = str(e)
        print("LCD write error:", e)
        return False

def lcd_msg(linea1="", linea2="", pausa=0):
    ok = lcd_escribir(linea1, linea2)
    if not ok:
        try:
            init_lcd()
            lcd_escribir(linea1, linea2)
        except:
            pass
    if pausa > 0:
        time.sleep(pausa)

# =========================================
# WIFI
# =========================================
def wifi_conectado():
    try:
        return network.WLAN(network.STA_IF).isconnected()
    except:
        return False

def refrescar_ip():
    global wifi_ip
    try:
        wlan = network.WLAN(network.STA_IF)
        if wlan.isconnected():
            wifi_ip = wlan.ifconfig()[0]
        else:
            wifi_ip = "Sin WiFi"
    except:
        wifi_ip = "Sin WiFi"

def wifi_rssi():
    try:
        wlan = network.WLAN(network.STA_IF)
        if wlan.isconnected():
            return wlan.status("rssi")
    except:
        pass
    return None

# =========================================
# SENSOR
# =========================================
def init_sensor():
    global sensor
    try:
        sensor = dht.DHT22(Pin(DHT_PIN))
        return True
    except Exception as e:
        print("Sensor init error:", e)
        sensor = None
        return False

def leer_sensor():
    global temperatura_actual, humedad_actual, ultima_lectura_epoch
    global sensor_ok, sensor_error, contador_lecturas, contador_errores_sensor

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

            temperatura_actual = t
            humedad_actual = h
            ultima_lectura_epoch = ahora_epoch()

            sensor_ok = True
            sensor_error = "Ninguno"
            contador_lecturas += 1
            return True

        except Exception as e:
            sensor_ok = False
            sensor_error = "Intento {}: {}".format(intento, e)
            contador_errores_sensor += 1
            print("Sensor error:", sensor_error)
            time.sleep(DELAY_REINTENTO_SENSOR)

    return False

# =========================================
# CÁLCULOS AMBIENTALES
# =========================================
def punto_rocio(temp, hum):
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

def sensacion_ambiente(temp, hum):
    if temp is None or hum is None:
        return "Sin datos"
    if 20 <= temp <= 24 and 40 <= hum <= 60:
        return "Bueno"
    if 18 <= temp <= 27 and 35 <= hum <= 70:
        return "Regular"
    return "Malo"

def lista_alertas(temp, hum):
    alertas = []

    if temp is None or hum is None:
        alertas.append("Sin datos del sensor")
        return alertas

    if temp < TEMP_BAJA:
        alertas.append("Temperatura baja")
    if temp > TEMP_ALTA:
        alertas.append("Temperatura alta")
    if hum < HUM_BAJA:
        alertas.append("Humedad baja")
    if hum > HUM_ALTA:
        alertas.append("Humedad alta")

    dp = punto_rocio(temp, hum)
    if dp is not None and dp > 16:
        alertas.append("Riesgo de condensación")

    if not alertas:
        alertas.append("Ninguna")

    return alertas

def estado_resfriado(temp, hum):
    if temp is None or hum is None:
        return "Sin datos"
    if 20 <= temp <= 22 and 45 <= hum <= 60:
        return "Muy bueno"
    if 19 <= temp <= 24 and 40 <= hum <= 70:
        return "Aceptable"
    return "Poco favorable"

def semaforo_ambiente():
    estado = sensacion_ambiente(temperatura_actual, humedad_actual)
    if estado == "Bueno":
        return "🟢"
    if estado == "Regular":
        return "🟡"
    return "🔴"

# =========================================
# CSV
# =========================================
def asegurar_csv():
    try:
        if not existe_archivo(CSV_FILE):
            with open(CSV_FILE, "w") as f:
                f.write("epoch,temperatura,humedad,punto_rocio,confort,resfriado\n")
    except Exception as e:
        print("CSV init error:", e)

def guardar_csv(temp, hum):
    global contador_guardados

    if not guardado_activo:
        return False

    try:
        dp = punto_rocio(temp, hum)
        confort = sensacion_ambiente(temp, hum)
        resf = estado_resfriado(temp, hum)

        with open(CSV_FILE, "a") as f:
            f.write("{},{:.1f},{:.1f},{},{},{}\n".format(
                ahora_epoch(),
                temp,
                hum,
                "" if dp is None else "{:.1f}".format(dp),
                confort,
                resf
            ))

        contador_guardados += 1
        return True

    except Exception as e:
        print("CSV save error:", e)
        return False

def leer_csv_texto():
    try:
        with open(CSV_FILE, "r") as f:
            return f.read()
    except Exception as e:
        return "Error leyendo CSV: {}".format(e)

def borrar_csv():
    try:
        if existe_archivo(CSV_FILE):
            os.remove(CSV_FILE)
        asegurar_csv()
        return True, "CSV reiniciado"
    except Exception as e:
        return False, str(e)

def estadisticas():
    datos = {
        "count": 0,
        "tmin": None, "tmax": None, "tavg": None,
        "hmin": None, "hmax": None, "havg": None,
    }

    try:
        with open(CSV_FILE, "r") as f:
            lineas = f.readlines()

        temps = []
        hums = []

        for linea in lineas[1:]:
            partes = linea.strip().split(",")
            if len(partes) < 3:
                continue
            try:
                temps.append(float(partes[1]))
                hums.append(float(partes[2]))
            except:
                pass

        if temps and hums:
            datos["count"] = len(temps)
            datos["tmin"] = min(temps)
            datos["tmax"] = max(temps)
            datos["tavg"] = sum(temps) / len(temps)
            datos["hmin"] = min(hums)
            datos["hmax"] = max(hums)
            datos["havg"] = sum(hums) / len(hums)

    except Exception as e:
        print("Stats error:", e)

    return datos

# =========================================
# LCD PANEL ROTATIVO
# =========================================
def actualizar_lcd_principal(forzar=False):
    global ultimo_cambio_lcd, indice_lcd

    if not lcd_activo:
        return

    ahora = ahora_epoch()

    if not forzar and (ahora - ultimo_cambio_lcd < ROTACION_LCD_SEG):
        return

    ultimo_cambio_lcd = ahora

    confort = sensacion_ambiente(temperatura_actual, humedad_actual)
    dp = punto_rocio(temperatura_actual, humedad_actual)
    alerta = lista_alertas(temperatura_actual, humedad_actual)[0]
    hora = hora_actual_texto()

    pantallas = [
        ("T:{}C H:{}%".format(fmt1(temperatura_actual), fmt1(humedad_actual)),
         "Conf:{}".format(texto_seguro(confort, 10))),

        ("Rocio:{}C".format(fmt1(dp)),
         "Hora:{}".format(hora)),

        ("Alerta:",
         texto_seguro(alerta, 16)),

        ("Resfriado:",
         texto_seguro(estado_resfriado(temperatura_actual, humedad_actual), 16)),

        ("WiFi:{}".format("OK" if wifi_conectado() else "OFF"),
         texto_seguro(wifi_ip, 16)),
    ]

    if indice_lcd >= len(pantallas):
        indice_lcd = 0

    p = pantallas[indice_lcd]
    lcd_escribir(p[0], p[1])

    indice_lcd += 1
    if indice_lcd >= len(pantallas):
        indice_lcd = 0

# =========================================
# WEB - ESTILO
# =========================================
def estilo_base():
    return """
    <style>
    body {
        font-family: Arial, sans-serif;
        background: #050b05;
        color: #e8ffe8;
        margin: 0;
        padding: 16px;
    }
    .wrap {
        max-width: 1000px;
        margin: auto;
    }
    .card {
        background: #0b140b;
        border: 1px solid #1f5d1f;
        border-radius: 18px;
        padding: 16px;
        margin-bottom: 16px;
        box-shadow: 0 0 0 1px rgba(0,255,80,0.05);
    }
    .title {
        font-size: 30px;
        font-weight: bold;
        margin-bottom: 8px;
        color: #d8ffd8;
    }
    .sub {
        color: #9fd09f;
        font-size: 14px;
        margin-bottom: 3px;
    }
    .grid {
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
        font-size: 44px;
        font-weight: bold;
        color: #f3fff3;
    }
    .ok {
        color: #4dff88;
        font-weight: bold;
    }
    .bad {
        color: #ff6666;
        font-weight: bold;
    }
    .btn {
        display: inline-block;
        padding: 12px 16px;
        background: #1f7a1f;
        color: #ecffec;
        text-decoration: none;
        border-radius: 12px;
        font-weight: bold;
        margin-right: 8px;
        margin-top: 8px;
        border: 1px solid #2eb82e;
    }
    .btn2 {
        background: #103b10;
        color: #bfffbf;
    }
    .mono {
        font-family: monospace;
        background: #020617;
        padding: 10px;
        border-radius: 10px;
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
        background: #5d1010;
        color: #ffd0d0;
    }
    .okpill {
        background: #103b10;
        color: #bfffbf;
    }
    a.inline {
        color: #7dff9b;
    }
    @media (max-width: 700px) {
        .grid, .grid3 {
            grid-template-columns: 1fr;
        }
    }
    </style>
    """

# =========================================
# WEB - PÁGINAS
# =========================================
def html_inicio():
    est = estadisticas()
    alertas = lista_alertas(temperatura_actual, humedad_actual)
    dp = punto_rocio(temperatura_actual, humedad_actual)
    confort = sensacion_ambiente(temperatura_actual, humedad_actual)
    resf = estado_resfriado(temperatura_actual, humedad_actual)
    rssi = wifi_rssi()

    alertas_html = "".join(
        '<div class="pill alert">{}</div>'.format(a) if a != "Ninguna"
        else '<div class="pill okpill">{}</div>'.format(a)
        for a in alertas
    )

    return """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="{refresh}">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ESP32 JC Monitor</title>
{style}
</head>
<body>
<div class="wrap">

    <div class="card">
        <div class="title">ESP32 JC Monitor v41</div>
        <div class="sub">IP: {ip}</div>
        <div class="sub">Fecha: {fecha}</div>
        <div class="sub">Hora: {hora}</div>
        <div class="sub">Uptime: {uptime}</div>
        <div class="sub">Sensor: <span class="{sensor_class}">{sensor_state}</span></div>
        <div class="sub">WiFi: <span class="{wifi_class}">{wifi_state}</span></div>
        <div class="sub">RSSI: {rssi}</div>
        <div class="sub">Último error sensor: {sensor_error}</div>
        <div class="sub">Última lectura epoch: {ultima}</div>
    </div>

    <div class="grid">
        <div class="card">
            <div class="sub">Temperatura actual</div>
            <div class="big">{temp} °C</div>
        </div>
        <div class="card">
            <div class="sub">Humedad actual</div>
            <div class="big">{hum} %</div>
        </div>
    </div>

    <div class="grid">
        <div class="card">
            <div class="sub">Confort ambiental</div>
            <div class="big" style="font-size:34px;">{semaforo} {confort}</div>
        </div>
        <div class="card">
            <div class="sub">Punto de rocío</div>
            <div class="big" style="font-size:34px;">{dp} °C</div>
        </div>
    </div>

    <div class="card">
        <div class="sub">Cómo viene para resfriado</div>
        <div class="big" style="font-size:34px;">{resfriado}</div>
    </div>

    <div class="card">
        <div class="title" style="font-size:22px;">Alertas</div>
        {alertas}
    </div>

    <div class="card">
        <div class="title" style="font-size:22px;">Estadísticas</div>
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

    <div class="card">
        <div class="title" style="font-size:22px;">Acceso rápido</div>
        <a class="btn" href="/acciones">Ir a acciones</a>
        <a class="btn btn2" href="/estado">Estado técnico</a>
        <a class="btn btn2" href="/json">JSON</a>
    </div>

</div>
</body>
</html>
""".format(
        refresh=REFRESCO_WEB,
        style=estilo_base(),
        ip=wifi_ip,
        fecha=fecha_actual_texto(),
        hora=hora_actual_texto(),
        uptime=uptime_texto(),
        sensor_class="ok" if sensor_ok else "bad",
        sensor_state=estado_sensor(),
        wifi_class="ok" if wifi_conectado() else "bad",
        wifi_state=estado_wifi(),
        rssi="{} dBm".format(rssi) if rssi is not None else "N/D",
        sensor_error=sensor_error,
        ultima=ultima_lectura_epoch,
        temp=fmt1(temperatura_actual),
        hum=fmt1(humedad_actual),
        semaforo=semaforo_ambiente(),
        confort=confort,
        dp=fmt1(dp),
        resfriado=resf,
        alertas=alertas_html,
        tmin=fmt1(est["tmin"]),
        tmax=fmt1(est["tmax"]),
        tavg=fmt1(est["tavg"]),
        hmin=fmt1(est["hmin"]),
        hmax=fmt1(est["hmax"]),
        havg=fmt1(est["havg"]),
        count=est["count"],
    )

def html_acciones():
    return """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Acciones</title>
{style}
</head>
<body>
<div class="wrap">
    <div class="card">
        <div class="title">Acciones</div>
        <a class="btn" href="/leer">Forzar lectura</a>
        <a class="btn" href="/descargar">Descargar CSV</a>
        <a class="btn btn2" href="/borrar_csv">Borrar CSV</a>
        <a class="btn btn2" href="/toggle_log">{texto_log}</a>
        <a class="btn btn2" href="/lcd_on">LCD ON</a>
        <a class="btn btn2" href="/lcd_off">LCD OFF</a>
        <a class="btn btn2" href="/reiniciar">Reiniciar ESP32</a>
        <p><a class="inline" href="/">Volver</a></p>
    </div>
</div>
</body>
</html>
""".format(
        style=estilo_base(),
        texto_log="Desactivar guardado" if guardado_activo else "Activar guardado"
    )

def html_estado():
    return """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Estado técnico</title>
{style}
</head>
<body>
<div class="wrap">
    <div class="card">
        <div class="title">Estado técnico</div>
        <div class="mono">Versión: {version}</div>
        <div class="mono">IP: {ip}</div>
        <div class="mono">Uptime: {uptime}</div>
        <div class="mono">RAM libre: {ram}</div>
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
        <div class="mono">Última lectura epoch: {ultima}</div>
        <div class="mono">CSV: {csv}</div>
        <div class="mono">Guardado activo: {log_activo}</div>
        <div class="mono">LCD activo: {lcd_activo}</div>
        <p><a class="inline" href="/">Volver</a></p>
    </div>
</div>
</body>
</html>
""".format(
        style=estilo_base(),
        version=VERSION,
        ip=wifi_ip,
        uptime=uptime_texto(),
        ram=memoria_libre(),
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
        log_activo=guardado_activo,
        lcd_activo=lcd_activo
    )

def json_estado():
    dp = punto_rocio(temperatura_actual, humedad_actual)
    confort = sensacion_ambiente(temperatura_actual, humedad_actual)
    resf = estado_resfriado(temperatura_actual, humedad_actual)
    rssi = wifi_rssi()

    return """{{
  "version": "{version}",
  "ip": "{ip}",
  "temperatura": "{temp}",
  "humedad": "{hum}",
  "punto_rocio": "{dp}",
  "confort": "{confort}",
  "resfriado": "{resfriado}",
  "sensor_ok": {sensor_ok},
  "wifi_ok": {wifi_ok},
  "rssi": "{rssi}",
  "uptime": "{uptime}",
  "ultima_lectura_epoch": "{ultima}"
}}""".format(
        version=VERSION,
        ip=wifi_ip,
        temp=fmt1(temperatura_actual),
        hum=fmt1(humedad_actual),
        dp=fmt1(dp),
        confort=confort,
        resfriado=resf,
        sensor_ok="true" if sensor_ok else "false",
        wifi_ok="true" if wifi_conectado() else "false",
        rssi="{} dBm".format(rssi) if rssi is not None else "N/D",
        uptime=uptime_texto(),
        ultima=ultima_lectura_epoch
    )

# =========================================
# RESPUESTA HTTP
# =========================================
def responder(cl, body, ctype="text/html; charset=utf-8", code="200 OK", extras=None):
    try:
        cl.send("HTTP/1.0 {}\r\n".format(code))
        cl.send("Content-Type: {}\r\n".format(ctype))
        if extras:
            for h in extras:
                cl.send(h + "\r\n")
        cl.send("\r\n")
        cl.send(body)
    except Exception as e:
        print("send_response error:", e)

# =========================================
# SERVER
# =========================================
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
        print("Servidor web listo")
        return True
    except Exception as e:
        server = None
        server_ok = False
        server_error = str(e)
        print("Server init error:", e)
        return False

def manejar_web():
    global contador_hits, server_ok, server_error, contador_errores_web
    global guardado_activo, lcd_activo

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
        return

    contador_hits += 1

    try:
        req = cl.recv(1024)
        req = str(req)

        if "GET /descargar " in req:
            data = leer_csv_texto()
            responder(
                cl,
                data,
                ctype="text/plain",
                extras=["Content-Disposition: attachment; filename={}".format(CSV_FILE)]
            )

        elif "GET /estado " in req:
            responder(cl, html_estado())

        elif "GET /acciones " in req:
            responder(cl, html_acciones())

        elif "GET /leer " in req:
            ok = leer_sensor()
            if ok:
                actualizar_lcd_principal(True)
            else:
                lcd_msg("Lectura manual", "ERROR", 0)
            responder(cl, html_inicio())

        elif "GET /borrar_csv " in req:
            ok, msg = borrar_csv()
            lcd_msg("CSV", "reiniciado" if ok else "error", 0)
            responder(cl, "<html><body><h1>{}</h1><p><a href='/'>Volver</a></p></body></html>".format(msg))

        elif "GET /toggle_log " in req:
            guardado_activo = not guardado_activo
            lcd_msg("Guardado", "ON" if guardado_activo else "OFF", 0)
            responder(cl, html_acciones())

        elif "GET /lcd_on " in req:
            lcd_activo = True
            init_lcd()
            try:
                lcd.backlight_on()
            except:
                pass
            actualizar_lcd_principal(True)
            responder(cl, html_acciones())

        elif "GET /lcd_off " in req:
            try:
                lcd_msg("LCD", "APAGANDO", 1)
                lcd.backlight_off()
            except:
                pass
            lcd_activo = False
            responder(cl, html_acciones())

        elif "GET /json " in req:
            responder(cl, json_estado(), ctype="application/json; charset=utf-8")

        elif "GET /reiniciar " in req:
            responder(cl, "<html><body><h1>Reiniciando ESP32...</h1></body></html>")
            try:
                cl.close()
            except:
                pass
            time.sleep(1)
            machine.reset()
            return

        else:
            responder(cl, html_inicio())

        server_ok = True
        server_error = "Ninguno"

    except Exception as e:
        server_ok = False
        server_error = str(e)
        contador_errores_web += 1
        print("web handler error:", e)

    try:
        cl.close()
    except:
        pass

# =========================================
# ARRANQUE
# =========================================
gc.collect()

init_lcd()
lcd_msg("ESP32 JC", VERSION, PAUSA_LCD_BOOT)

lcd_msg("Iniciando", "sensor/web", PAUSA_LCD_BOOT)

init_sensor()
asegurar_csv()
refrescar_ip()
init_server()

lcd_msg("Web lista", texto_seguro(wifi_ip, 16), PAUSA_LCD_BOOT)

# lectura inmediata al arranque
if leer_sensor():
    actualizar_lcd_principal(True)
else:
    lcd_msg("Sensor Error", "sin lectura", PAUSA_LCD_BOOT)

ultimo_guardado = ahora_epoch()

# =========================================
# LOOP
# =========================================
while True:
    try:
        gc.collect()
        refrescar_ip()
        manejar_web()
        actualizar_lcd_principal(False)

        ahora = ahora_epoch()

        if ahora - ultimo_guardado >= INTERVALO_GUARDADO:
            if leer_sensor():
                guardar_csv(temperatura_actual, humedad_actual)
                actualizar_lcd_principal(True)
            else:
                lcd_msg("Sensor Error", "reintentando", 0)

            ultimo_guardado = ahora

        if temperatura_actual is None or humedad_actual is None:
            if leer_sensor():
                actualizar_lcd_principal(True)
            else:
                lcd_msg("Esperando", "sensor...", 0)
                time.sleep(1)

        time.sleep(0.2)

    except Exception as e:
        print("Loop error:", e)
        lcd_msg("Loop Error", texto_seguro(e, 16), 2)