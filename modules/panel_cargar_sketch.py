import subprocess
import threading
import shutil
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .arduino_cli import ArduinoCLI, SKETCH_PATH
from .estado_ui import BarCarga
from .persistencia import cargar_boards, guardar_placa, obtener_puerto_default, guardar_puerto_default
from .rutas import configurar_ventana


FRAME_WIDTH = 350
LIST_MAX_HEIGHT = 200
TEXT_HEIGHT = 6
DETAILS_HEIGHT = 4
COLOR_TITULO = "OliveDrab2"

arduino_boards = cargar_boards()
arduino = ArduinoCLI()
fqbn_var = None
port_var = None
placa_var = None
frame_radios = None
board_combo = None
detalles_output = None
text_output = None
barCarga = None


def _finalizar(callback=None):
    barCarga.detener()
    if callback:
        callback()


def _actualizar_progreso(valor):
    if barCarga is not None and text_output is not None:
        text_output.after(0, barCarga.actualizar, valor)


def inicializar_arduino():
    barCarga.iniciar()

    def tarea():
        try:
            text_output.insert(tk.END, "Inicializando entorno Arduino...\n")
            _actualizar_progreso(15)
            arduino.initialize()
            _actualizar_progreso(90)
            text_output.insert(tk.END, "Arduino listo\n")
        except subprocess.CalledProcessError:
            text_output.insert(
                tk.END,
                "No se pudo preparar el entorno Arduino. "
                "Comprueba la conexión a Internet y vuelve a intentarlo.\n",
            )
        except Exception:
            text_output.insert(
                tk.END,
                "No se pudo inicializar Arduino CLI. "
                "Verifica la instalación e inténtalo de nuevo.\n",
            )
        finally:
            text_output.after(0, barCarga.detener)

    threading.Thread(target=tarea, daemon=True).start()


def detectar_fqbn_automatico():
    try:
        return arduino.detect_fqbn(port_var.get())
    except Exception:
        text_output.insert(tk.END, "No se pudo consultar la placa en el puerto seleccionado.\n")
        return None


def asegurar_core_instalado(fqbn):
    arduino.ensure_core(fqbn)


def detectar_placas():
    return arduino.list_boards()


def mostrar_detalles(val, key):
    detalles_output.delete("1.0", tk.END)
    detalles_output.insert(
        tk.END,
        f"Placa: {val.get('name', key)}\nFQBN: {val['fqbn']}\nMCU: {val.get('mcu', '-')}\n",
    )


def guardar_asociacion_puerto():
    puerto = port_var.get().strip() if port_var else ""
    clave = placa_var.get().strip() if placa_var else ""
    fqbn = fqbn_var.get().strip() if fqbn_var else ""
    if not puerto or not fqbn:
        return

    guardar_placa(f"puerto_{puerto}", fqbn)
    if clave:
        guardar_placa(f"puerto_{puerto}_placa", clave)


def seleccionar_placa(val, key):
    fqbn_var.set(val["fqbn"])
    guardar_asociacion_puerto()
    mostrar_detalles(val, key)


def on_placa_seleccionada(event=None):
    key = placa_var.get()
    value = arduino_boards.get(key)
    if value:
        seleccionar_placa(value, key)
    else:
        guardado = next((k for k, v in arduino_boards.items() if v["fqbn"] == key), None)
        if guardado:
            seleccionar_placa(arduino_boards[guardado], guardado)


def mostrar_info_puerto():
    parent = text_output.winfo_toplevel()
    ventana = tk.Toplevel(parent)
    ventana.title("Información del puerto")
    configurar_ventana(ventana)
    ventana.after(10, configurar_ventana, ventana)
    ventana.configure(bg="black")
    ventana.geometry("620x544")
    ventana.minsize(520, 480)
    ventana.resizable(False, False)
    ventana.transient(parent)

    from .puertos import crear_panel as crear_panel_puertos
    from .puertos import liberar_puertos

    def salir():
        liberar_puertos()
        ventana.destroy()

    crear_panel_puertos(ventana, on_exit=salir)

    ventana.update_idletasks()
    posicion_x = (ventana.winfo_screenwidth() - ventana.winfo_width()) // 2
    posicion_y = (ventana.winfo_screenheight() - ventana.winfo_height()) // 2
    ventana.geometry(f"+{posicion_x}+{posicion_y}")
    ventana.grab_set()


def seleccionar_puerto(linea, puerto):
    port_var.set(puerto)
    fqbn_var.set("")
    placa_var.set("")
    detalles_output.delete("1.0", tk.END)
    line_lower = linea.lower()
    match_key = None
    for key in sorted(arduino_boards, key=len, reverse=True):
        if all(part in line_lower for part in key.split("_")):
            match_key = key
            break

    if match_key:
        fqbn_var.set(arduino_boards[match_key]["fqbn"])
        placa_var.set(match_key)
        guardar_asociacion_puerto()
        mostrar_detalles(arduino_boards[match_key], match_key)
        return

    board_combo["values"] = sorted(arduino_boards)
    placa_var.set("")
    fqbn_var.set("")
    detalles_output.insert(tk.END, "No se detectó un FQBN exacto para este puerto.\nSelecciona manualmente la placa Arduino disponible.\n")


def escanear_puertos():
    barCarga.iniciar()

    def tarea():
        try:
            _actualizar_progreso(5)
            salida = detectar_placas()
            _actualizar_progreso(55)
            text_output.delete("1.0", tk.END)
            text_output.insert(tk.END, "Escaneo de puertos completado.\n")
            for widget in frame_radios.winfo_children():
                widget.destroy()
            puertos = []
            for line in salida.splitlines():
                line = line.strip()
                if line and not line.startswith("Port"):
                    puerto = line.split()[0]
                    puertos.append((puerto, line))
                    tk.Radiobutton(
                        frame_radios,
                        text=line,
                        variable=port_var,
                        value=puerto,
                        bg="black",
                        fg="white",
                        selectcolor="black",
                        anchor="w",
                        command=lambda value=line, selected=puerto: seleccionar_puerto(value, selected),
                    ).pack(anchor="w", fill="x")
                    _actualizar_progreso(85)
            if puertos:
                primer_puerto, primer_linea = puertos[0]
                if primer_puerto != obtener_puerto_default():
                    guardar_puerto_default(primer_puerto)
                port_var.set(primer_puerto)
                seleccionar_puerto(primer_linea, primer_puerto)
        finally:
            text_output.after(0, barCarga.detener)

    threading.Thread(target=tarea, daemon=True).start()


def _cargar(fqbn, sketch_path):
    asegurar_core_instalado(fqbn)
    _actualizar_progreso(15)
    arduino.compile(fqbn, sketch_path)
    _actualizar_progreso(72)
    arduino.upload(port_var.get(), fqbn, sketch_path)
    _actualizar_progreso(95)


def _mostrar_confirmacion_sketch(nombre_archivo, nombre_placa):
    ventana = tk.Toplevel(text_output.winfo_toplevel())
    ventana.title("Confirmar carga de sketch")
    configurar_ventana(ventana)
    ventana.resizable(False, False)
    ventana.transient(text_output.winfo_toplevel())
    ventana.grab_set()

    respuesta = [False]
    contenido = tk.Frame(ventana, bg="black")
    contenido.pack(padx=24, pady=20)

    tk.Label(
        contenido,
        text="Se cargará el Sketch:",
        fg="white",
        bg="black",
        anchor="center",
        justify="center",
    ).pack(fill="x")
    tk.Label(
        contenido,
        text=nombre_archivo,
        fg="white",
        bg="black",
        font=("Arial", 10, "bold"),
        anchor="center",
        justify="center",
    ).pack(fill="x", pady=(0, 12))
    tk.Label(
        contenido,
        text=(
            "Esto eliminará el sketch de Arduino Hound cargado previamente "
            f"en la placa seleccionada: {nombre_placa}.\n\n"
            "¿Desea continuar?"
        ),
        fg="white",
        bg="black",
        justify="center",
        anchor="center",
    ).pack(fill="x")

    botones = tk.Frame(contenido, bg="black")
    botones.pack(pady=(18, 0))

    def aceptar():
        respuesta[0] = True
        ventana.destroy()

    tk.Button(
        botones,
        text="Cancelar",
        command=ventana.destroy,
        bg="black",
        fg="white",
        highlightbackground="OliveDrab",
        highlightthickness=1,
    ).pack(side="left", padx=5)
    tk.Button(
        botones,
        text="Aceptar",
        command=aceptar,
        bg="black",
        fg="white",
        highlightbackground="OliveDrab",
        highlightthickness=1,
    ).pack(side="left", padx=5)

    ventana.update_idletasks()
    ancho = ventana.winfo_width()
    alto = ventana.winfo_height()
    posicion_x = (ventana.winfo_screenwidth() - ancho) // 2
    posicion_y = (ventana.winfo_screenheight() - alto) // 2
    ventana.geometry(f"{ancho}x{alto}+{posicion_x}+{posicion_y}")
    ventana.protocol("WM_DELETE_WINDOW", ventana.destroy)
    ventana.wait_window()
    return respuesta[0]


def _confirmar_reemplazo_firmware():
    parent = text_output.winfo_toplevel()
    ventana = tk.Toplevel(parent)
    ventana.title("Advertencia de firmware")
    configurar_ventana(ventana)
    ventana.after(10, configurar_ventana, ventana)
    ventana.configure(bg="black")
    ventana.resizable(False, False)
    ventana.transient(parent)

    respuesta = [False]
    contenido = tk.Frame(ventana, bg="black")
    contenido.pack(padx=24, pady=20)

    tk.Label(
        contenido,
        text=(
            'Al dar clic en Aceptar el firmware cargado actualmente será eliminado '
            'y reemplazado por el Sketch de "Arduino Hound". Asegurese de tener '
            'un respaldo del Sketch de Arduino actual. ¿Desea continuar?'
        ),
        fg="white",
        bg="black",
        wraplength=430,
        justify="center",
    ).pack(fill="x")

    botones = tk.Frame(contenido, bg="black")
    botones.pack(pady=(18, 0))

    def cancelar():
        ventana.destroy()

    def aceptar():
        respuesta[0] = True
        ventana.destroy()

    boton_cancelar = tk.Button(
        botones,
        text="Cancelar",
        command=cancelar,
        bg="black",
        fg="white",
        highlightbackground="OliveDrab",
        highlightthickness=1,
        takefocus=True,
    )
    boton_cancelar.pack(side="left", padx=5)
    tk.Button(
        botones,
        text="Aceptar",
        command=aceptar,
        bg="black",
        fg="white",
        highlightbackground="OliveDrab",
        highlightthickness=1,
    ).pack(side="left", padx=5)

    ventana.protocol("WM_DELETE_WINDOW", cancelar)
    ventana.bind("<Escape>", lambda _event: cancelar())
    ventana.update_idletasks()
    posicion_x = (ventana.winfo_screenwidth() - ventana.winfo_width()) // 2
    posicion_y = (ventana.winfo_screenheight() - ventana.winfo_height()) // 2
    ventana.geometry(f"+{posicion_x}+{posicion_y}")
    ventana.grab_set()
    ventana.after_idle(boton_cancelar.focus_set)
    ventana.wait_window()
    return respuesta[0]


def cargar_sketch():
    if not _confirmar_reemplazo_firmware():
        return
    if not fqbn_var.get() or not port_var.get():
        messagebox.showerror("Error", "Selecciona FQBN y puerto.", parent=text_output.winfo_toplevel())
        return
    if not SKETCH_PATH.exists():
        messagebox.showerror(
            "Error",
            "No se encontró el sketch requerido. Verifica la instalación de la aplicación.",
            parent=text_output.winfo_toplevel(),
        )
        return
    fqbn = fqbn_var.get()

    def preguntar_automatico():
        if not messagebox.askyesno("Modo automático", "No se pudo cargar usando configuración del JSON.\n\n¿Deseas intentar detección automática de placa?", parent=text_output.winfo_toplevel()):
            return
        intentar_auto()

    def intentar_auto():
        barCarga.iniciar()

        def tarea():
            _actualizar_progreso(10)
            fqbn_auto = detectar_fqbn_automatico()
            _actualizar_progreso(25)
            if not fqbn_auto:
                text_output.after(0, lambda: _finalizar(lambda: messagebox.showerror("Error", "No se pudo detectar el FQBN automáticamente.", parent=text_output.winfo_toplevel())))
                return
            try:
                text_output.insert(tk.END, f"Intentando automático: {fqbn_auto}\n")
                _cargar(fqbn_auto, SKETCH_PATH)
                text_output.after(0, lambda: _finalizar(lambda: messagebox.showinfo("Éxito", f"Cargado automáticamente con:\n{fqbn_auto}", parent=text_output.winfo_toplevel())))
            except subprocess.CalledProcessError:
                text_output.after(0, lambda: _finalizar(lambda: messagebox.showerror("Error", "Falló también el método automático", parent=text_output.winfo_toplevel())))

        threading.Thread(target=tarea, daemon=True).start()

    def intentar_json():
        barCarga.iniciar()

        def tarea():
            try:
                text_output.insert(tk.END, f"\nIntento con JSON: {fqbn}\n")
                _actualizar_progreso(10)
                _cargar(fqbn, SKETCH_PATH)
                text_output.after(0, lambda: _finalizar(lambda: messagebox.showinfo("Éxito", "Sketch cargado correctamente", parent=text_output.winfo_toplevel())))
            except subprocess.CalledProcessError:
                text_output.insert(tk.END, "Falló método JSON\n")
                text_output.after(0, lambda: _finalizar(preguntar_automatico))

        threading.Thread(target=tarea, daemon=True).start()

    intentar_json()


def cargar_respaldo():
    archivo = filedialog.askopenfilename(
        parent=text_output.winfo_toplevel(),
        title="Seleccionar sketch de Arduino",
        filetypes=(
            ("Sketch de Arduino", "*.ino *.pde *.cpp *.c *.h"),
            ("Todos los archivos", "*.*"),
        ),
    )
    if not archivo:
        return
    if not port_var.get() or not fqbn_var.get():
        messagebox.showerror("Error", "Selecciona puerto y placa.", parent=text_output.winfo_toplevel())
        return

    nombre_placa = placa_var.get().strip() or fqbn_var.get().strip()
    nombre_archivo = Path(archivo).name
    if not _mostrar_confirmacion_sketch(nombre_archivo, nombre_placa):
        return

    fqbn = fqbn_var.get().strip()

    def tarea():
        carpeta_temporal = None
        try:
            _actualizar_progreso(5)
            carpeta_temporal = tempfile.mkdtemp(prefix="ArduinoHoundSketch_")
            ruta_temporal = Path(carpeta_temporal) / Path(archivo).name
            shutil.copy2(archivo, ruta_temporal)
            _actualizar_progreso(10)
            text_output.after(0, lambda: text_output.insert(tk.END, f"Cargando: {nombre_archivo}\n"))
            _cargar(fqbn, ruta_temporal.parent)
            text_output.after(0, lambda: _finalizar(lambda: messagebox.showinfo("Éxito", f"Sketch cargado correctamente en:\n{nombre_placa}", parent=text_output.winfo_toplevel())))
        except (OSError, subprocess.CalledProcessError):
            text_output.after(0, lambda: _finalizar(lambda: messagebox.showerror(
                "Error",
                "No se pudo cargar el sketch. Verifica la placa, el puerto y la conexión.",
                parent=text_output.winfo_toplevel(),
            )))
        finally:
            if carpeta_temporal:
                shutil.rmtree(carpeta_temporal, ignore_errors=True)

    barCarga.iniciar()
    threading.Thread(target=tarea, daemon=True).start()


def crear_panel(root):
    global fqbn_var, port_var, placa_var, frame_radios, board_combo
    global detalles_output, text_output, barCarga
    fqbn_var = tk.StringVar()
    port_var = tk.StringVar()
    placa_var = tk.StringVar()

    outer = tk.Frame(root, bg="black", highlightbackground="white", highlightthickness=1)
    outer.pack(padx=5, pady=5, fill="both", expand=True)
    main = tk.Frame(outer, bg="black")
    main.pack(fill="both", expand=True)

    barCarga = BarCarga(main, bg="black")
    barCarga.pack(side="bottom", fill="x", padx=5, pady=5)

    tk.Label(main, text="Cargar Sketch en Arduino", fg=COLOR_TITULO, bg="black", font=("Arial", 14, "bold")).pack(pady=10)

    buttons = tk.Frame(main, bg="black")
    buttons.pack()
    buttons.grid_columnconfigure(0, weight=1)
    buttons.grid_columnconfigure(1, weight=1)
    for indice, (label, command) in enumerate((
        ("🔎 Escanear puertos", escanear_puertos),
        ("+ Info. del puerto", mostrar_info_puerto),
        ("⚡ Cargar sketch", cargar_sketch),
        ("⤵️ Cargar respaldo", cargar_respaldo),
    )):
        tk.Button(
            buttons,
            text=label,
            command=command,
            width=20,
            height=1,
            justify="center",
            bg="black",
            fg="white",
            highlightbackground="OliveDrab",
            highlightthickness=1,
        ).grid(row=indice // 2, column=indice % 2, sticky="ew", padx=3, pady=2)

    frame_radios = tk.Frame(main, bg="black", highlightbackground="white", highlightthickness=1)
    frame_radios.pack(fill="x", pady=5)

    list_frame = tk.Frame(main, bg="black")
    list_frame.pack(fill="x", pady=5)
    estilo_combo = ttk.Style(main)
    estilo_combo.configure(
        "Placas.TCombobox",
        fieldbackground="black",
        background="black",
        foreground="yellow1",
        arrowcolor="yellow1",
        bordercolor="white",
        lightcolor="black",
        darkcolor="black",
    )
    estilo_combo.map(
        "Placas.TCombobox",
        fieldbackground=[("readonly", "black")],
        background=[("readonly", "black")],
        foreground=[("readonly", "yellow1")],
        selectbackground=[("readonly", "black")],
        selectforeground=[("readonly", "yellow1")],
    )
    main.option_add("*TCombobox*Listbox.background", "black")
    main.option_add("*TCombobox*Listbox.foreground", "yellow1")
    main.option_add("*TCombobox*Listbox.selectBackground", "#333333")
    main.option_add("*TCombobox*Listbox.selectForeground", "yellow1")
    board_combo = ttk.Combobox(list_frame, textvariable=placa_var, state="readonly", width=26, style="Placas.TCombobox")
    board_combo.pack()
    board_combo["values"] = sorted(arduino_boards)
    board_combo.bind("<<ComboboxSelected>>", on_placa_seleccionada)

    detalles_output = tk.Text(main, height=DETAILS_HEIGHT, bg="black", fg=COLOR_TITULO)
    detalles_output.pack()
    text_output = tk.Text(main, height=TEXT_HEIGHT, bg="black", fg=COLOR_TITULO)
    text_output.pack()

    puerto_guardado = obtener_puerto_default()
    if puerto_guardado:
        port_var.set(puerto_guardado)

    root.after(500, inicializar_arduino)
    root.after(600, lambda: escanear_puertos())
