# boot.py
# Ejecuta tareas básicas al iniciar el ESP32

print("BOOT iniciado")

try:
    import wifi
    wifi.connect()
except Exception as e:
    print("WiFi error:", e)

try:
    import updater
    updater.update()
except Exception as e:
    print("Updater error:", e)
