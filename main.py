import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

try:
    from PIL import Image, ImageEnhance, ImageTk
except ImportError:
    Image = None
    ImageEnhance = None
    ImageTk = None

def _ocultar_consolas_subprocesos():
    # Evita que cada subproceso (arduino-cli, powershell, etc.) abra una ventana CMD en Windows.
    if sys.platform != "win32":
        return
    original = subprocess.Popen

    class PopenSinConsola(original):
        def __init__(self, *args, **kwargs):
            kwargs["creationflags"] = kwargs.get("creationflags", 0) | subprocess.CREATE_NO_WINDOW
            super().__init__(*args, **kwargs)

    subprocess.Popen = PopenSinConsola


_ocultar_consolas_subprocesos()

# Importar módulos desde la carpeta modules
import modules.bbdd_publica as bbdd_publica
import modules.cargarSketch as cargarSketch
import modules.puertos as puertos
import modules.rastrear as rastrear
import modules.rf_hound as rf_hound
from modules.rutas import APP_NAME, titulo


# ---------------- CONFIG ----------------
BG_COLOR = "black"
FRAME_BORDER_COLOR = "white"
COLOR_AZUL = "#3399FF"
COLOR_RF_VERDE = "green2"
TITLE = APP_NAME
HEADER_HEIGHT = 100
FOOTER_HEIGHT = 60
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
ICON_PATH = ASSETS_DIR / "IconoAHound.ico"
ICON_RF_PATH = ASSETS_DIR / "RFHound.png"
TEXTO_DESARROLLADORES = (
    "Instituto Politécnico Nacional - Escuela Superior de Ingeniería Mecánica y Eléctrica, Unidad Zacatenco\n"
    "Software desarrollado por: Juan José Contreras Arteaga\n"
    "Tesis de Maestría en Ingeniería en Sistemas\n"
    "Aplicación en la competencia Hidrochallenge, organizada por el IPN y el Centro de Desarrollo Aeroespacial (CDA)"
)
LOGO_WIDTH = 70
LOGO_GAP = 60
LOGOS_HEADER = ["ipn_logo.png", "esime_logo.png", "HC26_logo_2.png"]
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

# Grid de la ventana principal
root.columnconfigure(0, weight=1)
root.rowconfigure(0, weight=0)  # Barra de pestañas superior
root.rowconfigure(1, weight=0)  # Encabezado
root.rowconfigure(2, weight=1)  # Área de contenido según pestaña activa
root.rowconfigure(3, weight=0)  # Pie de página

# ---------------- BARRA DE PESTAÑAS SUPERIOR ----------------
frame_tabs = tk.Frame(root, bg=BG_COLOR)
frame_tabs.grid(row=0, column=0, sticky="ew", padx=15, pady=(6, 2))

tabs_container = tk.Frame(frame_tabs, bg=BG_COLOR)
tabs_container.pack(side="left")

pestana_activa = ["arduino"]
btn_tab_arduino = None
btn_tab_rf = None
label_titulo_header = None
logo_izq_label = None
logo_arduino_img = None
logo_rf_img = None
frame_main_content = None
frame_rf_content = None


def cambiar_pestana(nombre):
    """Arduino Hound / FRHound."""
    if nombre == "arduino":
        pestana_activa[0] = "arduino"
        if frame_rf_content is not None:
            frame_rf_content.grid_remove()
        if frame_main_content is not None:
            frame_main_content.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)

        if label_titulo_header is not None:
            label_titulo_header.config(text=APP_NAME, fg=COLOR_AZUL)
        if logo_izq_label is not None and logo_arduino_img is not None:
            logo_izq_label.config(image=logo_arduino_img)
            logo_izq_label.image = logo_arduino_img

        if btn_tab_arduino is not None:
            btn_tab_arduino.config(
                bg="#142132",
                fg=COLOR_AZUL,
                highlightbackground=COLOR_AZUL,
                activebackground="#1e2f47",
                activeforeground=COLOR_AZUL,
            )
        if btn_tab_rf is not None:
            btn_tab_rf.config(
                bg="#111111",
                fg="gray65",
                highlightbackground="#333333",
                activebackground="#1e221e",
                activeforeground=COLOR_RF_VERDE,
            )
    elif nombre == "rf":
        pestana_activa[0] = "rf"
        if frame_main_content is not None:
            frame_main_content.grid_remove()
        if frame_rf_content is not None:
            frame_rf_content.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)

        if label_titulo_header is not None:
            label_titulo_header.config(text="RF Hound", fg=COLOR_RF_VERDE)
        if logo_izq_label is not None:
            imagen_rf = logo_rf_img or logo_arduino_img
            if imagen_rf is not None:
                logo_izq_label.config(image=imagen_rf)
                logo_izq_label.image = imagen_rf

        if btn_tab_arduino is not None:
            btn_tab_arduino.config(
                bg="#111111",
                fg="gray65",
                highlightbackground="#333333",
                activebackground="#1e2f47",
                activeforeground=COLOR_AZUL,
            )
        if btn_tab_rf is not None:
            btn_tab_rf.config(
                bg="#102516",
                fg=COLOR_RF_VERDE,
                highlightbackground=COLOR_RF_VERDE,
                activebackground="#14301d",
                activeforeground=COLOR_RF_VERDE,
            )


btn_tab_arduino = tk.Button(
    tabs_container,
    text=f"  {APP_NAME}  ",
    font=("Arial", 10, "bold"),
    bg="#142132",
    fg=COLOR_AZUL,
    activebackground="#1e2f47",
    activeforeground=COLOR_AZUL,
    bd=0,
    highlightthickness=1,
    highlightbackground=COLOR_AZUL,
    relief="flat",
    cursor="hand2",
    padx=16,
    pady=5,
    command=lambda: cambiar_pestana("arduino"),
)
btn_tab_arduino.pack(side="left", padx=(0, 6))

btn_tab_rf = tk.Button(
    tabs_container,
    text="  RF Hound  ",
    font=("Arial", 10, "bold"),
    bg="#111111",
    fg="gray65",
    activebackground="#1e221e",
    activeforeground=COLOR_RF_VERDE,
    bd=0,
    highlightthickness=1,
    highlightbackground="#333333",
    relief="flat",
    cursor="hand2",
    padx=16,
    pady=5,
    command=lambda: cambiar_pestana("rf"),
)
btn_tab_rf.pack(side="left", padx=0)


def _on_hover_arduino(_event):
    if pestana_activa[0] != "arduino" and btn_tab_arduino is not None:
        btn_tab_arduino.config(bg="#1a1a1a", fg="white")


def _on_leave_arduino(_event):
    if pestana_activa[0] != "arduino" and btn_tab_arduino is not None:
        btn_tab_arduino.config(bg="#111111", fg="gray65")


def _on_hover_rf(_event):
    if pestana_activa[0] != "rf" and btn_tab_rf is not None:
        btn_tab_rf.config(bg="#1a1a1a", fg="white")


def _on_leave_rf(_event):
    if pestana_activa[0] != "rf" and btn_tab_rf is not None:
        btn_tab_rf.config(bg="#111111", fg="gray65")


btn_tab_arduino.bind("<Enter>", _on_hover_arduino)
btn_tab_arduino.bind("<Leave>", _on_leave_arduino)
btn_tab_rf.bind("<Enter>", _on_hover_rf)
btn_tab_rf.bind("<Leave>", _on_leave_rf)

# ---------------- ENCABEZADO ----------------
frame_header = tk.Frame(root, bg=BG_COLOR, height=HEADER_HEIGHT)
frame_header.grid(row=1, column=0, sticky="ew", padx=15, pady=0)
frame_header.grid_propagate(False)  # conserva el alto fijo aunque no tenga contenido

# Columnas laterales con el mismo peso para que la columna central quede centrada.
frame_header.grid_rowconfigure(0, weight=1)
frame_header.grid_columnconfigure(0, weight=1)
frame_header.grid_columnconfigure(1, weight=0)
frame_header.grid_columnconfigure(2, weight=1)

header_izq = tk.Frame(frame_header, bg=BG_COLOR)
header_izq.grid(row=0, column=0, sticky="w", padx=10)

if ImageTk:
    if ICON_PATH.exists():
        try:
            logo_arduino_img = ImageTk.PhotoImage(Image.open(ICON_PATH).resize((90, 90)))
        except Exception:
            pass
    if ICON_RF_PATH.exists():
        try:
            logo_rf_img = ImageTk.PhotoImage(Image.open(ICON_RF_PATH).resize((90, 90)))
        except Exception:
            pass

imagen_inicial = logo_arduino_img or logo_rf_img
if imagen_inicial is not None:
    logo_izq_label = tk.Label(header_izq, image=imagen_inicial, bg=BG_COLOR)
    logo_izq_label.image = imagen_inicial  # evita que el garbage collector lo elimine
    logo_izq_label.pack(side="left", padx=(0, 10))

label_titulo_header = tk.Label(
    header_izq, text=APP_NAME, fg=COLOR_AZUL, bg=BG_COLOR,
    font=("Arial", 18, "bold")
)
label_titulo_header.pack(side="left")

# Los tres logos institucionales quedan centrados en el encabezado, en el mismo orden.
header_centro = tk.Frame(frame_header, bg=BG_COLOR)
header_centro.grid(row=0, column=1)

logos_institucionales_imgs = []
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
            logos_institucionales_imgs.append(logo_img)
            margen_derecho = 0 if indice == ultimo_indice else LOGO_GAP
            lbl_institucional = tk.Label(header_centro, image=logo_img, bg=BG_COLOR)
            lbl_institucional.image = logo_img
            lbl_institucional.pack(side="left", padx=(0, margen_derecho), pady=0)
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
        messagebox.showerror(titulo("Actualizar BBDD"), mensaje)
        return
    boton_actualizar_bbdd.config(image=icono_actualizar_deshabilitado)


def _salir_aplicacion():
    for liberar in (puertos.liberar_puertos, rastrear.liberar_puertos, rf_hound.liberar_recursos):
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

# ---------------- PESTAÑA 1: CONTENIDO MAIN (ARDUINO HOUND) ----------------
frame_main_content = tk.Frame(root, bg=BG_COLOR)
frame_main_content.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
frame_main_content.columnconfigure(0, weight=7)
frame_main_content.columnconfigure(1, weight=13)
frame_main_content.rowconfigure(0, weight=1)

# Panel Cargar sketch
frame_cargar_sketch = tk.Frame(
    frame_main_content,
    bg=BG_COLOR,
    highlightbackground=FRAME_BORDER_COLOR,
    highlightthickness=1,
)
frame_cargar_sketch.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

cargarSketch.crear_panel(frame_cargar_sketch)

# Panel Rastrear componentes
frame_rastrear = tk.Frame(
    frame_main_content,
    bg=BG_COLOR,
    highlightbackground=FRAME_BORDER_COLOR,
    highlightthickness=1,
)
frame_rastrear.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

rastrear.crear_panel(frame_rastrear)

# ---------------- PESTAÑA 2: CONTENIDO RF HOUND ----------------
frame_rf_content = tk.Frame(root, bg=BG_COLOR)
frame_rf_content.columnconfigure(0, weight=1)
frame_rf_content.rowconfigure(0, weight=1)

rf_hound.crear_panel(frame_rf_content)
frame_rf_content.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
frame_rf_content.grid_remove()

# ---------------- PIE DE PÁGINA ----------------
frame_footer = tk.Frame(root, bg=BG_COLOR, height=FOOTER_HEIGHT)
frame_footer.grid(row=3, column=0, sticky="ew", padx=15, pady=0)
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