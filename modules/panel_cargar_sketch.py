import subprocess
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from .arduino_cli import ArduinoCLI, SKETCH_PATH
from .estado_ui import BarCarga
from .persistencia import cargar_boards


FRAME_WIDTH = 350
LIST_MAX_HEIGHT = 200
TEXT_HEIGHT = 6
DETAILS_HEIGHT = 4
COLOR_TITULO = "OliveDrab2"

arduino_boards = cargar_boards()
arduino = ArduinoCLI()
BACKUP_SKETCH_PATH = SKETCH_PATH

buscar_var = None
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


def inicializar_arduino():
    barCarga.iniciar()

    def tarea():
        try:
            text_output.insert(tk.END, "Inicializando entorno Arduino...\n")
            arduino.initialize()
            text_output.insert(tk.END, "Índice actualizado\nArduino listo\n")
        except Exception as error:
            text_output.insert(tk.END, f"Error inicializando: {error}\n")
        finally:
            text_output.after(0, barCarga.detener)

    threading.Thread(target=tarea, daemon=True).start()


def detectar_fqbn_automatico():
    try:
        return arduino.detect_fqbn(port_var.get())
    except Exception as error:
        text_output.insert(tk.END, f"Error detectando FQBN: {error}\n")
        return None


def asegurar_core_instalado(fqbn):
    arduino.ensure_core(fqbn)


def detectar_placas():
    return arduino.list_boards()


def mostrar_detalles(val, key):
    detalles_output.delete("1.0", tk.END)
    detalles_output.insert(
        tk.END,
        f"Placa: {key}\nFQBN: {val['fqbn']}\nMCU: {val.get('mcu', '-')}\n",
    )


def seleccionar_placa(val, key):
    fqbn_var.set(val["fqbn"])
    mostrar_detalles(val, key)


def filtrar_listado(event=None):
    texto = buscar_var.get().lower().strip()
    opciones = [
        key for key, value in arduino_boards.items()
        if not texto or texto in key.lower() or texto in value["fqbn"].lower()
    ]
    board_combo["values"] = opciones
    if placa_var.get() not in opciones:
        placa_var.set("")
        fqbn_var.set("")


def on_placa_seleccionada(event=None):
    key = placa_var.get()
    value = arduino_boards.get(key)
    if value:
        seleccionar_placa(value, key)


def seleccionar_puerto(linea, puerto):
    port_var.set(puerto)
    fqbn_var.set("")
    placa_var.set("")
    buscar_var.set("")
    detalles_output.delete("1.0", tk.END)
    line_lower = linea.lower()
    for key in sorted(arduino_boards, key=len, reverse=True):
        if all(part in line_lower for part in key.split("_")):
            buscar_var.set(key)
            fqbn_var.set(arduino_boards[key]["fqbn"])
            placa_var.set(key)
            filtrar_listado()
            mostrar_detalles(arduino_boards[key], key)
            return
    filtrar_listado()


def escanear_puertos():
    barCarga.iniciar()

    def tarea():
        try:
            salida = detectar_placas()
            text_output.delete("1.0", tk.END)
            text_output.insert(tk.END, salida)
            for widget in frame_radios.winfo_children():
                widget.destroy()
            for line in salida.splitlines():
                line = line.strip()
                if line and not line.startswith("Port"):
                    puerto = line.split()[0]
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
        finally:
            text_output.after(0, barCarga.detener)

    threading.Thread(target=tarea, daemon=True).start()


def _cargar(fqbn, sketch_path):
    asegurar_core_instalado(fqbn)
    arduino.compile(fqbn, sketch_path)
    arduino.upload(port_var.get(), fqbn, sketch_path)


def cargar_sketch():
    if not fqbn_var.get() or not port_var.get():
        messagebox.showerror("Error", "Selecciona FQBN y puerto.")
        return
    if not SKETCH_PATH.exists():
        messagebox.showerror("Error", f"No se encuentra el sketch en:\n{SKETCH_PATH}")
        return
    fqbn = fqbn_var.get()

    def preguntar_automatico():
        if not messagebox.askyesno("Modo automático", "No se pudo cargar usando configuración del JSON.\n\n¿Deseas intentar detección automática de placa?"):
            return
        intentar_auto()

    def intentar_auto():
        barCarga.iniciar()

        def tarea():
            fqbn_auto = detectar_fqbn_automatico()
            if not fqbn_auto:
                text_output.after(0, lambda: _finalizar(lambda: messagebox.showerror("Error", "No se pudo detectar el FQBN automáticamente.")))
                return
            try:
                text_output.insert(tk.END, f"Intentando automático: {fqbn_auto}\n")
                _cargar(fqbn_auto, SKETCH_PATH)
                text_output.after(0, lambda: _finalizar(lambda: messagebox.showinfo("Éxito", f"Cargado automáticamente con:\n{fqbn_auto}")))
            except subprocess.CalledProcessError:
                text_output.after(0, lambda: _finalizar(lambda: messagebox.showerror("Error", "Falló también el método automático")))

        threading.Thread(target=tarea, daemon=True).start()

    def intentar_json():
        barCarga.iniciar()

        def tarea():
            try:
                text_output.insert(tk.END, f"\nIntento con JSON: {fqbn}\n")
                _cargar(fqbn, SKETCH_PATH)
                text_output.after(0, lambda: _finalizar(lambda: messagebox.showinfo("Éxito", "Sketch cargado correctamente")))
            except subprocess.CalledProcessError:
                text_output.insert(tk.END, "Falló método JSON\n")
                text_output.after(0, lambda: _finalizar(preguntar_automatico))

        threading.Thread(target=tarea, daemon=True).start()

    intentar_json()


def cargar_respaldo():
    if not port_var.get():
        messagebox.showerror("Error", "Selecciona puerto.")
        return
    fqbn = fqbn_var.get()

    def preguntar_todas():
        if not messagebox.askyesno("Modo avanzado", "Intentar con todas las placas?"):
            return
        intentar_todas()

    def intentar_todas():
        barCarga.iniciar()

        def tarea():
            boards = sorted(arduino_boards.items(), key=lambda item: 0 if item[0] == "nano_oldboot" else 1)
            for key, value in boards:
                try:
                    text_output.insert(tk.END, f"Intentando: {key}\n")
                    _cargar(value["fqbn"], BACKUP_SKETCH_PATH)
                    text_output.after(0, lambda k=key: _finalizar(lambda: messagebox.showinfo("Éxito", f"Cargado con:\n{k}")))
                    return
                except subprocess.CalledProcessError:
                    continue
            text_output.after(0, lambda: _finalizar(lambda: messagebox.showerror("Error", "No se pudo cargar.")))

        threading.Thread(target=tarea, daemon=True).start()

    def intentar_actual():
        barCarga.iniciar()

        def tarea():
            try:
                text_output.insert(tk.END, f"\nIntentando auto: {fqbn}\n")
                _cargar(fqbn, BACKUP_SKETCH_PATH)
                text_output.after(0, lambda: _finalizar(lambda: messagebox.showinfo("Éxito", f"Cargado con:\n{fqbn}")))
            except subprocess.CalledProcessError:
                text_output.insert(tk.END, f"Falló: {fqbn}\n")
                text_output.after(0, lambda: _finalizar(preguntar_todas))

        threading.Thread(target=tarea, daemon=True).start()

    if fqbn:
        intentar_actual()
    else:
        preguntar_todas()


def crear_panel(root):
    global buscar_var, fqbn_var, port_var, placa_var, frame_radios, board_combo
    global detalles_output, text_output, barCarga
    buscar_var = tk.StringVar()
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
    for label, command in (("🔎 Escanear puertos", escanear_puertos), ("⚡ Cargar sketch", cargar_sketch), ("⤵️ Cargar respaldo", cargar_respaldo)):
        tk.Button(buttons, text=label, command=command, width=15, bg="black", fg="white", highlightbackground="OliveDrab", highlightthickness=1).pack(side="left", padx=3)

    frame_radios = tk.Frame(main, bg="black", highlightbackground="white", highlightthickness=1)
    frame_radios.pack(fill="x", pady=5)
    search_frame = tk.Frame(main, bg="black")
    search_frame.pack(fill="x")
    tk.Label(search_frame, text="FQBN:", fg="white", bg="black").pack(side="left")
    entry = tk.Entry(search_frame, textvariable=buscar_var)
    entry.pack(side="left")
    entry.bind("<KeyRelease>", filtrar_listado)

    list_frame = tk.Frame(main, bg="black")
    list_frame.pack(fill="x", pady=5)
    board_combo = ttk.Combobox(list_frame, textvariable=placa_var, state="readonly", width=30)
    board_combo.pack(fill="x")
    board_combo.bind("<<ComboboxSelected>>", on_placa_seleccionada)

    detalles_output = tk.Text(main, height=DETAILS_HEIGHT, bg="black", fg=COLOR_TITULO)
    detalles_output.pack()
    text_output = tk.Text(main, height=TEXT_HEIGHT, bg="black", fg="white")
    text_output.pack()
    root.after(500, inicializar_arduino)
    filtrar_listado()
