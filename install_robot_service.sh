#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN_USER="${SUDO_USER:-$(id -un)}"
if [[ $EUID -ne 0 ]]; then
  echo 'Run with: sudo ./scripts/install_robot_service.sh' >&2
  exit 1
fi
if [[ ! -f "$ROOT/ros2_ws/install/setup.bash" ]]; then
  echo 'ROS workspace has not been built. Run scripts/build_ros.sh first.' >&2
  exit 1
fi
ENV_FILE="$ROOT/config/robot.env"
if grep -q 'CHANGE_THIS_TO_A_LONG_RANDOM_SECRET' "$ENV_FILE"; then
  TOKEN="$(openssl rand -hex 24)"
  sed -i "s/CHANGE_THIS_TO_A_LONG_RANDOM_SECRET/$TOKEN/" "$ENV_FILE"
  echo "Generated API token in $ENV_FILE. Copy it to the Flutter app build setting." 
fi
UNIT="/etc/systemd/system/lab-robot.service"
cat > "$UNIT" <<UNITFILE
[Unit]
Description=AI Laboratory Assistant Robot ROS 2 Stack
Wants=network-online.target
After=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=$RUN_USER
SupplementaryGroups=dialout video
WorkingDirectory=$ROOT
EnvironmentFile=$ENV_FILE
Environment=PYTHONUNBUFFERED=1
ExecStart=/bin/bash $ROOT/scripts/run_robot.sh
Restart=on-failure
RestartSec=5
KillSignal=SIGINT
TimeoutStopSec=15

[Install]
WantedBy=multi-user.target
UNITFILE
systemctl daemon-reload
systemctl enable --now lab-robot.service
systemctl --no-pager --full status lab-robot.service || true
printf '\nAuto-start enabled. Logs: journalctl -u lab-robot -f\n'
printf 'API token is stored in: %s\n' "$ENV_FILE"
