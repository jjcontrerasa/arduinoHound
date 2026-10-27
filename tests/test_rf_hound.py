import queue
import json
import tempfile
from pathlib import Path
import tkinter as tk
import unittest
from unittest.mock import patch

from modules.rf_hound import PanelRF
from modules.rf_receiver import ReceptorRF, comando_lora, interpretar_linea, interpretar_paquete


class ProtocoloTests(unittest.TestCase):
    def test_mediciones_validas(self):
        self.assertEqual(interpretar_linea("RF,915.0,-101"), ("RF", 915.0, -101.0))
        self.assertEqual(interpretar_linea("PEAK,433.4,-92"), ("PEAK", 433.4, -92.0))

    def test_no_acepta_datos_malformados(self):
        for linea in (
            "INFO,RFHound listo", "RF,nan,-100", "RF,915,inf", "PEAK,915",
            "RF,915,texto", "RF,2400,-80", "RF,915,-300", "RF,915,-100,extra",
        ):
            with self.subTest(linea=linea):
                self.assertIsNone(interpretar_linea(linea))

    def test_rssi_no_es_identidad(self):
        eventos = queue.Queue()
        receptor = ReceptorRF(eventos)

        class Puerto:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def read_until(self, *args):
                return b"RF,915,-90\n"

            def write(self, _data):
                pass

        with patch("modules.rf_receiver.serial.Serial", return_value=Puerto()), \
                patch("modules.rf_receiver.time.monotonic", side_effect=(0, 0, 8)):
            self.assertTrue(receptor.observar("COM_TEST"))
        self.assertEqual(eventos.get_nowait()[0], "error")
        self.assertTrue(eventos.empty())

    def test_cerrar_sin_iniciar(self):
        receptor = ReceptorRF(queue.Queue())
        receptor.cerrar()
        self.assertTrue(receptor.fin.is_set())

    def test_paquetes_texto_y_binario(self):
        texto = b"LAT:19,LON:-99\r\n"
        p = interpretar_paquete(f"PKT,915,-90,7,{len(texto)},{texto.hex()}")
        self.assertEqual(p["texto"], texto.decode())
        self.assertEqual(p["hex"], texto.hex().upper())
        self.assertIsNone(interpretar_paquete("PKT,915,-90,7,2,FF00")["texto"])
        self.assertEqual(interpretar_paquete("PKT,915,-90,7,0,")["longitud"], 0)

    def test_paquetes_invalidos(self):
        for linea in (
            "PKT,915,-90,7,2,FF", "PKT,915,-90,7,1,GG",
            "PKT,nan,-90,7,1,00", "PKT,915,-90,inf,1,00",
            "PKT,433,-90,7,1,00", "PKT,915,-90,7,256," + "00" * 256,
            "PKT,915,-90,7,-1,", "PKT,915,-90,7,1,  ",
        ):
            with self.subTest(linea=linea), self.assertRaises(ValueError):
                interpretar_paquete(linea)

    def test_perfil_lora(self):
        self.assertEqual(
            comando_lora("915", "125", "7", "5", "12", "8", True, False),
            "LORA,915.000,125,7,5,18,8,1,0",
        )
        for posicion, valor in ((0, "433"), (0, "nan"), (1, "100"), (2, "13"),
                                (3, "9"), (4, "100"), (5, "0")):
            args = ["915", "125", "7", "5", "12", "8", True, False]
            args[posicion] = valor
            with self.subTest(args=args), self.assertRaises(ValueError):
                comando_lora(*args)

    def test_transporte_paquete_largo_fragmentado(self):
        eventos = queue.Queue()
        receptor = ReceptorRF(eventos)
        contenido = bytes(range(255))
        linea = f"PKT,915,-90,7,255,{contenido.hex()}"
        recibidos = iter((
            b"HELLO,RFHOUND,2,SX1262,868,928\n",
            linea[:200].encode(), (linea[200:] + "\n").encode(),
        ))
        escritos = []

        class Puerto:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def write(self, data):
                escritos.append(data)

            def read_until(self, *args):
                try:
                    return next(recibidos)
                except StopIteration:
                    raise OSError("Fin de prueba")

        with patch("modules.rf_receiver.serial.Serial", return_value=Puerto()):
            receptor.observar("COM_TEST")
        salida = list(eventos.queue)
        self.assertIn(("conectado", "COM_TEST"), salida)
        self.assertIn(("linea", linea), salida)
        self.assertIn(("desconectado", ""), salida)
        self.assertIn(b"ID\n", escritos)
        self.assertEqual(bytes.fromhex(interpretar_paquete(linea)["hex"]), contenido)
        self.assertFalse(receptor.conectado.is_set())


class InterfazTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        with patch.object(ReceptorRF, "start"):
            self.panel = PanelRF(self.root)
        self.enviar = patch.object(self.panel.receptor, "enviar")
        self.comandos = self.enviar.start()

    def tearDown(self):
        self.panel.cerrar()
        self.enviar.stop()
        self.root.destroy()

    def entregar(self, tipo, dato=""):
        if self.panel.after_id is not None:
            self.root.after_cancel(self.panel.after_id)
        self.panel.eventos.put((tipo, dato))
        self.panel.sondear()

    def test_estados_y_reconexion(self):
        p = self.panel
        self.assertEqual(p.iniciar.cget("state"), "disabled")
        self.assertEqual(p.detener.cget("state"), "disabled")
        self.entregar("conectado", "COM_TEST")
        self.assertEqual(p.iniciar.cget("state"), "normal")
        self.assertEqual(p.detener.cget("state"), "disabled")
        p.iniciar.invoke()
        self.assertEqual(p.modo, "IDLE")  # A request is not a hardware acknowledgement.
        self.entregar("linea", "ACK,SCAN")
        self.assertEqual(p.iniciar.cget("state"), "disabled")
        self.assertEqual(p.detener.cget("state"), "normal")
        self.entregar("linea", "PEAK,915,-99")
        self.assertEqual(len(p.tabla.get_children()), 1)
        p.detener.invoke()
        self.entregar("linea", "ACK,IDLE")
        self.entregar("linea", "PEAK,916,-98")
        self.assertEqual(len(p.tabla.get_children()), 1)
        self.entregar("desconectado")
        self.assertFalse(p.escaneando)
        self.assertEqual(p.iniciar.cget("state"), "disabled")
        self.assertEqual(p.detener.cget("state"), "disabled")
        self.entregar("conectado", "COM_NEW")
        self.assertEqual(p.iniciar.cget("state"), "normal")
        self.assertEqual(p.detener.cget("state"), "disabled")

    def test_limita_resultados_y_consola(self):
        p = self.panel
        self.entregar("conectado", "COM_TEST")
        p.iniciar.invoke()
        self.entregar("linea", "ACK,SCAN")
        for frecuencia in range(800, 950):
            self.entregar("linea", f"PEAK,{frecuencia},-100")
        self.assertEqual(len(p.tabla.get_children()), 100)
        for _ in range(300):
            p.log("mensaje")
        self.assertLessEqual(int(p.consola.index("end-1c").split(".")[0]), 250)

    def test_fijar_capturar_decodificar_guardar(self):
        p = self.panel
        self.entregar("conectado", "COM_TEST")
        self.assertEqual(p.capturar.cget("state"), "disabled")
        p.fijar.invoke()
        self.entregar("linea", "ACK,HOLD")
        self.assertEqual(p.fija, 915)
        self.assertEqual(p.capturar.cget("state"), "normal")
        p.capturar.invoke()
        # The packet profile must come from the command, not edited widgets.
        p.crc.set(False)
        self.entregar("linea", "ACK,LORA")
        self.entregar("linea", "PKT,915,-90,7,4,484F4C41")
        self.assertEqual(p.total_paquetes, 1)
        self.assertTrue(p.paquetes[0]["perfil"]["crc"])
        p.lista_paquetes.selection_set("1")
        p.seleccionar_paquete()
        self.assertIn("HOLA", p.decodificado.get("1.0", "end"))
        with tempfile.TemporaryDirectory() as directorio:
            ruta = Path(directorio) / "captura.jsonl"
            with patch("modules.rf_hound.filedialog.asksaveasfilename", return_value=str(ruta)):
                p.guardar()
            self.assertEqual(json.loads(ruta.read_text())["hex"], "484F4C41")
        self.entregar("linea", "ERR,PACKET,-7")
        self.assertEqual(p.total_paquetes, 1)
        self.assertEqual(p.modo, "LORA")
        p.detener.invoke()
        self.entregar("linea", "ERR,PACKET,-7")
        self.assertIsNotNone(p.pendiente)
        self.entregar("linea", "ACK,IDLE")
        self.assertEqual(p.modo, "IDLE")

    def test_rechazo_perfil_y_limite_paquetes(self):
        p = self.panel
        self.entregar("conectado", "COM_TEST")
        p.fijar.invoke()
        self.entregar("linea", "ACK,HOLD")
        p.sync.set("ZZ")
        p.capturar.invoke()
        self.assertIsNone(p.pendiente)
        p.sync.set("12")
        p.capturar.invoke()
        self.entregar("linea", "ACK,LORA")
        for _ in range(510):
            self.entregar("linea", "PKT,915,-90,7,1,00")
        self.assertEqual(p.total_paquetes, 510)
        self.assertEqual(len(p.paquetes), 500)
        self.assertEqual(len(p.lista_paquetes.get_children()), 500)
        self.entregar("linea", "PKT,915,-90,7,1,ZZ")
        self.assertEqual(p.total_paquetes, 510)

    def test_commande_error_y_timeout(self):
        p = self.panel
        self.entregar("conectado", "COM_TEST")
        p.fijar.invoke()
        self.entregar("linea", "ERR,HOLD,-1")
        self.assertIsNone(p.pendiente)
        self.assertEqual(p.modo, "IDLE")
        p.fijar.invoke()
        p.pendiente = ("HOLD", "HOLD,915", 0)
        self.entregar("linea", "ALIVE,IDLE")
        self.assertFalse(p.conectado)
        self.assertTrue(p.receptor.reiniciar.is_set())


if __name__ == "__main__":
    unittest.main()
