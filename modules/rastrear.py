import tkinter as tk
import subprocess
import threading
import webbrowser
from .deteccion_puertos import obtener_puertos, parsear_puertos
from .estado_ui import BarCarga, IndicadorEstado
from .persistencia import cargar_placas
from .rastreo_serial import leer_datos

COLOR_TITULO = "OliveDrab2"
COLOR_OK = "green"


def liberar_puertos():
    """Intento best-effort de liberar puertos de procesos comunes de Arduino."""
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


def formatear_nombre_placa(nombre):
    texto = str(nombre or "").strip()
    if not texto or texto.lower() in {"-", "unknown", "none", "ninguno", "desconocida", "puerto ocupado"}:
        return "Desconocida"

    if texto.lower().startswith("arduino:"):
        texto = texto.split(":")[-1]

    texto = texto.replace("_", " ").replace("-", " ")
    reemplazos = {
        "uno r4 minima": "UNO R4 Minima",
        "uno r4 wifi": "UNO R4 WiFi",
        "nano oldboot": "Nano Old Boot",
        "nano every": "Nano Every",
        "mega2560": "MEGA2560",
        "mega 2560": "MEGA2560",
        "uno": "UNO",
        "nano": "Nano",
        "leonardo": "Leonardo",
        "micro": "Micro",
    }

    texto_normal = texto.strip()
    clave = texto_normal.lower()
    if clave in reemplazos:
        return reemplazos[clave]

    palabras = []
    for parte in texto_normal.split():
        parte = parte.strip()
        if not parte:
            continue
        if parte.lower() in {"r4", "wifi", "oldboot", "every"}:
            palabras.append(parte.upper() if parte.lower() == "r4" else parte.title())
        else:
            palabras.append(parte.title())
    return " ".join(palabras) if palabras else "Desconocida"

# =========================
# DETECTAR PUERTOS
# =========================

# =========================
# UI
# =========================
def crear_panel(root):

    seleccion = tk.StringVar()
    dispositivos = []
    gps_coords_actuales = [None]
    gps_detectado = [False]

    outer = tk.Frame(root, bg="black",
                     highlightbackground="white",
                     highlightthickness=1)
    outer.pack(fill="both", expand=True, padx=5, pady=5)

    main = tk.Frame(outer, bg="black")
    main.pack(fill="both", expand=True)

    barCarga = BarCarga(main, bg="black")
    barCarga.pack(side="bottom", fill="x", padx=5, pady=5)

    tk.Label(main, text="Rastrear componentes",
             fg=COLOR_TITULO,
             bg="black",
             font=("Arial", 14, "bold")).pack(pady=10)

    frame_btn = tk.Frame(main, bg="black")
    frame_btn.pack()

    # =========================
    # INDICADORES DE PROTOCOLO + GPS
    # =========================
    frame_indicadores = tk.Frame(main, bg="black")
    frame_indicadores.pack(pady=(0, 5))

    indicador_i2c = IndicadorEstado(frame_indicadores, "I2C")
    indicador_i2c.pack(side="left", padx=8)

    indicador_uart = IndicadorEstado(frame_indicadores, "UART")
    indicador_uart.pack(side="left", padx=8)

    indicador_spi = IndicadorEstado(frame_indicadores, "SPI")
    indicador_spi.pack(side="left", padx=8)

    boton_gps = tk.Button(frame_indicadores, text="🌐",
                          command=lambda: mostrar_gps(),
                          state="disabled",
                          bg="black", fg="white",
                          disabledforeground="gray30",
                          highlightbackground="OliveDrab",
                          highlightthickness=1)
    boton_gps.pack(side="left", padx=(20, 0))

    frame_lista = tk.Frame(main, bg="black",
                           highlightbackground="white",
                           highlightthickness=1)
    frame_lista.pack(fill="both", expand=True)

    salida = tk.Text(main, bg="black", fg="white", height=10)
    salida.pack(fill="both", expand=True)

    salida.tag_config("ok", foreground=COLOR_OK)

    frame_debug = tk.Frame(main, bg="black", highlightbackground="white", highlightthickness=1)
    frame_debug.pack(fill="both", expand=True, pady=(5, 0))

    tk.Label(frame_debug, text="Diagnóstico en tiempo real", fg="#7fe9ff", bg="black", font=("Arial", 10, "bold")).pack(anchor="w", padx=5, pady=(5, 0))
    debug_output = tk.Text(frame_debug, bg="black", fg="#7fe9ff", height=7)
    debug_output.pack(fill="both", expand=True, padx=5, pady=5)

    debug_output.tag_config("debug", foreground="#7fe9ff")

    # =========================
    # MOSTRAR RESULTADO
    # =========================
    def resolver_nombre_placa(puerto, valor_board):
        if not valor_board or valor_board == "-":
            return "Desconocida"

        nombre = str(valor_board).strip()
        placas = cargar_placas()
        clave_guardada = placas.get(f"puerto_{puerto}_placa")
        if clave_guardada:
            return formatear_nombre_placa(clave_guardada)

        if nombre.upper() not in {"UNKNOWN", "NONE", "PUERTO OCUPADO"}:
            try:
                from .persistencia import cargar_boards
                for key, value in cargar_boards().items():
                    if value.get("fqbn") == nombre:
                        return formatear_nombre_placa(key)
            except Exception:
                pass
            return formatear_nombre_placa(nombre)

        return "Desconocida"

    def mostrar_resultado(puerto, datos):

        salida.delete("1.0", tk.END)

        if datos["board"] == "PUERTO OCUPADO":
            salida.insert(tk.END, f"Puerto: {puerto}\n")
            salida.insert(tk.END, "❌ El puerto está en uso\n\n")
            salida.insert(tk.END, "Cierra Arduino IDE o monitor serial.\n")
            return

        nombre_placa = resolver_nombre_placa(puerto, datos["board"])
        salida.insert(tk.END, f"Puerto: {puerto}\n", "ok")
        salida.insert(tk.END, f"Placa detectada: {nombre_placa}\n\n", "ok")

        i2c_hay = str(datos.get('i2c', 'ninguno')).strip().lower() not in {'-', '', 'none', 'ninguno'}
        uart_hay = str(datos.get('uart', 'ninguno')).strip().lower() not in {'-', '', 'none', 'ninguno'}
        spi_hay = str(datos.get('spi', 'ninguno')).strip().lower() not in {'-', '', 'none', 'ninguno'}

        indicador_i2c.resultado(i2c_hay)
        indicador_uart.resultado(uart_hay)
        indicador_spi.resultado(spi_hay)

        salida.insert(tk.END, "=== I2C ===\n")
        salida.insert(tk.END, f"{datos['i2c']}\n\n")

        salida.insert(tk.END, "=== UART ===\n")
        salida.insert(tk.END, f"{datos['uart']}\n")

        if datos["lora"] != "-":
            salida.insert(tk.END, "\n=== LORA UART ===\n")
            salida.insert(tk.END, f"{datos['lora']}\n")

        salida.insert(tk.END, "\n=== GPS ===\n")
        if gps_detectado[0]:
            if gps_coords_actuales[0]:
                salida.insert(tk.END, "GPS: conectado y coordenadas disponibles\n", "ok")
            else:
                salida.insert(tk.END, "GPS: conectado, esperando coordenadas\n", "ok")
        else:
            salida.insert(tk.END, "GPS: no detectado\n")

        salida.insert(tk.END, "\n=== SPI ===\n")
        salida.insert(tk.END, f"{datos['spi']}\n")

    # =========================
    # GPS: ICONO Y VENTANA EMERGENTE
    # =========================
    def manejar_evento(tipo, valor):
        if tipo == "debug":
            texto = str(valor).strip()
            if not texto:
                return
            debug_output.insert(tk.END, f"{texto}\n")
            debug_output.see(tk.END)
            return

        if tipo == "i2c":
            indicador_i2c.encender()
        elif tipo == "uart":
            indicador_uart.encender()
            valor_upper = str(valor).upper()
            if "GPS" in valor_upper:
                gps_detectado[0] = True
                boton_gps.config(text="GPS conectado", state="normal", bg="black", fg="#7fe9ff")
                if not gps_coords_actuales[0]:
                    debug_output.insert(tk.END, "GPS detectado: módulo presente, esperando coordenadas...\n")
                    debug_output.see(tk.END)
            elif "TRANSCEIVER" in valor_upper or "HC-12" in valor_upper or "RF" in valor_upper or "AT_RESP" in valor_upper:
                debug_output.insert(tk.END, f"Transceptor UART detectado: {valor}\n")
                debug_output.see(tk.END)
        elif tipo == "spi":
            indicador_spi.encender()
        elif tipo == "gps_coords" and valor:
            partes = str(valor).split(",")
            if len(partes) == 2:
                gps_coords_actuales[0] = (partes[0].strip(), partes[1].strip())
                gps_detectado[0] = True
                boton_gps.config(text="GPS detectado", state="normal", bg="green", fg="white")

    def mostrar_gps():
        if not gps_coords_actuales[0]:
            return

        lat, lon = gps_coords_actuales[0]

        ventana = tk.Toplevel(root)
        ventana.title("Ubicación GPS")
        ventana.configure(bg="black")
        ventana.resizable(False, False)
        ventana.transient(root)
        ventana.grab_set()

        tk.Label(ventana, text="📍 Coordenadas GPS",
                 fg=COLOR_TITULO, bg="black",
                 font=("Arial", 12, "bold")).pack(padx=20, pady=(15, 8))

        tk.Label(ventana, text=f"Latitud: {lat}", fg="white", bg="black").pack(padx=20, anchor="w")
        tk.Label(ventana, text=f"Longitud: {lon}", fg="white", bg="black").pack(padx=20, pady=(0, 15), anchor="w")

        frame_botones = tk.Frame(ventana, bg="black")
        frame_botones.pack(pady=(0, 15), padx=20)

        def buscar_en_maps():
            webbrowser.open(f"https://www.google.com/maps/search/?api=1&query={lat},{lon}")

        tk.Button(frame_botones, text="Buscar en Maps",
                  command=buscar_en_maps,
                  bg="black", fg="white",
                  highlightbackground="OliveDrab",
                  highlightthickness=1).pack(side="left", padx=5)

        tk.Button(frame_botones, text="Salir",
                  command=ventana.destroy,
                  bg="black", fg="white",
                  highlightbackground="OliveDrab",
                  highlightthickness=1).pack(side="left", padx=5)

    # =========================
    # RASTREAR
    # =========================
    def rastrear():

        puerto = seleccion.get()
        if not puerto:
            return

        liberar_puertos()

        salida.delete("1.0", tk.END)
        salida.insert(tk.END, "🔍 Liberando puertos y rastreando...\n")

        indicador_i2c.apagar()
        indicador_uart.apagar()
        indicador_spi.apagar()
        gps_coords_actuales[0] = None
        gps_detectado[0] = False
        debug_output.delete("1.0", tk.END)
        boton_gps.config(text="🌐", state="disabled", bg="black", fg="white")

        barCarga.iniciar()

        def tarea():
            try:
                datos = leer_datos(
                    puerto,
                    on_evento=lambda tipo, valor: root.after(0, manejar_evento, tipo, valor)
                )
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

    btn_actualizar = tk.Button(
        frame_btn,
        text="🔄",
        command=lambda: escanear_async(),
        bg="black",
        fg="white",
        highlightbackground="OliveDrab",
        highlightthickness=1,
        width=3,
    )
    btn_actualizar.pack(side="left", padx=(0, 5))
    btn_actualizar.bind("<Enter>", lambda event: btn_actualizar.config(bg="OliveDrab"))
    btn_actualizar.bind("<Leave>", lambda event: btn_actualizar.config(bg="black"))
    btn_actualizar.tooltip = "Escanear puertos"
    btn_actualizar.configure(cursor="hand2")

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
            salida.delete("1.0", tk.END)
            salida.insert(tk.END, "No se detectaron puertos conectados\n")
            return

        if len(dispositivos) == 1:
            d = dispositivos[0]
            seleccion.set(d["puerto"])
            salida.delete("1.0", tk.END)
            salida.insert(tk.END, f"{d['puerto']} - {d['nombre']}\n", "ok")
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

        if dispositivos:
            seleccion.set(dispositivos[0]["puerto"])
            salida.delete("1.0", tk.END)
            salida.insert(tk.END, f"{dispositivos[0]['puerto']} - {dispositivos[0]['nombre']}\n", "ok")

    def escanear_async():
        barCarga.iniciar()

        def tarea():
            try:
                root.after(0, escanear)
            finally:
                root.after(0, barCarga.detener)

        threading.Thread(target=tarea, daemon=True).start()

    root.after(500, escanear_async)