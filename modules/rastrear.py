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
from .persistencia import cargar_boards, cargar_i2c, cargar_json, cargar_placas
from .rastreo_serial import leer_datos
from .rutas import configurar_ventana, resource_path, user_data_path

COLOR_TITULO = "OliveDrab2"
COLOR_OK = "green"


def _normalizar_valor_spi(valor):
    texto = str(valor or "").strip().upper()
    if texto.startswith("0X"):
        texto = texto[2:]
    try:
        return format(int(texto, 16), "X")
    except ValueError:
        return texto


def _buscar_descripcion_spi(nombre, comando, data, catalogo):
    nombre_normalizado = re.sub(r"[^A-Z0-9]", "", str(nombre).upper())
    if nombre_normalizado == "TARJETASD":
        nombre_normalizado = "SDCARD"

    comando_normalizado = _normalizar_valor_spi(comando)
    comandos_equivalentes = {comando_normalizado}
    if comando_normalizado and not comando_normalizado.startswith("CMD"):
        try:
            comandos_equivalentes.add(format(int(comando_normalizado, 16) & 0x7F, "X"))
        except ValueError:
            pass

    candidatos = [
        dispositivo for dispositivo in catalogo
        if _normalizar_valor_spi(dispositivo.get("cmd")) in comandos_equivalentes
    ]

    if candidatos:
        data_normalizada = _normalizar_valor_spi(data)
        coincidencias_data = [
            dispositivo for dispositivo in candidatos
            if _normalizar_valor_spi(dispositivo.get("data")) == data_normalizada
        ]
        if coincidencias_data:
            candidatos = coincidencias_data

        if len(candidatos) == 1:
            return candidatos[0].get("description", "-")

        for dispositivo in candidatos:
            nombre_catalogo = re.sub(
                r"[^A-Z0-9]", "", str(dispositivo.get("name", "")).upper()
            )
            if nombre_normalizado == nombre_catalogo or nombre_normalizado.endswith(nombre_catalogo):
                return dispositivo.get("description", "-")

        return candidatos[0].get("description", "-")

    for dispositivo in catalogo:
        nombre_catalogo = re.sub(
            r"[^A-Z0-9]", "", str(dispositivo.get("name", "")).upper()
        )
        if nombre_normalizado == nombre_catalogo or nombre_normalizado.endswith(nombre_catalogo):
            return dispositivo.get("description", "-")

    return "-"


def _parsear_dispositivo_uart(linea):
    partes = str(linea).strip().split(";")
    if not partes or not partes[0].startswith("UART_DEV:"):
        return None

    nombre = partes[0].partition(":")[2].strip()
    if not nombre or nombre.upper() in {"UNKNOWN", "NONE", "-"}:
        nombre = "Desconocido"

    campos = {}
    for parte in partes[1:]:
        clave, separador, valor = parte.partition("=")
        if separador:
            campos[clave.strip().upper()] = valor.strip()

    rx = campos.get("RX", "-") or "-"
    tx = campos.get("TX", "-") or "-"
    return rx, tx, nombre


def liberar_puertos():
    """Cierra procesos conocidos que suelen mantener abierto un puerto serial."""
    procesos = [
        "arduino.exe",
        "arduino_debug.exe",
        "arduino-cli.exe",
        "Arduino IDE.exe",
        "arduino-ide.exe",
        "putty.exe",
        "ttermpro.exe",
        "teraterm.exe",
        "realterm.exe",
        "CoolTerm.exe",
        "serial-monitor.exe",
    ]

    for proceso in procesos:
        try:
            subprocess.run([
                "taskkill",
                "/F",
                "/T",
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
    escaneo_activo = [False]
    rastreo_cancelacion = [None]
    rastreo_hilo = [None]
    version_escaneo_puertos = [0]
    catalogo_i2c = cargar_i2c()
    catalogo_spi_json = cargar_json(
        resource_path("data", "dispositivos_spi.json"), {"spi_devices": []}
    )
    catalogo_spi = catalogo_spi_json.get("spi_devices", [])
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

    frame_resultados = tk.Frame(main, bg="black")
    frame_resultados.pack(fill="both", expand=True, padx=5, pady=(5, 0))
    frame_resultados.grid_columnconfigure(0, weight=1, uniform="resultados")
    frame_resultados.grid_columnconfigure(1, weight=1, uniform="resultados")
    frame_resultados.grid_rowconfigure(0, weight=1)

    frame_tablas = tk.Frame(frame_resultados, bg="black")
    frame_tablas.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

    frame_diagnostico = tk.Frame(frame_resultados, bg="black")
    frame_diagnostico.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

    frame_i2c = tk.Frame(frame_tablas, bg="black")
    frame_i2c.pack(fill="x", pady=(0, 5))

    tk.Label(frame_i2c, text="Dispositivos I2C",
             fg="white", bg="black", anchor="w").pack(fill="x")

    estilo_tabla = ttk.Style()
    estilo_tabla.configure(
        "ArduinoHound.Treeview",
        background="black",
        foreground="cyan",
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
    tabla_i2c.column("direccion", width=60, minwidth=45, anchor="center", stretch=False)
    tabla_i2c.column("dispositivo", width=105, minwidth=80, anchor="w", stretch=False)
    tabla_i2c.column("descripcion", width=180, minwidth=140, anchor="w", stretch=True)
    tabla_i2c.pack(side="left", fill="x", expand=True)

    tabla_scroll = ttk.Scrollbar(frame_i2c, orient="vertical", command=tabla_i2c.yview)
    tabla_scroll.pack(side="right", fill="y")
    tabla_i2c.configure(yscrollcommand=tabla_scroll.set)

    frame_uart = tk.Frame(frame_tablas, bg="black")
    frame_uart.pack(fill="x", pady=(0, 5))

    tk.Label(frame_uart, text="Dispositivos UART",
             fg="white", bg="black", anchor="w").pack(fill="x")

    tabla_uart = ttk.Treeview(
        frame_uart,
        columns=("rx", "tx", "nombre"),
        show="headings",
        height=2,
        style="ArduinoHound.Treeview",
    )
    tabla_uart.heading("rx", text="RX")
    tabla_uart.heading("tx", text="TX")
    tabla_uart.heading("nombre", text="Descripción")
    tabla_uart.column("rx", width=75, minwidth=60, anchor="center", stretch=False)
    tabla_uart.column("tx", width=75, minwidth=60, anchor="center", stretch=False)
    tabla_uart.column("nombre", width=190, minwidth=130, anchor="w", stretch=True)
    tabla_uart.pack(side="left", fill="x", expand=True)

    tabla_uart_scroll = ttk.Scrollbar(frame_uart, orient="vertical", command=tabla_uart.yview)
    tabla_uart_scroll.pack(side="right", fill="y")
    tabla_uart.configure(yscrollcommand=tabla_uart_scroll.set)

    frame_spi = tk.Frame(frame_tablas, bg="black")
    frame_spi.pack(fill="x")

    tk.Label(frame_spi, text="Dispositivos SPI",
             fg="white", bg="black", anchor="w").pack(fill="x")

    tabla_spi = ttk.Treeview(
        frame_spi,
        columns=("cs", "cmd", "data", "descripcion"),
        show="headings",
        height=2,
        style="ArduinoHound.Treeview",
    )
    tabla_spi.heading("cs", text="CS (Chip Select)")
    tabla_spi.heading("cmd", text="CMD")
    tabla_spi.heading("data", text="Data")
    tabla_spi.heading("descripcion", text="Descripción")
    tabla_spi.column("cs", width=90, minwidth=75, anchor="center", stretch=False)
    tabla_spi.column("cmd", width=60, minwidth=50, anchor="center", stretch=False)
    tabla_spi.column("data", width=80, minwidth=65, anchor="center", stretch=False)
    tabla_spi.column("descripcion", width=170, minwidth=120, anchor="w", stretch=True)
    tabla_spi.pack(side="left", fill="x", expand=True)

    tabla_spi_scroll = ttk.Scrollbar(frame_spi, orient="vertical", command=tabla_spi.yview)
    tabla_spi_scroll.pack(side="right", fill="y")
    tabla_spi.configure(yscrollcommand=tabla_spi_scroll.set)

    salida = tk.Text(frame_diagnostico, bg="black", fg="white", height=10)
    salida.pack(fill="both", expand=True)

    salida.tag_config("ok", foreground=COLOR_OK)

    def abrir_ventana_reporte():
        ventana = tk.Toplevel(root)
        ventana.title("Generar reporte")
        configurar_ventana(ventana)
        ventana.configure(bg="black")
        ventana.geometry("1040x660")
        ventana.resizable(False, False)
        ventana.transient(root)
        ventana.grab_set()

        ventana.update_idletasks()
        ventana.after(10, configurar_ventana, ventana)
        x = (ventana.winfo_screenwidth() - ventana.winfo_width()) // 2
        y = (ventana.winfo_screenheight() - ventana.winfo_height()) // 2
        ventana.geometry(f"+{x}+{y}")

        tk.Label(
            ventana,
            text="Generar reporte",
            fg=COLOR_TITULO,
            bg="black",
            font=("Arial", 10, "bold"),
        ).pack(padx=24, pady=(18, 12))

        fuente_clave = ("Arial", 10)
        fuente_valor = ("Arial", 10, "bold")
        color_valor = "cyan"
        estilo_reporte = ttk.Style(ventana)
        estilo_reporte.configure(
            "Reporte.TCombobox",
            fieldbackground="#202020",
            foreground=color_valor,
            font=fuente_valor,
        )
        estilo_reporte.configure(
            "Reporte.Treeview",
            background="black",
            foreground=color_valor,
            fieldbackground="black",
            borderwidth=0,
            relief="flat",
            rowheight=24,
        )
        estilo_reporte.configure(
            "Reporte.Treeview.Heading",
            background="black",
            foreground="white",
            borderwidth=0,
            relief="flat",
        )
        estilo_reporte.map(
            "Reporte.Treeview.Heading",
            background=[("active", "black"), ("pressed", "black")],
        )
        ahora = datetime.now()

        frame_fecha_hora = tk.Frame(ventana, bg="black")
        frame_fecha_hora.pack(fill="x", padx=20)
        for columna, peso in enumerate((1, 2, 1)):
            frame_fecha_hora.grid_columnconfigure(columna, weight=peso)
        fecha_frame = tk.Frame(frame_fecha_hora, bg="black")
        fecha_frame.grid(row=0, column=0, sticky="w")
        tk.Label(fecha_frame, text="Fecha:", fg="white", bg="black", font=fuente_clave).pack(side="left")
        tk.Label(fecha_frame, text=f"{ahora:%d/%m/%Y}", fg=color_valor, bg="black", font=fuente_valor).pack(side="left", padx=(5, 0))
        etiqueta_total = tk.Label(
            frame_fecha_hora,
            text="0 dispositivos encontrados.",
            fg=color_valor,
            bg="black",
            font=fuente_valor,
            anchor="center",
        )
        etiqueta_total.grid(row=0, column=1, sticky="ew")
        hora_frame = tk.Frame(frame_fecha_hora, bg="black")
        hora_frame.grid(row=0, column=2, sticky="e")
        tk.Label(hora_frame, text="Hora:", fg="white", bg="black", font=fuente_clave).pack(side="left")
        tk.Label(hora_frame, text=f"{ahora:%H:%M:%S}", fg=color_valor, bg="black", font=fuente_valor).pack(side="left", padx=(5, 0))

        tk.Frame(ventana, bg="white", height=1).pack(fill="x", padx=20, pady=(10, 12))

        frame_datos = tk.Frame(ventana, bg="black")
        frame_datos.pack(fill="x", padx=20)
        frame_datos.grid_columnconfigure(0, weight=1, uniform="datos_reporte")
        frame_datos.grid_columnconfigure(1, weight=1, uniform="datos_reporte")

        frame_datos_izquierda = tk.Frame(frame_datos, bg="black")
        frame_datos_izquierda.grid(row=0, column=0, sticky="new", padx=(0, 24))
        frame_datos_izquierda.grid_columnconfigure(0, minsize=210, weight=0)
        frame_datos_izquierda.grid_columnconfigure(1, weight=1)

        frame_datos_derecha = tk.Frame(frame_datos, bg="black")
        frame_datos_derecha.grid(row=0, column=1, sticky="new", padx=(24, 0))
        frame_datos_derecha.grid_columnconfigure(0, minsize=55, weight=0)
        frame_datos_derecha.grid_columnconfigure(1, weight=1)

        def agregar_clave(marco, fila, texto):
            tk.Label(
            marco,
                text=texto,
                fg="white",
                bg="black",
                font=fuente_clave,
                anchor="nw",
                wraplength=205,
            ).grid(row=fila, column=0, sticky="nw", pady=4)

        agregar_clave(frame_datos_izquierda, 0, "Nombre del equipo:")
        equipo_var = tk.StringVar()
        tk.Entry(
            frame_datos_izquierda,
            textvariable=equipo_var,
            bg="#202020",
            fg=color_valor,
            insertbackground=color_valor,
            font=fuente_valor,
            width=18,
        ).grid(row=0, column=1, sticky="ew", pady=4)

        agregar_clave(frame_datos_izquierda, 1, "Placa:")
        placa_label = tk.Label(
            frame_datos_izquierda,
            text=reporte_actual[0].get("board", "No disponible"),
            fg=color_valor,
            bg="black",
            font=fuente_valor,
            anchor="w",
            wraplength=150,
        )
        placa_label.grid(row=1, column=1, sticky="w", pady=4)

        agregar_clave(
            frame_datos_izquierda,
            2,
            "FQBN (Nombre de Placa Totalmente Calificado):",
        )
        fqbn_label = tk.Label(
            frame_datos_izquierda,
            text=reporte_actual[0].get("fqbn", "No disponible"),
            fg=color_valor,
            bg="black",
            font=fuente_valor,
            anchor="w",
            wraplength=260,
        )
        fqbn_label.grid(row=2, column=1, sticky="w", pady=4)

        etiquetas_resumen = {}
        dispositivos_modificados = {"I2C": False, "UART": False, "SPI": False}
        filas_protocolo = {"I2C": 0, "UART": 1, "SPI": 2}
        for protocolo, fila in filas_protocolo.items():
            agregar_clave(frame_datos_derecha, fila, f"{protocolo}:")
            etiquetas_resumen[protocolo] = tk.Label(
                frame_datos_derecha,
                text="Ninguno",
                fg="VioletRed1",
                bg="black",
                font=fuente_valor,
                anchor="nw",
                justify="left",
                wraplength=360,
            )
            etiquetas_resumen[protocolo].grid(row=fila, column=1, sticky="ew", pady=4)

        def actualizar_resumen_reporte():
            registro = reporte_actual[0]
            seleccionados = registro.get("i2c_seleccion", {})
            dispositivos_i2c = []
            for dispositivo in registro.get("i2c", []):
                direccion = dispositivo.get("direccion", "")
                seleccion = seleccionados.get(direccion, {})
                nombre_dispositivo = (
                    seleccion.get("dispositivo", "")
                    if isinstance(seleccion, dict)
                    else str(seleccion or "")
                )
                if not nombre_dispositivo:
                    opciones = registro.get("i2c_opciones", {}).get(direccion, [])
                    if opciones:
                        nombre_dispositivo = opciones[0].get("dispositivo", "")
                dispositivos_i2c.append(
                    str(nombre_dispositivo or "No identificado").strip()
                )

            uart = [
                modulo.split("(", 1)[0].strip()
                for modulo in str(registro.get("uart", "")).split(" | ")
                if modulo.strip().lower() not in {"", "-", "none", "ninguno"}
            ]
            spi = []
            for modulo in str(registro.get("spi", "")).split(","):
                nombre = modulo.split(";", 1)[0].strip()
                if nombre.lower() not in {"", "-", "none", "ninguno"}:
                    spi.append(nombre)

            for protocolo, dispositivos in (("I2C", dispositivos_i2c), ("UART", uart), ("SPI", spi)):
                etiqueta = etiquetas_resumen[protocolo]
                etiqueta.config(
                    text=", ".join(dispositivos) if dispositivos else "Ninguno",
                    fg=(
                        "greenyellow"
                        if dispositivos_modificados[protocolo]
                        else color_valor if dispositivos else "VioletRed1"
                    ),
                )
            total = len(dispositivos_i2c) + len(uart) + len(spi)
            etiqueta_total.config(text=f"{total} dispositivos encontrados.")

        marco_tabla_i2c = tk.Frame(ventana, bg="black")
        marco_tabla_i2c.pack(fill="x", expand=False, padx=0, pady=(12, 0))
        for columna in range(3):
            marco_tabla_i2c.grid_columnconfigure(columna, weight=1, uniform="reporte_protocolos")

        tabla_i2c = tk.Frame(
            marco_tabla_i2c,
            bg="black",
            highlightbackground="white",
            highlightcolor="white",
            highlightthickness=1,
        )
        tabla_i2c.grid(row=0, column=0, sticky="new", padx=0)
        tabla_i2c.grid_columnconfigure(0, minsize=150, weight=0)
        tabla_i2c.grid_columnconfigure(1, minsize=150, weight=0)

        tk.Label(
            tabla_i2c,
            text="Direcciones I2C",
            fg="white",
            bg="black",
            font=fuente_valor,
            anchor="w",
        ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        tk.Label(
            tabla_i2c,
            text="Dirección",
            fg="white",
            bg="black",
            font=fuente_valor,
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=(0, 12), pady=(0, 4))
        tk.Label(
            tabla_i2c,
            text="Dispositivo",
            fg="white",
            bg="black",
            font=fuente_valor,
            anchor="w",
        ).grid(row=1, column=1, sticky="ew", pady=(0, 4))

        cuerpo_tabla = tk.Frame(tabla_i2c, bg="black", height=34)
        cuerpo_tabla.grid(row=2, column=0, columnspan=2, sticky="nsew")
        cuerpo_tabla.grid_propagate(False)
        tabla_i2c.grid_rowconfigure(2, weight=1)
        lienzo_i2c = tk.Canvas(cuerpo_tabla, bg="black", highlightthickness=0)
        lienzo_i2c.pack(side="left", fill="both", expand=True)
        filas_i2c = tk.Frame(lienzo_i2c, bg="black")
        ventana_filas_i2c = lienzo_i2c.create_window((0, 0), window=filas_i2c, anchor="nw")
        filas_i2c.grid_columnconfigure(0, minsize=150, weight=0)
        filas_i2c.grid_columnconfigure(1, minsize=150, weight=0)
        filas_i2c.bind(
            "<Configure>",
            lambda _event: lienzo_i2c.configure(scrollregion=lienzo_i2c.bbox("all")),
        )
        lienzo_i2c.bind(
            "<Configure>",
            lambda event: lienzo_i2c.itemconfigure(ventana_filas_i2c, width=event.width),
        )

        etiqueta_scroll_i2c = f"ScrollI2C{ventana}"
        lienzos_por_widget = {}

        def desplazar_tabla_i2c(event):
            if getattr(event, "num", None) == 4:
                desplazamiento = -1
            elif getattr(event, "num", None) == 5:
                desplazamiento = 1
            else:
                desplazamiento = -1 if event.delta > 0 else 1
            lienzo = lienzos_por_widget.get(event.widget, lienzo_i2c)
            lienzo.yview_scroll(desplazamiento, "units")
            return "break"

        ventana.bind_class(etiqueta_scroll_i2c, "<MouseWheel>", desplazar_tabla_i2c)
        ventana.bind_class(etiqueta_scroll_i2c, "<Button-4>", desplazar_tabla_i2c)
        ventana.bind_class(etiqueta_scroll_i2c, "<Button-5>", desplazar_tabla_i2c)

        def agregar_etiqueta_scroll(widget, lienzo):
            lienzos_por_widget[widget] = lienzo
            widget.bindtags((etiqueta_scroll_i2c, *widget.bindtags()))
            for hijo in widget.winfo_children():
                agregar_etiqueta_scroll(hijo, lienzo)

        def crear_tabla_protocolo(columna, titulo, columnas):
            marco = tk.Frame(
                marco_tabla_i2c,
                bg="black",
                highlightbackground="white",
                highlightcolor="white",
                highlightthickness=1,
            )
            marco.grid(row=0, column=columna, sticky="new", padx=0)
            tk.Label(
                marco,
                text=titulo,
                fg="white",
                bg="black",
                font=fuente_valor,
                anchor="w",
            ).grid(row=0, column=0, columnspan=len(columnas), sticky="ew", pady=(0, 4))

            encabezados = tk.Frame(marco, bg="black")
            encabezados.grid(row=1, column=0, sticky="ew")
            filas = tk.Frame(marco, bg="black", height=34)
            filas.grid(row=2, column=0, sticky="ew")
            filas.grid_propagate(False)
            lienzo = tk.Canvas(filas, bg="black", highlightthickness=0)
            lienzo.pack(fill="both", expand=True)
            filas_datos = tk.Frame(lienzo, bg="black")
            ventana_filas = lienzo.create_window((0, 0), window=filas_datos, anchor="nw")

            for indice, (identificador, encabezado, ancho) in enumerate(columnas):
                encabezados.grid_columnconfigure(indice, minsize=ancho, weight=1)
                filas_datos.grid_columnconfigure(indice, minsize=ancho, weight=1)
                tk.Label(
                    encabezados,
                    text=encabezado,
                    fg="white",
                    bg="black",
                    font=fuente_valor,
                    anchor="w",
                ).grid(row=0, column=indice, sticky="ew", padx=(0, 8), pady=(0, 4))

            filas_datos.bind(
                "<Configure>",
                lambda _event, lienzo=lienzo: lienzo.configure(
                    scrollregion=lienzo.bbox("all")
                ),
            )
            lienzo.bind(
                "<Configure>",
                lambda event, lienzo=lienzo, ventana_filas=ventana_filas:
                    lienzo.itemconfigure(ventana_filas, width=event.width),
            )
            agregar_etiqueta_scroll(filas_datos, lienzo)
            return lienzo, filas_datos, columnas

        lienzo_uart, filas_uart, columnas_uart = crear_tabla_protocolo(
            1,
            "Direcciones UART",
            (("rx", "RX", 55), ("tx", "TX", 55), ("set", "SET", 55), ("nombre", "Dispositivo", 150)),
        )
        lienzo_spi, filas_spi, columnas_spi = crear_tabla_protocolo(
            2,
            "Direcciones SPI",
            (("cs", "CS", 55), ("nombre", "Dispositivo", 105), ("cmd", "CMD", 55), ("data", "Data", 75)),
        )

        def insertar_fila_tabla(
            filas, columnas, numero, valores, columna_editable=None, al_editar=None
        ):
            for indice, valor in enumerate(valores):
                if indice == columna_editable:
                    campo = tk.Entry(
                        filas,
                        bg="black",
                        fg=color_valor,
                        insertbackground=color_valor,
                        font=fuente_valor,
                        relief="flat",
                        highlightthickness=0,
                    )
                    campo.insert(0, str(valor))
                    campo.grid(
                        row=numero,
                        column=indice,
                        sticky="ew",
                        padx=(0, 8),
                        pady=3,
                    )
                    if al_editar is not None:
                        campo.bind(
                            "<FocusOut>",
                            lambda _event, campo=campo: al_editar(campo),
                        )
                else:
                    tk.Label(
                        filas,
                        text=valor,
                        fg=color_valor,
                        bg="black",
                        font=fuente_valor,
                        anchor="w",
                    ).grid(row=numero, column=indice, sticky="ew", padx=(0, 8), pady=3)

        def llenar_tablas_uart_spi_reporte():
            for widget in filas_uart.winfo_children():
                widget.destroy()
            modulos_uart = [
                modulo.strip()
                for modulo in str(reporte_actual[0].get("uart", "")).split(" | ")
                if modulo.strip().lower() not in {"", "-", "none", "ninguno"}
            ]
            for fila, modulo in enumerate(modulos_uart):
                coincidencia = re.match(
                    r"^(.*?)\s*\(RX=([^,]+),\s*TX=([^,)]+)", modulo
                )
                if coincidencia:
                    nombre, rx, tx = (parte.strip() for parte in coincidencia.groups())
                else:
                    nombre, rx, tx = modulo, "-", "-"
                coincidencia_set = re.search(r"\bSET=([^,\)\s]+)", modulo)
                set_pin = coincidencia_set.group(1).strip() if coincidencia_set else "-"

                def actualizar_nombre_uart(
                    campo,
                    fila=fila,
                    modulo_original=modulo,
                    nombre_original=nombre,
                ):
                    nombre_nuevo = campo.get().strip() or nombre_original
                    campo.delete(0, tk.END)
                    campo.insert(0, nombre_nuevo)
                    modulos_actuales = str(reporte_actual[0].get("uart", "")).split(" | ")
                    if fila >= len(modulos_actuales):
                        return
                    sufijo = modulo_original[len(nombre_original):]
                    modulos_actuales[fila] = nombre_nuevo + sufijo
                    reporte_actual[0]["uart"] = " | ".join(modulos_actuales)
                    if nombre_nuevo != nombre_original:
                        dispositivos_modificados["UART"] = True
                        campo.configure(fg="greenyellow")
                    else:
                        campo.configure(fg=color_valor)
                    actualizar_resumen_reporte()

                insertar_fila_tabla(
                    filas_uart,
                    columnas_uart,
                    fila,
                    (rx, tx, set_pin, nombre or "Desconocido"),
                    columna_editable=3,
                    al_editar=actualizar_nombre_uart,
                )
            if not modulos_uart:
                insertar_fila_tabla(filas_uart, columnas_uart, 0, ("-", "-", "-", "Ninguno"))
            agregar_etiqueta_scroll(filas_uart, lienzo_uart)

            for widget in filas_spi.winfo_children():
                widget.destroy()
            modulos_spi = []
            for modulo in str(reporte_actual[0].get("spi", "")).split(","):
                partes = modulo.strip().split(";")
                nombre = partes[0].strip()
                if nombre.lower() in {"", "-", "none", "ninguno"}:
                    continue
                campos = {}
                for parte in partes[1:]:
                    clave, separador, valor = parte.partition("=")
                    if separador:
                        campos[clave.strip().upper()] = valor.strip()
                modulos_spi.append({
                    "original": modulo.strip(),
                    "name": nombre,
                    "values": (
                        campos.get("CS", "-"),
                        nombre,
                        campos.get("CMD", "-"),
                        campos.get("DATA", "-"),
                    ),
                })
            if modulos_spi:
                for fila, modulo in enumerate(modulos_spi):
                    def actualizar_nombre_spi(
                        campo,
                        fila=fila,
                        original=modulo["original"],
                        nombre_original=modulo["name"],
                    ):
                        nombre_nuevo = campo.get().strip() or nombre_original
                        campo.delete(0, tk.END)
                        campo.insert(0, nombre_nuevo)
                        modulos_actuales = str(reporte_actual[0].get("spi", "")).split(",")
                        if fila >= len(modulos_actuales):
                            return
                        sufijo = original[len(nombre_original):]
                        modulos_actuales[fila] = nombre_nuevo + sufijo
                        reporte_actual[0]["spi"] = ",".join(modulos_actuales)
                        if nombre_nuevo != nombre_original:
                            dispositivos_modificados["SPI"] = True
                            campo.configure(fg="greenyellow")
                        else:
                            campo.configure(fg=color_valor)
                        actualizar_resumen_reporte()

                    insertar_fila_tabla(
                        filas_spi,
                        columnas_spi,
                        fila,
                        modulo["values"],
                        columna_editable=1,
                        al_editar=actualizar_nombre_spi,
                    )
            else:
                insertar_fila_tabla(filas_spi, columnas_spi, 0, ("-", "Ninguno", "-", "-"))
            agregar_etiqueta_scroll(filas_spi, lienzo_spi)

        def llenar_i2c_reporte():
            for widget in filas_i2c.winfo_children():
                widget.destroy()

            registros = reporte_actual[0].get("i2c", [])
            seleccionados = reporte_actual[0].get("i2c_seleccion", {})
            actualizar_resumen_reporte()
            llenar_tablas_uart_spi_reporte()

            if not registros:
                tk.Label(
                    filas_i2c,
                    text="Ninguno",
                    fg="VioletRed1",
                    bg="black",
                    font=fuente_valor,
                    anchor="w",
                ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=4)
                agregar_etiqueta_scroll(filas_i2c, lienzo_i2c)
                return

            direcciones_vistas = set()
            fila_numero = 0
            for registro in registros:
                direccion = str(registro.get("direccion", "")).strip()
                clave_direccion = direccion.lower()
                if not direccion or clave_direccion in direcciones_vistas:
                    continue
                direcciones_vistas.add(clave_direccion)

                tk.Label(
                    filas_i2c,
                    text=direccion,
                    fg=color_valor,
                    bg="black",
                    font=fuente_valor,
                    anchor="w",
                ).grid(row=fila_numero, column=0, sticky="ew", padx=(0, 12), pady=3)

                opciones = [
                    opcion
                    for opcion in catalogo_i2c
                    if str(opcion.get("direccion", "")).strip().lower() == clave_direccion
                ]
                nombres = [str(opcion.get("dispositivo", "No identificado")) for opcion in opciones]
                selector_frame = tk.Frame(filas_i2c, bg="black", width=150, height=28)
                selector_frame.grid(row=fila_numero, column=1, sticky="w", pady=3)
                selector_frame.grid_propagate(False)
                selector = ttk.Combobox(
                    selector_frame,
                    values=nombres,
                    state="normal",
                    width=48,
                    font=fuente_valor,
                    style="Reporte.TCombobox",
                )
                selector.place(x=0, y=0, width=150, height=28)
                seleccion_guardada = seleccionados.get(direccion, {})
                dispositivo_guardado = (
                    seleccion_guardada.get("dispositivo", "")
                    if isinstance(seleccion_guardada, dict)
                    else str(seleccion_guardada)
                )
                dispositivo_inicial = (
                    dispositivo_guardado
                    or (nombres[0] if nombres else "No identificado")
                )
                selector.set(dispositivo_inicial)

                def actualizar_dispositivo(
                    _event=None,
                    selector=selector,
                    direccion=direccion,
                    opciones=opciones,
                    dispositivo_inicial=dispositivo_inicial,
                ):
                    dispositivo = selector.get().strip()
                    if not dispositivo:
                        dispositivo = dispositivo_inicial
                        selector.set(dispositivo)
                    opcion = next(
                        (item for item in opciones if str(item.get("dispositivo", "")) == dispositivo),
                        None,
                    )
                    reporte_actual[0].setdefault("i2c_seleccion", {})[direccion] = {
                        "descripcion": opcion.get("descripcion", "Personalizado") if opcion else "Personalizado",
                        "dispositivo": dispositivo,
                    }
                    if dispositivo != dispositivo_inicial:
                        dispositivos_modificados["I2C"] = True
                        selector.configure(foreground="greenyellow")
                    else:
                        selector.configure(foreground=color_valor)
                    actualizar_resumen_reporte()

                selector.bind("<<ComboboxSelected>>", actualizar_dispositivo)
                selector.bind("<FocusOut>", actualizar_dispositivo)
                agregar_etiqueta_scroll(selector, lienzo_i2c)
                actualizar_dispositivo()
                fila_numero += 1

            agregar_etiqueta_scroll(filas_i2c, lienzo_i2c)

        llenar_i2c_reporte()

        frame_reporte = tk.Frame(ventana, bg="black")
        frame_reporte.pack(padx=18, pady=(0, 18))

        def ver_registros():
            try:
                with reportes_file.open("r", encoding="utf-8") as archivo:
                    registros = json.load(archivo)
            except (OSError, json.JSONDecodeError):
                messagebox.showinfo(
                    "Ver registros",
                    "No hay reportes guardados.",
                    parent=ventana,
                )
                return

            if isinstance(registros, dict):
                registros = [registros]
            if not isinstance(registros, list) or not registros:
                messagebox.showinfo(
                    "Ver registros",
                    "No hay reportes guardados.",
                    parent=ventana,
                )
                return

            ventana_registros = tk.Toplevel(ventana)
            ventana_registros.title("Registros guardados")
            configurar_ventana(ventana_registros)
            ventana_registros.after(10, configurar_ventana, ventana_registros)
            ventana_registros.configure(bg="black")
            ventana_registros.geometry("760x480")
            ventana_registros.resizable(False, False)
            ventana_registros.transient(ventana)

            lista_registros = ttk.Treeview(
                ventana_registros,
                columns=("fecha", "hora", "equipo", "placa"),
                show="headings",
                height=8,
                style="Reporte.Treeview",
            )
            for clave, encabezado, ancho in (
                ("fecha", "Fecha", 90),
                ("hora", "Hora", 80),
                ("equipo", "Equipo", 210),
                ("placa", "Placa", 280),
            ):
                lista_registros.heading(clave, text=encabezado)
                lista_registros.column(clave, width=ancho, anchor="w", stretch=True)
            lista_registros.pack(fill="x", padx=16, pady=(16, 8))

            detalles_registro = tk.Text(
                ventana_registros,
                bg="black",
                fg=color_valor,
                height=8,
                wrap="word",
                relief="flat",
                highlightthickness=0,
            )
            detalles_registro.pack(fill="both", expand=True, padx=16, pady=(0, 16))
            registros_por_id = {}
            for indice, registro in enumerate(registros):
                if not isinstance(registro, dict):
                    continue
                identificador = str(indice)
                registros_por_id[identificador] = registro
                lista_registros.insert(
                    "",
                    "end",
                    iid=identificador,
                    values=(
                        registro.get("fecha", "-"),
                        registro.get("hora", "-"),
                        registro.get("nombre_equipo", "-"),
                        registro.get("board", "-"),
                    ),
                )

            def mostrar_detalle_registro(_event=None):
                seleccion = lista_registros.selection()
                if not seleccion:
                    return
                registro = registros_por_id.get(seleccion[0], {})
                detalles_registro.delete("1.0", tk.END)
                detalles_registro.insert(
                    tk.END, json.dumps(registro, ensure_ascii=False, indent=2)
                )

            lista_registros.bind("<<TreeviewSelect>>", mostrar_detalle_registro)
            ventana_registros.grab_set()

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
            messagebox.showinfo(
                "Generar reporte",
                "El reporte se guardó correctamente.",
                parent=ventana,
            )

        tk.Button(
            frame_reporte,
            text="Ver registros",
            command=ver_registros,
            bg="black", fg="white", highlightbackground="OliveDrab", highlightthickness=1,
        ).pack(side="left", padx=5)

        boton_guardar = tk.Button(
            frame_reporte,
            text="Generar reporte",
            command=guardar_reporte,
            bg="black",
            fg="white",
            highlightbackground="OliveDrab",
            highlightthickness=1,
        )
        boton_guardar.pack(side="left", padx=5)

        boton_salir = tk.Button(
            frame_reporte,
            text="Salir sin guardar",
            command=ventana.destroy,
            bg="black",
            fg="white",
            highlightbackground="OliveDrab",
            highlightthickness=1,
        )
        boton_salir.pack(side="left", padx=5)
        boton_salir.configure(default="active")
        ventana.after_idle(boton_salir.focus_set)

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

    frame_debug = tk.Frame(frame_diagnostico, bg="black", highlightbackground="white", highlightthickness=1)
    frame_debug.pack(fill="both", expand=True, pady=(5, 0))

    tk.Label(frame_debug, text="Diagnóstico en tiempo real", fg="#7fe9ff", bg="black", font=("Arial", 10, "bold")).pack(anchor="w", padx=5, pady=(5, 0))
    debug_output = tk.Text(frame_debug, bg="black", fg="#7fe9ff", height=7)
    debug_output.pack(fill="both", expand=True, padx=5, pady=5)

    debug_output.tag_config("debug", foreground="#7fe9ff")

    def actualizar_tabla_uart(linea):
        dispositivo = _parsear_dispositivo_uart(linea)
        if dispositivo is None:
            return
        rx, tx, nombre = dispositivo
        for item in tabla_uart.get_children():
            valores = tabla_uart.item(item, "values")
            if valores[0] == rx and valores[1] == tx:
                tabla_uart.item(item, values=(rx, tx, nombre))
                return

        tabla_uart.insert("", "end", values=(rx, tx, nombre))

    def actualizar_tabla_spi(linea):
        partes = str(linea).strip().split(";")
        if not partes or not partes[0].startswith("SPI:") or partes[0] == "SPI:NONE":
            return

        nombre = partes[0].partition(":")[2].strip()
        campos = {}
        for parte in partes[1:]:
            clave, separador, valor = parte.partition("=")
            if separador:
                campos[clave.strip().upper()] = valor.strip()

        cs = campos.get("CS", "-")
        comando = campos.get("CMD", "-")
        data = campos.get("DATA", "-")
        descripcion = _buscar_descripcion_spi(nombre, comando, data, catalogo_spi)
        if "R1" in campos and data != "-":
            data = f"R1={campos['R1']}; R2={data}"

        for item in tabla_spi.get_children():
            if tabla_spi.item(item, "values")[0] == cs:
                tabla_spi.item(item, values=(cs, comando, data, descripcion))
                return

        tabla_spi.insert("", "end", values=(cs, comando, data, descripcion))

    def limpiar_resultados_rastreo():
        salida.delete("1.0", tk.END)
        debug_output.delete("1.0", tk.END)
        tabla_i2c.delete(*tabla_i2c.get_children())
        tabla_uart.delete(*tabla_uart.get_children())
        tabla_spi.delete(*tabla_spi.get_children())
        indicador_i2c.apagar()
        indicador_uart.apagar()
        indicador_spi.apagar()
        gps_coords_actuales[0] = None
        gps_detectado[0] = False
        reporte_disponible[0] = False
        reporte_actual[0] = {}
        boton_gps.config(text="🌐", state="disabled", bg="black", fg="white")
        boton_reporte.config(state="disabled")

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
            salida.insert(tk.END, "❌ No se pudo abrir el puerto\n")
            detalle = datos.get("error_puerto", "")
            if detalle:
                salida.insert(tk.END, f"Detalle: {detalle}\n\n")
            salida.insert(tk.END, "Verifica que ningún monitor serial externo lo esté usando.\n")
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
            "board": formatear_nombre_placa(datos.get("board", "-")),
            "fqbn": fqbn or "No disponible",
            "uart": datos.get("uart", "-"),
            "spi": datos.get("spi", "-"),
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
    def manejar_evento(tipo, valor, cancelacion=None):
        if cancelacion is not None and cancelacion.is_set():
            return
        if tipo == "debug":
            texto = str(valor).strip()
            if not texto:
                return
            if texto.startswith("BOARD:"):
                barCarga.actualizar(10)
            elif texto.startswith("I2C"):
                barCarga.actualizar(25)
            elif texto.startswith("SPI:"):
                barCarga.actualizar(45)
            elif texto.startswith(("UART_DEV:", "UART_INFO:")):
                barCarga.actualizar(65)
            elif texto.startswith("GPS_COORDS:"):
                barCarga.actualizar(85)
            elif texto.startswith("STATUS:READY"):
                barCarga.actualizar(95)
            if texto.startswith("UART_DEV:"):
                actualizar_tabla_uart(texto)
            elif texto.startswith("SPI:"):
                actualizar_tabla_spi(texto)
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
        limpiar_resultados_rastreo()

        if escaneo_activo[0]:
            salida.insert(tk.END, "Ya hay un rastreo en curso para este puerto.\n")
            return

        puerto = seleccion.get()
        if not puerto:
            return

        escaneo_activo[0] = True
        cancelacion = threading.Event()
        rastreo_cancelacion[0] = cancelacion
        barCarga.iniciar()
        barCarga.actualizar(5)
        liberar_puertos()

        salida.delete("1.0", tk.END)
        salida.insert(tk.END, "🔍 Liberando puertos y rastreando...\n")

        def tarea():
            try:
                datos = leer_datos(
                    puerto,
                    timeout=0.25,
                    on_evento=lambda tipo, valor: root.after(0, manejar_evento, tipo, valor, cancelacion),
                    cancelacion=cancelacion,
                )
                root.after(0, barCarga.actualizar, 95)
                if not cancelacion.is_set():
                    root.after(0, lambda: mostrar_resultado(puerto, datos))
            finally:
                def finalizar_rastreo():
                    if rastreo_cancelacion[0] is cancelacion:
                        rastreo_cancelacion[0] = None
                        rastreo_hilo[0] = None
                        escaneo_activo[0] = False
                    barCarga.detener()

                root.after(0, finalizar_rastreo)

        rastreo_hilo[0] = threading.Thread(target=tarea, daemon=True)
        rastreo_hilo[0].start()

    icono_actualizar = tk.PhotoImage(file=str(resource_path("assets", "ico_ActualizarBBDD.png")))
    factor_icono = max(1, (max(icono_actualizar.width(), icono_actualizar.height()) + 23) // 24)
    if factor_icono > 1:
        icono_actualizar = icono_actualizar.subsample(factor_icono, factor_icono)

    btn_actualizar = tk.Button(
        frame_btn,
        text="Actualizar",
        image=icono_actualizar,
        compound="left",
        command=lambda: actualizar_puertos(),
        bg="black",
        fg="white",
        highlightbackground="OliveDrab",
        highlightthickness=1,
        padx=8,
    )
    btn_actualizar.image = icono_actualizar
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
    def escanear(raw):
        nonlocal dispositivos

        for w in frame_lista.winfo_children():
            w.destroy()

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

    def escanear_async(liberar=False):
        version_escaneo_puertos[0] += 1
        version = version_escaneo_puertos[0]
        barCarga.iniciar()

        def tarea():
            try:
                if liberar:
                    liberar_puertos()
                raw = obtener_puertos()
                root.after(0, barCarga.actualizar, 70)
                root.after(0, completar_escaneo, raw, version)
            except Exception as error:
                root.after(0, completar_escaneo, str(error), version)

        threading.Thread(target=tarea, daemon=True).start()

    def completar_escaneo(raw, version):
        if version != version_escaneo_puertos[0]:
            return
        try:
            barCarga.actualizar(85)
            escanear(raw)
        finally:
            barCarga.detener()
            btn_actualizar.config(state="normal")

    def actualizar_puertos():
        limpiar_resultados_rastreo()
        version_escaneo_puertos[0] += 1
        btn_actualizar.config(state="disabled")
        cancelacion = rastreo_cancelacion[0]
        if cancelacion is not None:
            cancelacion.set()
            salida.delete("1.0", tk.END)
            salida.insert(tk.END, "Deteniendo el rastreo y liberando puertos...\n")

        def esperar_rastreo():
            if escaneo_activo[0]:
                root.after(50, esperar_rastreo)
                return
            escanear_async(liberar=True)

        esperar_rastreo()

    root.after(500, escanear_async)