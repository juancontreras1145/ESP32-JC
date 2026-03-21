from machine import I2C
import time

class LCD:
    def __init__(self, i2c, addr=0x27):
        self.i2c = i2c
        self.addr = addr
        self.backlight = 0x08
        self._startup()

    def _write(self, data):
        self.i2c.writeto(self.addr, bytes([data | self.backlight]))

    def _pulse(self, data):
        self._write(data | 0x04)
        time.sleep_us(1)
        self._write(data & ~0x04)
        time.sleep_us(50)

    def _send4(self, nibble, rs=0):
        data = (nibble & 0xF0) | rs
        self._write(data)
        self._pulse(data)

    def _send8(self, value, rs=0):
        self._send4(value & 0xF0, rs)
        self._send4((value << 4) & 0xF0, rs)

    def command(self, cmd):
        self._send8(cmd, 0)
        if cmd in (0x01, 0x02):
            time.sleep_ms(2)

    def write_char(self, c):
        self._send8(ord(c), 1)

    def _startup(self):
        time.sleep_ms(50)
        for _ in range(3):
            self._send4(0x30)
            time.sleep_ms(5)

        self._send4(0x20)
        time.sleep_ms(5)

        self.command(0x28)
        self.command(0x0C)
        self.command(0x06)
        self.command(0x01)
        time.sleep_ms(5)

    def reinit(self):
        self._startup()

    def clear(self):
        self.command(0x01)

    def home(self):
        self.command(0x02)

    def move_to(self, col, row):
        addr = 0x80 + (0x40 * row) + col
        self.command(addr)

    def putstr(self, s):
        for ch in s:
            self.write_char(ch)

    def backlight_on(self):
        self.backlight = 0x08
        self._write(0x00)

    def backlight_off(self):
        self.backlight = 0x00
        self._write(0x00)