import runpy
import queue
import subprocess
import tempfile
import threading
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import serial
from serial.tools.list_ports_common import ListPortInfo

from modules.aReader import LectorSerial, MAX_BYTES, PanelReader
from modules.acceso_serial import acceso_puerto
from modules.rf_receiver import ReceptorRF


class PuertoSimulado:
    def __init__(self):
        self.fragmentos = queue.Queue()
        self.cerrado = False
        self.write = Mock()
        self.reset_input_buffer = Mock()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.cerrado = True

    @property
    def in_waiting(self):
        return 0

    def read(self, cantidad):
        try:
            dato = self.fragmentos.get(timeout=0.01)
        except queue.Empty:
            return b""
        if isinstance(dato, Exception):
            raise dato
        return dato


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.enumeracion = patch("modules.aReader.list_ports.comports", return_value=[])
        self.puertos = self.enumeracion.start()
        self.addCleanup(self.enumeracion.stop)
        self.addCleanup(self.root.destroy)
        self.panel = PanelReader(self.root)

    def esperar(self, condicion):
        limite = time.monotonic() + 3
        while not condicion() and time.monotonic() < limite:
            self.root.update()
            time.sleep(0.005)
        self.assertTrue(condicion(), "La operacion serial no termino a tiempo")

    def preparar_puerto(self):
        puerto = ListPortInfo("COM_TEST")
        puerto.description = "Arduino simulado"
        self.puertos.return_value = [puerto]
        self.panel.actualizar()

    def iniciar(self, simulado):
        self.preparar_puerto()
        parche = patch("modules.aReader.serial.Serial", return_value=simulado)
        fabrica = parche.start()
        self.addCleanup(parche.stop)
        self.panel.conectar()
        self.esperar(lambda: "Leyendo" in self.panel.estado["text"])
        return fabrica

    def test_sin_puerto(self):
        self.assertEqual(self.panel.estado_puertos["text"], "Sin puerto conectado")
        self.assertIsNotNone(self.panel.after_id)
        self.panel.conectar()
        self.assertIn("Selecciona un puerto", self.panel.estado["text"])

    def test_conexion_varios_puertos_y_desconexion(self):
        primero = ListPortInfo("COM3")
        primero.description = "Arduino Uno"
        segundo = ListPortInfo("COM12")
        segundo.description = "USB Serial"
        for puertos, esperado in (
            ([primero], {"COM3": ("COM3", "Arduino Uno")}),
            ([segundo, primero], {"COM3": ("COM3", "Arduino Uno"), "COM12": ("COM12", "USB Serial")}),
            ([], {}),
        ):
            with self.subTest(puertos=puertos), patch("serial.Serial") as conexion:
                self.puertos.return_value = puertos
                self.panel.actualizar()
                self.assertEqual(
                    {item: tuple(self.panel.puertos.item(item, "values"))
                     for item in self.panel.puertos.get_children()}, esperado,
                )
                conexion.assert_not_called()

    def test_error_visible_y_recuperacion(self):
        self.puertos.side_effect = OSError("Acceso denegado")
        self.panel.actualizar()
        self.assertIn("Acceso denegado", self.panel.estado_puertos["text"])
        self.assertEqual(self.panel.estado_puertos["fg"], "#ff6b6b")
        self.assertIsNotNone(self.panel.after_id)
        self.puertos.side_effect = None
        self.panel.actualizar()
        self.assertEqual(self.panel.estado_puertos["text"], "Sin puerto conectado")
        self.assertEqual(self.panel.estado_puertos["fg"], "white")

    def test_destruir_cancela_actualizacion(self):
        after_id = self.panel.after_id
        lectura_id = self.panel.lectura_id
        self.panel.frame.destroy()
        self.assertIsNone(self.panel.after_id)
        self.assertNotIn(after_id, self.root.tk.call("after", "info"))
        self.assertNotIn(lectura_id, self.root.tk.call("after", "info"))

    def test_baudios_invalidos_no_abren_puerto(self):
        self.preparar_puerto()
        with patch("modules.aReader.serial.Serial") as conexion:
            for valor in ("", "abc", "0", "-9600", "9600.5"):
                with self.subTest(valor=valor):
                    self.panel.baudios.set(valor)
                    self.panel.conectar()
                    self.assertIn("Baudios invalidos", self.panel.estado["text"])
            conexion.assert_not_called()

    def test_recepcion_bruta_utf8_fragmentado_y_cierre(self):
        simulado = PuertoSimulado()
        self.panel.baudios.set("57600")
        fabrica = self.iniciar(simulado)
        fabrica.assert_called_once_with(
            "COM_TEST", 57600, timeout=0.1, bytesize=8, parity="N", stopbits=1,
            xonxoff=False, rtscts=False, dsrdtr=False,
        )
        self.assertEqual(str(self.panel.combo_baudios["state"]), "disabled")
        fragmentos = (b"  RAW:1;\r\n\xc3", b"\xb1\t\x00", b"\xff\n")
        for dato in fragmentos:
            simulado.fragmentos.put(dato)
        recibido = b"".join(fragmentos)
        self.esperar(lambda: self.panel.total_bytes == len(recibido))
        self.assertEqual(bytes(self.panel.datos), recibido)
        self.assertEqual(self.panel.monitor.get("1.0", "end-1c"), recibido.decode("utf-8", errors="replace"))
        simulado.write.assert_not_called()
        simulado.reset_input_buffer.assert_not_called()
        self.panel.desconectar()
        self.assertEqual(str(self.panel.conectar_btn["state"]), "disabled")
        self.esperar(lambda: self.panel.trabajador is None)
        self.assertTrue(simulado.cerrado)
        self.assertEqual(self.panel.estado["text"], "Desconectado.")
        self.assertEqual(str(self.panel.combo_baudios["state"]), "normal")
        self.assertFalse(acceso_puerto("COM_TEST")[1].is_set())

    def test_error_apertura_y_reconexion(self):
        self.preparar_puerto()
        with patch("modules.aReader.serial.Serial", side_effect=serial.SerialException("Puerto ocupado")):
            self.panel.conectar()
            self.esperar(lambda: self.panel.trabajador is None)
        self.assertIn("Puerto ocupado", self.panel.estado["text"])
        self.iniciar(PuertoSimulado())

    def test_desconexion_fisica_y_lectura_fallida(self):
        for detectar_por_lista in (True, False):
            with self.subTest(por_lista=detectar_por_lista):
                simulado = PuertoSimulado()
                self.iniciar(simulado)
                if detectar_por_lista:
                    self.puertos.return_value = []
                    self.panel.actualizar()
                else:
                    simulado.fragmentos.put(serial.SerialException("USB retirado"))
                self.esperar(lambda: self.panel.trabajador is None)
                self.assertTrue(simulado.cerrado)
                self.assertIn("desconectado" if detectar_por_lista else "USB retirado", self.panel.estado["text"])

    def test_hex_guardado_y_limpiar(self):
        datos = b"\x00\xff\r\n\x80"
        self.panel._recibir(datos)
        self.panel.formato.set("Hex")
        self.panel._cambiar_formato()
        self.assertEqual(self.panel.monitor.get("1.0", "end-1c"), "00 FF 0D 0A 80 ")
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "lectura.bin"
            with patch("modules.aReader.filedialog.asksaveasfilename", return_value=str(ruta)):
                self.panel.guardar()
            self.assertEqual(ruta.read_bytes(), datos)
        self.panel.limpiar()
        self.assertEqual(bytes(self.panel.datos), b"")
        self.assertEqual(self.panel.total_bytes, 0)
        self.assertEqual(self.panel.monitor.get("1.0", "end-1c"), "")

    def test_historial_acotado_con_aviso(self):
        self.panel._recibir(b"A" * (MAX_BYTES + 100))
        self.assertEqual(len(self.panel.datos), MAX_BYTES)
        self.assertEqual(self.panel.descartados, 100)
        self.assertEqual(len(self.panel.monitor.get("1.0", "end-1c")), MAX_BYTES)
        self.assertIn("100 bytes antiguos retirados", self.panel.historial["text"])

    def test_destruir_conexion_activa_libera_puerto(self):
        simulado = PuertoSimulado()
        self.iniciar(simulado)
        trabajador = self.panel.trabajador
        self.panel.frame.destroy()
        self.assertTrue(simulado.cerrado)
        self.assertFalse(trabajador.is_alive())
        self.assertFalse(acceso_puerto("COM_TEST")[1].is_set())

    def test_utf8_incompleto_al_desconectar_y_cambiar_formato(self):
        simulado = PuertoSimulado()
        self.iniciar(simulado)
        simulado.fragmentos.put(b"\xc3")
        self.esperar(lambda: self.panel.total_bytes == 1)
        self.panel.desconectar()
        self.esperar(lambda: self.panel.trabajador is None)
        self.assertEqual(self.panel.monitor.get("1.0", "end-1c"), "\ufffd")
        self.panel._cambiar_formato()
        self.assertEqual(self.panel.monitor.get("1.0", "end-1c"), "\ufffd")
        simulado = PuertoSimulado()
        self.iniciar(simulado)
        simulado.fragmentos.put(b"OK")
        self.esperar(lambda: self.panel.total_bytes == 3)
        self.assertTrue(self.panel.monitor.get("1.0", "end-1c").endswith("OK"))

    def test_error_guardado_visible(self):
        with patch("modules.aReader.filedialog.asksaveasfilename", return_value="invalido.bin"), \
                patch("builtins.open", side_effect=PermissionError("Sin permiso")), \
                patch("modules.aReader.messagebox.showerror") as aviso:
            self.panel.guardar()
        self.assertIn("Sin permiso", aviso.call_args.args[1])

    def test_dos_paneles_y_borde_naranja(self):
        self.root.geometry("1200x720")
        self.root.deiconify()
        self.esperar(lambda: self.panel.monitor.winfo_height() > 1)
        izquierda, derecha = self.panel.frame.grid_slaves(row=0)[::-1]
        self.assertGreater(derecha.winfo_width(), izquierda.winfo_width())
        self.assertGreater(self.panel.monitor.winfo_height(), 200)
        self.assertEqual(self.panel.monitor.master["highlightbackground"], "#FFB347")
        self.assertLess(self.panel.estado.winfo_y(), self.panel.monitor.master.winfo_y())
        self.root.withdraw()


class TransporteTests(unittest.TestCase):
    def test_loopback_pyserial_recibe_bytes_exactos(self):
        eventos = queue.Queue(maxsize=256)
        conexion = serial.serial_for_url("loop://", timeout=0.1)
        datos = b"  UNO:123\r\nESP32:\x00\xff\xc3\xb1\n"
        conexion.write(datos)
        lector = LectorSerial("LOOP_TEST", 115200, eventos)
        try:
            with patch("modules.aReader.serial.Serial", return_value=conexion):
                lector.start()
                recibido = bytearray()
                limite = time.monotonic() + 3
                while len(recibido) < len(datos) and time.monotonic() < limite:
                    tipo, dato = eventos.get(timeout=1)
                    if tipo == "datos":
                        recibido.extend(dato)
                self.assertEqual(bytes(recibido), datos)
        finally:
            lector.fin.set()
            lector.join(timeout=2)
            conexion.close()
        self.assertFalse(lector.is_alive())
        self.assertEqual(lector.error, "")

    def test_reserva_impide_sondeo_rf_del_mismo_puerto(self):
        bloqueo, reserva = acceso_puerto("COM_RESERVADO")
        reserva.set()
        try:
            with patch("modules.rf_receiver.serial.Serial") as abrir:
                ReceptorRF(queue.Queue()).observar("COM_RESERVADO")
                abrir.assert_not_called()
        finally:
            reserva.clear()
        self.assertTrue(bloqueo.acquire(blocking=False))
        bloqueo.release()

    def test_cancelar_espera_de_puerto_ocupado(self):
        bloqueo, reserva = acceso_puerto("COM_OCUPADO")
        bloqueo.acquire()
        lector = LectorSerial("COM_OCUPADO", 9600, queue.Queue())
        try:
            with patch("modules.aReader.serial.Serial") as abrir:
                lector.start()
                self.assertTrue(reserva.wait(timeout=1))
                lector.fin.set()
                lector.join(timeout=2)
                self.assertFalse(lector.is_alive())
                abrir.assert_not_called()
        finally:
            bloqueo.release()
        self.assertFalse(reserva.is_set())

    def test_cola_llena_no_impide_cerrar(self):
        eventos = queue.Queue(maxsize=1)
        eventos.put(("datos", b"pendiente"))
        lector = LectorSerial("COM_LLENO", 9600, eventos)
        lector.fin.set()
        lector.start()
        lector.join(timeout=2)
        self.assertFalse(lector.is_alive())
        self.assertIn("Cola de recepcion llena", lector.error)

    def test_reader_espera_a_que_rf_libere_el_puerto(self):
        puerto_rf = PuertoSimulado()
        primer_mensaje = True

        def leer_rf(*args):
            nonlocal primer_mensaje
            time.sleep(0.005)
            if primer_mensaje:
                primer_mensaje = False
                return b"HELLO,RFHOUND,2,SX1262,868,928\n"
            return b""

        puerto_rf.read_until = leer_rf
        puerto_reader = PuertoSimulado()
        receptor = ReceptorRF(queue.Queue())
        hilo_rf = threading.Thread(target=receptor.observar, args=("COM_COMPARTIDO",))
        lector = LectorSerial("COM_COMPARTIDO", 9600, queue.Queue())
        abierto_reader = threading.Event()

        def abrir(puerto, baudios, **kwargs):
            if baudios == 115200:
                return puerto_rf
            self.assertTrue(puerto_rf.cerrado, "Reader abrio el puerto antes de cerrar RF")
            abierto_reader.set()
            return puerto_reader

        try:
            with patch("serial.Serial", side_effect=abrir):
                hilo_rf.start()
                self.assertTrue(receptor.conectado.wait(timeout=2))
                lector.start()
                self.assertTrue(abierto_reader.wait(timeout=2))
                hilo_rf.join(timeout=2)
                self.assertFalse(hilo_rf.is_alive())
                self.assertTrue(acceso_puerto("COM_COMPARTIDO")[1].is_set())
                puerto_rf.write.assert_any_call(b"STOP\n")
        finally:
            receptor.fin.set()
            lector.fin.set()
            hilo_rf.join(timeout=2)
            if lector.ident is not None:
                lector.join(timeout=2)
        self.assertTrue(puerto_reader.cerrado)
        self.assertFalse(acceso_puerto("COM_COMPARTIDO")[1].is_set())


class PestanasTests(unittest.TestCase):
    def test_encabezado_compartido_y_cambio_de_pestanas(self):
        ruta = Path(__file__).resolve().parents[1] / "main.py"
        original_popen = subprocess.Popen
        app = None
        try:
            with patch("modules.cargarSketch.crear_panel"), \
                    patch("modules.rastrear.crear_panel"), \
                    patch("modules.rf_hound.crear_panel"), \
                    patch("modules.aReader.list_ports.comports", return_value=[]):
                app = runpy.run_path(str(ruta), run_name="prueba_pestanas")
            root = app["root"]
            root.withdraw()
            header = tuple(app["frame_header"].winfo_children())
            for nombre, texto, color, imagen, frame in (
                ("reader", "Arduino Reader", "DarkGoldenrod1", "logo_reader_img", "frame_reader_content"),
                ("rf", "RF Hound", "green2", "logo_rf_img", "frame_rf_content"),
                ("reader", "Arduino Reader", "DarkGoldenrod1", "logo_reader_img", "frame_reader_content"),
                ("arduino", "Arduino Hound V3", "#3399FF", "logo_arduino_img", "frame_main_content"),
            ):
                with self.subTest(pestana=nombre):
                    app[f"btn_tab_{nombre}"].invoke()
                    self.assertEqual(app["pestana_activa"][0], nombre)
                    self.assertEqual(app["label_titulo_header"]["text"], texto)
                    self.assertEqual(app["label_titulo_header"]["fg"], color)
                    self.assertIsNotNone(app[imagen])
                    self.assertEqual(str(app["logo_izq_label"]["image"]), str(app[imagen]))
                    self.assertEqual(tuple(app["frame_header"].winfo_children()), header)
                    for contenido in ("frame_main_content", "frame_rf_content", "frame_reader_content"):
                        self.assertEqual(bool(app[contenido].grid_info()), contenido == frame)
        finally:
            subprocess.Popen = original_popen
            if app is not None:
                app["aReader"].liberar_recursos()
                for after_id in app["root"].tk.call("after", "info"):
                    app["root"].after_cancel(after_id)
                app["root"].destroy()


if __name__ == "__main__":
    unittest.main()
