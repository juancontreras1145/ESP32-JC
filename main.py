from machine import Pin, I2C
import time
import dht
import network

LCD_ADDR = 39
i2c = I2C(0, scl=Pin(9), sda=Pin(8), freq=400000)

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

sensor = dht.DHT22(Pin(4))

SSID = "S25"
PASSWORD = "12345678"

lcd_init()
lcd_print("RECUPERADO", "Conectando...")

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(SSID, PASSWORD)

timeout = 15
while not wlan.isconnected() and timeout > 0:
    time.sleep(1)
    timeout -= 1

ip = wlan.ifconfig()[0] if wlan.isconnected() else "NO WIFI"

while True:
    try:
        sensor.measure()
        t = sensor.temperature()
        h = sensor.humidity()
        lcd_print("IP:" + ip, "T:{:.1f} H:{:.1f}".format(t, h))
    except Exception as e:
        lcd_print("RECUPERADO", "Sensor error")
    time.sleep(5)