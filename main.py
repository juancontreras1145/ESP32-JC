from machine import Pin, I2C
import network
import socket
import time
import dht

# WIFI
SSID = "TU_HOTSPOT"
PASSWORD = "TU_CLAVE"

# SENSOR
sensor = dht.DHT11(Pin(4))

# LCD
i2c = I2C(0, sda=Pin(8), scl=Pin(9))
devices = i2c.scan()

lcd_addr = devices[0] if devices else None

def conectar_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)

    while not wlan.isconnected():
        time.sleep(1)

    print("WiFi conectado")
    print(wlan.ifconfig())

    return wlan.ifconfig()[0]

ip = conectar_wifi()

# SERVIDOR WEB
addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
server = socket.socket()
server.bind(addr)
server.listen(1)

print("Servidor activo en:", ip)

while True:

    sensor.measure()
    temp = sensor.temperature()
    hum = sensor.humidity()

    conn, addr = server.accept()
    request = conn.recv(1024)

    html = f"""
    <html>
    <head>
    <title>ESP32 Sensor</title>
    </head>
    <body style="font-family:Arial">
    <h1>ESP32 Monitor</h1>
    <h2>Temperatura: {temp} C</h2>
    <h2>Humedad: {hum} %</h2>
    </body>
    </html>
    """

    conn.send("HTTP/1.1 200 OK\n")
    conn.send("Content-Type: text/html\n")
    conn.send("Connection: close\n\n")
    conn.sendall(html)
    conn.close()