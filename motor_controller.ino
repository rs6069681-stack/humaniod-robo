/*
 * ESP32 MOTOR CONTROLLER — safety-oriented starter firmware.
 * Target: ESP32 Arduino core 3.x, ArduinoJson 7.x.
 * Wiring is NOT verified for your exact ESP32 board. Check GPIOs before connection.
 * Two BTS7960 boards are treated as left-side and right-side drive channels.
 * Do not parallel two motors on one channel unless stall-current ratings permit it.
 */
#include <Arduino.h>
#include <ArduinoJson.h>

// GPIO ASSIGNMENTS ARE PLACEHOLDERS. Confirm pin availability on your ESP32 variant.
static const int L_RPWM = 25, L_LPWM = 26, L_REN = 27, L_LEN = 14;
static const int R_RPWM = 32, R_LPWM = 33, R_REN = 18, R_LEN = 19;
// NC emergency-stop loop to GND while healthy. Open circuit / pressed => HIGH => stop.
static const int ESTOP_PIN = 23;
static const uint32_t BAUD = 115200;
static const uint32_t WATCHDOG_MS = 450;
static const int PWM_HZ = 18000;
static const int PWM_BITS = 10;
static const int PWM_MAX = (1 << PWM_BITS) - 1;

uint32_t lastValidCommandMs = 0;
uint32_t motionDeadlineMs = 0;
bool motionActive = false;

void setChannel(int rpwm, int lpwm, float value) {
  value = constrain(value, -1.0f, 1.0f);
  int duty = (int)(fabs(value) * PWM_MAX);
  if (value > 0) { ledcWrite(rpwm, duty); ledcWrite(lpwm, 0); }
  else if (value < 0) { ledcWrite(rpwm, 0); ledcWrite(lpwm, duty); }
  else { ledcWrite(rpwm, 0); ledcWrite(lpwm, 0); }
}

void stopMotors() {
  setChannel(L_RPWM, L_LPWM, 0);
  setChannel(R_RPWM, R_LPWM, 0);
  digitalWrite(L_REN, LOW); digitalWrite(L_LEN, LOW);
  digitalWrite(R_REN, LOW); digitalWrite(R_LEN, LOW);
  motionActive = false;
}

bool estopHealthy() { return digitalRead(ESTOP_PIN) == LOW; }

void drive(float left, float right, uint32_t durationMs) {
  if (!estopHealthy()) { stopMotors(); return; }
  left = constrain(left, -1.0f, 1.0f);
  right = constrain(right, -1.0f, 1.0f);
  digitalWrite(L_REN, HIGH); digitalWrite(L_LEN, HIGH);
  digitalWrite(R_REN, HIGH); digitalWrite(R_LEN, HIGH);
  setChannel(L_RPWM, L_LPWM, left);
  setChannel(R_RPWM, R_LPWM, right);
  motionActive = (fabs(left) > 0.001f || fabs(right) > 0.001f);
  motionDeadlineMs = millis() + constrain(durationMs, 100UL, 2000UL);
}

void processLine(const String &line) {
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, line);
  if (err) { Serial.println("{\"event\":\"bad_json\"}"); return; }
  const char *action = doc["action"] | "";
  float speed = doc["speed"] | 0.0f;
  float duration = doc["duration_s"] | 0.5f;
  if (!estopHealthy()) {
    stopMotors();
    Serial.println("{\"event\":\"estop_active\",\"motors_enabled\":false}");
    return;
  }
  lastValidCommandMs = millis();
  if (strcmp(action, "stop") == 0) { stopMotors(); return; }
  if (speed < 0.0f || speed > 0.15f || duration < 0.1f || duration > 2.0f) {
    stopMotors(); Serial.println("{\"event\":\"command_out_of_range\"}"); return;
  }
  float v = speed / 0.15f; // map physical m/s cap to normalized PWM request
  if (strcmp(action, "move_forward") == 0) drive(v, v, (uint32_t)(duration * 1000));
  else if (strcmp(action, "move_backward") == 0) drive(-v, -v, (uint32_t)(duration * 1000));
  else if (strcmp(action, "turn_left") == 0) drive(-v, v, (uint32_t)(duration * 1000));
  else if (strcmp(action, "turn_right") == 0) drive(v, -v, (uint32_t)(duration * 1000));
  else { stopMotors(); Serial.println("{\"event\":\"unknown_action\"}"); }
}

void setup() {
  Serial.begin(BAUD);
  pinMode(L_REN, OUTPUT); pinMode(L_LEN, OUTPUT);
  pinMode(R_REN, OUTPUT); pinMode(R_LEN, OUTPUT);
  pinMode(ESTOP_PIN, INPUT_PULLUP);
  // Configure PWM outputs before enabling the driver channels.
  ledcAttach(L_RPWM, PWM_HZ, PWM_BITS); ledcAttach(L_LPWM, PWM_HZ, PWM_BITS);
  ledcAttach(R_RPWM, PWM_HZ, PWM_BITS); ledcAttach(R_LPWM, PWM_HZ, PWM_BITS);
  stopMotors();
  lastValidCommandMs = millis();
  Serial.println("{\"board\":\"motor\",\"status\":\"ready\",\"motors_enabled\":false}");
}

void loop() {
  static String line;
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n') { processLine(line); line = ""; }
    else if (c != '\r' && line.length() < 512) line += c;
    else if (line.length() >= 512) { line = ""; stopMotors(); }
  }
  if (!estopHealthy()) {
    stopMotors();
  }
  if (motionActive && (int32_t)(millis() - motionDeadlineMs) >= 0) stopMotors();
  if (motionActive && millis() - lastValidCommandMs > WATCHDOG_MS) stopMotors();
  static uint32_t lastStatus = 0;
  if (millis() - lastStatus > 1000) {
    lastStatus = millis();
    Serial.printf("{\"board\":\"motor\",\"state\":\"%s\",\"estop_healthy\":%s,\"motors_enabled\":%s}\n",
                  motionActive ? "ACTIVE" : "IDLE", estopHealthy() ? "true" : "false", motionActive ? "true" : "false");
  }
  delay(2);
}
