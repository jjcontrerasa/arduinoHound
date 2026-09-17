import json

from .rutas import resource_path, user_data_path


BOARDS_FILE = resource_path("data", "boards.json")
PLACAS_FILE = user_data_path("placas.json")
I2C_FILE = user_data_path("dispositivos_i2c.json")


def cargar_json(path, default=None):
    if not path.exists():
        return {} if default is None else default
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return {} if default is None else default


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


def cargar_boards():
    return cargar_json(BOARDS_FILE, {})


def cargar_placas():
    return cargar_json(PLACAS_FILE, {})


def guardar_placa(nombre, fqbn):
    placas = cargar_placas()
    placas[nombre] = fqbn
    guardar_json(PLACAS_FILE, placas)
