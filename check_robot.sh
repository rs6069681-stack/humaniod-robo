#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo '=== ROS ==='
ros2 doctor --report || true
echo '\n=== systemd ==='
systemctl --no-pager status lab-robot.service || true
echo '\n=== serial devices ==='
ls -l /dev/serial/by-id 2>/dev/null || true
echo '\n=== video devices ==='
v4l2-ctl --list-devices 2>/dev/null || ls -l /dev/video* 2>/dev/null || true
echo '\n=== ROS topics (requires sourced workspace) ==='
source /opt/ros/jazzy/setup.bash
source "$ROOT/ros2_ws/install/setup.bash"
ros2 topic list || true
