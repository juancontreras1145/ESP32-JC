
import math

def dew_point(temp, hum):
    a = 17.27
    b = 237.7
    alpha = ((a*temp)/(b+temp))+math.log(hum/100.0)
    return (b*alpha)/(a-alpha)

def comfort(temp,hum):
    if temp is None:
        return "Sin datos"
    if 20 <= temp <= 26 and 40 <= hum <= 60:
        return "Bueno"
    if 18 <= temp <= 28:
        return "Regular"
    return "Malo"
