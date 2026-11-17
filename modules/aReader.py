"""Monitor serial de recepcion, sin comandos ni interpretacion de protocolos.

Configurar los mismos baudios que Serial.begin() (8N1, sin control de flujo).
La apertura del puerto puede reiniciar placas Arduino/ESP32 mediante DTR/RTS,
igual que otros monitores seriales. Cerrar otros monitores antes de conectar.
No se estiman baudios a partir de texto: no es fiable para silencio o binarios.
Texto usa UTF-8 incremental, reemplazando secuencias invalidas; Hex muestra cada
byte exacto. Se conservan los ultimos 256 KiB, exportables sin conversion a .bin.
Limpiar borra ese historial, no el buffer del dispositivo. No se envia nada.
El encabezado y sus acciones se comparten con las otras pestanas en main.
El puerto reservado interrumpe el sondeo RF de ese puerto hasta desconectar.
"""

import codecs
import queue
import threading
import tkinter as tk
from tkinter import filedialog, ttk

import serial
from serial.tools import list_ports

from .acceso_serial import acceso_puerto
from .rutas import crear_boton, messagebox, titulo

COLOR_TITULO = "DarkGoldenrod1"
COLOR_BORDE = "#FFB347"
INTERVALO_ACTUALIZACION_MS = 1500
INTERVALO_LECTURA_MS = 50
MAX_BYTES = 256 * 1024
BAUDIOS = (300, 1200, 2400, 4800, 9600, 19200, 38400, 57600,
           74880, 115200, 230400, 250000, 460800, 500000, 921600, 1000000, 2000000)
_panel = None


def crear_panel(parent):
    global _panel
    _panel = PanelReader(parent)
    return _panel


def liberar_recursos():
    if _panel is not None:
        _panel.cerrar()


class LectorSerial(threading.Thread):
    """Unico propietario del puerto; nunca accede a widgets de Tk."""

    def __init__(self, puerto, baudios, eventos):
        super().__init__(daemon=True, name="ArduinoReader-Serial")
        self.puerto = puerto
        self.baudios = baudios
        self.eventos = eventos
        self.fin = threading.Event()
        self.error = ""

    def emitir(self, tipo, dato):
        while True:
            try:
                self.eventos.put((tipo, dato), timeout=0.1)
                return
            except queue.Full:
                if self.fin.is_set():
                    raise OSError("Cola de recepcion llena al cerrar; el ultimo fragmento no pudo conservarse.")

    def run(self):
        error = ""
        bloqueo, reserva = acceso_puerto(self.puerto)
        adquirido = False
        reserva.set()
        try:
            self.emitir("esperando", "")
            while not self.fin.is_set():
                if bloqueo.acquire(timeout=0.1):
                    adquirido = True
                    break
            if not adquirido or self.fin.is_set():
                return
            with serial.Serial(
                self.puerto, self.baudios, timeout=0.1,
                bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                xonxoff=False, rtscts=False, dsrdtr=False,
            ) as conexion:
                self.emitir("conectado", "")
                while not self.fin.is_set():
                    datos = conexion.read(min(max(conexion.in_waiting, 1), 4096))
                    if datos:
                        self.emitir("datos", datos)
        except (OSError, serial.SerialException, ValueError) as exc:
            error = str(exc)
        finally:
            if adquirido:
                bloqueo.release()
            reserva.clear()
            self.error = error


class PanelReader:
    def __init__(self, parent):
        self.cerrado = False
        self.after_id = None
        self.lectura_id = None
        self.trabajador = None
        self.eventos = queue.Queue(maxsize=256)
        self.datos = bytearray()
        self.total_bytes = 0
        self.descartados = 0
        self.mensaje_cierre = "Desconectado."
        self.decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self.frame = tk.Frame(
            parent, bg="black", highlightbackground="white", highlightthickness=1,
        )
        self.frame.pack(fill="both", expand=True, padx=5, pady=5)
        self.frame.columnconfigure(0, weight=35, uniform="reader")
        self.frame.columnconfigure(1, weight=65, uniform="reader")
        self.frame.rowconfigure(0, weight=1)
        izquierda = tk.Frame(self.frame, bg="black", highlightbackground="white", highlightthickness=1)
        derecha = tk.Frame(self.frame, bg="black", highlightbackground="white", highlightthickness=1)
        izquierda.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)
        derecha.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)
        tk.Label(
            izquierda, text="Puertos conectados", bg="black", fg=COLOR_TITULO,
            font=("Arial", 14, "bold"),
        ).pack(pady=(15, 10))
        lista = tk.Frame(izquierda, bg="black")
        lista.pack(fill="both", expand=True, padx=10)
        self.puertos = ttk.Treeview(
            lista, columns=("puerto", "descripcion"), show="headings", selectmode="browse", height=7,
        )
        for campo, texto, ancho in (("puerto", "Puerto", 75), ("descripcion", "Dispositivo", 180)):
            self.puertos.heading(campo, text=texto)
            self.puertos.column(campo, width=ancho, minwidth=60)
        scroll = ttk.Scrollbar(lista, orient="vertical", command=self.puertos.yview)
        self.puertos.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.puertos.pack(fill="both", expand=True)
        self.estado_puertos = tk.Label(izquierda, bg="black", fg="white", wraplength=280)
        self.estado_puertos.pack(fill="x", padx=10, pady=5)
        crear_boton(izquierda, "Actualizar puertos", self.actualizar).pack(pady=5)
        tk.Label(izquierda, text="Baudios (igual que Serial.begin)", bg="black", fg="white").pack(pady=(10, 3))
        self.baudios = tk.StringVar(value="115200")
        self.combo_baudios = ttk.Combobox(
            izquierda, textvariable=self.baudios, values=BAUDIOS, width=15,
        )
        self.combo_baudios.pack(padx=10, pady=5)
        botones = tk.Frame(izquierda, bg="black")
        botones.pack(pady=10)
        self.conectar_btn = crear_boton(botones, "Conectar", self.conectar)
        self.conectar_btn.pack(side="left", padx=3)
        self.desconectar_btn = crear_boton(botones, "Desconectar", self.desconectar, state="disabled")
        self.desconectar_btn.pack(side="left", padx=3)
        tk.Label(
            izquierda, text="8N1 / sin control de flujo.\n"
            "Cierra Arduino IDE u otros monitores antes de conectar.\n"
            "Abrir el puerto puede reiniciar la placa.\n"
            "Desconecta antes de cargar un sketch o rastrear.\n"
            "No se puede deducir el baudrate de forma fiable.",
            bg="black", fg="gray70", wraplength=280, justify="left",
        ).pack(fill="x", padx=12, pady=(5, 15))

        self.estado = tk.Label(
            derecha, text="Desconectado. Selecciona puerto y baudios.",
            bg="black", fg="white", anchor="w", justify="left", wraplength=550,
        )
        self.estado.pack(fill="x", padx=10, pady=12)
        opciones = tk.Frame(derecha, bg="black")
        opciones.pack(fill="x", padx=10, pady=(0, 8))
        self.formato = tk.StringVar(value="Texto UTF-8")
        formato = ttk.Combobox(
            opciones, textvariable=self.formato, values=("Texto UTF-8", "Hex"),
            state="readonly", width=13,
        )
        formato.pack(side="left")
        formato.bind("<<ComboboxSelected>>", self._cambiar_formato)
        self.autoscroll = tk.BooleanVar(value=True)
        tk.Checkbutton(
            opciones, text="Autoscroll", variable=self.autoscroll, bg="black",
            fg="white", selectcolor="#222222", activebackground="black", activeforeground="white",
        ).pack(side="left", padx=4)
        crear_boton(opciones, "Limpiar", self.limpiar).pack(side="right")
        crear_boton(opciones, "Guardar .bin", self.guardar).pack(side="right", padx=5)
        caja = tk.Frame(derecha, bg="black", highlightbackground=COLOR_BORDE, highlightthickness=2)
        caja.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        caja.rowconfigure(0, weight=1)
        caja.columnconfigure(0, weight=1)
        self.monitor = tk.Text(
            caja, bg="#080808", fg="white", font=("Consolas", 10), wrap="none",
            state="disabled", bd=0, highlightthickness=0, width=40, height=12,
        )
        vertical = ttk.Scrollbar(caja, orient="vertical", command=self.monitor.yview)
        horizontal = ttk.Scrollbar(caja, orient="horizontal", command=self.monitor.xview)
        self.monitor.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.monitor.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.historial = tk.Label(derecha, bg="black", fg="gray70", anchor="w")
        self.historial.pack(fill="x", padx=10, pady=(0, 10))
        self.frame.bind("<Destroy>", self._al_destruir)
        self._actualizar_contador()
        self.actualizar()
        self._procesar_eventos()

    def actualizar(self):
        if self.cerrado:
            return
        if self.after_id is not None:
            self.frame.after_cancel(self.after_id)
        try:
            puertos = sorted(list_ports.comports())
        except OSError as error:
            self.estado_puertos.config(text=f"Error al consultar los puertos: {error}", fg="#ff6b6b")
        else:
            seleccion = self.puertos.selection()
            actuales = {puerto.device: puerto for puerto in puertos}
            for item in self.puertos.get_children():
                if item not in actuales:
                    self.puertos.delete(item)
            for nombre, puerto in actuales.items():
                valores = (nombre, puerto.description)
                if self.puertos.exists(nombre):
                    self.puertos.item(nombre, values=valores)
                else:
                    self.puertos.insert("", "end", iid=nombre, values=valores)
            if not self.puertos.selection() and actuales:
                elegido = seleccion[0] if seleccion and seleccion[0] in actuales else next(iter(actuales))
                self.puertos.selection_set(elegido)
            self.estado_puertos.config(
                text=f"{len(puertos)} puerto(s) detectado(s)" if puertos else "Sin puerto conectado",
                fg="white",
            )
            if self.trabajador is not None and self.trabajador.puerto not in actuales:
                self.desconectar("Puerto desconectado fisicamente.")
        self.after_id = self.frame.after(INTERVALO_ACTUALIZACION_MS, self.actualizar)

    def conectar(self):
        if self.cerrado or self.trabajador is not None:
            return
        seleccion = self.puertos.selection()
        if not seleccion:
            self.estado.config(text="Selecciona un puerto conectado.", fg="#ff6b6b")
            return
        try:
            baudios = int(self.baudios.get())
            if baudios <= 0:
                raise ValueError
        except ValueError:
            self.estado.config(text="Baudios invalidos: introduce un entero positivo.", fg="#ff6b6b")
            return
        self.mensaje_cierre = "Desconectado."
        self.trabajador = LectorSerial(seleccion[0], baudios, self.eventos)
        self.conectar_btn.config(state="disabled")
        self.combo_baudios.config(state="disabled")
        self.desconectar_btn.config(state="normal")
        self.estado.config(text=f"Abriendo {seleccion[0]} a {baudios} baudios...", fg=COLOR_TITULO)
        self.trabajador.start()

    def desconectar(self, mensaje="Desconectado."):
        if self.trabajador is not None:
            self.mensaje_cierre = mensaje
            self.trabajador.fin.set()
            self.desconectar_btn.config(state="disabled")
            self.estado.config(text="Cerrando puerto serial...", fg=COLOR_TITULO)

    def _procesar_eventos(self):
        if self.cerrado:
            return
        fragmentos = []
        for _ in range(32):
            try:
                tipo, dato = self.eventos.get_nowait()
            except queue.Empty:
                break
            if tipo == "datos":
                fragmentos.append(dato)
            elif tipo == "esperando" and not self.trabajador.fin.is_set():
                self.estado.config(
                    text=f"Reservando {self.trabajador.puerto}; esperando liberar el sondeo RF...",
                    fg=COLOR_TITULO,
                )
            elif tipo == "conectado" and not self.trabajador.fin.is_set():
                self.estado.config(
                    text=f"Leyendo {self.trabajador.puerto} a {self.trabajador.baudios} baudios (8N1)...",
                    fg=COLOR_TITULO,
                )
        if fragmentos:
            self._recibir(b"".join(fragmentos))
        if self.trabajador is not None and not self.trabajador.is_alive() and self.eventos.empty():
            pendiente = self.decoder.decode(b"", final=True)
            if pendiente and self.formato.get() == "Texto UTF-8":
                self._insertar(pendiente)
            self.decoder.reset()
            error = self.trabajador.error
            self.trabajador = None
            self.conectar_btn.config(state="normal")
            self.combo_baudios.config(state="normal")
            self.desconectar_btn.config(state="disabled")
            self.estado.config(
                text=f"Error serial: {error}" if error else self.mensaje_cierre,
                fg="#ff6b6b" if error else "white",
            )
        self.lectura_id = self.frame.after(INTERVALO_LECTURA_MS, self._procesar_eventos)

    def _recibir(self, datos):
        self.total_bytes += len(datos)
        self.datos.extend(datos)
        exceso = max(0, len(self.datos) - MAX_BYTES)
        if exceso:
            del self.datos[:exceso]
            self.descartados += exceso
            self._cambiar_formato()
        elif self.formato.get() == "Hex":
            self._insertar(datos.hex(" ").upper() + " ")
        else:
            self._insertar(self.decoder.decode(datos))
        self._actualizar_contador()

    def _insertar(self, texto, reemplazar=False):
        posicion = self.monitor.yview()[0]
        self.monitor.config(state="normal")
        if reemplazar:
            self.monitor.delete("1.0", "end")
        self.monitor.insert("end", texto)
        self.monitor.config(state="disabled")
        if self.autoscroll.get():
            self.monitor.see("end")
        else:
            self.monitor.yview_moveto(posicion)

    def _cambiar_formato(self, _event=None):
        self.decoder.reset()
        texto = (self.datos.hex(" ").upper() + " " if self.datos else "")
        if self.formato.get() == "Texto UTF-8":
            texto = self.decoder.decode(bytes(self.datos), final=self.trabajador is None)
            if self.trabajador is None:
                self.decoder.reset()
        self._insertar(texto, reemplazar=True)

    def _actualizar_contador(self):
        self.historial.config(
            text=f"{self.total_bytes} bytes recibidos | {len(self.datos)} conservados de {MAX_BYTES}\n"
            f"{self.descartados} bytes antiguos retirados | Texto: UTF-8; Hex/.bin: bytes exactos",
        )

    def limpiar(self):
        self.datos.clear()
        self.total_bytes = 0
        self.descartados = 0
        self.decoder.reset()
        self._insertar("", reemplazar=True)
        self._actualizar_contador()

    def guardar(self):
        ruta = filedialog.asksaveasfilename(
            parent=self.frame, title=titulo("Guardar bytes de Arduino Reader"),
            defaultextension=".bin", filetypes=(("Bytes originales", "*.bin"), ("Todos", "*.*")),
        )
        if not ruta:
            return
        try:
            with open(ruta, "wb") as archivo:
                archivo.write(self.datos)
        except OSError as error:
            messagebox.showerror(titulo("Arduino Reader"), f"No se pudieron guardar los bytes:\n{error}")

    def cerrar(self):
        if self.cerrado:
            return
        self.cerrado = True
        for after_id in (self.after_id, self.lectura_id):
            if after_id is not None:
                self.frame.after_cancel(after_id)
        self.after_id = self.lectura_id = None
        if self.trabajador is not None:
            self.trabajador.fin.set()
            self.trabajador.join(timeout=1)
            if self.trabajador.is_alive():
                raise RuntimeError("Arduino Reader: el controlador serial no termino de cerrar el puerto.")

    def _al_destruir(self, event):
        if event.widget is self.frame:
            self.cerrar()
