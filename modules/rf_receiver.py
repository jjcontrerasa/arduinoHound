"""Transporte USB RF Hound v2; comandos y paquetes descritos en RFHound/PROTOCOLO.txt."""

from datetime import datetime, timezone
import math
import queue
import threading
import time

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None


def interpretar_linea(linea):
    partes = linea.split(",")
    if len(partes) != 3 or partes[0] not in ("RF", "PEAK"):
        return None
    try:
        frecuencia, rssi = float(partes[1]), float(partes[2])
    except ValueError:
        return None
    if not all(map(math.isfinite, (frecuencia, rssi))):
        return None
    if not 150 <= frecuencia <= 960 or not -200 <= rssi <= 10:
        return None
    return partes[0], frecuencia, rssi


def interpretar_paquete(linea):
    """Valida el sobre serial antes de convertir los bytes recibidos."""
    partes = linea.split(",")
    if len(partes) != 6 or partes[0] != "PKT":
        raise ValueError("Sobre de paquete invalido")
    frecuencia, rssi, snr = (float(v) for v in partes[1:4])
    longitud = int(partes[4])
    if not all(map(math.isfinite, (frecuencia, rssi, snr))):
        raise ValueError("Mediciones no finitas")
    if not 868 <= frecuencia <= 928 or not -200 <= rssi <= 10 or not -50 <= snr <= 50:
        raise ValueError("Mediciones fuera de rango")
    if not 0 <= longitud <= 255 or len(partes[5]) != longitud * 2:
        raise ValueError("Longitud de paquete invalida")
    contenido = bytes.fromhex(partes[5])
    if len(contenido) != longitud:
        raise ValueError("Contenido hexadecimal invalido")
    try:
        texto = contenido.decode("utf-8")
    except UnicodeDecodeError:
        texto = None
    if texto is not None and not all(c.isprintable() or c in "\r\n\t" for c in texto):
        texto = None
    return {
        "hora": datetime.now(timezone.utc).isoformat(),
        "frecuencia": frecuencia, "rssi": rssi, "snr": snr,
        "longitud": longitud, "hex": contenido.hex().upper(), "texto": texto,
    }


def comando_lora(frecuencia, bw, sf, cr, sync, preambulo, crc, iq):
    f, b = float(frecuencia), float(bw)
    s, c, p = int(sf), int(cr), int(preambulo)
    palabra = int(sync, 16)
    if not math.isfinite(f) or not 868 <= f <= 928:
        raise ValueError("Frecuencia admitida: 868-928 MHz (verifica tu antena y banda)")
    if b not in (125, 250, 500) or s not in range(7, 13) or c not in range(5, 9):
        raise ValueError("Perfil LoRa no admitido")
    if not 0 <= palabra <= 255 or not 6 <= p <= 65535:
        raise ValueError("Sync word: 00-FF; preambulo: 6-65535")
    return f"LORA,{f:.3f},{b:g},{s},{c},{palabra},{p},{int(bool(crc))},{int(bool(iq))}"


class ReceptorRF(threading.Thread):
    def __init__(self, eventos):
        super().__init__(daemon=True, name="RFHound-USB")
        self.eventos = eventos
        self.fin = threading.Event()
        self.conectado = threading.Event()
        self.reiniciar = threading.Event()
        self.comandos = queue.Queue(maxsize=16)
        self.reintentos = {}

    def enviar(self, comando):
        if not self.conectado.is_set() or self.fin.is_set():
            raise RuntimeError("Receptor RF Hound no conectado")
        try:
            self.comandos.put_nowait(comando)
        except queue.Full as error:
            raise RuntimeError("Cola de comandos RF llena") from error

    def emitir(self, tipo, dato=""):
        # Limita memoria si la ventana no procesa eventos temporalmente.
        while not self.fin.is_set() and not self.reiniciar.is_set():
            try:
                self.eventos.put((tipo, dato), timeout=0.1)
                return
            except queue.Full:
                continue

    def run(self):
        if serial is None or list_ports is None:
            self.emitir("error", "Falta pyserial: no se puede reconocer el receptor USB.")
            return
        while not self.fin.is_set():
            try:
                puertos = list(list_ports.comports())
                presentes = {p.device for p in puertos}
                self.reintentos = {p: t for p, t in self.reintentos.items() if p in presentes}
                for puerto in puertos:
                    if self.fin.is_set():
                        break
                    # CP210x y USB nativo Espressif son candidatos, no identificaciones.
                    if puerto.vid not in (0x10C4, 0x303A):
                        continue
                    if time.monotonic() < self.reintentos.get(puerto.device, 0):
                        continue
                    incompatible = self.observar(puerto.device)
                    self.reintentos[puerto.device] = (
                        math.inf if incompatible else time.monotonic() + 3
                    )
            except OSError as error:
                self.emitir("error", f"No se pueden enumerar puertos USB: {error}")
            self.fin.wait(1)

    def observar(self, puerto):
        identificado = False
        try:
            with serial.Serial(puerto, 115200, timeout=0.2) as conexion:
                conexion.dtr = False
                conexion.rts = True
                if self.fin.wait(0.1):
                    return
                conexion.rts = False
                limite = time.monotonic() + 7
                ultimo_dato = time.monotonic()
                buffer = b""
                conexion.write(b"ID\n")
                while not self.fin.is_set():
                    if identificado:
                        try:
                            comando = self.comandos.get_nowait()
                        except queue.Empty:
                            comando = None
                        if comando is not None:
                            conexion.write((comando + "\n").encode("ascii"))
                    fragmento = conexion.read_until(b"\n", 2048)
                    buffer += fragmento
                    ahora = time.monotonic()
                    if len(buffer) > 2048:
                        raise OSError("Trama serial demasiado larga")
                    if not buffer.endswith(b"\n"):
                        if ahora > (ultimo_dato + 5 if identificado else limite):
                            raise OSError("El firmware no responde con tramas completas")
                        continue
                    linea = buffer.decode("utf-8", errors="replace").strip()
                    buffer = b""
                    if linea:
                        ultimo_dato = ahora
                    if not identificado:
                        if linea == "HELLO,RFHOUND,2,SX1262,868,928":
                            identificado = True
                            self.conectado.set()
                            self.emitir("conectado", puerto)
                        elif linea == "INFO,RFHound listo":
                            self.emitir("error", f"{puerto}: firmware antiguo; carga RF Hound v2.")
                            return True
                        elif ahora > limite:
                            self.emitir("error", f"{puerto}: sin firma RF Hound; no se habilita escaneo.")
                            # No reiniciar repetidamente otra placa con el mismo adaptador.
                            return True
                    elif ahora - ultimo_dato > 5:
                        self.emitir("error", f"{puerto}: el firmware dejo de responder.")
                        return
                    elif linea:
                        self.emitir("linea", linea)
                if identificado:
                    conexion.write(b"STOP\n")
        except (OSError, serial.SerialException) as error:
            self.emitir("error", f"{puerto}: {error}")
        finally:
            self.conectado.clear()
            self.reiniciar.clear()
            while True:
                try:
                    self.comandos.get_nowait()
                except queue.Empty:
                    break
            if identificado:
                self.emitir("desconectado")

    def cerrar(self):
        self.fin.set()
        if self.is_alive():
            self.join(timeout=1)
