from machine import Pin, I2C
import time

I2C_SDA = 8
I2C_SCL = 9

# Inicializar I2C
i2c = I2C(0, sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=400000)

print("Escaneando I2C...")
devices = i2c.scan()
print("Encontrados:", [hex(d) for d in devices])

if not devices:
    raise Exception("No se detecto ningun dispositivo I2C")

addr = devices[0]

# LCD simple
class LCD:
    def __init__(self, i2c, addr):
        self.i2c = i2c
        self.addr = addr
        self.backlight = 0x08
        self.init_lcd()

    def write(self, data):
        self.i2c.writeto(self.addr, bytes([data | self.backlight]))

    def pulse(self, data):
        self.write(data | 0x04)
        time.sleep_us(1)
        self.write(data & ~0x04)
        time.sleep_us(50)

    def send(self, data, rs):
        high = data & 0xF0
        low = (data << 4) & 0xF0
        self.write(high | rs)
        self.pulse(high | rs)
        self.write(low | rs)
        self.pulse(low | rs)

    def cmd(self, cmd):
        self.send(cmd, 0)

    def data(self, data):
        self.send(data, 1)

    def init_lcd(self):
        time.sleep_ms(20)
        self.cmd(0x33)
        self.cmd(0x32)
        self.cmd(0x28)
        self.cmd(0x0C)
        self.cmd(0x06)
        self.cmd(0x01)

    def clear(self):
        self.cmd(0x01)

    def print(self, text):
        for c in text:
            self.data(ord(c))

lcd = LCD(i2c, addr)

lcd.clear()
lcd.print("Hola Camila")

lcd.cmd(0xC0)  # segunda linea
lcd.print("Te Quiero")

while True:
    time.sleep(1)