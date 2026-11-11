#!/usr/bin/env bash
set -euo pipefail
if [[ ! -f /opt/ros/jazzy/setup.bash ]]; then
  echo 'ROS 2 Jazzy not found at /opt/ros/jazzy. Install Ubuntu 24.04 + ROS 2 Jazzy first.' >&2
  exit 1
fi
source /opt/ros/jazzy/setup.bash
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/ros2_ws"
rosdep install --from-paths src --ignore-src -r -y || true
colcon build --symlink-install
printf '\nBuild complete. Source with: source %s/ros2_ws/install/setup.bash\n' "$ROOT"
