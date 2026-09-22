import hashlib
import json
import sqlite3
from urllib.error import URLError
from urllib.request import Request, urlopen

from .rutas import resource_path, user_data_path


BOARDS_SQL_FILE = resource_path("data", "boards.sql")
BOARDS_JSON_FILE = user_data_path("boards.json")
BOARDS_SQL_CACHE = user_data_path("boards.sql")
BOARDS_SQL_HASH = user_data_path("boards.sql.sha256")
BOARDS_SQL_URL = (
    "https://raw.githubusercontent.com/jjcontrerasa/BD_ArduinoHound/"
    "main/boards.sql"
)
_CATALOGO_SINCRONIZADO = False
PLACAS_FILE = user_data_path("placas.json")
I2C_FILE = user_data_path("dispositivos_i2c.json")
PUERTOS_FILE = user_data_path("puertos.json")


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


def _leer_texto(path):
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _boards_desde_sql(script):
    with sqlite3.connect(":memory:") as connection:
        connection.executescript(script)
        filas = connection.execute(
            "SELECT key, name, mcu, fqbn, alternate_fqbn FROM boards ORDER BY rowid"
        ).fetchall()
    return {
        key: {
            "name": name,
            "mcu": mcu,
            "fqbn": fqbn,
            **({"alternate_fqbn": alternate_fqbn} if alternate_fqbn else {}),
        }
        for key, name, mcu, fqbn, alternate_fqbn in filas
    }


def _actualizar_catalogo_remoto():
    try:
        request = Request(
            BOARDS_SQL_URL,
            headers={"User-Agent": "ArduinoHound/1.0"},
        )
        with urlopen(request, timeout=5) as response:
            remoto = response.read().decode("utf-8")
    except (OSError, URLError, UnicodeDecodeError):
        return False

    hash_remoto = hashlib.sha256(remoto.encode("utf-8")).hexdigest()
    if _leer_texto(BOARDS_SQL_HASH).strip() == hash_remoto and BOARDS_JSON_FILE.exists():
        return False

    try:
        boards = _boards_desde_sql(remoto)
        if not boards:
            return False
        BOARDS_SQL_CACHE.write_text(remoto, encoding="utf-8")
        BOARDS_SQL_HASH.write_text(hash_remoto, encoding="ascii")
        guardar_json(BOARDS_JSON_FILE, boards)
        return True
    except (OSError, sqlite3.Error):
        return False


def _crear_json_desde_respaldo():
    if BOARDS_JSON_FILE.exists():
        return
    script = _leer_texto(BOARDS_SQL_CACHE) or _leer_texto(BOARDS_SQL_FILE)
    if not script:
        return
    try:
        boards = _boards_desde_sql(script)
        if boards:
            guardar_json(BOARDS_JSON_FILE, boards)
    except (sqlite3.Error, OSError):
        pass


def cargar_boards():
    global _CATALOGO_SINCRONIZADO
    if not _CATALOGO_SINCRONIZADO:
        _actualizar_catalogo_remoto()
        _CATALOGO_SINCRONIZADO = True
    _crear_json_desde_respaldo()
    return cargar_json(BOARDS_JSON_FILE, {})


def cargar_placas():
    return cargar_json(PLACAS_FILE, {})


def guardar_placa(nombre, fqbn):
    placas = cargar_placas()
    placas[nombre] = fqbn
    guardar_json(PLACAS_FILE, placas)


def cargar_puertos_guardados():
    return cargar_json(PUERTOS_FILE, {})


def guardar_puerto_default(puerto):
    datos = cargar_puertos_guardados()
    datos["default"] = puerto
    guardar_json(PUERTOS_FILE, datos)


def obtener_puerto_default():
    datos = cargar_puertos_guardados()
    return datos.get("default", "")
