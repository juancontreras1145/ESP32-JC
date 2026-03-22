
# Advanced Environmental Analysis Engine (Compact)
# Designed for ESP32 dashboards or small displays

import time
import math

def phase_of_day(hour):
    if 5 <= hour < 8:
        return "amanecer"
    elif 8 <= hour < 12:
        return "mañana"
    elif 12 <= hour < 17:
        return "tarde"
    elif 17 <= hour < 20:
        return "atardecer"
    elif 20 <= hour < 23:
        return "noche"
    else:
        return "madrugada"


# --- Base environmental states (short phrases) ---
BASE = [
"Ambiente estable",
"Clima interior OK",
"Condicion normal",
"Lectura estable",
"Microclima OK",
"Estado ambiental",
"Clima tranquilo",
"Balance interior",
"Parametros OK",
"Ambiente controlado",
"Lectura correcta",
"Clima domestico",
"Condicion neutra",
"Estado interior",
"Ambiente equilibrado"
]

TEMP = [
"Exterior mas frio",
"Exterior mas calido",
"Temp interior fresca",
"Temp interior calida",
"Dif termica alta",
"Gradiente termico",
"Balance termico",
"Cambio termico",
"Interior retiene calor",
"Interior retiene frio",
"Temp estable",
"Temp moderada"
]

HUM = [
"Humedad alta",
"Humedad baja",
"Aire seco",
"Aire humedo",
"Dif humedad",
"Humedad estable",
"Humedad moderada",
"Cambio humedad",
"Humedad interior",
"Humedad exterior"
]

VENT = [
"Ventilar recomendado",
"Ventilar breve",
"Ventilar ayuda",
"Ventilar neutro",
"Ventilar poco util",
"Aire renovado",
"Aire cargado",
"Aire estable",
"Ventilar posible",
"Ventilar leve"
]

MOLD = [
"Riesgo moho bajo",
"Riesgo moho medio",
"Riesgo moho alto"
]

COND = [
"Sin condensacion",
"Condensacion posible",
"Condensacion probable"
]

COMFORT = [
"Confort ideal",
"Confort aceptable",
"Ambiente fresco",
"Ambiente calido"
]

PHASE_MSG = {
"amanecer":[
"Amanecer fresco",
"Amanecer estable",
"Aire matinal",
"Hora de ventilar",
"Inicio del dia"
],
"mañana":[
"Manana estable",
"Clima matinal",
"Actividad diurna",
"Ambiente templado",
"Manana tranquila"
],
"tarde":[
"Tarde termica",
"Acumula calor",
"Clima diurno",
"Tarde estable",
"Ambiente activo"
],
"atardecer":[
"Transicion termica",
"Aire vespertino",
"Atardecer fresco",
"Hora de balance",
"Cambio de dia"
],
"noche":[
"Noche estable",
"Clima nocturno",
"Aire nocturno",
"Temp descendente",
"Noche tranquila"
],
"madrugada":[
"Madrugada calma",
"Aire muy estable",
"Temp minima",
"Silencio termico",
"Madrugada fria"
]
}


# --- helper calculations ---

def dew_point(temp, hum):
    a = 17.27
    b = 237.7
    alpha = ((a * temp) / (b + temp)) + math.log(hum/100.0)
    return (b * alpha) / (a - alpha)


def absolute_humidity(temp, hum):
    return 6.112 * math.exp((17.67 * temp) / (temp + 243.5)) * hum * 2.1674 / (273.15 + temp)


# --- main analysis ---

def environmental_analysis(temp_in, hum_in, temp_out, hum_out):

    hour = time.localtime()[3]
    phase = phase_of_day(hour)

    messages = []

    # temperature logic
    if temp_out < temp_in - 2:
        messages.append("Exterior mas frio")
    if temp_out > temp_in + 2:
        messages.append("Exterior mas calido")

    if abs(temp_out-temp_in) > 5:
        messages.append("Dif termica alta")

    if temp_in < 18:
        messages.append("Interior fresco")
    elif temp_in > 26:
        messages.append("Interior calido")

    # humidity logic
    if hum_in > 70:
        messages.append("Humedad alta")
    elif hum_in < 35:
        messages.append("Aire seco")

    if abs(hum_out-hum_in) > 15:
        messages.append("Dif humedad")

    # ventilation logic
    if temp_out < temp_in and hum_out <= hum_in:
        messages.append("Ventilar ayuda")
    elif temp_out > temp_in and hum_out >= hum_in:
        messages.append("Ventilar poco util")

    # dew point / condensation
    dp = dew_point(temp_in, hum_in)

    if temp_in - dp > 5:
        messages.append("Sin condensacion")
    elif temp_in - dp > 2:
        messages.append("Condensacion posible")
    else:
        messages.append("Condensacion probable")

    # mold risk
    if hum_in > 75:
        messages.append("Riesgo moho alto")
    elif hum_in > 60:
        messages.append("Riesgo moho medio")
    else:
        messages.append("Riesgo moho bajo")

    # comfort index
    if 20 <= temp_in <= 24 and 40 <= hum_in <= 60:
        messages.append("Confort ideal")
    elif 18 <= temp_in <= 26:
        messages.append("Confort aceptable")
    else:
        messages.append("Ambiente fresco" if temp_in < 20 else "Ambiente calido")

    # phase message
    phase_list = PHASE_MSG.get(phase, [])
    if phase_list:
        messages.append(phase_list[hour % len(phase_list)])

    # baseline message
    messages.append(BASE[hour % len(BASE)])

    return messages


# Example usage
if __name__ == "__main__":

    # Example sensor values
    temp_in = 22
    hum_in = 60
    temp_out = 18
    hum_out = 70

    analysis = environmental_analysis(temp_in, hum_in, temp_out, hum_out)

    print("Analisis ambiental:")
    for a in analysis[:4]:   # show only first few (for small screens)
        print("-", a)
