import asyncio
import collections
import threading
from collections import OrderedDict

from api.alert_manager import AlertManager
from api.config import (
    ALERT_CONSECUTIVE_THRESHOLD,
    ALERT_MAX_GAP_SECONDS,
    ALERT_SOUND_PATH,
)

processing_lock: asyncio.Lock = None   # initialised in main.py lifespan

latest_frame: bytes = None
frame_lock = threading.Lock()

job_queue: OrderedDict = OrderedDict()
history: list = []

HISTORY_MAX = 100

live_mode_running: bool = False
live_mode_task = None
active_prompt: str = ""
active_use_case: str = ""   # "gear" | "weapon" | "custom" | ""

alert_manager = AlertManager(
    consecutive_threshold=ALERT_CONSECUTIVE_THRESHOLD,
    max_gap_seconds=ALERT_MAX_GAP_SECONDS,
    sound_path=ALERT_SOUND_PATH,
)

# ── Queue / inference stats (updated by analyze.py) ──────────────────────────
queue_depth: int = 0
queue_peak: int = 0
last_inference_latency_ms: int = None
avg_inference_latency_ms: int = None
consumer_idle_seconds: float = None
cancelled_count: int = 0
last_session_summary: dict = None

_latency_window: collections.deque = collections.deque(maxlen=10)
_consumer_last_complete_ts: float = None   # monotonic timestamp
