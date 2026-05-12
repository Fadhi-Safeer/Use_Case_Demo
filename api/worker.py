import asyncio
import time
from datetime import datetime

from api import state
from api.camera import encode_b64
from api.config import cfg
from api.inference import query


async def worker_loop():
    while True:
        if not state.job_queue:
            await asyncio.sleep(0.1)
            continue

        job_id, job = next(iter(state.job_queue.items()))

        async with state.processing_lock:
            job["status"] = "processing"
            frame_bytes = job["frame_bytes"]
            prompt = job["prompt"]

            t0 = time.time()
            try:
                size = int(cfg("max_image_size"))
                frame_b64 = encode_b64(frame_bytes, size=(size, size))
                # store thumbnail at fixed 96×64
                thumb_b64 = encode_b64(frame_bytes, size=(192, 128), quality=75)
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, lambda: query(frame_b64, prompt))
                elapsed = round(time.time() - t0, 1)
                job.update(
                    {
                        "status": "done",
                        "result": result,
                        "elapsed": elapsed,
                        "thumb": thumb_b64,
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                    }
                )
            except Exception as exc:
                elapsed = round(time.time() - t0, 1)
                job.update(
                    {
                        "status": "error",
                        "result": str(exc),
                        "elapsed": elapsed,
                        "thumb": None,
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                    }
                )

            # Move from queue → history
            state.job_queue.pop(job_id, None)

            finished = {k: v for k, v in job.items() if k != "frame_bytes"}
            state.history.insert(0, finished)
            if len(state.history) > state.HISTORY_MAX:
                state.history.pop()
