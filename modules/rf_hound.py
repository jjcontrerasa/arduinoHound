"""Módulo para el sistema RF Hound.

Proporciona la interfaz gráfica y los contenedores de control para el subsistema
de radiofrecuencia (RF), incluyendo parámetros de comunicación, escaneo de espectro,
telemetría y monitoreo de paquetes en tiempo real.
"""

import tkinter as tk
from tkinter import ttk, messagebox

# ---------------- CONFIGURACIÓN ESTÉTICA ----------------
COLOR_BG = "black"
COLOR_TEXTO = "white"
COLOR_TITULO = "green2"
COLOR_SUBTITULO = "#55ff55"
COLOR_BORDE = "white"
COLOR_VERDE_OSCURO = "#004d00"
COLOR_TERMINAL_TEXT = "green2"

# Variables globales del módulo
_estado_escucha = False
_terminal_output = None
_tabla_paquetes = None


def liberar_recursos():
    """Libera hilos, puertos o recursos abiertos por el subsistema RF."""
    global _estado_escucha
    _estado_escucha = False


def crear_panel(parent):
    """Construye el panel completo de RF Hound dentro del contenedor indicado."""
    global _terminal_output, _tabla_paquetes

    # Marco exterior con borde blanco consistente con el diseño general
    marco_exterior = tk.Frame(
        parent,
        bg=COLOR_BG,
        highlightbackground=COLOR_BORDE,
        highlightthickness=1,
    )
    marco_exterior.pack(fill="both", expand=True, padx=5, pady=5)

    # Contenedor principal con grid de 2 columnas (Control / Telemetría)
    marco_principal = tk.Frame(marco_exterior, bg=COLOR_BG)
    marco_principal.pack(fill="both", expand=True, padx=8, pady=8)

    marco_principal.columnconfigure(0, weight=35, uniform="columnas_rf")
    marco_principal.columnconfigure(1, weight=65, uniform="columnas_rf")
    marco_principal.rowconfigure(0, weight=1)

    # =========================================================================
    # COLUMNA IZQUIERDA: CONFIGURACIÓN Y CONTROL RF
    # =========================================================================
    frame_control = tk.Frame(
        marco_principal,
        bg=COLOR_BG,
        highlightbackground=COLOR_BORDE,
        highlightthickness=1,
    )
    frame_control.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=0)

    # Título de la sección
    tk.Label(
        frame_control,
        text="Control y Configuración RF",
        fg=COLOR_TITULO,
        bg=COLOR_BG,
        font=("Arial", 13, "bold"),
    ).pack(pady=(12, 10))

    # Formulario de parámetros
    form_frame = tk.Frame(frame_control, bg=COLOR_BG)
    form_frame.pack(fill="x", padx=15, pady=5)
    form_frame.columnconfigure(0, weight=1)
    form_frame.columnconfigure(1, weight=2)

    # Estilo personalizado para comboboxes oscuros
    estilo_rf = ttk.Style(parent)
    estilo_rf.configure(
        "RF.TCombobox",
        fieldbackground="#121212",
        background="#202020",
        foreground="green2",
        arrowcolor="green2",
    )

    # 1. Módulo de RF
    tk.Label(form_frame, text="Módulo RF:", fg=COLOR_TEXTO, bg=COLOR_BG, font=("Arial", 9, "bold")).grid(
        row=0, column=0, sticky="w", pady=6
    )
    combo_modulo = ttk.Combobox(
        form_frame,
        values=["LoRa SX1276/SX1278", "NRF24L01+", "HC-12 (SI4463)", "ESP-NOW", "Receptor ASK/FSK 433MHz"],
        state="readonly",
        style="RF.TCombobox",
    )
    combo_modulo.set("LoRa SX1276/SX1278")
    combo_modulo.grid(row=0, column=1, sticky="ew", pady=6)

    # 2. Frecuencia de operación
    tk.Label(form_frame, text="Frecuencia:", fg=COLOR_TEXTO, bg=COLOR_BG, font=("Arial", 9, "bold")).grid(
        row=1, column=0, sticky="w", pady=6
    )
    combo_freq = ttk.Combobox(
        form_frame,
        values=["433.0 MHz", "868.0 MHz", "915.0 MHz", "2.4 GHz"],
        state="readonly",
        style="RF.TCombobox",
    )
    combo_freq.set("915.0 MHz")
    combo_freq.grid(row=1, column=1, sticky="ew", pady=6)

    # 3. Potencia Tx
    tk.Label(form_frame, text="Potencia Tx:", fg=COLOR_TEXTO, bg=COLOR_BG, font=("Arial", 9, "bold")).grid(
        row=2, column=0, sticky="w", pady=6
    )
    combo_power = ttk.Combobox(
        form_frame,
        values=["2 dBm", "5 dBm", "10 dBm", "14 dBm", "17 dBm", "20 dBm (Máx)"],
        state="readonly",
        style="RF.TCombobox",
    )
    combo_power.set("14 dBm")
    combo_power.grid(row=2, column=1, sticky="ew", pady=6)

    # 4. Ancho de banda / Data Rate
    tk.Label(form_frame, text="Ancho de Banda:", fg=COLOR_TEXTO, bg=COLOR_BG, font=("Arial", 9, "bold")).grid(
        row=3, column=0, sticky="w", pady=6
    )
    combo_bw = ttk.Combobox(
        form_frame,
        values=["125 kHz", "250 kHz", "500 kHz"],
        state="readonly",
        style="RF.TCombobox",
    )
    combo_bw.set("125 kHz")
    combo_bw.grid(row=3, column=1, sticky="ew", pady=6)

    # Indicadores de estado
    frame_status = tk.LabelFrame(
        frame_control,
        text=" Estado del Transceptor ",
        fg="white",
        bg=COLOR_BG,
        font=("Arial", 9, "bold"),
        labelanchor="n",
        highlightbackground="#333333",
        highlightthickness=1,
    )
    frame_status.pack(fill="x", padx=15, pady=(15, 10))

    status_inner = tk.Frame(frame_status, bg=COLOR_BG)
    status_inner.pack(padx=10, pady=8, fill="x")

    tk.Label(status_inner, text="Hardware:", fg="gray70", bg=COLOR_BG, font=("Arial", 9)).grid(row=0, column=0, sticky="w")
    lbl_hw_status = tk.Label(status_inner, text="Listo / En espera", fg="yellow", bg=COLOR_BG, font=("Arial", 9, "bold"))
    lbl_hw_status.grid(row=0, column=1, sticky="w", padx=(5, 0))

    tk.Label(status_inner, text="Modo actual:", fg="gray70", bg=COLOR_BG, font=("Arial", 9)).grid(row=1, column=0, sticky="w", pady=(4, 0))
    lbl_mode = tk.Label(status_inner, text="Reposo (Standby)", fg="cyan", bg=COLOR_BG, font=("Arial", 9, "bold"))
    lbl_mode.grid(row=1, column=1, sticky="w", padx=(5, 0), pady=(4, 0))

    # Botones de acción
    botones_frame = tk.Frame(frame_control, bg=COLOR_BG)
    botones_frame.pack(fill="x", padx=15, pady=10)

    def _toggle_escaneo():
        global _estado_escucha
        _estado_escucha = not _estado_escucha
        if _estado_escucha:
            btn_escaneo.config(text="🛑 Detener escaneo", fg="red")
            lbl_mode.config(text="Escaneando espectro...", fg="green2")
            if _terminal_output:
                _terminal_output.insert(tk.END, "[RF Hound] Escaneo iniciado en " + combo_freq.get() + "...\n")
                _terminal_output.see(tk.END)
        else:
            btn_escaneo.config(text="📡 Iniciar recepción / escaneo", fg="green2")
            lbl_mode.config(text="Reposo (Standby)", fg="cyan")
            if _terminal_output:
                _terminal_output.insert(tk.END, "[RF Hound] Escaneo detenido.\n")
                _terminal_output.see(tk.END)

    def _limpiar_terminal():
        if _terminal_output:
            _terminal_output.delete("1.0", tk.END)

    btn_escaneo = tk.Button(
        botones_frame,
        text="📡 Iniciar recepción / escaneo",
        command=_toggle_escaneo,
        bg=COLOR_BG,
        fg=COLOR_TITULO,
        activebackground="#112211",
        activeforeground=COLOR_TITULO,
        highlightbackground="green2",
        highlightthickness=1,
        font=("Arial", 10, "bold"),
        cursor="hand2",
    )
    btn_escaneo.pack(fill="x", pady=4)

    btn_limpiar = tk.Button(
        botones_frame,
        text="🧹 Limpiar consola y datos",
        command=_limpiar_terminal,
        bg=COLOR_BG,
        fg="white",
        activebackground="#222222",
        activeforeground="white",
        highlightbackground="gray50",
        highlightthickness=1,
        font=("Arial", 9),
        cursor="hand2",
    )
    btn_limpiar.pack(fill="x", pady=4)

    # =========================================================================
    # COLUMNA DERECHA: TELEMETRÍA Y MONITOR DE SEÑALES RF
    # =========================================================================
    frame_monitor = tk.Frame(
        marco_principal,
        bg=COLOR_BG,
        highlightbackground=COLOR_BORDE,
        highlightthickness=1,
    )
    frame_monitor.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=0)

    # Título del monitor
    tk.Label(
        frame_monitor,
        text="Monitor de Señales y Telemetría RF",
        fg=COLOR_TITULO,
        bg=COLOR_BG,
        font=("Arial", 13, "bold"),
    ).pack(pady=(12, 10))

    # Contenedor de tabla de paquetes recibidos
    frame_tabla = tk.Frame(frame_monitor, bg=COLOR_BG)
    frame_tabla.pack(fill="both", expand=True, padx=10, pady=(0, 5))

    tk.Label(
        frame_tabla,
        text="Paquetes RF Detectados",
        fg="white",
        bg=COLOR_BG,
        font=("Arial", 10, "bold"),
        anchor="w",
    ).pack(fill="x", pady=(0, 4))

    estilo_tree = ttk.Style(parent)
    estilo_tree.configure(
        "RF.Treeview",
        background="black",
        foreground="green2",
        fieldbackground="black",
        rowheight=22,
    )
    estilo_tree.configure(
        "RF.Treeview.Heading",
        background="#181818",
        foreground="white",
        relief="flat",
        font=("Arial", 9, "bold"),
    )
    estilo_tree.map(
        "RF.Treeview.Heading",
        background=[("active", "#282828"), ("pressed", "#111111")],
    )

    columnas = ("hora", "freq", "rssi", "snr", "payload")
    _tabla_paquetes = ttk.Treeview(
        frame_tabla,
        columns=columnas,
        show="headings",
        height=6,
        style="RF.Treeview",
    )
    _tabla_paquetes.heading("hora", text="Hora")
    _tabla_paquetes.heading("freq", text="Frecuencia")
    _tabla_paquetes.heading("rssi", text="RSSI (dBm)")
    _tabla_paquetes.heading("snr", text="SNR (dB)")
    _tabla_paquetes.heading("payload", text="Carga útil / Datos recibidos")

    _tabla_paquetes.column("hora", width=80, minwidth=65, anchor="center")
    _tabla_paquetes.column("freq", width=95, minwidth=80, anchor="center")
    _tabla_paquetes.column("rssi", width=90, minwidth=75, anchor="center")
    _tabla_paquetes.column("snr", width=80, minwidth=70, anchor="center")
    _tabla_paquetes.column("payload", width=260, minwidth=180, anchor="w")

    _tabla_paquetes.pack(fill="both", expand=True)

    # Consola en tiempo real
    frame_consola = tk.Frame(
        frame_monitor,
        bg=COLOR_BG,
        highlightbackground="#333333",
        highlightthickness=1,
    )
    frame_consola.pack(fill="both", expand=True, padx=10, pady=(5, 10))

    tk.Label(
        frame_consola,
        text="Consola de Diagnóstico RF en Tiempo Real",
        fg=COLOR_SUBTITULO,
        bg=COLOR_BG,
        font=("Arial", 9, "bold"),
        anchor="w",
    ).pack(fill="x", padx=5, pady=(5, 2))

    _terminal_output = tk.Text(
        frame_consola,
        bg="#080808",
        fg=COLOR_TERMINAL_TEXT,
        insertbackground="green2",
        font=("Consolas", 9),
        height=7,
        relief="flat",
        highlightthickness=0,
    )
    _terminal_output.pack(fill="both", expand=True, padx=5, pady=5)
    _terminal_output.insert(
        tk.END,
        "[RF Hound] Sistema de Radiofrecuencia preparado.\n"
        "[RF Hound] Selecciona los parámetros del transceptor y pulsa 'Iniciar recepción'.\n",
    )
