import time

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from api import state

router = APIRouter()


@router.get("/video_feed")
def video_feed():
    def generate():
        while True:
            with state.frame_lock:
                frame = state.latest_frame
            if frame is None:
                time.sleep(0.05)
                continue
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            time.sleep(1 / 30)

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
