import json
import os

OUTPUT_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "dispositivos_i2c.json")
)

def detectar():
    # Simulación de dispositivos I2C
    dispositivos = [
        {"direccion": "0x27", "tipo": "LCD I2C"},
        {"direccion": "0x68", "tipo": "RTC DS3231"}
    ]

    guardar_json(dispositivos)
    return dispositivos

def guardar_json(data):
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)