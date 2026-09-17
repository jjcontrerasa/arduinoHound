import tkinter as tk
from pathlib import Path

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

# Importar módulos desde la carpeta modules
import modules.cargarSketch as cargarSketch
import modules.puertos as puertos
import modules.rastrear as rastrear


# ---------------- CONFIG ----------------
BG_COLOR = "black"
FRAME_BORDER_COLOR = "white"
COLOR_AZUL = "#3399FF"
TITLE = "ArduinoHound V2"
HEADER_HEIGHT = 90
FOOTER_HEIGHT = 45
ICON_PATH = Path(__file__).resolve().parent / "assets" / "IconoAHound.ico"

# ---------------- MAIN WINDOW ----------------
root = tk.Tk()
root.title(TITLE)
root.configure(bg=BG_COLOR)
root.state("zoomed")

# Tamaño inicial
root.geometry("1200x720")

# Grid 3 columnas
root.columnconfigure(0, weight=1)
root.columnconfigure(1, weight=1)
root.columnconfigure(2, weight=1)
root.rowconfigure(0, weight=0)
root.rowconfigure(1, weight=1)
root.rowconfigure(2, weight=0)

# ---------------- ENCABEZADO ----------------
frame_header = tk.Frame(root, bg=BG_COLOR, height=HEADER_HEIGHT)
frame_header.grid(row=0, column=0, columnspan=3, sticky="ew", padx=15, pady=0)
frame_header.grid_propagate(False)  # conserva el alto fijo aunque no tenga contenido

header_izq = tk.Frame(frame_header, bg=BG_COLOR)
header_izq.pack(side="left", fill="y", padx=10)

if ImageTk and ICON_PATH.exists():
    try:
        logo_img = ImageTk.PhotoImage(Image.open(ICON_PATH).resize((48, 48)))
        logo_label = tk.Label(header_izq, image=logo_img, bg=BG_COLOR)
        logo_label.image = logo_img  # evita que el garbage collector lo elimine
        logo_label.pack(side="left", padx=(0, 10))
    except Exception:
        pass

tk.Label(
    header_izq, text="Arduino Hound", fg=COLOR_AZUL, bg=BG_COLOR,
    font=("Arial", 18, "bold")
).pack(side="left")

header_der = tk.Frame(frame_header, bg=BG_COLOR)
header_der.pack(side="right", fill="y", padx=10)
tk.Label(
    header_der,
    text="Desarrollado en ESIME Zacatenco del IPN en cooperación con el CDA\npara la competencia Hidrochallenge 2026",
    fg="white", bg=BG_COLOR, font=("Arial", 10), justify="right"
).pack(side="right")

# ---------------- PANEL IZQUIERDO ----------------
frame_izq = tk.Frame(
    root,
    bg=BG_COLOR,
    highlightbackground=FRAME_BORDER_COLOR,
    highlightthickness=1
)
frame_izq.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

puertos.crear_panel(frame_izq)

# ---------------- PANEL CENTRAL ----------------
frame_centro = tk.Frame(
    root,
    bg=BG_COLOR,
    highlightbackground=FRAME_BORDER_COLOR,
    highlightthickness=1
)
frame_centro.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)

cargarSketch.crear_panel(frame_centro)

# ---------------- PANEL DERECHO ----------------
frame_der = tk.Frame(
    root,
    bg=BG_COLOR,
    highlightbackground=FRAME_BORDER_COLOR,
    highlightthickness=1
)
frame_der.grid(row=1, column=2, sticky="nsew", padx=5, pady=5)

rastrear.crear_panel(frame_der)

# ---------------- PIE DE PÁGINA ----------------
frame_footer = tk.Frame(root, bg=BG_COLOR, height=FOOTER_HEIGHT)
frame_footer.grid(row=2, column=0, columnspan=3, sticky="ew", padx=15, pady=0)
frame_footer.grid_propagate(False)  # conserva el alto fijo aunque no tenga contenido

# ---------------- AJUSTE DINÁMICO ----------------
def ajustar_ventana(event):
    """
    Control simple para evitar que la ventana se haga demasiado pequeña
    """
    min_width = 900
    min_height = 600

    if root.winfo_width() < min_width:
        root.geometry(f"{min_width}x{root.winfo_height()}")

    if root.winfo_height() < min_height:
        root.geometry(f"{root.winfo_width()}x{min_height}")

root.bind("<Configure>", ajustar_ventana)

# ---------------- START ----------------
if __name__ == "__main__":
    root.mainloop()