from machine import Pin
import dht

sensor = None

def init():
    global sensor
    sensor = dht.DHT22(Pin(4))

def read():
    sensor.measure()
    return sensor.temperature(), sensor.humidity()
