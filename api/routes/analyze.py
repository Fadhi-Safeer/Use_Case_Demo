import asyncio
import logging
import time
import uuid
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from api import state
from api.camera import encode_b64
from api.config import cfg
from api.inference import query
from api.yolo.detector import detect_people

router = APIRouter()

# ── Suppress poll noise ───────────────────────────────────────────────────────

class _SuppressPollingFilter(logging.Filter):
    _PATHS = {"/status", "/history"}

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(p in msg for p in self._PATHS)


logging.getLogger("uvicorn.access").addFilter(_SuppressPollingFilter())

# ── Use-case config ───────────────────────────────────────────────────────────

_USE_CASES = {
    "gear": {
        "system_key": "gear_system_prompt",
        "user_key":   "gear_user_prompt",
        "fixed_user": True,   # user prompt comes from settings, not request body
    },
    "weapon": {
        "system_key": "weapon_system_prompt",
        "user_key":   "weapon_user_prompt",
        "fixed_user": True,
    },
    "custom": {
        "system_key": "custom_system_prompt",
        "user_key":   None,
        "fixed_user": False,  # user prompt comes from request body
    },
}


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
    if interval not in (2.0, 3.0, 5.0, 10.0):
        interval = float(cfg("frame_interval"))

    if state.live_mode_running:
        return JSONResponse({"error": "Live mode already running"}, status_code=409)

    job_id = f"{use_case}-" + str(uuid.uuid4())[:6]
    state.live_mode_running = True
    state.active_prompt = prompt
    state.active_use_case = use_case

    # Insert placeholder so the card appears immediately
    state.history.insert(0, {
        "id":        job_id,
        "use_case":  use_case,
        "status":    "queued",
        "prompt":    prompt,
        "result":    None,
        "elapsed":   None,
        "thumb":     None,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
    })
    if len(state.history) > state.HISTORY_MAX:
        state.history.pop()

    async def live_loop():
        while state.live_mode_running:
            with state.frame_lock:
                frame = state.latest_frame

            if frame is None:
                await asyncio.sleep(interval)
                continue

            if state.processing_lock.locked():
                await asyncio.sleep(interval)
                continue

            entry = next((j for j in state.history if j["id"] == job_id), None)
            if entry:
                entry["status"] = "processing"
                entry["timestamp"] = datetime.now().strftime("%H:%M:%S")

            async with state.processing_lock:
                t0 = time.time()
                try:
                    size = int(cfg("max_image_size"))
                    thumb_b64 = encode_b64(frame, size=(192, 128), quality=75)
                    loop = asyncio.get_event_loop()

                    if cfg("enable_person_crop"):
                        max_p = int(cfg("yolo_max_persons"))
                        crops = await loop.run_in_executor(
                            None, lambda: detect_people(frame, max_persons=max_p)
                        )
                    else:
                        crops = []

                    if crops:
                        results = []
                        for crop_bytes in crops:
                            crop_b64 = encode_b64(crop_bytes)
                            r = await loop.run_in_executor(
                                None,
                                lambda cb=crop_b64: query(cb, prompt, system_prompt=system_prompt),
                            )
                            results.append(r)
                        result = (
                            "\n".join(f"Person {i+1}: {r}" for i, r in enumerate(results))
                            if len(results) > 1
                            else results[0]
                        )
                    else:
                        frame_b64 = encode_b64(frame, size=(size, size))
                        result = await loop.run_in_executor(
                            None,
                            lambda: query(frame_b64, prompt, system_prompt=system_prompt),
                        )

                    elapsed = round(time.time() - t0, 1)
                    if entry:
                        entry.update({
                            "status":  "done",
                            "result":  result,
                            "elapsed": elapsed,
                            "thumb":   thumb_b64,
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                        })
                except Exception as exc:
                    elapsed = round(time.time() - t0, 1)
                    if entry:
                        entry.update({
                            "status":  "error",
                            "result":  str(exc),
                            "elapsed": elapsed,
                            "thumb":   None,
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                        })

            if not state.live_mode_running:
                break
            for _ in range(int(interval * 10)):
                if not state.live_mode_running:
                    break
                await asyncio.sleep(0.1)

        entry = next((j for j in state.history if j["id"] == job_id), None)
        if entry and entry["status"] == "processing":
            entry["status"] = "done"

    state.live_mode_task = asyncio.create_task(live_loop())
    return JSONResponse({
        "job_id":    job_id,
        "use_case":  use_case,
        "status":    "started",
        "interval":  interval,
        "prompt":    prompt,
    })


# ── /stop_live ────────────────────────────────────────────────────────────────

@router.post("/stop_live")
async def stop_live():
    state.live_mode_running = False
    state.active_prompt = ""
    state.active_use_case = ""
    if state.live_mode_task and not state.live_mode_task.done():
        state.live_mode_task.cancel()
        try:
            await state.live_mode_task
        except asyncio.CancelledError:
            pass
    state.live_mode_task = None
    return JSONResponse({"status": "stopped"})


# ── /status ───────────────────────────────────────────────────────────────────

@router.get("/status")
def status():
    with state.frame_lock:
        camera_ok = state.latest_frame is not None

    return JSONResponse({
        "camera_ok":    camera_ok,
        "live_mode":    state.live_mode_running,
        "active_prompt": state.active_prompt,
        "active_use_case": getattr(state, "active_use_case", ""),
        "queue_size":   len(state.job_queue),
    })


# ── /history ──────────────────────────────────────────────────────────────────

@router.get("/history")
def history():
    return JSONResponse({"jobs": list(state.history)})
