"""Safe simulation feed. It simulates telemetry and command acknowledgements; never drives motors."""
import json
import time
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class SimulationNode(Node):
    def __init__(self):
        super().__init__('robot_simulation')
        self.sensor_pub = self.create_publisher(String, '/robot/sensors', 10)
        self.motor_pub = self.create_publisher(String, '/robot/motor_status', 10)
        self.create_subscription(String, '/robot/motor_command', self.on_motor_command, 10)
        self.create_subscription(String, '/robot/sensor_command', self.on_sensor_command, 10)
        self.servo_angle = 90
        self.motion_until = 0.0
        self.last_action = 'stop'
        self.timer = self.create_timer(0.1, self.publish_sample)
        self.get_logger().warning('SIMULATION MODE: commands are simulated only; no physical motor output is connected.')

    def on_motor_command(self, msg):
        try:
            payload = json.loads(msg.data)
            action = str(payload.get('action', 'stop'))
            if action == 'stop':
                self.motion_until = 0.0
                self.last_action = 'stop'
            elif action in {'move_forward', 'move_backward', 'turn_left', 'turn_right'}:
                duration = min(max(float(payload.get('duration_s', 0.5)), 0.1), 2.0)
                self.motion_until = time.monotonic() + duration
                self.last_action = action
        except Exception as exc:
            self.get_logger().warning(f'Ignored invalid simulated motor command: {exc}')

    def on_sensor_command(self, msg):
        try:
            payload = json.loads(msg.data)
            if payload.get('action') == 'servo':
                self.servo_angle = max(20, min(160, int(payload.get('angle', 90))))
        except Exception as exc:
            self.get_logger().warning(f'Ignored invalid simulated sensor command: {exc}')

    def publish_sample(self):
        sensor = String()
        sensor.data = json.dumps({'sensors': {'front': 1.20, 'left': 1.10, 'right': 1.15, 'rear': 1.30},
                                  'servo_angle': self.servo_angle, 'simulation': True, 'time': time.time()})
        moving = time.monotonic() < self.motion_until
        motor = String()
        motor.data = json.dumps({'board': 'motor_simulation', 'state': 'ACTIVE' if moving else 'IDLE',
                                 'last_action': self.last_action, 'servo_angle': self.servo_angle, 'estop_healthy': True,
                                 'motors_enabled': moving, 'simulation': True})
        self.sensor_pub.publish(sensor)
        self.motor_pub.publish(motor)


def main(args=None):
    rclpy.init(args=args)
    node = SimulationNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node(); rclpy.shutdown()
