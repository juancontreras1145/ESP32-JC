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

        self.command(0x28)   # 4 bits, 2 lineas
        self.command(0x0C)   # display on
        self.command(0x06)   # entry mode
        self.command(0x01)   # clear
        time.sleep_ms(2)

    # -------------------------
    # BAJO NIVEL
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
    # COMANDOS
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
    # RELLENO MANUAL
    # -------------------------
    def _pad_left(self, text):
        if len(text) >= self.cols:
            return text[:self.cols]
        return text + (" " * (self.cols - len(text)))

    def _pad_right(self, text):
        if len(text) >= self.cols:
            return text[:self.cols]
        return (" " * (self.cols - len(text))) + text

    def _pad_center(self, text):
        if len(text) >= self.cols:
            return text[:self.cols]
        total = self.cols - len(text)
        left = total // 2
        right = total - left
        return (" " * left) + text + (" " * right)

    # -------------------------
    # ESCRITURA
    # -------------------------
    def write_line(self, text, row=0, align="left"):
        text = str(text)

        if len(text) > self.cols:
            text = text[:self.cols]

        if align == "center":
            text = self._pad_center(text)
        elif align == "right":
            text = self._pad_right(text)
        else:
            text = self._pad_left(text)

        self.move_to(0, row)
        self.putstr(text)

    def message(self, line1="", line2=""):
        self.write_line(line1, 0, "left")
        if self.rows > 1:
            self.write_line(line2, 1, "left")

    def message_centered(self, line1="", line2=""):
        self.write_line(line1, 0, "center")
        if self.rows > 1:
            self.write_line(line2, 1, "center")

    def scroll_text(self, text, row=0, delay_ms=180, loops=1):
        text = str(text)
        if len(text) <= self.cols:
            self.write_line(text, row)
            return

        buf = text + "    "
        max_i = len(buf) - self.cols + 1

        for _ in range(loops):
            for i in range(max_i):
                self.write_line(buf[i:i+self.cols], row)
                time.sleep_ms(delay_ms)