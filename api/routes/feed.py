import time

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from api import state
from api.runtime import cfg

router = APIRouter()


@router.get("/video_feed")
def video_feed():
    def generate():
        while True:
            with state.frame_lock:
                frame = state.latest_frame_display or state.latest_frame
            if frame is None:
                time.sleep(0.05)
                continue
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            fps_cap = max(1, int(cfg("display_fps_cap")))
            time.sleep(1.0 / fps_cap)

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
