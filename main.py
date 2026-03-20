from machine import Pin, RTC
import dht
import network
import socket
import time
import os
import gc

try:
    import ntptime
    NTP_OK = True
except:
    NTP_OK = False

from lcd import LCD1602_I2C

# =========================
# CONFIG
# =========================
SSID = "S25"
PASSWORD = "12345678"

LCD_SDA = 8
LCD_SCL = 9
LCD_ADDR = 0x27

DHT_PIN = 4
SAVE_INTERVAL_MIN = 10

AUTO_REFRESH_WEB = 20   # segundos

# =========================
# INIT
# =========================
lcd = LCD1602_I2C(sda=LCD_SDA, scl=LCD_SCL, addr=LCD_ADDR)
sensor = dht.DHT22(Pin(DHT_PIN))
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

current_temp = None
current_hum = None
last_save_key = None
boot_ms = time.ticks_ms()

# =========================
# HELPERS
# =========================
def fmt1(x):
    return "{:.1f}".format(x).replace(".", ",")

def uptime_text():
    secs = time.ticks_diff(time.ticks_ms(), boot_ms) // 1000
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    return "{:02d}:{:02d}:{:02d}".format(h, m, s)

def wifi_connect():
    if wlan.isconnected():
        return True

    wlan.connect(SSID, PASSWORD)
    timeout = 20

    while not wlan.isconnected() and timeout > 0:
        lcd.print("Conectando WiFi", str(timeout))
        time.sleep(1)
        timeout -= 1

    return wlan.isconnected()

def wifi_ip():
    if wlan.isconnected():
        return wlan.ifconfig()[0]
    return "Sin WiFi"

def sync_time():
    if not NTP_OK:
        print("ntptime no disponible")
        return False

    try:
        ntptime.settime()
        print("Hora sincronizada")
        return True
    except Exception as e:
        print("NTP error:", e)
        return False

def now_local():
    rtc = RTC()
    y, mo, d, wd, hh, mm, ss, sub = rtc.datetime()

    # Ajuste simple UTC-3
    hh -= 3
    if hh < 0:
        hh += 24
        d -= 1
        if d <= 0:
            d = 1

    return y, mo, d, hh, mm, ss

def fecha_text():
    y, mo, d, hh, mm, ss = now_local()
    return "{:04d}-{:02d}-{:02d}".format(y, mo, d)

def fecha_corta():
    y, mo, d, hh, mm, ss = now_local()
    return "{:02d}-{:02d}".format(mo, d)

def hora_text():
    y, mo, d, hh, mm, ss = now_local()
    return "{:02d}:{:02d}:{:02d}".format(hh, mm, ss)

def csv_filename():
    return "temperaturas_{}.csv".format(fecha_text())

def ensure_csv():
    fn = csv_filename()
    if fn not in os.listdir():
        with open(fn, "w") as f:
            f.write("fecha;hora;temperatura;humedad\n")
    return fn

def save_row(temp, hum):
    global last_save_key

    y, mo, d, hh, mm, ss = now_local()

    # guardar solo cuando el minuto cae exacto en 0,10,20,30,40,50
    if mm % SAVE_INTERVAL_MIN != 0:
        return False

    key = "{} {:02d}:{:02d}".format(fecha_text(), hh, mm)
    if key == last_save_key:
        return False

    fn = ensure_csv()
    with open(fn, "a") as f:
        f.write(
            "{};{};{};{}\n".format(
                fecha_text(),
                hora_text(),
                fmt1(temp),
                fmt1(hum)
            )
        )

    last_save_key = key
    print("Guardado:", key)
    return True

def read_last_rows(limit=12):
    fn = csv_filename()
    if fn not in os.listdir():
        return []

    try:
        with open(fn, "r") as f:
            lines = f.readlines()[1:]
        lines = [x.strip() for x in lines if x.strip()]
        return lines[-limit:]
    except:
        return []

def stats_today():
    fn = csv_filename()
    if fn not in os.listdir():
        return None

    temps = []
    hums = []

    try:
        with open(fn, "r") as f:
            lines = f.readlines()[1:]

        for line in lines:
            p = line.strip().split(";")
            if len(p) == 4:
                try:
                    temps.append(float(p[2].replace(",", ".")))
                    hums.append(float(p[3].replace(",", ".")))
                except:
                    pass

        if not temps or not hums:
            return None

        return {
            "t_min": fmt1(min(temps)),
            "t_max": fmt1(max(temps)),
            "t_avg": fmt1(sum(temps) / len(temps)),
            "h_min": fmt1(min(hums)),
            "h_max": fmt1(max(hums)),
            "h_avg": fmt1(sum(hums) / len(hums)),
            "count": len(temps),
        }
    except:
        return None

def html_page():
    rows = read_last_rows(14)
    stats = stats_today()

    temp_txt = "--,-" if current_temp is None else fmt1(current_temp)
    hum_txt = "--,-" if current_hum is None else fmt1(current_hum)

    trs = ""
    if rows:
        for r in reversed(rows):
            p = r.split(";")
            if len(p) == 4:
                trs += "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                    p[0], p[1], p[2], p[3]
                )
    else:
        trs = '<tr><td colspan="4">Sin registros todavía</td></tr>'

    if stats:
        stats_html = """
        <div class="grid3">
            <div class="mini"><div class="label">Temp mín</div><div class="value">{}</div></div>
            <div class="mini"><div class="label">Temp máx</div><div class="value">{}</div></div>
            <div class="mini"><div class="label">Temp prom</div><div class="value">{}</div></div>
            <div class="mini"><div class="label">Hum mín</div><div class="value">{}</div></div>
            <div class="mini"><div class="label">Hum máx</div><div class="value">{}</div></div>
            <div class="mini"><div class="label">Hum prom</div><div class="value">{}</div></div>
        </div>
        <div class="small">Registros del día: {}</div>
        """.format(
            stats["t_min"], stats["t_max"], stats["t_avg"],
            stats["h_min"], stats["h_max"], stats["h_avg"],
            stats["count"]
        )
    else:
        stats_html = '<div class="small">Todavía no hay suficientes datos del día.</div>'

    return """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="{refresh}">
<title>ESP32 Monitor Ambiental</title>
<style>
body {{
    font-family: Arial, sans-serif;
    background: #0f172a;
    color: #e5e7eb;
    margin: 0;
    padding: 16px;
}}
.wrap {{
    max-width: 980px;
    margin: auto;
}}
.card {{
    background: #111827;
    border: 1px solid #374151;
    border-radius: 18px;
    padding: 16px;
    margin-bottom: 16px;
    box-shadow: 0 4px 14px rgba(0,0,0,0.18);
}}
.header {{
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: 10px;
    align-items: center;
}}
h1, h2 {{
    margin: 0 0 10px 0;
}}
.small {{
    color: #94a3b8;
    font-size: 14px;
}}
.grid2 {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0,1fr));
    gap: 14px;
}}
.grid3 {{
    display: grid;
    grid-template-columns: repeat(3, minmax(0,1fr));
    gap: 10px;
}}
.bigbox {{
    background: linear-gradient(180deg, #111827, #172033);
    border-radius: 16px;
    padding: 16px;
}}
.biglabel {{
    color: #93c5fd;
    font-size: 15px;
    margin-bottom: 8px;
}}
.bigvalue {{
    font-size: 34px;
    font-weight: bold;
}}
.mini {{
    background: #1f2937;
    border-radius: 14px;
    padding: 12px;
}}
.label {{
    color: #93c5fd;
    font-size: 13px;
    margin-bottom: 6px;
}}
.value {{
    font-size: 22px;
    font-weight: bold;
}}
.btn {{
    display: inline-block;
    padding: 11px 16px;
    border-radius: 12px;
    text-decoration: none;
    background: #22c55e;
    color: #052e16;
    font-weight: bold;
    margin-right: 8px;
}}
.btn.alt {{
    background: #38bdf8;
    color: #082f49;
}}
table {{
    width: 100%;
    border-collapse: collapse;
}}
th, td {{
    padding: 10px;
    border-bottom: 1px solid #374151;
    text-align: left;
    font-size: 14px;
}}
.footer {{
    text-align: center;
    color: #64748b;
    font-size: 13px;
    margin-top: 12px;
}}
@media (max-width: 700px) {{
    .grid2, .grid3 {{
        grid-template-columns: 1fr;
    }}
}}
</style>
</head>
<body>
<div class="wrap">

    <div class="card">
        <div class="header">
            <div>
                <h1>ESP32 · Monitor Ambiental</h1>
                <div class="small">Panel simple, claro y compatible con Excel</div>
            </div>
            <div>
                <a class="btn" href="/csv">Descargar CSV</a>
                <a class="btn alt" href="/">Actualizar</a>
            </div>
        </div>
    </div>

    <div class="card">
        <div class="small">IP: <b>{ip}</b></div>
        <div class="small">Fecha: <b>{fecha}</b> · Hora: <b>{hora}</b></div>
        <div class="small">Uptime: <b>{uptime}</b></div>
        <div class="small">Archivo del día: <b>{archivo}</b></div>
    </div>

    <div class="grid2">
        <div class="card bigbox">
            <div class="biglabel">Temperatura actual</div>
            <div class="bigvalue">{temp} °C</div>
        </div>
        <div class="card bigbox">
            <div class="biglabel">Humedad actual</div>
            <div class="bigvalue">{hum} %</div>
        </div>
    </div>

    <div class="card">
        <h2>Resumen del día</h2>
        {stats_html}
    </div>

    <div class="card">
        <h2>Últimos registros</h2>
        <table>
            <thead>
                <tr>
                    <th>Fecha</th>
                    <th>Hora</th>
                    <th>Temperatura</th>
                    <th>Humedad</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
    </div>

    <div class="footer">
        Actualización automática cada {refresh} segundos
    </div>
</div>
</body>
</html>
""".format(
        refresh=AUTO_REFRESH_WEB,
        ip=wifi_ip(),
        fecha=fecha_text(),
        hora=hora_text(),
        uptime=uptime_text(),
        archivo=csv_filename(),
        temp=temp_txt,
        hum=hum_txt,
        stats_html=stats_html,
        rows=trs
    )

def send_response(cl, body, ctype="text/html; charset=utf-8", status="200 OK"):
    cl.send("HTTP/1.1 {}\r\n".format(status))
    cl.send("Content-Type: {}\r\n".format(ctype))
    cl.send("Connection: close\r\n\r\n")
    if isinstance(body, str):
        cl.sendall(body)
    else:
        cl.sendall(body)

def start_server():
    addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(2)
    s.settimeout(1)
    print("Web disponible en http://{}".format(wifi_ip()))
    return s

# =========================
# ARRANQUE
# =========================
lcd.print("ESP32 Monitor", "Conectando...")
wifi_connect()
sync_time()
ensure_csv()

lcd.print("WiFi OK", wifi_ip())
time.sleep(2)

server = start_server()

# =========================
# LOOP
# =========================
while True:
    try:
        sensor.measure()
        current_temp = round(sensor.temperature(), 1)
        current_hum = round(sensor.humidity(), 1)

        save_row(current_temp, current_hum)

        lcd.print(
            "T:{} H:{}%".format(fmt1(current_temp), fmt1(current_hum)),
            hora_text()[:5] + " " + fecha_corta()
        )

    except Exception as e:
        print("Sensor error:", e)
        lcd.print("Error sensor", "")

    try:
        cl, remote = server.accept()
        req = cl.recv(2048)
        req = req.decode("utf-8", "ignore")
        first_line = req.split("\r\n")[0]

        if "GET /csv " in first_line:
            fn = csv_filename()
            if fn in os.listdir():
                with open(fn, "r") as f:
                    data = f.read()
                send_response(cl, data, ctype="text/csv; charset=utf-8")
            else:
                send_response(cl, "No hay archivo todavía", ctype="text/plain; charset=utf-8")
        else:
            send_response(cl, html_page())

        cl.close()

    except OSError:
        pass
    except Exception as e:
        print("Web error:", e)

    gc.collect()
    time.sleep(2)
