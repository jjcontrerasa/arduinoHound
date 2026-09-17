import time

import serial


def leer_datos(puerto, baudrate=115200, timeout=2):
    datos = {"board": "-", "i2c": "-", "uart": "-", "lora": "-", "spi": "-"}
    try:
        with serial.Serial(puerto, baudrate, timeout=timeout) as connection:
            time.sleep(2)
            for _ in range(30):
                line = connection.readline().decode(errors="ignore").strip()
                if line.startswith("BOARD:"):
                    datos["board"] = line.replace("BOARD:", "")
                elif line.startswith("I2C:"):
                    datos["i2c"] = line.replace("I2C:", "")
                elif line.startswith("UART_DEV:"):
                    datos["uart"] = line.replace("UART_DEV:", "")
                elif line.startswith("LORA_INFO:"):
                    datos["lora"] = line.replace("LORA_INFO:", "")
                elif line.startswith("SPI:"):
                    modulo = line.replace("SPI:", "")
                    if datos["spi"] == "-":
                        datos["spi"] = modulo
                    else:
                        datos["spi"] += "," + modulo
    except serial.SerialException:
        datos["board"] = "PUERTO OCUPADO"
    except Exception as error:
        datos["board"] = f"Error: {error}"
    return datos
