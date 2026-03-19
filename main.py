from machine import Pin, I2C
import time
import dht

# =========================
# CONFIGURACION
# =========================

DHT_PIN = 4
I2C_SDA = 8
I2C_SCL = 9
I2C_FREQ = 400000

LCD_COLS = 16
LCD_ROWS = 2

# Direcciones I2C comunes del modulo PCF8574
LCD_ADDRS = [0x27, 0x3F]

# =========================
# DRIVER LCD I2C 16x2
# =========================

class I2cLcd:
    MASK_RS = 0x01
    MASK_RW = 0x02
    MASK_E  = 0x04
    SHIFT_BACKLIGHT = 3
    SHIFT_DATA = 4

    def __init__(self, i2c, addr, num_lines, num_columns):
        self.i2c = i2c
        self.addr = addr
        self.num_lines = num_lines
        self.num_columns = num_columns
        self.backlight = True

        time.sleep_ms(20)
        self._write_init_nibble(0x03)
        time.sleep_ms(5)
        self._write_init_nibble(0x03)
        time.sleep_ms(1)
        self._write_init_nibble(0x03)
        time.sleep_ms(1)
        self._write_init_nibble(0x02)

        self._cmd(0x28)  # 4-bit, 2 lines, 5x8
        self._cmd(0x0C)  # display on, cursor off
        self._cmd(0x06)  # entry mode
        self.clear()

    def _write_byte(self, val):
        self.i2c.writeto(self.addr, bytes([val]))

    def _pulse_enable(self, data):
        self._write_byte(data | self.MASK_E)
        time.sleep_us(1)
        self._write_byte(data & ~self.MASK_E)
        time.sleep_us(50)

    def _write4bits(self, nibble, rs=0):
        data = (nibble << self.SHIFT_DATA)
        if self.backlight:
            data |= (1 << self.SHIFT_BACKLIGHT)
        if rs:
            data |= self.MASK_RS
        self._write_byte(data)
        self._pulse_enable(data)

    def _write_init_nibble(self, nibble):
        data = (nibble << self.SHIFT_DATA)
        if self.backlight:
            data |= (1 << self.SHIFT_BACKLIGHT)
        self._write_byte(data)
        self._pulse_enable(data)

    def _send(self, value, rs=0):
        self._write4bits((value >> 4) & 0x0F, rs)
        self._write4bits(value & 0x0F, rs)

    def _cmd(self, cmd):
        self._send(cmd, 0)
        if cmd in (0x01, 0x02):
            time.sleep_ms(2)

    def _data(self, data):
        self._send(data, 1)

    def clear(self):
        self._cmd(0x01)
        time.sleep_ms(2)

    def move_to(self, col, row):
        row_offsets = [0x00, 0x40, 0x14, 0x54]
        self._cmd(0x80 | (col + row_offsets[row]))

    def putstr(self, string):
        for ch in string:
            self._data(ord(ch))

    def putline(self, text, row=0):
        text = str(text)
        if len(text) < self.num_columns:
            text = text + (" " * (self.num_columns - len(text)))
        else:
            text = text[:self.num_columns]

        self.move_to(0, row)
        self.putstr(text)

# =========================
# INICIALIZACION
# =========================

print("Iniciando sensor DHT11...")
sensor = dht.DHT11(Pin(DHT_PIN))

print("Iniciando I2C...")
i2c = I2C(0, sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=I2C_FREQ)

encontrados = i2c.scan()
print("I2C encontrados:", [hex(x) for x in encontrados])

lcd_addr = None
for addr in LCD_ADDRS:
    if addr in encontrados:
        lcd_addr = addr
        break

if lcd_addr is None:
    raise Exception("No se encontro LCD I2C en 0x27 ni 0x3F")

print("LCD encontrado en:", hex(lcd_addr))
lcd = I2cLcd(i2c, lcd_addr, LCD_ROWS, LCD_COLS)

lcd.clear()
lcd.putline("ESP32 + DHT11", 0)
lcd.putline("Iniciando...", 1)
time.sleep(2)

# =========================
# LOOP PRINCIPAL
# =========================

while True:
    try:
        sensor.measure()
        temp = sensor.temperature()
        hum = sensor.humidity()

        print("Temperatura:", temp, "C")
        print("Humedad:", hum, "%")

        lcd.putline("Temp: {} C".format(temp), 0)
        lcd.putline("Hum : {} %".format(hum), 1)

    except Exception as e:
        print("Error:", e)
        lcd.putline("Error sensor", 0)
        lcd.putline(str(e)[:16], 1)

    time.sleep(2)
