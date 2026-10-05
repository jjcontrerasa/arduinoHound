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
    "https://raw.githubusercontent.com/jjcontrerasa/arduinoHound/"
    "main/data/boards.sql"
)
_CATALOGO_SINCRONIZADO = False
PLACAS_FILE = user_data_path("placas.json")
I2C_FILE = user_data_path("dispositivos_i2c.json")
I2C_CACHE_FILE = user_data_path("dispositivos_i2c.cache.json")
I2C_HASH_FILE = user_data_path("dispositivos_i2c.sha256")
I2C_URL = (
    "https://raw.githubusercontent.com/jjcontrerasa/arduinoHound/"
    "main/data/dispositivos_i2c.json"
)
PUERTOS_FILE = user_data_path("puertos.json")
CATALOGOS_URL_BASE = (
    "https://raw.githubusercontent.com/jjcontrerasa/arduinoHound/"
    "main/data/"
)
SPI_FILE = user_data_path("dispositivos_spi.json")
FIRMAS_AVR_FILE = user_data_path("firmas_avr.json")
CATALOGO_PLACAS_FILE = user_data_path("catalogo_placas.json")
_I2C_SINCRONIZADO = False


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


def _actualizar_catalogo_i2c():
    try:
        request = Request(I2C_URL, headers={"User-Agent": "ArduinoHound/1.0"})
        with urlopen(request, timeout=5) as response:
            remoto = response.read().decode("utf-8")
        registros = json.loads(remoto)
        if not isinstance(registros, list):
            return False
    except (OSError, URLError, UnicodeDecodeError, json.JSONDecodeError):
        return False

    hash_remoto = hashlib.sha256(remoto.encode("utf-8")).hexdigest()
    if _leer_texto(I2C_HASH_FILE).strip() == hash_remoto and I2C_FILE.exists():
        return False

    try:
        I2C_CACHE_FILE.write_text(remoto, encoding="utf-8")
        I2C_HASH_FILE.write_text(hash_remoto, encoding="ascii")
        guardar_json(I2C_FILE, registros)
        return True
    except OSError:
        return False


def _crear_json_i2c_desde_respaldo():
    if I2C_FILE.exists():
        return
    respaldo = _leer_texto(I2C_CACHE_FILE) or _leer_texto(resource_path("data", "dispositivos_i2c.json"))
    if not respaldo:
        return
    try:
        registros = json.loads(respaldo)
        if isinstance(registros, list):
            guardar_json(I2C_FILE, registros)
    except (OSError, json.JSONDecodeError):
        pass


def cargar_i2c():
    global _I2C_SINCRONIZADO
    if not _I2C_SINCRONIZADO:
        _actualizar_catalogo_i2c()
        _I2C_SINCRONIZADO = True
    _crear_json_i2c_desde_respaldo()
    return cargar_json(I2C_FILE, [])


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


# Catalogos publicos de solo lectura: se descargan del repositorio, se guardan en
# la carpeta de datos del usuario y, sin red, se usa la copia incluida en data/.
_CATALOGOS_REMOTOS = {
    "dispositivos_spi.json": SPI_FILE,
    "firmas_avr.json": FIRMAS_AVR_FILE,
    "placas.json": CATALOGO_PLACAS_FILE,
}
_CATALOGOS_SINCRONIZADOS = set()
_RED_DISPONIBLE = [True]


def _sincronizar_catalogo(nombre):
    if nombre in _CATALOGOS_SINCRONIZADOS or not _RED_DISPONIBLE[0]:
        return False
    _CATALOGOS_SINCRONIZADOS.add(nombre)
    destino = _CATALOGOS_REMOTOS[nombre]
    try:
        request = Request(CATALOGOS_URL_BASE + nombre, headers={"User-Agent": "ArduinoHound/1.0"})
        with urlopen(request, timeout=3) as response:
            remoto = response.read().decode("utf-8")
        datos = json.loads(remoto)
    except (OSError, URLError, UnicodeDecodeError, json.JSONDecodeError):
        _RED_DISPONIBLE[0] = False
        return False
    if not isinstance(datos, (dict, list)) or not datos:
        return False
    try:
        guardar_json(destino, datos)
    except OSError:
        return False
    return True


def cargar_catalogo(nombre, default):
    _sincronizar_catalogo(nombre)
    destino = _CATALOGOS_REMOTOS[nombre]
    if not destino.exists():
        respaldo = cargar_json(resource_path("data", nombre), None)
        return respaldo if respaldo else default
    return cargar_json(destino, default)


def cargar_spi():
    return cargar_catalogo("dispositivos_spi.json", {"spi_devices": []})


def cargar_firmas_avr():
    return cargar_catalogo("firmas_avr.json", {})


def cargar_catalogo_placas():
    return cargar_catalogo("placas.json", {})
