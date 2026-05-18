import asyncio
import dataclasses
import logging
import time
from datetime import datetime

import api.session as session
from api import state
from api.camera import encode_b64
from api.runtime import cfg
from api.inference import query

log = logging.getLogger(__name__)

# ── Queue item ────────────────────────────────────────────────────────────────

@dataclasses.dataclass
class CaptureItem:
    frame_jpg:     bytes   # JPEG bytes (~150KB) from state.latest_frame
    capture_ts:    float   # time.monotonic() at capture moment
    seq_num:       int     # monotonically increasing per session
    session_id:    str     # e.g. "gear-a1b2c3"
    use_case:      str
    prompt:        str
    system_prompt: str

# Warning tiers (depth threshold, log level, message)
_WARN_TIERS = [
    (20,  logging.INFO,    "inference lagging behind capture"),
    (50,  logging.WARNING, "inference significantly behind, queue growing"),
    (100, logging.ERROR,   "inference severely lagged, investigate"),
]


def _reset_session_stats():
    session.last_warned_tier             = 0
    session.stuck_warning_fired          = False
    session.session_start_ts             = time.monotonic()
    session.total_captured               = 0
    session.total_inferred               = 0
    state.queue_depth             = 0
    state.queue_peak              = 0
    state.cancelled_count         = 0
    state.last_inference_latency_ms = None
    state.avg_inference_latency_ms  = None
    state.consumer_idle_seconds     = None
    state._consumer_last_complete_ts = None
    state._latency_window.clear()


def _check_queue_warnings(queue: asyncio.Queue):
    depth = queue.qsize()
    # Find highest crossed tier
    fired_tier, fired_level, fired_msg = 0, 0, ""
    for threshold, level, msg in _WARN_TIERS:
        if depth >= threshold:
            fired_tier, fired_level, fired_msg = threshold, level, msg
    # Rising edge only
    if fired_tier > session.last_warned_tier:
        log.log(fired_level, f"[queue] depth={depth}: {fired_msg}")
        session.last_warned_tier = fired_tier


def _record_latency(latency_ms: float):
    state._latency_window.append(latency_ms)
    state.last_inference_latency_ms = int(latency_ms)
    state.avg_inference_latency_ms  = int(
        sum(state._latency_window) / len(state._latency_window)
    )


def _make_history_entry(item: CaptureItem, status: str = "queued") -> dict:
    return {
        "id":          f"{item.session_id}-{item.seq_num}",
        "session_id":  item.session_id,
        "use_case":    item.use_case,
        "status":      status,
        "prompt":      item.prompt,
        "result":      None,
        "elapsed":     None,
        "latency_ms":  None,
        "thumb":       None,
        "timestamp":   datetime.now().strftime("%H:%M:%S"),
        "alert_fired": False,
        "seq_num":     item.seq_num,
    }


def _insert_history_entry(item: CaptureItem, status: str = "queued"):
    state.history.insert(0, _make_history_entry(item, status))
    if len(state.history) > state.HISTORY_MAX:
        state.history.pop()


def _find_history_entry(session_id: str, seq_num: int):
    entry_id = f"{session_id}-{seq_num}"
    return next((j for j in state.history if j["id"] == entry_id), None)


def _on_inference_stuck(depth: int, idle_seconds: float):
    """Hook point for future watchdog. No-op."""
    pass


# ── Producer coroutine ────────────────────────────────────────────────────────

async def _producer(queue: asyncio.Queue, session_id: str, use_case: str,
                    prompt: str, system_prompt: str, interval: float):
    seq = 0
    next_capture = time.monotonic()

    while state.live_mode_running:
        now = time.monotonic()
        sleep_for = max(0.0, next_capture - now)
        if sleep_for > 0:
            await asyncio.sleep(sleep_for)

        if not state.live_mode_running:
            break

        with state.frame_lock:
            frame = state.latest_frame

        if frame is not None:
            seq += 1
            session.total_captured += 1
            item = CaptureItem(
                frame_jpg=frame,
                capture_ts=time.monotonic(),
                seq_num=seq,
                session_id=session_id,
                use_case=use_case,
                prompt=prompt,
                system_prompt=system_prompt,
            )
            queue.put_nowait(item)
            _insert_history_entry(item)

            state.queue_depth = queue.qsize()
            if state.queue_depth > state.queue_peak:
                state.queue_peak = state.queue_depth
            _check_queue_warnings(queue)

        next_capture += interval   # absolute schedule — no drift


# ── Consumer coroutine ────────────────────────────────────────────────────────

async def _consumer(queue: asyncio.Queue):

    while True:
        try:
            item = await asyncio.wait_for(queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            state.queue_depth = queue.qsize()
            if not state.live_mode_running and queue.empty():
                break
            # Update idle seconds
            if state._consumer_last_complete_ts is not None:
                idle = time.monotonic() - state._consumer_last_complete_ts
                state.consumer_idle_seconds = round(idle, 1)
                # Stuck detection (rising edge)
                if idle > 30 and not queue.empty() and not session.stuck_warning_fired:
                    log.error(
                        f"[queue] inference appears stuck, last completed {idle:.0f}s ago, "
                        f"queue depth={queue.qsize()}"
                    )
                    session.stuck_warning_fired = True
                    _on_inference_stuck(queue.qsize(), idle)
            continue

        # Got an item — run inference
        session.stuck_warning_fired = False
        state.queue_depth = queue.qsize()

        entry = _find_history_entry(item.session_id, item.seq_num)
        if entry:
            entry["status"]    = "processing"
            entry["timestamp"] = datetime.now().strftime("%H:%M:%S")

        async with state.processing_lock:
            t0 = time.time()
            try:
                w         = int(cfg("max_image_size"))
                h         = w * 9 // 16
                frame_b64 = encode_b64(item.frame_jpg, size=(w, h))
                thumb_b64 = encode_b64(item.frame_jpg, size=(96, 64), quality=25)

                result    = await query(frame_b64, item.prompt, system_prompt=item.system_prompt)
                elapsed    = round(time.time() - t0, 1)
                latency_ms = int((time.monotonic() - item.capture_ts) * 1000)
                _record_latency(latency_ms)

                yes_response = result.strip().lower().startswith("yes")
                is_threat    = (not yes_response) if item.use_case == "gear" else yes_response
                alert_fired  = state.alert_manager.update(is_threat)

                if entry:
                    entry.update({
                        "status":      "done",
                        "result":      result,
                        "elapsed":     elapsed,
                        "latency_ms":  latency_ms,
                        "thumb":       thumb_b64,
                        "timestamp":   datetime.now().strftime("%H:%M:%S"),
                        "alert_fired": alert_fired,
                    })

            except Exception as exc:
                elapsed = round(time.time() - t0, 1)
                if entry:
                    entry.update({
                        "status":    "error",
                        "result":    str(exc),
                        "elapsed":   elapsed,
                        "latency_ms": None,
                        "thumb":     None,
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                    })

        session.total_inferred += 1
        state._consumer_last_complete_ts = time.monotonic()
        state.consumer_idle_seconds      = 0.0
        state.queue_depth                = queue.qsize()


# ── Shutdown sequence ─────────────────────────────────────────────────────────

async def _shutdown_session(session_id: str):

    # Step 2: wait for producer to exit (exits at next cadence tick)
    if session.producer_task and not session.producer_task.done():
        try:
            await asyncio.wait_for(
                asyncio.shield(session.producer_task),
                timeout=float(cfg("frame_interval")) + 2.0,
            )
        except asyncio.TimeoutError:
            session.producer_task.cancel()
            try:
                await session.producer_task
            except asyncio.CancelledError:
                pass

    # Step 3: flush remaining queue — mark each item as "cancelled"
    queue = session.inference_queue
    cancelled = 0
    if queue is not None:
        while not queue.empty():
            try:
                item = queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            entry = _find_history_entry(item.session_id, item.seq_num)
            if entry:
                entry.update({
                    "status":      "cancelled",
                    "timestamp":   datetime.now().strftime("%H:%M:%S"),
                })
            else:
                _insert_history_entry(item, status="cancelled")
            cancelled += 1

    state.cancelled_count = cancelled
    state.queue_depth     = 0

    # Step 4: wait for consumer to finish in-flight inference then exit
    if session.consumer_task and not session.consumer_task.done():
        try:
            await asyncio.wait_for(
                asyncio.shield(session.consumer_task),
                timeout=35.0,   # one INFERENCE_TIMEOUT (30s) + 5s buffer
            )
        except asyncio.TimeoutError:
            session.consumer_task.cancel()
            try:
                await session.consumer_task
            except asyncio.CancelledError:
                pass

    # Step 5: emit session summary
    duration = round(time.monotonic() - session.session_start_ts, 1)
    summary  = {
        "session_id":               session_id,
        "total_captured":           session.total_captured,
        "total_inferred":           session.total_inferred,
        "total_cancelled":          cancelled,
        "peak_queue_depth":         state.queue_peak,
        "avg_inference_latency_ms": state.avg_inference_latency_ms,
        "duration_seconds":         duration,
    }
    state.last_session_summary = summary
    log.info(f"[session] ended: {summary}")

    session.producer_task = None
    session.consumer_task = None
