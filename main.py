import asyncio
import socket
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api import state
from api.camera import start_camera
from api.config import APP_HOST, APP_PORT
from api.routes.analyze import router as analyze_router
from api.routes.feed import router as feed_router
from api.routes.settings import router as settings_router
from api.worker import worker_loop

BASE_DIR = Path(__file__).parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    state.processing_lock = asyncio.Lock()
    start_camera()
    asyncio.create_task(worker_loop())
    yield


app = FastAPI(title="Robomy Live VLM", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

app.include_router(feed_router)
app.include_router(analyze_router)
app.include_router(settings_router)


@app.get("/")
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


if __name__ == "__main__":
    try:
        ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        ip = "localhost"
    print(f"\nRobomy Live VLM — http://{ip}:{APP_PORT}\n")
    uvicorn.run("main:app", host=APP_HOST, port=APP_PORT, reload=False)
