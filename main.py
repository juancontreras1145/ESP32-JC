VERSION = "MONITOR OK 00:20"

from machine import Pin, I2C
import dht
import time
import network
import socket

# -------- WIFI --------
SSID = "S25"
PASSWORD = "12345678"

# -------- LCD --------
LCD_ADDR = 39
ROWS = 2
COLS = 16

i2c = I2C(0, scl=Pin(9), sda=Pin(8))

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

# -------- SENSOR --------
sensor = dht.DHT22(Pin(4))

# -------- WIFI --------
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

lcd_init()
lcd_print("Conectando WiFi", "")

wlan.connect(SSID, PASSWORD)

timeout = 15

while not wlan.isconnected() and timeout > 0:
    time.sleep(1)
    timeout -= 1

if wlan.isconnected():
    ip = wlan.ifconfig()[0]
else:
    ip = "NO WIFI"

# -------- VERSION --------

lcd_print("VERSION:", VERSION)
time.sleep(3)

# -------- WEB SERVER --------

def webpage(temp, hum):
    html = f"""
    <html>
    <head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>ESP32 Monitor</title>
    </head>

    <body style="font-family:Arial;text-align:center">

    <h1>ESP32 Monitor</h1>

    <h2>Temperatura</h2>
    <h3>{temp} °C</h3>

    <h2>Humedad</h2>
    <h3>{hum} %</h3>

    <p>IP: {ip}</p>

    <p>VERSION: {VERSION}</p>

    </body>
    </html>
    """
    return html

addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
server = socket.socket()
server.bind(addr)
server.listen(1)

# -------- LOOP --------

while True:

    try:
        sensor.measure()
        temp = sensor.temperature()
        hum = sensor.humidity()

        lcd_print(
            "T:{}C H:{}%".format(temp, hum),
            "IP:" + ip
        )

    except:
        temp = 0
        hum = 0
        lcd_print("Sensor error", "")

    try:
        conn, addr = server.accept()
        request = conn.recv(1024)

        response = webpage(temp, hum)

        conn.send("HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n")
        conn.send(response)
        conn.close()

    except:
        pass

    time.sleep(5)