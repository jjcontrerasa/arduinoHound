import re
import subprocess

try:
    import serial.tools.list_ports as list_ports
except Exception:  # pragma: no cover
    list_ports = None


def obtener_dispositivos():
    if list_ports is not None:
        try:
            dispositivos = []
            for port in list_ports.comports():
                device = getattr(port, "device", "") or getattr(port, "name", "") or ""
                descripcion = getattr(port, "description", "") or ""
                nombre = getattr(port, "name", "") or device
                vid = getattr(port, "vid", None)
                pid = getattr(port, "pid", None)
                serial = getattr(port, "serial_number", None)
                fabricante = getattr(port, "manufacturer", None)
                producto = getattr(port, "product", None)

                dispositivos.append({
                    "puerto": device,
                    "nombre": nombre,
                    "descripcion": descripcion,
                    "vid": f"{vid:04X}" if isinstance(vid, int) else (str(vid) if vid else "-"),
                    "pid": f"{pid:04X}" if isinstance(pid, int) else (str(pid) if pid else "-"),
                    "serial": serial or "-",
                    "fabricante": fabricante or "-",
                    "producto": producto or "-",
                    "raw": f"{descripcion} ({device})" if descripcion and device else (descripcion or device or nombre),
                })
            if dispositivos:
                return dispositivos
        except Exception:
            pass

    try:
        result = subprocess.run(
            ["wmic", "path", "Win32_PnPEntity", "get", "Name,DeviceID,PNPDeviceID"],
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


def familia_fqbn(fqbn):
    if not isinstance(fqbn, str):
        return None
    partes = fqbn.split(":")
    if len(partes) < 3:
        return None
    if partes[1] == "esp32":
        return "esp32"
    if partes[0] == "arduino":
        return "arduino"
    return None


def identificar_placa(entrada, catalogos, dispositivo=None):
    candidatos = {}
    for board in entrada.get("matching_boards", []):
        fqbn = board.get("fqbn", "")
        familia = familia_fqbn(fqbn)
        for grupo, catalogo in catalogos.items():
            for clave, datos in catalogo.items():
                if datos["fqbn"] == fqbn:
                    candidatos[fqbn] = (familia or grupo, clave, datos)
                    break
            else:
                continue
            break
        else:
            if familia:
                candidatos[fqbn] = (
                    familia, fqbn,
                    {"name": board.get("name", fqbn), "fqbn": fqbn, "mcu": "-"},
                )

    if candidatos:
        familias = {value[0] for value in candidatos.values()}
        if len(familias) != 1:
            return None, None, None
        if len(candidatos) == 1:
            return next(iter(candidatos.values()))
        return next(iter(familias)), None, None

    port = entrada.get("port", {})
    dispositivo = dispositivo or {}
    texto = " ".join(
        str(value) for value in (
            port.get("label", ""),
            *(board.get("name", "") for board in entrada.get("matching_boards", [])),
            *(dispositivo.get(field, "") for field in (
                "descripcion", "fabricante", "producto", "raw"
            )),
        )
    )
    normalizado = " " + re.sub(r"[^a-z0-9]+", " ", texto.lower()).strip() + " "
    coincidencias = []
    claves_arduino = []
    for familia, catalogo in catalogos.items():
        for clave, datos in catalogo.items():
            familia_placa = familia_fqbn(datos["fqbn"]) or familia
            nombre = re.sub(r"[^a-z0-9]+", " ", datos["name"].lower()).strip()
            if nombre and f" {nombre} " in normalizado:
                coincidencias.append((len(nombre), familia_placa, clave, datos))
            if familia_placa == "arduino":
                nombre_clave = re.sub(r"[^a-z0-9]+", " ", clave.lower()).strip()
                if nombre_clave and f" {nombre_clave} " in normalizado:
                    claves_arduino.append((len(nombre_clave), familia_placa, clave, datos))
    if coincidencias:
        _, familia, clave, datos = max(coincidencias, key=lambda item: item[0])
        return familia, clave, datos

    propiedades = port.get("properties", {})
    vids = {
        str(value).lower().removeprefix("0x")
        for value in (dispositivo.get("vid"), propiedades.get("vid"))
    }
    if (
        re.search(r"\besp32", texto, re.IGNORECASE)
        or "303a" in vids
    ):
        return "esp32", None, None
    if claves_arduino:
        _, familia, clave, datos = max(claves_arduino, key=lambda item: item[0])
        return familia, clave, datos
    if re.search(r"\barduino\b", texto, re.IGNORECASE):
        return "arduino", None, None
    return None, None, None


def parsear_dispositivos(salida):
    if isinstance(salida, list):
        devices = []
        for item in salida:
            if not isinstance(item, dict):
                continue
            puerto = item.get("puerto") or item.get("device") or ""
            if not puerto:
                continue
            nombre = item.get("descripcion") or item.get("nombre") or item.get("producto") or identificar(str(puerto))
            devices.append({
                "puerto": puerto,
                "nombre": identificar(str(nombre)),
                "vid": str(item.get("vid") or "-").upper(),
                "pid": str(item.get("pid") or "-").upper(),
                "serial": str(item.get("serial") or "-"),
                "raw": str(item.get("raw") or nombre or puerto),
            })
        return devices

    devices = []
    for line in (salida.splitlines() if isinstance(salida, str) else []):
        line = line.strip()
        if not line or "COM" not in line:
            continue
        if any(value in line for value in ("ROOT\\", "BTH\\", "SWD\\")):
            continue
        port = re.search(r"(COM\d+)", line)
        if not port:
            continue

        vid_match = re.search(r"VID_([0-9A-F]+)", line, flags=re.IGNORECASE)
        pid_match = re.search(r"PID_([0-9A-F]+)", line, flags=re.IGNORECASE)
        serial_match = re.search(r"SERIAL_([^\s\]]+)|SN_([^\s\]]+)|\\([^\\]+)$", line, flags=re.IGNORECASE)
        serial_value = None

        if serial_match:
            serial_value = serial_match.group(1) or serial_match.group(2) or serial_match.group(0).strip('\\')

        devices.append({
            "puerto": port.group(1),
            "nombre": identificar(line),
            "vid": vid_match.group(1).upper() if vid_match else "-",
            "pid": pid_match.group(1).upper() if pid_match else "-",
            "serial": serial_value or "-",
            "raw": line,
        })
    return devices


def obtener_puertos():
    if list_ports is not None:
        try:
            puertos = []
            for port in list_ports.comports():
                descripcion = getattr(port, "description", "") or ""
                nombre = getattr(port, "name", "") or ""
                device = getattr(port, "device", "") or nombre or ""
                if descripcion and device:
                    puertos.append(f"{descripcion} ({device})")
                elif device:
                    puertos.append(device)
                elif descripcion:
                    puertos.append(descripcion)
            if puertos:
                return "\n".join(puertos)
        except Exception:
            pass

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
    lines = salida.splitlines() if isinstance(salida, str) else []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if any(value in line for value in ("ROOT\\", "BTH\\", "SWD\\")):
            continue
        match = re.search(r"(COM\d+)", line)
        if not match:
            continue
        puerto = match.group(1)
        nombre = line.split("(")[0].strip() if "(" in line else line.strip()
        nombre = nombre.replace(puerto, "").strip(" -")
        if not nombre:
            nombre = "Puerto serial"
        devices.append({
            "puerto": puerto,
            "nombre": nombre,
        })
    return devices
