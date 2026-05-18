import asyncio
import logging
import time
import uuid

from fastapi import APIRouter
from fastapi.responses import JSONResponse

import api.session as session
from api import state
from api.runtime import cfg, _USE_CASES
from api.routes.live_session import (
    _producer, _consumer, _shutdown_session,
    _reset_session_stats, CaptureItem,
)

router = APIRouter()
log = logging.getLogger(__name__)

# ── Suppress poll noise ───────────────────────────────────────────────────────

class _SuppressPollingFilter(logging.Filter):
    _PATHS = {"/status", "/history"}

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(p in msg for p in self._PATHS)


logging.getLogger("uvicorn.access").addFilter(_SuppressPollingFilter())


# ── /start_live ───────────────────────────────────────────────────────────────

@router.post("/start_live")
async def start_live(data: dict):
    use_case = (data.get("use_case") or "custom").lower()
    if use_case not in _USE_CASES:
        use_case = "custom"

    uc = _USE_CASES[use_case]
    system_prompt = cfg(uc["system_key"])

    if uc["fixed_user"]:
        prompt = cfg(uc["user_key"])
    else:
        prompt = (data.get("prompt") or "").strip()
        if not prompt:
            return JSONResponse({"error": "No prompt provided"}, status_code=400)

    interval = float(data.get("interval_seconds") or cfg("frame_interval"))
    if interval not in (2.0, 3.0, 5.0):
        interval = float(cfg("frame_interval"))

    if state.live_mode_running:
        return JSONResponse({"error": "Live mode already running"}, status_code=409)

    session_id                 = f"{use_case}-" + str(uuid.uuid4())[:6]
    session.current_session_id = session_id
    session.current_use_case   = use_case

    state.live_mode_running = True
    state.active_prompt     = prompt
    state.active_use_case   = use_case

    _reset_session_stats()

    session.inference_queue = asyncio.Queue()
    session.producer_task   = asyncio.create_task(
        _producer(session.inference_queue, session_id, use_case, prompt, system_prompt, interval)
    )
    session.consumer_task   = asyncio.create_task(
        _consumer(session.inference_queue)
    )
    state.live_mode_task = session.producer_task

    return JSONResponse({
        "job_id":    session_id,   # frontend stores as liveSessionId
        "use_case":  use_case,
        "status":    "started",
        "interval":  interval,
        "prompt":    prompt,
    })


# ── /stop_live ────────────────────────────────────────────────────────────────

@router.post("/stop_live")
async def stop_live():
    if not state.live_mode_running:
        return JSONResponse({"status": "stopped"})

    # Step 1: signal producer (immediate)
    state.live_mode_running = False
    state.active_prompt     = ""
    state.active_use_case   = ""
    state.live_mode_task    = None

    # Background cleanup — UI does not block on this
    asyncio.create_task(_shutdown_session(session.current_session_id))
    return JSONResponse({"status": "stopping"})


# ── /status ───────────────────────────────────────────────────────────────────

@router.get("/status")
def status():
    with state.frame_lock:
        camera_ok = state.latest_frame is not None

    idle = None
    if state._consumer_last_complete_ts is not None:
        idle = round(time.monotonic() - state._consumer_last_complete_ts, 1)

    return JSONResponse({
        "camera_ok":                 camera_ok,
        "live_mode":                 state.live_mode_running,
        "active_prompt":             state.active_prompt,
        "active_use_case":           getattr(state, "active_use_case", ""),
        "queue_depth":               state.queue_depth,
        "queue_peak":                state.queue_peak,
        "last_inference_latency_ms": state.last_inference_latency_ms,
        "avg_inference_latency_ms":  state.avg_inference_latency_ms,
        "consumer_idle_seconds":     idle,
        "cancelled_count":           state.cancelled_count,
    })


# ── /history ──────────────────────────────────────────────────────────────────

@router.get("/history")
def history():
    payload = {"jobs": list(state.history)}
    if state.last_session_summary is not None:
        payload["session_summary"] = state.last_session_summary
    return JSONResponse(payload)
