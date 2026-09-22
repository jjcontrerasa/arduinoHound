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
HEADER_HEIGHT = 100
FOOTER_HEIGHT = 60
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
ICON_PATH = ASSETS_DIR / "IconoAHound.ico"
TEXTO_DESARROLLADORES = (
    "Instituto Politécnico Nacional - Escuela Superior de Ingeniería Mecánica y Eléctrica, Unidad Zacatenco\n"
    "Software desarrollado por: Juan José Contreras Arteaga\n"
    "Tesis de Maestría en Ingeniería en Sistemas\n"
    "Aplicación en la competencia Hidrochallenge, organizada por el IPN y el Centro de Desarrollo Aeroespacial (CDA)\n"
    "para la competencia Hidrochallenge 2026"
)
LOGO_WIDTH = 70
LOGO_GAP = 60
LOGO_MARGEN_DERECHO = 40
LOGOS_HEADER = ["ipn_logo.png", "esime_logo.png", "HC26_logo.png"]

# ---------------- MAIN WINDOW ----------------
root = tk.Tk()
root.title(TITLE)
root.configure(bg=BG_COLOR)
root.state("zoomed")

if ICON_PATH.exists():
    try:
        root.iconbitmap(str(ICON_PATH))
    except Exception:
        pass


def _activar_modo_oscuro():
    """Fuerza la barra de titulo oscura en Windows 10/11 (no falla si no aplica)."""
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        valor = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(valor), ctypes.sizeof(valor))
    except Exception:
        pass


root.after(10, _activar_modo_oscuro)

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
        logo_img = ImageTk.PhotoImage(Image.open(ICON_PATH).resize((90, 90)))
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
header_der.pack(side="right", fill="y", pady=0)

if ImageTk:
    ultimo_indice = len(LOGOS_HEADER) - 1
    for indice, nombre_archivo in enumerate(LOGOS_HEADER):
        ruta_logo = ASSETS_DIR / nombre_archivo
        if not ruta_logo.exists():
            continue
        try:
            imagen = Image.open(ruta_logo)
            alto_nuevo = int(imagen.height * (LOGO_WIDTH / imagen.width))
            logo_img = ImageTk.PhotoImage(imagen.resize((LOGO_WIDTH, alto_nuevo)))
            # Separación de 60px entre logos; el último conserva 40px de margen derecho.
            margen_derecho = LOGO_MARGEN_DERECHO if indice == ultimo_indice else LOGO_GAP
            logo_label = tk.Label(header_der, image=logo_img, bg=BG_COLOR)
            logo_label.image = logo_img
            logo_label.pack(side="left", padx=(0, margen_derecho), pady=0)
        except Exception:
            pass

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

tk.Label(
    frame_footer,
    text=TEXTO_DESARROLLADORES,
    fg="white", bg=BG_COLOR, font=("Arial", 5), justify="center"
).pack(expand=True)

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