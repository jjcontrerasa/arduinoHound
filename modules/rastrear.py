import tkinter as tk
import subprocess
import threading
from .deteccion_puertos import obtener_puertos, parsear_puertos
from .estado_ui import BarCarga
from .rastreo_serial import leer_datos

COLOR_TITULO = "OliveDrab2"
COLOR_OK = "green"

# =========================
# DETECTAR PUERTOS
# =========================

# =========================
# UI
# =========================
def crear_panel(root):

    seleccion = tk.StringVar()
    dispositivos = []

    outer = tk.Frame(root, bg="black",
                     highlightbackground="white",
                     highlightthickness=1)
    outer.pack(fill="both", expand=True, padx=5, pady=5)

    main = tk.Frame(outer, bg="black")
    main.pack(fill="both", expand=True)

    barCarga = BarCarga(main, bg="black")
    barCarga.pack(side="bottom", fill="x", padx=5, pady=5)

    tk.Label(main, text="Rastrear Puertos",
             fg=COLOR_TITULO,
             bg="black",
             font=("Arial", 14, "bold")).pack(pady=10)

    frame_btn = tk.Frame(main, bg="black")
    frame_btn.pack()

    frame_lista = tk.Frame(main, bg="black",
                           highlightbackground="white",
                           highlightthickness=1)
    frame_lista.pack(fill="both", expand=True)

    salida = tk.Text(main, bg="black", fg="white", height=12)
    salida.pack(fill="both", expand=True)

    salida.tag_config("ok", foreground=COLOR_OK)

    # =========================
    # MOSTRAR RESULTADO
    # =========================
    def mostrar_resultado(puerto, datos):

        salida.delete("1.0", tk.END)

        if datos["board"] == "PUERTO OCUPADO":
            salida.insert(tk.END, f"Puerto: {puerto}\n")
            salida.insert(tk.END, "❌ El puerto está en uso\n\n")
            salida.insert(tk.END, "Cierra Arduino IDE o monitor serial.\n")
            return

        salida.insert(tk.END, f"Puerto: {puerto}\n", "ok")
        salida.insert(tk.END, f"Placa detectada: {datos['board']}\n\n", "ok")

        salida.insert(tk.END, "=== I2C ===\n")
        salida.insert(tk.END, f"{datos['i2c']}\n\n")

        salida.insert(tk.END, "=== UART ===\n")
        salida.insert(tk.END, f"{datos['uart']}\n")

        if datos["lora"] != "-":
            salida.insert(tk.END, "\n=== LORA UART ===\n")
            salida.insert(tk.END, f"{datos['lora']}\n")

        salida.insert(tk.END, "\n=== SPI ===\n")
        salida.insert(tk.END, f"{datos['spi']}\n")

    # =========================
    # RASTREAR
    # =========================
    def rastrear():

        puerto = seleccion.get()
        if not puerto:
            return

        salida.delete("1.0", tk.END)
        salida.insert(tk.END, "🔍 Rastreando...\n")

        barCarga.iniciar()

        def tarea():
            try:
                datos = leer_datos(puerto)
                root.after(0, lambda: mostrar_resultado(puerto, datos))
            finally:
                root.after(0, barCarga.detener)

        threading.Thread(target=tarea, daemon=True).start()

    # =========================
    # LIBERAR
    # =========================
    def liberar():
        salida.delete("1.0", tk.END)
        salida.insert(tk.END, "🔓 Intentando liberar...\n")

        barCarga.iniciar()

        def tarea():
            try:
                subprocess.run("mode", shell=True)
                root.after(0, lambda: salida.insert(tk.END, "✅ Liberación completada\n"))
            except Exception:
                root.after(0, lambda: salida.insert(tk.END, "⚠️ No se pudo liberar\n"))
            finally:
                root.after(0, barCarga.detener)

        threading.Thread(target=tarea, daemon=True).start()

    tk.Button(frame_btn, text="🔍 Rastrear componentes",
              command=rastrear,
              bg="black", fg="white",
              highlightbackground="OliveDrab",
              highlightthickness=1).pack(side="left", padx=5)

    tk.Button(frame_btn, text="🔓 Liberar puertos",
              command=liberar,
              bg="black", fg="white",
              highlightbackground="OliveDrab",
              highlightthickness=1).pack(side="left", padx=5)

    # =========================
    # ESCANEAR
    # =========================
    def escanear():
        nonlocal dispositivos

        for w in frame_lista.winfo_children():
            w.destroy()

        raw = obtener_puertos()
        dispositivos = parsear_puertos(raw)

        if not dispositivos:
            salida.insert(tk.END, "No se detectaron puertos\n")
            return

        if len(dispositivos) == 1:
            d = dispositivos[0]
            seleccion.set(d["puerto"])

            salida.insert(tk.END,
                          f"{d['puerto']} - {d['nombre']}\n",
                          "ok")

        else:
            for d in dispositivos:
                txt = f"{d['puerto']} - {d['nombre']}"

                tk.Radiobutton(
                    frame_lista,
                    text=txt,
                    variable=seleccion,
                    value=d["puerto"],
                    bg="black",
                    fg="white",
                    selectcolor="black",
                    anchor="w"
                ).pack(anchor="w", fill="x")

    def escanear_async():
        barCarga.iniciar()

        def tarea():
            try:
                escanear()
            finally:
                root.after(0, barCarga.detener)

        threading.Thread(target=tarea, daemon=True).start()

    root.after(500, escanear_async)