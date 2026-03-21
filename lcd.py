import time

class LCD:

    def __init__(self, i2c, addr=0x27, cols=16, rows=2):
        self.i2c = i2c
        self.addr = addr
        self.cols = cols
        self.rows = rows
        self.backlight = True

        time.sleep_ms(50)

        self._write4(0x30)
        time.sleep_ms(5)
        self._write4(0x30)
        time.sleep_ms(5)
        self._write4(0x30)
        time.sleep_ms(5)

        self._write4(0x20)
        time.sleep_ms(5)

        self.command(0x28)
        self.command(0x0C)
        self.command(0x06)
        self.command(0x01)

    # -------------------------
    # LOW LEVEL
    # -------------------------

    def _write_byte(self, data):
        self.i2c.writeto(self.addr, bytes([data | (0x08 if self.backlight else 0)]))

    def _pulse(self, data):
        self._write_byte(data | 0x04)
        time.sleep_us(1)
        self._write_byte(data & ~0x04)
        time.sleep_us(50)

    def _write4(self, data, rs=0):
        val = (data & 0xF0) | (0x01 if rs else 0)
        self._write_byte(val)
        self._pulse(val)

    def _write8(self, data, rs=0):
        self._write4(data & 0xF0, rs)
        self._write4((data << 4) & 0xF0, rs)

    # -------------------------
    # COMMANDS
    # -------------------------

    def command(self, cmd):
        self._write8(cmd, 0)
        if cmd in (0x01, 0x02):
            time.sleep_ms(2)

    def write_char(self, ch):
        self._write8(ord(ch), 1)

    def putstr(self, text):
        for c in text:
            self.write_char(c)

    def clear(self):
        self.command(0x01)

    def home(self):
        self.command(0x02)

    def move_to(self, col, row):
        row_offsets = [0x00, 0x40, 0x14, 0x54]
        self.command(0x80 + row_offsets[row] + col)

    # -------------------------
    # BACKLIGHT
    # -------------------------

    def backlight_on(self):
        self.backlight = True
        self._write_byte(0)

    def backlight_off(self):
        self.backlight = False
        self._write_byte(0)

    # -------------------------
    # TEXT
    # -------------------------

    def write_line(self, text, row=0, align="left"):

        if len(text) > self.cols:
            text = text[:self.cols]

        if align == "center":
            text = text.center(self.cols)
        elif align == "right":
            text = text.rjust(self.cols)
        else:
            text = text.ljust(self.cols)

        self.move_to(0, row)
        self.putstr(text)

    def message(self, line1="", line2=""):
        self.write_line(line1, 0)
        if self.rows > 1:
            self.write_line(line2, 1)

    def message_centered(self, line1="", line2=""):
        self.write_line(line1, 0, "center")
        if self.rows > 1:
            self.write_line(line2, 1, "center")

    # -------------------------
    # SCROLL
    # -------------------------

    def scroll_text(self, text, row=0, delay_ms=200, loops=1):

        if len(text) <= self.cols:
            self.write_line(text, row)
            return

        buf = text + "    "

        for _ in range(loops):
            for i in range(len(buf) - self.cols + 1):
                self.write_line(buf[i:i+self.cols], row)
                time.sleep_ms(delay_ms)

    # -------------------------
    # REINIT
    # -------------------------

    def reinit(self):
        self.clear()
        self.command(0x28)
        self.command(0x0C)
        self.command(0x06)