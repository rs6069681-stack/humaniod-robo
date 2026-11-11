#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "$ROOT/config/robot.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/config/robot.env"
  set +a
fi
if [[ "${HARDWARE_MODE:-false}" == "true" && "${SIMULATION_ENABLED:-true}" == "true" ]]; then
  echo 'Invalid config: set SIMULATION_ENABLED=false when HARDWARE_MODE=true.' >&2
  exit 2
fi
if [[ "${HARDWARE_MODE:-false}" == "true" ]]; then
  if [[ "${MOTOR_ESP32_PORT:-}" == *REPLACE* || "${SENSOR_ESP32_PORT:-}" == *REPLACE* ]]; then
    echo 'Hardware mode blocked: replace both ESP32 serial placeholders with actual /dev/serial/by-id paths.' >&2
    exit 2
  fi
fi
source /opt/ros/jazzy/setup.bash
source "$ROOT/ros2_ws/install/setup.bash"
exec ros2 launch lab_robot_bringup robot.launch.py \
  hardware_mode:="${HARDWARE_MODE:-false}" \
  simulation_enabled:="${SIMULATION_ENABLED:-true}" \
  camera_enabled:="${CAMERA_ENABLED:-true}" \
  display_enabled:="${DISPLAY_ENABLED:-false}"
