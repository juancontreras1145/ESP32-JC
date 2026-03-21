from machine import I2C
import time


class LCD:
    # Bits del PCF8574
    MASK_RS = 0x01
    MASK_RW = 0x02
    MASK_E  = 0x04
    MASK_BL = 0x08

    def __init__(self, i2c: I2C, addr: int = 0x27, cols: int = 16, rows: int = 2):
        self.i2c = i2c
        self.addr = addr
        self.cols = cols
        self.rows = rows
        self.backlight = True
        self._startup()

    # =========================
    # Internos
    # =========================
    def _bl_mask(self) -> int:
        return self.MASK_BL if self.backlight else 0x00

    def _write_byte(self, value: int) -> None:
        self.i2c.writeto(self.addr, bytes([value | self._bl_mask()]))

    def _pulse_enable(self, value: int) -> None:
        self._write_byte(value | self.MASK_E)
        time.sleep_us(1)
        self._write_byte(value & ~self.MASK_E)
        time.sleep_us(50)

    def _write4(self, nibble: int, rs: int = 0) -> None:
        value = (nibble & 0xF0) | (self.MASK_RS if rs else 0)
        self._write_byte(value)
        self._pulse_enable(value)

    def _write8(self, value: int, rs: int = 0) -> None:
        self._write4(value & 0xF0, rs)
        self._write4((value << 4) & 0xF0, rs)

    def _sanitize(self, text: str) -> str:
        # LCD HD44780 no maneja bien muchos caracteres unicode/acentos
        repl = {
            "á": "a", "à": "a", "ä": "a", "â": "a",
            "é": "e", "è": "e", "ë": "e", "ê": "e",
            "í": "i", "ì": "i", "ï": "i", "î": "i",
            "ó": "o", "ò": "o", "ö": "o", "ô": "o",
            "ú": "u", "ù": "u", "ü": "u", "û": "u",
            "Á": "A", "À": "A", "Ä": "A", "Â": "A",
            "É": "E", "È": "E", "Ë": "E", "Ê": "E",
            "Í": "I", "Ì": "I", "Ï": "I", "Î": "I",
            "Ó": "O", "Ò": "O", "Ö": "O", "Ô": "O",
            "Ú": "U", "Ù": "U", "Ü": "U", "Û": "U",
            "ñ": "n", "Ñ": "N",
            "°": chr(223),   # suele verse bien como símbolo grado
        }

        out = []
        for ch in str(text):
            if ch in repl:
                out.append(repl[ch])
            else:
                code = ord(ch)
                if 32 <= code <= 126:
                    out.append(ch)
                else:
                    out.append("?")
        return "".join(out)

    def _row_addr(self, row: int) -> int:
        # Direcciones típicas HD44780
        row_offsets = [0x00, 0x40, 0x14, 0x54]
        if row < 0:
            row = 0
        if row >= self.rows:
            row = self.rows - 1
        return 0x80 + row_offsets[row]

    # =========================
    # Inicialización
    # =========================
    def _startup(self) -> None:
        time.sleep_ms(50)

        # Secuencia robusta para 4 bits
        for _ in range(3):
            self._write4(0x30)
            time.sleep_ms(5)

        self._write4(0x20)
        time.sleep_ms(5)

        # Function set
        if self.rows > 1:
            self.command(0x28)  # 4-bit, 2 líneas, 5x8
        else:
            self.command(0x20)  # 4-bit, 1 línea

        self.command(0x0C)      # display on, cursor off, blink off
        self.command(0x06)      # entry mode: cursor avanza
        self.command(0x01)      # clear
        time.sleep_ms(3)

    def reinit(self) -> None:
        self._startup()

    # =========================
    # Comandos base
    # =========================
    def command(self, cmd: int) -> None:
        self._write8(cmd, rs=0)
        if cmd in (0x01, 0x02):
            time.sleep_ms(3)

    def write_char(self, ch: str) -> None:
        ch = self._sanitize(ch)
        if not ch:
            return
        self._write8(ord(ch[0]), rs=1)

    def putstr(self, text: str) -> None:
        text = self._sanitize(text)
        for ch in text:
            self.write_char(ch)

    def clear(self) -> None:
        self.command(0x01)

    def home(self) -> None:
        self.command(0x02)

    def move_to(self, col: int, row: int) -> None:
        if col < 0:
            col = 0
        if col >= self.cols:
            col = self.cols - 1
        self.command(self._row_addr(row) + col)

    # =========================
    # Backlight
    # =========================
    def backlight_on(self) -> None:
        self.backlight = True
        self._write_byte(0x00)

    def backlight_off(self) -> None:
        self.backlight = False
        self._write_byte(0x00)

    def set_backlight(self, state: bool) -> None:
        if state:
            self.backlight_on()
        else:
            self.backlight_off()

    # =========================
    # Escritura cómoda
    # =========================
    def clear_line(self, row: int) -> None:
        self.write_line("", row)

    def write_line(self, text: str, row: int = 0, align: str = "left") -> None:
        text = self._sanitize(text)

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

    def center(self, text: str, row: int = 0) -> None:
        self.write_line(text, row=row, align="center")

    def message(self, line1: str = "", line2: str = "") -> None:
        self.write_line(line1, 0, "left")
        if self.rows > 1:
            self.write_line(line2, 1, "left")

    def message_centered(self, line1: str = "", line2: str = "") -> None:
        self.write_line(line1, 0, "center")
        if self.rows > 1:
            self.write_line(line2, 1, "center")

    # =========================
    # Textos largos
    # =========================
    def scroll_text(self, text: str, row: int = 0, delay_ms: int = 250, loops: int = 1, padding: int = 4) -> None:
        text = self._sanitize(text)

        if len(text) <= self.cols:
            self.write_line(text, row)
            return

        pad = " " * padding
        buf = text + pad

        for _ in range(loops):
            for i in range(len(buf) - self.cols + 1):
                self.write_line(buf[i:i + self.cols], row)
                time.sleep_ms(delay_ms)

    # =========================
    # Utilidades
    # =========================
    def splash(self, title: str = "", subtitle: str = "", delay_s: float = 1.5) -> None:
        self.clear()
        self.message_centered(title, subtitle)
        time.sleep(delay_s)

    def test(self) -> None:
        self.clear()
        self.message("LCD OK", "Probando...")
        time.sleep(1)
        self.clear()
        self.write_line("1234567890123456", 0)
        if self.rows > 1:
            self.write_line("abcdefghijklmnop", 1)
        time.sleep(1)
        self.clear()