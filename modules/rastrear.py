import tkinter as tk
import subprocess
import threading
import webbrowser
import re
import json
from datetime import datetime
from tkinter import filedialog, ttk
from .deteccion_puertos import obtener_puertos, parsear_puertos
from .estado_ui import BarCarga, IndicadorEstado
from .persistencia import cargar_boards, cargar_i2c, cargar_placas
from .rastreo_serial import leer_datos
from .rutas import configurar_ventana, user_data_path

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
    reporte_disponible = [False]
    reporte_actual = [{}]
    catalogo_i2c = cargar_i2c()
    reportes_file = user_data_path("reportes.json")

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

    frame_i2c = tk.Frame(main, bg="black")
    frame_i2c.pack(fill="x", padx=5, pady=(5, 0))

    tk.Label(frame_i2c, text="Dispositivos I2C detectados",
             fg="white", bg="black", anchor="w").pack(fill="x")

    estilo_tabla = ttk.Style()
    estilo_tabla.configure(
        "ArduinoHound.Treeview",
        background="black",
        foreground="white",
        fieldbackground="black",
        rowheight=22,
    )
    estilo_tabla.configure(
        "ArduinoHound.Treeview.Heading",
        background="black",
        foreground="white",
        relief="flat",
    )
    estilo_tabla.map(
        "ArduinoHound.Treeview.Heading",
        background=[("active", "black"), ("pressed", "black")],
    )
    tabla_i2c = ttk.Treeview(
        frame_i2c,
        columns=("direccion", "dispositivo", "descripcion"),
        show="headings",
        height=2,
        style="ArduinoHound.Treeview",
    )
    tabla_i2c.heading("direccion", text="Dirección")
    tabla_i2c.heading("dispositivo", text="Dispositivo posible")
    tabla_i2c.heading("descripcion", text="Descripción")
    tabla_i2c.column("direccion", width=65, minwidth=50, anchor="center", stretch=False)
    tabla_i2c.column("dispositivo", width=120, minwidth=100, anchor="w", stretch=False)
    tabla_i2c.column("descripcion", width=200, minwidth=180, anchor="w", stretch=False)
    tabla_i2c.pack(side="left", fill="x", expand=True)

    tabla_scroll = ttk.Scrollbar(frame_i2c, orient="vertical", command=tabla_i2c.yview)
    tabla_scroll.pack(side="right", fill="y")
    tabla_i2c.configure(yscrollcommand=tabla_scroll.set)

    salida = tk.Text(main, bg="black", fg="white", height=10)
    salida.pack(fill="both", expand=True)

    salida.tag_config("ok", foreground=COLOR_OK)

    def abrir_ventana_reporte():
        ventana = tk.Toplevel(root)
        ventana.title("Generar reporte")
        configurar_ventana(ventana)
        ventana.configure(bg="black")
        ventana.geometry("620x460")
        ventana.resizable(False, False)
        ventana.transient(root)
        ventana.grab_set()

        ventana.update_idletasks()
        x = (ventana.winfo_screenwidth() - ventana.winfo_width()) // 2
        y = (ventana.winfo_screenheight() - ventana.winfo_height()) // 2
        ventana.geometry(f"+{x}+{y}")

        tk.Label(
            ventana,
            text="Generar reporte",
            fg=COLOR_TITULO,
            bg="black",
            font=("Arial", 12, "bold"),
        ).pack(padx=24, pady=(18, 12))

        frame_datos = tk.Frame(ventana, bg="black")
        frame_datos.pack(fill="x", padx=20)

        ahora = datetime.now()
        tk.Label(frame_datos, text=f"Fecha: {ahora:%d/%m/%Y}", fg="white", bg="black").grid(row=0, column=0, sticky="w", padx=(0, 25))
        tk.Label(frame_datos, text=f"Hora: {ahora:%H:%M:%S}", fg="white", bg="black").grid(row=0, column=1, sticky="w")
        tk.Label(frame_datos, text="Nombre del equipo:", fg="white", bg="black").grid(row=1, column=0, sticky="w", pady=(10, 0))
        equipo_var = tk.StringVar()
        tk.Entry(frame_datos, textvariable=equipo_var, bg="#202020", fg="white", insertbackground="white", width=30).grid(row=1, column=1, sticky="w", pady=(10, 0))
        placa_label = tk.Label(frame_datos, text=f"Placa: {reporte_actual[0].get('fqbn', 'No disponible')}", fg="white", bg="black")
        placa_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

        tk.Label(ventana, text="I2C:", fg="white", bg="black", anchor="w").pack(fill="x", padx=20, pady=(14, 4))
        frame_i2c_reporte = tk.Frame(ventana, bg="black")
        frame_i2c_reporte.pack(fill="x", padx=20)

        def llenar_i2c_reporte():
            for widget in frame_i2c_reporte.winfo_children():
                widget.destroy()

            registros = reporte_actual[0].get("i2c", [])
            opciones_por_direccion = reporte_actual[0].get("i2c_opciones", {})
            seleccionados = reporte_actual[0].get("i2c_seleccion", {})

            if not registros:
                tk.Label(
                    frame_i2c_reporte,
                    text="No se detectaron dispositivos I2C",
                    fg="gray70",
                    bg="black",
                    anchor="w",
                ).pack(fill="x", pady=2)
                return

            def crear_fila_i2c(registro):
                direccion = registro["direccion"]
                fila = tk.Frame(frame_i2c_reporte, bg="black")
                fila.pack(fill="x", pady=2)
                tk.Label(
                    fila,
                    text=direccion,
                    fg="white",
                    bg="black",
                    anchor="w",
                    width=10,
                ).pack(side="left")

                opciones = opciones_por_direccion.get(direccion, [])
                descripciones = [
                    opcion.get("descripcion", "-") if isinstance(opcion, dict) else str(opcion)
                    for opcion in opciones
                ]
                dispositivos = [
                    opcion.get("dispositivo", "-") if isinstance(opcion, dict) else "-"
                    for opcion in opciones
                ]
                selector = ttk.Combobox(fila, values=descripciones, state="readonly", width=36)
                if opciones:
                    descripcion_guardada = seleccionados.get(direccion, descripciones[0])
                    selector.set(descripcion_guardada if descripcion_guardada in descripciones else descripciones[0])
                else:
                    selector.set("No identificado")
                selector.pack(side="left", padx=(8, 0))

                dispositivo_label = tk.Label(
                    fila,
                    text="",
                    fg="#7fe9ff",
                    bg="black",
                    anchor="w",
                    width=24,
                )
                dispositivo_label.pack(side="left", padx=(10, 0))

                def actualizar_dispositivo(_event=None):
                    indice = selector.current()
                    if 0 <= indice < len(dispositivos):
                        dispositivo = dispositivos[indice]
                        dispositivo_label.config(text=dispositivo)
                        reporte_actual[0].setdefault("i2c_seleccion", {})[direccion] = {
                            "descripcion": selector.get(),
                            "dispositivo": dispositivo,
                        }
                    else:
                        dispositivo_label.config(text="No identificado")

                actualizar_dispositivo()

                def guardar_seleccion(_event):
                    actualizar_dispositivo(_event)

                selector.bind("<<ComboboxSelected>>", guardar_seleccion)

            for registro in registros:
                crear_fila_i2c(registro)

        llenar_i2c_reporte()

        frame_reporte = tk.Frame(ventana, bg="black")
        frame_reporte.pack(padx=18, pady=(0, 18))

        def descargar_registros():
            ruta = filedialog.askopenfilename(
                title="Descargar registros",
                filetypes=[("Reportes JSON", "*.json"), ("Todos los archivos", "*.*")],
                parent=ventana,
            )
            if not ruta:
                return
            try:
                with open(ruta, "r", encoding="utf-8") as archivo:
                    registros = json.load(archivo)
                if isinstance(registros, list) and registros:
                    registros = registros[-1]
                equipo_var.set(registros.get("nombre_equipo", ""))
                placa_label.config(text=f"Placa: {registros.get('fqbn', 'No disponible')}")
                reporte_actual[0].update(registros)
                llenar_i2c_reporte()
            except (OSError, json.JSONDecodeError, AttributeError):
                return

        def guardar_reporte():
            registro = dict(reporte_actual[0])
            registro["nombre_equipo"] = equipo_var.get().strip()
            registro["fecha"] = datetime.now().strftime("%d/%m/%Y")
            registro["hora"] = datetime.now().strftime("%H:%M:%S")
            try:
                registros = []
                if reportes_file.exists():
                    with reportes_file.open("r", encoding="utf-8") as archivo:
                        datos_guardados = json.load(archivo)
                    registros = datos_guardados if isinstance(datos_guardados, list) else [datos_guardados]
                registros.append(registro)
                with reportes_file.open("w", encoding="utf-8") as archivo:
                    json.dump(registros, archivo, indent=4, ensure_ascii=False)
            except (OSError, json.JSONDecodeError):
                return
            boton_guardar.config(state="disabled")

        tk.Button(
            frame_reporte,
            text="⬇ Descargar registros",
            command=descargar_registros,
            bg="black", fg="white", highlightbackground="OliveDrab", highlightthickness=1,
        ).pack(side="left", padx=5)

        boton_guardar = tk.Button(
            frame_reporte,
            text="💾 Guardar reporte",
            command=guardar_reporte,
            bg="black",
            fg="white",
            highlightbackground="OliveDrab",
            highlightthickness=1,
        )
        boton_guardar.pack(side="left", padx=5)

        tk.Button(
            frame_reporte,
            text="🚪 Salir sin guardar",
            command=ventana.destroy,
            bg="black",
            fg="white",
            highlightbackground="OliveDrab",
            highlightthickness=1,
        ).pack(side="left", padx=5)

    boton_reporte = tk.Button(
        frame_btn,
        text="📄 Generar reporte",
        command=abrir_ventana_reporte,
        state="disabled",
        bg="black",
        fg="white",
        disabledforeground="gray30",
        highlightbackground="OliveDrab",
        highlightthickness=1,
    )
    boton_reporte.pack(side="left", padx=5)

    def actualizar_tabla_i2c(valor):
        tabla_i2c.delete(*tabla_i2c.get_children())
        direcciones = []
        for direccion in re.findall(r"0x[0-9a-fA-F]{1,2}", str(valor or "")):
            direccion = direccion.upper().replace("X", "x")
            if direccion.lower() not in {item.lower() for item in direcciones}:
                direcciones.append(direccion)

        registros_por_direccion = {}
        for registro in catalogo_i2c:
            direccion = str(registro.get("direccion", "")).lower()
            registros_por_direccion.setdefault(direccion, []).append(registro)

        for direccion in direcciones:
            registros = registros_por_direccion.get(direccion.lower(), [])
            if not registros:
                tabla_i2c.insert("", "end", values=(direccion, "No identificado", "Dirección I2C detectada"))
                continue
            registro = registros[0]
            tabla_i2c.insert(
                "", "end",
                values=(direccion, registro.get("dispositivo", "-"), registro.get("descripcion", "-")),
            )

        if not direcciones:
            tabla_i2c.insert("", "end", values=("-", "Ninguno", "No se detectaron dispositivos I2C"))

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

        valor_uart = str(datos.get("uart", ""))
        if "GPS" in valor_uart.upper():
            gps_detectado[0] = True
            boton_gps.config(text="GPS detectado", state="normal" if gps_coords_actuales[0] else "disabled")

        i2c_hay = str(datos.get('i2c', 'ninguno')).strip().lower() not in {'-', '', 'none', 'ninguno'}
        uart_hay = str(datos.get('uart', 'ninguno')).strip().lower() not in {'-', '', 'none', 'ninguno'}
        spi_hay = str(datos.get('spi', 'ninguno')).strip().lower() not in {'-', '', 'none', 'ninguno'}

        placas = cargar_placas()
        fqbn = placas.get(f"puerto_{puerto}", "")
        if not fqbn:
            for clave, placa in cargar_boards().items():
                if clave.lower() == str(datos.get("board", "")).strip().lower():
                    fqbn = placa.get("fqbn", "")
                    break

        direcciones = []
        for direccion in re.findall(r"0x[0-9a-fA-F]{1,2}", str(datos.get("i2c", ""))):
            direccion = direccion.upper().replace("X", "x")
            if direccion.lower() not in {item["direccion"].lower() for item in direcciones}:
                registros = [
                    item for item in catalogo_i2c
                    if str(item.get("direccion", "")).lower() == direccion.lower()
                ]
                direcciones.append({
                    "direccion": direccion,
                    "descripcion": registros[0].get("descripcion", "Dispositivo I2C") if registros else "Dirección I2C detectada",
                })

        reporte_actual[0] = {
            "fecha": datetime.now().strftime("%d/%m/%Y"),
            "hora": datetime.now().strftime("%H:%M:%S"),
            "nombre_equipo": "",
            "fqbn": fqbn or "No disponible",
            "i2c": direcciones,
            "i2c_opciones": {
                item["direccion"]: [
                    {
                        "descripcion": registro.get("descripcion", "-"),
                        "dispositivo": registro.get("dispositivo", "-"),
                    }
                    for registro in catalogo_i2c
                    if str(registro.get("direccion", "")).lower() == item["direccion"].lower()
                ]
                for item in direcciones
            },
        }

        reporte_disponible[0] = i2c_hay or uart_hay or gps_detectado[0] or spi_hay
        boton_reporte.config(state="normal" if reporte_disponible[0] else "disabled")

        indicador_i2c.resultado(i2c_hay)
        indicador_uart.resultado(uart_hay)
        indicador_spi.resultado(spi_hay)

        salida.insert(tk.END, "=== I2C ===\n")
        salida.insert(tk.END, f"Pines del bus: {datos.get('i2c_pines', 'No disponibles')}\n")
        actualizar_tabla_i2c(datos["i2c"])
        salida.insert(tk.END, "Consultar la tabla superior para ver las coincidencias por dirección.\n\n")

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
        configurar_ventana(ventana)
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
        reporte_disponible[0] = False
        debug_output.delete("1.0", tk.END)
        boton_gps.config(text="🌐", state="disabled", bg="black", fg="white")
        boton_reporte.config(state="disabled")

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