#include <Wire.h>
#include <SPI.h>

// ================= CONFIGURACIÓN DE LA PLACA =================
#if defined(ARDUINO_MEGAAVR_NANO_EVERY)
  #define uart Serial1
  #define BOARD_NAME "NANO_EVERY"
#elif defined(ARDUINO_AVR_MEGA2560)
  #define uart Serial1
  #define BOARD_NAME "MEGA2560"
#elif defined(ARDUINO_AVR_MEGA1280)
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

// ================= CONFIGURACIÓN DE MÓDULOS SPI =================
// La salida SPI es adicional y conserva el protocolo serial existente.
// Los dos primeros pines conservan la configuración original. El escaneo
// automático prueba también otros GPIO que pueden usarse como CS.
#define AUTO_SCAN_SPI_CS 0

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
  // No usar Serial USB ni las líneas físicas del bus SPI como CS.
  if (pin == 0 || pin == 1 || pin == MOSI || pin == MISO || pin == SCK) {
    return true;
  }

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

  Serial.print("SPI:");
  Serial.println(modulosFlashSPI[modulo].nombre);
  return true;
}

bool probarModuloSPI(byte csPin, int modulo) {
  byte id = leerRegistroSPI(csPin, modulosSPI[modulo].regID);

  if (id != modulosSPI[modulo].valorEsperado) {
    return false;
  }

  Serial.print("SPI:");
  Serial.println(modulosSPI[modulo].nombre);
  return true;
}

void detectarSPI() {
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

  // Primero se prueban los pines declarados explícitamente.
  for (int modulo = 0; modulo < NUM_MODULOS_SPI; modulo++) {
    byte csPin = modulosSPI[modulo].csPin;

    if (!encontrados[modulo] && probarModuloSPI(csPin, modulo)) {
      encontrados[modulo] = true;
    }
  }

  for (int modulo = 0; modulo < NUM_MODULOS_FLASH_SPI; modulo++) {
    if (!encontradosFlash[modulo] && probarFlashSPI(modulo)) {
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
      if (!encontrados[modulo] && probarModuloSPI(csPin, modulo)) {
        encontrados[modulo] = true;
      }
    }
  }
#endif

  bool encontrado = false;
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
String consultarLora(const char *comando) {
  uart.println(comando);

  unsigned long inicio = millis();
  String respuesta;

  while (millis() - inicio < 500) {
    while (uart.available()) {
      char caracter = uart.read();

      if (caracter != '\r' && caracter != '\n') {
        respuesta += caracter;
      }
    }
  }

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
  String respuesta = "";

  while (millis() - inicio < timeout) {
    while (puerto.available()) {
      char c = puerto.read();
      if (c == '\r' || c == '\n') {
        if (respuesta.length() > 0) {
          respuesta += ' ';
        }
        continue;
      }
      respuesta += c;
    }
    delay(10);
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
    texto.indexOf("AT") >= 0 ||
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

bool probarPuertoSerial(byte rxPin, byte txPin, bool escucharGPSPrimero = false) {
  if (rxPin == txPin || !esPinSerialPermitido(rxPin) || !esPinSerialPermitido(txPin)) {
    return false;
  }

  SoftwareSerial prueba(rxPin, txPin);
  prueba.begin(escucharGPSPrimero ? GPS_BAUD : UART_BAUD);
  delay(200);

  if (escucharGPSPrimero) {
    float lat = 0.0, lon = 0.0;
    bool gpsDetectado = leerGPSSoftware(prueba, 1800, lat, lon);
    if (gpsDetectado) {
      informarGPS(rxPin, txPin, lat, lon, lat != 0.0 || lon != 0.0);
      prueba.end();
      return true;
    }
    prueba.end();
    prueba.begin(UART_BAUD);
    delay(50);
  }

  prueba.println("AT");
  String respuesta = leerRespuestaSoftware(prueba, 500);
  if (esRespuestaTransceptor(respuesta)) {
    Serial.print("UART_DEV:TRANSCEIVER;RX=");
    Serial.print(rxPin);
    Serial.print(";TX=");
    Serial.print(txPin);
    Serial.print(";TYPE=");
    Serial.print(respuesta.length() > 0 ? "AT_RESP" : "SERIAL");
    Serial.println();
    if (respuesta.length() > 0) {
      Serial.print("UART_INFO:");
      Serial.println(respuesta);
    }
    prueba.end();
    return true;
  }

  prueba.println("AT+ADDRESS?");
  String respuestaLora = leerRespuestaSoftware(prueba, 500);
  if (respuestaLora.indexOf("+ADDRESS=") >= 0) {
    Serial.print("UART_DEV:LORA_RYLR998;RX=");
    Serial.print(rxPin);
    Serial.print(";TX=");
    Serial.print(txPin);
    Serial.println();
    Serial.print("LORA_INFO:");
    Serial.println(respuestaLora);
    prueba.end();
    return true;
  }

  prueba.end();
  prueba.begin(GPS_BAUD);
  delay(50);
  float lat = 0.0, lon = 0.0;
  bool gpsDetectado = leerGPSSoftware(prueba, 1500, lat, lon);

  if (gpsDetectado) {
    informarGPS(rxPin, txPin, lat, lon, lat != 0.0 || lon != 0.0);
    prueba.end();
    return true;
  }

  prueba.end();
  return false;
}

bool escanearPuertosSerial() {
  if (probarPuertoSerial(4, 5, true) || probarPuertoSerial(5, 4, true) ||
      probarPuertoSerial(2, 3, true) || probarPuertoSerial(3, 2, true)) {
    return true;
  }

  for (byte rx = SERIAL_SCAN_MIN_PIN; rx <= SERIAL_SCAN_MAX_PIN; rx++) {
    for (byte tx = rx + 1; tx <= SERIAL_SCAN_MAX_PIN; tx++) {
      if ((rx == 2 && tx == 3) || (rx == 3 && tx == 2)) {
        continue;
      }
      if (probarPuertoSerial(rx, tx)) {
        return true;
      }
    }
  }

  return false;
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

  // -------- SUBPROCESO 1: IDENTIFICACIÓN DE LA PLACA --------
  // Es una salida inmediata y no requiere comunicación con dispositivos.
  Serial.print("BOARD:");
  Serial.println(BOARD_NAME);

  // -------- SUBPROCESO 2: DETECCIÓN DE DISPOSITIVOS I2C --------
  detectarI2C();

  // -------- SUBPROCESO 3: DETECCIÓN UART Y GPS --------
  // La detección GPS forma parte de esta fase y no depende de obtener fix.
  detectarGPS();

  // -------- SUBPROCESO 4: DETECCIÓN DE DISPOSITIVOS SPI --------
  detectarSPI();

  // Indica al programa Python que terminó el ciclo de detección.
  Serial.println("STATUS:READY");

  delay(3000);
}


// ================= DETECCIÓN DE DISPOSITIVOS I2C =================
// Recorre las direcciones I2C y reporta las que responden correctamente.
void detectarI2C() {

  byte error, address;
  int found = 0;

  Serial.print("I2C:");

  for (address = 1; address < 127; address++) {

    Wire.beginTransmission(address);
    error = Wire.endTransmission();

    if (error == 0) {
      if (found > 0) {
        Serial.print(",");
      }
      Serial.print("0x");
      if (address < 16) Serial.print("0");
      Serial.print(address, HEX);
      found++;
    }

    // Pausa breve para dar estabilidad al bus I2C entre consultas.
    delay(5);
  }

  if (found == 0) {
    Serial.print("NONE");
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
#if defined(ARDUINO_MEGAAVR_NANO_EVERY) || defined(ARDUINO_AVR_MEGA2560) || defined(ARDUINO_AVR_MEGA1280) || defined(ARDUINO_AVR_LEONARDO) || defined(ARDUINO_AVR_MICRO)
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

  if (!detectado && (uart.available() || uart.peek() >= 0)) {
    String respuestaLora = consultarLora("AT+ADDRESS?");
    if (respuestaLora.indexOf("+ADDRESS=") >= 0) {
      Serial.print("UART_DEV:LORA_RYLR998;RX=");
      Serial.print("HW");
      Serial.print(";TX=");
      Serial.print("HW");
      Serial.println();
      Serial.print("LORA_INFO:");
      Serial.println(respuestaLora);
      detectado = true;
    }
  }

  if (!detectado) {
    detectado = escanearPuertosSerial();
  }

  if (!detectado) {
    Serial.print("UART_DEV:UNKNOWN;RX=");
    Serial.print("-");
    Serial.print(";TX=");
    Serial.print("-");
    Serial.println();
  }
}