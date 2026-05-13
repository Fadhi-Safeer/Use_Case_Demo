from ultralytics import YOLO
import cv2
import numpy as np

MODEL_PATH = "models/person_detection_model.engine"
_model = None


def load_model():
    """Call once at startup from main.py lifespan."""
    global _model
    _model = YOLO(MODEL_PATH, task="detect")


def detect_people(frame_bytes: bytes, conf: float = 0.5, max_persons: int = 2) -> list:
    """JPEG bytes in → list of JPEG crop bytes out. Empty list = no persons found."""
    if _model is None:
        raise RuntimeError("YOLO model not loaded. Call load_model() first.")
    nparr = np.frombuffer(frame_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    results = _model(frame, conf=conf, classes=[0], verbose=False)
    crops = []
    for i, box in enumerate(results[0].boxes):
        if i >= max_persons:
            break
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)
        crop = frame[y1:y2, x1:x2]
        _, enc = cv2.imencode(".jpg", crop)
        crops.append(enc.tobytes())
    return crops
