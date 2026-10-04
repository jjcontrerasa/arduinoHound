import subprocess
import tkinter as tk
import threading
import re
import time
from tkinter import ttk
from .deteccion_puertos import obtener_dispositivos, parsear_dispositivos
from .estado_ui import BarCarga
from .persistencia import PLACAS_FILE, cargar_boards, cargar_placas, guardar_placa, obtener_puerto_default, guardar_puerto_default
from .rutas import resource_path

try:
    import serial
except ImportError:  # pragma: no cover
    serial = None

COLOR_TITULO = "OliveDrab2"
COLOR_OK = "green"

PLACAS_JSON = PLACAS_FILE


def _perfil_firma_avr(mcu):
    """Devuelve los protocolos de bootloader que pueden leer la firma del MCU."""
    mcu = (mcu or "").upper()
    if "ATMEGA328" in mcu:
        return (("arduino", "atmega328p", "115200"), ("arduino", "atmega328p", "57600"))
    if "ATMEGA2560" in mcu:
        return (("arduino", "atmega2560", "115200"),)
    if "ATMEGA4809" in mcu:
        return (("jtag2updi", "atmega4809", "115200"),)
    if "ATMEGA32U4" in mcu:
        return (("avr109", "atmega32u4", "57600"),)
    if "ATMEGA168" in mcu:
        return (("arduino", "atmega168", "57600"), ("arduino", "atmega168", "19200"))
    if "ATMEGA8" in mcu:
        return (("arduino", "atmega8", "19200"),)
    return ()


def leer_firma_avr(puerto, mcu):
    """Lee la firma por el bootloader sin escribir en la memoria del microcontrolador."""
    perfiles = _perfil_firma_avr(mcu)
    if not perfiles:
        return "No disponible (se requiere un bootloader AVR compatible)"

    if "ATMEGA4809" in (mcu or "").upper():
        herramientas = [resource_path("packages", "arduino", "tools", "avrdude", "8.0.0-arduino1", "bin", "avrdude.exe")]
    else:
        herramientas = [
            resource_path("packages", "arduino", "tools", "avrdude", "6.3.0-arduino17", "bin", "avrdude.exe"),
            resource_path("packages", "arduino", "tools", "avrdude", "8.0.0-arduino1", "bin", "avrdude.exe"),
        ]
    herramienta = next((ruta for ruta in herramientas if ruta.exists()), herramientas[0])
    configuracion = herramienta.parent.parent / "etc" / "avrdude.conf"
    if not herramienta.exists() or not configuracion.exists():
        return "No disponible (avrdude no encontrado)"

    for programador, microcontrolador, velocidad in perfiles:
        if serial is not None and "ATMEGA32U4" not in (mcu or "").upper():
            try:
                with serial.Serial(puerto, 1200, timeout=0) as conexion:
                    conexion.dtr = False
                    time.sleep(0.1)
                    conexion.dtr = True
                time.sleep(0.35)
            except (OSError, serial.SerialException):
                pass

        comando = [
            str(herramienta), "-C", str(configuracion), "-v", "-n",
            "-c", programador, "-p", microcontrolador,
            "-P", puerto, "-b", velocidad,
        ]
        try:
            resultado = subprocess.run(
                comando,
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.TimeoutExpired):
            continue

        coincidencia = re.search(
            r"device signature\s*=\s*(0x[0-9a-f]+)",
            f"{resultado.stdout}\n{resultado.stderr}",
            flags=re.IGNORECASE,
        )
        if coincidencia:
            return coincidencia.group(1).upper()

    return "No disponible (no respondió el bootloader AVR)"


def liberar_puertos():
    """Intento de liberar puertos bloqueados por Arduino IDE o serial monitor."""
    procesos = [
        "arduino.exe",
        "arduino_debug.exe",
        "arduino-cli.exe",
        "Arduino IDE.exe",
    ]
    for proceso in procesos:
        try:
            subprocess.run([
                "taskkill",
                "/F",
                "/IM",
                proceso,
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        except Exception:
            pass
    return True

# =========================
# JSON HELPERS
# =========================
def cargar_json(path):
    return cargar_placas() if path == PLACAS_JSON else cargar_boards()

def guardar_json(nombre, fqbn):
    guardar_placa(nombre, fqbn)

# =========================
# HARDWARE
# =========================
parsear = parsear_dispositivos

# =========================
# UI
# =========================
def crear_panel(root, on_exit=None):

    seleccion = tk.StringVar()

    placas_guardadas = {}
    dispositivos_actuales = []
    consulta_firma_id = 0
    operaciones_activas = 0

    boards = cargar_boards()

    def detectar_fqbn_por_dispositivo(dispositivo):
        nombre = (dispositivo.get("nombre", "") or "").lower()
        raw = (dispositivo.get("raw", "") or "").lower()
        for key, value in sorted(boards.items(), key=lambda item: len(item[0]), reverse=True):
            key_norm = key.lower().replace("_", " ")
            patron = r"(?<!\w)" + r"\s+".join(re.escape(part) for part in key_norm.split()) + r"(?!\w)"
            if re.search(patron, nombre) or re.search(patron, raw):
                return value["fqbn"]
        return ""

    def recargar_placas():
        nonlocal placas_guardadas
        placas_guardadas = cargar_json(PLACAS_JSON)

    outer = tk.Frame(root, bg="black", highlightbackground="white", highlightthickness=1)
    outer.pack(fill="both", expand=True, padx=5, pady=5)

    main = tk.Frame(outer, bg="black")
    main.pack(fill="both", expand=True)

    barCarga = BarCarga(main, bg="black")
    barCarga.pack(side="bottom", fill="x", padx=5, pady=5)

    def iniciar_operacion():
        nonlocal operaciones_activas
        if not operaciones_activas:
            barCarga.iniciar()
        operaciones_activas += 1
        barCarga.actualizar(min(10 + operaciones_activas * 15, 70))

    def terminar_operacion():
        nonlocal operaciones_activas
        operaciones_activas = max(0, operaciones_activas - 1)
        if not operaciones_activas:
            barCarga.detener()

    tk.Label(main, text="Escanear puertos",
             fg=COLOR_TITULO, bg="black",
             font=("Arial", 14, "bold")).pack(pady=10)
    tk.Label(
        main,
        text=(
            "Se muestra información adicional que el fabricante imprime en la placa, "
            "puede asociar una placa al dispositivo actual si lo desea."
        ),
        fg="cyan",
        bg="black",
        wraplength=580,
        justify="center",
    ).pack(fill="x", padx=10, pady=(0, 8))

    frame_btn = tk.Frame(main, bg="black")
    frame_btn.pack()

    frame_lista = tk.Frame(main, bg="black",
                           highlightbackground="white",
                           highlightthickness=1)
    frame_lista.pack(fill="both", expand=True)

    # =========================
    # FQBN UI
    # =========================
    frame_fqbn = tk.Frame(main, bg="black")
    frame_fqbn.pack(fill="x")

    tk.Label(frame_fqbn, text="FQBN: ",
             fg="white", bg="black").pack(side="left")

    fqbn_var = tk.StringVar()
    estilo_fqbn = ttk.Style(main)
    estilo_fqbn.configure(
        "Puertos.FQBN.TCombobox",
        foreground=COLOR_OK,
        fieldbackground="black",
    )
    estilo_fqbn.map(
        "Puertos.FQBN.TCombobox",
        foreground=[("readonly", COLOR_OK)],
    )
    fqbn_combo = ttk.Combobox(
        frame_fqbn,
        textvariable=fqbn_var,
        state="readonly",
        values=sorted({v["fqbn"] for v in boards.values()}),
        width=28,
        style="Puertos.FQBN.TCombobox",
    )
    fqbn_combo.pack(side="left", fill="x", expand=False)

    btn_guardar = tk.Button(frame_fqbn,
        text="Asociar a la placa",
        bg="black", fg="white",
        highlightbackground="OliveDrab",
        highlightthickness=1,
        width=20)
    btn_guardar.pack(side="left", padx=5)

    def actualizar_opciones_fqbn(seleccion=None):
        opciones = sorted({v["fqbn"] for v in boards.values()})
        fqbn_combo["values"] = opciones
        if seleccion and seleccion in opciones:
            fqbn_var.set(seleccion)
        elif opciones:
            fqbn_var.set(opciones[0])
        else:
            fqbn_var.set("")

    def filtrar(event=None):
        texto = (fqbn_var.get() or "").strip().lower()
        opciones = []
        for v in boards.values():
            fqbn = v["fqbn"]
            if not texto or texto in fqbn.lower():
                opciones.append(fqbn)
        if not opciones:
            opciones = sorted({v["fqbn"] for v in boards.values()})
        fqbn_combo["values"] = sorted(set(opciones))

    # =========================
    # DETALLES
    # =========================
    detalles = tk.Text(main, bg="black", fg="white", height=10)
    detalles.pack(fill="both", expand=True)

    detalles.tag_config("ok", foreground=COLOR_OK)

    def mostrar(d):

        nonlocal consulta_firma_id

        recargar_placas()

        opciones = sorted({v["fqbn"] for v in boards.values()})
        fqbn_combo["values"] = opciones

        fqbn_detectado = detectar_fqbn_por_dispositivo(d)
        fqbn_asociado = (
            placas_guardadas.get(f"puerto_{d['puerto']}", "")
            or placas_guardadas.get(d["nombre"], "")
        )

        if fqbn_asociado and fqbn_asociado in opciones:
            fqbn_var.set(fqbn_asociado)
        elif fqbn_detectado and fqbn_detectado in opciones:
            fqbn_var.set(fqbn_detectado)
        elif opciones:
            fqbn_var.set(opciones[0])
        else:
            fqbn_var.set("")

        detalles.delete("1.0", tk.END)

        detalles.insert(tk.END, f"Placa: {d['nombre']}\n")
        detalles.insert(tk.END, f"Puerto: {d['puerto']}\n")
        detalles.insert(tk.END, f"Fabricante: {d.get('fabricante', '-')}\n")
        detalles.insert(tk.END, f"Producto: {d.get('producto', '-')}\n")
        detalles.insert(tk.END, f"VID: {d['vid']}\n")
        detalles.insert(tk.END, f"PID: {d['pid']}\n")
        detalles.insert(tk.END, f"Numero de serie USB real: {d['serial']}\n\n")

        mcu = next(
            (placa.get("mcu", "") for placa in boards.values() if placa["fqbn"] == (fqbn_asociado or fqbn_detectado)),
            "",
        )
        consulta_firma_id += 1
        id_consulta = consulta_firma_id
        detalles.insert(tk.END, "Firma: consultando...\n")

        if fqbn_detectado:
            detalles.insert(tk.END, f"FQBN asignado: {fqbn_detectado}\n", "ok")
            detalles.insert(tk.END, f"Placa detectada: {next((k for k, v in boards.items() if v['fqbn'] == fqbn_detectado), d['nombre'])}\n", "ok")

        if fqbn_asociado:
            mcu = next(
                (v.get("mcu", "-") for v in boards.values() if v["fqbn"] == fqbn_asociado),
                "-",
            )
            detalles.insert(tk.END, f"Placa asociada: {mcu}\n", "ok")

        detalles.insert(tk.END, "\n=== DETALLE SISTEMA ===\n")
        detalles.insert(tk.END, d["raw"])
        barCarga.actualizar(75)

        def consultar_firma():
            try:
                firma = leer_firma_avr(d["puerto"], mcu)

                def actualizar_firma():
                    try:
                        if id_consulta != consulta_firma_id or seleccion.get() != d["puerto"]:
                            return
                        contenido = detalles.get("1.0", tk.END)
                        detalles.delete("1.0", tk.END)
                        detalles.insert(tk.END, contenido.replace("Firma: consultando...", f"Firma: {firma}", 1))
                    finally:
                        terminar_operacion()

                root.after(0, actualizar_firma)
            except Exception:
                root.after(0, terminar_operacion)

        iniciar_operacion()
        threading.Thread(target=consultar_firma, daemon=True).start()

    def guardar_actual():

        sel = seleccion.get()
        if not sel:
            return

        fqbn = fqbn_var.get().strip()
        if not fqbn:
            return

        for d in dispositivos_actuales:
            if d["puerto"] == sel:
                guardar_json(d["nombre"], fqbn)
                recargar_placas()
                mostrar(d)
                return

    btn_guardar.config(command=guardar_actual)
    fqbn_combo.bind("<<ComboboxSelected>>", lambda event: guardar_actual())

    def ejecutar(dispositivos):

        nonlocal dispositivos_actuales

        for w in frame_lista.winfo_children():
            w.destroy()

        recargar_placas()

        dispositivos_actuales = dispositivos

        for d in dispositivos_actuales:

            txt = f"{d['puerto']} - {d['nombre']}"

            tk.Radiobutton(
                frame_lista,
                text=txt,
                variable=seleccion,
                value=d["puerto"],
                bg="black",
                fg="white",
                selectcolor="black",
                anchor="w",
                command=lambda x=d: mostrar(x)
            ).pack(anchor="w", fill="x")

        if dispositivos_actuales:
            primer = dispositivos_actuales[0]
            if primer["puerto"] != obtener_puerto_default():
                guardar_puerto_default(primer["puerto"])
            seleccion.set(primer["puerto"])
            mostrar(primer)

    def escanear():
        iniciar_operacion()

        def tarea():
            try:
                liberar_puertos()
                dispositivos = parsear(obtener_dispositivos())
                root.after(0, barCarga.actualizar, 55)
            except Exception:
                dispositivos = []

            def actualizar_panel():
                try:
                    barCarga.actualizar(70)
                    ejecutar(dispositivos)
                finally:
                    terminar_operacion()

            root.after(0, actualizar_panel)

        threading.Thread(target=tarea, daemon=True).start()

    tk.Button(frame_btn, text="🔎 Escanear Puertos",
              command=escanear,
              bg="black", fg="white",
              highlightbackground="OliveDrab",
              highlightthickness=1).pack(side="left", padx=3)

    if on_exit is not None:
        tk.Button(frame_btn, text="✕ Salir",
                  command=on_exit,
                  bg="black", fg="white",
                  highlightbackground="OliveDrab",
                  highlightthickness=1).pack(side="left", padx=3)

    puerto_guardado = obtener_puerto_default()
    if puerto_guardado:
        seleccion.set(puerto_guardado)
    root.after(500, escanear)
