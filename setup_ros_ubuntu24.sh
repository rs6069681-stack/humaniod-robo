#!/usr/bin/env bash
set -euo pipefail
VERSION_ID="$(. /etc/os-release && echo "$VERSION_ID")"
if [[ "$VERSION_ID" != "24.04" ]]; then
  echo 'This installer targets Ubuntu 24.04 (Noble) 64-bit with ROS 2 Jazzy.' >&2
  echo 'ROS Jazzy binaries are not a generic install for every Raspberry Pi OS release.' >&2
  exit 2
fi

sudo apt update
sudo apt install -y software-properties-common curl locales
sudo add-apt-repository universe -y
sudo locale-gen en_US en_US.UTF-8 || true

# Official ROS repository bootstrap package keeps repository/key configuration updated.
sudo apt update
ROS_APT_SOURCE_VERSION="$(curl -fsSL https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest | grep -F 'tag_name' | head -1 | awk -F'"' '{print $4}')"
if [[ -z "$ROS_APT_SOURCE_VERSION" ]]; then
  echo 'Could not determine the ros-apt-source release version. Install ROS 2 Jazzy following the official manual guide.' >&2
  exit 3
fi
CODENAME="$(. /etc/os-release && echo "${UBUNTU_CODENAME:-${VERSION_CODENAME}}")"
curl -fL -o /tmp/ros2-apt-source.deb \
  "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros2-apt-source_${ROS_APT_SOURCE_VERSION}.${CODENAME}_all.deb"
sudo dpkg -i /tmp/ros2-apt-source.deb
sudo apt update
sudo apt install -y \
  ros-jazzy-ros-base ros-dev-tools python3-colcon-common-extensions python3-rosdep \
  python3-fastapi python3-uvicorn python3-pydantic python3-opencv \
  python3-serial python3-pip python3-pygame v4l-utils git

if [[ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]]; then
  sudo rosdep init || true
fi
rosdep update
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
bash "$ROOT/scripts/build_ros.sh"
echo 'ROS dependencies installed and workspace built. Keep hardware mode OFF until wiring is verified.'
