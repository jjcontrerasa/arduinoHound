import os
import sys
from pathlib import Path


PROJECT_PATH = Path(__file__).resolve().parent.parent
RESOURCE_PATH = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else PROJECT_PATH

if getattr(sys, "frozen", False):
    USER_DATA_PATH = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ArduinoHound"
else:
    USER_DATA_PATH = PROJECT_PATH

USER_DATA_PATH.mkdir(parents=True, exist_ok=True)


def resource_path(*parts):
    return RESOURCE_PATH.joinpath(*parts)


def user_data_path(*parts):
    path = USER_DATA_PATH.joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def arduino_cli_path():
    return resource_path("arduino-cli.exe")
