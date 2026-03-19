from machine import Pin, I2C, RTC
import dht
import time
import ntptime
import network
import socket
import os
import gc
import json

# =========================
# CONFIG
# =========================
DHT_PIN = 4
SDA_PIN = 8
SCL_PIN = 9
LCD_ADDR = 39          # 0x27
CSV_FILE = "temperaturas.csv"
SAVE_INTERVAL_MIN = 10
HISTORY_LIMIT = 48     # ultimos 48 registros para la web

# =========================
# LCD I2C
# =========================
i2c = I2C(0, sda=Pin(SDA_PIN), scl=Pin(SCL_PIN), freq=400000)

def write_byte(val):
    i2c.writeto(LCD_ADDR, bytes([val]))

def pulse(data):
    write_byte(data | 0x04)
    time.sleep_us(1)
    write_byte(data & ~0x04)
    time.sleep_us(50)

def send(val, rs):
    high = val & 0xF0
    low = (val << 4) & 0xF0
    write_byte(high | rs | 0x08)
    pulse(high | rs | 0x08)
    write_byte(low | rs | 0x08)
    pulse(low | rs | 0x08)

def cmd(c):
    send(c, 0)

def data(d):
    send(d, 1)

def lcd_init():
    time.sleep_ms(20)
    cmd(0x33)
    cmd(0x32)
    cmd(0x28)
    cmd(0x0C)
    cmd(0x06)
    cmd(0x01)
    time.sleep_ms(5)

def lcd_clear():
    cmd(0x01)
    time.sleep_ms(5)

def lcd_print(line1="", line2=""):
    lcd_clear()
    for c in str(line1)[:16]:
        data(ord(c))
    cmd(0xC0)
    for c in str(line2)[:16]:
        data(ord(c))

# =========================
# SENSOR
# =========================
sensor = dht.DHT22(Pin(DHT_PIN))

# =========================
# WIFI / TIME
# =========================
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

def wifi_ip():
    try:
        if wlan.isconnected():
            return wlan.ifconfig()[0]
    except:
        pass
    return "Sin WiFi"

def wifi_rssi():
    try:
        return wlan.status("rssi")
    except:
        return None

def wifi_quality_text(rssi):
    if rssi is None:
        return "Sin dato"
    if rssi >= -55:
        return "Excelente"
    if rssi >= -67:
        return "Buena"
    if rssi >= -75:
        return "Regular"
    return "Debil"

def sync_time_chile():
    try:
        ntptime.settime()
        return True
    except Exception as e:
        print("Error NTP:", e)
        return False

def now_chile():
    rtc = RTC()
    y, m, d, wd, hh, mm, ss, sub = rtc.datetime()

    # Ajuste simple UTC-3
    hh -= 3
    if hh < 0:
        hh += 24
        d -= 1

    return y, m, d, hh, mm, ss

def fecha_hora_texto():
    y, m, d, hh, mm, ss = now_chile()
    fecha = "{:02d}/{:02d}".format(d, m)
    hora = "{:02d}:{:02d}:{:02d}".format(hh, mm, ss)
    return fecha, hora

# =========================
# CSV
# =========================
def init_csv():
    if CSV_FILE not in os.listdir():
        with open(CSV_FILE, "w") as f:
            f.write("fecha,hora,temp,hum\n")

def guardar_registro(fecha, hora, temp, hum):
    with open(CSV_FILE, "a") as f:
        f.write("{},{},{},{}\n".format(fecha, hora, temp, hum))

def leer_registros(limit=HISTORY_LIMIT):
    filas = []
    try:
        with open(CSV_FILE, "r") as f:
            lineas = f.readlines()

        for linea in lineas[1:]:
            linea = linea.strip()
            if not linea:
                continue
            partes = linea.split(",")
            if len(partes) == 4:
                fecha, hora, temp, hum = partes
                filas.append({
                    "fecha": fecha,
                    "hora": hora,
                    "temp": temp,
                    "hum": hum
                })

        if len(filas) > limit:
            filas = filas[-limit:]

    except Exception as e:
        print("Error leyendo CSV:", e)

    return filas

ultimo_minuto_guardado = -1

def toca_guardar(minuto):
    global ultimo_minuto_guardado
    if minuto % SAVE_INTERVAL_MIN == 0 and minuto != ultimo_minuto_guardado:
        ultimo_minuto_guardado = minuto
        return True
    return False

# =========================
# ESTADO
# =========================
current_temp = None
current_hum = None
last_save_fecha = "-"
last_save_hora = "-"
boot_saved = False
start_ms = time.ticks_ms()

def uptime_text():
    secs = time.ticks_diff(time.ticks_ms(), start_ms) // 1000
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    return "{:02d}:{:02d}:{:02d}".format(h, m, s)

def safe_float(v, default=0):
    try:
        return float(v)
    except:
        return default

# =========================
# HTML / API
# =========================
def json_api():
    fecha, hora = fecha_hora_texto()
    rssi = wifi_rssi()
    hist = leer_registros()

    data_obj = {
        "temp": current_temp,
        "hum": current_hum,
        "fecha": fecha,
        "hora": hora,
        "ip": wifi_ip(),
        "rssi": rssi,
        "wifi_quality": wifi_quality_text(rssi),
        "uptime": uptime_text(),
        "last_save_fecha": last_save_fecha,
        "last_save_hora": last_save_hora,
        "mem_free": gc.mem_free(),
        "history": hist
    }
    return json.dumps(data_obj)

def render_html():
    return """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ESP32 Pro Monitor</title>
<style>
:root{
  --bg:#0f1115;
  --card:#171a21;
  --muted:#9aa4b2;
  --text:#f5f7fb;
  --line:#2a3140;
  --accent:#6ee7b7;
  --accent2:#60a5fa;
  --accent3:#f59e0b;
}
*{box-sizing:border-box}
body{
  margin:0;
  background:linear-gradient(180deg,#0d1016,#111827);
  color:var(--text);
  font-family:Arial,sans-serif;
}
.wrap{
  max-width:980px;
  margin:auto;
  padding:16px;
}
h1{
  margin:0 0 14px 0;
  font-size:28px;
}
.sub{
  color:var(--muted);
  margin-bottom:18px;
}
.grid{
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  gap:12px;
}
@media(min-width:800px){
  .grid{grid-template-columns:repeat(4,minmax(0,1fr))}
}
.card{
  background:rgba(23,26,33,.92);
  border:1px solid var(--line);
  border-radius:18px;
  padding:14px;
  box-shadow:0 6px 20px rgba(0,0,0,.18);
}
.label{
  color:var(--muted);
  font-size:13px;
  margin-bottom:8px;
}
.big{
  font-size:28px;
  font-weight:700;
}
.row{
  display:grid;
  grid-template-columns:1.2fr .8fr;
  gap:12px;
  margin-top:12px;
}
@media(max-width:799px){
  .row{grid-template-columns:1fr}
}
canvas{
  width:100%;
  background:#fff;
  border-radius:14px;
}
table{
  width:100%;
  border-collapse:collapse;
}
th,td{
  padding:8px 6px;
  border-bottom:1px solid var(--line);
  text-align:left;
  font-size:14px;
}
.pill{
  display:inline-block;
  padding:5px 10px;
  border-radius:999px;
  font-size:12px;
  background:#1f2937;
  color:#d1d5db;
}
.actions{
  margin-top:14px;
  display:flex;
  gap:10px;
  flex-wrap:wrap;
}
a.btn{
  text-decoration:none;
  color:#04111f;
  background:var(--accent);
  padding:10px 14px;
  border-radius:12px;
  font-weight:700;
}
a.btn.alt{
  background:var(--accent2);
}
.footer{
  color:var(--muted);
  margin-top:16px;
  font-size:12px;
}
</style>
</head>
<body>
<div class="wrap">
  <h1>ESP32 Pro Monitor</h1>
  <div class="sub">Temperatura, humedad, historial, CSV y estado del sistema</div>

  <div class="grid">
    <div class="card">
      <div class="label">Temperatura actual</div>
      <div class="big" id="temp">--.- C</div>
    </div>
    <div class="card">
      <div class="label">Humedad actual</div>
      <div class="big" id="hum">--.- %</div>
    </div>
    <div class="card">
      <div class="label">WiFi</div>
      <div class="big" id="wifiq">--</div>
      <div class="label" id="rssi">RSSI --</div>
    </div>
    <div class="card">
      <div class="label">IP</div>
      <div class="big" id="ip" style="font-size:20px">--</div>
    </div>
  </div>

  <div class="grid" style="margin-top:12px">
    <div class="card">
      <div class="label">Fecha</div>
      <div class="big" id="fecha" style="font-size:20px">--/--</div>
    </div>
    <div class="card">
      <div class="label">Hora</div>
      <div class="big" id="hora" style="font-size:20px">--:--:--</div>
    </div>
    <div class="card">
      <div class="label">Uptime</div>
      <div class="big" id="uptime" style="font-size:20px">--</div>
    </div>
    <div class="card">
      <div class="label">Memoria libre</div>
      <div class="big" id="mem" style="font-size:20px">--</div>
    </div>
  </div>

  <div class="row">
    <div class="card">
      <div class="label">Historial</div>
      <canvas id="chart" width="640" height="300"></canvas>
      <div class="actions">
        <span class="pill" id="lastsave">Ultimo guardado: --</span>
        <a class="btn" href="/csv">Descargar CSV</a>
        <a class="btn alt" href="/api">Ver API JSON</a>
      </div>
    </div>

    <div class="card">
      <div class="label">Ultimos registros</div>
      <table>
        <thead>
          <tr><th>Fecha</th><th>Hora</th><th>Temp</th><th>Hum</th></tr>
        </thead>
        <tbody id="rows">
          <tr><td colspan="4">Cargando...</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <div class="footer">Actualizacion automatica cada 5 segundos</div>
</div>

<script>
async function loadData(){
  try{
    const r = await fetch('/api');
    const j = await r.json();

    document.getElementById('temp').textContent = (j.temp ?? '--') + ' C';
    document.getElementById('hum').textContent = (j.hum ?? '--') + ' %';
    document.getElementById('wifiq').textContent = j.wifi_quality || '--';
    document.getElementById('rssi').textContent = 'RSSI ' + (j.rssi ?? '--') + ' dBm';
    document.getElementById('ip').textContent = j.ip || '--';
    document.getElementById('fecha').textContent = j.fecha || '--/--';
    document.getElementById('hora').textContent = j.hora || '--:--:--';
    document.getElementById('uptime').textContent = j.uptime || '--';
    document.getElementById('mem').textContent = (j.mem_free ?? '--') + ' B';
    document.getElementById('lastsave').textContent =
      'Ultimo guardado: ' + (j.last_save_fecha || '--') + ' ' + (j.last_save_hora || '--');

    const rows = document.getElementById('rows');
    const hist = j.history || [];
    if(hist.length === 0){
      rows.innerHTML = '<tr><td colspan="4">Sin datos</td></tr>';
    }else{
      rows.innerHTML = hist.slice().reverse().map(r =>
        `<tr><td>${r.fecha}</td><td>${r.hora}</td><td>${r.temp}</td><td>${r.hum}</td></tr>`
      ).join('');
    }

    drawChart(hist);
  }catch(e){
    console.log(e);
  }
}

function drawChart(hist){
  const c = document.getElementById('chart');
  const ctx = c.getContext('2d');
  ctx.clearRect(0,0,c.width,c.height);
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0,0,c.width,c.height);

  if(!hist || hist.length < 2){
    ctx.fillStyle = '#111';
    ctx.font = '16px Arial';
    ctx.fillText('Sin suficientes datos', 20, 30);
    return;
  }

  const temps = hist.map(x => parseFloat(x.temp));
  const hums  = hist.map(x => parseFloat(x.hum));
  const labels = hist.map(x => x.hora);

  const all = temps.concat(hums);
  let minV = Math.min(...all) - 2;
  let maxV = Math.max(...all) + 2;
  if(minV === maxV){ minV -= 1; maxV += 1; }

  const left = 40, top = 20, w = 570, h = 230;

  ctx.strokeStyle = '#ccc';
  ctx.beginPath();
  ctx.moveTo(left, top);
  ctx.lineTo(left, top+h);
  ctx.lineTo(left+w, top+h);
  ctx.stroke();

  ctx.fillStyle = '#333';
  ctx.font = '12px Arial';
  ctx.fillText(maxV.toFixed(1), 6, top+5);
  ctx.fillText(minV.toFixed(1), 6, top+h);

  function plot(data, color){
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    for(let i=0;i<data.length;i++){
      const x = left + (w * i / (data.length - 1));
      const y = top + h - ((data[i]-minV)/(maxV-minV))*h;
      if(i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
    }
    ctx.stroke();
  }

  plot(temps, '#ef4444');
  plot(hums, '#3b82f6');

  ctx.fillStyle = '#ef4444';
  ctx.fillRect(left, top+h+15, 12, 12);
  ctx.fillStyle = '#111';
  ctx.fillText('Temp', left+18, top+h+25);

  ctx.fillStyle = '#3b82f6';
  ctx.fillRect(left+90, top+h+15, 12, 12);
  ctx.fillStyle = '#111';
  ctx.fillText('Hum', left+108, top+h+25);

  ctx.fillStyle = '#666';
  const step = Math.max(1, Math.floor(labels.length / 6));
  for(let i=0;i<labels.length;i+=step){
    const x = left + (w * i / (labels.length - 1));
    ctx.fillText(labels[i], x-12, top+h+45);
  }
}

loadData();
setInterval(loadData, 5000);
</script>
</body>
</html>"""

# =========================
# SERVER
# =========================
def serve():
    addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(addr)
    server.listen(3)
    server.settimeout(1)
    return server

# =========================
# BOOT MAIN
# =========================
lcd_init()
lcd_print("Iniciando...", "Dashboard PRO")
time.sleep(2)

sync_ok = sync_time_chile()
init_csv()

if sync_ok:
    f, h = fecha_hora_texto()
    lcd_print("Hora OK", "{} {}".format(f, h[:5]))
else:
    lcd_print("Sin NTP", wifi_ip())
time.sleep(2)

# guardar una lectura inmediata al arrancar
try:
    sensor.measure()
    current_temp = round(sensor.temperature(), 1)
    current_hum = round(sensor.humidity(), 1)
    f, h = fecha_hora_texto()
    guardar_registro(f, h[:5], current_temp, current_hum)
    last_save_fecha = f
    last_save_hora = h[:5]
    lcd_print("Inicio guardado", "{} {}".format(f, h[:5]))
    time.sleep(2)
except Exception as e:
    print("Error guardado inicial:", e)
    lcd_print("Error inicial", str(e)[:16])
    time.sleep(2)

server = serve()
lcd_print("IP ESP32", wifi_ip())
time.sleep(2)

# =========================
# LOOP
# =========================
while True:
    try:
        sensor.measure()
        current_temp = round(sensor.temperature(), 1)
        current_hum = round(sensor.humidity(), 1)

        fecha, hora_full = fecha_hora_texto()
        _, _, _, hh, mm, ss = now_chile()

        lcd_print("T:{}C H:{}%".format(current_temp, current_hum),
                  "{} {}".format(fecha, hora_full[:5]))

        if toca_guardar(mm):
            guardar_registro(fecha, hora_full[:5], current_temp, current_hum)
            last_save_fecha = fecha
            last_save_hora = hora_full[:5]
            lcd_print("Guardado OK", "{} {}".format(fecha, hora_full[:5]))
            time.sleep(2)

    except Exception as e:
        print("Error sensor:", e)
        lcd_print("Error sensor", str(e)[:16])

    try:
        cl, remote = server.accept()
        req = cl.recv(1024)
        req_str = req.decode("utf-8")

        if "GET /api " in req_str:
            payload = json_api()
            cl.send("HTTP/1.1 200 OK\r\n")
            cl.send("Content-Type: application/json\r\n")
            cl.send("Connection: close\r\n\r\n")
            cl.sendall(payload)

        elif "GET /csv " in req_str:
            try:
                with open(CSV_FILE, "r") as f:
                    contenido = f.read()
                cl.send("HTTP/1.1 200 OK\r\n")
                cl.send("Content-Type: text/csv\r\n")
                cl.send("Content-Disposition: attachment; filename=temperaturas.csv\r\n")
                cl.send("Connection: close\r\n\r\n")
                cl.sendall(contenido)
            except:
                cl.send("HTTP/1.1 500 Internal Server Error\r\nContent-Type: text/plain\r\n\r\n")
                cl.sendall("Error CSV")

        else:
            html = render_html()
            cl.send("HTTP/1.1 200 OK\r\n")
            cl.send("Content-Type: text/html; charset=utf-8\r\n")
            cl.send("Connection: close\r\n\r\n")
            cl.sendall(html)

        cl.close()

    except OSError:
        pass

    gc.collect()
    time.sleep(1)