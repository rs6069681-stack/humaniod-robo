# Install ROS software and enable automatic startup

## Target platform

Recommended target: Raspberry Pi 4 (4 GB or 8 GB) running **Ubuntu 24.04 64-bit** and **ROS 2 Jazzy**. The setup script intentionally checks the Ubuntu version. Do not run it unmodified on another OS release.

## 1. Copy the robot-side folder to the Raspberry Pi

Copy `robot_ros_software/` to a stable path such as `/home/robot/lab_robot/robot_ros_software/`.

## 2. Install dependencies and build the ROS workspace

```bash
cd ~/lab_robot/robot_ros_software
bash scripts/setup_ros_ubuntu24.sh
```

This installs the ROS base, colcon/rosdep, FastAPI/uvicorn/Pydantic, OpenCV, serial support, Pygame and camera utilities, then builds the package.

## 3. Test simulation before attaching motor power

```bash
bash scripts/run_robot.sh
```

In another terminal:

```bash
curl http://127.0.0.1:8000/api/health
ros2 topic list
ros2 topic echo /robot/status
```

The `config/robot.env` defaults to simulation. The simulation node publishes mock front/left/right/rear distances and mock motor-controller health. No ESP32 serial motor bridge is launched.

## 4. Enable automatic launch at every boot

```bash
sudo bash scripts/install_robot_service.sh
sudo systemctl status lab-robot.service
journalctl -u lab-robot.service -f
```

The installer creates `/etc/systemd/system/lab-robot.service`, generates a random API token if the placeholder remains, enables the service for boot, and starts it now. The API token is in `config/robot.env`; pass it to the phone app at build time.

## 5. Connect the Flutter app

On the development computer, open the separate folder `flutter_mobile_app/`, generate Flutter platform files, and run:

```bash
flutter create --project-name lab_assistant_robot_app --org com.labrobot --platforms=android,ios,web .
flutter pub get
flutter run --dart-define=ROBOT_API_URL=http://PI_LAN_IP:8000 --dart-define=ROBOT_API_TOKEN=TOKEN_FROM_CONFIG
```

Phone and Pi must be on the same trusted Wi-Fi/LAN. Use the Pi's actual LAN IP, obtained with `hostname -I`.

## 6. Hardware commissioning

Before hardware mode:

1. Identify both ESP32 devices using `ls -l /dev/serial/by-id/` and use persistent IDs in `config/robot.env`.
2. Verify logic and motor supply voltage independently with a multimeter.
3. Confirm the exact ESP32 variant and GPIO pins; replace the placeholder pin map in both `.ino` files.
4. Confirm exact VL53 module model and I2C wiring. Four sensors need XSHUT/address handling or a suitable multiplexer.
5. Verify motor stall current and BTS7960 thermal/current ratings before pairing two motors on a channel.
6. Install and test a physical normally-closed E-stop loop that disables motor driver enable/power independently of ROS.
7. Test one motor channel at a time with the wheels lifted and a current-limited supply.
8. Verify that unplugging the app, Wi-Fi, USB serial or ROS causes the ESP32 watchdog to stop motor outputs.

Only then edit `config/robot.env` to set `HARDWARE_MODE=true` and `SIMULATION_ENABLED=false`, and set the actual serial paths. Restart `lab-robot.service`.

## 7. Screen / display

The optional Pygame robot face is disabled by default. On a Pi with a running graphical desktop, set `DISPLAY_ENABLED=true`, make sure the systemd service has the correct `DISPLAY` and `XAUTHORITY`, then restart the service. The code is for a touchscreen/HDMI framebuffer-style display; it is not a driver for an unspecified LED matrix.

## 8. Logs and diagnostics

```bash
sudo systemctl status lab-robot.service
journalctl -u lab-robot.service -f
bash scripts/check_robot.sh
```

## State machine

`BOOTING → IDLE → ACTIVE` is the normal start path. `ACTIVE → STANDBY → IDLE` is standby/wake. `IDLE/ACTIVE/STANDBY → OFF` stops movement and changes the robot software mode. `E_STOP` is latched until the physical switch circuit reports healthy and the phone app sends `Reset E-Stop`. The Raspberry Pi remains powered in OFF and STANDBY so the API can remain reachable.
