"""Two USB serial bridges: motor ESP32 and sensor/servo ESP32."""
import json
import os
import threading
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

try:
    import serial
except ImportError:
    serial = None


class SerialBridge(Node):
    def __init__(self):
        super().__init__('esp32_serial_bridge')
        self.declare_parameter('motor_port', os.getenv('MOTOR_ESP32_PORT', '/dev/ttyUSB0'))
        self.declare_parameter('sensor_port', os.getenv('SENSOR_ESP32_PORT', '/dev/ttyUSB1'))
        self.declare_parameter('baudrate', 115200)
        self.baud = int(self.get_parameter('baudrate').value)
        self.motor_port = str(self.get_parameter('motor_port').value)
        self.sensor_port = str(self.get_parameter('sensor_port').value)
        self.last_attempt = {'motor': 0.0, 'sensor': 0.0}
        self.lock = threading.RLock()
        self.buffers = {'motor': bytearray(), 'sensor': bytearray()}
        self.motor = self._open(self.motor_port, 'motor')
        self.sensor = self._open(self.sensor_port, 'sensor')
        self.sensor_pub = self.create_publisher(String, '/robot/sensors', 10)
        self.motor_status_pub = self.create_publisher(String, '/robot/motor_status', 10)
        self.create_subscription(String, '/robot/motor_command', self.motor_command, 10)
        self.create_subscription(String, '/robot/sensor_command', self.sensor_command, 10)
        self.timer = self.create_timer(0.02, self.read_ports)
        self.get_logger().warning('Motor GPIO assignments and serial devices must be verified before enabling hardware mode.')

    def _open(self, port, label):
        if serial is None:
            self.get_logger().error('pyserial missing. Install python3-serial.')
            return None
        try:
            link = serial.Serial(port, self.baud, timeout=0, write_timeout=0.2)
            self.get_logger().info(f'{label} ESP32 connected: {port}')
            return link
        except Exception as exc:
            self.get_logger().error(f'{label} ESP32 unavailable at {port}: {exc}')
            return None

    def _send(self, link, msg, label):
        if link is None:
            self.get_logger().error(f'{label} command rejected: board not connected')
            return
        try:
            payload = json.loads(msg.data)
            if not isinstance(payload, dict):
                raise ValueError('JSON payload must be an object')
            encoded = (json.dumps(payload, separators=(',', ':')) + '\n').encode('utf-8')
            with self.lock:
                link.write(encoded)
        except Exception as exc:
            self.get_logger().warning(f'{label} command rejected: {exc}')

    def motor_command(self, msg):
        self._send(self.motor, msg, 'motor')

    def sensor_command(self, msg):
        self._send(self.sensor, msg, 'sensor')

    def _reconnect_if_needed(self):
        now = time.monotonic()
        for key, attr, port in (('motor', 'motor', self.motor_port),
                                ('sensor', 'sensor', self.sensor_port)):
            if getattr(self, attr) is None and now - self.last_attempt[key] >= 3.0:
                self.last_attempt[key] = now
                setattr(self, attr, self._open(port, key))

    def _read_one(self, link, publisher, label, key):
        if link is None:
            return
        try:
            with self.lock:
                count = link.in_waiting
                if count:
                    self.buffers[key].extend(link.read(count))
            while b'\n' in self.buffers[key]:
                raw, _, remainder = self.buffers[key].partition(b'\n')
                self.buffers[key] = bytearray(remainder)
                line = raw.decode('utf-8', errors='ignore').strip()
                if not line:
                    continue
                try:
                    json.loads(line)
                    out = String(); out.data = line; publisher.publish(out)
                except json.JSONDecodeError:
                    self.get_logger().warning(f'{label} produced invalid JSON telemetry')
            if len(self.buffers[key]) > 4096:
                self.buffers[key].clear()
                self.get_logger().warning(f'{label} serial line too large; buffer reset')
        except Exception as exc:
            self.get_logger().error(f'{label} serial read failed: {exc}; will reconnect')
            try:
                link.close()
            except Exception:
                pass
            if key == 'motor': self.motor = None
            else: self.sensor = None

    def read_ports(self):
        self._reconnect_if_needed()
        self._read_one(self.sensor, self.sensor_pub, 'sensor ESP32', 'sensor')
        self._read_one(self.motor, self.motor_status_pub, 'motor ESP32', 'motor')

    def destroy_node(self):
        try:
            if self.motor:
                self.motor.write(b'{"action":"stop","speed":0,"duration_s":0.1}\n')
            if self.motor:
                self.motor.close()
            if self.sensor:
                self.sensor.close()
        except Exception:
            pass
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = SerialBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
