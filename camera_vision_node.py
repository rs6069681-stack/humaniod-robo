"""OpenCV camera + optional YOLO node. Publishes compressed annotated frames for the API node."""
import json
import time

import cv2
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import String


class CameraVisionNode(Node):
    def __init__(self):
        super().__init__('camera_vision_node')
        self.declare_parameter('camera_index', 0)
        self.declare_parameter('width', 640)
        self.declare_parameter('height', 480)
        self.declare_parameter('fps', 15)
        self.declare_parameter('model_path', '')
        self.declare_parameter('confidence', 0.45)
        self.frame_pub = self.create_publisher(CompressedImage, '/robot/camera/jpeg', 2)
        self.detection_pub = self.create_publisher(String, '/robot/detections', 10)
        self.cap = None
        self.last_camera_attempt = 0.0
        self._open_camera()
        self.model = None
        model_path = str(self.get_parameter('model_path').value).strip()
        if model_path:
            try:
                from ultralytics import YOLO
                self.model = YOLO(model_path)
                self.get_logger().info(f'YOLO model loaded: {model_path}')
            except Exception as exc:
                self.get_logger().error(f'YOLO could not load; camera will still run without AI detections: {exc}')
        self.frame_count = 0
        self.timer = self.create_timer(1.0 / max(1, int(self.get_parameter('fps').value)), self.capture)
        if not self.cap or not self.cap.isOpened():
            self.get_logger().warning('Camera not yet available; will retry automatically.')
        else:
            self.get_logger().info('OpenCV camera opened. Publishing /robot/camera/jpeg and /robot/detections.')

    def _open_camera(self):
        now = time.monotonic()
        if now - self.last_camera_attempt < 3.0:
            return
        self.last_camera_attempt = now
        cap = cv2.VideoCapture(int(self.get_parameter('camera_index').value))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(self.get_parameter('width').value))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(self.get_parameter('height').value))
        cap.set(cv2.CAP_PROP_FPS, int(self.get_parameter('fps').value))
        if cap.isOpened():
            self.cap = cap
            self.get_logger().info('OpenCV camera connected.')
        else:
            cap.release()
            self.cap = None

    def capture(self):
        if not self.cap or not self.cap.isOpened():
            self._open_camera()
            return
        ok, frame = self.cap.read()
        if not ok:
            self.cap.release()
            self.cap = None
            self.get_logger().warning('Camera frame read failed; reconnecting.')
            return
        self.frame_count += 1
        detections = []
        annotated = frame
        if self.model is not None and self.frame_count % 2 == 0:
            try:
                confidence = float(self.get_parameter('confidence').value)
                result = self.model.predict(frame, conf=confidence, verbose=False)[0]
                names = result.names
                if result.boxes is not None:
                    for box in result.boxes:
                        x1, y1, x2, y2 = [int(x) for x in box.xyxy[0].tolist()]
                        score = float(box.conf[0])
                        cls_id = int(box.cls[0])
                        label = str(names.get(cls_id, cls_id))
                        detections.append({'label': label, 'confidence': round(score, 4),
                                           'bbox': [x1, y1, x2, y2]})
                        cv2.rectangle(annotated, (x1, y1), (x2, y2), (60, 220, 140), 2)
                        cv2.putText(annotated, f'{label} {score:.2f}', (x1, max(20, y1 - 8)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (60, 220, 140), 2)
            except Exception as exc:
                self.get_logger().warning(f'YOLO inference error: {exc}')
        det = String()
        det.data = json.dumps({'timestamp': time.time(), 'detections': detections})
        self.detection_pub.publish(det)
        ok, encoded = cv2.imencode('.jpg', annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
        if ok:
            image = CompressedImage()
            image.header.stamp = self.get_clock().now().to_msg()
            image.format = 'jpeg'
            image.data = encoded.tobytes()
            self.frame_pub.publish(image)

    def destroy_node(self):
        if self.cap:
            self.cap.release()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = CameraVisionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node(); rclpy.shutdown()
