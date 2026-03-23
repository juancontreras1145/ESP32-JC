
import urequests

data_ext = {}

def fetch_weather_outside(lat, lon):
    global data_ext
    try:
        url = "https://api.open-meteo.com/v1/forecast?latitude={}&longitude={}&current_weather=true".format(lat,lon)
        r = urequests.get(url)
        data_ext = r.json()
        r.close()
    except Exception as e:
        print("weather error:", e)

def get_weather():
    return data_ext
