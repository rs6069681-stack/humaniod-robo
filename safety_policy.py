"""Pure safety checks, separated so they can be unit-tested without ROS installed."""
MOTION_ACTIONS = {'move_forward', 'move_backward', 'turn_left', 'turn_right'}
DIRECTION_SENSOR = {
    'move_forward': 'front', 'move_backward': 'rear',
    'turn_left': 'left', 'turn_right': 'right',
}


def validate_motion(*, action, speed, duration_s, state, sensors, sensor_age_s,
                    motor_status_age_s, estop_healthy, obstacle_stop_m=0.25,
                    max_speed_mps=0.15, sensor_stale_s=0.75, simulation=False):
    if action not in MOTION_ACTIONS:
        return False, 'Unsupported movement action.'
    if state != 'ACTIVE':
        return False, 'Activate the robot before movement.'
    if not (0.0 < float(speed) <= float(max_speed_mps)):
        return False, f'Speed must be greater than 0 and at most {max_speed_mps:.2f} m/s.'
    if not (0.1 <= float(duration_s) <= 2.0):
        return False, 'Movement duration must be between 0.1 and 2.0 seconds.'
    direction = DIRECTION_SENSOR[action]
    if sensor_age_s is None or sensor_age_s > sensor_stale_s:
        return False, f'{direction} distance data is missing or stale.'
    distance = sensors.get(direction)
    if distance is None:
        return False, f'{direction} distance sensor is unavailable.'
    if float(distance) < float(obstacle_stop_m):
        return False, f'Obstacle at {float(distance):.2f} m: {action} blocked.'
    if not simulation:
        if motor_status_age_s is None or motor_status_age_s > 1.5:
            return False, 'Motor controller heartbeat is missing or stale.'
        if estop_healthy is not True:
            return False, 'Physical emergency-stop circuit is not confirmed healthy.'
    return True, 'Accepted'
