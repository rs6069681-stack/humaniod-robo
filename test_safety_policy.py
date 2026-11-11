import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ros2_ws/src/lab_robot_bringup'))
from lab_robot_bringup.safety_policy import validate_motion

BASE = dict(action='move_forward', speed=0.08, duration_s=0.5, state='ACTIVE',
            sensors={'front': 1.0, 'rear': 1.0, 'left': 1.0, 'right': 1.0},
            sensor_age_s=0.05, motor_status_age_s=0.1, estop_healthy=True)

def test_valid_simulated_motion():
    assert validate_motion(**BASE, simulation=True)[0] is True

def test_blocks_when_not_active():
    args = dict(BASE); args['state'] = 'STANDBY'
    assert validate_motion(**args, simulation=True)[0] is False

def test_blocks_stale_sensors():
    args = dict(BASE); args['sensor_age_s'] = 2.0
    assert validate_motion(**args, simulation=True)[0] is False

def test_blocks_obstacle():
    args = dict(BASE); args['sensors'] = dict(BASE['sensors'], front=0.10)
    assert validate_motion(**args, simulation=True)[0] is False

def test_hardware_requires_motor_watchdog_and_estop_telemetry():
    args = dict(BASE); args['motor_status_age_s'] = None
    assert validate_motion(**args, simulation=False)[0] is False
    args = dict(BASE); args['estop_healthy'] = False
    assert validate_motion(**args, simulation=False)[0] is False
