from machine import Pin, I2C
import dht
import time
import lcd_api
import i2c_lcd

# LCD
i2c = I2C(0, sda=Pin(8), scl=Pin(9), freq=400000)
lcd = i2c_lcd.I2cLcd(i2c, 39, 2, 16)

# Sensor DHT22
sensor = dht.DHT22(Pin(4))

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
        print(e)

    time.sleep(3)