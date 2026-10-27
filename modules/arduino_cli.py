import json
import subprocess

from .rutas import arduino_cli_path, resource_path, user_data_path


REQUIRED_CORES = ("arduino:avr", "arduino:megaavr")
ESP32_PACKAGE_URL = "https://espressif.github.io/arduino-esp32/package_esp32_index.json"
SKETCH_PATH = resource_path("ArduinoHound")


class ArduinoCLI:
    def __init__(self):
        self.cli_path = arduino_cli_path()
        self.config_path = user_data_path("arduino-cli.yaml")
        self.data_path = user_data_path("arduino_data")
        self.downloads_path = user_data_path("arduino_downloads")
        self.user_path = user_data_path("arduino_user")
        self.command = []

    def ensure_config(self):
        if not self.config_path.exists():
            self.config_path.write_text(
                "board_manager:\n"
                "  additional_urls: []\n"
                "directories:\n"
                f"  data: {self.data_path}\n"
                f"  downloads: {self.downloads_path}\n"
                f"  user: {self.user_path}\n",
                encoding="utf-8",
            )
        self.command = [
            str(self.cli_path),
            "--config-file", str(self.config_path),
            "--config-dir", str(user_data_path()),
        ]
        return self.command

    def run(self, *arguments, **kwargs):
        if not self.command:
            self.ensure_config()
        return subprocess.run(self.command + list(arguments), **kwargs)

    def initialize(self):
        installed = self.run(
            "core", "list", capture_output=True, text=True, check=True
        ).stdout
        missing_cores = [core for core in REQUIRED_CORES if core not in installed]
        if not missing_cores:
            return

        self.run("core", "update-index", check=True)
        for core in missing_cores:
            self.run("core", "install", core, check=True)

    def list_boards(self):
        return self.run("board", "list", capture_output=True, text=True, check=True).stdout

    def discover_boards(self):
        result = self.run(
            "board", "list", "--format", "json",
            capture_output=True, text=True, check=True,
        )
        data = json.loads(result.stdout)
        if not isinstance(data, dict):
            raise ValueError("Arduino CLI no devolvio un objeto de deteccion valido.")
        ports = data.get("detected_ports", [])
        if not isinstance(ports, list) or any(
            not isinstance(entry, dict)
            or not isinstance(entry.get("port"), dict)
            or not isinstance(entry["port"].get("address"), str)
            for entry in ports
        ):
            raise ValueError("Arduino CLI devolvio una lista de puertos invalida.")
        for entry in ports:
            boards = entry.get("matching_boards", [])
            if not isinstance(boards, list) or any(
                not isinstance(board, dict)
                or not isinstance(board.get("fqbn", ""), str)
                or not isinstance(board.get("name", ""), str)
                for board in boards
            ):
                raise ValueError("Arduino CLI devolvio una lista de placas invalida.")
        return ports

    def ensure_core(self, fqbn):
        parts = fqbn.split(":")
        if len(parts) < 3 or not all(parts[:3]):
            raise ValueError(f"FQBN invalido: {fqbn}")
        platform = ":".join(parts[:2])
        installed = self.run("core", "list", capture_output=True, text=True, check=True).stdout
        if platform not in installed:
            extra = (
                ["--additional-urls", ESP32_PACKAGE_URL]
                if platform == "esp32:esp32" else []
            )
            self.run("core", "update-index", *extra, check=True)
            self.run("core", "install", platform, *extra, check=True)

    def compile(self, fqbn, sketch_path=SKETCH_PATH):
        return self.run("compile", "--fqbn", fqbn, str(sketch_path), check=True)

    def upload(self, port, fqbn, sketch_path=SKETCH_PATH):
        return self.run("upload", "-p", port, "--fqbn", fqbn, str(sketch_path), check=True)

    def detect_fqbn(self, port):
        for entry in self.discover_boards():
            if entry["port"]["address"].casefold() == port.strip().casefold():
                fqbns = {
                    board["fqbn"]
                    for board in entry.get("matching_boards", [])
                    if isinstance(board.get("fqbn"), str)
                    and board["fqbn"].count(":") >= 2
                }
                return next(iter(fqbns)) if len(fqbns) == 1 else None
        return None
