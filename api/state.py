import asyncio
import threading
from collections import OrderedDict

processing_lock: asyncio.Lock = None  # initialised in main.py on startup

latest_frame: bytes = None
frame_lock = threading.Lock()

job_queue: OrderedDict = OrderedDict()
history: list = []

HISTORY_MAX = 50

live_mode_running: bool = False
live_mode_task = None
active_prompt: str = ""
