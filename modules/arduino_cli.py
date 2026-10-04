import subprocess

from .rutas import arduino_cli_path, resource_path, user_data_path


REQUIRED_CORES = ("arduino:avr", "arduino:megaavr")
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
        return self.run("board", "list", capture_output=True, text=True).stdout

    def ensure_core(self, fqbn):
        platform = ":".join(fqbn.split(":")[:2])
        installed = self.run("core", "list", capture_output=True, text=True).stdout
        if platform not in installed:
            self.run("core", "install", platform, check=True)

    def compile(self, fqbn, sketch_path=SKETCH_PATH):
        return self.run("compile", "--fqbn", fqbn, str(sketch_path), check=True)

    def upload(self, port, fqbn, sketch_path=SKETCH_PATH):
        return self.run("upload", "-p", port, "--fqbn", fqbn, str(sketch_path), check=True)

    def detect_fqbn(self, port):
        for line in self.list_boards().splitlines():
            if port in line:
                for part in line.split():
                    if part.count(":") == 2:
                        return part
        return None
