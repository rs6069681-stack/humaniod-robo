# Network and phone-app connection

1. ROS 2 and the API node run on the Raspberry Pi.
2. The API listens on `0.0.0.0:8000` by default.
3. The phone app sends commands and reads status over HTTP.
4. The phone app receives camera JPEG frames over a separate WebSocket.
5. Set `ROBOT_API_TOKEN` in `config/robot.env`; the service installer generates one if the placeholder is present.
6. Enter the same token when running/building Flutter using `--dart-define=ROBOT_API_TOKEN=...`.

Keep the API on a trusted Wi-Fi network only. Do not port-forward it to the internet. For a deployed robot, use HTTPS/WSS, a proper pairing/login flow, firewall allow-listing and short-lived credentials. A static token compiled into an APK is convenient for a prototype but is not a secure production identity system.

## Phone controls and software states

| App button | ROS state/action | Meaning |
|---|---|---|
| Start / Ready | `start` → `IDLE` | Makes the robot software ready after OFF/STANDBY |
| Activate | `activate` → `ACTIVE` | Allows movement requests to pass safety checks |
| STOP | `stop` | Stops the motors without necessarily changing ACTIVE state |
| Standby | `standby` → `STANDBY` | Stops movement but leaves Pi/ROS/API online |
| Wake | `wake` → `IDLE` | Leaves standby; movement still requires Activate |
| Robot OFF | `off` → `OFF` | Stops movement and disables operation; Pi/ROS/API stay online |
| Reset E-Stop | `reset_estop` → `IDLE` | Only after physical E-stop circuit reports healthy |

The app's Robot OFF is a software state, not an electrical shutdown. If the Pi is fully powered down, the app cannot reach its API to start it. For true remote power-on, add a separate power-management board/latching circuit with a safe wake input.
