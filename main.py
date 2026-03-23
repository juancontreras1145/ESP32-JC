
import gc,time

from config import VERSION, LAT, LON, INTERVALO_GUARDADO
from utils import now_epoch
from storage import append_log, ensure_csv, append_csv
from sensor_interior import init_sensor, read_sensor, get_values
from weather_ext import fetch_weather_outside
from lcd_ui import init_lcd, lcd_msg
from web_routes import init_server, handle_web

append_log("Inicio " + VERSION)

gc.collect()

init_lcd()
lcd_msg("ESP32 JC","Iniciando")

init_sensor()
ensure_csv()

init_server()

ultimo = now_epoch()

while True:

    handle_web()

    ahora = now_epoch()

    if ahora - ultimo >= INTERVALO_GUARDADO:

        if read_sensor():
            t,h = get_values()
            append_csv(ahora,t,h)
            lcd_msg("Temp {}C".format(t),"Hum {}%".format(h))

        fetch_weather_outside(LAT,LON)

        ultimo = ahora

    time.sleep(0.2)
