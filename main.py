# =====================================
# ESP32 JC - MAIN RESCATE MINIMO
# =====================================

import time
import os
import gc
import socket
import network
import machine

VERSION = "ESP32 JC Rescue Main v1"

LOG_FILE = "main.log"
PORT = 80
SERVER_TIMEOUT = 1

inicio_epoch = time.time()
wifi_ip = "Sin WiFi"
server = None


def log(msg):
    line = "[MAIN] {}".format(msg)
    print(line)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except:
        pass


def uptime_texto():
    try:
        seg = max(0, int(time.time() - inicio_epoch))
    except:
        seg = 0
    h = seg // 3600
    m = (seg % 3600) // 60
    s = seg % 60
    return "{:02d}:{:02d}:{:02d}".format(h, m, s)


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


def html_escape(s):
    try:
        s = str(s)
        s = s.replace("&", "&amp;")
        s = s.replace("<", "&lt;")
        s = s.replace(">", "&gt;")
        s = s.replace('"', "&quot;")
        return s
    except:
        return ""


def read_logs_tail(max_lines=80):
    try:
        if LOG_FILE not in os.listdir():
            return "Sin logs"
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()
        if len(lines) > max_lines:
            lines = lines[-max_lines:]
        return "".join(lines)
    except Exception as e:
        return "Error leyendo log: {}".format(e)


def list_files_text():
    out = []
    try:
        items = os.listdir()
        items.sort()
        for name in items:
            try:
                size = os.stat(name)[6]
            except:
                size = 0
            out.append("{} ({} bytes)".format(name, size))
    except Exception as e:
        out.append("Error listando archivos: {}".format(e))
    return "\n".join(out)


def page_home():
    return """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ESP32 Rescue Main</title>
<style>
body { font-family: Arial; background:#08111f; color:#eef4ff; padding:16px; }
.card { background:#0d1b2a; border:1px solid #1f4f88; border-radius:16px; padding:16px; margin-bottom:16px; }
pre { background:#040b16; padding:12px; border-radius:10px; white-space:pre-wrap; overflow-wrap:break-word; }
a { color:#8ec5ff; }
</style>
</head>
<body>
<div class="card">
<h1>ESP32 Rescue Main</h1>
<p><b>Version:</b> %s</p>
<p><b>IP:</b> %s</p>
<p><b>Uptime:</b> %s</p>
<p><a href="/reset">Reiniciar</a></p>
<p><a href="/ping">Ping</a></p>
</div>

<div class="card">
<h2>Archivos</h2>
<pre>%s</pre>
</div>

<div class="card">
<h2>main.log</h2>
<pre>%s</pre>
</div>
</body>
</html>
""" % (
        html_escape(VERSION),
        html_escape(wifi_ip),
        html_escape(uptime_texto()),
        html_escape(list_files_text()),
        html_escape(read_logs_tail(80)),
    )


def respond(cl, body, ctype="text/html; charset=utf-8", code="200 OK"):
    try:
        if isinstance(body, bytes):
            body_bytes = body
        else:
            body_bytes = body.encode("utf-8")

        headers = [
            "HTTP/1.0 {}".format(code),
            "Content-Type: {}".format(ctype),
            "Content-Length: {}".format(len(body_bytes)),
            "Connection: close",
        ]
        cl.send("\r\n".join(headers))
        cl.send("\r\n\r\n")
        cl.send(body_bytes)
    except Exception as e:
        log("respond error: {}".format(e))


def route_path(req_text):
    try:
        line = req_text.split("\r\n")[0]
        parts = line.split(" ")
        if len(parts) >= 2:
            return parts[1]
    except:
        pass
    return "/"


def init_server():
    global server
    try:
        addr = socket.getaddrinfo("0.0.0.0", PORT)[0][-1]
        server = socket.socket()
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(addr)
        server.listen(2)
        server.settimeout(SERVER_TIMEOUT)
        log("Servidor web listo en puerto {}".format(PORT))
        return True
    except Exception as e:
        server = None
        log("Error iniciando servidor: {}".format(e))
        return False


def handle_web():
    global server

    if server is None:
        return

    try:
        cl, addr = server.accept()
    except OSError:
        return
    except Exception as e:
        log("accept error: {}".format(e))
        return

    try:
        req = cl.recv(1024)
        if not req:
            cl.close()
            return

        try:
            req_text = req.decode("utf-8")
        except:
            req_text = str(req)

        path = route_path(req_text)

        if path == "/ping":
            respond(cl, "OK: " + VERSION, ctype="text/plain; charset=utf-8")
        elif path == "/reset":
            respond(cl, "Reiniciando...", ctype="text/plain; charset=utf-8")
            try:
                cl.close()
            except:
                pass
            time.sleep(1)
            machine.reset()
            return
        else:
            respond(cl, page_home())

    except Exception as e:
        log("handler error: {}".format(e))

    try:
        cl.close()
    except:
        pass


log("Inicio " + VERSION)
gc.collect()
refresh_ip()
init_server()
log("IP: {}".format(wifi_ip))

while True:
    try:
        gc.collect()
        refresh_ip()
        handle_web()
        time.sleep(0.2)
    except Exception as e:
        log("loop error: {}".format(e))
        time.sleep(1)