"""Gestiona el versionado de los JSON de la app en una carpeta git publica local."""
import hashlib
import shutil
import subprocess
from datetime import datetime

from .persistencia import cargar_json, guardar_json
from .rutas import PROJECT_PATH, user_data_path

# Carpeta local (aun no es repo git, se inicializa sola en el primer uso).
# Cambia esta ruta si quieres publicar las versiones en otro sitio.
PUBLIC_REPO_PATH = PROJECT_PATH.parent / "ArduinoHound_BD_Publica"

ESTADO_FILE = user_data_path(".estado_bbdd_publica.json")

IGNORAR_DIRS = {"packages", "staging", "tmp", "core", "Nueva carpeta", "__pycache__", ".git"}


def _listar_json_repositorio():
    archivos = []
    for ruta in PROJECT_PATH.rglob("*.json"):
        partes = ruta.relative_to(PROJECT_PATH).parts[:-1]
        if any(parte in IGNORAR_DIRS for parte in partes):
            continue
        archivos.append(ruta)
    return sorted(archivos)


def _firma_archivos(archivos):
    partes = []
    for ruta in archivos:
        try:
            estado = ruta.stat()
            partes.append(f"{ruta.relative_to(PROJECT_PATH)}:{estado.st_size}:{int(estado.st_mtime)}")
        except OSError:
            partes.append(f"{ruta}:faltante")
    return hashlib.sha256("|".join(partes).encode("utf-8")).hexdigest()


def hay_cambios_pendientes():
    archivos = _listar_json_repositorio()
    if not archivos:
        return False
    firma_actual = _firma_archivos(archivos)
    estado = cargar_json(ESTADO_FILE, {})
    return estado.get("firma") != firma_actual


def publicar_nueva_version():
    """Copia los JSON del proyecto a una nueva subcarpeta versionada y hace commit en PUBLIC_REPO_PATH."""
    archivos = _listar_json_repositorio()
    if not archivos:
        return False, "No se encontraron archivos JSON para versionar."

    try:
        PUBLIC_REPO_PATH.mkdir(parents=True, exist_ok=True)
        if not (PUBLIC_REPO_PATH / ".git").exists():
            init = subprocess.run(
                ["git", "init"], cwd=PUBLIC_REPO_PATH, capture_output=True, text=True, check=False
            )
            if init.returncode != 0:
                return False, f"No se pudo inicializar el repositorio git: {init.stderr.strip()}"

        marca_tiempo = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        carpeta_version = PUBLIC_REPO_PATH / "versions" / marca_tiempo
        carpeta_version.mkdir(parents=True, exist_ok=True)

        for ruta in archivos:
            destino = carpeta_version / ruta.relative_to(PROJECT_PATH)
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ruta, destino)

        subprocess.run(["git", "add", "."], cwd=PUBLIC_REPO_PATH, capture_output=True, text=True, check=False)
        commit = subprocess.run(
            ["git", "commit", "-m", f"Actualizacion BBDD {marca_tiempo}"],
            cwd=PUBLIC_REPO_PATH, capture_output=True, text=True, check=False,
        )
        salida_commit = (commit.stdout + commit.stderr).lower()
        if commit.returncode != 0 and "nothing to commit" not in salida_commit and "nada para hacer" not in salida_commit:
            return False, f"No se pudo crear el commit: {commit.stderr.strip()}"
    except OSError as error:
        return False, f"Error al publicar la nueva version: {error}"

    guardar_json(ESTADO_FILE, {"firma": _firma_archivos(archivos), "fecha": marca_tiempo})
    return True, f"Nueva version guardada en {carpeta_version}"
