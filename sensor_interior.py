
import dht, machine, time
from config import DHT_PIN

sensor = None
temp = None
hum = None

def init_sensor():
    global sensor
    sensor = dht.DHT22(machine.Pin(DHT_PIN))

def read_sensor():
    global temp, hum
    try:
        sensor.measure()
        temp = sensor.temperature()
        hum = sensor.humidity()
        return True
    except Exception as e:
        print("sensor error:", e)
        return False

def get_values():
    return temp, hum
