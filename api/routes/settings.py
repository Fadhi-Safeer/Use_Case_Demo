from fastapi import APIRouter
from fastapi.responses import JSONResponse

from api.runtime import cfg, update_cfg
from api.camera import CAMERA_DEVICE

router = APIRouter()

ALLOWED_KEYS = {
    "model",
    "num_predict",
    "max_image_size",
    "frame_interval",
    "job_timeout_seconds",
    "frame_timeout_seconds",
    "max_queue_size",
    "show_duplicate_results",
    "gear_system_prompt",
    "gear_user_prompt",
    "weapon_system_prompt",
    "weapon_user_prompt",
    "custom_system_prompt",
    "display_max_width",
    "display_jpeg_quality",
    "display_fps_cap",
}


def _current_settings():
    return {
        "model":                 cfg("model"),
        "num_predict":           cfg("num_predict"),
        "max_image_size":        cfg("max_image_size"),
        "frame_interval":        cfg("frame_interval"),
        "job_timeout_seconds":   cfg("job_timeout_seconds"),
        "frame_timeout_seconds": cfg("frame_timeout_seconds"),
        "max_queue_size":        cfg("max_queue_size"),
        "show_duplicate_results": cfg("show_duplicate_results"),
        "gear_system_prompt":    cfg("gear_system_prompt"),
        "gear_user_prompt":      cfg("gear_user_prompt"),
        "weapon_system_prompt":  cfg("weapon_system_prompt"),
        "weapon_user_prompt":    cfg("weapon_user_prompt"),
        "custom_system_prompt":  cfg("custom_system_prompt"),
        "camera_device":         CAMERA_DEVICE,
        "display_max_width":     cfg("display_max_width"),
        "display_jpeg_quality":  cfg("display_jpeg_quality"),
        "display_fps_cap":       cfg("display_fps_cap"),
    }


@router.get("/settings")
def get_settings():
    return JSONResponse(_current_settings())


@router.post("/settings")
async def post_settings(data: dict):
    for key, value in data.items():
        if key in ALLOWED_KEYS:
            update_cfg(key, value)
    return JSONResponse(_current_settings())
