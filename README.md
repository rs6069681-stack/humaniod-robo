# Robot ROS Software (Raspberry Pi)

This folder is the **robot-side software only**. The Flutter phone app is a separate sibling folder: `../flutter_mobile_app/`.

## Included ROS 2 nodes

| Node / executable | Function |
|---|---|
| `safety_supervisor` | Robot states, obstacle checks, stale sensor checks, E-stop latch, command gating |
| `serial_bridge` | Independent USB serial connections to motor ESP32 and sensor ESP32 |
| `simulation_node` | Mock sensor/controller messages; no physical motor output |
| `camera_vision_node` | OpenCV live camera capture, optional YOLO detection, annotated JPEG frames |
| `robot_api_node` | FastAPI + WebSocket server hosted as a ROS node; Flutter connects here |
| `robot_display_node` | Optional Pygame touchscreen face with state expressions and detection labels |

## Topics

| Topic | Type | Direction / use |
|---|---|---|
| `/robot/app_command` | `std_msgs/String` JSON | Phone API → safety supervisor |
| `/robot/status` | `std_msgs/String` JSON | Safety supervisor → API/display |
| `/robot/sensors` | `std_msgs/String` JSON | Sensor ESP32 bridge → safety supervisor |
| `/robot/motor_status` | `std_msgs/String` JSON | Motor ESP32 bridge → safety supervisor |
| `/robot/motor_command` | `std_msgs/String` JSON | Safety supervisor → motor ESP32 bridge |
| `/robot/sensor_command` | `std_msgs/String` JSON | Safety supervisor → sensor ESP32 bridge |
| `/robot/detections` | `std_msgs/String` JSON | Vision node → API/display |
| `/robot/camera/jpeg` | `sensor_msgs/CompressedImage` | Vision node → phone camera WebSocket |

The ESP32 serial protocol is newline-delimited JSON at 115200 baud. The motor ESP32 independently enforces a short command watchdog and physical E-stop input. Pi-side validation is an additional layer, not a replacement for hardware safety.

## API exposed for the separate Flutter app

- `GET /api/health`
- `GET /api/status`
- `POST /api/command`
- `POST /api/intent/preview`
- `POST /api/chat`
- `GET /api/vision/latest`
- `GET /api/camera/snapshot`
- `WS /ws/status`
- `WS /ws/camera` (binary JPEG frames)

Commands accepted by the API: `start`, `activate`, `stop`, `standby`, `wake`, `off`, `reset_estop`, `move_forward`, `move_backward`, `turn_left`, `turn_right`, `set_servo`.

The API confirms that a command is queued to ROS, not that physical motion has occurred. The app must observe the next `/api/status` state. The safety supervisor can reject a queued command.

## Quick simulation run

On Ubuntu 24.04 64-bit with ROS 2 Jazzy:

```bash
cd robot_ros_software
bash scripts/setup_ros_ubuntu24.sh
bash scripts/run_robot.sh
```

The provided `config/robot.env` defaults to `HARDWARE_MODE=false` and `SIMULATION_ENABLED=true`. This is the correct first test; no physical motor board is contacted. The camera node tries `/dev/video0`; camera availability is optional for simulation.

API health: `http://127.0.0.1:8000/api/health`

## Automatic start at boot

After the workspace is built:

```bash
sudo bash scripts/install_robot_service.sh
sudo systemctl status lab-robot.service
journalctl -u lab-robot.service -f
```

The systemd service runs the ROS launch process automatically on every Pi boot. Flutter does not need to be open for the robot-side ROS stack to run.

## Hardware mode — only after verification

Edit `config/robot.env`:

```dotenv
HARDWARE_MODE=true
SIMULATION_ENABLED=false
MOTOR_ESP32_PORT=/dev/serial/by-id/your-motor-controller-id
SENSOR_ESP32_PORT=/dev/serial/by-id/your-sensor-controller-id
```

Then restart the service:

```bash
sudo systemctl restart lab-robot.service
```

Do not enable hardware mode until the exact GPIO assignments and power wiring have been confirmed. Start with motor power disconnected, then test with wheels lifted and a working physical E-stop.

## Object detection

OpenCV camera streaming works independently of YOLO. For object detection, install `requirements-vision.txt`, set `YOLO_MODEL_PATH` in `config/robot.env` to a model file on the Pi and restart the service. The Pi 4 CPU may deliver low FPS; measure it and use a small model or an accelerator if needed.

## LLM and voice

The ROS API can use an OpenAI-compatible chat-completions endpoint when `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL` are set in `config/robot.env`. Without these credentials it replies with a local robot-status summary. The Flutter app uses the phone's speech-to-text and text-to-speech services. LLM responses are informational and do not directly command motors.

## Known limits to resolve against your actual build

- Firmware pin numbers are examples/placeholders, not a verified wiring diagram.
- Sensor firmware currently targets Adafruit VL53L0X-compatible modules. VL53L1X or other models need the matching driver/API.
- The four VL53 devices need separate XSHUT lines and address reassignment, or a supported I2C multiplexer. Confirm your breakout boards.
- Two BTS7960s provide two motor channels. Pairing four motors into left/right groups is permitted only if driver and motor stall-current ratings allow it.
- Battery percentage is not available until a battery monitor/voltage-sense circuit is specified.
- The touchscreen face is Pygame-based. An LED matrix has no driver because its exact model/controller was not in the component sheet.
- No encoders or LiDAR are listed; this package does not include wheel odometry, SLAM or Nav2 autonomous navigation.
