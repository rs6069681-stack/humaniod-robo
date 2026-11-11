"""Phone-app API hosted as a ROS 2 node. Flutter remains a separate app/process."""
import asyncio
import hmac
import json
import os
import threading
import time
import urllib.request
import urllib.error
from collections import deque

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from sensor_msgs.msg import CompressedImage

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field
import uvicorn


class CommandBody(BaseModel):
    action: str = Field(min_length=2, max_length=32)
    speed: float = Field(default=0.08, ge=0.0, le=0.15)
    duration_s: float = Field(default=0.5, ge=0.1, le=2.0)
    angle: int | None = Field(default=None, ge=20, le=160)


class ChatBody(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class IntentBody(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class RobotApiNode(Node):
    def __init__(self):
        super().__init__('robot_api_node')
        self.declare_parameter('host', os.getenv('ROBOT_API_HOST', '0.0.0.0'))
        self.declare_parameter('port', int(os.getenv('ROBOT_API_PORT', '8000')))
        self.declare_parameter('api_token', os.getenv('ROBOT_API_TOKEN', ''))
        self.declare_parameter('llm_base_url', os.getenv('LLM_BASE_URL', ''))
        self.declare_parameter('llm_api_key', os.getenv('LLM_API_KEY', ''))
        self.declare_parameter('llm_model', os.getenv('LLM_MODEL', ''))
        self._lock = threading.RLock()
        self._state = {
            'name': 'AI Laboratory Assistant Robot', 'state': 'BOOTING',
            'simulation': True, 'connected': False, 'motors_enabled': False,
            'battery_percent': None, 'motor_estop_healthy': None,
            'sensors': {'front': None, 'left': None, 'right': None, 'rear': None},
            'sensor_age_s': None, 'servo_angle': 90, 'detections': [],
            'fault': None, 'timestamp': None, 'last_command': None,
        }
        self._jpeg = None
        self._events = deque(maxlen=100)
        self.command_pub = self.create_publisher(String, '/robot/app_command', 10)
        self.create_subscription(String, '/robot/status', self.on_status, 10)
        self.create_subscription(String, '/robot/detections', self.on_detections, 10)
        self.create_subscription(CompressedImage, '/robot/camera/jpeg', self.on_camera, 2)
        self.app = self._create_app()
        self.server = None
        self.server_thread = None
        self._start_http_server()

    def add_event(self, kind, message):
        with self._lock:
            self._events.append({'time': time.time(), 'type': kind, 'message': str(message)[:300]})

    def on_status(self, msg):
        try:
            payload = json.loads(msg.data)
            with self._lock:
                self._state.update(payload)
        except Exception as exc:
            self.get_logger().warning(f'Invalid /robot/status message: {exc}')

    def on_detections(self, msg):
        try:
            payload = json.loads(msg.data)
            with self._lock:
                self._state['detections'] = payload.get('detections', [])[:30]
        except Exception:
            pass

    def on_camera(self, msg):
        with self._lock:
            self._jpeg = bytes(msg.data)

    def snapshot(self):
        with self._lock:
            data = dict(self._state)
            data['sensors'] = dict(self._state.get('sensors', {}))
            data['detections'] = list(self._state.get('detections', []))
            data['events'] = list(self._events)[-50:]
            return data

    def jpeg(self):
        with self._lock:
            return self._jpeg

    def token_ok(self, token):
        expected = str(self.get_parameter('api_token').value)
        if not expected:
            return True
        return bool(token) and hmac.compare_digest(token, expected)

    async def require_auth(self, authorization: str | None = Header(default=None)):
        expected = str(self.get_parameter('api_token').value)
        if expected:
            supplied = authorization or ''
            if not supplied.startswith('Bearer ') or not self.token_ok(supplied[7:]):
                raise HTTPException(status_code=401, detail='Valid Bearer token required')

    def publish_command(self, payload):
        msg = String(); msg.data = json.dumps(payload, separators=(',', ':'))
        self.command_pub.publish(msg)
        self.add_event('app_command', payload.get('action', 'unknown'))

    def _create_app(self):
        api = FastAPI(title='AI Laboratory Assistant Robot ROS API', version='2.0.0')
        api.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=False,
                           allow_methods=['GET', 'POST'], allow_headers=['*'])
        owner = self

        @api.get('/api/health')
        async def health():
            status = owner.snapshot()
            return {'ok': True, 'service': 'robot_api_node', 'ros_state': status.get('state'),
                    'simulation': status.get('simulation'), 'camera_available': owner.jpeg() is not None}

        @api.get('/api/status', dependencies=[Depends(self.require_auth)])
        async def status():
            return owner.snapshot()

        @api.post('/api/command', dependencies=[Depends(self.require_auth)])
        async def command(body: CommandBody):
            allowed = {'start', 'activate', 'stop', 'standby', 'wake', 'off', 'reset_estop',
                       'move_forward', 'move_backward', 'turn_left', 'turn_right', 'set_servo'}
            if body.action not in allowed:
                raise HTTPException(status_code=400, detail='Unsupported command')
            payload = body.model_dump(exclude_none=True)
            owner.publish_command(payload)
            return {'accepted': True, 'queued_for_ros_safety_check': True,
                    'message': f"'{body.action}' sent to ROS safety supervisor; check live status for result."}

        @api.post('/api/intent/preview', dependencies=[Depends(self.require_auth)])
        async def intent_preview(body: IntentBody):
            phrase = ' '.join(body.text.lower().strip().split())
            mapping = {
                'start robot': ('start', 'start robot software control'),
                'activate robot': ('activate', 'activate robot'), 'activate': ('activate', 'activate robot'),
                'stop': ('stop', 'stop movement'), 'stop robot': ('stop', 'stop movement'),
                'standby': ('standby', 'enter standby'), 'go to standby': ('standby', 'enter standby'),
                'wake': ('wake', 'wake robot from standby'), 'wake up': ('wake', 'wake robot from standby'),
                'turn off robot': ('off', 'put robot in software OFF state'),
                'move forward': ('move_forward', 'move forward'),
                'move backward': ('move_backward', 'move backward'),
                'turn left': ('turn_left', 'turn left'), 'turn right': ('turn_right', 'turn right'),
            }
            match = mapping.get(phrase)
            return {'matched': bool(match), 'requires_confirmation': bool(match),
                    'action': match[0] if match else None,
                    'description': match[1] if match else None,
                    'notice': 'Preview only. No robot command has been executed.'}

        @api.post('/api/chat', dependencies=[Depends(self.require_auth)])
        async def chat(body: ChatBody):
            status_data = owner.snapshot()
            base_url = str(owner.get_parameter('llm_base_url').value).strip().rstrip('/')
            api_key = str(owner.get_parameter('llm_api_key').value).strip()
            model = str(owner.get_parameter('llm_model').value).strip()
            if not (base_url and api_key and model):
                state = status_data.get('state', 'UNKNOWN')
                sensors = status_data.get('sensors', {})
                reply = (f"I am your laboratory assistant robot. My current state is {state}. "
                         f"Distance readings (metres): front={sensors.get('front')}, "
                         f"left={sensors.get('left')}, right={sensors.get('right')}, rear={sensors.get('rear')}. "
                         "The conversational LLM is not configured yet. Movement and safety commands are "
                         "handled separately by the ROS safety supervisor, not by the language model.")
                return {'reply': reply, 'llm_configured': False}
            request_data = {
                'model': model,
                'messages': [
                    {'role': 'system', 'content': ('You are the voice/text assistant for an indoor laboratory robot. '
                     'Explain status and detections. Never claim a movement command was executed. '
                     'Never instruct the system to bypass its ROS safety supervisor or emergency stop. '
                     'Current robot telemetry: ' + json.dumps(status_data)[:6000])},
                    {'role': 'user', 'content': body.message},
                ],
                'temperature': 0.2,
            }
            req = urllib.request.Request(base_url + '/chat/completions',
                data=json.dumps(request_data).encode('utf-8'),
                headers={'Authorization': 'Bearer ' + api_key, 'Content-Type': 'application/json'},
                method='POST')
            try:
                with urllib.request.urlopen(req, timeout=25) as response:
                    result = json.loads(response.read().decode('utf-8'))
                reply = result['choices'][0]['message']['content']
                return {'reply': reply, 'llm_configured': True}
            except (urllib.error.URLError, KeyError, ValueError, TimeoutError) as exc:
                raise HTTPException(status_code=502, detail=f'LLM request failed: {exc}')

        @api.get('/api/vision/latest', dependencies=[Depends(self.require_auth)])
        async def vision_latest():
            return {'detections': owner.snapshot().get('detections', []),
                    'camera_available': owner.jpeg() is not None}

        @api.get('/api/camera/snapshot', dependencies=[Depends(self.require_auth)])
        async def camera_snapshot():
            frame = owner.jpeg()
            if not frame:
                raise HTTPException(status_code=503, detail='No camera frame received from ROS camera node')
            return Response(content=frame, media_type='image/jpeg', headers={'Cache-Control': 'no-store'})

        async def websocket_auth(ws):
            token = ws.query_params.get('token', '')
            if not owner.token_ok(token):
                await ws.close(code=4401)
                return False
            return True

        @api.websocket('/ws/status')
        async def status_ws(ws: WebSocket):
            if not await websocket_auth(ws):
                return
            await ws.accept()
            try:
                while True:
                    await ws.send_json(owner.snapshot())
                    await asyncio.sleep(0.5)
            except WebSocketDisconnect:
                pass

        @api.websocket('/ws/camera')
        async def camera_ws(ws: WebSocket):
            if not await websocket_auth(ws):
                return
            await ws.accept()
            try:
                while True:
                    frame = owner.jpeg()
                    if frame:
                        await ws.send_bytes(frame)
                    await asyncio.sleep(1 / 12)
            except WebSocketDisconnect:
                pass
        return api

    def _start_http_server(self):
        host = str(self.get_parameter('host').value)
        port = int(self.get_parameter('port').value)
        config = uvicorn.Config(self.app, host=host, port=port, log_level='info', access_log=False)
        self.server = uvicorn.Server(config)
        self.server_thread = threading.Thread(target=self.server.run, name='robot-http-api', daemon=True)
        self.server_thread.start()
        self.get_logger().info(f'Robot API starting at http://{host}:{port}')

    def destroy_node(self):
        if self.server:
            self.server.should_exit = True
        if self.server_thread:
            self.server_thread.join(timeout=3)
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = RobotApiNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
