"""Escaneo de potencia, frecuencia fija y captura LoRa pasiva RF Hound."""

from collections import deque
import json
import math
import queue
import time
import tkinter as tk
from tkinter import filedialog, ttk

from .rf_receiver import ReceptorRF, comando_lora, interpretar_linea, interpretar_paquete
from .rutas import messagebox, titulo

_panel = None


def liberar_recursos():
    """Detiene el monitor USB y libera el receptor."""
    if _panel is not None:
        _panel.cerrar()


def crear_panel(parent):
    """Construye RF Hound sin modificar otras pantallas ni el encabezado."""
    global _panel
    _panel = PanelRF(parent)


class PanelRF:
    def __init__(self, parent):
        self.parent = parent
        self.cerrado = False
        self.conectado = False
        self.escaneando = False
        self.modo = "IDLE"
        self.pendiente = None
        self.fija = None
        self.perfil_activo = {}
        self.after_id = None
        self.paquetes = deque(maxlen=500)
        self.total_paquetes = 0
        self.eventos = queue.Queue(maxsize=1024)
        self.receptor = ReceptorRF(self.eventos)
        exterior = tk.Frame(parent, bg="black", highlightbackground="white", highlightthickness=1)
        exterior.pack(fill="both", expand=True, padx=5, pady=5)
        columnas = tk.Frame(exterior, bg="black")
        columnas.pack(fill="both", expand=True, padx=8, pady=8)
        columnas.columnconfigure(0, weight=35, uniform="columnas_rf")
        columnas.columnconfigure(1, weight=65, uniform="columnas_rf")
        columnas.rowconfigure(0, weight=1)
        izquierda = tk.Frame(columnas, bg="black", highlightbackground="white", highlightthickness=1)
        derecha = tk.Frame(columnas, bg="black", highlightbackground="white", highlightthickness=1)
        izquierda.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        derecha.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        self.etiqueta(izquierda, "Receptor RF", True).pack(pady=(12, 15))
        self.hardware = self.etiqueta(izquierda, "Buscando receptor USB...")
        self.hardware.pack(fill="x", padx=15, pady=10)
        self.etiqueta(
            izquierda, "Conecta tu Heltec con firmware RF Hound v2.\n"
            "Reconocimiento automatico por USB.",
        ).pack(fill="x", padx=15, pady=10)
        self.iniciar = self.boton(izquierda, "Iniciar escaneo", self.iniciar_escaneo)
        self.iniciar.pack(fill="x", padx=15, pady=(15, 5))
        self.detener = self.boton(izquierda, "Detener escaneo / captura", self.detener_escaneo)
        self.detener.pack(fill="x", padx=15, pady=5)
        self.estado = self.etiqueta(izquierda, "Modo: detenido")
        self.estado.pack(fill="x", padx=15, pady=10)
        self.etiqueta(
            izquierda,
            "1. Escanea actividad RF.\n2. Selecciona o escribe una frecuencia.\n"
            "3. Fijala y configura un perfil LoRa.\n4. Intenta capturar paquetes.\n\n"
            "Recepcion pasiva: no transmite.\n"
            "RSSI no identifica dispositivos.\n"
            "La etapa RF y antena deben ser compatibles.\n"
            "Esta version limita la banda a 868-928 MHz.\n"
            "No captura HC-12, NRF24 ni Bluetooth.\n"
            "No descifra contenido cifrado.",
        ).pack(fill="x", padx=15, pady=15)

        self.etiqueta(derecha, "Actividad y captura RF", True).pack(pady=(10, 5))
        self.senal = self.etiqueta(derecha, "En espera de receptor y escaneo")
        self.senal.pack(fill="x", padx=10, pady=3)
        self.tabs = ttk.Notebook(derecha)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=5)
        actividad = tk.Frame(self.tabs, bg="black")
        captura = tk.Frame(self.tabs, bg="black")
        datos = tk.Frame(self.tabs, bg="black")
        self.tabs.add(actividad, text="Detectar senal")
        self.tabs.add(captura, text="Capturar paquetes")
        self.tabs.add(datos, text="Decodificar datos")
        limites = tk.Frame(actividad, bg="black")
        limites.pack(fill="x", padx=5, pady=5)
        self.desde = self.campo(limites, "Desde MHz", "902", 0)
        self.hasta = self.campo(limites, "Hasta MHz", "928", 1)
        self.paso = self.campo(limites, "Paso MHz", "0.5", 2)
        fijo = tk.Frame(actividad, bg="black")
        fijo.pack(fill="x", padx=5, pady=5)
        self.frecuencia = self.campo(fijo, "Frecuencia MHz", "915", 0)
        self.fijar = self.boton(fijo, "Fijar frecuencia", self.fijar_frecuencia)
        self.fijar.grid(row=1, column=1, padx=5, sticky="ew")
        estilo = ttk.Style(parent)
        estilo.configure("RF.Treeview", background="black", foreground="green2",
                         fieldbackground="black", rowheight=24)
        self.tabla = ttk.Treeview(
            actividad, columns=("freq", "rssi", "tipo"), show="headings",
            style="RF.Treeview", height=6,
        )
        for nombre, titulo, ancho in (
            ("freq", "Frecuencia (MHz)", 130), ("rssi", "RSSI (dBm)", 100),
            ("tipo", "Resultado", 220),
        ):
            self.tabla.heading(nombre, text=titulo)
            self.tabla.column(nombre, width=ancho, minwidth=80, anchor="center")
        self.tabla.pack(fill="both", expand=True, padx=5, pady=5)
        self.tabla.bind("<<TreeviewSelect>>", self.seleccionar_frecuencia)
        self.etiqueta(actividad, "Selecciona un pico para copiar su frecuencia. No demuestra un enlace RF.").pack(pady=3)

        self.objetivo = self.etiqueta(captura, "Primero fija una frecuencia en Detectar senal.")
        self.objetivo.pack(fill="x", padx=5, pady=5)
        perfil = tk.Frame(captura, bg="black")
        perfil.pack(fill="x", padx=5)
        self.bw = self.campo(perfil, "BW kHz", "125", 0, ("125", "250", "500"))
        self.sf = self.campo(perfil, "SF", "7", 1, tuple(str(i) for i in range(7, 13)))
        self.cr = self.campo(perfil, "CR 4/x", "5", 2, ("5", "6", "7", "8"))
        self.sync = self.campo(perfil, "Sync HEX", "12", 3)
        otro = tk.Frame(captura, bg="black")
        otro.pack(fill="x", padx=5, pady=5)
        self.preambulo = self.campo(otro, "Preambulo", "8", 0)
        self.crc = tk.BooleanVar(parent, value=True)
        self.iq = tk.BooleanVar(parent, value=False)
        for col, (texto, variable) in enumerate((("CRC", self.crc), ("IQ invertida", self.iq)), start=1):
            tk.Checkbutton(otro, text=texto, variable=variable, bg="black", fg="white",
                           selectcolor="#222222", activebackground="black").grid(row=1, column=col)
        self.etiqueta(captura, "LoRa, cabecera explicita. Los parametros deben coincidir con el emisor.").pack()
        self.capturar = self.boton(captura, "Intentar captura LoRa", self.intentar_captura)
        self.capturar.pack(fill="x", padx=5, pady=5)
        self.contador = self.etiqueta(captura, "0 paquetes recibidos. Sin paquetes no hay datos que decodificar.")
        self.contador.pack(fill="x", padx=5)
        self.lista_paquetes = ttk.Treeview(
            captura, columns=("hora", "rssi", "snr", "bytes"),
            show="headings", style="RF.Treeview", height=4,
        )
        for nombre, titulo in (("hora", "Hora UTC"), ("rssi", "RSSI"), ("snr", "SNR"), ("bytes", "Bytes")):
            self.lista_paquetes.heading(nombre, text=titulo)
            self.lista_paquetes.column(nombre, width=100, minwidth=50)
        self.lista_paquetes.pack(fill="both", expand=True, padx=5, pady=5)
        self.lista_paquetes.bind("<<TreeviewSelect>>", self.seleccionar_paquete)
        self.exportar = tk.Button(captura, text="Guardar paquetes JSONL", command=self.guardar,
                                  bg="black", fg="green2", state="disabled")
        self.exportar.pack(pady=3)
        self.etiqueta(datos, "Bytes originales y texto UTF-8 si es legible; no identifica el modulo ni descifra.").pack(pady=5)
        self.decodificado = tk.Text(datos, bg="#080808", fg="green2", wrap="word", height=8, state="disabled")
        self.decodificado.pack(fill="both", expand=True, padx=5, pady=5)
        self.consola = tk.Text(derecha, bg="#080808", fg="green2", font=("Consolas", 9),
                              height=4, state="disabled", wrap="word")
        self.consola.pack(fill="x", padx=10, pady=5)
        self.log("USB automatico. El escaneo mide potencia; solo PKT contiene paquetes.")
        self.receptor.start()
        self.botones()
        self.sondear()
        parent.bind("<Destroy>", self.al_destruir, add="+")

    @staticmethod
    def etiqueta(parent, texto, titulo=False):
        return tk.Label(parent, text=texto, bg="black", fg="green2" if titulo else "white",
                        font=("Arial", 13 if titulo else 9, "bold" if titulo else "normal"),
                        justify="left", wraplength=480)

    @staticmethod
    def boton(parent, texto, accion):
        return tk.Button(parent, text=texto, command=accion, state="disabled",
                         bg="black", fg="green2", disabledforeground="gray50",
                         font=("Arial", 10, "bold"))

    @staticmethod
    def campo(parent, texto, valor, columna, opciones=None):
        parent.columnconfigure(columna, weight=1)
        tk.Label(parent, text=texto, bg="black", fg="white").grid(row=0, column=columna, sticky="w")
        variable = tk.StringVar(parent, value=valor)
        if opciones is None:
            widget = tk.Entry(parent, textvariable=variable, width=9)
        else:
            widget = ttk.Combobox(parent, textvariable=variable, values=opciones, state="readonly", width=7)
        widget.grid(row=1, column=columna, sticky="ew", padx=(0, 5))
        return variable

    def log(self, texto):
        self.consola.config(state="normal")
        self.consola.insert("end", texto + "\n")
        if int(self.consola.index("end-1c").split(".")[0]) > 250:
            self.consola.delete("1.0", "51.0")
        self.consola.see("end")
        self.consola.config(state="disabled")

    def botones(self):
        libre = self.conectado and self.pendiente is None
        self.iniciar.config(state="normal" if libre and self.modo != "SCAN" else "disabled")
        self.detener.config(state="normal" if libre and self.modo != "IDLE" else "disabled")
        self.fijar.config(state="normal" if libre else "disabled")
        self.capturar.config(state="normal" if libre and self.modo == "HOLD" else "disabled")
        self.estado.config(text=f"Modo: {self.modo}" + (" (esperando placa...)" if self.pendiente else ""))

    def solicitar(self, comando, modo):
        if self.pendiente is not None:
            self.log("Espera la confirmacion del comando anterior.")
            return
        try:
            self.receptor.enviar(comando)
        except RuntimeError as error:
            self.log(str(error))
            return
        self.pendiente = (modo, comando, time.monotonic() + 5)
        self.botones()

    def iniciar_escaneo(self):
        try:
            a, b, paso = map(float, (self.desde.get(), self.hasta.get(), self.paso.get()))
            if not all(map(math.isfinite, (a, b, paso))) or not (
                868 <= a < b <= 928 and 0.05 <= paso <= 5 and (b - a) / paso <= 1200
            ):
                raise ValueError("Banda: 868-928 MHz; inicio < fin; paso: 0.05-5 MHz.")
        except ValueError as error:
            self.log(f"Escaneo invalido: {error}")
            return
        self.solicitar(f"SCAN,{a:.3f},{b:.3f},{paso:.3f}", "SCAN")

    def detener_escaneo(self):
        self.solicitar("STOP", "IDLE")

    def seleccionar_frecuencia(self, _event=None):
        seleccion = self.tabla.selection()
        if seleccion:
            self.frecuencia.set(self.tabla.item(seleccion[0], "values")[0])

    def fijar_frecuencia(self):
        try:
            frecuencia = float(self.frecuencia.get())
            if not math.isfinite(frecuencia) or not 868 <= frecuencia <= 928:
                raise ValueError("Banda admitida: 868-928 MHz.")
        except ValueError as error:
            self.log(f"Frecuencia invalida: {error}")
            return
        self.solicitar(f"HOLD,{frecuencia:.3f}", "HOLD")

    def intentar_captura(self):
        if self.modo != "HOLD" or self.fija is None:
            self.log("Primero fija la frecuencia.")
            return
        try:
            comando = comando_lora(
                self.fija, self.bw.get(), self.sf.get(), self.cr.get(),
                self.sync.get(), self.preambulo.get(), self.crc.get(), self.iq.get(),
            )
        except ValueError as error:
            self.log(f"Perfil invalido: {error}")
            return
        self.solicitar(comando, "LORA")

    def confirmar(self, modo):
        if self.pendiente is None or self.pendiente[0] != modo:
            self.log(f"Confirmacion inesperada: {modo}")
            return
        comando = self.pendiente[1]
        self.pendiente = None
        self.modo = modo
        self.escaneando = modo != "IDLE"
        if modo == "HOLD":
            self.fija = float(comando.split(",")[1])
            self.objetivo.config(text=f"Frecuencia fija: {self.fija:g} MHz")
        if modo == "SCAN":
            self.tabla.delete(*self.tabla.get_children())
        self.log(f"Placa confirmo {modo}: {comando}")
        if modo == "LORA":
            self.perfil_activo = {
                "comando": comando, "crc": comando.split(",")[-2] == "1",
                "cabecera": "explicita",
            }
            if not self.perfil_activo["crc"]:
                self.log("Aviso: CRC deshabilitado; no se garantiza integridad del contenido.")
            self.contador.config(text=f"Escuchando LoRa; {self.total_paquetes} paquetes. Esperando tramas compatibles.")
        self.botones()

    def agregar_paquete(self, linea):
        try:
            paquete = interpretar_paquete(linea)
        except ValueError as error:
            self.log(f"Paquete serial rechazado: {error}")
            return
        self.total_paquetes += 1
        paquete["perfil"] = dict(self.perfil_activo)
        clave = str(self.total_paquetes)
        paquete["id"] = clave
        self.paquetes.append(paquete)
        self.lista_paquetes.insert("", "end", iid=clave, values=(
            paquete["hora"][11:23], paquete["rssi"], paquete["snr"], paquete["longitud"],
        ))
        filas = self.lista_paquetes.get_children()
        if len(filas) > 500:
            self.lista_paquetes.delete(filas[0])
        self.lista_paquetes.see(clave)
        self.contador.config(text=f"{self.total_paquetes} paquetes recibidos; se conservan los ultimos 500.")
        self.exportar.config(state="normal")

    def seleccionar_paquete(self, _event=None):
        seleccion = self.lista_paquetes.selection()
        if not seleccion:
            return
        paquete = next((p for p in self.paquetes if p["id"] == seleccion[0]), None)
        if paquete is None:
            return
        texto = paquete["texto"]
        salida = (
            f"Hora UTC: {paquete['hora']}\nFrecuencia: {paquete['frecuencia']} MHz\n"
            f"RSSI: {paquete['rssi']} dBm | SNR: {paquete['snr']} dB\n"
            f"Perfil: {paquete['perfil']}\n\nHEX:\n{paquete['hex']}\n\n"
            f"Texto UTF-8:\n{texto if texto is not None else '[Binario o texto no legible]'}"
        )
        self.decodificado.config(state="normal")
        self.decodificado.delete("1.0", "end")
        self.decodificado.insert("end", salida)
        self.decodificado.config(state="disabled")

    def guardar(self):
        ruta = filedialog.asksaveasfilename(
            parent=self.parent, defaultextension=".jsonl",
            filetypes=[("Paquetes JSONL", "*.jsonl")], title=titulo("Guardar paquetes RF"),
        )
        if not ruta:
            return
        try:
            with open(ruta, "w", encoding="utf-8") as archivo:
                for paquete in self.paquetes:
                    archivo.write(json.dumps(paquete, ensure_ascii=True) + "\n")
        except OSError as error:
            self.log(f"Error al guardar: {error}")
            messagebox.showerror(titulo("RF Hound"), str(error), parent=self.parent)
            return
        self.log(f"Guardados {len(self.paquetes)} paquetes en {ruta}")

    def procesar_linea(self, dato):
        if dato.startswith("ACK,"):
            self.confirmar(dato.split(",", 1)[1])
            return
        if dato.startswith("ALIVE,"):
            return
        if dato.startswith("ERR,"):
            self.log(dato)
            if not dato.startswith(("ERR,PACKET,", "ERR,COMMAND,")):
                self.modo = "IDLE"
                self.escaneando = False
            if self.pendiente is not None and not dato.startswith("ERR,PACKET,"):
                self.pendiente = None
            self.botones()
            return
        if dato.startswith("PKT,"):
            if self.modo == "LORA":
                self.agregar_paquete(dato)
            return
        if self.modo not in ("SCAN", "HOLD"):
            return
        medicion = interpretar_linea(dato)
        if medicion is None:
            self.log("Trama no reconocida: " + dato[:120])
            return
        clase, frecuencia, rssi = medicion
        self.senal.config(text=f"Medicion: {frecuencia:g} MHz | {rssi:g} dBm (no identifica dispositivos)")
        if clase == "PEAK" or self.modo == "HOLD":
            clave = f"{frecuencia:g}"
            valores = (clave, f"{rssi:g}", "Pico RSSI" if clase == "PEAK" else "Frecuencia fija")
            if self.tabla.exists(clave):
                self.tabla.item(clave, values=valores)
                self.tabla.move(clave, "", "end")
            else:
                self.tabla.insert("", "end", iid=clave, values=valores)
            filas = self.tabla.get_children()
            if len(filas) > 100:
                self.tabla.delete(filas[0])

    def sondear(self):
        for _ in range(200):
            try:
                tipo, dato = self.eventos.get_nowait()
            except queue.Empty:
                break
            if tipo == "conectado":
                self.conectado = True
                self.modo = "IDLE"
                self.hardware.config(text=f"RF Hound v2 verificado\n{dato}", fg="green2")
                self.log(f"Firmware v2 reconocido en {dato}.")
                self.botones()
            elif tipo == "desconectado":
                self.conectado = False
                self.pendiente = None
                self.modo = "IDLE"
                self.escaneando = False
                self.fija = None
                self.hardware.config(text="Receptor desconectado", fg="yellow")
                self.senal.config(text="Sin receptor")
                self.log("Receptor desconectado. Esperando reconexion USB.")
                self.botones()
            elif tipo == "error":
                self.log(dato)
            elif tipo == "linea":
                self.procesar_linea(dato)
        if self.pendiente is not None and time.monotonic() > self.pendiente[2]:
            self.log("Sin confirmacion: deteniendo receptor para evitar estado incierto.")
            self.pendiente = None
            self.conectado = False
            self.escaneando = False
            self.modo = "IDLE"
            self.receptor.reiniciar.set()
            self.botones()
            self.hardware.config(text="Sin confirmacion. Reconectando...", fg="red")
        if not self.cerrado:
            self.after_id = self.parent.after(100, self.sondear)

    def al_destruir(self, event):
        if event.widget is self.parent:
            self.cerrar()

    def cerrar(self):
        if self.cerrado:
            return
        self.cerrado = True
        if self.after_id is not None:
            self.parent.after_cancel(self.after_id)
        self.receptor.cerrar()
