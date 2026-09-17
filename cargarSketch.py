"""Lanzador compatible del panel de carga de sketches.

La aplicación principal debe iniciarse con main.py. Este archivo se conserva
para compatibilidad con el uso histórico: python cargarSketch.py
"""

import tkinter as tk

from modules.cargarSketch import *


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Cargar Sketch en Arduino")
    root.configure(bg="black")
    root.geometry("370x720")
    crear_panel(root)
    root.mainloop()
