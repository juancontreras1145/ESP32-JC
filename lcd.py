from time import sleep_ms

class LCD:
    def __init__(self, i2c, addr, cols=16, rows=2):
        self.i2c = i2c
        self.addr = addr
        self.cols = cols
        self.rows = rows

        self.backlight = 0x08

        sleep_ms(20)
        self._write(0x30)
        sleep_ms(5)
        self._write(0x30)
        sleep_ms(1)
        self._write(0x30)
        self._write(0x20)

        self.command(0x28)
        self.command(0x08)
        self.command(0x01)
        sleep_ms(2)
        self.command(0x06)
        self.command(0x0C)

    def _write(self, data):
        self.i2c.writeto(self.addr, bytes([data | self.backlight]))

    def _pulse(self, data):
        self._write(data | 0x04)
        self._write(data & ~0x04)

    def _send(self, data, mode):
        high = data & 0xF0
        low = (data << 4) & 0xF0
        self._pulse(high | mode)
        self._pulse(low | mode)

    def command(self, cmd):
        self._send(cmd, 0)

    def write(self, char):
        self._send(ord(char), 1)

    def clear(self):
        self.command(0x01)
        sleep_ms(2)

    def move_to(self, col, row):
        addr = col + (0x40 * row)
        self.command(0x80 | addr)

    def message(self, line1="", line2=""):
        self.clear()
        self.move_to(0,0)
        for c in line1[:16]:
            self.write(c)

        self.move_to(0,1)
        for c in line2[:16]:
            self.write(c)

    def message_centered(self, line1="", line2=""):
        l1 = line1.center(self.cols)
        l2 = line2.center(self.cols)
        self.message(l1,l2)

    def backlight_on(self):
        self.backlight = 0x08
        self._write(0)

    def backlight_off(self):
        self.backlight = 0x00
        self._write(0)