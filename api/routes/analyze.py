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

router = APIRouter()


class _SuppressPollingFilter(logging.Filter):
    _PATHS = {"/status", "/history"}

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(p in msg for p in self._PATHS)


logging.getLogger("uvicorn.access").addFilter(_SuppressPollingFilter())


@router.post("/analyze")
async def analyze(data: dict):
    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        return JSONResponse({"error": "No prompt"}, status_code=400)

    with state.frame_lock:
        frame = state.latest_frame

    if frame is None:
        return JSONResponse({"error": "No camera frame available"}, status_code=503)

    job_id = str(uuid.uuid4())[:8]
    state.job_queue[job_id] = {
        "id": job_id,
        "status": "queued",
        "prompt": prompt,
        "frame_bytes": frame,
        "thumb": None,
        "result": None,
        "elapsed": None,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
    }
    return JSONResponse({"job_id": job_id, "status": "queued"})


@router.post("/start_live")
async def start_live(data: dict):
    prompt = (data.get("prompt") or "").strip()
    interval = float(data.get("interval_seconds") or 3.0)
    if interval not in (2.0,3.0, 5.0, 10.0):
        interval = 3.0
    if not prompt:
        return JSONResponse({"error": "No prompt"}, status_code=400)

    if state.live_mode_running:
        return JSONResponse({"error": "Live mode already running"}, status_code=409)

    job_id = "live-" + str(uuid.uuid4())[:6]
    state.live_mode_running = True
    state.active_prompt = prompt

    # Insert placeholder into history so the card appears immediately
    state.history.insert(0, {
        "id": job_id,
        "status": "queued",
        "prompt": prompt,
        "result": None,
        "elapsed": None,
        "thumb": None,
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

            # Skip cycle if GPU is already busy
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
                    frame_b64 = encode_b64(frame, size=(size, size))
                    thumb_b64 = encode_b64(frame, size=(192, 128), quality=75)
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(None, lambda: query(frame_b64, prompt))
                    elapsed = round(time.time() - t0, 1)
                    if entry:
                        entry.update({
                            "status": "done",
                            "result": result,
                            "elapsed": elapsed,
                            "thumb": thumb_b64,
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                        })
                except Exception as exc:
                    elapsed = round(time.time() - t0, 1)
                    if entry:
                        entry.update({
                            "status": "error",
                            "result": str(exc),
                            "elapsed": elapsed,
                            "thumb": None,
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                        })

            if not state.live_mode_running:
                break
            # Sleep in small chunks so stop is responsive
            for _ in range(int(interval * 10)):
                if not state.live_mode_running:
                    break
                await asyncio.sleep(0.1)

        # Ensure card doesn't stay stuck on "processing" after stop
        entry = next((j for j in state.history if j["id"] == job_id), None)
        if entry and entry["status"] == "processing":
            entry["status"] = "done"

    state.live_mode_task = asyncio.create_task(live_loop())
    return JSONResponse({"job_id": job_id, "status": "started", "interval": interval})


@router.post("/stop_live")
async def stop_live():
    state.live_mode_running = False
    state.active_prompt = ""
    if state.live_mode_task and not state.live_mode_task.done():
        state.live_mode_task.cancel()
        try:
            await state.live_mode_task
        except asyncio.CancelledError:
            pass
    state.live_mode_task = None
    return JSONResponse({"status": "stopped"})


@router.get("/status")
def status():
    with state.frame_lock:
        camera_ok = state.latest_frame is not None

    processing_id = None
    queued_ids = []
    for jid, job in state.job_queue.items():
        if job["status"] == "processing":
            processing_id = jid
        else:
            queued_ids.append(jid)

    jobs = [
        {"id": jid, "status": job["status"], "prompt": job["prompt"]}
        for jid, job in state.job_queue.items()
    ]

    return JSONResponse(
        {
            "camera_ok": camera_ok,
            "processing": processing_id,
            "queued": queued_ids,
            "queue_size": len(state.job_queue),
            "jobs": jobs,
            "live_mode": state.live_mode_running,
            "active_prompt": state.active_prompt,
        }
    )


@router.get("/history")
def history():
    return JSONResponse({"jobs": list(state.history)})
