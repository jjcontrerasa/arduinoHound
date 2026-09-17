import re
import subprocess


def obtener_dispositivos():
    try:
        result = subprocess.run(
            ["wmic", "path", "Win32_PnPEntity", "get", "Name,DeviceID"],
            capture_output=True,
            text=True,
        )
        return result.stdout
    except OSError as error:
        return str(error)


def identificar(linea):
    text = linea.lower()
    if "nano" in text:
        return "Arduino Nano"
    if "uno" in text:
        return "Arduino Uno"
    if "mega" in text:
        return "Arduino Mega"
    if "1a86" in text:
        return "CH340"
    if "0403" in text:
        return "FTDI"
    if "10c4" in text:
        return "CP210x"
    if "usb" in text:
        return "Serial USB"
    return "Serial"


def parsear_dispositivos(salida):
    devices = []
    for line in salida.splitlines():
        line = line.strip()
        if not line or "COM" not in line:
            continue
        if any(value in line for value in ("ROOT\\", "BTH\\", "SWD\\")):
            continue
        port = re.search(r"(COM\d+)", line)
        if not port:
            continue
        vid = re.search(r"VID_([0-9A-F]+)", line)
        pid = re.search(r"PID_([0-9A-F]+)", line)
        serial = re.search(r"\\([^\\]+)$", line)
        devices.append({
            "puerto": port.group(1),
            "nombre": identificar(line),
            "vid": vid.group(1) if vid else "-",
            "pid": pid.group(1) if pid else "-",
            "serial": serial.group(1) if serial else "-",
            "raw": line,
        })
    return devices


def obtener_puertos():
    try:
        result = subprocess.run(
            ["wmic", "path", "Win32_PnPEntity", "get", "Name"],
            capture_output=True,
            text=True,
        )
        return result.stdout
    except OSError:
        return ""


def parsear_puertos(salida):
    devices = []
    for line in salida.splitlines():
        line = line.strip()
        if not line or "COM" not in line:
            continue
        if any(value in line for value in ("ROOT\\", "BTH\\", "SWD\\")):
            continue
        match = re.search(r"(COM\d+)", line)
        if match:
            devices.append({
                "puerto": match.group(1),
                "nombre": line.split("(")[0].strip(),
            })
    return devices
