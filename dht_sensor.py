from machine import Pin
import dht

class DHTReader:
    def __init__(self, pin=4):
        self.sensor = dht.DHT22(Pin(pin))

    def read(self):
        self.sensor.measure()
        t = round(self.sensor.temperature(), 1)
        h = round(self.sensor.humidity(), 1)
        return t, h
