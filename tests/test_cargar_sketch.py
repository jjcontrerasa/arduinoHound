import json
from pathlib import Path
import subprocess
import tempfile
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

from modules.arduino_cli import ArduinoCLI, ESP32_PACKAGE_URL
from modules.deteccion_puertos import familia_fqbn, identificar_placa
from modules.persistencia import cargar_boards_esp32


ARDUINO_BOARDS = {
    "uno": {"name": "Arduino UNO Rev3", "mcu": "ATmega328P", "fqbn": "arduino:avr:uno"},
    "nano": {"name": "Arduino Nano (original)", "mcu": "ATmega328P", "fqbn": "arduino:avr:nano"},
    "nano_every": {"name": "Arduino Nano Every", "mcu": "ATmega4809", "fqbn": "arduino:megaavr:nona4809"},
    "uno_r4_wifi": {"name": "Arduino UNO R4 WiFi", "mcu": "RA4M1 + ESP32-S3", "fqbn": "arduino:renesas_uno:unor4wifi"},
}
ESP32_BOARDS = cargar_boards_esp32()
with patch("modules.persistencia.cargar_boards", return_value=ARDUINO_BOARDS.copy()):
    from modules import panel_cargar_sketch as panel


def entrada(puerto="COM9", fqbn=None, nombre="", label=""):
    return {
        "port": {"address": puerto, "label": label, "protocol": "serial"},
        "matching_boards": [{"name": nombre, "fqbn": fqbn}] if fqbn else [],
    }


class ImmediateThread:
    def __init__(self, target, daemon):
        self.target = target

    def start(self):
        self.target()


class IdentificacionTests(unittest.TestCase):
    def identificar(self, board, metadata=None):
        return identificar_placa(
            board, {"arduino": ARDUINO_BOARDS, "esp32": ESP32_BOARDS}, metadata
        )

    def test_fqbn_tiene_prioridad_sobre_descripcion(self):
        familia, clave, datos = self.identificar(
            entrada(fqbn="arduino:renesas_uno:unor4wifi"),
            {"descripcion": "Arduino UNO R4 WiFi con ESP32-S3"},
        )
        self.assertEqual((familia, clave), ("arduino", "uno_r4_wifi"))
        self.assertEqual(datos["fqbn"], "arduino:renesas_uno:unor4wifi")

    def test_esp32_y_opciones_de_fqbn_se_conservan(self):
        fqbn = "esp32:esp32:esp32s3:CDCOnBoot=cdc"
        familia, clave, datos = self.identificar(entrada(fqbn=fqbn, nombre="ESP32-S3"))
        self.assertEqual(familia, "esp32")
        self.assertEqual(clave, fqbn)
        self.assertEqual(datos["fqbn"], fqbn)

    def test_nano_esp32_usa_arquitectura_y_no_marca(self):
        self.assertEqual(familia_fqbn("arduino:esp32:nano_nora"), "esp32")
        self.assertEqual(
            self.identificar(entrada(label="Arduino Nano ESP32")),
            ("esp32", None, None),
        )

    def test_familia_fqbn_prevalece_sobre_grupo_del_catalogo(self):
        nano = {"name": "Arduino Nano ESP32", "mcu": "ESP32-S3", "fqbn": "arduino:esp32:nano_nora"}
        catalogos = {"arduino": {"nano_esp32": nano}, "esp32": ESP32_BOARDS}
        for board in (
            entrada(fqbn=nano["fqbn"]),
            entrada(label=nano["name"]),
        ):
            with self.subTest(board=board):
                self.assertEqual(
                    identificar_placa(board, catalogos),
                    ("esp32", "nano_esp32", nano),
                )

    def test_fqbn_esp32_del_catalogo(self):
        familia, clave, datos = self.identificar(entrada(fqbn="esp32:esp32:esp32c3"))
        self.assertEqual((familia, clave), ("esp32", "esp32_c3_dev_module"))
        self.assertEqual(datos, ESP32_BOARDS[clave])

    def test_nombre_exacto_y_modelo_arduino(self):
        for label, familia, clave in (
            ("DOIT ESP32 DEVKIT V1", "esp32", "esp32_doit_devkit_v1"),
            ("Arduino Nano Every", "arduino", "nano_every"),
            ("Arduino UNO R4 WiFi", "arduino", "uno_r4_wifi"),
        ):
            with self.subTest(label=label):
                resultado = self.identificar(entrada(label=label))
                self.assertEqual(resultado[:2], (familia, clave))

    def test_esp32_sin_modelo_no_inventa_fqbn(self):
        for metadata in ({"descripcion": "ESP32-S3"}, {"vid": "303A"}):
            self.assertEqual(self.identificar(entrada(), metadata), ("esp32", None, None))

    def test_usb_nativo_desde_cli(self):
        board = entrada()
        board["port"]["properties"] = {"vid": "0x303A", "pid": "0x1001"}
        self.assertEqual(self.identificar(board), ("esp32", None, None))

    def test_vid_cli_no_se_descarta_por_metadatos_usb_incompletos(self):
        board = entrada()
        board["port"]["properties"] = {"vid": "0x303A"}
        self.assertEqual(
            self.identificar(board, {"vid": "-", "descripcion": "USB Serial"}),
            ("esp32", None, None),
        )

    def test_adaptador_generico_o_esp8266_no_identifica_familia(self):
        for metadata in (
            {"descripcion": "USB-SERIAL CH340", "vid": "1A86"},
            {"descripcion": "Silicon Labs CP210x", "vid": "10C4"},
            {"descripcion": "FTDI USB Serial", "vid": "0403"},
            {"descripcion": "Unknown"},
            {"descripcion": "ESP8266", "fabricante": "Espressif"},
        ):
            with self.subTest(metadata=metadata):
                self.assertEqual(self.identificar(entrada(), metadata), (None, None, None))

    def test_varios_fqbn_no_elige_el_primero(self):
        board = entrada(fqbn="esp32:esp32:esp32")
        board["matching_boards"].append({"fqbn": "esp32:esp32:esp32s3"})
        self.assertEqual(self.identificar(board), ("esp32", None, None))
        board["matching_boards"].append({"fqbn": "arduino:avr:uno"})
        self.assertEqual(self.identificar(board), (None, None, None))


class ArduinoCLITests(unittest.TestCase):
    def setUp(self):
        self.cli = ArduinoCLI()

    def test_descubrimiento_json_y_errores(self):
        with patch.object(self.cli, "run", return_value=Mock(stdout=json.dumps({
            "detected_ports": [entrada(fqbn="esp32:esp32:esp32")]
        }))) as run:
            self.assertEqual(self.cli.discover_boards()[0]["port"]["address"], "COM9")
            run.assert_called_once_with(
                "board", "list", "--format", "json",
                capture_output=True, text=True, check=True,
            )
        invalidos = [
            "invalid json", '{"detected_ports": "error"}', '{"detected_ports": [{}]}',
        ]
        for matching_boards in (None, {}, [None], [{"fqbn": 42}], [{"name": None}]):
            board = entrada()
            board["matching_boards"] = matching_boards
            invalidos.append(json.dumps({"detected_ports": [board]}))
        for stdout in invalidos:
            with self.subTest(stdout=stdout), patch.object(
                self.cli, "run", return_value=Mock(stdout=stdout)
            ), self.assertRaises(ValueError):
                self.cli.discover_boards()

    def test_deteccion_compara_puerto_exacto_y_conserva_opciones(self):
        fqbn = "esp32:esp32:esp32:FlashSize=4M"
        with patch.object(self.cli, "discover_boards", return_value=[
            entrada("COM10", "arduino:avr:uno"), entrada("COM1", fqbn),
        ]):
            self.assertEqual(self.cli.detect_fqbn("com1"), fqbn)
            self.assertIsNone(self.cli.detect_fqbn("COM11"))

    def test_deteccion_fqbn_ambiguo(self):
        board = entrada(fqbn="esp32:esp32:esp32")
        board["matching_boards"].append({"fqbn": "esp32:esp32:esp32s3"})
        with patch.object(self.cli, "discover_boards", return_value=[board]):
            self.assertIsNone(self.cli.detect_fqbn("COM9"))

    def test_prepara_core_esp32_con_indice_oficial(self):
        with patch.object(self.cli, "run", return_value=Mock(stdout="arduino:avr")) as run:
            self.cli.ensure_core("esp32:esp32:esp32")
        self.assertEqual(run.call_count, 3)
        self.assertEqual(
            run.call_args_list[1].args,
            ("core", "update-index", "--additional-urls", ESP32_PACKAGE_URL),
        )
        self.assertEqual(
            run.call_args_list[2].args,
            ("core", "install", "esp32:esp32", "--additional-urls", ESP32_PACKAGE_URL),
        )
        self.assertTrue(all(call.kwargs["check"] for call in run.call_args_list))

    def test_reutiliza_core_instalado(self):
        with patch.object(self.cli, "run", return_value=Mock(stdout="esp32:esp32 3.3.2")) as run:
            self.cli.ensure_core("esp32:esp32:esp32s3")
            self.assertEqual(run.call_count, 1)

    def test_core_arduino_no_usa_indice_esp32(self):
        with patch.object(self.cli, "run", return_value=Mock(stdout="")) as run:
            self.cli.ensure_core("arduino:avr:uno")
        self.assertEqual(run.call_args_list[-1].args, ("core", "install", "arduino:avr"))

    def test_core_invalido_y_fallo_de_instalacion_no_se_ocultan(self):
        with self.assertRaises(ValueError):
            self.cli.ensure_core("esp32")
        with patch.object(self.cli, "run", side_effect=[
            Mock(stdout=""), subprocess.CalledProcessError(1, "core update-index"),
        ]), self.assertRaises(subprocess.CalledProcessError):
            self.cli.ensure_core("esp32:esp32:esp32")

    def test_compile_upload_con_el_mismo_fqbn(self):
        fqbn = "esp32:esp32:esp32c3"
        with patch.object(self.cli, "run") as run:
            self.cli.compile(fqbn, Path("sketch"))
            self.cli.upload("COM9", fqbn, Path("sketch"))
        self.assertEqual(run.call_args_list[0].args, ("compile", "--fqbn", fqbn, "sketch"))
        self.assertEqual(
            run.call_args_list[1].args,
            ("upload", "-p", "COM9", "--fqbn", fqbn, "sketch"),
        )


class PanelTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        patchers = (
            patch.object(panel, "arduino_boards", ARDUINO_BOARDS.copy()),
            patch.object(panel, "esp32_boards", ESP32_BOARDS.copy()),
            patch.object(panel, "guardar_placa"),
            patch.object(panel, "guardar_puerto_default"),
            patch.object(panel, "obtener_puerto_default", return_value=""),
        )
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        with patch.object(self.root, "after"):
            panel.crear_panel(self.root)
        panel.puertos_detectados.clear()
        panel.metadatos_puertos.clear()

    def seleccionar(self, fqbn):
        panel.puertos_detectados["COM9"] = entrada(fqbn=fqbn)
        panel.seleccionar_puerto("", "COM9")

    def estados(self):
        return str(panel.board_combo["state"]), str(panel.esp32_combo["state"])

    def test_listas_lado_a_lado_con_etiquetas_y_colores(self):
        arduino, esp32 = panel.board_combo, panel.esp32_combo
        self.assertEqual(arduino.master, esp32.master)
        self.assertEqual((arduino.grid_info()["column"], esp32.grid_info()["column"]), (0, 1))
        labels = {
            item.cget("text"): item.cget("fg")
            for item in arduino.master.winfo_children() if isinstance(item, tk.Label)
        }
        self.assertEqual(labels, {"Arduino": "cyan", "ESP32": "DarkOrange1"})
        self.assertEqual(self.estados(), ("readonly", "readonly"))

    def test_cambio_de_familia_limpia_seleccion_y_deshabilita_lista_opuesta(self):
        self.seleccionar("arduino:avr:uno")
        self.assertEqual(self.estados(), ("readonly", "disabled"))
        self.assertEqual(panel.fqbn_var.get(), "arduino:avr:uno")
        self.seleccionar("esp32:esp32:esp32s3")
        self.assertEqual(self.estados(), ("disabled", "readonly"))
        self.assertEqual(panel.fqbn_var.get(), "esp32:esp32:esp32s3")
        self.assertEqual(panel.placa_var.get(), "")
        self.assertEqual(panel.esp32_var.get(), "esp32_s3_dev_module")
        self.seleccionar("arduino:avr:uno")
        self.assertEqual(panel.esp32_var.get(), "")

    def test_familia_sin_modelo_bloquea_lista_opuesta_pero_no_inventa_fqbn(self):
        panel.puertos_detectados["COM9"] = entrada(label="ESP32-S3")
        panel.seleccionar_puerto("", "COM9")
        self.assertEqual(self.estados(), ("disabled", "readonly"))
        self.assertEqual(panel.fqbn_var.get(), "")

    def test_puerto_desconocido_y_sin_puertos_habilitan_ambas(self):
        self.seleccionar("esp32:esp32:esp32")
        panel.seleccionar_puerto("USB-SERIAL CH340", "COM3")
        self.assertEqual(self.estados(), ("readonly", "readonly"))
        self.assertEqual(panel.fqbn_var.get(), "")
        self.assertEqual(panel.esp32_var.get(), "")
        panel._actualizar_puertos([], [])
        self.assertEqual(self.estados(), ("readonly", "readonly"))
        self.assertEqual(panel.port_var.get(), "")

    def test_seleccion_manual_cambia_fqbn_y_limpia_la_otra_lista(self):
        panel.port_var.set("COM9")
        panel.placa_var.set("uno")
        panel.on_placa_seleccionada()
        panel.esp32_var.set("esp32_c3_dev_module")
        panel.on_esp32_seleccionada()
        self.assertEqual(panel.fqbn_var.get(), "esp32:esp32:esp32c3")
        self.assertEqual(panel.placa_var.get(), "")
        self.assertEqual(self.estados(), ("readonly", "readonly"))

    def test_fqbn_detectado_fuera_del_catalogo_se_muestra_y_se_usa(self):
        fqbn = "esp32:esp32:esp32s3:CDCOnBoot=cdc"
        self.seleccionar(fqbn)
        self.assertEqual(panel.esp32_var.get(), fqbn)
        self.assertIn(fqbn, panel.esp32_combo["values"])
        self.assertEqual(panel.fqbn_var.get(), fqbn)

    def test_sin_cli_match_se_usan_metadatos_usb(self):
        panel._actualizar_puertos([], [{"puerto": "COM9", "descripcion": "ESP32-S3"}])
        self.assertEqual(self.estados(), ("disabled", "readonly"))
        self.assertEqual(panel.port_var.get(), "COM9")
        self.assertEqual(panel.fqbn_var.get(), "")

    def test_metadatos_wmic_identifican_esp32_sin_modelo(self):
        panel._actualizar_puertos(
            [], r"USB Serial (COM9) USB\VID_303A&PID_1001\123456",
        )
        self.assertEqual(self.estados(), ("disabled", "readonly"))
        self.assertEqual(panel.port_var.get(), "COM9")
        self.assertEqual(panel.fqbn_var.get(), "")

    def test_error_de_escaneo_se_informa_y_rehabilita_ambas_listas(self):
        self.seleccionar("esp32:esp32:esp32")
        with patch.object(panel.threading, "Thread", ImmediateThread), \
                patch.object(panel, "detectar_placas", side_effect=ValueError("JSON invalido")):
            panel.escanear_puertos()
            self.root.update()
        self.assertEqual(self.estados(), ("readonly", "readonly"))
        self.assertEqual(panel.fqbn_var.get(), "")
        self.assertFalse(panel.barCarga._activo)
        self.assertIn("No se pudieron consultar los puertos: JSON invalido", panel.text_output.get("1.0", "end"))

    def test_sketch_incluido_se_carga_en_esp32_con_su_fqbn(self):
        self.seleccionar("esp32:esp32:esp32")
        with patch.object(panel.threading, "Thread", ImmediateThread), \
                patch.object(panel, "_confirmar_reemplazo_firmware", return_value=True), \
                patch.object(panel, "_cargar") as cargar, \
                patch.object(panel.messagebox, "showinfo") as info:
            panel.cargar_sketch()
            self.root.update()
        cargar.assert_called_once_with("esp32:esp32:esp32", panel.SKETCH_PATH, "COM9")
        info.assert_called_once()
        self.assertFalse(panel.barCarga._activo)

    def test_modo_automatico_carga_sketch_en_esp32_detectada(self):
        panel.port_var.set("COM9")
        panel.fqbn_var.set("arduino:avr:uno")
        with patch.object(panel.threading, "Thread", ImmediateThread), \
                patch.object(panel, "_confirmar_reemplazo_firmware", return_value=True), \
                patch.object(panel, "_cargar", side_effect=[
                    subprocess.CalledProcessError(1, "compile"), None,
                ]) as cargar, \
                patch.object(panel.arduino, "detect_fqbn", return_value="esp32:esp32:esp32s3"), \
                patch.object(panel.messagebox, "askyesno", return_value=True), \
                patch.object(panel.messagebox, "showinfo") as info:
            panel.cargar_sketch()
            self.root.update()
        self.assertEqual(
            cargar.call_args_list[-1].args,
            ("esp32:esp32:esp32s3", panel.SKETCH_PATH, "COM9"),
        )
        info.assert_called_once()

    def test_carga_usa_puerto_capturado_y_no_el_valor_actual_del_widget(self):
        panel.port_var.set("COM10")
        with patch.object(panel.arduino, "ensure_core") as core, \
                patch.object(panel.arduino, "compile") as compile_sketch, \
                patch.object(panel.arduino, "upload") as upload:
            panel._cargar("esp32:esp32:esp32", Path("sketch"), "COM9")
        core.assert_called_once_with("esp32:esp32:esp32")
        compile_sketch.assert_called_once_with("esp32:esp32:esp32", Path("sketch"))
        upload.assert_called_once_with("COM9", "esp32:esp32:esp32", Path("sketch"))

    def test_sketch_incluido_conserva_carga_arduino(self):
        self.seleccionar("arduino:avr:uno")
        with patch.object(panel.threading, "Thread", ImmediateThread), \
                patch.object(panel, "_confirmar_reemplazo_firmware", return_value=True), \
                patch.object(panel, "_cargar") as cargar, \
                patch.object(panel.messagebox, "showinfo") as info:
            panel.cargar_sketch()
            self.root.update()
        cargar.assert_called_once_with("arduino:avr:uno", panel.SKETCH_PATH, "COM9")
        info.assert_called_once()
        self.assertFalse(panel.barCarga._activo)

    def test_respaldo_esp32_compila_y_carga_con_fqbn_seleccionado(self):
        self.seleccionar("esp32:esp32:esp32c3")

        def comprobar_sketch(fqbn, path):
            self.assertEqual(fqbn, "esp32:esp32:esp32c3")
            self.assertEqual(path.name, "MiSketch")
            self.assertTrue((path / "MiSketch.ino").is_file())

        with tempfile.TemporaryDirectory() as carpeta:
            archivo = Path(carpeta) / "MiSketch.ino"
            archivo.write_text("void setup() {} void loop() {}", encoding="utf-8")
            with patch.object(panel.filedialog, "askopenfilename", return_value=str(archivo)), \
                    patch.object(panel, "_mostrar_confirmacion_sketch", return_value=True), \
                    patch.object(panel.threading, "Thread", ImmediateThread), \
                    patch.object(panel.arduino, "ensure_core") as core, \
                    patch.object(panel.arduino, "compile", side_effect=comprobar_sketch) as compile_sketch, \
                    patch.object(panel.arduino, "upload") as upload, \
                    patch.object(panel.messagebox, "showinfo") as info:
                panel.cargar_respaldo()
                self.root.update()
                self.assertEqual(compile_sketch.call_count, 1)
                core.assert_called_once_with("esp32:esp32:esp32c3")
                self.assertEqual(upload.call_args.args[:2], ("COM9", "esp32:esp32:esp32c3"))
                self.assertEqual(upload.call_args.args[2], compile_sketch.call_args.args[1])
                info.assert_called_once()

    def test_error_compilando_esp32_no_carga_ni_notifica_exito(self):
        self.seleccionar("esp32:esp32:esp32c3")
        with tempfile.TemporaryDirectory() as carpeta:
            archivo = Path(carpeta) / "MiSketch.ino"
            archivo.write_text("void setup() {} void loop() {}", encoding="utf-8")
            with patch.object(panel.filedialog, "askopenfilename", return_value=str(archivo)), \
                    patch.object(panel, "_mostrar_confirmacion_sketch", return_value=True), \
                    patch.object(panel.threading, "Thread", ImmediateThread), \
                    patch.object(panel.arduino, "ensure_core"), \
                    patch.object(panel.arduino, "compile", side_effect=subprocess.CalledProcessError(1, "compile")), \
                    patch.object(panel.arduino, "upload") as upload, \
                    patch.object(panel.messagebox, "showerror") as error, \
                    patch.object(panel.messagebox, "showinfo") as info:
                panel.cargar_respaldo()
                self.root.update()
                upload.assert_not_called()
                info.assert_not_called()
                error.assert_called_once()
                self.assertIn("compile", error.call_args.args[1])
                self.assertFalse(panel.barCarga._activo)


if __name__ == "__main__":
    unittest.main()
