# ======================================
# ESP32 RESCATE SERVER + UPDATE GITHUB
# ======================================

import socket
import os
import network
import time

PORT = 80
TOKEN = "jc123"

# URL de tu main.py en GitHub
GITHUB_MAIN = "https://raw.githubusercontent.com/USUARIO/REPO/main/main.py"

def wifi_ip():
    try:
        wlan = network.WLAN(network.STA_IF)
        if wlan.isconnected():
            return wlan.ifconfig()[0]
    except:
        pass
    return "0.0.0.0"

def parse_path(req):
    try:
        line = req.split("\r\n")[0]
        return line.split(" ")[1]
    except:
        return "/"

def split_args(path):
    if "?" not in path:
        return path, {}

    p,q = path.split("?",1)
    args={}

    for pair in q.split("&"):
        if "=" in pair:
            k,v = pair.split("=",1)
        else:
            k,v = pair,""
        args[k]=v

    return p,args

def list_files():
    out=[]
    try:
        for f in os.listdir():
            try:
                size=os.stat(f)[6]
            except:
                size=0
            out.append((f,size))
    except:
        pass
    return out

def page_files():

    rows=""

    for name,size in list_files():
        rows += "<li><a href='/download?name={}'> {} ({} bytes)</a></li>".format(name,name,size)

    return """<html>
<body>
<h2>ESP32 RESCATE</h2>

<a href="/update">Actualizar main.py desde GitHub</a>

<h3>Archivos</h3>
<ul>
{}
</ul>

</body>
</html>
""".format(rows)

def send_file_stream(cl,filename):

    if not filename or filename not in os.listdir():
        cl.send("HTTP/1.0 404 Not Found\r\n\r\n")
        return

    size=os.stat(filename)[6]

    headers=[
        "HTTP/1.0 200 OK",
        "Content-Type: application/octet-stream",
        "Content-Length: {}".format(size),
        "Content-Disposition: attachment; filename={}".format(filename),
        "\r\n"
    ]

    cl.send("\r\n".join(headers))

    with open(filename,"rb") as f:
        while True:
            data=f.read(1024)
            if not data:
                break
            cl.send(data)

def update_from_github(cl):

    try:
        import urequests

        r = urequests.get(GITHUB_MAIN)
        code = r.text
        r.close()

        with open("main.py","w") as f:
            f.write(code)

        body="Actualizado desde GitHub. Reinicia ESP32."

    except Exception as e:
        body="Error update: {}".format(e)

    cl.send("HTTP/1.0 200 OK\r\nContent-Type:text/plain\r\n\r\n")
    cl.send(body)

def handle(cl):

    req = cl.recv(1024).decode()

    path=parse_path(req)
    path,args=split_args(path)

    if path=="/":
        body=page_files()
        cl.send("HTTP/1.0 200 OK\r\nContent-Type:text/html\r\n\r\n")
        cl.send(body)

    elif path=="/download":
        send_file_stream(cl,args.get("name",""))

    elif path=="/update":
        update_from_github(cl)

    else:
        cl.send("HTTP/1.0 404 Not Found\r\n\r\n")

def main():

    print("RESCATE SERVER")
    print("IP:",wifi_ip())

    addr=socket.getaddrinfo("0.0.0.0",PORT)[0][-1]

    s=socket.socket()
    s.bind(addr)
    s.listen(5)

    while True:

        cl,addr=s.accept()

        try:
            handle(cl)
        except Exception as e:
            print("error:",e)

        try:
            cl.close()
        except:
            pass


main()