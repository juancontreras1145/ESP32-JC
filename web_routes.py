
import socket

server = None

def init_server(port=80):
    global server
    addr = socket.getaddrinfo("0.0.0.0",port)[0][-1]
    server = socket.socket()
    server.bind(addr)
    server.listen(1)

def handle_web():
    global server
    try:
        cl,addr = server.accept()
        req = cl.recv(512)
        cl.send("HTTP/1.0 200 OK\r\nContent-type:text/html\r\n\r\n")
        cl.send("<h1>ESP32 Monitor activo</h1>")
        cl.close()
    except:
        pass
