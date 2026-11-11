# Hardware mapping and safety constraints

## Mapping from supplied component list

| Component | Qty in spreadsheet | Software use |
|---|---:|---|
| VL53 sensor | 4 total | front/left/right/rear distance readings (exact model still to verify) |
| Johnson motor | 4 | left pair / right pair drive arrangement (only if electrical ratings allow) |
| BTS7960 | 2 | left and right motor-driver channels (not four independent channels) |
| ESP32 | 2 | motor controller and sensor/servo controller |
| Servo | 1 | sensor/mechanism positioning |
| Buck converter | 2 | regulated compute/logic rails after load/voltage calculation |
| Lithium battery item | 2 | pack/battery supply; chemistry, series/parallel and BMS are unknown |
| M100050 | 1 | exact part not identified; not used by the software |
| X160 connector | 4 | wiring connectors; current rating/pinout unknown |
| Misc accessories | 1 set | mechanical/electrical accessories |

## Safety architecture

- ROS safety supervisor validates state, speed, direction sensor freshness, obstacle distance and motor-controller heartbeat.
- ESP32 motor firmware independently disables outputs at boot/reset, after watchdog timeout, and when the E-stop loop opens.
- Flutter app can request actions but cannot bypass the safety supervisor.
- LLM does not publish motor PWM or issue shell commands.
- OFF/STANDBY send STOP before changing state.
- E-stop is latched: releasing the switch alone does not reactivate movement; reset is explicit and only accepted when the ESP32 reports a healthy circuit.

## Unresolved electrical details

Do not treat the placeholder pin assignments as a wiring plan. Need exact ESP32 board models, BTS7960 module pin labels, motor rated/stall current and polarity, battery voltage/BMS, buck converter ratings, exact VL53 breakout boards, servo supply and E-stop switch wiring.

A software stop is not an emergency stop. The physical E-stop must remove motor driver enable/power independently of Raspberry Pi, ROS, Wi-Fi, Flutter and LLM.

## Navigation limits

This build provides manual directional control, live camera and distance-based stop gating. No LiDAR, wheel encoders or IMU appears in the supplied list, so mapping, localization, odometry and fully autonomous Nav2 navigation are not included or claimed.
