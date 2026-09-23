import tkinter as tk
from pathlib import Path
from tkinter import messagebox

try:
    from PIL import Image, ImageEnhance, ImageTk
except ImportError:
    Image = None
    ImageEnhance = None
    ImageTk = None

# Importar módulos desde la carpeta modules
import modules.bbdd_publica as bbdd_publica
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
    "Aplicación en la competencia Hidrochallenge, organizada por el IPN y el Centro de Desarrollo Aeroespacial (CDA)"
)
LOGO_WIDTH = 70
LOGO_GAP = 60
LOGOS_HEADER = ["ipn_logo.png", "esime_logo.png", "HC26_logo.png"]
TAMANIO_ICONO_ACCION = 40
ICONO_ACTUALIZAR_BBDD_PATH = ASSETS_DIR / "ico_ActualizarBBDD.png"
ICONO_SALIR_PATH = ASSETS_DIR / "ico_Salir.png"
INTERVALO_REVISION_BBDD_MS = 4000

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

# Columnas laterales con el mismo peso para que la columna central quede centrada.
frame_header.grid_rowconfigure(0, weight=1)
frame_header.grid_columnconfigure(0, weight=1)
frame_header.grid_columnconfigure(1, weight=0)
frame_header.grid_columnconfigure(2, weight=1)

header_izq = tk.Frame(frame_header, bg=BG_COLOR)
header_izq.grid(row=0, column=0, sticky="w", padx=10)

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

# Los tres logos institucionales quedan centrados en el encabezado, en el mismo orden.
header_centro = tk.Frame(frame_header, bg=BG_COLOR)
header_centro.grid(row=0, column=1)

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
            margen_derecho = 0 if indice == ultimo_indice else LOGO_GAP
            logo_label = tk.Label(header_centro, image=logo_img, bg=BG_COLOR)
            logo_label.image = logo_img
            logo_label.pack(side="left", padx=(0, margen_derecho), pady=0)
        except Exception:
            pass

header_der = tk.Frame(frame_header, bg=BG_COLOR)
header_der.grid(row=0, column=2, sticky="e", padx=10)


def _generar_variantes_icono(ruta, tamanio):
    """Devuelve (imagen_normal, imagen_atenuada) o (None, None) si no se puede cargar."""
    if not (ImageTk and ruta.exists()):
        return None, None
    try:
        base = Image.open(ruta).convert("RGBA").resize((tamanio, tamanio), Image.LANCZOS)
        normal = ImageTk.PhotoImage(base)
        atenuada = ImageEnhance.Brightness(base).enhance(0.35) if ImageEnhance else base
        deshabilitada = ImageTk.PhotoImage(atenuada)
        return normal, deshabilitada
    except Exception:
        return None, None


icono_actualizar_normal, icono_actualizar_deshabilitado = _generar_variantes_icono(
    ICONO_ACTUALIZAR_BBDD_PATH, TAMANIO_ICONO_ACCION
)
icono_salir_normal, _icono_salir_deshabilitado = _generar_variantes_icono(
    ICONO_SALIR_PATH, TAMANIO_ICONO_ACCION
)

boton_actualizar_bbdd = None


def _revisar_estado_bbdd():
    """Habilita/deshabilita el icono de Actualizar BBDD según haya cambios pendientes."""
    if boton_actualizar_bbdd is not None:
        pendiente = bbdd_publica.hay_cambios_pendientes()
        estado_actual = str(boton_actualizar_bbdd["state"])
        if pendiente and estado_actual == "disabled":
            boton_actualizar_bbdd.config(state="normal", image=icono_actualizar_normal)
        elif not pendiente and estado_actual != "disabled":
            boton_actualizar_bbdd.config(state="disabled", image=icono_actualizar_deshabilitado)
    root.after(INTERVALO_REVISION_BBDD_MS, _revisar_estado_bbdd)


def _actualizar_bbdd():
    if boton_actualizar_bbdd is None:
        return
    boton_actualizar_bbdd.config(state="disabled")
    exito, mensaje = bbdd_publica.publicar_nueva_version()
    if not exito:
        boton_actualizar_bbdd.config(state="normal", image=icono_actualizar_normal)
        messagebox.showerror("Actualizar BBDD", mensaje)
        return
    boton_actualizar_bbdd.config(image=icono_actualizar_deshabilitado)


def _salir_aplicacion():
    for liberar in (puertos.liberar_puertos, rastrear.liberar_puertos):
        try:
            liberar()
        except Exception:
            pass
    root.quit()
    root.destroy()


if icono_actualizar_normal:
    boton_actualizar_bbdd = tk.Button(
        header_der, image=icono_actualizar_normal, bg=BG_COLOR, activebackground=BG_COLOR,
        bd=0, highlightthickness=0, relief="flat", cursor="hand2",
        command=_actualizar_bbdd,
    )
    boton_actualizar_bbdd.pack(side="left", padx=(0, 15))
    root.after(500, _revisar_estado_bbdd)

if icono_salir_normal:
    tk.Button(
        header_der, image=icono_salir_normal, bg=BG_COLOR, activebackground=BG_COLOR,
        bd=0, highlightthickness=0, relief="flat", cursor="hand2",
        command=_salir_aplicacion,
    ).pack(side="left")

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