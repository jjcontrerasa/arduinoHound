"""Genera data/manifiesto.json con el SHA-256 de cada catalogo publico.

Ejecutar antes de publicar los catalogos: python generar_manifiesto.py
"""
import hashlib
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
EXCLUIR = {"manifiesto.json", "firmas_avr.mysql.sql"}


def hash_normalizado(ruta):
    texto = ruta.read_text(encoding="utf-8").replace("\r\n", "\n")
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


archivos = {
    ruta.name: hash_normalizado(ruta)
    for ruta in sorted(DATA.iterdir())
    if ruta.suffix in {".json", ".sql"} and ruta.name not in EXCLUIR
}
(DATA / "manifiesto.json").write_text(
    json.dumps({"archivos": archivos}, indent=4, ensure_ascii=False) + "\n", encoding="utf-8"
)
print("\n".join(f"{n}  {h}" for n, h in archivos.items()))
