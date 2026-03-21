from machine import I2C
import time

class LCD:

    def __init__(self, i2c, addr=0x27):
        self.i2c = i2c
        self.addr = addr

        self.backlight = 0x08

        self.init_lcd()

    def write_byte(self, data):
        self.i2c.writeto(self.addr, bytes([data | self.backlight]))

    def toggle_enable(self, data):
        self.write_byte(data | 0x04)
        time.sleep_us(1)
        self.write_byte(data & ~0x04)
        time.sleep_us(50)

    def send(self, data, mode=0):
        high = mode | (data & 0xF0)
        low = mode | ((data << 4) & 0xF0)

        self.write_byte(high)
        self.toggle_enable(high)

        self.write_byte(low)
        self.toggle_enable(low)

    def command(self, cmd):
        self.send(cmd, 0)

    def write_char(self, char):
        self.send(ord(char), 1)

    def init_lcd(self):

        time.sleep_ms(50)

        self.write_byte(0x30)
        time.sleep_ms(5)

        self.write_byte(0x30)
        time.sleep_ms(5)

        self.write_byte(0x30)
        time.sleep_ms(5)

        self.write_byte(0x20)
        time.sleep_ms(5)

        self.command(0x28)
        self.command(0x08)
        self.command(0x01)
        time.sleep_ms(2)
        self.command(0x06)
        self.command(0x0C)

    def clear(self):
        self.command(0x01)
        time.sleep_ms(2)

    def move_to(self, col, row):

        addr = col + (0x40 * row)

        self.command(0x80 | addr)

    def putstr(self, string):

        for char in string:
            self.write_char(char)
