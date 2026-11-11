"""Central ROS safety/state supervisor. ESP32 firmware must enforce local watchdog/E-stop too."""
import json
import time
from datetime import datetime, timezone

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from .safety_policy import validate_motion

VALID_STATES = {'OFF', 'BOOTING', 'IDLE', 'ACTIVE', 'STANDBY', 'FAULT', 'E_STOP'}
MOTION = {'move_forward', 'move_backward', 'turn_left', 'turn_right'}
DIRECTION_SENSOR = {
    'move_forward': 'front', 'move_backward': 'rear',
    'turn_left': 'left', 'turn_right': 'right',
}


class SafetySupervisor(Node):
    def __init__(self):
        super().__init__('safety_supervisor')
        self.declare_parameter('obstacle_stop_m', 0.25)
        self.declare_parameter('sensor_stale_s', 0.75)
        self.declare_parameter('max_speed_mps', 0.15)
        self.state = 'BOOTING'
        self.simulation = False
        self.sensors = {}
        self.sensor_time = 0.0
        self.motor_status = {}
        self.motor_status_time = 0.0
        self.estop_latched = False
        self.fault = None
        self.last_command = 'boot'
        self.motor_pub = self.create_publisher(String, '/robot/motor_command', 10)
        self.sensor_command_pub = self.create_publisher(String, '/robot/sensor_command', 10)
        self.status_pub = self.create_publisher(String, '/robot/status', 10)
        self.create_subscription(String, '/robot/app_command', self.on_app_command, 10)
        self.create_subscription(String, '/robot/sensors', self.on_sensors, 10)
        self.create_subscription(String, '/robot/motor_status', self.on_motor_status, 10)
        self.create_subscription(String, '/robot/detections', self.on_detections, 10)
        self.detections = []
        self.create_timer(0.25, self.publish_status)
        self._publish_motor({'action': 'stop', 'speed': 0.0, 'duration_s': 0.1})
        self.state = 'IDLE'
        self.get_logger().info('Safety supervisor ready; motor output remains stopped until ACTIVE.')

    def on_sensors(self, msg):
        try:
            payload = json.loads(msg.data)
            values = payload.get('sensors', payload)
            if not isinstance(values, dict):
                return
            clean = {}
            for key in ('front', 'left', 'right', 'rear'):
                val = values.get(key)
                clean[key] = float(val) if val is not None else None
            self.sensors = clean
            self.simulation = bool(payload.get('simulation', False))
            self.sensor_time = time.monotonic()
        except Exception as exc:
            self.get_logger().warning(f'Invalid sensor message: {exc}')

    def on_motor_status(self, msg):
        try:
            self.motor_status = json.loads(msg.data)
            self.motor_status_time = time.monotonic()
            if self.motor_status.get('estop_healthy') is False:
                self.estop_latched = True
                self.state = 'E_STOP'
                self.fault = 'Physical emergency stop is active or its circuit is open.'
                self._publish_motor({'action': 'stop', 'speed': 0.0, 'duration_s': 0.1})
            # E-stop release never resumes motion. An explicit reset command is required.
        except Exception as exc:
            self.get_logger().warning(f'Invalid motor status: {exc}')

    def on_detections(self, msg):
        try:
            data = json.loads(msg.data)
            self.detections = data.get('detections', [])[:30]
        except Exception:
            self.detections = []

    def on_app_command(self, msg):
        try:
            command = json.loads(msg.data)
            if not isinstance(command, dict):
                raise ValueError('command must be a JSON object')
            action = str(command.get('action', '')).strip().lower()
            if self.estop_latched and action not in {'stop', 'reset_estop'}:
                self._reject('Emergency stop is latched. Release the physical E-stop and request reset.')
                return
            speed = float(command.get('speed', 0.08))
            duration = float(command.get('duration_s', 0.5))
            if action == 'start':
                if self.state in {'OFF', 'STANDBY', 'IDLE'}:
                    if self.estop_latched:
                        self._reject('Cannot start: reset the physical E-stop first.')
                    else:
                        self.state = 'IDLE'; self.fault = None; self.last_command = 'start'
                else:
                    self._reject(f'Cannot start from {self.state}.')
                return
            if action == 'activate':
                if self.state not in {'IDLE', 'STANDBY'} or self.estop_latched:
                    self._reject(f'Activation rejected while state={self.state}.')
                    return
                self.state = 'ACTIVE'; self.last_command = action
                return
            if action in {'standby', 'off'}:
                self._stop()
                self.state = 'STANDBY' if action == 'standby' else 'OFF'
                self.last_command = action
                return
            if action == 'wake':
                if self.state == 'STANDBY' and not self.estop_latched:
                    self.state = 'IDLE'; self.last_command = action
                else:
                    self._reject('Wake is allowed only from STANDBY with E-stop released.')
                return
            if action == 'reset_estop':
                healthy = self.motor_status.get('estop_healthy') is True
                if healthy and self.estop_latched:
                    self.estop_latched = False
                    self.fault = None
                    self.state = 'IDLE'
                    self.last_command = 'reset_estop'
                else:
                    self._reject('E-stop reset rejected: physical E-stop circuit is not confirmed healthy.')
                return
            if action == 'stop':
                self._stop(); self.last_command = 'stop'; return
            if action == 'set_servo':
                if self.state not in {'IDLE', 'ACTIVE'}:
                    self._reject('Servo command requires IDLE or ACTIVE state.'); return
                angle = int(command.get('angle', 90))
                if not 20 <= angle <= 160:
                    self._reject('Servo angle must be between 20 and 160 degrees.'); return
                self._publish(self.sensor_command_pub, {'action': 'servo', 'angle': angle})
                self.last_command = 'set_servo'
                return
            if action in MOTION:
                self._motion(action, speed, duration)
                return
            self._reject(f'Unknown action: {action}')
        except Exception as exc:
            self._reject(f'Malformed app command: {exc}')

    def _motion(self, action, speed, duration):
        sensor_age = None if self.sensor_time <= 0 else time.monotonic() - self.sensor_time
        motor_age = None if self.motor_status_time <= 0 else time.monotonic() - self.motor_status_time
        allowed, reason = validate_motion(
            action=action, speed=speed, duration_s=duration, state=self.state,
            sensors=self.sensors, sensor_age_s=sensor_age,
            motor_status_age_s=motor_age,
            estop_healthy=self.motor_status.get('estop_healthy'),
            obstacle_stop_m=float(self.get_parameter('obstacle_stop_m').value),
            max_speed_mps=float(self.get_parameter('max_speed_mps').value),
            sensor_stale_s=float(self.get_parameter('sensor_stale_s').value),
            simulation=self.simulation,
        )
        if not allowed:
            self._stop(); self._reject(reason); return
        duration = min(max(float(duration), 0.1), 2.0)
        self._publish_motor({'action': action, 'speed': float(speed), 'duration_s': duration})
        self.last_command = action

    def _stop(self):
        self._publish_motor({'action': 'stop', 'speed': 0.0, 'duration_s': 0.1})

    def _publish_motor(self, payload):
        self._publish(self.motor_pub, payload)

    @staticmethod
    def _publish(publisher, payload):
        msg = String(); msg.data = json.dumps(payload, separators=(',', ':'))
        publisher.publish(msg)

    def _reject(self, reason):
        self.get_logger().warning(reason)
        self.fault = reason
        self.last_command = 'rejected'
        self._stop()

    def publish_status(self):
        sensor_age = None if not self.sensor_time else round(time.monotonic() - self.sensor_time, 3)
        payload = {
            'name': 'AI Laboratory Assistant Robot',
            'state': self.state,
            'simulation': self.simulation,
            'connected': bool(self.motor_status) or bool(self.sensors),
            'motors_enabled': bool(self.motor_status.get('motors_enabled', False)),
            'motor_estop_healthy': self.motor_status.get('estop_healthy'),
            'sensors': self.sensors,
            'sensor_age_s': sensor_age,
            'servo_angle': self.motor_status.get('servo_angle', 90),
            'detections': self.detections,
            'fault': self.fault,
            'last_command': self.last_command,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
        msg = String(); msg.data = json.dumps(payload)
        self.status_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = SafetySupervisor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node._stop()
        node.destroy_node()
        rclpy.shutdown()
