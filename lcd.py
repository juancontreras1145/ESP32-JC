from machine import Pin, I2C
import time

class LCD1602_I2C:
    def __init__(self, sda=8, scl=9, addr=0x27):
        self.addr = addr
        self.i2c = I2C(0, sda=Pin(sda), scl=Pin(scl), freq=400000)
        self.init()

    def _write_byte(self, val):
        self.i2c.writeto(self.addr, bytes([val]))

    def _pulse(self, data):
        self._write_byte(data | 0x04)
        time.sleep_us(1)
        self._write_byte(data & ~0x04)
        time.sleep_us(50)

    def _send(self, val, rs):
        high = val & 0xF0
        low = (val << 4) & 0xF0

        self._write_byte(high | rs | 0x08)
        self._pulse(high | rs | 0x08)

        self._write_byte(low | rs | 0x08)
        self._pulse(low | rs | 0x08)

    def cmd(self, c):
        self._send(c, 0)

    def data(self, d):
        self._send(d, 1)

    def init(self):
        time.sleep_ms(50)
        self.cmd(0x33)
        self.cmd(0x32)
        self.cmd(0x28)
        self.cmd(0x0C)
        self.cmd(0x06)
        self.cmd(0x01)
        time.sleep_ms(5)

    def clear(self):
        self.cmd(0x01)
        time.sleep_ms(5)

    def print(self, line1="", line2=""):
        self.clear()
        for c in str(line1)[:16]:
            self.data(ord(c))
        self.cmd(0xC0)
        for c in str(line2)[:16]:
            self.data(ord(c))
