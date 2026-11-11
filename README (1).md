# ESP32 firmware build guide

Two separate Arduino sketches are supplied:

1. `motor_controller/motor_controller.ino` — motor-driver PWM, direction, physical E-stop input and command watchdog.
2. `sensor_controller/sensor_controller.ino` — four VL53L0X-compatible distance sensors and one servo.

## Arduino IDE libraries

- ESP32 board support package (select the exact board variant you own).
- ArduinoJson 7.x.
- For sensor board: Adafruit_VL53L0X and ESP32Servo.

Set serial baud rate to 115200. Both boards send newline-terminated JSON messages and receive newline-terminated JSON commands.

## Firmware protocol examples

Motor command:

```json
{"action":"move_forward","speed":0.08,"duration_s":0.5}
```

Motor stop:

```json
{"action":"stop","speed":0,"duration_s":0.1}
```

Servo command:

```json
{"action":"servo","angle":90}
```

Sensor telemetry:

```json
{"sensors":{"front":0.52,"left":0.71,"right":0.68,"rear":1.10},"servo_angle":90,"board":"sensor"}
```

These are examples of the software protocol. The exact model of the VL53 sensor in the component sheet is not identified. The sketch currently targets VL53L0X-compatible modules only. Use the correct Adafruit sensor library for a different VL53 model.

## Critical pin warning

Every GPIO number in the sketches is a placeholder. Check your exact ESP32 board and create a wiring diagram before connecting the BTS7960 boards, servo or E-stop. Never power motors or servo from the ESP32 3.3 V pin. Use correctly rated regulated supplies and common signal ground. Add a physical normally-closed emergency-stop circuit that disables the motor driver hardware.
