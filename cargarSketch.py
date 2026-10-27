"""Lanzador compatible del panel de carga de sketches.

La aplicación principal debe iniciarse con main.py. Este archivo se conserva
para compatibilidad con el uso histórico: python cargarSketch.py
"""

import tkinter as tk

from modules.cargarSketch import *
from modules.rutas import configurar_ventana, titulo


if __name__ == "__main__":
    root = tk.Tk()
    root.title(titulo("Cargar Sketch en Arduino / ESP32"))
    configurar_ventana(root)
    root.geometry("370x720")
    crear_panel(root)
    root.mainloop()
