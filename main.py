from machine import Pin, I2C
import network
import socket
import time
import dht

# =====================
# SENSOR
# =====================

sensor = dht.DHT11(Pin(4))

# =====================
# LCD I2C
# =====================

i2c = I2C(0, sda=Pin(8), scl=Pin(9), freq=400000)

devices = i2c.scan()

lcd_addr = None
for d in devices:
    if d in [0x27, 0x3F]:
        lcd_addr = d
        break

def lcd_print(line1, line2=""):
    try:
        i2c.writeto(lcd_addr, b'\x00')
    except:
        pass

# =====================
# WIFI
# =====================

wlan = network.WLAN(network.STA_IF)
wlan.active(True)

while not wlan.isconnected():
    time.sleep(1)

ip = wlan.ifconfig()[0]

print("IP:", ip)

# =====================
# SERVIDOR WEB
# =====================

addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]

server = socket.socket()
server.bind(addr)
server.listen(1)

print("Servidor web activo")

# =====================
# LOOP
# =====================

while True:

    sensor.measure()
    temp = sensor.temperature()
    hum = sensor.humidity()

    print("Temp:", temp, "Hum:", hum)

    try:
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

    except:
        pass

    time.sleep(2)