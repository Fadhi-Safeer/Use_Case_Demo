from fastapi import APIRouter
from fastapi.responses import JSONResponse

from api.config import cfg, update_cfg
from api.camera import CAMERA_DEVICE

router = APIRouter()

ALLOWED_KEYS = {"model", "num_predict", "max_image_size", "system_prompt"}


@router.get("/settings")
def get_settings():
    return JSONResponse(
        {
            "model": cfg("model"),
            "num_predict": cfg("num_predict"),
            "max_image_size": cfg("max_image_size"),
            "system_prompt": cfg("system_prompt"),
            "camera_device": CAMERA_DEVICE,
        }
    )


@router.post("/settings")
async def post_settings(data: dict):
    for key, value in data.items():
        if key in ALLOWED_KEYS:
            update_cfg(key, value)
    return JSONResponse(
        {
            "model": cfg("model"),
            "num_predict": cfg("num_predict"),
            "max_image_size": cfg("max_image_size"),
            "system_prompt": cfg("system_prompt"),
            "camera_device": CAMERA_DEVICE,
        }
    )
