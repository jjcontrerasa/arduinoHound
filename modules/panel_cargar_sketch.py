import subprocess
import threading
import shutil
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .arduino_cli import ArduinoCLI, SKETCH_PATH
from .deteccion_puertos import (
    familia_fqbn, identificar_placa, obtener_dispositivos, parsear_dispositivos,
)
from .estado_ui import BarCarga
from .persistencia import (
    cargar_boards, cargar_boards_esp32, guardar_placa,
    obtener_puerto_default, guardar_puerto_default,
)
from .rutas import configurar_ventana, titulo


FRAME_WIDTH = 350
LIST_MAX_HEIGHT = 200
TEXT_HEIGHT = 6
DETAILS_HEIGHT = 5
COLOR_TITULO = "OliveDrab2"

arduino_boards = cargar_boards()
esp32_boards = cargar_boards_esp32()
arduino = ArduinoCLI()
fqbn_var = None
port_var = None
placa_var = None
esp32_var = None
frame_radios = None
board_combo = None
esp32_combo = None
puertos_detectados = {}
metadatos_puertos = {}
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
    return arduino.discover_boards()


def mostrar_detalles(val, key):
    detalles_output.delete("1.0", tk.END)
    detalles_output.insert(
        tk.END,
        f"Placa: {val.get('name', key)}\nFQBN: {val['fqbn']}\nMCU: {val.get('mcu', '-')}\n",
    )
    if familia_fqbn(val["fqbn"]) == "esp32":
        detalles_output.insert(tk.END, "Carga del sketch con el FQBN ESP32 seleccionado.\n")


def guardar_asociacion_puerto():
    puerto = port_var.get().strip() if port_var else ""
    clave = (placa_var.get().strip() or esp32_var.get().strip()) if placa_var else ""
    fqbn = fqbn_var.get().strip() if fqbn_var else ""
    if not puerto or not fqbn:
        return

    guardar_placa(f"puerto_{puerto}", fqbn)
    if clave:
        guardar_placa(f"puerto_{puerto}_placa", clave)


def seleccionar_placa(val, key):
    es_esp32 = familia_fqbn(val["fqbn"]) == "esp32"
    catalogo, combo = (esp32_boards, esp32_combo) if es_esp32 else (arduino_boards, board_combo)
    if key not in catalogo:
        catalogo[key] = val
        combo["values"] = sorted(catalogo)
    placa_var.set("" if es_esp32 else key)
    esp32_var.set(key if es_esp32 else "")
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


def on_esp32_seleccionada(event=None):
    key = esp32_var.get()
    value = esp32_boards.get(key)
    if value:
        seleccionar_placa(value, key)


def _habilitar_listas(familia=None):
    board_combo.configure(state="disabled" if familia == "esp32" else "readonly")
    esp32_combo.configure(state="disabled" if familia == "arduino" else "readonly")


def mostrar_info_puerto():
    parent = text_output.winfo_toplevel()
    ventana = tk.Toplevel(parent)
    ventana.title(titulo("Información del puerto"))
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
    esp32_var.set("")
    detalles_output.delete("1.0", tk.END)
    entrada = puertos_detectados.get(
        puerto, {"port": {"address": puerto, "label": linea}}
    )
    familia, clave, datos = identificar_placa(
        entrada,
        {"arduino": arduino_boards, "esp32": esp32_boards},
        metadatos_puertos.get(puerto),
    )
    _habilitar_listas(familia)
    if datos:
        seleccionar_placa(datos, clave)
        return

    nombre = {"arduino": "Arduino", "esp32": "ESP32"}.get(familia, "Arduino o ESP32")
    detalles_output.insert(
        tk.END,
        f"No se detectó un FQBN exacto para este puerto.\n"
        f"Selecciona manualmente la placa {nombre}.\n",
    )


def _actualizar_puertos(entradas, dispositivos):
    puertos_detectados.clear()
    metadatos_puertos.clear()
    if isinstance(dispositivos, str):
        dispositivos = parsear_dispositivos(dispositivos)
    if isinstance(dispositivos, list):
        metadatos_puertos.update({
            item["puerto"]: item for item in dispositivos if item.get("puerto")
        })
    puertos_detectados.update({item["port"]["address"]: item for item in entradas})
    for puerto, datos in metadatos_puertos.items():
        puertos_detectados.setdefault(
            puerto, {"port": {"address": puerto, "label": datos.get("descripcion", "")}}
        )
    for widget in frame_radios.winfo_children():
        widget.destroy()
    port_var.set("")
    fqbn_var.set("")
    placa_var.set("")
    esp32_var.set("")
    detalles_output.delete("1.0", tk.END)
    _habilitar_listas()
    text_output.delete("1.0", tk.END)
    text_output.insert(tk.END, "Escaneo de puertos completado.\n")
    for puerto, entrada in puertos_detectados.items():
        nombres = ", ".join(
            board.get("name", "") for board in entrada.get("matching_boards", [])
            if board.get("name")
        )
        descripcion = (
            nombres or metadatos_puertos.get(puerto, {}).get("descripcion")
            or entrada["port"].get("label") or "Puerto serial"
        )
        linea = f"{puerto} - {descripcion}"
        tk.Radiobutton(
            frame_radios, text=linea, variable=port_var, value=puerto,
            bg="black", fg="white", selectcolor="black", anchor="w",
            wraplength=340,
            command=lambda value=linea, selected=puerto: seleccionar_puerto(value, selected),
        ).pack(anchor="w", fill="x")
    if puertos_detectados:
        guardado = obtener_puerto_default()
        puerto = guardado if guardado in puertos_detectados else next(iter(puertos_detectados))
        guardar_puerto_default(puerto)
        seleccionar_puerto("", puerto)
    else:
        text_output.insert(tk.END, "No se encontraron placas. Ambas listas están habilitadas.\n")


def escanear_puertos():
    barCarga.iniciar()

    def tarea():
        try:
            _actualizar_progreso(5)
            entradas = detectar_placas()
            dispositivos = obtener_dispositivos()
            _actualizar_progreso(55)
        except (OSError, subprocess.CalledProcessError, ValueError) as error:
            def mostrar_error(mensaje=str(error)):
                _actualizar_puertos([], [])
                text_output.insert(tk.END, f"No se pudieron consultar los puertos: {mensaje}\n")
                barCarga.detener()
            text_output.after(0, mostrar_error)
        else:
            text_output.after(
                0, lambda: _finalizar(lambda: _actualizar_puertos(entradas, dispositivos))
            )

    threading.Thread(target=tarea, daemon=True).start()


def _cargar(fqbn, sketch_path, puerto):
    asegurar_core_instalado(fqbn)
    _actualizar_progreso(15)
    arduino.compile(fqbn, sketch_path)
    _actualizar_progreso(72)
    arduino.upload(puerto, fqbn, sketch_path)
    _actualizar_progreso(95)


def _mostrar_confirmacion_sketch(nombre_archivo, nombre_placa):
    ventana = tk.Toplevel(text_output.winfo_toplevel())
    ventana.title(titulo("Confirmar carga de sketch"))
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
    ventana.title(titulo("Advertencia de firmware"))
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
            'un respaldo del Sketch actual de la placa. ¿Desea continuar?'
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
    fqbn = fqbn_var.get().strip()
    puerto = port_var.get().strip()
    if not _confirmar_reemplazo_firmware():
        return
    if not fqbn or not puerto:
        messagebox.showerror(titulo("Error"), "Selecciona FQBN y puerto.", parent=text_output.winfo_toplevel())
        return
    if not SKETCH_PATH.exists():
        messagebox.showerror(
            titulo("Error"),
            "No se encontró el sketch requerido. Verifica la instalación de la aplicación.",
            parent=text_output.winfo_toplevel(),
        )
        return
    def preguntar_automatico():
        if not messagebox.askyesno(titulo("Modo automático"), "No se pudo cargar usando configuración del JSON.\n\n¿Deseas intentar detección automática de placa?", parent=text_output.winfo_toplevel()):
            return
        intentar_auto()

    def intentar_auto():
        barCarga.iniciar()

        def tarea():
            try:
                _actualizar_progreso(10)
                fqbn_auto = arduino.detect_fqbn(puerto)
                _actualizar_progreso(25)
                if not fqbn_auto:
                    raise ValueError("No se pudo detectar un FQBN único automáticamente.")
                text_output.after(0, lambda: text_output.insert(tk.END, f"Intentando automático: {fqbn_auto}\n"))
                _cargar(fqbn_auto, SKETCH_PATH, puerto)
                text_output.after(0, lambda: _finalizar(lambda: messagebox.showinfo(titulo("Éxito"), f"Cargado automáticamente con:\n{fqbn_auto}", parent=text_output.winfo_toplevel())))
            except (OSError, ValueError, subprocess.CalledProcessError) as error:
                mensaje = f"Falló el método automático: {error}"
                text_output.after(0, lambda: _finalizar(lambda: messagebox.showerror(titulo("Error"), mensaje, parent=text_output.winfo_toplevel())))

        threading.Thread(target=tarea, daemon=True).start()

    def intentar_json():
        barCarga.iniciar()

        def tarea():
            try:
                text_output.after(0, lambda: text_output.insert(tk.END, f"\nIntento con JSON: {fqbn}\n"))
                _actualizar_progreso(10)
                _cargar(fqbn, SKETCH_PATH, puerto)
                text_output.after(0, lambda: _finalizar(lambda: messagebox.showinfo(titulo("Éxito"), "Sketch cargado correctamente", parent=text_output.winfo_toplevel())))
            except (OSError, ValueError, subprocess.CalledProcessError) as error:
                mensaje = f"Falló método JSON: {error}\n"
                text_output.after(0, lambda: text_output.insert(tk.END, mensaje))
                text_output.after(0, lambda: _finalizar(preguntar_automatico))

        threading.Thread(target=tarea, daemon=True).start()

    intentar_json()


def cargar_respaldo():
    archivo = filedialog.askopenfilename(
        parent=text_output.winfo_toplevel(),
        title=titulo("Seleccionar sketch de Arduino / ESP32"),
        filetypes=(
            ("Sketch de Arduino", "*.ino *.pde *.cpp *.c *.h"),
            ("Todos los archivos", "*.*"),
        ),
    )
    if not archivo:
        return
    if not port_var.get() or not fqbn_var.get():
        messagebox.showerror(titulo("Error"), "Selecciona puerto y placa.", parent=text_output.winfo_toplevel())
        return

    fqbn = fqbn_var.get().strip()
    puerto = port_var.get().strip()
    nombre_placa = placa_var.get().strip() or esp32_var.get().strip() or fqbn
    nombre_archivo = Path(archivo).name
    if not _mostrar_confirmacion_sketch(nombre_archivo, nombre_placa):
        return

    def tarea():
        carpeta_temporal = None
        try:
            _actualizar_progreso(5)
            carpeta_temporal = tempfile.mkdtemp(prefix="ArduinoHoundSketch_")
            ruta_sketch = Path(carpeta_temporal) / Path(archivo).stem
            ruta_sketch.mkdir()
            ruta_temporal = ruta_sketch / Path(archivo).name
            shutil.copy2(archivo, ruta_temporal)
            _actualizar_progreso(10)
            text_output.after(0, lambda: text_output.insert(tk.END, f"Cargando: {nombre_archivo}\n"))
            _cargar(fqbn, ruta_sketch, puerto)
            text_output.after(0, lambda: _finalizar(lambda: messagebox.showinfo(titulo("Éxito"), f"Sketch cargado correctamente en:\n{nombre_placa}", parent=text_output.winfo_toplevel())))
        except (OSError, ValueError, subprocess.CalledProcessError) as error:
            mensaje = f"No se pudo cargar el sketch. Verifica la placa, el puerto y la conexión.\n\n{error}"
            text_output.after(0, lambda: _finalizar(lambda: messagebox.showerror(
                titulo("Error"),
                mensaje,
                parent=text_output.winfo_toplevel(),
            )))
        finally:
            if carpeta_temporal:
                shutil.rmtree(carpeta_temporal, ignore_errors=True)

    barCarga.iniciar()
    threading.Thread(target=tarea, daemon=True).start()


def crear_panel(root):
    global fqbn_var, port_var, placa_var, frame_radios, board_combo
    global detalles_output, text_output, barCarga, esp32_var, esp32_combo
    fqbn_var = tk.StringVar()
    port_var = tk.StringVar()
    placa_var = tk.StringVar()
    esp32_var = tk.StringVar()

    outer = tk.Frame(root, bg="black", highlightbackground="white", highlightthickness=1)
    outer.pack(padx=5, pady=5, fill="both", expand=True)
    main = tk.Frame(outer, bg="black")
    main.pack(fill="both", expand=True)

    barCarga = BarCarga(main, bg="black")
    barCarga.pack(side="bottom", fill="x", padx=5, pady=5)

    tk.Label(main, text="Cargar Sketch en Arduino / ESP32", fg=COLOR_TITULO, bg="black", font=("Arial", 14, "bold")).pack(pady=10)

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
    list_frame.columnconfigure(0, weight=1, uniform="placas")
    list_frame.columnconfigure(1, weight=1, uniform="placas")
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
        fieldbackground=[("disabled", "#1b1b1b"), ("readonly", "black")],
        background=[("readonly", "black")],
        foreground=[("disabled", "gray50"), ("readonly", "yellow1")],
        selectbackground=[("readonly", "black")],
        selectforeground=[("readonly", "yellow1")],
    )
    main.option_add("*TCombobox*Listbox.background", "black")
    main.option_add("*TCombobox*Listbox.foreground", "yellow1")
    main.option_add("*TCombobox*Listbox.selectBackground", "#333333")
    main.option_add("*TCombobox*Listbox.selectForeground", "yellow1")
    tk.Label(list_frame, text="Arduino", fg="cyan", bg="black").grid(
        row=0, column=0, sticky="w", padx=5,
    )
    tk.Label(list_frame, text="ESP32", fg="DarkOrange1", bg="black").grid(
        row=0, column=1, sticky="w", padx=5,
    )
    board_combo = ttk.Combobox(list_frame, textvariable=placa_var, state="readonly", width=16, style="Placas.TCombobox")
    board_combo.grid(row=1, column=0, sticky="ew", padx=5)
    board_combo["values"] = sorted(arduino_boards)
    board_combo.bind("<<ComboboxSelected>>", on_placa_seleccionada)
    esp32_combo = ttk.Combobox(
        list_frame, textvariable=esp32_var, state="readonly", width=16,
        style="Placas.TCombobox", values=sorted(esp32_boards),
    )
    esp32_combo.grid(row=1, column=1, sticky="ew", padx=5)
    esp32_combo.bind("<<ComboboxSelected>>", on_esp32_seleccionada)

    detalles_output = tk.Text(main, height=DETAILS_HEIGHT, bg="black", fg=COLOR_TITULO)
    detalles_output.pack()
    text_output = tk.Text(main, height=TEXT_HEIGHT, bg="black", fg=COLOR_TITULO)
    text_output.pack()

    puerto_guardado = obtener_puerto_default()
    if puerto_guardado:
        port_var.set(puerto_guardado)

    root.after(500, inicializar_arduino)
    root.after(600, lambda: escanear_puertos())
