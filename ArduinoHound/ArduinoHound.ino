#include <Wire.h>
#include <SPI.h>
#if defined(ARDUINO_AVR_NANO_EVERY) || defined(ARDUINO_AVR_MEGA2560) || defined(ARDUINO_AVR_MEGA1280)
#include <SD.h>
#define ARDUINOHOUND_SD_DETECTION
#endif

// ================= CONFIGURACIÓN DE LA PLACA =================
#if defined(ARDUINO_AVR_NANO_EVERY)
  #include <SoftwareSerial.h>
  #define uart Serial1
  #define BOARD_NAME "NANO_EVERY"
#elif defined(ARDUINO_AVR_MEGA2560)
  #include <SoftwareSerial.h>
  #define uart Serial1
  #define BOARD_NAME "MEGA2560"
#elif defined(ARDUINO_AVR_MEGA1280)
  #include <SoftwareSerial.h>
  #define uart Serial1
  #define BOARD_NAME "MEGA1280"
#elif defined(ARDUINO_AVR_LEONARDO)
  #define uart Serial1
  #define BOARD_NAME "LEONARDO"
#elif defined(ARDUINO_AVR_MICRO)
  #define uart Serial1
  #define BOARD_NAME "MICRO"
#elif defined(ARDUINO_AVR_UNO)
  #include <SoftwareSerial.h>
  SoftwareSerial uart(2, 3);
  #define BOARD_NAME "UNO"
#elif defined(ARDUINO_AVR_NANO)
  #include <SoftwareSerial.h>
  SoftwareSerial uart(2, 3);
  #define BOARD_NAME "NANO"
#else
  #include <SoftwareSerial.h>
  SoftwareSerial uart(2, 3);
  #define BOARD_NAME "UNKNOWN"
#endif

#define UART_BAUD 9600
#define GPS_BAUD 9600
#define SERIAL_SCAN_MIN_PIN 2
#define SERIAL_SCAN_MAX_PIN 13
const unsigned long UART_SCAN_BAUDS[] = {9600, 57600, 115200};
bool pinesCSDetectados[SERIAL_SCAN_MAX_PIN + 1] = {false};
bool pinesUARTDetectados[SERIAL_SCAN_MAX_PIN + 1] = {false};
bool hc12Encontrado = false;

void registrarPinCS(byte pin) {
  if (pin <= SERIAL_SCAN_MAX_PIN) {
    pinesCSDetectados[pin] = true;
  }
}

void registrarPinesUART(byte rxPin, byte txPin) {
  if (rxPin <= SERIAL_SCAN_MAX_PIN) {
    pinesUARTDetectados[rxPin] = true;
  }
  if (txPin <= SERIAL_SCAN_MAX_PIN) {
    pinesUARTDetectados[txPin] = true;
  }
}

void limpiarPinesDetectados() {
  for (byte pin = 0; pin <= SERIAL_SCAN_MAX_PIN; pin++) {
    pinesCSDetectados[pin] = false;
    pinesUARTDetectados[pin] = false;
  }
  hc12Encontrado = false;
}

// ================= CONFIGURACIÓN DE MÓDULOS SPI =================
// La salida SPI es adicional y conserva el protocolo serial existente.
// Los dos primeros pines conservan la configuración original. El escaneo
// automático prueba también otros GPIO que pueden usarse como CS.
#define AUTO_SCAN_SPI_CS 1

struct ModuloSPI {
  const char* nombre;
  byte csPin;
  byte regID;
  byte valorEsperado;
};

ModuloSPI modulosSPI[] = {
  {"ADXL345", 9, 0x00, 0xE5},
  {"LoRa SX1278", 10, 0x42, 0x12}
};

const int NUM_MODULOS_SPI = sizeof(modulosSPI) / sizeof(ModuloSPI);

// Memorias flash SPI: usan el comando fijo JEDEC ID (0x9F) en vez del
// esquema de registro + bit de lectura que usan sensores como el ADXL345.
struct ModuloFlashSPI {
  const char* nombre;
  byte csPin;
  byte manufacturerID;
  byte memoryType;
  byte capacidad;
};

ModuloFlashSPI modulosFlashSPI[] = {
  {"W25Q64", 4, 0xEF, 0x40, 0x17}
};

const int NUM_MODULOS_FLASH_SPI = sizeof(modulosFlashSPI) / sizeof(ModuloFlashSPI);

byte leerRegistroSPI(int csPin, byte registro) {
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
  digitalWrite(csPin, LOW);
  SPI.transfer(registro | 0x80);
  byte valor = SPI.transfer(0x00);
  digitalWrite(csPin, HIGH);
  SPI.endTransaction();
  return valor;
}

bool esPinSPIExcluido(byte pin) {
  // No usar UART USB ni las líneas físicas de los buses SPI e I2C como CS.
  if (pin == 0 || pin == 1 || pin == MOSI || pin == MISO || pin == SCK) {
    return true;
  }
#if defined(ARDUINO_AVR_NANO_EVERY)
  if (pin == A4 || pin == A5) {
    return true;
  }
#endif
#if defined(PIN_WIRE_SDA)
  if (pin == PIN_WIRE_SDA) {
    return true;
  }
#endif
#if defined(PIN_WIRE_SCL)
  if (pin == PIN_WIRE_SCL) {
    return true;
  }
#endif

  return false;
}

bool csYaConfigurado(byte pin) {
  for (int i = 0; i < NUM_MODULOS_SPI; i++) {
    if (modulosSPI[i].csPin == pin) {
      return true;
    }
  }
  for (int i = 0; i < NUM_MODULOS_FLASH_SPI; i++) {
    if (modulosFlashSPI[i].csPin == pin) {
      return true;
    }
  }
  return false;
}

void leerJEDEC_ID(int csPin, byte &manufacturer, byte &tipo, byte &capacidad) {
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
  digitalWrite(csPin, LOW);
  SPI.transfer(0x9F);
  manufacturer = SPI.transfer(0x00);
  tipo = SPI.transfer(0x00);
  capacidad = SPI.transfer(0x00);
  digitalWrite(csPin, HIGH);
  SPI.endTransaction();
}

bool probarFlashSPI(int modulo) {
  byte csPin = modulosFlashSPI[modulo].csPin;
  byte manufacturer, tipo, capacidad;
  leerJEDEC_ID(csPin, manufacturer, tipo, capacidad);

  if (manufacturer != modulosFlashSPI[modulo].manufacturerID ||
      tipo != modulosFlashSPI[modulo].memoryType ||
      capacidad != modulosFlashSPI[modulo].capacidad) {
    return false;
  }

  registrarPinCS(csPin);
  Serial.print("SPI:");
  Serial.print(modulosFlashSPI[modulo].nombre);
  Serial.print(";CS=D");
  Serial.print(csPin);
  Serial.print(";CMD=0x9F;DATA=0x");
  Serial.print(manufacturer, HEX);
  Serial.print(tipo, HEX);
  Serial.println(capacidad, HEX);
  return true;
}

bool probarModuloSPI(byte csPin, int modulo) {
  byte id = leerRegistroSPI(csPin, modulosSPI[modulo].regID);

  if (id != modulosSPI[modulo].valorEsperado) {
    return false;
  }

  registrarPinCS(csPin);
  Serial.print("SPI:");
  Serial.print(modulosSPI[modulo].nombre);
  Serial.print(";CS=D");
  Serial.print(csPin);
  Serial.print(";CMD=0x");
  Serial.print(modulosSPI[modulo].regID | 0x80, HEX);
  Serial.print(";DATA=0x");
  Serial.print(id, HEX);
  Serial.println(";MODE=0");
  return true;
}

bool probarDispositivoSPIGenerico(byte csPin, byte &comandoDetectado,
                                  byte &respuestaDetectada, byte &modoDetectado) {
  const byte comandos[] = {0x00, 0x9F};
  const byte modos[] = {SPI_MODE0, SPI_MODE1, SPI_MODE2, SPI_MODE3};

  for (byte comando = 0; comando < sizeof(comandos); comando++) {
    for (byte modo = 0; modo < sizeof(modos); modo++) {
      byte respuestas[3];

      for (byte muestra = 0; muestra < 3; muestra++) {
        SPI.beginTransaction(SPISettings(100000, MSBFIRST, modos[modo]));
        digitalWrite(csPin, LOW);
        SPI.transfer(comandos[comando]);
        respuestas[muestra] = SPI.transfer(0x00);
        digitalWrite(csPin, HIGH);
        SPI.endTransaction();
        delayMicroseconds(50);
      }

      // SPI no define una consulta universal; se descartan MISO inactivo y lecturas inestables.
      if (respuestas[0] != 0x00 && respuestas[0] != 0xFF &&
          respuestas[0] == respuestas[1] && respuestas[1] == respuestas[2]) {
        comandoDetectado = comandos[comando];
        respuestaDetectada = respuestas[0];
        modoDetectado = modo;
        return true;
      }
    }
  }

  return false;
}

bool probarBMP280(byte csPin, byte &idDetectado, byte &modoDetectado) {
  const byte modos[] = {SPI_MODE0, SPI_MODE3};

  for (byte modo = 0; modo < sizeof(modos); modo++) {
    byte ids[2];

    for (byte muestra = 0; muestra < 2; muestra++) {
      SPI.beginTransaction(SPISettings(100000, MSBFIRST, modos[modo]));
      digitalWrite(csPin, LOW);
      SPI.transfer(0xD0);
      ids[muestra] = SPI.transfer(0x00);
      digitalWrite(csPin, HIGH);
      SPI.endTransaction();
      delayMicroseconds(50);
    }

    if (ids[0] == ids[1] && (ids[0] == 0x58 || ids[0] == 0x60)) {
      idDetectado = ids[0];
      modoDetectado = modo == 0 ? 0 : 3;
      return true;
    }
  }

  return false;
}

#if defined(ARDUINOHOUND_SD_DETECTION)
void leerEstadoTarjetaSD(byte csPin, byte &respuestaR1, byte &estadoR2) {
  respuestaR1 = 0xFF;
  estadoR2 = 0xFF;

  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
  digitalWrite(csPin, HIGH);
  SPI.transfer(0xFF);
  digitalWrite(csPin, LOW);
  SPI.transfer(0x4D);
  SPI.transfer(0x00);
  SPI.transfer(0x00);
  SPI.transfer(0x00);
  SPI.transfer(0x00);
  SPI.transfer(0x01);

  for (byte intento = 0; intento < 8; intento++) {
    respuestaR1 = SPI.transfer(0xFF);
    if ((respuestaR1 & 0x80) == 0) {
      estadoR2 = SPI.transfer(0xFF);
      break;
    }
  }

  digitalWrite(csPin, HIGH);
  SPI.transfer(0xFF);
  SPI.endTransaction();

}

bool detectarTarjetaSD(byte &csEncontrado) {
  const byte csPins[] = {2, 3, 4, 5, 6, 7, 8, 9, 10};

  for (byte i = 0; i < sizeof(csPins); i++) {
    byte csPin = csPins[i];
    if (esPinSPIExcluido(csPin)) {
      continue;
    }

    pinMode(csPin, OUTPUT);
    digitalWrite(csPin, HIGH);
    delay(100);

    if (SD.begin(csPin)) {
      digitalWrite(csPin, HIGH);
      csEncontrado = csPin;
      registrarPinCS(csPin);
      byte respuestaR1, estadoR2;
      leerEstadoTarjetaSD(csPin, respuestaR1, estadoR2);
      Serial.print("SPI:Tarjeta SD;CS=D");
      Serial.print(csPin);
      Serial.print(";CMD=0xD;R1=0x");
      Serial.print(respuestaR1, HEX);
      Serial.print(";DATA=0x");
      Serial.print(estadoR2, HEX);
      Serial.print(";MODE=");
      Serial.println(SPI_MODE0);
      return true;
    }

    digitalWrite(csPin, HIGH);
  }

  return false;
}
#endif

void detectarSPI() {
  for (int pin = 2; pin <= 10; pin++) {
    byte csPin = (byte)pin;
    if (!esPinSPIExcluido(csPin)) {
      pinMode(csPin, OUTPUT);
      digitalWrite(csPin, HIGH);
    }
  }

  for (int i = 0; i < NUM_MODULOS_SPI; i++) {
    pinMode(modulosSPI[i].csPin, OUTPUT);
    digitalWrite(modulosSPI[i].csPin, HIGH);
  }
  for (int i = 0; i < NUM_MODULOS_FLASH_SPI; i++) {
    pinMode(modulosFlashSPI[i].csPin, OUTPUT);
    digitalWrite(modulosFlashSPI[i].csPin, HIGH);
  }

  bool encontrados[NUM_MODULOS_SPI] = {false};
  bool encontradosFlash[NUM_MODULOS_FLASH_SPI] = {false};
  byte sdCsPin = 0;
  bool sdEncontrada = false;
#if defined(ARDUINOHOUND_SD_DETECTION)
  sdEncontrada = detectarTarjetaSD(sdCsPin);
#endif

  // Primero se prueban los pines declarados explícitamente.
  for (int modulo = 0; modulo < NUM_MODULOS_SPI; modulo++) {
    byte csPin = modulosSPI[modulo].csPin;

    if (!(sdEncontrada && csPin == sdCsPin) &&
        !encontrados[modulo] && probarModuloSPI(csPin, modulo)) {
      encontrados[modulo] = true;
    }
  }

  for (int modulo = 0; modulo < NUM_MODULOS_FLASH_SPI; modulo++) {
    if (!(sdEncontrada && modulosFlashSPI[modulo].csPin == sdCsPin) &&
        !encontradosFlash[modulo] && probarFlashSPI(modulo)) {
      encontradosFlash[modulo] = true;
    }
  }

#if AUTO_SCAN_SPI_CS
  // Después se recorren los GPIO disponibles para configuraciones distintas.
  #if defined(NUM_DIGITAL_PINS)
    const int totalPines = NUM_DIGITAL_PINS;
  #else
    const int totalPines = 20;
  #endif

  for (int pin = 2; pin < totalPines; pin++) {
    byte csPin = (byte)pin;

    if (csYaConfigurado(csPin) || esPinSPIExcluido(csPin)) {
      continue;
    }

    pinMode(csPin, OUTPUT);
    digitalWrite(csPin, HIGH);

    for (int modulo = 0; modulo < NUM_MODULOS_SPI; modulo++) {
      if (probarModuloSPI(csPin, modulo)) {
        encontrados[modulo] = true;
      }
    }
  }
#endif

  // Barrido genérico: los módulos ya identificados conservan su nombre conocido.
  bool encontradoGenerico = false;
  bool encontradoBMP280 = false;
  for (int pin = 2; pin <= 10; pin++) {
    byte csPin = (byte)pin;
    bool yaDetectado = pinesCSDetectados[csPin] ||
               (sdEncontrada && csPin == sdCsPin);

    if (esPinSPIExcluido(csPin)) {
      continue;
    }

    for (int modulo = 0; modulo < NUM_MODULOS_SPI; modulo++) {
      if (modulosSPI[modulo].csPin == csPin && encontrados[modulo]) {
        yaDetectado = true;
      }
    }
    for (int modulo = 0; modulo < NUM_MODULOS_FLASH_SPI; modulo++) {
      if (modulosFlashSPI[modulo].csPin == csPin && encontradosFlash[modulo]) {
        yaDetectado = true;
      }
    }

    if (yaDetectado) {
      continue;
    }

    byte bmpId, bmpModo;
    if (probarBMP280(csPin, bmpId, bmpModo)) {
      encontradoBMP280 = true;
      registrarPinCS(csPin);
      Serial.print(bmpId == 0x58 ? "SPI:BMP280;CS=D" : "SPI:BME280;CS=D");
      Serial.print(csPin);
      Serial.print(";CMD=0xD0;DATA=0x");
      Serial.print(bmpId, HEX);
      Serial.print(";MODE=");
      Serial.println(bmpModo);
      continue;
    }

    byte comando, respuesta, modo;
    if (probarDispositivoSPIGenerico(csPin, comando, respuesta, modo)) {
      encontradoGenerico = true;
      registrarPinCS(csPin);
      Serial.print("SPI:Posible dispositivo SPI;CS=D");
      Serial.print(csPin);
      Serial.print(";CMD=0x");
      Serial.print(comando, HEX);
      Serial.print(";DATA=0x");
      Serial.print(respuesta, HEX);
      Serial.print(";MODE=");
      Serial.println(modo);
    }
  }

  bool encontrado = sdEncontrada || encontradoBMP280 || encontradoGenerico;
  for (int modulo = 0; modulo < NUM_MODULOS_SPI; modulo++) {
    if (encontrados[modulo]) {
      encontrado = true;
    }
  }
  for (int modulo = 0; modulo < NUM_MODULOS_FLASH_SPI; modulo++) {
    if (encontradosFlash[modulo]) {
      encontrado = true;
    }
  }

  if (!encontrado) {
    Serial.println("SPI:NONE");
  }
}

// ================= CONSULTA DE PARÁMETROS LORA =================
// Envía un comando AT y recopila la respuesta del módulo RYLR998.
String consultarLora(const char *comando, unsigned long baudRate) {
  uart.end();
  uart.begin(baudRate);
  delay(5);
  uart.println(comando);

  unsigned long inicio = millis();
  unsigned long ultimoByte = inicio;
  String respuesta;

  while (millis() - inicio < 150) {
    while (uart.available()) {
      char caracter = uart.read();
      ultimoByte = millis();

      if (caracter != '\r' && caracter != '\n') {
        respuesta += caracter;
      }
    }
    if (respuesta.length() > 0 && millis() - ultimoByte >= 25) {
      break;
    }
    delay(1);
  }

  uart.end();
  uart.begin(UART_BAUD);
  return respuesta;
}

bool esPinSerialPermitido(byte pin) {
  if (pin == 0 || pin == 1) {
    return false;
  }

  if (pin == MOSI || pin == MISO || pin == SCK) {
    return false;
  }

  if (pin == 18 || pin == 19 || pin == 20 || pin == 21) {
    return false;
  }

  return true;
}

String leerRespuestaSoftware(SoftwareSerial &puerto, unsigned long timeout) {
  unsigned long inicio = millis();
  unsigned long ultimoByte = inicio;
  String respuesta = "";

  while (millis() - inicio < timeout) {
    while (puerto.available()) {
      char c = puerto.read();
      ultimoByte = millis();
      if (c == '\r' || c == '\n') {
        if (respuesta.length() > 0) {
          respuesta += ' ';
        }
        continue;
      }
      respuesta += c;
    }
    if (respuesta.length() > 0 && millis() - ultimoByte >= 25) {
      break;
    }
    delay(1);
  }

  return respuesta;
}

bool leerGPSSoftware(SoftwareSerial &puerto, unsigned long timeout, float &lat, float &lon) {
  unsigned long inicio = millis();
  bool detectado = false;
  String trama = "";

  while (millis() - inicio < timeout) {
    while (puerto.available()) {
      char c = puerto.read();
      if (c == '$') {
        detectado = true;
        trama = "$";
      } else if (trama.length() > 0) {
        trama += c;
        if (c == '\n') {
          trama.trim();
          String cabecera = trama;
          cabecera.toUpperCase();
          if (cabecera.startsWith("$GP") || cabecera.startsWith("$GN") ||
              cabecera.startsWith("$GL") || cabecera.startsWith("$BD")) {
            detectado = true;
            parsearCoordenadasNMEA(trama, lat, lon);
          }
          trama = "";
        }
      }
    }
    delay(5);
  }

  return detectado;
}

bool esRespuestaTransceptor(const String &respuesta) {
  String texto = respuesta;
  texto.toUpperCase();

  return respuesta.length() > 0 && (
    texto.indexOf("OK") >= 0 ||
    texto.indexOf("HC-12") >= 0 ||
    texto.indexOf("MODE") >= 0 ||
    texto.indexOf("VERSION") >= 0 ||
    texto.indexOf("RF") >= 0 ||
    texto.indexOf("DATA") >= 0 ||
    texto.indexOf("SET") >= 0 ||
    texto.indexOf("BAUD") >= 0 ||
    texto.indexOf("CFG") >= 0 ||
    texto.indexOf("TX") >= 0 ||
    texto.indexOf("RX") >= 0
  );
}

void informarGPS(byte rxPin, byte txPin, float lat, float lon, bool coordsListas) {
  if (rxPin != 0 || txPin != 0) {
    registrarPinesUART(rxPin, txPin);
  }
  Serial.print("UART_DEV:GPS;RX=");
  Serial.print(rxPin);
  Serial.print(";TX=");
  Serial.print(txPin);
  Serial.println();

  if (coordsListas) {
    Serial.print("GPS_COORDS:");
    Serial.print(lat, 6);
    Serial.print(",");
    Serial.println(lon, 6);
  }
}

bool probarPuertoSerial(byte rxPin, byte txPin) {
  if (rxPin == txPin || !esPinSerialPermitido(rxPin) || !esPinSerialPermitido(txPin)) {
    return false;
  }

  SoftwareSerial prueba(rxPin, txPin);
  for (byte indiceBaud = 0; indiceBaud < sizeof(UART_SCAN_BAUDS) / sizeof(UART_SCAN_BAUDS[0]); indiceBaud++) {
    prueba.begin(UART_SCAN_BAUDS[indiceBaud]);
    delay(5);

    prueba.println("AT");
    String respuesta = leerRespuestaSoftware(prueba, 120);
    bool esHC12 = respuesta.indexOf("OK+") >= 0 || respuesta.indexOf("HC-12") >= 0;
    if (esHC12) {
      hc12Encontrado = true;
      registrarPinesUART(rxPin, txPin);
      Serial.print("UART_DEV:HC12;RX=");
      Serial.print(rxPin);
      Serial.print(";TX=");
      Serial.print(txPin);
      Serial.print(";BAUD=");
      Serial.println(UART_SCAN_BAUDS[indiceBaud]);
      Serial.print("UART_INFO:");
      Serial.println(respuesta);
      prueba.end();
      return true;
    }

    prueba.println("AT+ADDRESS?");
    String respuestaLora = leerRespuestaSoftware(prueba, 120);
    if (respuestaLora.indexOf("+ADDRESS=") >= 0) {
      registrarPinesUART(rxPin, txPin);
      Serial.print("UART_DEV:LORA_RYLR998;RX=");
      Serial.print(rxPin);
      Serial.print(";TX=");
      Serial.print(txPin);
      Serial.print(";BAUD=");
      Serial.println(UART_SCAN_BAUDS[indiceBaud]);
      Serial.print("LORA_INFO:");
      Serial.println(respuestaLora);
      prueba.end();
      return true;
    }

    if (esRespuestaTransceptor(respuesta)) {
      registrarPinesUART(rxPin, txPin);
      Serial.print("UART_DEV:TRANSCEIVER;RX=");
      Serial.print(rxPin);
      Serial.print(";TX=");
      Serial.print(txPin);
      Serial.print(";BAUD=");
      Serial.println(UART_SCAN_BAUDS[indiceBaud]);
      Serial.print("UART_INFO:");
      Serial.println(respuesta);
      prueba.end();
      return true;
    }
  }

  prueba.end();
  return false;
}

bool escanearGPSSoftware() {
  bool encontrado = false;

  for (byte rxPin = SERIAL_SCAN_MIN_PIN; rxPin <= SERIAL_SCAN_MAX_PIN; rxPin++) {
    if (!esPinSerialPermitido(rxPin)) {
      continue;
    }

    byte txPin = rxPin == SERIAL_SCAN_MIN_PIN ? SERIAL_SCAN_MIN_PIN + 1 : SERIAL_SCAN_MIN_PIN;
    if (!esPinSerialPermitido(txPin) || txPin == rxPin) {
      continue;
    }

    SoftwareSerial prueba(rxPin, txPin);
    prueba.begin(GPS_BAUD);
    delay(5);

    float lat = 0.0, lon = 0.0;
    if (leerGPSSoftware(prueba, 1200, lat, lon)) {
      informarGPS(rxPin, txPin, lat, lon, lat != 0.0 || lon != 0.0);
      encontrado = true;
      prueba.end();
      break;
    }
    prueba.end();
  }

  return encontrado;
}

bool escanearPuertosSerial(bool buscarGPS) {
  bool encontrado = buscarGPS && escanearGPSSoftware();

  for (byte rx = SERIAL_SCAN_MIN_PIN; rx <= SERIAL_SCAN_MAX_PIN; rx++) {
    for (byte tx = SERIAL_SCAN_MIN_PIN; tx <= SERIAL_SCAN_MAX_PIN; tx++) {
      if (rx == tx || !esPinSerialPermitido(rx) || !esPinSerialPermitido(tx)) {
        continue;
      }
      if (probarPuertoSerial(rx, tx)) {
        encontrado = true;
      }
    }
  }

  return encontrado;
}

bool esRespuestaHC12(const String &respuesta) {
  String texto = respuesta;
  texto.toUpperCase();
  return texto.indexOf("OK+FU") >= 0 || texto.indexOf("OK+HC-12") >= 0;
}

bool probarHC12ConSET(byte setPin, byte rxPin, byte txPin, unsigned long baudRate) {
  if (rxPin == txPin || rxPin == setPin || txPin == setPin ||
      !esPinSerialPermitido(rxPin) || !esPinSerialPermitido(txPin) ||
      pinesCSDetectados[rxPin] || pinesCSDetectados[txPin]) {
    return false;
  }

  SoftwareSerial prueba(rxPin, txPin);
  prueba.begin(baudRate);
  delay(5);
  prueba.println("AT+RX");
  String respuesta = leerRespuestaSoftware(prueba, 45);
  prueba.end();

  if (!esRespuestaHC12(respuesta)) {
    return false;
  }

  hc12Encontrado = true;
  registrarPinesUART(rxPin, txPin);
  Serial.print("UART_DEV:HC12;RX=");
  Serial.print(rxPin);
  Serial.print(";TX=");
  Serial.print(txPin);
  Serial.print(";SET=");
  Serial.print(setPin);
  Serial.print(";BAUD=");
  Serial.println(baudRate);
  Serial.print("UART_INFO:");
  Serial.println(respuesta);
  return true;
}

bool escanearPinSET(byte setPin) {
  pinMode(setPin, OUTPUT);
  digitalWrite(setPin, LOW);
  delay(40);

  bool encontrado = false;
  for (byte rxPin = SERIAL_SCAN_MIN_PIN; rxPin <= SERIAL_SCAN_MAX_PIN; rxPin++) {
    if (!esPinSerialPermitido(rxPin) || pinesCSDetectados[rxPin] || rxPin == setPin) {
      continue;
    }
    for (byte txPin = SERIAL_SCAN_MIN_PIN; txPin <= SERIAL_SCAN_MAX_PIN; txPin++) {
      for (byte indiceBaud = 0; indiceBaud < sizeof(UART_SCAN_BAUDS) / sizeof(UART_SCAN_BAUDS[0]); indiceBaud++) {
        if (probarHC12ConSET(setPin, rxPin, txPin, UART_SCAN_BAUDS[indiceBaud])) {
          encontrado = true;
          break;
        }
      }
    }
  }

  pinMode(setPin, INPUT_PULLUP);
  return encontrado;
}

bool escanearPinesSET() {
  const byte pinesSET[] = {4, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13};
  bool encontrado = false;

  for (byte i = 0; i < sizeof(pinesSET); i++) {
    byte setPin = pinesSET[i];
    if (!esPinSerialPermitido(setPin) || pinesCSDetectados[setPin] ||
        pinesUARTDetectados[setPin]) {
      continue;
    }
    if (escanearPinSET(setPin)) {
      encontrado = true;
    }
  }

  return encontrado;
}

void setup() {
  // Inicializa el puerto USB para enviar resultados al programa Python.
  Serial.begin(115200);

  // Inicializa la UART conectada al GPS o al módulo LoRa.
  uart.begin(UART_BAUD);

  // Inicializa el bus I2C para detectar periféricos conectados.
  Wire.begin();

  // Inicializa el bus SPI y los pines Chip Select de los módulos conocidos.
  SPI.begin();
  for (int i = 0; i < NUM_MODULOS_SPI; i++) {
    pinMode(modulosSPI[i].csPin, OUTPUT);
    digitalWrite(modulosSPI[i].csPin, HIGH);
  }
  for (int i = 0; i < NUM_MODULOS_FLASH_SPI; i++) {
    pinMode(modulosFlashSPI[i].csPin, OUTPUT);
    digitalWrite(modulosFlashSPI[i].csPin, HIGH);
  }

#if AUTO_SCAN_SPI_CS
  #if defined(NUM_DIGITAL_PINS)
    const int totalPinesSPI = NUM_DIGITAL_PINS;
  #else
    const int totalPinesSPI = 20;
  #endif

  for (int pin = 2; pin < totalPinesSPI; pin++) {
    byte csPin = (byte)pin;
    if (!csYaConfigurado(csPin) && !esPinSPIExcluido(csPin)) {
      pinMode(csPin, OUTPUT);
      digitalWrite(csPin, HIGH);
    }
  }
#endif

  delay(1000);

  // Notifica que la placa terminó su inicialización.
  Serial.println("INIT:");
}


// ================= LOOP =================
void loop() {

  limpiarPinesDetectados();

  // -------- SUBPROCESO 1: IDENTIFICACIÓN DE LA PLACA --------
  // Es una salida inmediata y no requiere comunicación con dispositivos.
  Serial.print("BOARD:");
  Serial.println(BOARD_NAME);

  // -------- SUBPROCESO 2: DETECCIÓN DE DISPOSITIVOS I2C --------
  detectarI2C();

  // -------- SUBPROCESO 3: DETECCIÓN DE DISPOSITIVOS SPI --------
  detectarSPI();

  // -------- SUBPROCESO 4: DETECCIÓN UART Y GPS --------
  // La detección GPS forma parte de esta fase y no depende de obtener fix.
  detectarGPS();

  // Indica al programa Python que terminó el ciclo de detección.
  Serial.println("STATUS:READY");

  delay(3000);
}


// ================= DETECCIÓN DE DISPOSITIVOS I2C =================
void informarPinesI2C() {
  Serial.print("I2C_PINS:SDA=");
#if defined(ARDUINO_AVR_MEGA2560) || defined(ARDUINO_AVR_MEGA1280)
  Serial.print("D20");
#elif defined(ARDUINO_AVR_LEONARDO) || defined(ARDUINO_AVR_MICRO)
  Serial.print("D2");
#elif defined(ARDUINO_AVR_NANO_EVERY)
  Serial.print("A4");
#else
  Serial.print("A4");
#endif
  Serial.print(";SCL=");
#if defined(ARDUINO_AVR_MEGA2560) || defined(ARDUINO_AVR_MEGA1280)
  Serial.println("D21");
#elif defined(ARDUINO_AVR_LEONARDO) || defined(ARDUINO_AVR_MICRO)
  Serial.println("D3");
#elif defined(ARDUINO_AVR_NANO_EVERY)
  Serial.println("A5");
#else
  Serial.println("A5");
#endif
}

// Recorre las direcciones I2C y reporta las que responden correctamente.
void detectarI2C() {
  byte direccionesEncontradas[126];
  byte address;
  byte found = 0;

  informarPinesI2C();

  for (address = 1; address < 127; address++) {
    Wire.beginTransmission(address);
    if (Wire.endTransmission() == 0) {
      direccionesEncontradas[found++] = address;
    }

    delay(5);
  }

  Serial.print("I2C:");
  if (found == 0) {
    Serial.print("NONE");
  } else {
    for (byte indice = 0; indice < found; indice++) {
      if (indice > 0) {
        Serial.print(",");
      }
      Serial.print("0x");
      if (direccionesEncontradas[indice] < 16) {
        Serial.print("0");
      }
      Serial.print(direccionesEncontradas[indice], HEX);
    }
  }
  Serial.println();
}


// ================= PARSEO DE COORDENADAS NMEA =================
// Convierte el formato ddmm.mmmm (grados+minutos) de una trama NMEA a grados decimales.
float convertirNMEAaGrados(String valor, char hemisferio) {
  float crudo = valor.toFloat();
  int grados = (int)(crudo / 100);
  float minutos = crudo - (grados * 100);
  float decimal = grados + (minutos / 60.0);

  if (hemisferio == 'S' || hemisferio == 'W') {
    decimal = -decimal;
  }

  return decimal;
}

// Soporta las tramas GGA y RMC, que son las que incluyen posición.
bool parsearCoordenadasNMEA(String trama, float &lat, float &lon) {
  String partes[15];
  int n = 0;
  int inicio = 0;

  for (int i = 0; i < (int)trama.length() && n < 15; i++) {
    if (trama.charAt(i) == ',') {
      partes[n++] = trama.substring(inicio, i);
      inicio = i + 1;
    }
  }
  if (n < 15) {
    partes[n++] = trama.substring(inicio);
  }

  String tipo = partes[0];
  String latStr, latHem, lonStr, lonHem;

  if (tipo.endsWith("GGA") && n >= 6) {
    latStr = partes[2]; latHem = partes[3];
    lonStr = partes[4]; lonHem = partes[5];
  } else if (tipo.endsWith("RMC") && n >= 7) {
    latStr = partes[3]; latHem = partes[4];
    lonStr = partes[5]; lonHem = partes[6];
  } else {
    return false;
  }

  if (latStr.length() == 0 || lonStr.length() == 0) {
    return false;
  }

  lat = convertirNMEAaGrados(latStr, latHem.charAt(0));
  lon = convertirNMEAaGrados(lonStr, lonHem.charAt(0));
  return true;
}

// ================= DETECCIÓN DE DISPOSITIVOS UART =================
bool escucharGPSHardware() {
#if defined(ARDUINO_AVR_NANO_EVERY) || defined(ARDUINO_AVR_MEGA2560) || defined(ARDUINO_AVR_MEGA1280) || defined(ARDUINO_AVR_LEONARDO) || defined(ARDUINO_AVR_MICRO)
  unsigned long inicio = millis();
  bool detectado = false;
  String trama = "";
  float lat = 0.0, lon = 0.0;

  while (millis() - inicio < 1800) {
    while (uart.available()) {
      char c = uart.read();
      if (c == '$') {
        detectado = true;
        trama = "$";
      } else if (trama.length() > 0) {
        trama += c;
        if (c == '\n') {
          trama.trim();
          parsearCoordenadasNMEA(trama, lat, lon);
          trama = "";
        }
      }
    }
    delay(5);
  }

  if (detectado) {
    informarGPS(0, 0, lat, lon, lat != 0.0 || lon != 0.0);
  }
  return detectado;
#else
  return false;
#endif
}

// Distingue entre un módulo LoRa RYLR998, un GPS o un dispositivo desconocido.
void detectarGPS() {
  bool detectado = escucharGPSHardware();

  if (!detectado) {
    for (byte indiceBaud = 0; indiceBaud < sizeof(UART_SCAN_BAUDS) / sizeof(UART_SCAN_BAUDS[0]); indiceBaud++) {
      String respuesta = consultarLora("AT", UART_SCAN_BAUDS[indiceBaud]);
      bool esHC12 = respuesta.indexOf("OK+") >= 0 || respuesta.indexOf("HC-12") >= 0;
      if (esHC12) {
        Serial.print("UART_DEV:HC12;RX=HW;TX=HW;BAUD=");
        Serial.println(UART_SCAN_BAUDS[indiceBaud]);
        Serial.print("UART_INFO:");
        Serial.println(respuesta);
        detectado = true;
        break;
      }

      String respuestaLora = consultarLora("AT+ADDRESS?", UART_SCAN_BAUDS[indiceBaud]);
      if (respuestaLora.indexOf("+ADDRESS=") >= 0) {
        Serial.print("UART_DEV:LORA_RYLR998;RX=HW;TX=HW;BAUD=");
        Serial.println(UART_SCAN_BAUDS[indiceBaud]);
        Serial.print("LORA_INFO:");
        Serial.println(respuestaLora);
        detectado = true;
        break;
      }

      if (esRespuestaTransceptor(respuesta)) {
        Serial.print("UART_DEV:TRANSCEIVER;RX=HW;TX=HW;BAUD=");
        Serial.println(UART_SCAN_BAUDS[indiceBaud]);
        Serial.print("UART_INFO:");
        Serial.println(respuesta);
        detectado = true;
        break;
      }
    }
  }

  bool encontradoSoftware = escanearPuertosSerial(!detectado);
  if (encontradoSoftware) {
    detectado = true;
  }

  if (escanearPinesSET()) {
    detectado = true;
  }

  if (!detectado) {
    Serial.print("UART_DEV:UNKNOWN;RX=");
    Serial.print("-");
    Serial.print(";TX=");
    Serial.print("-");
    Serial.println();
  }
}