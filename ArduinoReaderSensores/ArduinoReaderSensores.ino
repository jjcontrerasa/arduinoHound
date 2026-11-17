#include <Wire.h>

// Mismo cableado en ambas placas: GPS TX -> D0; HC-12 TX -> D8.
// D1 y D9 quedan sin conectar.
#if defined(ARDUINO_ARCH_MEGAAVR) && defined(__AVR_ATmega4809__)
#include <SoftwareSerial.h>
#define PLACA_TEXTO "Nano Every"
SoftwareSerial hc12(8, 9);
HardwareSerial &gps = Serial1;
#elif defined(ARDUINO_ARCH_ESP32) && defined(ARDUINO_NANO_ESP32)
#define PLACA_TEXTO "Nano ESP32"
HardwareSerial &gps = Serial1;
HardwareSerial &hc12 = Serial2;
#else
#error "ArduinoReaderSensores solo admite Arduino Nano Every y Arduino Nano ESP32."
#endif
const unsigned long MONITOR_BAUD = 115200;
const unsigned long GPS_BAUD = 9600;
const unsigned long HC12_BAUD = 9600;
uint8_t adxlAddress = 0;
unsigned long ultimaMedicion = 0;
unsigned long ultimoEstado = 0;
unsigned long ultimoIntentoADXL = 0;
unsigned long bytesGPS = 0;
unsigned long bytesHC12 = 0;
char nmea[128];
size_t nmeaLength = 0;
bool nmeaDesbordado = false;

#if defined(ARDUINO_ARCH_MEGAAVR)
// Wire de megaavr 1.8.8 no ofrece timeout. Limitar cada operacion del TWI0
// evita detener el monitor si el bus esta atascado o no tiene pull-ups.
void terminarI2C() {
  TWI0.MCTRLB = TWI_ACKACT_bm | TWI_MCMD_STOP_gc;
  TWI0.MSTATUS = TWI_BUSSTATE_IDLE_gc;
}

bool esperarI2C(uint8_t bandera) {
  unsigned long inicio = millis();
  while (!(TWI0.MSTATUS & bandera)) {
    if ((TWI0.MSTATUS & (TWI_BUSERR_bm | TWI_ARBLOST_bm)) ||
        millis() - inicio >= 25) {
      terminarI2C();
      return false;
    }
  }
  return true;
}

bool escribirByteI2C(uint8_t dato, bool direccion = false) {
  if (direccion) TWI0.MADDR = dato;
  else TWI0.MDATA = dato;
  if (!esperarI2C(TWI_WIF_bm)) return false;
  if (TWI0.MSTATUS & TWI_RXACK_bm) {
    terminarI2C();
    return false;
  }
  return true;
}

bool leerRegistros(uint8_t direccion, uint8_t registro, uint8_t *datos, uint8_t cantidad) {
  TWI0.MCTRLB = 0;
  if (!escribirByteI2C(direccion << 1, true) ||
      !escribirByteI2C(registro)) return false;
  TWI0.MADDR = (direccion << 1) | 1;
  for (uint8_t i = 0; i < cantidad; ++i) {
    if (!esperarI2C(TWI_RIF_bm)) return false;
    datos[i] = TWI0.MDATA;
    if (i + 1 == cantidad) terminarI2C();
    else TWI0.MCTRLB = TWI_MCMD_RECVTRANS_gc;
  }
  return true;
}

bool escribirRegistro(uint8_t direccion, uint8_t registro, uint8_t valor) {
  TWI0.MCTRLB = 0;
  if (!escribirByteI2C(direccion << 1, true) ||
      !escribirByteI2C(registro) ||
      !escribirByteI2C(valor)) return false;
  terminarI2C();
  return true;
}
#else
bool leerRegistros(uint8_t direccion, uint8_t registro, uint8_t *datos, uint8_t cantidad) {
  Wire.beginTransmission(direccion);
  Wire.write(registro);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(direccion, cantidad) != cantidad) return false;
  for (uint8_t i = 0; i < cantidad; ++i) {
    int dato = Wire.read();
    if (dato < 0) return false;
    datos[i] = static_cast<uint8_t>(dato);
  }
  return true;
}

bool escribirRegistro(uint8_t direccion, uint8_t registro, uint8_t valor) {
  Wire.beginTransmission(direccion);
  Wire.write(registro);
  Wire.write(valor);
  return Wire.endTransmission() == 0;
}
#endif

void buscarADXL() {
  const uint8_t direcciones[] = {0x53, 0x1D};
  for (uint8_t direccion : direcciones) {
    uint8_t identificador = 0;
    if (!leerRegistros(direccion, 0x00, &identificador, 1) || identificador != 0xE5) continue;
    // Resolucion completa, +/-2 g, 25 Hz y modo medida.
    if (!escribirRegistro(direccion, 0x31, 0x08) ||
        !escribirRegistro(direccion, 0x2C, 0x08) ||
        !escribirRegistro(direccion, 0x2D, 0x08)) {
      Serial.println(F("[ADXL345 ERROR] No se pudo configurar."));
      return;
    }
    adxlAddress = direccion;
    Serial.print(F("[ADXL345] Detectado en 0x"));
    Serial.println(adxlAddress, HEX);
    return;
  }
  Serial.println(F("[ADXL345] No detectado en I2C (0x53/0x1D). Revisar cableado."));
}

void medirADXL() {
  uint8_t datos[6];
  if (!leerRegistros(adxlAddress, 0x32, datos, 6)) {
    Serial.println(F("[ADXL345 ERROR] Fallo de lectura; se buscara de nuevo."));
    adxlAddress = 0;
    return;
  }
  int16_t ejes[3];
  for (uint8_t i = 0; i < 3; ++i) {
    uint8_t bajo = datos[i * 2];
    uint8_t alto = datos[i * 2 + 1];
    ejes[i] = static_cast<int16_t>((static_cast<uint16_t>(alto) << 8) | bajo);
  }
  Serial.print(F("[ADXL345] raw X="));
  Serial.print(ejes[0]);
  Serial.print(F(" Y="));
  Serial.print(ejes[1]);
  Serial.print(F(" Z="));
  Serial.print(ejes[2]);
  Serial.print(F(" | g X="));
  Serial.print(ejes[0] * 0.0039f, 3);
  Serial.print(F(" Y="));
  Serial.print(ejes[1] * 0.0039f, 3);
  Serial.print(F(" Z="));
  Serial.println(ejes[2] * 0.0039f, 3);
}

void recibirGPS() {
  for (uint8_t i = 0; i < 64 && gps.available(); ++i) {
    char dato = gps.read();
    ++bytesGPS;
    if (dato == '\n') {
      Serial.print(F("[GPS NMEA] "));
      Serial.write(reinterpret_cast<const uint8_t *>(nmea), nmeaLength);
      Serial.println();
      if (nmeaDesbordado) Serial.println(F("[GPS ERROR] Linea mayor de 127 bytes; truncada."));
      nmeaLength = 0;
      nmeaDesbordado = false;
    } else if (nmeaLength < sizeof(nmea) - 1) {
      nmea[nmeaLength++] = dato;
    } else {
      nmeaDesbordado = true;
    }
  }
}

void recibirHC12() {
#if defined(ARDUINO_ARCH_MEGAAVR)
  if (hc12.overflow()) Serial.println(F("[HC12 ERROR] Desbordamiento del buffer RX."));
#endif
  uint8_t datos[32];
  size_t cantidad = 0;
  while (hc12.available() && cantidad < sizeof(datos)) {
    datos[cantidad++] = hc12.read();
  }
  if (!cantidad) return;
  bytesHC12 += cantidad;
  Serial.print(F("[HC12 RX HEX] "));
  for (size_t i = 0; i < cantidad; ++i) {
    if (datos[i] < 16) Serial.print('0');
    Serial.print(datos[i], HEX);
    Serial.print(' ');
  }
  Serial.print(F(" | texto: "));
  Serial.write(datos, cantidad);
  Serial.println();
}

void setup() {
  Serial.begin(MONITOR_BAUD);
#if defined(ARDUINO_ARCH_ESP32)
  // Pines Arduino del Nano ESP32; el core los traduce a GPIO.
  gps.begin(GPS_BAUD, SERIAL_8N1, D0, D1);
  hc12.begin(HC12_BAUD, SERIAL_8N1, D8, D9);
  Wire.begin(SDA, SCL, 100000);
  Wire.setTimeOut(25);
#else
  gps.begin(GPS_BAUD);
  hc12.begin(HC12_BAUD);
  Wire.begin();
  Wire.setClock(100000);
  TWI0.MCTRLA &= ~TWI_RIEN_bm;
  TWI0.MCTRLA &= ~TWI_WIEN_bm;
#endif
  delay(300);
  Serial.println(F("\nArduino Reader - " PLACA_TEXTO " / ADXL345 / GPS / HC-12"));
  Serial.println(F("USB=115200; GPS=9600 RX D0; HC12=9600 RX D8; I2C=A4/A5."));
  Serial.println(F("Solo recepcion serial: no se envian comandos al GPS ni al HC-12."));
  Serial.println(F("GPS: NMEA sin interpretar; A/V en RMC indica fix valido/no valido."));
  buscarADXL();
}

void loop() {
  recibirHC12();
  recibirGPS();
  unsigned long ahora = millis();
  if (adxlAddress && ahora - ultimaMedicion >= 500) {
    ultimaMedicion = ahora;
    medirADXL();
  }
  if (!adxlAddress && ahora - ultimoIntentoADXL >= 5000) {
    ultimoIntentoADXL = ahora;
    buscarADXL();
  }
  if (ahora - ultimoEstado >= 5000) {
    ultimoEstado = ahora;
    Serial.print(F("[ESTADO] ms="));
    Serial.print(ahora);
    Serial.print(F(" | GPS bytes="));
    Serial.print(bytesGPS);
    Serial.print(F(" | HC12 bytes="));
    Serial.print(bytesHC12);
    Serial.print(F(" | ADXL345="));
    Serial.println(adxlAddress ? F("activo") : F("no detectado"));
    if (!bytesGPS) Serial.println(F("[GPS] Sin datos: revisar TX->D0 y baudios 9600."));
    if (!bytesHC12) Serial.println(F("[HC12] Sin recepcion: espera un emisor compatible; no confirma ausencia del modulo."));
  }
}
