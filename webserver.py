import socket

server = None

def start():
    global server

    addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]

    server = socket.socket()
    server.bind(addr)
    server.listen(1)

    print("Webserver iniciado en puerto 80")
