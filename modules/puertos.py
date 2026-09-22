import subprocess
import tkinter as tk
import threading
from tkinter import ttk
from .deteccion_puertos import obtener_dispositivos, parsear_dispositivos
from .estado_ui import BarCarga
from .persistencia import BOARDS_FILE, PLACAS_FILE, cargar_boards, cargar_placas, guardar_placa, obtener_puerto_default, guardar_puerto_default

COLOR_TITULO = "OliveDrab2"
COLOR_OK = "green"

PLACAS_JSON = PLACAS_FILE
BOARDS_JSON = BOARDS_FILE


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
def crear_panel(root):

    seleccion = tk.StringVar()

    placas_guardadas = {}
    dispositivos_actuales = []

    boards = cargar_json(BOARDS_JSON)

    def detectar_fqbn_por_dispositivo(dispositivo):
        nombre = (dispositivo.get("nombre", "") or "").lower()
        raw = (dispositivo.get("raw", "") or "").lower()
        for key, value in boards.items():
            key_norm = key.lower().replace("_", " ")
            if key_norm in nombre or key_norm in raw:
                return value["fqbn"]
            if any(part in nombre for part in key_norm.split()) or any(part in raw for part in key_norm.split()):
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

    tk.Label(main, text="Escanear Puertos",
             fg=COLOR_TITULO, bg="black",
             font=("Arial", 14, "bold")).pack(pady=10)

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
    fqbn_combo = ttk.Combobox(
        frame_fqbn,
        textvariable=fqbn_var,
        state="readonly",
        values=sorted({v["fqbn"] for v in boards.values()}),
        width=28,
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

        recargar_placas()

        opciones = sorted({v["fqbn"] for v in boards.values()})
        fqbn_combo["values"] = opciones

        fqbn_detectado = detectar_fqbn_por_dispositivo(d)
        fqbn_asociado = placas_guardadas.get(d["nombre"], "")

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

        if fqbn_detectado:
            detalles.insert(tk.END, f"FQBN asignado: {fqbn_detectado}\n", "ok")
            detalles.insert(tk.END, f"Placa detectada: {next((k for k, v in boards.items() if v['fqbn'] == fqbn_detectado), d['nombre'])}\n", "ok")

        if d["nombre"] in placas_guardadas:

            fqbn = placas_guardadas[d["nombre"]]

            mcu = "-"
            for v in boards.values():
                if v["fqbn"] == fqbn:
                    mcu = v.get("mcu", "-")

            detalles.insert(tk.END, f"Placa asociada: {mcu}\n", "ok")

        detalles.insert(tk.END, "\n=== DETALLE SISTEMA ===\n")
        detalles.insert(tk.END, d["raw"])

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

    def ejecutar():

        nonlocal dispositivos_actuales

        for w in frame_lista.winfo_children():
            w.destroy()

        recargar_placas()

        salida = obtener_dispositivos()
        dispositivos_actuales = parsear(salida)

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
        liberar_puertos()
        barCarga.iniciar()

        def tarea():
            try:
                ejecutar()
            finally:
                root.after(0, barCarga.detener)

        threading.Thread(target=tarea, daemon=True).start()

    tk.Button(frame_btn, text="🔎 Escanear Puertos",
              command=escanear,
              bg="black", fg="white",
              highlightbackground="OliveDrab",
              highlightthickness=1).pack()

    puerto_guardado = obtener_puerto_default()
    if puerto_guardado:
        seleccion.set(puerto_guardado)
    root.after(500, escanear)
