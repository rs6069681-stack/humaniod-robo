"""Optional ROS-driven animated robot face for the Pi touchscreen."""
import json
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

try:
    import pygame
except ImportError:
    pygame = None


class RobotDisplayNode(Node):
    def __init__(self):
        super().__init__('robot_display')
        if pygame is None:
            raise RuntimeError('pygame missing; install python3-pygame')
        pygame.init()
        self.screen = pygame.display.set_mode((800, 480), pygame.FULLSCREEN)
        pygame.display.set_caption('AI Laboratory Assistant')
        self.state = 'BOOTING'
        self.detections = []
        self.create_subscription(String, '/robot/status', self.on_status, 10)
        self.create_subscription(String, '/robot/detections', self.on_detections, 10)
        self.timer = self.create_timer(0.1, self.draw)
        self.get_logger().info('Robot touchscreen face started; press ESC with a keyboard to exit.')

    def on_status(self, msg):
        try: self.state = json.loads(msg.data).get('state', self.state)
        except Exception: pass

    def on_detections(self, msg):
        try: self.detections = json.loads(msg.data).get('detections', [])[:3]
        except Exception: self.detections = []

    def draw(self):
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                rclpy.shutdown()
                return
        screen = self.screen
        screen.fill((13, 25, 39))
        w, h = screen.get_size(); cx, cy = w // 2, h // 2
        accent = (68, 213, 180)
        if self.state in ('FAULT', 'E_STOP'): accent = (255, 86, 86)
        elif self.state in ('STANDBY', 'OFF'): accent = (135, 157, 180)
        pygame.draw.circle(screen, (25, 46, 65), (cx, cy - 10), 170)
        eye_y = cy - 55
        eye_h = 12 if self.state in ('STANDBY', 'OFF') else 38
        pygame.draw.ellipse(screen, accent, (cx - 100, eye_y - eye_h // 2, 58, eye_h))
        pygame.draw.ellipse(screen, accent, (cx + 42, eye_y - eye_h // 2, 58, eye_h))
        mouth = pygame.Rect(cx - 52, cy + 20, 104, 55)
        if self.state in ('FAULT', 'E_STOP'):
            pygame.draw.line(screen, accent, (cx - 45, cy + 54), (cx + 45, cy + 54), 7)
        elif self.state in ('STANDBY', 'OFF'):
            pygame.draw.line(screen, accent, (cx - 35, cy + 48), (cx + 35, cy + 48), 6)
        else:
            pygame.draw.arc(screen, accent, mouth, 3.3, 6.1, 7)
        title_font = pygame.font.Font(None, 38)
        small_font = pygame.font.Font(None, 25)
        title = title_font.render(f'LAB ASSISTANT  |  {self.state}', True, (238, 246, 250))
        screen.blit(title, title.get_rect(center=(cx, h - 55)))
        if self.detections:
            names = ', '.join(str(d.get('label', 'object')) for d in self.detections)
            line = small_font.render('I see: ' + names[:65], True, (190, 211, 224))
            screen.blit(line, line.get_rect(center=(cx, h - 24)))
        pygame.display.flip()

    def destroy_node(self):
        pygame.quit()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = RobotDisplayNode()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally:
        node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()
