"""Prepara las dependencias necesarias para ejecutar Arduino Hound V3.

Uso desde el código fuente:
    python instalar_dependencias.py

El ejecutable distribuido no necesita Python ni pip: debe incluir arduino-cli.exe,
ArduinoHound y data dentro del paquete generado.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
REQUIRED_PYTHON_PACKAGES = {
    "serial": "pyserial>=3.5",
}
REQUIRED_RUNTIME_FILES = (
    PROJECT_ROOT / "arduino-cli.exe",
    PROJECT_ROOT / "ArduinoHound" / "ArduinoHound.ino",
    PROJECT_ROOT / "data" / "boards.sql",
    PROJECT_ROOT / "data" / "placas.json",
)


def install_python_dependencies() -> None:
    missing = [
        package
        for module, package in REQUIRED_PYTHON_PACKAGES.items()
        if importlib.util.find_spec(module) is None
    ]

    if not missing:
        print("Dependencias Python: OK")
        return

    print(f"Instalando dependencias Python: {', '.join(missing)}")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", *missing]
    )


def validate_runtime_files() -> None:
    missing = [path for path in REQUIRED_RUNTIME_FILES if not path.is_file()]
    if missing:
        formatted = "\n".join(f"- {path.relative_to(PROJECT_ROOT)}" for path in missing)
        raise FileNotFoundError(
            "Faltan recursos necesarios para Arduino Hound V3:\n" + formatted
        )
    print("Recursos Arduino: OK")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Valida dependencias y recursos sin instalar paquetes.",
    )
    args = parser.parse_args()

    validate_runtime_files()
    if not args.check_only:
        install_python_dependencies()
    else:
        missing = [
            module
            for module in REQUIRED_PYTHON_PACKAGES
            if importlib.util.find_spec(module) is None
        ]
        if missing:
            raise RuntimeError(
                "Faltan dependencias Python: " + ", ".join(missing)
            )
        print("Dependencias Python: OK")

    print("Instalación validada correctamente.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
