import time

import serial


DESCRIPCIONES_I2C = {
    "0x20": "GPIO PCF8574",
    "0x21": "GPIO PCF8574",
    "0x22": "GPIO PCF8574",
    "0x23": "GPIO PCF8574",
    "0x24": "GPIO PCF8574",
    "0x25": "GPIO PCF8574",
    "0x26": "GPIO PCF8574",
    "0x27": "LCD I2C",
    "0x3c": "OLED SSD1306",
    "0x3d": "OLED SSD1306",
    "0x38": "LCD I2C",
    "0x39": "Sensor",
    "0x40": "Sensor / PWM",
    "0x41": "Sensor / PWM",
    "0x48": "ADC ADS1115",
    "0x49": "ADC ADS1115",
    "0x50": "EEPROM",
    "0x51": "EEPROM",
    "0x60": "RTC / Sensor",
    "0x68": "RTC DS3231",
    "0x69": "MPU6050",
    "0x6a": "MPU6050",
    "0x6b": "MPU6050",
    "0x76": "BMP280/BME280",
    "0x77": "BMP180/BMP280/BME280",
    "0x7c": "Sensor",
    "0x7d": "Sensor",
    "0x7e": "Sensor",
    "0x7f": "Sensor",
}


def _valor_vacio(raw_value):
    if raw_value is None:
        return True
    texto = str(raw_value).strip()
    if not texto:
        return True
    texto_norm = texto.lower().replace("i2c:", "")
    return texto_norm in {"-", "none", "ninguno", "unknown", "desconocida", "puerto ocupado"}


def _parsear_direcciones_i2c(raw_value):
    texto = str(raw_value).strip()
    if not texto:
        return []

    texto = texto.replace("I2C:", "").replace(";", ",")
    direcciones = []
    for parte in texto.split(","):
        direccion = parte.strip()
        if not direccion:
            continue
        if direccion.lower() in {"none", "ninguno", "unknown", "-"}:
            continue
        direcciones.append(direccion)
    return direcciones


def formatear_i2c(raw_value):
    direcciones = _parsear_direcciones_i2c(raw_value)
    if not direcciones:
        return "ninguno"

    items = []
    for direccion in direcciones:
        direccion_formateada = direccion.lower()
        if not direccion_formateada.startswith("0x"):
            try:
                direccion_formateada = hex(int(direccion_formateada, 16))
            except ValueError:
                direccion_formateada = direccion
        descripcion = DESCRIPCIONES_I2C.get(direccion_formateada.lower(), "Dispositivo I2C")
        items.append(f"{direccion} - {descripcion}")

    return ", ".join(items) if items else "ninguno"


def formatear_uart(raw_value):
    if _valor_vacio(raw_value):
        return "ninguno"

    texto = str(raw_value).strip()
    if not texto:
        return "ninguno"

    if "=" in texto:
        nombre, _, resto = texto.partition(";")
        nombre = nombre.strip()
        partes = {}
        for item in resto.split(";") if resto else []:
            if "=" not in item:
                continue
            clave, valor = item.split("=", 1)
            partes[clave.strip().upper()] = valor.strip()

        nombre_upper = nombre.upper()
        rx = partes.get("RX", "-")
        tx = partes.get("TX", "-")

        if nombre_upper == "GPS":
            return f"GPS (RX={rx}, TX={tx})"
        if nombre_upper in {"HC12", "HC-12", "HC_12"}:
            return f"HC-12 (RX={rx}, TX={tx})"
        if nombre_upper == "LORA_RYLR998":
            return f"LoRa RYLR998 (RX={rx}, TX={tx})"
        if nombre_upper == "TRANSCEIVER":
            tipo = partes.get("TYPE", "Transceptor UART")
            return f"{tipo} (RX={rx}, TX={tx})"
        if nombre_upper in {"UNKNOWN", "NINGUNO"}:
            return "UART desconocido"
        return f"{nombre} (RX={rx}, TX={tx})"

    texto_upper = texto.upper()
    if texto_upper in {"GPS", "HC12", "HC-12", "HC_12"}:
        return texto
    if texto_upper in {"UNKNOWN", "NONE", "NINGUNO"}:
        return "ninguno"
    if texto_upper == "TRANSCEIVER":
        return "Transceptor UART detectado"
    if texto_upper.startswith("UART_DEV:"):
        return texto.replace("UART_DEV:", "")
    return texto


def leer_datos(puerto, baudrate=115200, timeout=2, on_evento=None):
    """Lee el ciclo de detección del sketch.

    on_evento(tipo, valor) se invoca en cuanto llega la línea correspondiente,
    con tipo en {"uart", "i2c", "spi", "gps_coords"}, para poder actualizar
    la interfaz en tiempo real conforme cada protocolo termina de escanear.
    """
    datos = {"board": "-", "i2c": "-", "i2c_pines": "-", "uart": "-", "lora": "-", "spi": "-", "gps_coords": None}
    try:
        with serial.Serial(puerto, baudrate, timeout=timeout) as connection:
            time.sleep(2)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                line = connection.readline().decode(errors="ignore").strip()
                if not line:
                    continue
                if line.startswith("BOARD:"):
                    datos["board"] = line.replace("BOARD:", "")
                elif line.startswith("I2C_PINS:"):
                    datos["i2c_pines"] = line.replace("I2C_PINS:", "", 1)
                elif line.startswith("I2C:") or line.startswith("I2C"):
                    raw_i2c = line.replace("I2C:", "", 1)
                    datos["i2c"] = formatear_i2c(raw_i2c)
                    if on_evento:
                        on_evento("i2c", datos["i2c"])
                elif line.startswith("UART_DEV:"):
                    datos["uart"] = formatear_uart(line.replace("UART_DEV:", ""))
                    if on_evento:
                        on_evento("uart", datos["uart"])
                elif line.startswith("LORA_INFO:"):
                    datos["lora"] = line.replace("LORA_INFO:", "")
                elif line.startswith("GPS_COORDS:"):
                    datos["gps_coords"] = line.replace("GPS_COORDS:", "")
                    if on_evento:
                        on_evento("gps_coords", datos["gps_coords"])
                elif line.startswith("SPI:"):
                    modulo = line.replace("SPI:", "")
                    if datos["spi"] == "-":
                        datos["spi"] = modulo
                    else:
                        datos["spi"] += "," + modulo
                elif line.startswith("STATUS:READY"):
                    if on_evento:
                        on_evento("spi", datos["spi"])
                    break

                if on_evento:
                    on_evento("debug", line)

                if line.startswith("STATUS:READY"):
                    break
    except serial.SerialException:
        datos["board"] = "PUERTO OCUPADO"
    except Exception as error:
        datos["board"] = f"Error: {error}"
    return datos
