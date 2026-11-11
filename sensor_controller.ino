/*
 * ESP32 SENSOR CONTROLLER — VL53L0X + one servo example.
 * Requires ArduinoJson 7, Adafruit_VL53L0X and ESP32Servo libraries.
 * Assumes VL53L0X-compatible breakouts and XSHUT pins. Confirm exact sensor model first.
 * If your sensor is VL53L1X or another model, use its matching library/API instead.
 */
#include <Arduino.h>
#include <Wire.h>
#include <ArduinoJson.h>
#include <Adafruit_VL53L0X.h>
#include <ESP32Servo.h>

static const uint32_t BAUD = 115200;
static const int SDA_PIN = 21, SCL_PIN = 22;
static const int XSHUT[4] = {13, 14, 25, 26}; // PLACEHOLDERS: verify GPIOs and board
static const uint8_t ADDR[4] = {0x30, 0x31, 0x32, 0x33};
static const char *LABEL[4] = {"front", "left", "right", "rear"};
static const int SERVO_PIN = 27; // PLACEHOLDER: verify GPIO and power supply
static const int SERVO_MIN = 20, SERVO_MAX = 160;

Adafruit_VL53L0X s0, s1, s2, s3;
Adafruit_VL53L0X *sensors[4] = {&s0, &s1, &s2, &s3};
bool sensorReady[4] = {false, false, false, false};
Servo mechanismServo;
uint32_t lastReport = 0;

void initSensors() {
  for (int i = 0; i < 4; i++) { pinMode(XSHUT[i], OUTPUT); digitalWrite(XSHUT[i], LOW); }
  delay(20);
  for (int i = 0; i < 4; i++) {
    digitalWrite(XSHUT[i], HIGH); delay(15);
    sensorReady[i] = sensors[i]->begin(0x29, false, &Wire);
    if (sensorReady[i]) {
      sensors[i]->setAddress(ADDR[i]);
      delay(10);
    }
  }
}

float readMeters(int index) {
  if (!sensorReady[index]) return -1.0f;
  VL53L0X_RangingMeasurementData_t measure;
  sensors[index]->rangingTest(&measure, false);
  if (measure.RangeStatus == 4 || measure.RangeMilliMeter == 0) return -1.0f;
  return measure.RangeMilliMeter / 1000.0f;
}

void handleCommand(const String &line) {
  JsonDocument doc;
  if (deserializeJson(doc, line)) return;
  const char *action = doc["action"] | "";
  if (strcmp(action, "servo") == 0) {
    int angle = doc["angle"] | 90;
    mechanismServo.write(constrain(angle, SERVO_MIN, SERVO_MAX));
  }
}

void setup() {
  Serial.begin(BAUD);
  Wire.begin(SDA_PIN, SCL_PIN);
  initSensors();
  mechanismServo.setPeriodHertz(50);
  mechanismServo.attach(SERVO_PIN, 500, 2400);
  mechanismServo.write(90);
  Serial.println("{\"board\":\"sensor\",\"status\":\"ready\"}");
}

void loop() {
  static String line;
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n') { handleCommand(line); line = ""; }
    else if (c != '\r' && line.length() < 256) line += c;
    else if (line.length() >= 256) line = "";
  }
  if (millis() - lastReport >= 100) {
    lastReport = millis();
    JsonDocument doc;
    JsonObject sensorsJson = doc["sensors"].to<JsonObject>();
    for (int i = 0; i < 4; i++) {
      float value = readMeters(i);
      if (value >= 0) sensorsJson[LABEL[i]] = value;
      else sensorsJson[LABEL[i]] = nullptr;
    }
    doc["board"] = "sensor";
    doc["servo_angle"] = mechanismServo.read();
    serializeJson(doc, Serial);
    Serial.println();
  }
  delay(2);
}
