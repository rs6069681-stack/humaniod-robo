from setuptools import setup
from glob import glob
import os

package_name = 'lab_robot_bringup'
setup(
    name=package_name,
    version='2.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    entry_points={'console_scripts': [
        'serial_bridge = lab_robot_bringup.serial_bridge:main',
        'safety_supervisor = lab_robot_bringup.safety_supervisor:main',
        'simulation_node = lab_robot_bringup.simulation_node:main',
        'camera_vision_node = lab_robot_bringup.camera_vision_node:main',
        'robot_api_node = lab_robot_bringup.robot_api_node:main',
        'robot_display_node = lab_robot_bringup.robot_display_node:main',
    ]},
)
