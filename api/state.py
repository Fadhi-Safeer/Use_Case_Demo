import asyncio
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

HISTORY_MAX = 50

live_mode_running: bool = False
live_mode_task = None
active_prompt: str = ""
active_use_case: str = ""   # "gear" | "weapon" | "custom" | ""

alert_manager = AlertManager(
    consecutive_threshold=ALERT_CONSECUTIVE_THRESHOLD,
    max_gap_seconds=ALERT_MAX_GAP_SECONDS,
    sound_path=ALERT_SOUND_PATH,
)
