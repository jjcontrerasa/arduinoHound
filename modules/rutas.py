import os
import sys
import tkinter as tk
from tkinter import ttk
from pathlib import Path


APP_NAME = "Arduino Hound V3"
BG_COLOR = "black"
FG_COLOR = "white"
ACCENT_COLOR = "OliveDrab"


def titulo(subtitulo=None):
    return f"{APP_NAME} - {subtitulo}" if subtitulo else APP_NAME


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
    ventana.configure(bg=BG_COLOR)
    aplicar_tema(ventana)
    if ICON_PATH.exists():
        try:
            ventana.iconbitmap(str(ICON_PATH))
        except tk.TclError:
            pass
    ventana.after(10, _activar_barra_titulo_oscura, ventana)


def aplicar_tema(ventana):
    """Aplica el fondo común y los estilos ttk oscuros a la aplicación."""
    ventana.configure(bg=BG_COLOR)
    estilo = ttk.Style(ventana)
    try:
        estilo.theme_use("clam")
    except tk.TclError:
        pass

    estilo.configure("TFrame", background=BG_COLOR)
    estilo.configure("TLabel", background=BG_COLOR, foreground=FG_COLOR)
    estilo.configure(
        "TButton",
        background=BG_COLOR,
        foreground=FG_COLOR,
        bordercolor=ACCENT_COLOR,
        focuscolor=ACCENT_COLOR,
        padding=(8, 4),
    )
    estilo.map(
        "TButton",
        background=[("active", "#202020"), ("disabled", "#151515")],
        foreground=[("disabled", "#777777")],
    )
    estilo.configure(
        "TEntry",
        fieldbackground="#111111",
        foreground=FG_COLOR,
        insertcolor=FG_COLOR,
    )
    estilo.configure(
        "TCombobox",
        fieldbackground="#111111",
        background=BG_COLOR,
        foreground=FG_COLOR,
        arrowcolor=FG_COLOR,
    )
    estilo.map(
        "TCombobox",
        fieldbackground=[("readonly", "#111111"), ("disabled", "#151515")],
        foreground=[("readonly", FG_COLOR), ("disabled", "#777777")],
        selectbackground=[("readonly", "#111111")],
        selectforeground=[("readonly", FG_COLOR)],
    )
    estilo.configure(
        "Treeview",
        background=BG_COLOR,
        foreground=FG_COLOR,
        fieldbackground=BG_COLOR,
        borderwidth=0,
    )
    estilo.configure(
        "Treeview.Heading",
        background="#181818",
        foreground=FG_COLOR,
        borderwidth=0,
    )
    estilo.map("Treeview.Heading", background=[("active", "#242424")])
    estilo.configure("TNotebook", background=BG_COLOR, borderwidth=0)
    estilo.configure(
        "TNotebook.Tab",
        background="#181818",
        foreground=FG_COLOR,
        padding=(10, 5),
    )
    estilo.map(
        "TNotebook.Tab",
        background=[("selected", "#303030"), ("active", "#242424")],
        foreground=[("selected", FG_COLOR)],
    )
    estilo.configure("TCheckbutton", background=BG_COLOR, foreground=FG_COLOR)
    estilo.map("TCheckbutton", background=[("active", BG_COLOR)])
    estilo.configure(
        "Horizontal.TProgressbar",
        background=ACCENT_COLOR,
        troughcolor="#202020",
        bordercolor="#202020",
    )


def _activar_barra_titulo_oscura(ventana):
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
    except (AttributeError, OSError, tk.TclError):
        pass


def crear_ventana(parent, titulo_ventana=None, modal=False):
    """Crea una ventana secundaria con el tema y el comportamiento comunes."""
    parent = parent.winfo_toplevel()
    ventana = tk.Toplevel(parent)
    if titulo_ventana:
        ventana.title(titulo_ventana)
    configurar_ventana(ventana)
    ventana.transient(parent)
    if modal:
        ventana.grab_set()
    return ventana


def crear_boton(parent, texto, comando=None, **opciones):
    """Construye un botón clásico con la paleta común, permitiendo excepciones."""
    estilo = {
        "bg": BG_COLOR,
        "fg": FG_COLOR,
        "activebackground": "#202020",
        "activeforeground": FG_COLOR,
        "highlightbackground": ACCENT_COLOR,
        "highlightthickness": 1,
        "relief": "flat",
        "font": ("Arial", 10),
        "cursor": "hand2",
    }
    estilo.update(opciones)
    return tk.Button(parent, text=texto, command=comando, **estilo)


def _mostrar_dialogo(titulo_dialogo, mensaje, parent=None, tipo="info", pregunta=False):
    parent = parent or tk._default_root
    if parent is None:
        raise RuntimeError("No hay una ventana principal para mostrar el diálogo.")
    parent = parent.winfo_toplevel()

    ventana = crear_ventana(parent, titulo_dialogo)
    ventana.resizable(False, False)
    respuesta = [False]
    contenido = tk.Frame(ventana, bg=BG_COLOR)
    contenido.pack(padx=24, pady=20)

    color = {"error": "#ff6b6b", "warning": "#ffd166", "info": "#70b7ff"}[tipo]
    tk.Label(
        contenido,
        text="!" if tipo in ("error", "warning") else "i",
        bg=BG_COLOR,
        fg=color,
        font=("Arial", 18, "bold"),
    ).pack(pady=(0, 8))
    tk.Label(
        contenido,
        text=mensaje,
        bg=BG_COLOR,
        fg=FG_COLOR,
        justify="center",
        wraplength=460,
    ).pack(fill="x")

    botones = tk.Frame(contenido, bg=BG_COLOR)
    botones.pack(pady=(18, 0))

    def cerrar(valor=False):
        respuesta[0] = valor
        ventana.destroy()

    if pregunta:
        aceptar = crear_boton(botones, "Sí", lambda: cerrar(True))
        aceptar.pack(side="left", padx=5)
        crear_boton(botones, "No", lambda: cerrar(False)).pack(side="left", padx=5)
        aceptar.focus_set()
        ventana.bind("<Escape>", lambda _event: cerrar(False))
    else:
        aceptar = crear_boton(botones, "Aceptar", lambda: cerrar(True))
        aceptar.pack()
        aceptar.focus_set()
        ventana.bind("<Escape>", lambda _event: cerrar(True))

    ventana.protocol("WM_DELETE_WINDOW", lambda: cerrar(False))
    ventana.update_idletasks()
    parent.update_idletasks()
    x = parent.winfo_rootx() + (parent.winfo_width() - ventana.winfo_width()) // 2
    y = parent.winfo_rooty() + (parent.winfo_height() - ventana.winfo_height()) // 2
    ventana.geometry(f"+{max(0, x)}+{max(0, y)}")
    ventana.grab_set()
    ventana.wait_window()
    return respuesta[0]


class _ThemedMessageBox:
    def showinfo(self, title, message, **options):
        _mostrar_dialogo(title, message, parent=options.get("parent"), tipo="info")
        return "ok"

    def showerror(self, title, message, **options):
        _mostrar_dialogo(title, message, parent=options.get("parent"), tipo="error")
        return "ok"

    def showwarning(self, title, message, **options):
        _mostrar_dialogo(title, message, parent=options.get("parent"), tipo="warning")
        return "ok"

    def askyesno(self, title, message, **options):
        return _mostrar_dialogo(
            title, message, parent=options.get("parent"), tipo="info", pregunta=True
        )


messagebox = _ThemedMessageBox()
