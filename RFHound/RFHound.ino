// RF Hound v2: passive SX1262 receiver, Heltec ESP32-S3 V3, high-band RF path.
// Serial protocol and manual LoRa profile: see PROTOCOLO.txt.
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <RadioLib.h>
#include <math.h>
#include "logo_placa.h"

Adafruit_SSD1306 oled(128, 64, &Wire, 21);
SX1262 radio = new Module(8, 14, 12, 13);
enum Mode { IDLE, SCAN, HOLD, LORA };
Mode mode = IDLE;
bool radioOk = false, oledOk = false;
volatile bool packetReady = false;
float frequency = 915, scanStart = 902, scanEnd = 928, scanStep = 0.5;
float peakRSSI = -200, peakFrequency = 902;
unsigned long nextSample = 0, heartbeat = 0;
char command[192];
size_t commandSize = 0;
bool overflow = false;

void IRAM_ATTR received() { packetReady = true; }

const char* modeName() {
  switch (mode) {
    case SCAN: return "SCAN";
    case HOLD: return "HOLD";
    case LORA: return "LORA";
    default: return "IDLE";
  }
}

void displayStatus(const char* text) {
  if (!oledOk) return;
  oled.clearDisplay();
  oled.setTextColor(SSD1306_WHITE);
  oled.setTextSize(1);
  oled.setCursor(0, 0);
  oled.println("RF Hound RX");
  oled.println(text);
  oled.printf("%.3f MHz\n", frequency);
  oled.display();
}

void identity() {
  if (radioOk) Serial.println("HELLO,RFHOUND,2,SX1262,868,928");
  else Serial.println("ERR,RADIO,initialization_failed");
}

bool check(int16_t result, const char* operation) {
  if (result == RADIOLIB_ERR_NONE) return true;
  mode = IDLE;
  radio.standby();
  Serial.printf("ERR,%s,%d\n", operation, result);
  displayStatus("Error - ver USB");
  return false;
}

bool validFrequency(float f) {
  return isfinite(f) && f >= 868 && f <= 928;
}

bool powerMode() {
  packetReady = false;
  return check(radio.beginFSK(frequency, 4.8, 5.0, 117.3, 10, 16), "FSK");
}

void execute(char* line) {
  if (strcmp(line, "ID") == 0) { identity(); return; }
  if (strcmp(line, "STOP") == 0) {
    if (!check(radio.standby(), "STOP")) return;
    mode = IDLE;
    packetReady = false;
    Serial.println("ACK,IDLE");
    displayStatus("Detenido");
    return;
  }
  if (!radioOk) { Serial.println("ERR,RADIO,not_ready"); return; }
  float a, b, c;
  unsigned int sf, cr, sync, preamble, crc, iq;
  int used = 0;
  if (sscanf(line, "SCAN,%f,%f,%f%n", &a, &b, &c, &used) == 3 &&
      line[used] == '\0' && validFrequency(a) && validFrequency(b) &&
      a < b && isfinite(c) && c >= 0.05 && c <= 5 && (b - a) / c <= 1200) {
    mode = IDLE;
    frequency = scanStart = a; scanEnd = b; scanStep = c;
    if (!powerMode()) return;
    peakRSSI = -200; peakFrequency = a;
    mode = SCAN; nextSample = millis();
    Serial.println("ACK,SCAN");
    displayStatus("Barrido RSSI");
    return;
  }
  used = 0;
  if (sscanf(line, "HOLD,%f%n", &a, &used) == 1 && line[used] == '\0' && validFrequency(a)) {
    mode = IDLE; frequency = a;
    if (!powerMode() || !check(radio.startReceive(), "HOLD")) return;
    mode = HOLD; nextSample = millis();
    Serial.println("ACK,HOLD");
    displayStatus("Frecuencia fija");
    return;
  }
  used = 0;
  if (sscanf(line, "LORA,%f,%f,%u,%u,%u,%u,%u,%u%n",
             &a, &b, &sf, &cr, &sync, &preamble, &crc, &iq, &used) == 8 &&
      line[used] == '\0' && validFrequency(a) &&
      (b == 125 || b == 250 || b == 500) && sf >= 7 && sf <= 12 &&
      cr >= 5 && cr <= 8 && sync <= 255 && preamble >= 6 && preamble <= 65535 &&
      crc <= 1 && iq <= 1) {
    mode = IDLE; frequency = a; packetReady = false;
    if (!check(radio.begin(a, b, sf, cr, sync, 10, preamble, 1.8), "LORA") ||
        !check(radio.explicitHeader(), "HEADER") ||
        !check(radio.setCRC(crc ? 2 : 0), "CRC") ||
        !check(radio.invertIQ(iq), "IQ")) return;
    radio.setPacketReceivedAction(received);
    if (!check(radio.startReceive(), "RX")) return;
    mode = LORA;
    Serial.println("ACK,LORA");
    displayStatus("Captura LoRa");
    return;
  }
  Serial.println("ERR,COMMAND,invalid_parameters");
}

void commands() {
  while (Serial.available()) {
    char ch = Serial.read();
    if (ch == '\r') continue;
    if (ch == '\n') {
      command[commandSize] = '\0';
      if (overflow) Serial.println("ERR,COMMAND,too_long");
      else execute(command);
      commandSize = 0; overflow = false;
    } else if (commandSize < sizeof(command) - 1) {
      command[commandSize++] = ch;
    } else overflow = true;
  }
}

void capture() {
  if (!packetReady) return;
  packetReady = false;
  uint8_t data[255];
  size_t length = radio.getPacketLength();
  if (length > sizeof(data)) {
    Serial.println("ERR,PACKET,too_long");
  } else {
    int16_t result = radio.readData(data, length);
    if (result == RADIOLIB_ERR_NONE) {
      Serial.printf("PKT,%.3f,%.1f,%.1f,%u,", frequency, radio.getRSSI(), radio.getSNR(), (unsigned)length);
      for (size_t i = 0; i < length; ++i) Serial.printf("%02X", data[i]);
      Serial.println();
      displayStatus("Paquete recibido");
    } else {
      // CRC failures are diagnostics, never successful packets.
      Serial.printf("ERR,PACKET,%d\n", result);
    }
  }
  check(radio.startReceive(), "RX");
}

void setup() {
  Serial.begin(115200);
  pinMode(36, OUTPUT); digitalWrite(36, LOW); delay(50);
  Wire.begin(17, 18);
  oledOk = oled.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  if (oledOk) {
    oled.clearDisplay();
    oled.drawBitmap(0, 0, LOGO_PLACA, 128, 64, SSD1306_WHITE);
    oled.display();
  } else Serial.println("ERR,OLED,initialization_failed");
  SPI.begin(9, 11, 10, 8);
  radioOk = check(radio.beginFSK(frequency, 4.8, 5.0, 117.3, 10, 16), "INIT");
  delay(3000);
  identity();
  if (radioOk) {
    check(radio.standby(), "IDLE");
    displayStatus("Listo - USB");
  }
}

void loop() {
  commands();
  unsigned long now = millis();
  if (mode == LORA) capture();
  if ((mode == SCAN || mode == HOLD) && (long)(now - nextSample) >= 0) {
    if (mode == SCAN) {
      if (!check(radio.setFrequency(frequency), "FREQUENCY") ||
          !check(radio.startReceive(), "SCAN")) return;
      delay(3);
    }
    float rssi = radio.getRSSI(false);
    Serial.printf("RF,%.3f,%.1f\n", frequency, rssi);
    if (mode == SCAN) {
      if (!check(radio.standby(), "SCAN")) return;
      if (rssi > peakRSSI) { peakRSSI = rssi; peakFrequency = frequency; }
      frequency += scanStep;
      if (frequency > scanEnd + 0.001) {
        Serial.printf("PEAK,%.3f,%.1f\n", peakFrequency, peakRSSI);
        frequency = scanStart; peakRSSI = -200;
      }
    }
    nextSample = millis() + (mode == HOLD ? 50 : 10);
  }
  if (now - heartbeat >= 1000) {
    Serial.printf("ALIVE,%s\n", modeName());
    heartbeat = now;
  }
  delay(1);
}
