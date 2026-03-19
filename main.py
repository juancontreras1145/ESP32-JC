from machine import Pin, I2C
import dht
import time
import lcd_api
import i2c_lcd

# Configuración I2C de tu LCD
i2c = I2C(0, sda=Pin(8), scl=Pin(9), freq=400000)

# Dirección detectada antes
I2C_ADDR = 39

# Tamaño LCD
lcd = i2c_lcd.I2cLcd(i2c, I2C_ADDR, 2, 16)

# Sensor DHT11 en GPIO4
sensor = dht.DHT11(Pin(4))

lcd.clear()
lcd.putstr("Sensor listo")
time.sleep(2)

while True:

    try:
        sensor.measure()

        temp = sensor.temperature()
        hum = sensor.humidity()

        lcd.clear()

        lcd.move_to(0,0)
        lcd.putstr("Temp: {} C".format(temp))

        lcd.move_to(0,1)
        lcd.putstr("Hum: {} %".format(hum))

        print("Temp:", temp)
        print("Hum:", hum)

    except Exception as e:

        lcd.clear()
        lcd.putstr("Error sensor")
        print("Error:", e)

    time.sleep(3)