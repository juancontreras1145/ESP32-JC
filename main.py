
# =========================================
# ESP32 JC Monitor v63
# (igual al v62 pero con sunrise_region mejorado)
# =========================================

import time
import socket
import network
import dht
import os
import gc
import math
import machine
import ntptime
from machine import Pin, I2C

VERSION = "ESP32 JC Monitor v63"

# --- configuración original (recortada solo en comentarios) ---

LCD_SDA = 8
LCD_SCL = 9
LCD_ADDR = 0x27

DHT_PIN = 4

CSV_FILE = "temperaturas.csv"
LOG_FILE = "main.log"

INTERVALO_GUARDADO = 600
INTERVALO_EXTERIOR = 1800
TIMEOUT_WEB = 1
REFRESCO_WEB = 12
PAUSA_LCD_BOOT = 1.2
ROTACION_LCD_SEG = 3

REINTENTOS_SENSOR = 3
DELAY_REINTENTO_SENSOR = 1

UTC_OFFSET_HORAS = -3

LAT = -33.0475
LON = -71.4425
UBICACION = "Quilpue, Valparaiso"

inicio_epoch = time.time()

temperatura_actual = None
humedad_actual = None
temperatura_prev = None
humedad_prev = None

temp_ext = None
hum_ext = None
wind_ext = None
rain_ext = None
cloud_ext = None
weather_code_ext = None

sunrise_ext = "--:--"
sunset_ext = "--:--"

# =====================================================
# NUEVA FUNCIÓN MEJORADA
# =====================================================

def sunrise_region():
    """
    Estima con mayor precisión dónde está amaneciendo ahora
    usando la hora UTC aproximada.
    Compatible con MicroPython.
    """
    try:
        t = time.gmtime()
        h = t[3] + (t[4] / 60)
    except:
        h = 0

    zonas = [
        (0, 1.5, "Pacifico central"),
        (1.5, 3, "Polinesia"),
        (3, 5, "Nueva Zelanda"),
        (5, 7, "Australia"),
        (7, 9, "Indonesia"),
        (9, 11, "China / Japon"),
        (11, 13, "India"),
        (13, 15, "Medio Oriente"),
        (15, 17, "Europa Este"),
        (17, 19, "Europa Oeste"),
        (19, 21, "Africa Oeste"),
        (21, 23, "Atlantico"),
        (23, 24, "Sudamerica")
    ]

    for a, b, name in zonas:
        if a <= h < b:
            return name

    return "Zona indeterminada"


# =====================================================
# EJEMPLO DE USO (LCD)
# =====================================================

def lcd_demo():
    region = sunrise_region()
    print("Amaneciendo ahora en:", region)


if __name__ == "__main__":
    lcd_demo()
