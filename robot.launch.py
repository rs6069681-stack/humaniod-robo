import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    hardware_mode = LaunchConfiguration('hardware_mode')
    camera_enabled = LaunchConfiguration('camera_enabled')
    display_enabled = LaunchConfiguration('display_enabled')
    motor_port = os.getenv('MOTOR_ESP32_PORT', '/dev/serial/by-id/MOTOR_ESP32')
    sensor_port = os.getenv('SENSOR_ESP32_PORT', '/dev/serial/by-id/SENSOR_ESP32')

    return LaunchDescription([
        DeclareLaunchArgument('hardware_mode', default_value='false',
                              description='false=safe simulation; true=connect physical ESP32 boards'),
        DeclareLaunchArgument('camera_enabled', default_value='true'),
        DeclareLaunchArgument('display_enabled', default_value='false'),
        DeclareLaunchArgument('simulation_enabled', default_value='true',
                              description='Publish mock sensor/motor telemetry for software testing'),
        Node(package='lab_robot_bringup', executable='safety_supervisor',
             name='safety_supervisor', output='screen', parameters=[{
                 'obstacle_stop_m': float(os.getenv('OBSTACLE_STOP_DISTANCE_M', '0.25')),
                 'sensor_stale_s': float(os.getenv('SENSOR_STALE_SECONDS', '0.75')),
                 'max_speed_mps': float(os.getenv('MAX_SPEED_MPS', '0.15')),
             }]),
        Node(package='lab_robot_bringup', executable='robot_api_node',
             name='robot_api_node', output='screen', parameters=[{
                 'host': os.getenv('ROBOT_API_HOST', '0.0.0.0'),
                 'port': int(os.getenv('ROBOT_API_PORT', '8000')),
                 'api_token': os.getenv('ROBOT_API_TOKEN', ''),
                 'llm_base_url': os.getenv('LLM_BASE_URL', ''),
                 'llm_api_key': os.getenv('LLM_API_KEY', ''),
                 'llm_model': os.getenv('LLM_MODEL', ''),
             }]),
        Node(package='lab_robot_bringup', executable='serial_bridge',
             name='esp32_serial_bridge', output='screen', condition=IfCondition(hardware_mode),
             parameters=[{'motor_port': motor_port, 'sensor_port': sensor_port,
                          'baudrate': int(os.getenv('ESP32_BAUDRATE', '115200'))}]),
        Node(package='lab_robot_bringup', executable='simulation_node',
             name='simulation_node', output='screen', condition=IfCondition(
                 LaunchConfiguration('simulation_enabled'))),
        Node(package='lab_robot_bringup', executable='camera_vision_node',
             name='camera_vision_node', output='screen', condition=IfCondition(camera_enabled),
             parameters=[{
                 'camera_index': int(os.getenv('CAMERA_INDEX', '0')),
                 'width': int(os.getenv('CAMERA_WIDTH', '640')),
                 'height': int(os.getenv('CAMERA_HEIGHT', '480')),
                 'fps': int(os.getenv('CAMERA_FPS', '15')),
                 'model_path': os.getenv('YOLO_MODEL_PATH', ''),
                 'confidence': float(os.getenv('YOLO_CONFIDENCE', '0.45')),
             }]),
        Node(package='lab_robot_bringup', executable='robot_display_node',
             name='robot_display_node', output='screen', condition=IfCondition(display_enabled)),
    ])
