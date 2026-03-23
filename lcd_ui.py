
from machine import I2C, Pin
from config import LCD_SDA, LCD_SCL, LCD_ADDR
from utils import safe_str

lcd = None

def init_lcd():
    global lcd
    try:
        from lcd import LCD
        i2c = I2C(0, sda=Pin(LCD_SDA), scl=Pin(LCD_SCL))
        lcd = LCD(i2c, LCD_ADDR)
    except:
        lcd = None

def lcd_msg(a="",b=""):
    try:
        if lcd:
            lcd.message(safe_str(a,16), safe_str(b,16))
    except:
        pass
