import os
import sys
import tkinter as tk
from pathlib import Path


PROJECT_PATH = Path(__file__).resolve().parent.parent
RESOURCE_PATH = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else PROJECT_PATH

if getattr(sys, "frozen", False):
    USER_DATA_PATH = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ArduinoHound"
else:
    USER_DATA_PATH = PROJECT_PATH

USER_DATA_PATH.mkdir(parents=True, exist_ok=True)


def resource_path(*parts):
    return RESOURCE_PATH.joinpath(*parts)


ICON_PATH = resource_path("assets", "IconoAHound.ico")


def user_data_path(*parts):
    path = USER_DATA_PATH.joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def arduino_cli_path():
    return resource_path("arduino-cli.exe")


def configurar_ventana(ventana):
    ventana.configure(bg="black")
    if ICON_PATH.exists():
        try:
            ventana.iconbitmap(str(ICON_PATH))
        except tk.TclError:
            pass
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetParent(ventana.winfo_id())
        valor = ctypes.c_int(1)
        for atributo in (20, 19):
            resultado = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, atributo, ctypes.byref(valor), ctypes.sizeof(valor)
            )
            if resultado == 0:
                break
    except (AttributeError, OSError):
        pass
