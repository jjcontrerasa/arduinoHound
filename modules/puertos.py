import tkinter as tk
import threading
from .deteccion_puertos import obtener_dispositivos, parsear_dispositivos
from .estado_ui import BarCarga
from .persistencia import BOARDS_FILE, PLACAS_FILE, cargar_boards, cargar_placas, guardar_placa

COLOR_TITULO = "OliveDrab2"
COLOR_OK = "green"

PLACAS_JSON = PLACAS_FILE
BOARDS_JSON = BOARDS_FILE

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
    entry = tk.Entry(frame_fqbn, textvariable=fqbn_var)
    entry.pack(side="left", fill="x", expand=True)

    btn_guardar = tk.Button(frame_fqbn,
        text="💾 Guardar",
        bg="black", fg="white",
        highlightbackground="OliveDrab",
        highlightthickness=1)
    btn_guardar.pack(side="left", padx=5)

    # ✅ CAMBIO AQUÍ (Listbox con estilo nuevo)
    listbox = tk.Listbox(
        main,
        height=4,
        bg="gray12",
        fg="DarkOliveGreen2",
        selectbackground="OliveDrab",
        selectforeground="black",
        highlightbackground="white",
        highlightthickness=1
    )
    listbox.pack(fill="x")

    # =========================
    # FILTRO
    # =========================
    def filtrar(event=None):
        txt = fqbn_var.get().lower()
        listbox.delete(0, tk.END)

        for k, v in boards.items():
            if txt in k.lower() or txt in v["fqbn"]:
                listbox.insert(tk.END, v["fqbn"])

    entry.bind("<KeyRelease>", filtrar)

    def sel(event):
        fqbn_var.set(listbox.get(tk.ACTIVE))

    listbox.bind("<<ListboxSelect>>", sel)

    # =========================
    # DETALLES
    # =========================
    detalles = tk.Text(main, bg="black", fg="white", height=10)
    detalles.pack(fill="both", expand=True)

    detalles.tag_config("ok", foreground=COLOR_OK)

    def mostrar(d):

        recargar_placas()

        detalles.delete("1.0", tk.END)

        detalles.insert(tk.END, f"Placa: {d['nombre']}\n")
        detalles.insert(tk.END, f"Puerto: {d['puerto']}\n")
        detalles.insert(tk.END, f"VID: {d['vid']}\n")
        detalles.insert(tk.END, f"PID: {d['pid']}\n")
        detalles.insert(tk.END, f"Numero de serie USB real: {d['serial']}\n\n")

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

    btn_guardar.config(command=guardar_actual)

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

    def escanear():
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

    root.after(500, escanear)
