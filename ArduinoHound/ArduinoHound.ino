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
  return false;
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
  bool encontrados[NUM_MODULOS_SPI] = {false};

  // Primero se prueban los pines declarados explícitamente.
  for (int modulo = 0; modulo < NUM_MODULOS_SPI; modulo++) {
    byte csPin = modulosSPI[modulo].csPin;

    if (!encontrados[modulo] && probarModuloSPI(csPin, modulo)) {
      encontrados[modulo] = true;
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

  // -------- SUBPROCESO 2: DETECCIÓN DEL DISPOSITIVO UART --------
  // Se ejecuta antes del escaneo I2C porque permite identificar rápidamente
  // un módulo LoRa o un GPS conectado a la UART.
  detectarGPS();

  // -------- SUBPROCESO 3: DETECCIÓN DE DISPOSITIVOS I2C --------
  // Se ejecuta al final porque revisa todas las direcciones I2C disponibles.
  detectarI2C();

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
      Serial.print("0x");
      if (address < 16) Serial.print("0");
      Serial.print(address, HEX);
      Serial.print(",");
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


// ================= DETECCIÓN DE DISPOSITIVOS UART =================
// Distingue entre un módulo LoRa RYLR998, un GPS o un dispositivo desconocido.
void detectarGPS() {

  // Encabezado de la respuesta que interpreta el programa Python.
  Serial.print("UART_DEV:");

  // -------- SUBPROCESO UART 1: DETECCIÓN DE LORA --------
  // El RYLR998 responde con +ADDRESS= ante esta consulta.
  String respuestaLora = consultarLora("AT+ADDRESS?");

  if (respuestaLora.indexOf("+ADDRESS=") >= 0) {
    Serial.println("LORA_RYLR998");

    // -------- SUBPROCESO UART 2: LECTURA DE CONFIGURACIÓN LORA --------
    // Obtiene los parámetros principales del módulo identificado.
    Serial.print("LORA_INFO:");
    Serial.print("ADDRESS=");
    Serial.print(respuestaLora);
    Serial.print(";NETWORKID=");
    Serial.print(consultarLora("AT+NETWORKID?"));
    Serial.print(";BAND=");
    Serial.print(consultarLora("AT+BAND?"));
    Serial.print(";PARAMETER=");
    Serial.println(consultarLora("AT+PARAMETER?"));
    return;
  }

  // -------- SUBPROCESO UART 3: DETECCIÓN DE GPS --------
  // Los mensajes NMEA de un GPS comienzan normalmente con '$'.
  unsigned long t = millis();
  bool gps = false;

  while (millis() - t < 2000) {

    if (uart.available()) {
      char c = uart.read();

      if (c == '$') {
        gps = true;
        break;
      }
    }
  }

  if (gps) {
    // Se encontró una trama compatible con la salida NMEA de un GPS.
    Serial.println("GPS");
  } else {
    // No se encontró respuesta LoRa ni una trama GPS en el tiempo establecido.
    Serial.println("UNKNOWN");
  }
}