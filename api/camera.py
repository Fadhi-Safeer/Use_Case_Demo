import base64
import threading
import time

import cv2

from api import state

CAMERA_DEVICE = "/dev/video0"
CAMERA_INDEX = 0

_cap_lock = threading.Lock()
_cap = None


def _open_camera():
    global _cap
    cap = cv2.VideoCapture(CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    _cap = cap


def _camera_loop():
    global _cap
    _open_camera()
    while True:
        with _cap_lock:
            ret, frame = _cap.read()
            # frame = cv2.flip(frame, 1)
        if ret:
            jpg = encode_bytes(frame)
            with state.frame_lock:
                state.latest_frame = jpg
        time.sleep(0.033)  # ~30 fps


def start_camera():
    t = threading.Thread(target=_camera_loop, daemon=True)
    t.start()


def encode_bytes(frame_or_bytes, size=None, quality=80):
    """Return JPEG bytes. Accepts a numpy frame or raw bytes."""
    if isinstance(frame_or_bytes, (bytes, bytearray)):
        arr = cv2.imdecode(
            __import__("numpy").frombuffer(frame_or_bytes, __import__("numpy").uint8),
            cv2.IMREAD_COLOR,
        )
    else:
        arr = frame_or_bytes
    if size:
        arr = cv2.resize(arr, size)
    _, buf = cv2.imencode(".jpg", arr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return buf.tobytes()


def encode_b64(frame_bytes, size=None, quality=80):
    """Return base64-encoded JPEG string."""
    jpg = encode_bytes(frame_bytes, size=size, quality=quality)
    return base64.b64encode(jpg).decode("utf-8")
